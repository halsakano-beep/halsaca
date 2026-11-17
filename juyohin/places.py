"""候補の収集：Google Places API (New) の Text Search。

1回の検索で返るのは最大60件（20件×3ページ）。全国を拾うには地域を細かく刻む。
都道府県単位だと有名どころに偏るので、本番は市区町村のリスト（--areas-file）で回す。

口コミ件数（userRatingCount）を「参拝者の多さ」の代わりに使う。
件数で絞るのは収集後（cli の targeting）なので、閾値を変えても取り直しは要らない。

料金：websiteUri と userRatingCount は Text Search の上位SKUに含まれる。
実行前に Google Cloud の料金表で1,000件あたりの単価を確認すること。
"""

from __future__ import annotations

import os
import re
import time
from typing import Callable, Iterator

import requests

API_URL = "https://places.googleapis.com/v1/places:searchText"
MAX_PAGES = 3  # API側の上限も3ページ（60件）
FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.userRatingCount",
    "places.rating", "places.websiteUri", "places.types", "nextPageToken",
])

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県",
    "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
    "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]

QUERIES = {"shrine": "神社", "temple": "寺"}

# 社寺ではないもの（駅・駐車場・付属の園など）
NOT_WORSHIP = re.compile(r"駅|バス停|駐車場|パーキング|幼稚園|保育園|こども園|霊園|墓地|斎場|会館|ホテル|旅館|食堂|カフェ|店$|教会")
SHRINE_NAME = re.compile(r"神社|大社|神宮|天満宮|八幡宮|稲荷|東照宮|権現|社$|宮$")
TEMPLE_NAME = re.compile(r"寺|院$|院\s|大師|観音|不動尊|地蔵尊|別院|本山|坊$|庵$|堂$")


def classify(name: str, types: list[str] | None = None) -> str:
    """名前と種別から shrine / temple / unknown を判定する。"""
    types = types or []
    if NOT_WORSHIP.search(name):
        return "unknown"
    if "shinto_shrine" in types:
        return "shrine"
    if "buddhist_temple" in types:
        return "temple"
    # 「〇〇寺 鎮守社」のような併記もあるので、寺を先に見る
    if TEMPLE_NAME.search(name) and not re.search(r"神社|神宮", name):
        return "temple"
    if SHRINE_NAME.search(name):
        return "shrine"
    return "unknown"


def prefecture_of(address: str) -> str:
    for pref in PREFECTURES:
        if pref in address:
            return pref
    return ""


def parse_place(p: dict) -> dict:
    name = (p.get("displayName") or {}).get("text", "")
    address = p.get("formattedAddress", "")
    return {
        "place_id": p["id"],
        "name": name,
        "kind": classify(name, p.get("types")),
        "prefecture": prefecture_of(address),
        "address": address,
        "reviews": p.get("userRatingCount", 0) or 0,
        "rating": p.get("rating"),
        "website": p.get("websiteUri", "") or "",
    }


class BudgetExceeded(Exception):
    """今月の無料枠の範囲（monthly_request_budget）を使い切った。"""


def search(query: str, api_key: str | None = None, session=None, pause: float = 2.0,
           before_request: Callable[[], None] | None = None) -> Iterator[dict]:
    """1つの検索語で最大3ページを辿る。1ページ＝1リクエストとして課金される。

    before_request は各リクエストの直前に呼ばれ、予算を超えるなら BudgetExceeded を投げる。
    """
    # クラウド環境でキーをプロキシが差し込む場合は、仮の値のまま送ればよい
    api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY", "injected-by-proxy")
    session = session or requests.Session()
    body = {"textQuery": query, "languageCode": "ja", "regionCode": "JP", "pageSize": 20}
    for page in range(MAX_PAGES):
        if before_request:
            before_request()
        resp = session.post(
            API_URL, json=body, timeout=30,
            headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": FIELD_MASK},
        )
        resp.raise_for_status()
        data = resp.json()
        for p in data.get("places", []):
            yield parse_place(p)
        token = data.get("nextPageToken")
        if not token or page == MAX_PAGES - 1:
            return
        body = {**body, "pageToken": token}
        time.sleep(pause)  # 次ページのトークンは少し待たないと有効にならない


def queries_for(areas: list[str], kinds: list[str]) -> list[str]:
    return [f"{area} {QUERIES[kind]}" for area in areas for kind in kinds]


def collect(queries: list[str], searcher: Callable = search) -> Iterator[dict]:
    """検索語ごとに検索し、社寺と判定できたものだけ返す（place_id で重複除去）。"""
    seen: set[str] = set()
    for query in queries:
        for place in searcher(query):
            if place["place_id"] in seen or place["kind"] == "unknown":
                continue
            seen.add(place["place_id"])
            yield place
