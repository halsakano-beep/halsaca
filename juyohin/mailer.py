"""送信（SMTP）と受信の確認（IMAP）。

会社のメールが Google Workspace でも Microsoft 365 でも使えるよう、標準の SMTP/IMAP にしている。
Microsoft 365 で基本認証が止められている場合は、OAuth 版に差し替える必要がある（README 参照）。
"""

from __future__ import annotations

import email
import imaplib
import re
import smtplib
from dataclasses import dataclass
from datetime import date
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr

from .config import Mail, Sender


def build_message(sender: Sender, to: str, subject: str, body: str,
                  in_reply_to: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((f"{sender.company} {sender.person}", sender.email))
    msg["To"] = to
    msg["Subject"] = subject
    domain = sender.email.split("@")[-1] if "@" in sender.email else None
    msg["Message-ID"] = make_msgid(domain=domain)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.set_content(body)  # テキストのみ。HTML・画像・リンク計測は入れない
    return msg


class SmtpSender:
    def __init__(self, mail: Mail):
        self.mail = mail
        self.conn: smtplib.SMTP | None = None

    def __enter__(self):
        self.conn = smtplib.SMTP(self.mail.smtp_host, self.mail.smtp_port, timeout=60)
        self.conn.starttls()
        self.conn.login(self.mail.username, self.mail.password)
        return self

    def send(self, msg: EmailMessage) -> None:
        self.conn.send_message(msg)

    def __exit__(self, *exc):
        if self.conn:
            self.conn.quit()


@dataclass
class Incoming:
    from_addr: str
    subject: str
    body: str
    in_reply_to: list[str]   # In-Reply-To と References に出てくる Message-ID
    is_bounce: bool
    raw_ids_in_body: list[str]


MSGID = re.compile(r"<[^<>\s]+@[^<>\s]+>")


def _text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() in ("text/plain", "message/delivery-status", "text/rfc822-headers"):
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(payload.decode(part.get_content_charset() or "utf-8", "replace"))
            elif part.get_content_type() == "message/rfc822":
                parts.append(str(part.get_payload(0)))
        return "\n".join(parts)
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(msg.get_content_charset() or "utf-8", "replace")


def parse_incoming(raw: bytes) -> Incoming:
    msg = email.message_from_bytes(raw)
    from_addr = parseaddr(msg.get("From", ""))[1].lower()
    subject = str(make_header(decode_header(msg.get("Subject", ""))))
    refs = MSGID.findall((msg.get("In-Reply-To", "") or "") + " " + (msg.get("References", "") or ""))
    body = _text(msg)
    bounce = bool(re.match(r"(mailer-daemon|postmaster)@", from_addr)) or "delivery-status" in msg.get_content_type() \
        or msg.get_content_type() == "multipart/report"
    return Incoming(from_addr, subject, body, refs, bounce, MSGID.findall(body) if bounce else [])


def fetch_since(mail: Mail, since: date) -> list[Incoming]:
    conn = imaplib.IMAP4_SSL(mail.imap_host, mail.imap_port)
    try:
        conn.login(mail.username, mail.password)
        conn.select("INBOX", readonly=True)  # 既読にしない
        _, data = conn.search(None, "SINCE", since.strftime("%d-%b-%Y"))
        out = []
        for num in data[0].split():
            _, parts = conn.fetch(num, "(BODY.PEEK[])")
            out.append(parse_incoming(parts[0][1]))
        return out
    finally:
        conn.logout()
