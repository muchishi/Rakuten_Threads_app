import os
from dotenv import load_dotenv
from post_core import create_post
from supabase_client import get_supabase

supabase = get_supabase()

USER_ID = os.getenv("THREADS_USER_ID")
TOKEN = os.getenv("THREADS_ACCESS_TOKEN")

result = (
    supabase.table("drafts")
    .select("*")
    .eq("status", "pending")
    .eq("post_type", "product")
    .limit(1)
    .execute()
)

if not result.data:
    print("投稿対象なし")
    exit()

draft = result.data[0]
draft_id = draft["id"]
item_code = draft["item_code"]
main_post = draft["main_post"]
reply_post = draft["reply_post"]
item_url = draft["item_url"]
image_url = draft["image_url"]

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
    supabase.table("drafts").update(
        {"status": "failed_main"}
    ).eq("id", draft["id"]).execute()
    print("投稿失敗")
    exit()

# main_resからmedia_idを取得
media_id = main_res["media_id"]


supabase.table("drafts").update(
    {"status": "posting_reply"}
).eq("id", draft["id"]).execute()
print("メイン投稿成功 → リプ投稿へ")

# -------------------
# リプ投稿
# -------------------
reply_text = reply_post
reply_res = create_post(USER_ID, TOKEN, reply_text, reply_to_id=media_id)

if not reply_res:
    supabase.table("drafts").update(
        {"status": "failed_reply"}
    ).eq("id", draft["id"]).execute()
    print("リプ投稿失敗")
    exit()
    exit()

print("リプ投稿成功")
# -------------------
# 完了処理
# -------------------
supabase.table("drafts").update(
    {"status": "posted"}
).eq("id", draft["id"]).execute()

print("商品投稿完了")
