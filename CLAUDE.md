# CLAUDE.md
<!-- このファイルはClaude Codeが起動時に自動で読み込む。編集・更新して使う。 -->

## プロジェクト概要

Threads（スレッズ）に自動投稿し、楽天アフィリエイトで収益化するPythonボット。
GitHub Actionsで3時間ごとに自動実行される。

**目標：商品紹介ではなく、インプレッション・コメント・保存を最大化する投稿を自動生成すること。**

---

## 技術スタック

| 項目 | 内容 |
|------|------|
| 言語 | Python 3.11 |
| DB | Supabase（PostgreSQL） |
| AI生成 | Google Gemini API（`google-genai`パッケージ） |
| 投稿先 | Threads Graph API（`graph.threads.net/v1.0`） |
| 商品取得 | 楽天市場 API（`openapi.rakuten.co.jp`） |
| 実行環境 | GitHub Actions（3時間ごと） / ローカル（.envで実行） |

---

## ファイル構成と役割

```
.
├── config.py                  # 定数・環境変数の一元管理。load_dotenv()はここだけで呼ぶ
├── supabase_client.py         # Supabaseクライアントのシングルトン管理
├── gemini_client.py           # Gemini APIラッパー。generate_with_retry / generate_with_fallback
├── generate_product_select.py # 楽天APIで商品検索 → Supabase(products)に保存
├── generate_product_post.py   # 未投稿商品をスコアリングで選定 → Geminiで投稿文生成 → drafts保存
├── generate_casual_post.py    # カジュアル（日常）投稿をGeminiで生成 → drafts保存
├── post_core.py               # Threads APIへの投稿処理（create → publish の2ステップ）
├── post_product.py            # draftsから商品投稿を取り出してThreadsに投稿
├── post_casual.py             # draftsからカジュアル投稿を取り出してThreadsに投稿
├── review_draft.py            # 承認待ち投稿の確認・承認（ローカル実行用）
├── run.py                     # エントリポイント。casual(40%) / product(60%) をランダム選択して実行
└── .github/workflows/run.yml  # GitHub Actions定義（3時間ごとに run.py を実行）
```

---

## Supabaseのテーブル構成

```sql
-- 楽天から取得した商品マスタ
products (
    id, item_code TEXT UNIQUE, item_name, price, review_count,
    review_average, point_rate, affiliate_rate, shop_name,
    genre_id, item_url, created_at, keyword, image_url
)

-- 投稿済み商品の記録（30日間の重複投稿防止）
posted_products (
    item_code TEXT PRIMARY KEY, posted_at TIMESTAMP
)

-- 生成済み下書き
drafts (
    id, item_code TEXT UNIQUE, main_post, reply_post, item_url,
    status TEXT DEFAULT 'pending',   -- pending / posting_reply / posted / failed_main / failed_reply
    created_at, post_type TEXT,      -- 'product' or 'casual'
    image_url, topic
)

-- カジュアル投稿の履歴（テーマ重複防止）
casual_posted (
    id, topic, post_text, posted_at TIMESTAMP
)
```

---

## 環境変数

GitHub ActionsではSecretsに格納。ローカルでは `.env` ファイルで管理（`config.py`でload_dotenv()を呼んでいるため自動読み込み）。

```env
RAKUTEN_APP_ID=
RAKUTEN_ACCESS_KEY=
GEMINI_API_KEY=
THREADS_USER_ID=
THREADS_ACCESS_TOKEN=
SUPABASE_URL=
SUPABASE_KEY=
```

---

## Geminiモデルの設定

`config.py` の定数で管理している。

```python
GEMINI_PRIMARY_MODEL = "gemini-2.5-flash-lite"   # コスト優先（1st）
GEMINI_FALLBACK_MODEL = "gemini-2.5-flash"        # 高品質（フォールバック）
```

フォールバックの流れ：`gemini_client.py` の `generate_with_fallback()` が担当。
プライマリ失敗 → フォールバックへ自動切替 → 両方失敗 → Exception送出。

---

## 投稿設計の方針（SNSマーケティング観点）

### 投稿タイプの比率
- `casual`（日常・共感投稿）: **70%**
- `product`（商品アフィリエイト投稿）: **30%**
- ※アフィリ投稿の連投はアルゴリズムから「広告アカウント」認定されるリスクがある。ガイドラインに基づきproductを30%以下に抑えている。

### Threadsアルゴリズムの優先シグナル
1. コメント・返信数（最重要）
2. 保存数
3. リポスト・引用
4. いいね数

### 投稿プロンプトの方針
- 商品スペック羅列は禁止。「使った後の変化・体験談」で語る
- 冒頭1行でスクロールを止めるフックを入れる
- 末尾にコメントを誘発する問いかけを必ず入れる
- 絵文字は1投稿3〜5個まで
- 文末に `#PR（楽天アフィリエイトリンクを含みます）`

---

## リファクタリング済みの主な変更点

（元のコードから以下を修正・改善済み）

1. **`generate_casual_post.py` の f-string バグ修正**
   - `prompt = """..."""` に f-string prefix がなく `used_topics` が展開されていなかった → `f"""..."""` に修正

2. **`generate_with_retry` の重複を解消**
   - `generate_product_post.py` と `generate_casual_post.py` に同一関数が存在 → `gemini_client.py` に集約

3. **`run.py` のsubprocessアンチパターンを解消**
   - `subprocess.run(["python", "xxx.py"])` → 各モジュールをimportして関数呼び出しに変更

4. **`load_dotenv()` の未実行を修正**
   - importはされていたが呼ばれていなかった → `config.py` で1回だけ呼ぶ

5. **`review_draft.py` をSQLite → Supabaseに統一**
   - 他のファイルはSupabaseなのにこのファイルだけSQLiteを使っていた

6. **エラーハンドリングの統一**
   - `exit()` と `raise Exception()` が混在 → `raise Exception()` に統一

7. **`get_category()` の判定漏れを修正**
   - `クレンジング`・`ダイエット`・`サプリメント` が「その他」に分類されていた → 適切なカテゴリに追加

8. **`generate_product_select.py` の upsert に `on_conflict="item_code"` を追加**
   - 指定がないと主キー（id）で重複判定してしまいUniqueConstraintエラーが出ていた

---

## 既知の課題・今後やりたいこと（改善案メモより）

- [ ] 投稿後N時間で閲覧数が一定以下なら自動削除する仕組み
- [ ] AIでトレンドをリサーチしてKEYWORDS（検索キーワード）を自動更新する
- [ ] 画像投稿の対応（現在は `image_url = None` で無効化中）
- [ ] セール期間（楽天スーパーセール・マラソン）の自動検知と投稿戦略の切り替え

---

## よく使うコマンド

```powershell
# ローカル実行
python run.py

# 投稿タイプを固定してテスト（run.py内のコメントを外す）
# post_type = "casual"

# 承認待ち投稿の確認（ローカルのみ）
python review_draft.py
```
