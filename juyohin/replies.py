"""返信の照合・分類・報告。

照合：In-Reply-To / References の Message-ID → 送った台帳の行。見つからなければ差出人アドレスで照合。
分類：「配信停止」はキーワードで即判定（取りこぼすと法令違反になるので AI に任せない）。
     それ以外は Claude が分類する。
報告：資料請求・興味あり・質問は「電話すべき先」として、社寺名・電話の材料と一緒に通知する。
"""

from __future__ import annotations

import json
import re
import sqlite3

import requests

from . import db
from .mailer import Incoming

MODEL = "claude-opus-5-5"

CLASSES = {
    "request": "資料請求",
    "interested": "興味あり",
    "question": "質問",
    "decline": "不要",
    "unsubscribe": "配信停止",
    "auto": "自動返信",
    "other": "その他",
}
HOT = {"request", "interested", "question"}

UNSUBSCRIBE = re.compile(r"配信停止|配信不要|送らないで|送信しないで|今後.{0,10}(不要|ご遠慮|お断り)|迷惑メール|unsubscribe", re.I)
AUTO_REPLY = re.compile(r"自動(返信|応答)|不在|休暇|auto[- ]?reply|out of office", re.I)

SYSTEM_PROMPT = """あなたは営業メールへの返信を仕分ける担当者です。
送ったのは、神社仏閣へのオリジナル授与品のご案内で、「資料希望」と返信してもらうことをお願いしています。
返信の本文から、分類と要約を返してください。
- request: 資料・カタログ・見積・サンプルを求めている
- interested: 資料の要求はないが前向き（話を聞きたい、検討する、電話がほしい等）
- question: 質問がある（価格、ロット、納期など）
- decline: 不要・間に合っている・取引先がある
- unsubscribe: 今後の連絡を断っている
- auto: 自動返信・不在通知
- other: どれにも当たらない
summary は、電話をかける前に読む一文。相手が何を求めているか、担当者名や電話番号が書かれていればそれも。"""

SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "enum": list(CLASSES)},
        "summary": {"type": "string"},
    },
    "required": ["label", "summary"],
    "additionalProperties": False,
}


def strip_quote(body: str) -> str:
    """引用部分（> で始まる行・「〜wrote:」以降）を落とし、相手が書いた部分だけにする。"""
    lines = []
    for line in body.splitlines():
        if re.match(r"\s*>", line) or re.search(r"(wrote:|のメッセージ:|-----Original Message-----|^\s*On .+ wrote)", line):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def classify(body: str, client=None) -> tuple[str, str]:
    own = strip_quote(body)
    if UNSUBSCRIBE.search(own):
        return "unsubscribe", own[:120]
    if AUTO_REPLY.search(own[:300]):
        return "auto", own[:120]
    import anthropic

    client = client or anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": own[:6000]}],
    )
    if response.stop_reason == "refusal":
        return "other", own[:120]
    data = json.loads(next(b.text for b in response.content if b.type == "text"))
    return data["label"], data["summary"]


def match(conn: sqlite3.Connection, inc: Incoming) -> sqlite3.Row | None:
    ids = inc.raw_ids_in_body if inc.is_bounce else inc.in_reply_to
    for mid in ids:
        row = conn.execute(
            "SELECT * FROM targets WHERE message_id = ? OR followup_id = ?", (mid, mid)
        ).fetchone()
        if row:
            return row
    if not inc.is_bounce:
        return conn.execute(
            "SELECT * FROM targets WHERE email = ? AND status IN ('sent', 'followed')", (inc.from_addr,)
        ).fetchone()
    return None


def process(conn: sqlite3.Connection, incoming: list[Incoming], classifier=classify) -> list[dict]:
    """返信を台帳に反映し、報告すべきものを返す。"""
    reports = []
    for inc in incoming:
        row = match(conn, inc)
        if row is None or row["status"] in ("replied", "bounced"):
            continue
        if inc.is_bounce:
            db.update(conn, row["place_id"], status="bounced")
            db.suppress(conn, row["email"], "bounced")
            continue
        label, summary = classifier(inc.body)
        if label == "auto":
            continue  # 自動返信は返信扱いにしない（追いメールの対象に残す）
        db.update(conn, row["place_id"], status="replied", reply_class=label, reply_summary=summary,
                  replied_at=db.now())
        if label in ("unsubscribe", "decline"):
            db.suppress(conn, row["email"], label)
        reports.append({"row": dict(row), "label": label, "summary": summary, "subject": inc.subject})
    conn.commit()
    return reports


def render_report(reports: list[dict]) -> str:
    hot = [r for r in reports if r["label"] in HOT]
    rest = [r for r in reports if r["label"] not in HOT]
    lines = [f"【授与品メール 返信報告】電話すべき先 {len(hot)}件 / その他 {len(rest)}件", ""]
    for r in hot:
        t = r["row"]
        lines += [
            f"■ {CLASSES[r['label']]}｜{t['name']}（{t['prefecture']}）",
            f"  要約：{r['summary']}",
            f"  住所：{t['address']}",
            f"  サイト：{t['website']}",
            f"  返信元：{t['email']}",
            "",
        ]
    if rest:
        lines.append("― その他 ―")
        lines += [f"・{CLASSES[r['label']]}｜{r['row']['name']}：{r['summary']}" for r in rest]
    return "\n".join(lines)


def post_webhook(url: str, text: str) -> None:
    if url:
        requests.post(url, json={"text": text, "content": {"type": "text", "text": text}}, timeout=20)
