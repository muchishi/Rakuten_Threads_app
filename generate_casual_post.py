import os
import sqlite3
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

conn = sqlite3.connect("rakuten.db")
cursor = conn.cursor()

# -----------------------
# カジュアル投稿プロンプト
# -----------------------
prompt = """
あなたは自然体で共感されるThreadsユーザーです。

以下の条件で雑談投稿を1つ作成してください。

条件：
・80〜120文字
・改行を入れて読みやすく
・自然でおちついた口調
・絵文字は1〜2個
・おじさんっぽくならないように
・日常の気づきや疑問
・商品紹介は禁止
・最後にPRなども絶対に入れない
・ポジティブや共感的な内容が好ましい

例：
・最近朝起きるのしんどすぎる
・コンビニコーヒーどれが一番うまいんだろ
・エアコンつけっぱなしって電気代どうなんだろ
・今日の天気、いいな
出力は1つのみ
"""


def generate_with_retry(prompt, model, retry=6, sleep_sec=7):
    for i in range(retry):
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            return response.text

        except Exception as e:
            print(f"[{model}] retry {i+1}/{retry} error: {e}")

            if i < retry - 1:
                time.sleep(sleep_sec)

    return None


def generate_with_fallback(prompt):
    # -----------------------
    # 1st: 2.5-flash（コスト安）
    # -----------------------
    text = generate_with_retry(prompt, "gemini-3.1-flash-lite", retry=10)

    if text:
        return text

    print("2.5-flash失敗 → 3.5-flashへフォールバック")

    # -----------------------
    # 2nd: 3.5-flash（高性能）
    # -----------------------
    text = generate_with_retry(prompt, "gemini-3.5-flash", retry=6)

    if text:
        return text

    raise Exception("両モデルとも生成失敗")


# -----------------------
# 使用例（カジュアル）
# -----------------------
post_text = generate_with_fallback(prompt)

print("生成成功")

print("===== casual post =====")
print(post_text)

# -----------------------
# DB保存
# -----------------------
cursor.execute(
    """
INSERT INTO drafts (
    item_code,
    main_post,
    reply_post,
    item_url,
    post_type
)
VALUES (?, ?, ?, ?, ?)
""",
    (None, post_text, "", "", "casual"),
)

conn.commit()
conn.close()

print("casual draft保存完了")
