"""ネットワークにもAPIにも接続しないテスト。"""

from datetime import datetime
from email.message import EmailMessage

from juyohin import compose, crawl, db, places, profile, replies
from juyohin.config import Sender, Sending
from juyohin.mailer import build_message, parse_incoming

SENDER = Sender(person="坂野", address="〒000-0000 テスト県", phone="000-0000-0000", email="sakano@example.co.jp")

TOP_HTML = """<html><body>
<h1>○○稲荷神社</h1>
<a href="/yuisho/">御由緒</a> <a href="/contact.html">お問い合わせ</a> <a href="https://other.example/">外部</a>
<p>商売繁昌の神として古くから崇敬を集める稲荷社です。</p>
</body></html>"""
CONTACT_HTML = """<html><body><p>社務所 info＠inari-test.jp（＠を半角に）</p>
<a href="mailto:info@inari-test.jp">メール</a></body></html>"""
YUISHO_HTML = "<html><body><p>御祭神 宇迦之御魂大神。秋の例大祭は十月。</p></body></html>"
REFUSAL_HTML = "<html><body><p>※営業・勧誘目的のメールはご遠慮ください。</p><p>info@foo.jp</p></body></html>"
FORM_HTML = "<html><body><form><textarea name=q></textarea></form></body></html>"


class FakeFetcher:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url):
        return self.pages.get(url)


# ── places ──
def test_classify():
    assert places.classify("伏見稲荷大社") == "shrine"
    assert places.classify("清水寺") == "temple"
    assert places.classify("〇〇天満宮") == "shrine"
    assert places.classify("神社前駅") == "unknown"
    assert places.classify("〇〇寺幼稚園") == "unknown"
    assert places.classify("〇〇", ["buddhist_temple"]) == "temple"


def test_collect_dedupes_and_drops_unknown():
    def fake(query):
        yield {"place_id": "a", "name": "A神社", "kind": "shrine"}
        yield {"place_id": "a", "name": "A神社", "kind": "shrine"}
        yield {"place_id": "b", "name": "B駐車場", "kind": "unknown"}

    got = list(places.collect(["大阪府"], ["shrine", "temple"], searcher=fake))
    assert [g["place_id"] for g in got] == ["a"]


def test_parse_place():
    p = places.parse_place({"id": "x", "displayName": {"text": "△△八幡宮"}, "formattedAddress": "日本、〒1 奈良県…",
                            "userRatingCount": 420, "websiteUri": "https://h.jp/"})
    assert p["kind"] == "shrine" and p["prefecture"] == "奈良県" and p["reviews"] == 420


# ── crawl ──
def test_crawl_finds_public_email_and_text():
    f = FakeFetcher({"https://inari-test.jp/": TOP_HTML, "https://inari-test.jp/contact.html": CONTACT_HTML,
                     "https://inari-test.jp/yuisho/": YUISHO_HTML})
    r = crawl.crawl("https://inari-test.jp/", f)
    assert ("info@inari-test.jp", "https://inari-test.jp/contact.html") in r.emails
    assert "宇迦之御魂大神" in r.text
    assert "other.example" not in " ".join(r.pages)
    assert crawl.judge(r, "https://inari-test.jp/") == ("", "info@inari-test.jp", "https://inari-test.jp/contact.html")


def test_obfuscated_email():
    assert crawl.extract_emails("<p>jimusho [at] tera.or.jp</p>") == ["jimusho@tera.or.jp"]
    assert crawl.extract_emails("<p>logo@2x.png</p>") == []


def test_refusal_excludes_even_with_email():
    r = crawl.crawl("https://foo.jp/", FakeFetcher({"https://foo.jp/": REFUSAL_HTML}))
    assert r.emails and r.refusal
    assert crawl.judge(r, "https://foo.jp/")[0] == "no_solicitation"


def test_form_only_and_no_email():
    r = crawl.crawl("https://f.jp/", FakeFetcher({"https://f.jp/": FORM_HTML}))
    assert crawl.judge(r, "https://f.jp/")[0] == "form_only"
    r = crawl.crawl("https://n.jp/", FakeFetcher({"https://n.jp/": "<p>hello</p>"}))
    assert crawl.judge(r, "https://n.jp/")[0] == "no_email"


# ── profile ──
def test_verify_drops_unsupported_claims():
    text = "御祭神 宇迦之御魂大神。商売繁昌の神として古くから崇敬を集める稲荷社です。"
    prof = {"personal_line": "商売繁昌の神として崇敬を集める貴社に、",
            "evidence": "商売繁昌の神として古くから崇敬を集める",
            "deity": "菅原道真公", "deity_evidence": "御祭神 菅原道真公",  # 本文にない＝捏造
            "lineage": "inari", "lineage_evidence": "稲荷社です"}
    out = profile.verify(prof, text)
    assert out["personal_line"]
    assert out["deity"] == "" and "deity" in out["dropped"]
    assert out["lineage"] == "inari"


