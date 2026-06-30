# generate_casual_post.py
"""
カジュアル（日常）投稿を生成してdraftsに保存する

【修正済みバグ】
- prompt が f-string になっていなかった（used_topics が展開されなかった）
- TOPIC/POST パース失敗時に IndexError が発生する脆弱な実装を修正
"""
import json
from datetime import datetime, timezone, timedelta
from supabase_client import get_supabase
from gemini_client import generate_with_fallback
from config import CASUAL_THEMES


def _get_season_hint(month: int) -> str:
    hints = {
        1:  "冬（寒さ・成人式・年明けムード）",
        2:  "冬（バレンタイン・まだ寒い・受験シーズン）",
        3:  "春の訪れ（卒業・花粉症・年度末）",
        4:  "春（新生活・新学期・花見・新社会人）",
        5:  "初夏（暑くなってきた・GW明けの疲れ）",
        6:  "梅雨（じめじめ・蒸し暑い・ボーナス月・夏前の準備）",
        7:  "夏（暑さ本番・夏バテ・夏祭り・花火）",
        8:  "真夏（猛暑・お盆・夏休み・節電）",
        9:  "秋の始まり（残暑・運動会・衣替え）",
        10: "秋（食欲の秋・読書の秋・ハロウィン）",
        11: "晩秋（朝晩の冷え込み・紅葉・年末準備）",
        12: "冬（クリスマス・大掃除・年末・忘年会）",
    }
    return hints.get(month, "")


def build_casual_prompt(used_topics: list[str]) -> str:
    """
    カジュアル投稿生成プロンプト。
    JSONで返させることで、脆弱な文字列パースを不要にする。
    """
    used_topics_str = "、".join(used_topics) if used_topics else "なし"

    now_jst = datetime.now(timezone(timedelta(hours=9)))
    month = now_jst.month
    season_hint = _get_season_hint(month)

    return f"""
あなたは自然体で共感されるThreadsユーザーです。

現在の時期: {month}月 - {season_hint}

最近使用したテーマ（避けてください）: {used_topics_str}

テーマ候補:
{chr(10).join(CASUAL_THEMES)}

上記テーマ候補から1つ選び、以下のJSON形式のみで出力してください（それ以外の文言は不要）。

{{
  "topic": "選んだテーマ名",
  "post": "投稿本文"
}}

投稿本文の条件（必ず守ること）:
・10〜350文字
・現在の時期（{month}月 / {season_hint}）に合った内容にする
・冒頭1行でスクロールが止まるフックから始める
・具体的なエピソード・数字・状況を入れる（「毎朝必ず」「3年続けて」「先週やらかした」）
・1〜2文ごとに改行してスマホで読みやすくする
・親近感のある口調（「〜だよね」「〜じゃない？」「私だけかな笑」）
・絵文字は2〜3個（意味のある箇所にのみ）
・必ず末尾にコメントを誘発する具体的な問いかけを1つ入れる
  良い例：「同じ人いる？」「みんなはどっち？」「これってあるある？」
  悪い例：「どう思いますか？」「皆さんはいかがでしょうか？」（堅くて読まれない）
・商品紹介・PR表記は絶対に禁止
・丁寧語（〜です・ます）は避けてSNSらしいカジュアルな文体で書く
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
