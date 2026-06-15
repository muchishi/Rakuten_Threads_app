# post_product.py
"""
draftsから商品投稿を取り出してThreadsに投稿する（メイン + リプライの2段階）
"""
from datetime import datetime, timezone
from supabase_client import get_supabase
from post_core import create_post


def post_product() -> None:
    supabase = get_supabase()

    # pending な商品投稿を1件取得
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
        return

    draft = result.data[0]
    draft_id = draft["id"]
    item_code = draft["item_code"]
    main_post = draft["main_post"]
    reply_post = draft["reply_post"]
    image_url = draft.get("image_url") or None  # "None"文字列と None を両方吸収

    print(f"投稿対象: {main_post}")

    # ── メイン投稿 ────────────────────────
    main_res = create_post(main_post, image_url=image_url)
    if not main_res:
        supabase.table("drafts").update({"status": "failed_main"}).eq("id", draft_id).execute()
        raise Exception("メイン投稿失敗")

    media_id = main_res["media_id"]
    supabase.table("drafts").update({"status": "posting_reply"}).eq("id", draft_id).execute()
    print("✅ メイン投稿成功 → リプ投稿へ")

    # ── リプライ投稿 ──────────────────────
    reply_res = create_post(reply_post, reply_to_id=media_id)
    if not reply_res:
        supabase.table("drafts").update({"status": "failed_reply"}).eq("id", draft_id).execute()
        raise Exception("リプ投稿失敗")

    print("✅ リプ投稿成功")

    # ── 完了処理 ──────────────────────────
    supabase.table("drafts").update({"status": "posted"}).eq("id", draft_id).execute()
    supabase.table("posted_products").upsert(
        {
            "item_code": item_code,
            "posted_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="item_code",
    ).execute()

    print("✅ 商品投稿完了")


if __name__ == "__main__":
    post_product()
