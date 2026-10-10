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
    # --- 誤検知を減らす ---
    ("python3 の「3 m」を単位と誤読しない → pass", [user("x"), tool("Bash", command="python3 make_quote.py > out.md")], False, False),
    ("バージョン番号は数字扱いしない → pass", [user("x"), tool("Write", file_path="package.json", content='{"version": "2.1.296"}')], False, False),
    ("IP アドレス → pass", [user("x"), tool("Write", file_path="hosts.txt", content="server 192.168.0.1")], False, False),
    ("5min・4 groups は単位にしない → pass", [user("x"), tool("Write", file_path="memo.md", content="タイムアウト 5min、4 groups")], False, False),
    ("リダイレクト先 .jsonl は .json と見なさない → pass", [user("x"), tool("Bash", command="echo '1,200円' > log.jsonl")], False, False),
    # --- 拾うべきものは残す ---
    ("単位 mm・kg → block", [user("x"), tool("Write", file_path="仕様.md", content="幅 100mm、重さ 2kg")], False, True),
    ("小数と掛率 → block", [user("x"), tool("Write", file_path="条件.md", content="掛率 0.8、粗利 12.5")], False, True),
    ("漢字の直後の数字 → block", [user("x"), tool("Write", file_path="見積.md", content="単価1200円")], False, True),
    ("英字直後の寸法 W100mm・t3mm → block", [user("x"), tool("Write", file_path="仕様.md", content="サイズ W100×H200×D50mm／厚さ t3mm")], False, True),
    ("1200x30個 → block", [user("x"), tool("Edit", file_path="見積.md", old_string="1200x30個", new_string="1200x40個")], False, True),
    ("文末ピリオドの小数 0.8. → block", [user("x"), tool("Edit", file_path="条件.md", old_string="掛率は0.8.", new_string="掛率は0.75.")], False, True),
    ("桁区切りの後ろが半角カンマ → block", [user("x"), tool("Write", file_path="a.md", content="price: 1,200, qty: 30")], False, True),
    ("x1.1 → block", [user("x"), tool("Write", file_path="a.md", content="原価 x1.1")], False, True),
    ("pcs・ケース・ml・JPY → block", [user("x"), tool("Write", file_path="a.md", content="30pcs、3ケース、500ml、JPY 1200")], False, True),
    ("全角カンマ・全角単位 → block", [user("x"), tool("Write", file_path="a.md", content="合計 ３６，０００、100ｍｍ")], False, True),
    ("小文字の数式・AVERAGE → block", [user("x"), tool("Write", file_path="a.md", content="=average(B2:B10)")], False, True),
    ("コード中の key=max・?sort=count・?api=v1/users → pass", [user("x"), tool("Write", file_path="a.py", content="sorted(xs, key=max)\nurl = '?sort=count&api=v1/users'\nshape=round")], False, False),
    ("5G回線・3M・512M は単位にしない → pass", [user("x"), tool("Write", file_path="a.md", content="5G回線、3M製テープ、memory: 512M")], False, False),
    ("識別子＋空白＋m/g（user1 m, h264 g）→ pass", [user("x"), tool("Write", file_path="a.md", content="user1 m、h264 g、ec2 m")], False, False),
    ("Box2.0・Linux2.6 → pass", [user("x"), tool("Write", file_path="a.md", content="Box2.0、Linux2.6")], False, False),
    ("全角単位・数え方の単位・外貨 → block", [user("x"), tool("Write", file_path="a.md", content="1ｍ、30冊、5袋、USD 100")], False, True),
    ("× の掛け算（単位なし）・@単価 → block", [user("x"), tool("Write", file_path="a.md", content="1200×30=36000、@1200")], False, True),
    ("改行・タブ直後の数字 → block", [user("x"), tool("Write", file_path="a.md", content="掛率\n0.8")], False, True),
    ("改行直後の数字＋空白＋単位 → block", [user("x"), tool("mcp__Gmail__create_draft", subject="件名", body="単価\n1200 円")], False, True),
    ("500円分・30個目 → block", [user("x"), tool("Write", file_path="a.md", content="500円分のクーポン")], False, True),
    ("漢字直後の @単価 → block", [user("x"), tool("Write", file_path="a.md", content="鉛筆 単価@1200 数量30")], False, True),
    ("第2部・部屋・口座・3ヶ月 → pass", [user("x"), tool("Write", file_path="a.md", content="第2部の資料、2部屋、1口座、3ヶ月後、1部門")], False, False),
    ("pkg@18.3.1・user@1234 → pass", [user("x"), tool("Write", file_path="a.md", content="npm i pkg@18.3.1、user@1234.example")], False, False),
    # --- 検知漏れを塞ぐ ---
    ("単位なしの TSV を Write → block", [user("x"), tool("Write", file_path="見積.tsv", content="鉛筆\t1200\t30\t36000")], False, True),
    ("外部CSVからExcel生成（コマンドに数字なし）→ block", [user("x"), tool("Bash", command="python -c \"import pandas as pd; pd.read_csv('in.csv').to_excel('見積.xlsx')\"")], False, True),
    ("ヒアドキュメントで単位なし CSV → block", [user("x"), tool("Bash", command="cat > 見積.csv <<'EOF'\n鉛筆,1200,30,36000\nEOF")], False, True),
    (".claude/ への Write → pass", [user("x"), tool("Write", file_path="/p/.claude/hooks/a.py", content="1,200円")], False, False),
    (".claude/ への Edit（Windows パス）→ pass", [user("x"), tool("Edit", file_path=r"C:\\Users\\h\\.claude\\b.py", old_string="1,000円", new_string="2,000円")], False, False),
    (".claude/ へのヒアドキュメント → pass", [user("x"), tool("Bash", command="cat > /p/.claude/settings.json <<'EOF'\n{\"a\": \"1,200円\"}\nEOF")], False, False),
    (".claude/ と見積の両方に書く Bash → block", [user("x"), tool("Bash", command="cat > .claude/x.json <<'EOF'\n{}\nEOF\necho '1,200円' > 見積.md")], False, True),
]

fail = 0
for title, rows, active, want in CASES:
    got = run(rows, active)
    ok = (got is not None and got.get("decision") == "block") == want
    fail += not ok
    print(("OK  " if ok else "NG  ") + title)
# 差し戻し理由に Bash コマンドの先頭が出ること
got = run([user("x"), tool("Bash", command="echo '単価 1,200円' > 見積.md")])
ok = bool(got) and "echo '単価 1,200円' > 見積.md" in got["reason"]
fail += not ok
print(("OK  " if ok else "NG  ") + "Bash の差し戻し理由にコマンドの先頭を表示")
print(f"\n{len(CASES) + 1 - fail}/{len(CASES) + 1} passed")
sys.exit(1 if fail else 0)
