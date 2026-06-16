# generate_product_post.py
"""
未投稿商品をスコアリングで選定し、Geminiで投稿文を生成してdraftsに保存する
"""
from datetime import datetime, timezone, timedelta
from supabase_client import get_supabase
from gemini_client import generate_with_fallback
from config import CATEGORY_RULES, SCORE_WEIGHTS, CATEGORY_TARGET_MAP, GEMINI_SYSTEM_PROMPT


def get_category(keyword: str) -> str:
    """キーワードからカテゴリ名を返す"""
    kw = keyword.lower()
    for keywords_list, category_name in CATEGORY_RULES:
        if any(k in kw for k in keywords_list):
            return category_name
    return "その他"


def determine_post_type(item: dict) -> str:
    """商品情報から最適な投稿タイプを判定する"""
    review_count = int(item.get("review_count") or 0)
    if review_count > 500:
        return "ランキング型"

    keyword = (item.get("keyword") or "").lower()
    daily_keywords = ["日用品", "キッチン", "掃除", "洗剤", "生活雑貨"]
    if any(k in keyword for k in daily_keywords):
        return "保存型"

    return "共感型"


def calc_score(item: dict) -> float:
    """商品のスコアを計算する（高いほど優先して投稿）"""
    w = SCORE_WEIGHTS
    return (
        item["review_count"] * w["review_count"]
        + item["review_average"] * w["review_average"]
        + item["point_rate"] * w["point_rate"]
        + item["affiliate_rate"] * w["affiliate_rate"]
    )


def build_main_prompt(item: dict, category: str, post_type: str) -> str:
    target = CATEGORY_TARGET_MAP.get(category, "楽天でお得に買い物したい人")
    return f"""
【商品情報】
商品名: {item["item_name"]}
価格: {item["price"]}円
レビュー評価: {item["review_average"]}（{item["review_count"]}件）
カテゴリ: {category}

【投稿タイプ】
{post_type}

【ターゲット】
{target}

【リンク誘導について】
リンクはリプ欄に掲載するため、本文中では「↓リプ欄のリンクから」や「詳しくはリプ欄に！」と誘導してください。

【文字数制限】
本文は500文字以内（#PR表記を含む）に収めること。

上記の情報をもとに、Threads投稿の本文のみを出力してください。
セクションラベルや余分な説明文は不要です。
""".strip()


def generate_product_draft() -> None:
    supabase = get_supabase()

    # 30日以内に投稿済みのitem_codeを取得
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    posted_codes = {
        row["item_code"]
        for row in supabase.table("posts")
        .select("item_code")
        .eq("post_type", "product")
        .gte("posted_at", cutoff)
        .not_.is_("item_code", "null")
        .execute()
        .data
    }

    # 未投稿商品を取得
    all_products = supabase.table("products").select("*").execute().data
    candidates = [p for p in all_products if p["item_code"] not in posted_codes]

    if not candidates:
        raise Exception("未投稿商品がありません")

    # スコア最大の商品を選定
    item = max(candidates, key=calc_score)
    category = get_category(item["keyword"])
    post_type = determine_post_type(item)

    print(f"選定商品: {item['item_name']} (カテゴリ: {category}, 投稿タイプ: {post_type})")

    # 投稿文生成（ガイドライン準拠のシステムプロンプトを使用）
    main_text = generate_with_fallback(
        build_main_prompt(item, category, post_type),
        system_instruction=GEMINI_SYSTEM_PROMPT,
    )
    reply_text = f"楽天のリンクはこちら（PR）\n\n{item['item_url']}"

    print("===== メイン投稿 =====")
    print(main_text)
    print("===== リプ投稿 =====")
    print(reply_text)

    # draftsに保存（item_url は reply_post テキストに埋め込み済みのため除外）
    supabase.table("drafts").upsert(
        {
            "item_code": item["item_code"],
            "main_post": main_text,
            "reply_post": reply_text,
            "image_url": item.get("image_url"),
            "status": "pending",
            "post_type": "product",
        },
        on_conflict="item_code",
    ).execute()

    print("✅ draft保存完了")


if __name__ == "__main__":
    generate_product_draft()
