import os
import time
from dotenv import load_dotenv
from google import genai
from supabase_client import get_supabase

supabase = get_supabase()



client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

posted = (
    supabase.table("posted_products")
    .select("item_code")
    .execute()
)

posted_codes = {
    row["item_code"]
    for row in posted.data
}

products = (
    supabase.table("products")
    .select("*")
    .execute()
)

candidates = [
    p
    for p in products.data
    if p["item_code"] not in posted_codes
]

def calc_score(item):
    return (
        item["review_count"] * 0.3
        + item["review_average"] * 100
        + item["point_rate"] * 50
        + item["affiliate_rate"] * 100
    )

if not candidates:
    raise Exception("未投稿商品がありません")

item = max(
    candidates,
    key=calc_score
)

item_code = item["item_code"]
item_name = item["item_name"]
price = item["price"]
review_count = item["review_count"]
review_average = item["review_average"]
point_rate = item["point_rate"]
affiliate_rate = item["affiliate_rate"]
keyword = item["keyword"]
item_url = item["item_url"]
shop_name = item["shop_name"]
image_url = item["image_url"]


def get_category(keyword):

    keyword = keyword.lower()

    # -------------------
    # 美容・コスメ（最優先）
    # -------------------
    if any(
        k in keyword
        for k in [
            "化粧",
            "コスメ",
            "美容",
            "スキンケア",
            "日焼け止め",
            "美容液",
            "化粧水",
            "乳液",
            "クリーム",
            "フェイス",
            "パック",
            "香水",
            "フレグランス",
            "ヘア",
            "シャンプー",
            "トリートメント",
            "オイル",
            "ミスト",
            "ボディ",
        ]
    ):
        return "美容・コスメ"

    # -------------------
    # 食品・飲料
    # -------------------
    elif any(
        k in keyword
        for k in [
            "天然水",
            "米",
            "コーヒー",
            "お茶",
            "紅茶",
            "プロテイン",
        ]
    ):
        return "食品・飲料"

    return "その他"


category = get_category(keyword)

main_prompt = f"""
あなたは楽天お得情報を発信する人気Threadsアカウント運営者です。

商品情報
商品名: {item_name}
価格: {price}円
レビュー件数: {review_count}
レビュー評価: {review_average}
ショップ名: {shop_name}
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
・食品・飲料 → 味・満足感
・日用品 → 便利さ・時短
・コスメの場合以下の切り口を必ず入れる（どれか1つでOK）
    ① 変化（Before/Afterの匂わせ）
    ② 他人評価（褒められた・気づかれた）
    ③ 友達に聞かれる系（商品名 or 使用感）
・寝具・インテリア → 快適さ・リラックス

自然な日常投稿として1つだけ出力してください。
"""

reply_text = f"""楽天のリンクはこちら（PR）\n\n{item_url}"""


def generate_with_retry(prompt, model, retry=6, sleep_sec=7):
    for i in range(retry):
        try:
            res = client.models.generate_content(model=model, contents=prompt)
            return res.text

        except Exception as e:
            print(f"[{model}] retry {i+1}/{retry} \nfailed: {e}\n\nf")

            if i < retry - 1:
                time.sleep(sleep_sec)

    return None


# -----------------------
# 1st model
# -----------------------
main_text = generate_with_retry(main_prompt, "gemini-3.1-flash-lite")
# reply_text = generate_with_retry(reply_prompt, "gemini-3.5-flash")

# -----------------------
# fallback model
# -----------------------
if not main_text or not reply_text:
    print("3.5-flash失敗 → 2.5-flashへ切替")

    main_text = main_text or generate_with_retry(main_prompt, "gemini-2.5-flash",10,10)
    # reply_text = reply_text or generate_with_retry(reply_prompt, "gemini-2.5-flash",10,10)

# -----------------------
# 最終チェック
# -----------------------
if not main_text or not reply_text:
    raise Exception("両モデルとも生成失敗")

print("メイン投稿生成成功")
print("リプ投稿生成成功")


print("===== メイン投稿 =====")
print(main_text)

print("===== リプ投稿 =====")
print(reply_text)

supabase.table("drafts").upsert(
    {
        "item_code": item_code,
        "main_post": main_text,
        "reply_post": reply_text,
        "item_url": item_url,
        "image_url": image_url,
        "status": "pending",
        "post_type": "product",
    }
).execute()

print("draft保存完了")

print("\n===== URL =====")
print(item_url)
