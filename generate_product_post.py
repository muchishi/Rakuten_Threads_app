import os
import sqlite3
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

conn = sqlite3.connect("rakuten.db")
cursor = conn.cursor()

cursor.execute("""
SELECT
    item_code,
    item_name,
    price,
    review_count,
    review_average,
    point_rate,
    affiliate_rate,
    keyword,
    item_url,
    shop_name,
    item_url,
    image_url
FROM products
WHERE item_code NOT IN (
    SELECT item_code
    FROM posted_products
)
ORDER BY
(
    review_count * 0.3 +
    review_average * 100 +
    point_rate * 50 +
    affiliate_rate * 100
) DESC
LIMIT 1
""")

# 投稿済み商品を除外して、レビュー件数、評価、ポイント還元率、アフィリエイト率の総合スコアが高い順に1件取得
item = cursor.fetchone()

conn.close()

item_code = item[0]
item_name = item[1]
price = item[2]
review_count = item[3]
review_average = item[4]
point_rate = item[5]
affiliate_rate = item[6]
keyword = item[7]
item_url = item[8]
shop_name = item[9]
item_url = item[10]
image_url = item[11]


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

# reply_prompt = f"""
# あなたは楽天アフィリエイト投稿を管理しています。

# 以下の商品情報をもとに、Threadsのリプライ用文章を作成してください。

# 商品名: {item_name}
# 価格: {price}円

# 条件
# ・1〜2行
# ・必ず「楽天のリンクはこちら（PR）」を含める
# ・煽り禁止
# ・シンプルに導線だけ

# 出力例：
# 楽天のリンクはこちら（PR)

# """
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

conn = sqlite3.connect("rakuten.db")
cursor = conn.cursor()

cursor.execute(
    """
INSERT OR IGNORE INTO drafts (
    item_code,
    main_post,
    reply_post,
    item_url,
    image_url
)
VALUES (?, ?, ?, ?, ?)
""",
    (item_code, main_text, reply_text, item_url, image_url),
)

conn.commit()
conn.close()

print("draft保存完了")

print("\n===== URL =====")
print(item_url)
