import os
import sqlite3
from dotenv import load_dotenv
from post_core import create_post
from supabase_client import supabase

load_dotenv()

USER_ID = os.getenv("THREADS_USER_ID")
TOKEN = os.getenv("THREADS_ACCESS_TOKEN")


result = (
    supabase.table("drafts")
    .select("*")
    .eq("status", "pending")
    .eq("post_type", "casual")
    .limit(1)
    .execute()
)

if not result.data:
    print("投稿対象なし")
    exit()

draft = result.data[0]

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
    supabase.table("drafts").update(
        {"status": "failed_main"}
    ).eq("id", draft["id"]).execute()
    print("投稿失敗")
    exit()

supabase.table("drafts").update(
    {"status": "posted"}
).eq("id", draft["id"]).execute()

print("雑談投稿完了")
