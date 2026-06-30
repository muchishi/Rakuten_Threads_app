# collect_insights.py
"""
posts テーブルの投稿について Threads Insights API からインプレッション等を取得し
post_insights テーブルに保存する

対象条件:
  - posted_at が 24 時間以上前（インプレッションが安定してから取得）
  - posted_at が 30 日以内（古すぎるデータは収集不要）
  - 過去 24 時間以内にすでに取得済みの投稿はスキップ
  - media_id が 'migrated_' で始まる（移行データ）はスキップ
  - insights_skip = TRUE の投稿はスキップ（削除済みなど取得不能な投稿）
"""
import time
from datetime import datetime, timezone, timedelta

import requests
from supabase_client import get_supabase
from config import THREADS_ACCESS_TOKEN

INSIGHTS_URL = "https://graph.threads.net/v1.0/{media_id}/insights"
METRICS = "views,likes,replies,reposts,quotes"


def _is_not_found_error(response_text: str) -> bool:
    """400 エラーが「投稿が存在しない」ことによるものか判定する"""
    text = response_text.lower()
    return "does not exist" in text or "unsupported get request" in text


def fetch_insights(media_id: str) -> tuple[dict | None, bool]:
    """
    Threads Insights API を叩いてメトリクスを返す。
    戻り値: (metrics_dict | None, should_skip)
      - should_skip=True のとき、この投稿は以後スキップすべき（削除済み等）
    """
    url = INSIGHTS_URL.format(media_id=media_id)
    params = {"metric": METRICS, "access_token": THREADS_ACCESS_TOKEN}
    try:
        res = requests.get(url, params=params, timeout=10)
    except Exception as e:
        print(f"  ⚠️ リクエスト例外 [{media_id}]: {e}")
        return None, False

    if res.status_code != 200:
        if _is_not_found_error(res.text):
            print(f"  ⚠️ 投稿が存在しないためスキップ登録 [{media_id}]")
            return None, True
        print(f"  ⚠️ API エラー [{media_id}]: {res.status_code} {res.text}")
        return None, False

    result = {}
    for item in res.json().get("data", []):
        name = item.get("name")
        values = item.get("values") or []
        if name and values:
            result[name] = values[0].get("value", 0)
    return result, False


def collect_all_insights() -> None:
    supabase = get_supabase()
    now = datetime.now(timezone.utc)

    cutoff_old = (now - timedelta(days=30)).isoformat()   # 30日より古い投稿は対象外
    cutoff_new = (now - timedelta(hours=24)).isoformat()  # 24時間以内の投稿は未安定のため対象外

    target_posts = (
        supabase.table("posts")
        .select("id, media_id")
        .gte("posted_at", cutoff_old)
        .lte("posted_at", cutoff_new)
        .neq("insights_skip", True)
        .execute()
        .data
    )

    # media_id が 'migrated_' 始まり（移行データ）を除外
    target_posts = [p for p in target_posts if not p["media_id"].startswith("migrated_")]

    if not target_posts:
        print("取得対象の投稿なし")
        return

    # 過去 24 時間以内にすでに取得済みの post_id を除外
    recently_fetched = {
        row["post_id"]
        for row in supabase.table("post_insights")
        .select("post_id")
        .gte("fetched_at", cutoff_new)
        .execute()
        .data
    }

    pending = [p for p in target_posts if p["id"] not in recently_fetched]
    print(f"インサイト取得対象: {len(pending)} 件 / 全 {len(target_posts)} 件")

    fetched_count = 0
    skip_count = 0
    for post in pending:
        post_id = post["id"]
        media_id = post["media_id"]

        metrics, should_skip = fetch_insights(media_id)

        if should_skip:
            supabase.table("posts").update({"insights_skip": True}).eq("id", post_id).execute()
            skip_count += 1
            continue

        if metrics is None:
            continue

        supabase.table("post_insights").insert({
            "post_id":       post_id,
            "media_id":      media_id,
            "views":         metrics.get("views"),
            "likes":         metrics.get("likes"),
            "replies_count": metrics.get("replies"),
            "reposts":       metrics.get("reposts"),
            "quotes":        metrics.get("quotes"),
        }).execute()

        fetched_count += 1
        v = metrics.get("views", "?")
        l = metrics.get("likes", "?")
        print(f"  ✅ [{media_id}] views:{v}  likes:{l}")
        time.sleep(0.5)  # レートリミット対策

    print(f"\n✅ インサイト取得完了: {fetched_count} 件保存 / {skip_count} 件スキップ登録（削除済み投稿）")


if __name__ == "__main__":
    collect_all_insights()
