# generate_casual_post.py
"""
カジュアル（日常）投稿を生成してdraftsに保存する

【修正済みバグ】
- prompt が f-string になっていなかった（used_topics が展開されなかった）
- TOPIC/POST パース失敗時に IndexError が発生する脆弱な実装を修正
"""
import json
from supabase_client import get_supabase
from gemini_client import generate_with_fallback
from config import CASUAL_THEMES


def build_casual_prompt(used_topics: list[str]) -> str:
    """
    カジュアル投稿生成プロンプト。
    JSONで返させることで、脆弱な文字列パースを不要にする。
    """
    used_topics_str = "、".join(used_topics) if used_topics else "なし"

    return f"""
あなたは自然体で共感されるThreadsユーザーです。

最近使用したテーマ（避けてください）: {used_topics_str}

テーマ候補:
{chr(10).join(CASUAL_THEMES)}

上記テーマ候補から1つ選び、以下のJSON形式のみで出力してください（それ以外の文言は不要）。

{{
  "topic": "選んだテーマ名",
  "post": "投稿本文"
}}

投稿本文の条件:
・10〜120文字
・現在の日本の時刻や季節に違和感がない内容
・改行を入れて読みやすく
・自然で落ち着いた口調
・絵文字は1〜2個
・日常の気づきや疑問
・商品紹介は禁止
・PR表記は絶対に入れない
・ポジティブまたは共感的な内容
""".strip()


def parse_casual_response(text: str) -> tuple[str, str]:
    """
    Geminiのレスポンス（JSON）をパースしてtopic, postを返す。
    パース失敗時は Exception を送出。
    """
    # コードブロックが含まれている場合は除去
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        topic = data["topic"].strip()
        post = data["post"].strip()
        return topic, post
    except (json.JSONDecodeError, KeyError) as e:
        raise Exception(f"Geminiレスポンスのパース失敗: {e}\n---\n{text}\n---")


def generate_casual_draft() -> None:
    supabase = get_supabase()

    # 直近20件の使用トピックを取得
    recent = (
        supabase.table("casual_posted")
        .select("topic")
        .order("posted_at", desc=True)
        .limit(20)
        .execute()
    )
    used_topics = [row["topic"] for row in (recent.data or [])]

    prompt = build_casual_prompt(used_topics)
    text = generate_with_fallback(prompt)
    topic, post = parse_casual_response(text)

    print("===== casual topic =====")
    print(topic)
    print("===== casual post =====")
    print(post)

    supabase.table("drafts").insert(
        {
            "main_post": post,
            "post_type": "casual",
            "status": "pending",
            "topic": topic,
        }
    ).execute()

    print("✅ casual draft保存完了")


if __name__ == "__main__":
    generate_casual_draft()
