import sqlite3

conn = sqlite3.connect("rakuten.db")

cursor = conn.cursor()

# テーブル作成
cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_code TEXT UNIQUE,
    item_name TEXT,
    price INTEGER,
    review_count INTEGER,
    review_average REAL,
    point_rate INTEGER,
    affiliate_rate REAL,
    shop_name TEXT,
    genre_id INTEGER,
    item_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    keyword TEXT,
    image_url TEXT
)
""")

# 投稿済み商品を記録するテーブル
cursor.execute("""
CREATE TABLE IF NOT EXISTS posted_products (
    item_code TEXT PRIMARY KEY, 
    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
)
""")

# 下書きテーブル
cursor.execute("""
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_code TEXT UNIQUE,
    main_post TEXT,
    reply_post TEXT,
    item_url TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    post_type TEXT DEFAULT 'product',
    image_url TEXT
)
""")

conn.commit()
conn.close()

print("DB作成完了")
