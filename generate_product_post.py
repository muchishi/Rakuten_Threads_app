# generate_product_post.py
"""
未投稿商品をスコアリングで選定し、Geminiで投稿文を生成してdraftsに保存する
"""
from datetime import datetime, timezone, timedelta
from supabase_client import get_supabase
from gemini_client import generate_with_fallback
from config import CATEGORY_RULES, SCORE_WEIGHTS


def get_category(keyword: str) -> str:
    """キーワードからカテゴリ名を返す"""
    kw = keyword.lower()
    for keywords_list, category_name in CATEGORY_RULES:
        if any(k in kw for k in keywords_list):
            return category_name
    return "その他"


def calc_score(item: dict) -> float:
    """商品のスコアを計算する（高いほど優先して投稿）"""
    w = SCORE_WEIGHTS
    return (
        item["review_count"] * w["review_count"]
        + item["review_average"] * w["review_average"]
        + item["point_rate"] * w["point_rate"]
        + item["affiliate_rate"] * w["affiliate_rate"]
    )


def build_main_prompt(item: dict, category: str) -> str:
    return f"""
あなたは楽天お得情報を発信する人気Threadsアカウント運営者です。

商品情報
商品名: {item["item_name"]}
価格: {item["price"]}円
レビュー件数: {item["review_count"]}
レビュー評価: {item["review_average"]}
ショップ名: {item["shop_name"]}
商品カテゴリ: {category}

以下の条件でThreads投稿文を作成してください。

条件
・120文字以内
・広告感を完全に消し、雑談・体験ベース
・「使ってみた感想」「変化」「周りの反応」を中心にする
・購買を促す表現は禁止
・URL禁止
・PR表記禁止
・絵文字は最大2〜3個
・改行多めで読みやすく

カテゴリ別ルール
・健康・ダイエット → 体の変化・継続できている実感
・食品・飲料 → 味・満足感
・日用品 → 便利さ・時短
・美容・コスメ → 以下のいずれか1つ
    ① 変化（Before/Afterの匂わせ）
    ② 他人評価（褒められた・気づかれた）
    ③ 友達に聞かれる系（商品名 or 使用感）
・寝具・インテリア → 快適さ・リラックス

自然な日常投稿として1つだけ出力してください。
""".strip()


def generate_product_draft() -> None:
    supabase = get_supabase()

    # 30日以内に投稿済みのitem_codeを取得
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    posted_codes = {
        row["item_code"]
        for row in supabase.table("posted_products")
        .select("item_code")
        .gte("posted_at", cutoff)
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

    print(f"選定商品: {item['item_name']} (カテゴリ: {category})")

    # 投稿文生成
    main_text = generate_with_fallback(build_main_prompt(item, category))
    reply_text = f"楽天のリンクはこちら（PR）\n\n{item['item_url']}"

    print("===== メイン投稿 =====")
    print(main_text)
    print("===== リプ投稿 =====")
    print(reply_text)

    # draftsに保存
    supabase.table("drafts").upsert(
        {
            "item_code": item["item_code"],
            "main_post": main_text,
            "reply_post": reply_text,
            "item_url": item["item_url"],
            "image_url": item.get("image_url"),
            "status": "pending",
            "post_type": "product",
        },
        on_conflict="item_code",
    ).execute()

    print("✅ draft保存完了")


if __name__ == "__main__":
    generate_product_draft()
