# generate_product_select.py
"""
楽天APIから商品を検索してSupabaseに保存する
"""
import random
import time
from urllib.parse import quote
import requests
from supabase_client import get_supabase
from config import RAKUTEN_APP_ID, RAKUTEN_ACCESS_KEY, RAKUTEN_AFFILIATE_ID, RAKUTEN_API_URL, KEYWORDS


def make_affiliate_url(item_url: str) -> str:
    """itemUrl から楽天アフィリエイト URL を生成する"""
    parts = RAKUTEN_AFFILIATE_ID.split(".")
    base = f"{parts[0]}.{parts[1]}"
    return f"https://hb.afl.rakuten.co.jp/hgc/{base}/?pc={quote(item_url, safe='')}"

# 1回のrunあたり取得するキーワード数の上限
# 全キーワードを毎回取得すると楽天APIのレートリミット(403)を引き起こすため
KEYWORDS_PER_RUN = 3


def fetch_and_upsert_products() -> None:
    supabase = get_supabase()

    # DBに商品がないキーワードを優先し、残りはランダム補完
    existing_keywords = {
        row["keyword"]
        for row in supabase.table("products").select("keyword").execute().data
        if row.get("keyword")
    }
    no_data = [kw for kw in KEYWORDS if kw not in existing_keywords]
    has_data = [kw for kw in KEYWORDS if kw in existing_keywords]

    target = no_data[:KEYWORDS_PER_RUN]
    if len(target) < KEYWORDS_PER_RUN:
        random.shuffle(has_data)
        target += has_data[: KEYWORDS_PER_RUN - len(target)]

    print(f"検索対象 ({len(target)}/{len(KEYWORDS)}件): {target}")

    for keyword in target:
        print(f"検索中: {keyword}")

        params = {
            "applicationId": RAKUTEN_APP_ID,
            "accessKey": RAKUTEN_ACCESS_KEY,
            "keyword": keyword,
            "hits": 3,
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
                    "item_url": make_affiliate_url(item["itemUrl"]),
                    "image_url": None,  # OG画像取得は将来対応
                },
                on_conflict="item_code"
            ).execute()

    print("✅ 商品保存完了")


if __name__ == "__main__":
    fetch_and_upsert_products()
