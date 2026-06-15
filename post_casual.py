# post_casual.py
"""
draftsからカジュアル投稿を取り出してThreadsに投稿する
"""
from supabase_client import get_supabase
from post_core import create_post


def post_casual() -> None:
    supabase = get_supabase()

    result = (
        supabase.table("drafts")
        .select("*")
        .eq("status", "pending")
        .eq("post_type", "casual")
        .limit(1)
        .execute()
    )

    if not result.data:
        print("カジュアル投稿の対象なし")
        return

    draft = result.data[0]
    draft_id = draft["id"]
    main_post = draft["main_post"]
    topic = draft.get("topic")

    print(f"投稿対象: {main_post}")

    res = create_post(main_post)
    if not res:
        supabase.table("drafts").update({"status": "failed_main"}).eq("id", draft_id).execute()
        raise Exception("カジュアル投稿失敗")

    supabase.table("drafts").update({"status": "posted"}).eq("id", draft_id).execute()
    supabase.table("casual_posted").insert(
        {"topic": topic, "post_text": main_post}
    ).execute()

    print("✅ カジュアル投稿完了")


if __name__ == "__main__":
    post_casual()
