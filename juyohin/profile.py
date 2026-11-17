"""公式サイトの本文から、文面に使う材料を Claude で読み取る。

誤った御祭神や神使への言及は致命傷なので、二重に守る。
  1. 本文に書かれていることだけを使わせ、根拠の引用（evidence）を必ず付けさせる
  2. 引用が実際に本文に含まれるかをコードで照合し、含まれなければその項目を捨てる
"""

from __future__ import annotations

import json
import re

MODEL = "claude-opus-5-5"

LINEAGES = ["inari", "tenmangu", "hachiman", "shinmei", "kannon_jizo", "other", "unknown"]

SYSTEM_PROMPT = """あなたは神社仏閣の公式サイトを読み、授与品の提案メールの下調べをする担当者です。
渡された本文に書かれていることだけを使ってください。書かれていないことは推測せず、空にしてください。
御祭神・御本尊・系列を取り違えることは、相手への大変な失礼になります。少しでも確信が持てなければ unknown にしてください。

personal_line は、メールの名乗りの直後に入れる一文です。
- 「学問の神様として多くの受験生が参拝される貴社に、」（寺院なら「貴寺院様に、」）のように、「に、」で終わる一文
- 事実だけ。褒めすぎない。調べた感を出しすぎない
- 根拠になる本文の一節を evidence に、本文から一字一句そのまま抜き出してください（20〜60字）
- 適切な一文が作れなければ personal_line と evidence は空にしてください"""

PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["shrine", "temple", "unknown"]},
        "deity": {"type": "string", "description": "御祭神または御本尊。本文にあるとおり。なければ空"},
        "deity_evidence": {"type": "string", "description": "deity の根拠となる本文の一節（そのまま抜き出し）"},
        "lineage": {"type": "string", "enum": LINEAGES,
                    "description": "稲荷・天満宮・八幡・神明（伊勢）・観音地蔵系（寺院）。確信がなければ unknown"},
        "lineage_evidence": {"type": "string"},
        "events": {
            "type": "array",
            "description": "本文にある主な行事（例大祭・七五三・花まつり等）",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "month": {"type": "integer", "description": "1〜12。不明なら0"}},
                "required": ["name", "month"],
                "additionalProperties": False,
            },
        },
        "does_shichigosan": {"type": "boolean", "description": "七五三の祈祷・祈願を行っていると本文にあるか"},
        "existing_juyohin": {"type": "array", "items": {"type": "string"}, "description": "本文にある授与品の名前"},
        "personal_line": {"type": "string"},
        "evidence": {"type": "string"},
    },
    "required": ["kind", "deity", "deity_evidence", "lineage", "lineage_evidence", "events",
                 "does_shichigosan", "existing_juyohin", "personal_line", "evidence"],
    "additionalProperties": False,
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def verify(profile: dict, page_text: str) -> dict:
    """根拠が本文に見当たらない項目を捨てる。捨てた項目は dropped に記録する。"""
    text = _norm(page_text)
    dropped = []
    checks = [
        ("personal_line", "evidence", ""),
        ("deity", "deity_evidence", ""),
        ("lineage", "lineage_evidence", "unknown"),
    ]
    for key, ev_key, empty in checks:
        value, ev = profile.get(key), _norm(profile.get(ev_key, ""))
        if value and value != empty and (not ev or ev not in text):
            profile[key] = empty
            profile[ev_key] = ""
            dropped.append(key)
    profile["dropped"] = dropped
    return profile


def extract(name: str, page_text: str, client=None) -> dict:
    import anthropic

    client = client or anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": PROFILE_SCHEMA}},
        messages=[{"role": "user", "content": f"社寺名：{name}\n\n公式サイトの本文：\n{page_text}"}],
    )
    if response.stop_reason == "refusal":
        return {"kind": "unknown", "deity": "", "lineage": "unknown", "events": [], "does_shichigosan": False,
                "existing_juyohin": [], "personal_line": "", "evidence": "", "dropped": ["refusal"]}
    text = next(b.text for b in response.content if b.type == "text")
    return verify(json.loads(text), page_text)