# ── compose ──
def test_compose_keeps_fixed_blocks_and_footer():
    d = compose.compose("○○稲荷神社", "shrine", {"lineage": "inari"}, 11, SENDER, Sending())
    for block in (compose.BLOCK_CREDIT, compose.BLOCK_CAPABILITY, compose.BLOCK_SPEED):
        assert block in d.body
    assert "九州の著名神社様" in d.body and "太宰府" not in d.body
    assert "白狐" in d.body
    assert "干支物" in d.body
    assert "資料希望" in d.body and "総合カタログ：" not in d.body
    assert "配信停止" in d.body and SENDER.address in d.body and SENDER.phone in d.body
    assert "崇敬者様" in d.body


def test_compose_temple_vocabulary_and_no_shichigosan():
    d = compose.compose("△△寺", "temple", {"lineage": "inari"}, 7, SENDER, Sending())
    assert "貴寺院様" in d.body and "参拝者様" in d.body
    assert "七五三" not in d.body and "御朱印関連グッズ" in d.body
    assert "白狐" not in d.body  # 寺院に稲荷系は付けない


def test_compose_original_mode_and_named():
    d = compose.compose("x神社", "shrine", {}, 1, SENDER,
                        Sending(closing_mode="original", dazaifu_name_allowed=True))
    assert "太宰府天満宮様" in d.body and "総合カタログ：" in d.body


def test_personal_line_inserted():
    d = compose.compose("x神社", "shrine", {"personal_line": "学問の神様として多くの受験生が参拝される貴社に、"},
                        1, SENDER, Sending())
    assert "受験生が参拝される貴社に、弊社の開発生産体制" in d.body


# ── db / replies ──
def _seed():
    conn = db.connect(":memory:")
    db.upsert_place(conn, {"place_id": "p1", "name": "○○神社", "kind": "shrine", "reviews": 500})
    db.update(conn, "p1", status="sent", email="info@jinja.jp", message_id="<abc@example.co.jp>", sent_at=db.now())
    return conn


def _incoming(body, in_reply_to="<abc@example.co.jp>", frm="info@jinja.jp"):
    m = EmailMessage()
    m["From"] = frm
    m["Subject"] = "Re: ご案内"
    if in_reply_to:
        m["In-Reply-To"] = in_reply_to
    m.set_content(body)
    return parse_incoming(m.as_bytes())


def test_reply_matched_and_classified():
    conn = _seed()
    reports = replies.process(conn, [_incoming("資料希望です。宮司 山田")], classifier=lambda b: ("request", "資料を希望"))
    assert reports[0]["label"] == "request"
    assert conn.execute("SELECT status FROM targets").fetchone()[0] == "replied"
    assert "電話すべき先 1件" in replies.render_report(reports)


def test_unsubscribe_is_keyword_not_ai():
    def boom(_):
        raise AssertionError("AI を呼んではいけない")

    assert replies.classify("今後このようなメールは不要です", client=None)[0] == "unsubscribe"
    conn = _seed()
    replies.process(conn, [_incoming("配信停止でお願いします")], classifier=replies.classify)
    assert db.is_suppressed(conn, "info@jinja.jp")


def test_unsubscribe_ignores_quoted_original():
    # 引用された元メールの「配信停止」で誤判定しない
    label, _ = replies.classify("ぜひ資料をお願いします\n> 配信停止とご返信ください", client=FakeClaude("request"))
    assert label == "request"


def test_bounce_suppresses():
    conn = _seed()
    m = EmailMessage()
    m["From"] = "MAILER-DAEMON@mx.example"
    m["Subject"] = "Undelivered"
    m.set_content("Message-ID: <abc@example.co.jp>\nUser unknown")
    replies.process(conn, [parse_incoming(m.as_bytes())], classifier=lambda b: ("other", ""))
    assert conn.execute("SELECT status FROM targets").fetchone()[0] == "bounced"


def test_email_dedupe_and_suppress_domain():
    conn = _seed()
    assert db.email_taken(conn, "info@jinja.jp", "other")
    db.suppress(conn, "@spam.jp", "manual")
    assert db.is_suppressed(conn, "a@spam.jp")


def test_message_is_plain_text_with_id():
    msg = build_message(SENDER, "info@jinja.jp", "件名", "本文", in_reply_to="<abc@x>")
    assert msg["Message-ID"].endswith("@example.co.jp>")
    assert msg["In-Reply-To"] == "<abc@x>"
    assert msg.get_content_type() == "text/plain"


def test_send_window():
    from juyohin.cli import can_send_now

    assert can_send_now(datetime(2026, 11, 17, 10), False) == ""      # 火曜10時
    assert can_send_now(datetime(2026, 11, 21, 10), False)            # 土曜
    assert can_send_now(datetime(2026, 11, 17, 20), False)            # 夜
    assert can_send_now(datetime(2026, 11, 21, 20), True) == ""


class FakeClaude:
    """anthropic クライアントの代わり。"""

    def __init__(self, label):
        self.label = label
        self.beta = self
        self.messages = self

    def create(self, **kwargs):
        import json
        from types import SimpleNamespace

        text = json.dumps({"label": self.label, "summary": "要約"})
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])
