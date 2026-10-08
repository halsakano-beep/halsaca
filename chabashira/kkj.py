"""官公需情報ポータルサイト検索API のクライアント。

仕様は「検索APIガイド V1.1」(2016年) に基づく。応答XMLの要素名は
実際の応答で未確認のため、`python -m chabashira.kkj --dump` で一度
生の応答を確認し、FIELD_CANDIDATES を必要に応じて直すこと。
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date

API_URL = "https://www.kkj.go.jp/api/"

# カテゴリ: 1=物品, 2=工事, 3=役務
CATEGORY_GOODS, CATEGORY_CONSTRUCTION, CATEGORY_SERVICE = 1, 2, 3

# JIS X0401 都道府県コード
PREFECTURES = {
    "北海道": "01", "青森県": "02", "岩手県": "03", "宮城県": "04", "秋田県": "05",
    "山形県": "06", "福島県": "07", "茨城県": "08", "栃木県": "09", "群馬県": "10",
    "埼玉県": "11", "千葉県": "12", "東京都": "13", "神奈川県": "14", "新潟県": "15",
    "富山県": "16", "石川県": "17", "福井県": "18", "山梨県": "19", "長野県": "20",
    "岐阜県": "21", "静岡県": "22", "愛知県": "23", "三重県": "24", "滋賀県": "25",
    "京都府": "26", "大阪府": "27", "兵庫県": "28", "奈良県": "29", "和歌山県": "30",
    "鳥取県": "31", "島根県": "32", "岡山県": "33", "広島県": "34", "山口県": "35",
    "徳島県": "36", "香川県": "37", "愛媛県": "38", "高知県": "39", "福岡県": "40",
    "佐賀県": "41", "長崎県": "42", "熊本県": "43", "大分県": "44", "宮崎県": "45",
    "鹿児島県": "46", "沖縄県": "47",
}

# 応答XMLの要素名の候補（大文字小文字は無視して照合する）
FIELD_CANDIDATES = {
    "key": ["Key", "ResultId"],
    "title": ["ProjectName", "Project_Name"],
    "url": ["ExternalDocumentURI", "Url", "URI"],
    "organization": ["OrganizationName", "Organization_Name"],
    "prefecture": ["PrefectureName"],
    "city": ["CityName"],
    "category": ["Category"],
    "procedure": ["ProcedureType", "Procedure_Type"],
    "issued": ["CftIssueDate", "CFT_Issue_Date", "Date"],
    "deadline": ["TenderSubmissionDeadline", "Tender_Submission_Deadline", "PeriodEndTime"],
    "description": ["ProjectDescription", "Description"],
}


@dataclass
class Notice:
    """入札公告1件。fields には応答の要素をすべて残す。"""

    fields: dict[str, str] = field(default_factory=dict)

    def get(self, name: str) -> str:
        lowered = {k.lower(): v for k, v in self.fields.items()}
        for candidate in FIELD_CANDIDATES.get(name, [name]):
            value = lowered.get(candidate.lower())
            if value:
                return value.strip()
        return ""

    @property
    def key(self) -> str:
        return self.get("key") or self.get("url") or self.get("title")

    @property
    def issued_date(self) -> date | None:
        raw = self.get("issued")[:10]
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_results(xml_text: str) -> tuple[int | None, list[Notice]]:
    """応答XMLから (総ヒット数, 公告のリスト) を取り出す。"""
    root = ET.fromstring(xml_text)
    hits = None
    notices = []
    for elem in root.iter():
        name = _local(elem.tag)
        if name == "SearchHits" and elem.text and elem.text.strip().isdigit():
            hits = int(elem.text.strip())
        elif name == "SearchResult":
            values = {}
            for child in elem:
                if len(child) == 0:
                    values[_local(child.tag)] = (child.text or "").strip()
            notices.append(Notice(values))
    return hits, notices


def search(
    query: str,
    *,
    lg_codes: list[str] | None = None,
    category: int | None = None,
    issued_from: date | None = None,
    issued_to: date | None = None,
    count: int = 1000,
    timeout: float = 30.0,
) -> tuple[int | None, list[Notice]]:
    """APIを1回呼ぶ。公示日の絞り込みはAPI側とこちら側の両方で行う。"""
    params = {"Query": query, "Count": str(min(count, 1000))}
    if lg_codes:
        params["LG_Code"] = ",".join(lg_codes)
    if category:
        params["Category"] = str(category)
    if issued_from or issued_to:
        start = issued_from.isoformat() if issued_from else ""
        end = issued_to.isoformat() if issued_to else ""
        params["CFT_Issue_Date"] = f"{start}/{end}"
    url = API_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "chabashira/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8")
    hits, notices = parse_results(text)
    if issued_from or issued_to:
        notices = [
            n for n in notices
            if n.issued_date is None
            or ((not issued_from or n.issued_date >= issued_from)
                and (not issued_to or n.issued_date <= issued_to))
        ]
    return hits, notices


def polite_pause(seconds: float = 1.5) -> None:
    """利用規約は大量の連続アクセスを禁じている。呼び出しの間に必ず挟む。"""
    time.sleep(seconds)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="官公需APIを1回呼んで生の応答を確認する")
    parser.add_argument("query")
    parser.add_argument("--pref", default="大阪府")
    parser.add_argument("--category", type=int, default=CATEGORY_SERVICE)
    parser.add_argument("--dump", action="store_true", help="生のXMLを表示する")
    args = parser.parse_args(argv)

    params = {
        "Query": args.query,
        "LG_Code": PREFECTURES[args.pref],
        "Category": str(args.category),
        "Count": "5",
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as response:
        text = response.read().decode("utf-8")
    if args.dump:
        print(text)
        return 0
    hits, notices = parse_results(text)
    print(f"総ヒット数: {hits}")
    for n in notices:
        print(f"- {n.get('issued')} {n.get('organization')} {n.get('title')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
