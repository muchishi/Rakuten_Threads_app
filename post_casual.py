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
SELECT id, main_post
FROM drafts
WHERE status ='pending' or status='approved'
ORDER BY id ASC
LIMIT 1
""")

draft = cursor.fetchone()

if not draft:
    print("雑談なし")
    exit()

draft_id, main_post = draft

print("投稿対象")
print(main_post)

# -------------------
# 投稿のみ
# -------------------
res = create_post(USER_ID, TOKEN, main_post)

if not res:
    cursor.execute("UPDATE drafts SET status='failed_main' WHERE id=?", (draft_id,))
    conn.commit()
    conn.close()
    exit()

cursor.execute("UPDATE drafts SET status='posted' WHERE id=?", (draft_id,))
conn.commit()
conn.close()

print("雑談投稿完了")
