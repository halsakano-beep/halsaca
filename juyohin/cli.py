"""コマンドの入口。1日の運用は次の順。

    collect  → crawl → profile → draft → review-export
    （人が CSV を見て承認列に ○ を付ける）
    review-import → send → poll（毎日）→ followup（毎日）

使い方は README.md。
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from . import compose, crawl, db, places, profile, replies
from .config import OUT_DIR, Config, load

APPROVE_MARKS = {"○", "◯", "o", "ok", "y", "yes", "1", "済"}
REJECT_MARKS = {"×", "x", "n", "no", "0", "除外"}
SEND_HOURS = range(9, 16)  # 平日9〜16時に送る（社務所・寺務所が開いている時間）


def in_band(row, cfg: Config) -> bool:
    return cfg.targeting.min_reviews <= (row["reviews"] or 0) <= cfg.targeting.max_reviews


# ── collect ─────────────────────────────────────────────
def cmd_collect(args, conn, cfg):
    areas = args.areas or []
    if args.areas_file:
        areas += [l.strip() for l in Path(args.areas_file).read_text(encoding="utf-8").splitlines() if l.strip()]
    if not areas:
        areas = places.PREFECTURES
    budget = cfg.targeting.monthly_request_budget
    queries = places.queries_for(areas, args.kinds)
    if not args.refresh:
        queries = [q for q in queries if not db.was_searched(conn, q)]

    def guard():
        if budget and db.api_requests(conn) >= budget:
            raise places.BudgetExceeded
        db.count_api_request(conn)

    def searcher(query):
        yield from places.search(query, before_request=guard)

    new = total = done = 0
    try:
        for query in queries:
            for place in places.collect([query], searcher):
                total += 1
                new += db.upsert_place(conn, place)
            conn.commit()
            db.mark_searched(conn, query)
            done += 1
    except places.BudgetExceeded:
        conn.commit()
        print(f"今月の上限（{budget}リクエスト）に達したので止めました。続きは来月、同じコマンドで再開できます。")
    print(f"検索 {done}/{len(queries)}語、{total}件を確認、新規 {new}件、"
          f"今月のリクエスト {db.api_requests(conn)}/{budget or '無制限'}")


# ── crawl ───────────────────────────────────────────────
def cmd_crawl(args, conn, cfg):
    fetcher = crawl.Fetcher()
    rows = [r for r in db.by_status(conn, "collected") if in_band(r, cfg)][: args.limit]
    stats: dict[str, int] = {}
    for row in rows:
        if not row["website"]:
            db.update(conn, row["place_id"], status="excluded", exclusion="no_website")
            stats["no_website"] = stats.get("no_website", 0) + 1
            conn.commit()
            continue
        result = crawl.crawl(row["website"], fetcher)
        exclusion, email, source = crawl.judge(result, row["website"])
        if not exclusion and db.is_suppressed(conn, email):
            exclusion = "suppressed"
        if not exclusion and db.email_taken(conn, email, row["place_id"]):
            exclusion = "duplicate_email"
        if exclusion:
            db.update(conn, row["place_id"], status="excluded", exclusion=exclusion,
                      notes=result.refusal or None, page_text=result.text)
        else:
            db.update(conn, row["place_id"], status="crawled", email=email.lower(), email_source=source,
                      email_seen_at=db.now(), page_text=result.text)
        key = exclusion or "ok"
        stats[key] = stats.get(key, 0) + 1
        conn.commit()
        print(f"  {row['name']}: {key}{' ' + email if email else ''}")
    print("巡回:", stats)


# ── profile ─────────────────────────────────────────────
def cmd_profile(args, conn, cfg):
    for row in db.by_status(conn, "crawled", args.limit):
        prof = profile.extract(row["name"], row["page_text"] or "")
        db.update(conn, row["place_id"], status="profiled", profile=prof)
        conn.commit()
        print(f"  {row['name']}: {prof.get('lineage')} / {prof.get('deity') or '-'} / "
              f"{'一文あり' if prof.get('personal_line') else '一文なし'}")


# ── draft ───────────────────────────────────────────────
def cmd_draft(args, conn, cfg):
    month = args.month or date.today().month
    rows = db.by_status(conn, "profiled", args.limit)
    for row in rows:
        d = compose.compose(row["name"], row["kind"], db.profile_of(row), month, cfg.sender, cfg.sending)
        db.update(conn, row["place_id"], status="drafted", subject=d.subject, body=d.body, notes=" / ".join(d.notes))
    conn.commit()
    print(f"下書き {len(rows)}件")


# ── review ──────────────────────────────────────────────
REVIEW_COLUMNS = ["承認", "place_id", "社寺名", "種別", "都道府県", "口コミ数", "宛先", "アドレス掲載ページ",
                  "サイト", "確認事項", "件名", "本文"]


def cmd_review_export(args, conn, cfg):
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"review_{date.today():%Y%m%d}.csv"
    rows = db.by_status(conn, "drafted", args.limit)
    with path.open("w", encoding="utf-8-sig", newline="") as f:  # Excel で文字化けしないよう BOM 付き
        w = csv.writer(f)
        w.writerow(REVIEW_COLUMNS)
        for r in rows:
            w.writerow(["", r["place_id"], r["name"], r["kind"], r["prefecture"], r["reviews"], r["email"],
                        r["email_source"], r["website"], r["notes"], r["subject"], r["body"]])
    print(f"{len(rows)}件 → {path}\n承認列に ○（送る）か ×（送らない）を入れ、本文は直接直してよい。")


def cmd_review_import(args, conn, cfg):
    approved = rejected = 0
    with open(args.file, encoding="utf-8-sig", newline="") as f:
        for rec in csv.DictReader(f):
            mark = (rec.get("承認") or "").strip().lower()
            row = conn.execute("SELECT status FROM targets WHERE place_id = ?", (rec["place_id"],)).fetchone()
            if not row or row["status"] != "drafted":
                continue
            if mark in APPROVE_MARKS:
                db.update(conn, rec["place_id"], status="approved", subject=rec["件名"], body=rec["本文"],
                          approved_at=db.now())
                approved += 1
            elif mark in REJECT_MARKS:
                db.update(conn, rec["place_id"], status="excluded", exclusion="manual")
                rejected += 1
    conn.commit()
    print(f"承認 {approved}件 / 除外 {rejected}件")


# ── send ────────────────────────────────────────────────
def sent_today(conn) -> int:
    today = date.today().isoformat()
    a = conn.execute("SELECT COUNT(*) FROM targets WHERE sent_at LIKE ?", (today + "%",)).fetchone()[0]
    b = conn.execute("SELECT COUNT(*) FROM targets WHERE followup_at LIKE ?", (today + "%",)).fetchone()[0]
    return a + b


def can_send_now(now: datetime, force: bool) -> str:
    if force:
        return ""
    if now.weekday() >= 5:
        return "土日は送らない（--force で上書き）"
    if now.hour not in SEND_HOURS:
        return "9〜16時以外は送らない（--force で上書き）"
    return ""


def _sender_ready(cfg: Config, dry_run: bool) -> bool:
    missing = cfg.missing_for_sending()
    if missing and not dry_run:
        print("送信に必要な設定が足りません:", ", ".join(missing), file=sys.stderr)
        return False
    return True


def _send_loop(items, cfg, dry_run, on_sent, force=False):
    from .mailer import SmtpSender, build_message

    if dry_run:
        for to, subject, body, reply_to, row in items:
            print(f"[dry-run] → {to} 件名:{subject}\n{body}\n{'-' * 40}")
        return
    with SmtpSender(cfg.mail) as smtp:
        for i, (to, subject, body, reply_to, row) in enumerate(items):
            if not force and datetime.now().hour not in SEND_HOURS:
                print(f"送信時間帯を過ぎたので止めます（残り {len(items) - i}件は次の営業日に）")
                return
            msg = build_message(cfg.sender, to, subject, body, in_reply_to=reply_to)
            smtp.send(msg)
            on_sent(row, msg["Message-ID"])
            print(f"  送信: {row['name']} <{to}>")
            if i < len(items) - 1:
                time.sleep(random.randint(cfg.sending.min_interval_sec, cfg.sending.max_interval_sec))


def cmd_send(args, conn, cfg):
    if (why := can_send_now(datetime.now(), args.force)) or not _sender_ready(cfg, args.dry_run):
        if why:
            print(why)
        return
    room = cfg.sending.daily_limit - sent_today(conn)
    rows = [r for r in db.by_status(conn, "approved") if not db.is_suppressed(conn, r["email"])]
    rows = rows[: min(room, args.limit or room)]
    if not rows:
        print("送る対象がありません（承認済み0件、または本日の上限）")
        return
    items = [(r["email"], r["subject"], r["body"], None, r) for r in rows]

    def on_sent(row, mid):
        db.update(conn, row["place_id"], status="sent", message_id=mid, sent_at=db.now())
        conn.commit()

    _send_loop(items, cfg, args.dry_run, on_sent, args.force)


def cmd_followup(args, conn, cfg):
    if (why := can_send_now(datetime.now(), args.force)) or not _sender_ready(cfg, args.dry_run):
        if why:
            print(why)
        return
    cutoff = (datetime.now() - timedelta(days=cfg.sending.followup_after_days)).isoformat()
    room = cfg.sending.daily_limit - sent_today(conn)
    rows = conn.execute("SELECT * FROM targets WHERE status = 'sent' AND sent_at < ? ORDER BY sent_at",
                        (cutoff,)).fetchall()
    rows = [r for r in rows if not db.is_suppressed(conn, r["email"])][:room]
    items = [(r["email"], compose.FOLLOWUP_SUBJECT_PREFIX + r["subject"],
              compose.compose_followup(r["name"], r["kind"], cfg.sender), r["message_id"], r) for r in rows]

    def on_sent(row, mid):
        db.update(conn, row["place_id"], status="followed", followup_id=mid, followup_at=db.now())
        conn.commit()

    if not items:
        print("追いメールの対象はありません")
        return
    _send_loop(items, cfg, args.dry_run, on_sent, args.force)


# ── poll ────────────────────────────────────────────────
def cmd_poll(args, conn, cfg):
    from .mailer import SmtpSender, build_message, fetch_since

    incoming = fetch_since(cfg.mail, date.today() - timedelta(days=args.days))
    reports = replies.process(conn, incoming)
    if not reports:
        print("新しい返信はありません")
        return
    text = replies.render_report(reports)
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"report_{datetime.now():%Y%m%d_%H%M}.txt"
    path.write_text(text, encoding="utf-8")
    print(text)
    hot = sum(r["label"] in replies.HOT for r in reports)
    if cfg.notify.report_to:
        with SmtpSender(cfg.mail) as smtp:
            smtp.send(build_message(cfg.sender, cfg.notify.report_to,
                                    f"【返信報告】電話すべき先 {hot}件", text))
    replies.post_webhook(cfg.notify.webhook_url, text)


# ── status / phone-list ─────────────────────────────────
def cmd_status(args, conn, cfg):
    print(f"今月の Places リクエスト: {db.api_requests(conn)}/{cfg.targeting.monthly_request_budget or '無制限'}\n")
    for status, n in sorted(db.counts(conn).items()):
        print(f"{status:10s} {n:6d}")
    print("\n除外の内訳:")
    for r in conn.execute("SELECT exclusion, COUNT(*) n FROM targets WHERE status='excluded' GROUP BY exclusion"):
        print(f"  {r['exclusion']:16s} {r['n']:6d}")
    print("\n口コミ件数の分布（収集済み全体）:")
    bands = [(0, 30), (30, 100), (100, 300), (300, 1000), (1000, 3000), (3000, 10000), (10000, 10**9)]
    for lo, hi in bands:
        n = conn.execute("SELECT COUNT(*) FROM targets WHERE reviews >= ? AND reviews < ?", (lo, hi)).fetchone()[0]
        mark = "◀ 対象" if lo >= cfg.targeting.min_reviews and hi <= cfg.targeting.max_reviews + 1 else ""
        print(f"  {lo:>6}〜{hi if hi < 10**9 else '':<6} {n:6d} {mark}")
    print("\n返信の内訳:")
    for r in conn.execute("SELECT reply_class, COUNT(*) n FROM targets WHERE status='replied' GROUP BY reply_class"):
        print(f"  {replies.CLASSES.get(r['reply_class'], r['reply_class']):8s} {r['n']:6d}")


def cmd_phone_list(args, conn, cfg):
    """メールを送れない（フォームのみ・アドレスなし・サイトなし）対象帯の社寺を、電話先として書き出す。"""
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"phone_{date.today():%Y%m%d}.csv"
    rows = conn.execute(
        "SELECT * FROM targets WHERE status='excluded' AND exclusion IN ('form_only','no_email','no_website') "
        "AND reviews BETWEEN ? AND ? ORDER BY prefecture, reviews DESC",
        (cfg.targeting.min_reviews, cfg.targeting.max_reviews)).fetchall()
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["社寺名", "種別", "都道府県", "住所", "口コミ数", "サイト", "理由"])
        for r in rows:
            w.writerow([r["name"], r["kind"], r["prefecture"], r["address"], r["reviews"], r["website"], r["exclusion"]])
    print(f"{len(rows)}件 → {path}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m juyohin.cli", description="神社仏閣向け授与品営業")
    p.add_argument("--db", default=str(db.DB_PATH))
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("collect", help="Places で候補を集める")
    s.add_argument("--areas", nargs="*")
    s.add_argument("--areas-file")
    s.add_argument("--kinds", nargs="+", default=["shrine", "temple"], choices=["shrine", "temple"])
    s.add_argument("--refresh", action="store_true", help="検索済みの語も検索し直す")
    s.set_defaults(func=cmd_collect)

    for name, func, default in [("crawl", cmd_crawl, 50), ("profile", cmd_profile, 50), ("draft", cmd_draft, 50),
                                ("review-export", cmd_review_export, 100)]:
        s = sub.add_parser(name)
        s.add_argument("--limit", type=int, default=default)
        if name == "draft":
            s.add_argument("--month", type=int, help="季節フックの基準月（既定は今月）")
        s.set_defaults(func=func)

    s = sub.add_parser("review-import")
    s.add_argument("file")
    s.set_defaults(func=cmd_review_import)

    for name, func in [("send", cmd_send), ("followup", cmd_followup)]:
        s = sub.add_parser(name)
        s.add_argument("--limit", type=int)
        s.add_argument("--dry-run", action="store_true")
        s.add_argument("--force", action="store_true", help="送信時間帯の制限を外す")
        s.set_defaults(func=func)

    s = sub.add_parser("poll", help="返信を確認して報告する")
    s.add_argument("--days", type=int, default=30)
    s.set_defaults(func=cmd_poll)

    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("phone-list").set_defaults(func=cmd_phone_list)

    args = p.parse_args(argv)
    conn = db.connect(args.db)
    args.func(args, conn, load())
    return 0


if __name__ == "__main__":
    sys.exit(main())
