"""SQLite の台帳。1社寺＝1行。工程が進むごとに status を書き換える。

status の流れ:
    collected  … Places で見つけた
    excluded   … 除外（理由は exclusion）
    crawled    … 公式サイトから公開アドレスを取れた
    profiled   … 御祭神・行事などを読み取った
    drafted    … 下書きができた（人の承認待ち）
    approved   … 人が承認した
    sent       … 初回を送った
    followed   … 追いメールを送った（これ以上は送らない）
    replied    … 返信があった（reply_class に分類）
    bounced    … 不達
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR

DB_PATH = DATA_DIR / "juyohin.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS targets (
    place_id      TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    kind          TEXT,              -- shrine / temple / unknown
    prefecture    TEXT,
    address       TEXT,
    reviews       INTEGER,
    rating        REAL,
    website       TEXT,
    status        TEXT NOT NULL DEFAULT 'collected',
    exclusion     TEXT,
    email         TEXT,
    email_source  TEXT,              -- アドレスを載せていたページのURL（公開の証跡）
    email_seen_at TEXT,
    page_text     TEXT,              -- 巡回で読んだ本文（プロフィール生成と根拠照合に使う）
    profile       TEXT,              -- JSON
    subject       TEXT,
    body          TEXT,
    notes         TEXT,              -- 下書きの確認事項
    approved_at   TEXT,
    message_id    TEXT,
    sent_at       TEXT,
    followup_id   TEXT,
    followup_at   TEXT,
    reply_class   TEXT,
    reply_summary TEXT,
    replied_at    TEXT,
    updated_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_status ON targets(status);
CREATE INDEX IF NOT EXISTS idx_email ON targets(email);

CREATE TABLE IF NOT EXISTS api_usage (
    month    TEXT PRIMARY KEY,       -- YYYY-MM
    requests INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS searched (
    query       TEXT PRIMARY KEY,    -- 一度検索した語は、--refresh なしでは検索し直さない
    searched_at TEXT
);

CREATE TABLE IF NOT EXISTS suppression (
    email      TEXT PRIMARY KEY,     -- アドレスまたは @domain
    reason     TEXT,
    created_at TEXT
);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_place(conn: sqlite3.Connection, row: dict) -> bool:
    """Places の結果を入れる。既にあれば口コミ件数だけ更新し、工程は戻さない。"""
    cur = conn.execute("SELECT 1 FROM targets WHERE place_id = ?", (row["place_id"],))
    if cur.fetchone():
        conn.execute(
            "UPDATE targets SET reviews = ?, rating = ?, updated_at = ? WHERE place_id = ?",
            (row.get("reviews"), row.get("rating"), now(), row["place_id"]),
        )
        return False
    conn.execute(
        """INSERT INTO targets (place_id, name, kind, prefecture, address, reviews, rating, website, updated_at)
           VALUES (:place_id, :name, :kind, :prefecture, :address, :reviews, :rating, :website, :updated_at)""",
        {**{"kind": "unknown", "prefecture": "", "address": "", "reviews": 0, "rating": None, "website": ""},
         **row, "updated_at": now()},
    )
    return True


def update(conn: sqlite3.Connection, place_id: str, **fields) -> None:
    if "profile" in fields and not isinstance(fields["profile"], (str, type(None))):
        fields["profile"] = json.dumps(fields["profile"], ensure_ascii=False)
    fields["updated_at"] = now()
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE targets SET {cols} WHERE place_id = ?", (*fields.values(), place_id))


def by_status(conn: sqlite3.Connection, status: str, limit: int | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM targets WHERE status = ? ORDER BY reviews DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return conn.execute(sql, (status,)).fetchall()


def profile_of(row: sqlite3.Row) -> dict:
    return json.loads(row["profile"]) if row["profile"] else {}


def email_taken(conn: sqlite3.Connection, email: str, place_id: str) -> bool:
    """同じアドレスが別の社寺に既に使われているか（兼務社・兼務寺院の重複送信を防ぐ）。"""
    cur = conn.execute(
        "SELECT 1 FROM targets WHERE email = ? AND place_id != ? AND status != 'excluded'",
        (email.lower(), place_id),
    )
    return cur.fetchone() is not None


def suppress(conn: sqlite3.Connection, email: str, reason: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO suppression (email, reason, created_at) VALUES (?, ?, ?)",
        (email.lower(), reason, now()),
    )


def is_suppressed(conn: sqlite3.Connection, email: str) -> bool:
    email = email.lower()
    domain = "@" + email.split("@")[-1]
    cur = conn.execute("SELECT 1 FROM suppression WHERE email IN (?, ?)", (email, domain))
    return cur.fetchone() is not None


def this_month() -> str:
    return datetime.now().strftime("%Y-%m")


def api_requests(conn: sqlite3.Connection, month: str | None = None) -> int:
    row = conn.execute("SELECT requests FROM api_usage WHERE month = ?", (month or this_month(),)).fetchone()
    return row[0] if row else 0


def count_api_request(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO api_usage (month, requests) VALUES (?, 1) "
        "ON CONFLICT(month) DO UPDATE SET requests = requests + 1",
        (this_month(),),
    )
    conn.commit()


def was_searched(conn: sqlite3.Connection, query: str) -> bool:
    return conn.execute("SELECT 1 FROM searched WHERE query = ?", (query,)).fetchone() is not None


def mark_searched(conn: sqlite3.Connection, query: str) -> None:
    conn.execute("INSERT OR REPLACE INTO searched (query, searched_at) VALUES (?, ?)", (query, now()))
    conn.commit()


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM targets GROUP BY status").fetchall()
    return {r["status"]: r["n"] for r in rows}
