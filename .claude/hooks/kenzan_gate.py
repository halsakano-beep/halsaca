#!/usr/bin/env python3
"""検算ゲート（classic Stop hook 版）
直近のユーザー入力以降に「数字を含む書き込み」があり、まだ「検算」エージェントを
呼んでいなければ、decision=block で差し戻して検算エージェントの起動を求める。"""
import json, re, sys

WRITE_TOOLS = re.compile(r"^(Write|Edit|MultiEdit|NotebookEdit|mcp__.*(create_draft|update_draft|send_message|reply|forward|create_file|update_file|edit-design))$")
SHELL_TOOLS = re.compile(r"^(Bash|PowerShell|mcp__.*device_bash)$")
SHELL_WRITES = re.compile(r"(openpyxl|xlsxwriter|python-pptx|from pptx|pptxgenjs|python-docx|from docx|reportlab|to_excel|to_csv|sed -i|>\s*\S+\.(csv|tsv|json|md|txt|html)\b)")
# 表計算の生成は数字が外部データから来ることが多いので、コマンドに数字がなくても対象
SHEET_WRITES = re.compile(r"(openpyxl|xlsxwriter|to_excel|to_csv|>\s*\S+\.(csv|tsv)\b)")
SHEET_FILE = re.compile(r"\.(csv|tsv)$", re.I)
# 単位は大文字小文字を区別し、直後に英字が続けば単位と見なさない（python3 make, 5min, 5G回線は対象外）。
# 英字の直後の数字（W100mm, t3mm）は空白を挟まず単位が付くときだけ数える（user1 m は対象外）。
UNITS = (r"(円|%|％|個|本|枚|件|名|人|台|箱|冊|部(?!屋|門|署|分)|点|袋|パック|缶|巻|足|着|組|口(?!座|目)|梱|包|ヶ(?!月|所)|箇|ケース|ダース|セット|式|ロット"
         r"|千|万|億|倍|掛|割|ドル|ｍｍ|ｃｍ|ｋｇ|ｍ|ｇ|Ｌ|ℓ|ｐｃｓ|ＰＣＳ|(kg|g|cm|mm|m|ml|mL|L|pcs|PCS|JPY|USD|yen)(?![A-Za-z]))")
NUM = re.compile(
    r"[¥￥$€]\s*\d|(JPY|USD)\s*\d|(?<![A-Za-z0-9_/.])[@＠]\s*\d{2,}"
    r"|(?<![A-Za-z_\d第])\d[\d,，]*(\.\d+)?\s*" + UNITS +
    r"|(?<=[A-Za-z])\d[\d,，]*(\.\d+)?" + UNITS +
    r"|(?<![\d,，])\d{1,3}([,，]\d{3})+(?![,，]?\d)"
    r"|(?:(?<=[×*])|(?<=(?<![A-Za-z])x)|(?<![A-Za-z_\d.]))\d+\.\d+(?!\.?\d)"
    r"|\d\s*×\s*\d"
    r"|=\s*(?i:SUM|ROUND|IF|AVERAGE|MIN|MAX|COUNT|VLOOKUP|XLOOKUP)\w*\s*\(|=\s*\$?[A-Z]+\$?\d+\s*[*+\-/]")
DIGITS = re.compile(r"\d[\d,]*(\.\d+)?")
SELF_DIR = re.compile(r"(^|[\\/])\.claude[\\/]")  # Claude Code 自身の設定・フックは対象外


def nums(s):
    return [m.group(0) for m in DIGITS.finditer(s or "")]


def text_of(v):
    """入力の文字列値だけを連結する（json.dumps だと改行が \\n になり、直後の数字が英字の後ろに見える）"""
    if isinstance(v, dict):
        return "\n".join(text_of(x) for x in v.values())
    if isinstance(v, list):
        return "\n".join(text_of(x) for x in v)
    return v if isinstance(v, str) else str(v)


def touches(name, inp):
    if SELF_DIR.search(str(inp.get("file_path") or inp.get("notebook_path") or "")):
        return False
    if name in ("Edit", "MultiEdit"):
        edits = inp.get("edits") or [inp]
        return any(nums(x.get("old_string")) != nums(x.get("new_string"))
                   and NUM.search((x.get("old_string") or "") + (x.get("new_string") or ""))
                   for x in edits)
    if SHELL_TOOLS.match(name):
        cmd = inp.get("command", "")
        writes = [m.group(0) for m in SHELL_WRITES.finditer(cmd) if not SELF_DIR.search(m.group(0))]
        return bool(writes) and bool(NUM.search(cmd) or any(SHEET_WRITES.search(w) for w in writes))
    if WRITE_TOOLS.match(name):
        if SHEET_FILE.search(inp.get("file_path") or "") and re.search(r"\d", inp.get("content") or ""):
            return True
        return bool(NUM.search(text_of(inp)))
    return False


def is_human_prompt(entry):
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    c = entry.get("message", {}).get("content")
    if isinstance(c, str):
        return True
    return isinstance(c, list) and not any(b.get("type") == "tool_result" for b in c if isinstance(b, dict))


def main():
    data = json.load(sys.stdin)
    if data.get("stop_hook_active"):
        return
    rows = []
    with open(data["transcript_path"], encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    start = max((i for i, r in enumerate(rows) if is_human_prompt(r)), default=-1)
    touched, verified = [], False
    for r in rows[start + 1:]:
        if r.get("type") != "assistant" or r.get("isSidechain"):
            continue
        for b in r.get("message", {}).get("content") or []:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            name, inp = b.get("name", ""), b.get("input") or {}
            if name in ("Agent", "Task") and "検算" in (inp.get("description", "") + inp.get("prompt", "")):
                touched, verified = [], True
            elif touches(name, inp):
                cmd = " ".join((inp.get("command") or "").split())
                label = (inp.get("file_path") or inp.get("notebook_path") or inp.get("subject")
                         or (f"{name}: {cmd[:40]}{'…' if len(cmd) > 40 else ''}" if cmd else name))
                if label not in touched:
                    touched.append(label)
    if not touched:
        return
    reason = "\n".join([
        "【検算ゲート】このターンで数字を含む編集・出力がありました：",
        *[f"- {t}" for t in touched], "",
        "返答を終える前に、Agentツールで検算サブエージェントを起動してください（description に「検算」を含める）。",
        "対象ファイル/本文と元データ・前提（単価、数量、掛率、税率、日付）を渡し、独立に再計算させること：",
        "1. 合計・小計・単価×数量・掛率・税込/税別", "2. 元データからの転記一致（桁・単位）",
        "3. 日付と曜日、期間、件数", "4. Excelなら数式の参照範囲と再計算結果",
        "ずれがあれば修正し、返答の最後に「検算：OK／修正n件（内容）」を1行添えること。",
    ])
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # フックの不具合でセッションを止めない
