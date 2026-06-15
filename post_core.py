# post_core.py
"""
Threads API への投稿処理（メディアコンテナ作成 → 公開の2ステップ）
"""
import time
import requests
from config import THREADS_USER_ID, THREADS_ACCESS_TOKEN


def create_post(
    text: str,
    image_url: str | None = None,
    reply_to_id: str | None = None,
    user_id: str = THREADS_USER_ID,
    token: str = THREADS_ACCESS_TOKEN,
) -> dict | None:
    """
    Threads に投稿する。成功時は dict、失敗時は None を返す。

    Args:
        text: 投稿テキスト
        image_url: 画像URL（任意）
        reply_to_id: リプライ先の media_id（任意）
        user_id: Threads ユーザーID（デフォルトは環境変数）
        token: アクセストークン（デフォルトは環境変数）
    """
    create_url = f"https://graph.threads.net/v1.0/{user_id}/threads"
    publish_url = f"https://graph.threads.net/v1.0/{user_id}/threads_publish"

    # ── メディアコンテナ作成 ──────────────
    payload: dict = {
        "media_type": "IMAGE" if image_url else "TEXT",
        "text": text,
        "access_token": token,
    }
    if image_url:
        payload["image_url"] = image_url
    if reply_to_id:
        payload["reply_to_id"] = reply_to_id

    create_res = requests.post(create_url, data=payload, timeout=15)
    if create_res.status_code != 200:
        print(f"❌ create 失敗 [{create_res.status_code}]: {create_res.text}")
        return None

    creation_id = create_res.json().get("id")
    if not creation_id:
        print(f"❌ creation_id 未取得: {create_res.text}")
        return None

    time.sleep(1.5)  # Threads API の推奨待機

    # ── 公開 ─────────────────────────────
    publish_res = requests.post(
        publish_url,
        data={"creation_id": creation_id, "access_token": token},
        timeout=15,
    )
    if publish_res.status_code != 200:
        print(f"❌ publish 失敗 [{publish_res.status_code}]: {publish_res.text}")
        return None

    publish_data = publish_res.json()
    return {
        "creation_id": creation_id,
        "media_id": publish_data.get("id"),
        "raw": publish_data,
        "is_reply": bool(reply_to_id),
    }
