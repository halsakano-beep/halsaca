"""設定の読み込み。

秘密情報（パスワード・APIキー）は config.toml に書かず、環境変数で渡す。
config.toml は .gitignore 済み。雛形は config.example.toml。
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.toml"
DATA_DIR = BASE_DIR / "data"
OUT_DIR = BASE_DIR / "out"


@dataclass
class Sender:
    """特定電子メール法で本文に必ず入れる送信者情報。"""

    person: str = "●●"            # 担当者名
    company: str = "株式会社アーテック"
    department: str = "法人事業部"
    address: str = ""              # 住所（必須）
    phone: str = ""                # 苦情・問い合わせ先（必須）
    email: str = ""                # 送信元アドレス＝受信拒否の通知先


@dataclass
class Mail:
    smtp_host: str = ""
    smtp_port: int = 587
    imap_host: str = ""
    imap_port: int = 993
    username: str = ""
    # パスワードは環境変数 JUYOHIN_MAIL_PASSWORD

    @property
    def password(self) -> str:
        return os.environ.get("JUYOHIN_MAIL_PASSWORD", "")


@dataclass
class Targeting:
    # Googleマップの口コミ件数を「参拝者の多さ」の代わりに使う。
    # 多すぎる（観光地化した大社）と少なすぎる（無人の小社）を外す。
    min_reviews: int = 100
    max_reviews: int = 3000


@dataclass
class Sending:
    daily_limit: int = 50
    min_interval_sec: int = 120     # 1通ごとの間隔（下限）
    max_interval_sec: int = 360     # 1通ごとの間隔（上限）
    followup_after_days: int = 12   # 返信がなければ1回だけ追いメール
    # 実績ブロック：太宰府天満宮の固有名詞の使用許可があるか
    dazaifu_name_allowed: bool = False
    # 締め：request＝「資料希望」の返信を促す / original＝太宰府原型（カタログ添付前提）
    closing_mode: str = "request"
    catalog_name: str = "総合カタログ.pdf"


@dataclass
class Notify:
    report_to: str = ""             # 返信の報告を受け取るアドレス
    webhook_url: str = ""           # 任意。LINE WORKS等の受信Webhook


@dataclass
class Config:
    sender: Sender = field(default_factory=Sender)
    mail: Mail = field(default_factory=Mail)
    targeting: Targeting = field(default_factory=Targeting)
    sending: Sending = field(default_factory=Sending)
    notify: Notify = field(default_factory=Notify)

    def missing_for_sending(self) -> list[str]:
        """送信の前に埋まっていなければならない項目。"""
        need = {
            "sender.person": self.sender.person not in ("", "●●"),
            "sender.address": bool(self.sender.address),
            "sender.phone": bool(self.sender.phone),
            "sender.email": bool(self.sender.email),
            "mail.smtp_host": bool(self.mail.smtp_host),
            "mail.username": bool(self.mail.username),
            "環境変数 JUYOHIN_MAIL_PASSWORD": bool(self.mail.password),
        }
        return [k for k, ok in need.items() if not ok]


def load(path: Path = CONFIG_PATH) -> Config:
    if not path.exists():
        return Config()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return Config(
        sender=Sender(**raw.get("sender", {})),
        mail=Mail(**raw.get("mail", {})),
        targeting=Targeting(**raw.get("targeting", {})),
        sending=Sending(**raw.get("sending", {})),
        notify=Notify(**raw.get("notify", {})),
    )
