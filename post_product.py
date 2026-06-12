import os
import sqlite3
from dotenv import load_dotenv
from post_core import create_post

load_dotenv()

USER_ID = os.getenv("THREADS_USER_ID")
TOKEN = os.getenv("THREADS_ACCESS_TOKEN")

conn = sqlite3.connect("rakuten.db")
cursor = conn.cursor()

cursor.execute("""
SELECT
    id,
    item_code,
    main_post,
    reply_post,
    item_url,
    image_url
FROM drafts
WHERE status='pending' or status='approved'
ORDER BY id ASC
LIMIT 1
""")

draft = cursor.fetchone()

if not draft:
    print("投稿待ちデータなし")
    exit()

draft_id, item_code, main_post, reply_post, item_url, image_url = draft

print("投稿対象")
print(main_post)

# -------------------
# メイン投稿
# -------------------
print("image_url:" , image_url)
# image_urlがない、もしくは"None"の文字列の場合はNoneに変換してcreate_postに渡す
if not image_url or image_url == "None":
    image_url = None

# create_postの戻り値をmain_resとして受け取るように変更
main_res = create_post(USER_ID, TOKEN, main_post, image_url=image_url)
print("main_res:", main_res)

# main_resがNoneの場合は失敗として処理
if not main_res:
    cursor.execute("UPDATE drafts SET status='failed_main' WHERE id=?", (draft_id,))
    conn.commit()
    conn.close()
    exit()

# main_resからmedia_idを取得
media_id = main_res["media_id"]


cursor.execute("UPDATE drafts SET status='posting_reply' WHERE id=?", (draft_id,))
print("メイン投稿成功 → リプ投稿へ")
conn.commit()

# -------------------
# リプ投稿
# -------------------
reply_text = reply_post
reply_res = create_post(USER_ID, TOKEN, reply_text, reply_to_id=media_id)

if not reply_res:
    cursor.execute("UPDATE drafts SET status='failed_reply' WHERE id=?", (draft_id,))
    conn.commit()
    conn.close()
    exit()

print("リプ投稿成功")
# -------------------
# 完了処理
# -------------------
cursor.execute("UPDATE drafts SET status='posted' WHERE id=?", (draft_id,))
cursor.execute(
    """
INSERT OR IGNORE INTO posted_products (item_code)
VALUES (?)
""",
    (item_code,),
)

conn.commit()
conn.close()

print("商品投稿完了")
