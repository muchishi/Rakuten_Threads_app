# generate_product_select.py
"""
楽天APIから商品を検索してSupabaseに保存する
"""
import time
import requests
from supabase_client import get_supabase
from config import RAKUTEN_APP_ID, RAKUTEN_ACCESS_KEY, RAKUTEN_API_URL, KEYWORDS


def fetch_and_upsert_products() -> None:
    supabase = get_supabase()

    for keyword in KEYWORDS:
        print(f"検索中: {keyword}")

        params = {
            "applicationId": RAKUTEN_APP_ID,
            "accessKey": RAKUTEN_ACCESS_KEY,
            "keyword": keyword,
            "hits": 1,
            "format": "json",
        }

        try:
            response = requests.get(RAKUTEN_API_URL, params=params, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"⚠️ APIリクエスト失敗 [{keyword}]: {e}")
            time.sleep(1.2)
            continue

        time.sleep(1.2)  # レートリミット対策

        data = response.json()

        if "Items" not in data:
            print(f"⚠️ 商品データなし [{keyword}]: {data}")
            continue

        for row in data["Items"]:
            item = row["Item"]

            review_average = (
                item.get("itemAverageRating")
                or item.get("reviewAverage")
                or 0.0
            )

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
                    "image_url": None,  # OG画像取得は将来対応
                },
                on_conflict="item_code"
            ).execute()

    print("✅ 商品保存完了")


if __name__ == "__main__":
    fetch_and_upsert_products()
