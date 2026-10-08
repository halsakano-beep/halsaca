# 茶柱：業種特化の入札速報

官公需情報ポータルサイトの検索APIで入札案件を集め、Claudeで要約して週刊メールにする。

## ファイル

| パス | 役割 | フェーズ |
| --- | --- | --- |
| `kkj.py` | 官公需APIのクライアントと応答XMLの解析 | 0〜 |
| `industries.py` | 業種ごとの検索キーワードと、本業と重なる除外語 | 0〜 |
| `survey.py` | 業種×地域の案件数を集計し、配信する業種を選ぶ | 0 |
| `digest.py` | 直近7日の案件を要約し、メール本文（テキスト・HTML）を作る | 1〜 |
| `templates/outreach_email.md` | 無料版の登録をお願いする案内メール | 2 |
| `site/index.html` | 申し込みページの下書き（GitHub Pages用） | 1 |
| `tests/` | APIに接続しないテスト | ― |

## 使い方

```bash
pip install -r chabashira/requirements.txt

# APIの生の応答を確認する（初回に必ず。要素名がずれていれば kkj.FIELD_CANDIDATES を直す）
python -m chabashira.kkj 清掃 --pref 大阪府 --dump

# フェーズ0：業種×地域の案件数（直近90日）
python -m chabashira.survey --prefs 大阪府 兵庫県 京都府 --days 90

# フェーズ1：週刊速報の本文を out/ に作る（ANTHROPIC_API_KEY が必要）
python -m chabashira.digest --industry 清掃 --prefs 大阪府 兵庫県

# テスト
python -m pytest chabashira/tests -q
```

## 未確認のこと

- 応答XMLの要素名は2016年版の仕様書と公開記事からの想定。実際の応答で確かめる
- 公示日での絞り込み（`CFT_Issue_Date`）の書式は未確認。こちら側でも日付で絞るので、効かなくても結果は正しい
- APIの商用利用の可否は運営者に問い合わせ中（手順書の手順5）
- 要約には Claude Opus 5.5 を使う。安全判定で拒否された場合に別のモデルで自動的にやり直す設定（server-side fallbacks）を有効にしている

## 守ること

- APIの呼び出しの間は1.5秒以上あける（`kkj.polite_pause`）
- 配信には出典として官公需情報ポータルサイトの名前とリンクを入れる
- 本業と重なる分野の案件は配信しない（`industries.EXCLUDED_WORDS`）
