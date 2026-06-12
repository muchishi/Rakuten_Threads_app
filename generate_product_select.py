import os
import requests
from dotenv import load_dotenv
import time
from bs4 import BeautifulSoup
from supabase_client import supabase

# 環境変数をロード
load_dotenv()

# 環境変数から楽天APIの認証情報を取得
APP_ID = os.getenv("RAKUTEN_APP_ID")
ACCESS_KEY = os.getenv("RAKUTEN_ACCESS_KEY")

# 楽天APIのエンドポイントURL
url = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"

# 検索キーワードのリスト
KEYWORDS = [
    "フェイスマスク",
    "香水",
    # "充電器",
    "日焼け止め",
    "化粧水",
    # "プロテイン",
    "トリートメント",
    "シャンプー",
    # "美容液",
    "化粧下地",
    "美容グッズ",
    "ヘアオイル",
    "ハンドクリーム",
    "ボディクリーム",
    "マッサージクリーム",
    "クレンジング",
    "ダイエット",
    "サプリメント",
]

def get_og_image(url, timeout=6):
    # try:
    #     headers = {
    #         "User-Agent": "Mozilla/5.0",
    #         "Accept-Language": "ja-JP,ja;q=0.9",
    #         "Cache-Control": "no-cache",
    #     }

    #     res = requests.get(url, headers=headers, timeout=timeout)
    #     res.raise_for_status()

    #     soup = BeautifulSoup(res.text, "html.parser")

    #     # OG優先
    #     og = soup.find("meta", property="og:image")
    #     if og and og.get("content"):
    #         return og["content"]

    #     # Twitterカードも拾う（重要）
    #     tw = soup.find("meta", attrs={"name": "twitter:image"})
    #     if tw and tw.get("content"):
    #         return tw["content"]

    #     print("⚠️ OG画像なし")
    #     return None

    # except Exception as e:
    #     print(f"⚠️ OG取得失敗: {e}")
        return None


for keyword in KEYWORDS:

    print(f"検索中: {keyword}")
    # APIリクエストのパラメータを設定
    params = {
        "applicationId": APP_ID,
        "accessKey": ACCESS_KEY,
        "keyword": keyword,
        "hits": 1,
        "format": "json",
    }
    # APIリクエストを送信してデータを取得
    response = requests.get(url, params=params)

    # APIのレートリミットを考慮して、リクエスト間に少し待機
    time.sleep(1.2)

    print(response.status_code)
    # print(response.text[:1000])

    # レスポンスからJSONデータを抽出
    data = response.json()

    # APIレスポンスに商品データが含まれているか確認
    if "Items" not in data:
        print(f"取得失敗: {keyword}")
        print(data)
        continue

    # データベースに商品データを保存
    for row in data["Items"]:
        item = row["Item"]

        # -----------------------
        # 画像URL取得
        # -----------------------
        image_url = None
        item_url = item["itemUrl"]
        # print(f"商品URL: {item_url}")
        result = get_og_image(item_url)
        if result:
            print(f"OG画像取得成功: {result}")
            image_url = result
        elif result is None:
            print("OG画像取得失敗 → APIの画像URLを使用")
            print(result)

        review_average = item.get("itemAverageRating") or item.get("reviewAverage") or 0

        supabase.table("products").upsert(
            {
                "item_code": item["itemCode"],
                "item_name": item["itemName"],
                "price": item["itemPrice"],
                "review_count": item["reviewCount"],
                "review_average": review_average,
                "point_rate": item["pointRate"],
                "affiliate_rate": item["affiliateRate"],
                "shop_name": item["shopName"],
                "genre_id": item["genreId"],
                "keyword": keyword,
                "item_url": item["itemUrl"],
                "image_url": image_url,
            }
        ).execute()

# 保存完了のメッセージを表示
print("保存完了")
