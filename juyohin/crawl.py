"""公式サイトの巡回：公開されているアドレスと、文面づくりの材料を集める。

特定電子メール法の「営業目的で公開されたアドレスへの送信」の例外を使うため、
次のどれかに当たる社寺は除外する。
  - サイトに営業・広告メールを断る表記がある（no_solicitation）
  - アドレスがなく、問い合わせフォームしかない（form_only） → 電話先リストに回す
  - アドレスが見つからない（no_email）

アドレスを載せていたページのURLと日時を残し、公開の証跡にする。
robots.txt で禁止されたページは読まない。同じサイトへの取得は間隔をあける。
"""

from __future__ import annotations

import re
import time
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; juyohin-research/0.1)"
MAX_PAGES = 6
MAX_TEXT = 20000
PAUSE_SEC = 2.0

# 本文の材料と連絡先が載っていそうなページ
LINK_HINTS = re.compile(
    r"問い?合わ?せ|お問合|連絡|アクセス|所在地|社務所|寺務所|contact|access|inquiry|"
    r"由緒|御由緒|縁起|歴史|御祭神|ご祭神|御本尊|ご本尊|授与|御守|お守|行事|祭事|年中|about",
    re.I,
)

# 営業・広告メールの拒否表記
NO_SOLICITATION = re.compile(
    r"(営業|広告|勧誘|セールス|宣伝|売り込み|販売|業者)[^。\n]{0,20}"
    r"(お断り|ご遠慮|禁止|控え|受け付けて(い|お)りません|お受け(いた)?し(てい|ており)ません|対応(いた)?し(てい|ており)ません|ご返信(いた)?しかね)"
)

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# よくある難読化：＠、[at]、(at)、 at 、★ など
OBFUSCATED_AT = re.compile(r"\s*(＠|\[\s*at\s*\]|\(\s*at\s*\)|（\s*at\s*）|\s+at\s+|★|☆|▲|◆)\s*", re.I)
OBFUSCATED_DOT = re.compile(r"\s*(\[\s*dot\s*\]|\(\s*dot\s*\)|．)\s*", re.I)
IGNORED_EMAIL = re.compile(
    r"\.(png|jpe?g|gif|webp|svg)$|@(example\.|sentry|wixpress\.com|.*\.wix\.com)|^(noreply|no-reply)@", re.I
)


@dataclass
class CrawlResult:
    emails: list[tuple[str, str]] = field(default_factory=list)  # (address, page_url)
    refusal: str = ""            # 拒否表記の抜粋
    has_form: bool = False
    text: str = ""
    pages: list[str] = field(default_factory=list)

    def best_email(self, website: str) -> tuple[str, str] | None:
        """サイトと同じドメインのアドレスを優先する。"""
        if not self.emails:
            return None
        host = urllib.parse.urlparse(website).hostname or ""
        site_domain = ".".join(host.split(".")[-2:])
        for addr, url in self.emails:
            if addr.split("@")[1].endswith(site_domain):
                return addr, url
        return self.emails[0]


def extract_emails(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for a in soup.select('a[href^="mailto:"]'):
        addr = urllib.parse.unquote(a["href"][7:]).split("?")[0].strip()
        found.append(addr)
    text = soup.get_text(" ")
    deobf = OBFUSCATED_DOT.sub(".", OBFUSCATED_AT.sub("@", text))
    found += EMAIL.findall(deobf)
    out = []
    for addr in found:
        addr = addr.strip(".").lower()
        if EMAIL.fullmatch(addr) and not IGNORED_EMAIL.search(addr) and addr not in out:
            out.append(addr)
    return out


def find_refusal(text: str) -> str:
    m = NO_SOLICITATION.search(text)
    return m.group(0) if m else ""


def has_contact_form(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    for form in soup.find_all("form"):
        if form.find("textarea"):
            return True
    return bool(re.search(r"(google\.com/forms|forms\.gle|formrun|form\.run|formzu|tayori)", html))


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text("\n")
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def candidate_links(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    host = urllib.parse.urlparse(base).hostname
    links = []
    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True) + " " + a["href"]
        if not LINK_HINTS.search(label):
            continue
        url = urllib.parse.urljoin(base, a["href"]).split("#")[0]
        if urllib.parse.urlparse(url).hostname == host and url not in links and url != base:
            links.append(url)
    return links


class Fetcher:
    """robots.txt を守り、間隔をあけて取得する。テストでは差し替える。"""

    def __init__(self, session=None, pause: float = PAUSE_SEC):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.pause = pause
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        parts = urllib.parse.urlparse(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                resp = self.session.get(root + "/robots.txt", timeout=15)
                rp.parse(resp.text.splitlines() if resp.status_code == 200 else [])
                self._robots[root] = rp
            except requests.RequestException:
                self._robots[root] = None
        rp = self._robots[root]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    def get(self, url: str) -> str | None:
        if not self.allowed(url):
            return None
        try:
            resp = self.session.get(url, timeout=20)
        except requests.RequestException:
            return None
        finally:
            time.sleep(self.pause)
        if resp.status_code != 200 or "html" not in resp.headers.get("Content-Type", "html"):
            return None
        resp.encoding = resp.apparent_encoding or resp.encoding
        return resp.text


def crawl(website: str, fetcher: Fetcher | None = None) -> CrawlResult:
    fetcher = fetcher or Fetcher()
    result = CrawlResult()
    top = fetcher.get(website)
    if top is None:
        return result
    queue = [(website, top)]
    for link in candidate_links(top, website)[: MAX_PAGES - 1]:
        html = fetcher.get(link)
        if html:
            queue.append((link, html))
    texts = []
    for url, html in queue:
        result.pages.append(url)
        for addr in extract_emails(html):
            if addr not in [e for e, _ in result.emails]:
                result.emails.append((addr, url))
        text = visible_text(html)
        if not result.refusal:
            result.refusal = find_refusal(text)
        result.has_form = result.has_form or has_contact_form(html)
        texts.append(f"=== {url}\n{text}")
    result.text = "\n".join(texts)[:MAX_TEXT]
    return result


def judge(result: CrawlResult, website: str) -> tuple[str, str | None, str | None]:
    """巡回結果から (exclusion, email, source_url) を返す。exclusion が空なら送ってよい。"""
    if result.refusal:
        return "no_solicitation", None, None
    best = result.best_email(website)
    if best:
        return "", best[0], best[1]
    if result.has_form:
        return "form_only", None, None
    return "no_email", None, None
