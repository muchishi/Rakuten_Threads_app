# ARCHITECTURE_MAP.md

## ファイル役割一覧

### エントリポイント

| ファイル | 役割 |
|----------|------|
| `run.py` | メインエントリ。casual(70%) / product(30%) をランダム選択して生成→投稿を実行 |

### 設定・共通

| ファイル | 役割 |
|----------|------|
| `config.py` | 環境変数・定数の一元管理。`load_dotenv()` はここだけで呼ぶ。`keywords.json` が存在すればそこから `KEYWORDS` を読み込む |
| `supabase_client.py` | Supabase クライアントのシングルトン管理 |
| `gemini_client.py` | Gemini API ラッパー。`generate_with_retry` / `generate_with_fallback`。`system_instruction` 対応 |

### 生成フェーズ

| ファイル | 役割 |
|----------|------|
| `generate_product_select.py` | 楽天 API で商品検索 → `products` テーブルに upsert |
| `generate_product_post.py` | 未投稿商品をスコアリングで選定 → 投稿タイプ判定 → Gemini で文章生成 → `drafts` に保存 |
| `generate_casual_post.py` | カジュアル投稿を Gemini で生成（JSON レスポンス） → `drafts` に保存 |

### 投稿フェーズ

| ファイル | 役割 |
|----------|------|
| `post_core.py` | Threads API への投稿処理（create → publish の2ステップ）。`media_id` を返す |
| `post_product.py` | `drafts` から商品投稿を取り出して Threads に投稿 → `posts` テーブルに記録 |
| `post_casual.py` | `drafts` からカジュアル投稿を取り出して Threads に投稿 → `posts` テーブルに記録 |

### 分析・メンテナンス

| ファイル | 役割 |
|----------|------|
| `collect_insights.py` | `posts` テーブルの24〜30日前の投稿について Threads Insights API からインプレッション等を取得 → `post_insights` に保存。`run.yml` から毎回実行 |
| `update_keywords.py` | `keywords.json` を週次で更新。低パフォーマンスキーワード3件除外 + 楽天売れ筋・Gemini リサーチで3件追加 |

### スキーマ・設定

| ファイル | 役割 |
|----------|------|
| `database.py` | Supabase スキーマ定義。実行すると Supabase SQL Editor に貼り付ける SQL を出力 |
| `keywords.json` | `KEYWORDS` リストの実体。`update_keywords.py` が自動上書き。直接編集しても動作する |
| `.github/workflows/run.yml` | 3時間ごとに `run.py` → `collect_insights.py` を実行 |
| `.github/workflows/update_keywords.yml` | 毎週月曜10時に `update_keywords.py` を実行し `keywords.json` をコミット |

---

## Supabase テーブル構成（v2）

```sql
-- 楽天商品マスタ
products (
    id BIGSERIAL PRIMARY KEY,
    item_code TEXT UNIQUE NOT NULL,
    item_name TEXT,
    price INTEGER,
    review_count INTEGER,
    review_average REAL,
    point_rate INTEGER,
    affiliate_rate REAL,
    shop_name TEXT,
    genre_id TEXT,
    item_url TEXT,
    image_url TEXT,           -- 現在は NULL（将来対応）
    keyword TEXT,             -- 検索に使ったキーワード
    created_at TIMESTAMPTZ
)

-- 生成済み下書き
drafts (
    id BIGSERIAL PRIMARY KEY,
    post_type TEXT,           -- 'product' | 'casual'
    status TEXT,              -- 'pending' | 'posting_reply' | 'posted' | 'failed_main' | 'failed_reply'
    item_code TEXT UNIQUE,    -- product のみ（casual は NULL）。UNIQUE は NULL を除外するため casual 複数行可
    main_post TEXT,
    reply_post TEXT,          -- product のみ（楽天リンクを含む）
    image_url TEXT,
    topic TEXT,               -- casual のみ（テーマ名）
    created_at TIMESTAMPTZ
)

-- 投稿済み記録（旧 posted_products + casual_posted を統合）
posts (
    id BIGSERIAL PRIMARY KEY,
    draft_id BIGINT,          -- drafts.id への FK
    post_type TEXT,           -- 'product' | 'casual'
    media_id TEXT,            -- Threads メイン投稿 ID（Insights API に使用）
    reply_media_id TEXT,      -- Threads リプライ投稿 ID（product のみ）
    item_code TEXT,           -- product のみ
    topic TEXT,               -- casual のみ（重複防止用）
    posted_at TIMESTAMPTZ
)

-- インプレッション記録（Threads Insights API の取得結果）
post_insights (
    id BIGSERIAL PRIMARY KEY,
    post_id BIGINT,           -- posts.id への FK（CASCADE DELETE）
    media_id TEXT,
    views INTEGER,
    likes INTEGER,
    replies_count INTEGER,
    reposts INTEGER,
    quotes INTEGER,
    fetched_at TIMESTAMPTZ
)
```

### テーブル間の関係

```
products ──< drafts (item_code FK)
drafts   ──< posts  (draft_id FK)
products ──< posts  (item_code FK)
posts    ──< post_insights (post_id FK, CASCADE)
```

---

## 環境変数一覧

| 変数名 | 用途 | 設定場所 |
|--------|------|----------|
| `RAKUTEN_APP_ID` | 楽天 API アプリケーション ID | GitHub Secrets / .env |
| `RAKUTEN_ACCESS_KEY` | 楽天 API アクセスキー | GitHub Secrets / .env |
| `RAKUTEN_AFFILIATE_ID` | 楽天アフィリエイト ID（アフィリエイト URL 生成に使用） | GitHub Secrets / .env |
| `GEMINI_API_KEY` | Google Gemini API キー | GitHub Secrets / .env |
| `THREADS_USER_ID` | Threads ユーザー ID | GitHub Secrets / .env |
| `THREADS_ACCESS_TOKEN` | Threads アクセストークン | GitHub Secrets / .env |
| `SUPABASE_URL` | Supabase プロジェクト URL | GitHub Secrets / .env |
| `SUPABASE_KEY` | Supabase anon key | GitHub Secrets / .env |

---

## Gemini モデル設定

```python
GEMINI_PRIMARY_MODEL  = "gemini-2.5-flash-lite"   # コスト優先（1st）
GEMINI_FALLBACK_MODEL = "gemini-2.5-flash"          # 高品質（フォールバック）
```

フォールバックの流れ：プライマリ失敗（6回リトライ）→ フォールバックへ自動切替（10回リトライ）→ 両方失敗 → Exception 送出。

商品投稿生成時のみ `system_instruction=GEMINI_SYSTEM_PROMPT` を渡す。カジュアル投稿はシステムプロンプトなし。
