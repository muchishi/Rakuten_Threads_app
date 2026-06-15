# database.py
"""
Supabase スキーマ定義

実行すると、Supabase SQL エディターに貼り付けるべき SQL が出力されます。
https://supabase.com/dashboard → SQL Editor で実行してください。

スキーマ変更履歴:
  v1: 初期スキーマ（products / posted_products / drafts / casual_posted）
  v2: posts テーブルへ統合・post_insights 追加・drafts 正規化
"""

# ── v2 新規インストール用 SQL ─────────────────────────────────────────────────

FRESH_SQL = """
-- =====================================================
-- Fresh Install (初回セットアップ用)
-- =====================================================

-- 1. 楽天商品マスタ
CREATE TABLE IF NOT EXISTS products (
    id           BIGSERIAL PRIMARY KEY,
    item_code    TEXT UNIQUE NOT NULL,
    item_name    TEXT NOT NULL,
    price        INTEGER NOT NULL DEFAULT 0,
    review_count INTEGER NOT NULL DEFAULT 0,
    review_average REAL NOT NULL DEFAULT 0,
    point_rate   INTEGER NOT NULL DEFAULT 0,
    affiliate_rate REAL NOT NULL DEFAULT 0,
    shop_name    TEXT,
    genre_id     TEXT,
    item_url     TEXT NOT NULL DEFAULT '',
    image_url    TEXT,
    keyword      TEXT NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. 生成済み下書き
--    item_url は reply_post テキストに埋め込み済みのため除外
--    item_code は product 投稿のみ。casual は NULL 許容（UNIQUE は NULL を除外するため複数行可）
CREATE TABLE IF NOT EXISTS drafts (
    id        BIGSERIAL PRIMARY KEY,
    post_type TEXT NOT NULL CHECK (post_type IN ('product', 'casual')),
    status    TEXT NOT NULL DEFAULT 'pending'
              CHECK (status IN ('pending', 'posting_reply', 'posted', 'failed_main', 'failed_reply')),
    item_code TEXT UNIQUE REFERENCES products(item_code) ON DELETE SET NULL,
    main_post TEXT NOT NULL,
    reply_post TEXT,
    image_url TEXT,
    topic     TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. 投稿済み記録（posted_products + casual_posted を統合）
--    media_id: Threads メイン投稿 ID（Insights API に使用）
--    reply_media_id: リプライ投稿 ID（product 投稿のみ）
CREATE TABLE IF NOT EXISTS posts (
    id             BIGSERIAL PRIMARY KEY,
    draft_id       BIGINT REFERENCES drafts(id) ON DELETE SET NULL,
    post_type      TEXT NOT NULL CHECK (post_type IN ('product', 'casual')),
    media_id       TEXT NOT NULL,
    reply_media_id TEXT,
    item_code      TEXT REFERENCES products(item_code) ON DELETE SET NULL,
    topic          TEXT,
    posted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS posts_item_code_idx  ON posts(item_code);
CREATE INDEX IF NOT EXISTS posts_posted_at_idx  ON posts(posted_at);
CREATE INDEX IF NOT EXISTS posts_post_type_idx  ON posts(post_type);

-- 4. インプレッション記録（Threads Insights API の取得結果）
CREATE TABLE IF NOT EXISTS post_insights (
    id            BIGSERIAL PRIMARY KEY,
    post_id       BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    media_id      TEXT NOT NULL,
    views         INTEGER,
    likes         INTEGER,
    replies_count INTEGER,
    reposts       INTEGER,
    quotes        INTEGER,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS post_insights_post_id_idx    ON post_insights(post_id);
CREATE INDEX IF NOT EXISTS post_insights_fetched_at_idx ON post_insights(fetched_at);
"""

# ── v1 → v2 マイグレーション用 SQL ───────────────────────────────────────────

MIGRATION_SQL = """
-- =====================================================
-- Migration: v1 → v2（既存データがある場合）
-- =====================================================

-- Step 1: drafts から item_url を削除（reply_post に埋め込み済みのため）
ALTER TABLE drafts DROP COLUMN IF EXISTS item_url;

-- Step 2: drafts に CHECK 制約を追加
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'drafts_post_type_check') THEN
        ALTER TABLE drafts ADD CONSTRAINT drafts_post_type_check
            CHECK (post_type IN ('product', 'casual'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'drafts_status_check') THEN
        ALTER TABLE drafts ADD CONSTRAINT drafts_status_check
            CHECK (status IN ('pending', 'posting_reply', 'posted', 'failed_main', 'failed_reply'));
    END IF;
END $$;

-- Step 3: posts テーブルを作成
CREATE TABLE IF NOT EXISTS posts (
    id             BIGSERIAL PRIMARY KEY,
    draft_id       BIGINT REFERENCES drafts(id) ON DELETE SET NULL,
    post_type      TEXT NOT NULL CHECK (post_type IN ('product', 'casual')),
    media_id       TEXT NOT NULL,
    reply_media_id TEXT,
    item_code      TEXT REFERENCES products(item_code) ON DELETE SET NULL,
    topic          TEXT,
    posted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS posts_item_code_idx  ON posts(item_code);
CREATE INDEX IF NOT EXISTS posts_posted_at_idx  ON posts(posted_at);
CREATE INDEX IF NOT EXISTS posts_post_type_idx  ON posts(post_type);

-- Step 4: posted_products のデータを posts に移行
--         移行前の media_id は不明なため 'migrated_' プレフィックスで区別
INSERT INTO posts (post_type, media_id, item_code, posted_at)
SELECT
    'product',
    'migrated_' || item_code,
    item_code,
    posted_at
FROM posted_products
ON CONFLICT DO NOTHING;

-- Step 5: casual_posted のデータを posts に移行
INSERT INTO posts (post_type, media_id, topic, posted_at)
SELECT
    'casual',
    'migrated_casual_' || id::TEXT,
    topic,
    posted_at
FROM casual_posted
ON CONFLICT DO NOTHING;

-- Step 6: post_insights テーブルを作成
CREATE TABLE IF NOT EXISTS post_insights (
    id            BIGSERIAL PRIMARY KEY,
    post_id       BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    media_id      TEXT NOT NULL,
    views         INTEGER,
    likes         INTEGER,
    replies_count INTEGER,
    reposts       INTEGER,
    quotes        INTEGER,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS post_insights_post_id_idx    ON post_insights(post_id);
CREATE INDEX IF NOT EXISTS post_insights_fetched_at_idx ON post_insights(fetched_at);

-- Step 7: 旧テーブルを削除（データ移行が確認できたら実行）
-- DROP TABLE IF EXISTS posted_products;
-- DROP TABLE IF EXISTS casual_posted;
"""

if __name__ == "__main__":
    print("=" * 60)
    print("Supabase SQL Editor に貼り付けて実行してください")
    print("https://supabase.com/dashboard → SQL Editor")
    print("=" * 60)
    print()
    print("【初回セットアップ（テーブルが存在しない場合）】")
    print(FRESH_SQL)
    print()
    print("【既存テーブルを v2 にアップグレードする場合】")
    print(MIGRATION_SQL)
