# refresh_threads_token.py
"""
Threadsの長期アクセストークンをリフレッシュし、GitHub Secretsを自動更新する
"""
import os
import subprocess
import sys
import requests

REPO = os.environ["GITHUB_REPOSITORY"]  # GitHub Actionsが自動セット（例: owner/repo）


def refresh_token(current_token: str) -> dict | None:
    """th_refresh_token で新しい長期トークンを取得する"""
    url = "https://graph.threads.net/refresh_access_token"
    params = {
        "grant_type": "th_refresh_token",
        "access_token": current_token,
    }
    res = requests.get(url, params=params, timeout=15)
    if res.status_code != 200:
        print(f"❌ トークンリフレッシュ失敗 [{res.status_code}]: {res.text}")
        return None

    data = res.json()
    if not data.get("access_token"):
        print(f"❌ access_token が取得できませんでした: {res.text}")
        return None
    return data


def update_secret(new_token: str) -> bool:
    """gh CLI経由でリポジトリのTHREADS_ACCESS_TOKENシークレットを更新する（標準入力で渡しログに出さない）"""
    result = subprocess.run(
        ["gh", "secret", "set", "THREADS_ACCESS_TOKEN", "--repo", REPO],
        input=new_token,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"❌ Secrets更新失敗: {result.stderr}")
        return False
    return True


if __name__ == "__main__":
    current_token = os.environ["THREADS_ACCESS_TOKEN"]

    data = refresh_token(current_token)
    if not data:
        sys.exit(1)

    new_token = data["access_token"]
    expires_in_days = data.get("expires_in", 0) // 86400
    print(f"✅ 新しいトークンを取得（有効期限: 約{expires_in_days}日）")

    if not update_secret(new_token):
        sys.exit(1)

    print("✅ THREADS_ACCESS_TOKEN を更新しました")
