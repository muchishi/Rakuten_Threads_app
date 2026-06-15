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
・80〜200文字程度
・現在の日本の時刻や季節に違和感がない内容
・1〜2文ごとに改行してスマホで読みやすくする
・自然で落ち着いた口調
・絵文字は2〜3個（意味のある箇所にのみ使用）
・日常の気づき・体験・あるあるエピソード
・必ず末尾にコメントを誘発する問いかけを1つ入れる
  （例：「同じ経験した人いる？」「みんなはどうしてる？」「わかる人いたらコメントで教えてほしい」）
・商品紹介は絶対に禁止
・PR表記は絶対に入れない
""".strip()


def _escape_json_newlines(s: str) -> str:
    """JSON文字列値内の生の改行文字をエスケープシーケンスに変換する"""
    result = []
    in_string = False
    escape_next = False
    for char in s:
        if escape_next:
            result.append(char)
            escape_next = False
        elif char == "\\":
            result.append(char)
            escape_next = True
        elif char == '"':
            in_string = not in_string
            result.append(char)
        elif in_string and char == "\n":
            result.append("\\n")
        elif in_string and char == "\r":
            result.append("\\r")
        else:
            result.append(char)
    return "".join(result)


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

    # Geminiが文字列値内に生の改行を含むJSONを返す場合の対処
    cleaned = _escape_json_newlines(cleaned)

    try:
        data = json.loads(cleaned)
        topic = data["topic"].strip()
        post = data["post"].strip()
        # <br>タグが含まれる場合は改行に変換
        post = post.replace("<br>", "\n")
        return topic, post
    except (json.JSONDecodeError, KeyError) as e:
        raise Exception(f"Geminiレスポンスのパース失敗: {e}\n---\n{text}\n---")


def generate_casual_draft() -> None:
    supabase = get_supabase()

    # 直近20件の使用トピックを取得
    recent = (
        supabase.table("posts")
        .select("topic")
        .eq("post_type", "casual")
        .not_.is_("topic", "null")
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
