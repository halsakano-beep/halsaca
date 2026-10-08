"""フェーズ0：業種×地域ごとに、直近の役務案件の数を数える。

使い方:
    python -m chabashira.survey --prefs 大阪府 兵庫県 京都府 --days 90

結果は out/survey_<日付>.csv と Markdown の表として出力する。
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

from . import kkj
from .industries import INDUSTRIES, is_excluded

OUT_DIR = Path(__file__).parent / "out"


def collect(industry: str, pref: str, issued_from: date, issued_to: date,
            search=kkj.search, pause=kkj.polite_pause) -> dict[str, kkj.Notice]:
    """業種のキーワードを順に検索し、重複を除いた案件を返す。"""
    found: dict[str, kkj.Notice] = {}
    for keyword in INDUSTRIES[industry]["keywords"]:
        _, notices = search(
            keyword,
            lg_codes=[kkj.PREFECTURES[pref]],
            category=kkj.CATEGORY_SERVICE,
            issued_from=issued_from,
            issued_to=issued_to,
        )
        for notice in notices:
            if not is_excluded(notice.get("title")):
                found.setdefault(notice.key, notice)
        pause()
    return found


def run(prefs: list[str], days: int, today: date | None = None,
        search=kkj.search, pause=kkj.polite_pause) -> list[dict]:
    today = today or date.today()
    issued_from = today - timedelta(days=days)
    weeks = days / 7
    rows = []
    for industry in INDUSTRIES:
        for pref in prefs:
            found = collect(industry, pref, issued_from, today, search, pause)
            orgs = {n.get("organization") for n in found.values() if n.get("organization")}
            rows.append({
                "業種": industry,
                "地域": pref,
                "案件数": len(found),
                "週あたり": round(len(found) / weeks, 1),
                "発注機関数": len(orgs),
            })
            print(f"{industry} × {pref}: {len(found)}件", file=sys.stderr)
    rows.sort(key=lambda r: r["週あたり"], reverse=True)
    return rows


def to_markdown(rows: list[dict]) -> str:
    header = "| 業種 | 地域 | 案件数 | 週あたり | 発注機関数 | 判定 |\n| --- | --- | --- | --- | --- | --- |"
    lines = [header]
    for r in rows:
        verdict = "候補" if r["週あたり"] >= 5 else "少ない"
        lines.append(f"| {r['業種']} | {r['地域']} | {r['案件数']} | {r['週あたり']} | {r['発注機関数']} | {verdict} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="業種×地域の入札案件数を集計する")
    parser.add_argument("--prefs", nargs="+", default=["大阪府", "兵庫県", "京都府"])
    parser.add_argument("--days", type=int, default=90)
    args = parser.parse_args(argv)

    rows = run(args.prefs, args.days)
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"survey_{date.today().isoformat()}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(to_markdown(rows))
    print(f"\nCSV: {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
