# 授与品営業：神社仏閣への半自動アウトリーチ

全国の社寺から、参拝者が多すぎず少なすぎない規模の社寺を拾います。公式サイトにアドレスを公開している先にだけ、太宰府フォーマットの案内メールを送ります。ゴールは「資料希望」の返信をもらうことで、返信があれば報告が上がり、アポイントは電話で取ります。

```
collect → crawl → profile → draft → review-export
   （CSV を見て承認列に ○ / × を付ける。本文は直接直してよい）
review-import → send → poll（毎日）→ followup（毎日）
```

## ファイル

| パス | 役割 |
| --- | --- |
| `places.py` | Google Places API (New) で候補を集め、神社か寺院かを名前で判定する |
| `crawl.py` | 公式サイトを巡回し、公開アドレス・営業お断りの表記・フォームの有無・本文を集める |
| `profile.py` | Claude が御祭神・系列・行事・パーソナライズの一文を読み取る。根拠の引用を本文と照合し、照合できない項目は捨てる |
| `compose.py` | 太宰府フォーマットの7ブロックを組み立てる。固定ブロックは一字一句このファイルのとおりで、AIには書かせない |
| `mailer.py` | SMTP で送信し、IMAP で受信を確認する（既読にはしない） |
| `replies.py` | 返信を照合して分類し、報告文を作る。「配信停止」はキーワードで判定する |
| `db.py` | SQLite の台帳（`data/juyohin.sqlite3`）と配信停止リスト |
| `cli.py` | コマンド |

## 準備

```bash
pip install -r juyohin/requirements.txt
cp juyohin/config.example.toml juyohin/config.toml   # 送信者情報・SMTP/IMAP を埋める
export GOOGLE_MAPS_API_KEY=...
export ANTHROPIC_API_KEY=...
export JUYOHIN_MAIL_PASSWORD=...
```

## 使い方

```bash
# 1. 候補を集める（都道府県単位だと有名どころに偏るので、本番は市区町村のリストで）
python -m juyohin.cli collect --areas 奈良県 和歌山県
python -m juyohin.cli collect --areas-file juyohin/areas.txt

# 2. 口コミ件数の分布を見て、config.toml の min_reviews / max_reviews を決める
python -m juyohin.cli status

# 3. 対象の件数帯だけ巡回し、下調べして、下書きを作る
python -m juyohin.cli crawl --limit 50
python -m juyohin.cli profile --limit 50
python -m juyohin.cli draft
python -m juyohin.cli review-export          # out/review_YYYYMMDD.csv

# 4. CSV に ○/× を付けて取り込み、送る（平日9〜16時、1日25通、2〜6分の間隔）
python -m juyohin.cli review-import juyohin/out/review_20261117.csv
python -m juyohin.cli send --dry-run         # まず中身を確認
python -m juyohin.cli send

# 5. 毎日：返信を確認して報告する。12日たっても返信がなければ追いメールを1回だけ送る
python -m juyohin.cli poll
python -m juyohin.cli followup

# メールを送れない先（フォームのみ・アドレスなし・サイトなし）を電話先リストとして書き出す
python -m juyohin.cli phone-list

# テスト（ネットワークに接続しない）
python -m pytest juyohin/tests -q
```

## 守ること（特定電子メール法）

- 送るのは、公式サイトに公開されているアドレスだけ。アドレスを載せていたページのURLと取得した日時を台帳に残す（`email_source`, `email_seen_at`）
- サイトに営業・広告メールを断る表記があれば、アドレスが載っていても送らない（`no_solicitation`）
- 本文の末尾に、送信者名・住所・電話番号・受信拒否の方法を必ず入れる（`compose.footer`）。設定が空のままでは `send` が止まる
- 「配信停止」と返信があれば、AIを通さずに配信停止リストに入れる。不達や「不要」の返信も同じリストに入れる
- 追いメールは1回だけ。それ以降は送らない

## 太宰府フォーマットからの変更点

- 締め（`closing_mode = "request"`）：原型は「カタログ、チラシ及びサンプルをご覧いただき」の締めにカタログを添付する形だった。初回は添付もリンクも付けず、「資料希望」の一言の返信をお願いする形に替えている。到達率のためと、返信を電話につなげるため。原型に戻すときは `"original"` にする
- 実績：太宰府の固有名詞は使用許可が取れるまで出さない（`dazaifu_name_allowed`）。相手が天満宮系なら「九州の天満宮様」と書く
- パーソナライズの一文は、名乗りではなく与信ブロックの後に置き、目的ブロックにつなげている

## 未確認のこと

- **会社のメール環境**：Microsoft 365 で基本認証（ユーザー名とパスワードでの SMTP/IMAP）が止められていれば、OAuth 版の `mailer` が必要になる。Google Workspace ならアプリパスワードで動く。情報システム部門に確認すること
- **送信ドメインの認証**：会社のドメインの SPF・DKIM・DMARC が設定されているか。されていないと迷惑メールに振り分けられやすい
- **会社の承認**：会社のアドレスで一斉に営業メールを送ってよいか、社内の規定を確認すること
- **Places API の料金**：`websiteUri` と `userRatingCount` は上位SKUに含まれる。全国を市区町村単位で回すと数千回の検索になるので、料金表で見積もってから回す
- **口コミ件数の閾値**：100〜3,000件は仮の値。`status` の分布を見てから決める
- **LINE WORKS への通知**：`webhook_url` は汎用のJSONを送るだけ。LINE WORKS の Bot API は認証が必要なので、使うならアダプタを足す
