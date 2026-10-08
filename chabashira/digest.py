"""フェーズ1：週刊の入札速報を作る。

1. 官公需APIで、指定業種×地域の直近7日の役務案件を集める
2. Claude が1件ずつ「何の仕事か・参加資格・必要な実績・締切」を要約する
3. メール本文（テキストとHTML）を out/ に書き出す

送信はしない。配信前に人が out/ の本文を検品する（フェーズ1の運用）。

使い方:
    python -m chabashira.digest --industry 清掃 --prefs 大阪府 兵庫県
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from . import kkj
from .survey import collect

OUT_DIR = Path(__file__).parent / "out"
MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """あなたは官公庁の入札公告を、中小の事業者向けに要約する担当者です。
読み手は、自社が応札できる案件かを30秒で判断したい経営者です。
公告に書かれていることだけを使い、書かれていない項目は「公告に記載なし」と書いてください。
推測で補ったり、金額や日付を作ったりしないでください。"""

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "work": {"type": "string", "description": "何の仕事か。場所と期間を含めて1〜2文"},
        "qualification": {"type": "string", "description": "参加資格（入札参加資格の等級や業種登録など）"},
        "experience": {"type": "string", "description": "必要な実績や資格者"},
        "deadline": {"type": "string", "description": "申込や入札の締切日時"},
        "note": {"type": "string", "description": "注意点を1文。なければ空文字"},
    },
    "required": ["work", "qualification", "experience", "deadline", "note"],
    "additionalProperties": False,
}


@dataclass
class Summary:
    notice: kkj.Notice
    work: str
    qualification: str
    experience: str
    deadline: str
    note: str


def summarize(notice: kkj.Notice, client=None) -> Summary:
    """Claude で公告を要約する。拒否された場合は要約なしで原文リンクだけ残す。"""
    import anthropic

    client = client or anthropic.Anthropic()
    source = "\n".join(f"{k}: {v}" for k, v in notice.fields.items() if v)
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": SUMMARY_SCHEMA},
        },
        messages=[{"role": "user", "content": f"次の入札公告を要約してください。\n\n{source}"}],
    )
    if response.stop_reason == "refusal":
        data = {key: "要約できませんでした。原文を確認してください" for key in SUMMARY_SCHEMA["required"]}
        data["note"] = ""
    else:
        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)
    return Summary(notice=notice, **data)


def render_text(industry: str, prefs: list[str], summaries: list[Summary], start: date, end: date) -> str:
    lines = [
        f"【{industry}の入札速報】{'・'.join(prefs)} {start:%m/%d}〜{end:%m/%d}公示分 {len(summaries)}件",
        "",
    ]
    for i, s in enumerate(summaries, 1):
        n = s.notice
        lines += [
            f"■{i}. {n.get('title')}",
            f"発注：{n.get('organization')}（{n.get('prefecture')}{n.get('city')}）",
            f"仕事：{s.work}",
            f"資格：{s.qualification}",
            f"実績：{s.experience}",
            f"締切：{s.deadline}",
        ]
        if s.note:
            lines.append(f"注意：{s.note}")
        lines += [f"原文：{n.get('url')}", ""]
    lines += [
        "要約はAIによるもので、誤りを含む場合があります。応札の判断は必ず原文で行ってください。",
        "出典：官公需情報ポータルサイト（中小企業庁） https://www.kkj.go.jp/",
    ]
    return "\n".join(lines)


def render_html(industry: str, prefs: list[str], summaries: list[Summary], start: date, end: date) -> str:
    e = html.escape
    items = []
    for s in summaries:
        n = s.notice
        note = f"<p><b>注意</b> {e(s.note)}</p>" if s.note else ""
        items.append(f"""
<div style="border-top:1px solid #ddd;padding:16px 0">
  <h3 style="margin:0 0 4px;font-size:16px">{e(n.get('title'))}</h3>
  <p style="margin:0 0 8px;color:#666;font-size:13px">{e(n.get('organization'))}（{e(n.get('prefecture'))}{e(n.get('city'))}）</p>
  <p><b>仕事</b> {e(s.work)}</p>
  <p><b>資格</b> {e(s.qualification)}</p>
  <p><b>実績</b> {e(s.experience)}</p>
  <p><b>締切</b> {e(s.deadline)}</p>
  {note}
  <p><a href="{e(n.get('url'))}">公告の原文を開く</a></p>
</div>""")
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><title>{e(industry)}の入札速報</title></head>
<body style="font-family:sans-serif;max-width:640px;margin:auto;padding:16px;line-height:1.6;color:#222">
<h2 style="font-size:18px">{e(industry)}の入札速報</h2>
<p>{e('・'.join(prefs))}　{start:%m/%d}〜{end:%m/%d}公示分　{len(summaries)}件</p>
{''.join(items)}
<p style="font-size:12px;color:#666;border-top:1px solid #ddd;padding-top:12px">
要約はAIによるもので、誤りを含む場合があります。応札の判断は必ず原文で行ってください。<br>
出典：<a href="https://www.kkj.go.jp/">官公需情報ポータルサイト（中小企業庁）</a><br>
発行：茶柱　{{{{送信者の住所}}}}　{{{{問い合わせ先}}}}<br>
配信停止：{{{{配信停止リンク}}}}
</p>
</body></html>"""


def build(industry: str, prefs: list[str], days: int = 7, today: date | None = None,
          search=kkj.search, pause=kkj.polite_pause, summarizer=summarize) -> tuple[str, str, int]:
    today = today or date.today()
    start = today - timedelta(days=days)
    notices: dict[str, kkj.Notice] = {}
    for pref in prefs:
        notices.update(collect(industry, pref, start, today, search, pause))
    ordered = sorted(notices.values(), key=lambda n: n.get("deadline") or "9999")
    summaries = [summarizer(n) for n in ordered]
    return (render_text(industry, prefs, summaries, start, today),
            render_html(industry, prefs, summaries, start, today),
            len(summaries))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="週刊の入札速報を作る")
    parser.add_argument("--industry", required=True)
    parser.add_argument("--prefs", nargs="+", required=True)
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args(argv)

    text, page, count = build(args.industry, args.prefs, args.days)
    OUT_DIR.mkdir(exist_ok=True)
    stem = f"digest_{args.industry}_{date.today().isoformat()}"
    (OUT_DIR / f"{stem}.txt").write_text(text, encoding="utf-8")
    (OUT_DIR / f"{stem}.html").write_text(page, encoding="utf-8")
    print(f"{count}件を要約しました: {OUT_DIR / stem}.txt / .html", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
