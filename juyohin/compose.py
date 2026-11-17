"""文面の組み立て：太宰府フォーマット（7ブロック）。

文面は Claude に書かせない。固定ブロックは一字一句このファイルのとおりにし、
相手に合わせて変わるのは、表の中から選ぶ部分と、profile で根拠を照合済みの一文だけ。
これで「AIが書いた感」と事実誤認の両方を防ぐ。

太宰府原型からの変更点（closing_mode = "request" のとき）:
  原型の締めは「カタログ、チラシ及びサンプルをご覧いただき」＋カタログ添付。
  初回は添付もリンクも付けず、「資料希望」の一言の返信を引き出す締めに替えている。
  原型に戻すときは closing_mode = "original"。
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Sender, Sending

# ── 固定ブロック（変えない） ─────────────────────────────
BLOCK_CREDIT = "弊社は、約70年間日本の教材や教具を製造販売し、売上高約100億円規模の会社です。"
BLOCK_PURPOSE = "この度は、弊社の開発生産体制を武器に製作したオリジナル授与品のご案内がしたく、ご連絡いたしました。"
BLOCK_CAPABILITY = (
    "社内には、「レーザー」「UV」「刺繍」「箔押し」「シルク」「熱転写」などの加工ができる機械を複数持ち合わせております。"
    "また、デザイナーや設計士も多数在籍しております。"
)
BLOCK_SPEED = "そのため、弊社では最短2週間、最低100個からオリジナルの授与品を製作することが可能です。"

ACHIEVEMENT_NAMED = "現在では既に、太宰府天満宮様をはじめ、多数の神社仏閣様の『オリジナルアクリル御守』や『オリジナルグッズ』を製作しております。"
ACHIEVEMENT_ANON = "現在では既に、九州の著名神社様をはじめ、多数の神社仏閣様の『オリジナルアクリル御守』や『オリジナルグッズ』を製作している実績がございます。"
ACHIEVEMENT_TENMANGU = "現在では既に、九州の天満宮様をはじめ、多数の神社仏閣様の『オリジナルアクリル御守』や『オリジナルグッズ』を製作している実績がございます。"

# ── 季節フック（送信月→2〜3ヶ月先の行事） ──────────────────
SEASON_HOOKS = {
    1: ["春の入学・学業御守", "桜モチーフの授与品", "夏詣グッズ"],
    2: ["春の入学・学業御守", "桜モチーフの授与品", "夏詣グッズ"],
    3: ["風鈴", "七夕笹", "夏越の大祓関連の授与品"],
    4: ["風鈴", "七夕笹", "夏詣グッズ"],
    5: ["風鈴", "七夕笹", "提灯", "七五三グッズ"],
    6: ["風鈴", "七夕笹", "提灯", "七五三グッズ"],
    7: ["七五三グッズ", "秋の例大祭関連の授与品", "提灯"],
    8: ["七五三グッズ", "秋の例大祭関連の授与品", "提灯"],
    9: ["破魔矢・干支物などの初詣関連の授与品", "七五三グッズの補充"],
    10: ["破魔矢・干支物などの初詣関連の授与品", "七五三グッズの補充"],
    11: ["干支物", "受験シーズンの学業御守", "春の入学関連の授与品"],
    12: ["干支物", "受験シーズンの学業御守", "春の入学関連の授与品"],
}
TEMPLE_REPLACEMENTS = {"七五三グッズ": "御朱印関連グッズ", "七五三グッズの補充": "御朱印関連グッズ",
                       "夏越の大祓関連の授与品": "花まつり関連の授与品"}

# ── 系列ごとの主力御守（確信がある場合だけ使う） ───────────────
LINEAGE_LINES = {
    "inari": "白狐など貴社ならではの意匠を活かしたアクリル御守や商売繁昌の授与品など、",
    "tenmangu": "梅や神牛の意匠を活かした学業御守や合格祈願の授与品など、",
    "hachiman": "必勝・厄除の御守や貴社ならではの授与品など、",
    "kannon_jizo": "安産・子育ての御守や御朱印関連グッズなど、",
}

SUBJECT = "【オリジナル授与品のご案内】株式会社アーテック（創業70年・教材メーカー）"
FOLLOWUP_SUBJECT_PREFIX = "Re: "


@dataclass
class Draft:
    subject: str
    body: str
    notes: list[str]


def honorific(kind: str) -> str:
    return "貴寺院様" if kind == "temple" else "貴社"


def season_items(month: int, kind: str, shichigosan: bool) -> list[str]:
    items = list(SEASON_HOOKS[month])
    if kind == "temple" and not shichigosan:
        items = [TEMPLE_REPLACEMENTS.get(i, i) for i in items]
    out = []
    for i in items:
        if i not in out:
            out.append(i)
    return out[:3]


def join_items(items: list[str]) -> str:
    return "、".join(items)


def achievement(lineage: str, named_allowed: bool) -> str:
    if named_allowed:
        return ACHIEVEMENT_NAMED
    if lineage == "tenmangu":
        return ACHIEVEMENT_TENMANGU
    return ACHIEVEMENT_ANON


def closing(kind: str, mode: str, catalog_name: str) -> list[str]:
    if kind == "temple":
        relation = "貴寺院様の授与品を通じた参拝者様とのご縁づくりに、弊社の生産体制をお役立ていただければ幸いです。"
    else:
        relation = "貴社の授与品を通じた崇敬者様とのご縁づくりに、弊社の生産体制をお役立ていただければ幸いです。"
    if mode == "original":
        return [relation, "",
                "どうか一度弊社のカタログ、チラシ及びサンプルをご覧いただき、ご検討いただければと存じます。",
                "どうぞよろしくお願いします。", "", f"総合カタログ：{catalog_name}"]
    return [relation, "",
            "ご興味をお持ちいただけましたら、本メールにご返信いただければ、カタログ・チラシ等の詳細資料をお送りいたします。",
            "「資料希望」の一言だけでも構いません。",
            "どうぞよろしくお願いします。"]


def footer(sender: Sender) -> list[str]:
    """特定電子メール法の表示義務（送信者・住所・問い合わせ先・受信拒否の方法）。"""
    return [
        "──────────────",
        f"{sender.company}　{sender.department}",
        f"{sender.person}",
        f"住所：{sender.address}",
        f"電話：{sender.phone}",
        f"メール：{sender.email}",
        "",
        "今後このようなご案内が不要の場合は、お手数ですが本メールに「配信停止」とご返信ください。",
        "以後のご連絡は差し控えます。",
    ]


def compose(name: str, kind: str, profile: dict, month: int, sender: Sender, sending: Sending) -> Draft:
    notes: list[str] = []
    kind = profile.get("kind") if profile.get("kind") in ("shrine", "temple") else kind
    if kind not in ("shrine", "temple"):
        kind = "shrine"
        notes.append("神社か寺院か判定できず、神社として書いた")
    lineage = profile.get("lineage", "unknown")
    if kind == "temple" and lineage in ("inari", "tenmangu", "hachiman", "shinmei"):
        lineage = "unknown"  # 寺院に神社系の系列が付いたら信用しない

    hello = [f"{name}", "ご担当者様", "", "お世話になります。", f"{sender.company}の{sender.person}と申します。"]
    personal = profile.get("personal_line", "").strip()

    lines = hello
    lines += ["", BLOCK_CREDIT]
    if personal:
        # 一文は目的ブロックにつなげる（「〜貴社に、」→「弊社の開発生産体制を…ご案内がしたく」）
        lines += [personal + "弊社の開発生産体制を武器に製作したオリジナル授与品のご案内がしたく、ご連絡いたしました。"]
    else:
        lines += [BLOCK_PURPOSE]
    lines += ["", BLOCK_CAPABILITY, BLOCK_SPEED, ""]

    ach = achievement(lineage, sending.dazaifu_name_allowed)
    lineage_line = LINEAGE_LINES.get(lineage)
    if lineage_line:
        ach += f"同様に、{lineage_line}お作りすることが可能です。"
    lines += [ach, ""]

    items = season_items(month, kind, bool(profile.get("does_shichigosan")))
    lines += [f"また、オリジナル商品だけでなく、{join_items(items)}などのお話も頂いております。", ""]
    lines += closing(kind, sending.closing_mode, sending.catalog_name)
    lines += [""] + footer(sender)

    if not sending.dazaifu_name_allowed:
        notes.append("実績は匿名表記（太宰府の固有名詞の使用許可が取れたら dazaifu_name_allowed=true）")
    if profile.get("dropped"):
        notes.append(f"根拠が本文に見当たらず捨てた項目: {', '.join(profile['dropped'])}")
    if not personal:
        notes.append("パーソナライズの一文なし（汎用形）")
    return Draft(subject=SUBJECT, body="\n".join(lines), notes=notes)


def compose_followup(name: str, kind: str, sender: Sender) -> str:
    """追いメール。1回だけ。短く、押さない。"""
    target = "貴寺院様" if kind == "temple" else "貴社"
    return "\n".join([
        f"{name}", "ご担当者様", "",
        "お世話になります。",
        f"{sender.company}の{sender.person}です。",
        "",
        f"先日、オリジナル授与品のご案内をお送りいたしました。ご多用のところ重ねてのご連絡となり恐れ入ります。",
        f"{target}の授与品のご検討の折に、資料だけでもお手元に置いていただければ幸いです。",
        "ご希望の際は、本メールに「資料希望」とご返信ください。",
        "",
        "本件でのご連絡は、こちらで最後とさせていただきます。",
        "どうぞよろしくお願いします。",
        "",
        *footer(sender),
    ])
