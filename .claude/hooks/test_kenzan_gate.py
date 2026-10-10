#!/usr/bin/env python3
"""kenzan_gate.py の回帰テスト： python3 .claude/hooks/test_kenzan_gate.py"""
import json, os, subprocess, sys, tempfile

GATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kenzan_gate.py")


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def tool(name, **inp):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}}


def run(rows, active=False):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
    out = subprocess.run([sys.executable, GATE], input=json.dumps({"transcript_path": f.name, "stop_hook_active": active}),
                         capture_output=True, text=True).stdout
    os.unlink(f.name)
    return json.loads(out) if out.strip() else None


CASES = [
    ("数字あり Write → block", [user("見積"), tool("Write", file_path="見積.md", content="単価 1,200円 × 30個 = 36,000円")], False, True),
    ("数字なし Write → pass", [user("メモ"), tool("Write", file_path="memo.md", content="よろしくお願いします")], False, False),
    ("stop_hook_active → pass", [user("x"), tool("Write", file_path="a.csv", content="合計,12.5%")], True, False),
    ("検算済み → pass", [user("x"), tool("Write", file_path="b.md", content="¥5,000"), tool("Agent", description="見積の検算", prompt="検算して")], False, False),
    ("検算後に再書き込み → block", [user("x"), tool("Agent", description="検算", prompt=""), tool("Write", file_path="c.md", content="¥5,000")], False, True),
    ("Edit で数字変更 → block", [user("x"), tool("Edit", file_path="d.md", old_string="合計 3,000円", new_string="合計 3,300円")], False, True),
    ("Edit で数字不変（文言のみ）→ pass", [user("x"), tool("Edit", file_path="d.md", old_string="合計 3,000円です", new_string="合計 3,000円となります")], False, False),
    ("前ターンの書き込みは対象外 → pass", [user("a"), tool("Write", file_path="e.md", content="1,000円"), user("ありがとう")], False, False),
    ("openpyxl で数字 → block", [user("x"), tool("Bash", command="python3 -c \"import openpyxl; ws['B2']=1200; ws['C2']='=B2*30'\"")], False, True),
    ("読むだけの Bash → pass", [user("x"), tool("Bash", command="cat 見積.md | grep 1,200円")], False, False),
    ("Gmail 下書き → block", [user("x"), tool("mcp__Gmail__create_draft", subject="お見積", body="合計 36,000円（税別）")], False, True),
]

fail = 0
for title, rows, active, want in CASES:
    got = run(rows, active)
    ok = (got is not None and got.get("decision") == "block") == want
    fail += not ok
    print(("OK  " if ok else "NG  ") + title)
print(f"\n{len(CASES) - fail}/{len(CASES)} passed")
sys.exit(1 if fail else 0)
