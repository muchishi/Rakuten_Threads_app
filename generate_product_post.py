# generate_product_post.py
"""
未投稿商品をスコアリングで選定し、Geminiで投稿文を生成してdraftsに保存する
"""
from datetime import datetime, timezone, timedelta
from supabase_client import get_supabase
from gemini_client import generate_with_fallback
from config import CATEGORY_RULES, SCORE_WEIGHTS, CATEGORY_TARGET_MAP, GEMINI_SYSTEM_PROMPT

_SEASON_HINTS = {
    1:  "冬（寒さ対策・乾燥・成人式シーズン）",
    2:  "冬（乾燥・バレンタイン・春の準備）",
    3:  "春の訪れ（花粉症・新生活準備・卒業式）",
    4:  "春（新生活・入学・紫外線が強くなり始め）",
    5:  "初夏（日差しが強くなる・GW・汗ばむ季節の入口）",
    6:  "梅雨〜初夏（蒸し暑い・紫外線ピーク・ボーナス月）",
    7:  "夏（紫外線・汗・夏バテ対策・夏祭り）",
    8:  "真夏（猛暑・日焼け・夏休み・冷感グッズ需要）",
    9:  "秋の始まり（残暑・乾燥が始まる・衣替え）",
    10: "秋（乾燥肌・読書の秋・ハロウィン）",
    11: "晩秋（寒くなる・防寒・年末準備）",
    12: "冬（クリスマス・乾燥・年末ギフト需要）",
}


def get_category(keyword: str) -> str:
    """キーワードからカテゴリ名を返す"""
    kw = keyword.lower()
    for keywords_list, category_name in CATEGORY_RULES:
        if any(k in kw for k in keywords_list):
            return category_name
    return "その他"


def determine_post_type(item: dict) -> str:
    """商品情報から最適な投稿タイプを判定する"""
    review_count = int(item.get("review_count") or 0)
    if review_count > 500:
        return "ランキング型"

    keyword = (item.get("keyword") or "").lower()
    daily_keywords = ["日用品", "キッチン", "掃除", "洗剤", "生活雑貨"]
    if any(k in keyword for k in daily_keywords):
        return "保存型"

    return "共感型"


def calc_score(item: dict) -> float:
    """商品のスコアを計算する（高いほど優先して投稿）"""
    w = SCORE_WEIGHTS
    return (
        (item.get("review_count") or 0) * w["review_count"]
        + (item.get("review_average") or 0) * w["review_average"]
        + (item.get("point_rate") or 0) * w["point_rate"]
        + (item.get("affiliate_rate") or 0) * w["affiliate_rate"]
        + (item.get("price") or 0) * w.get("price", 0)
    )


PR_NOTICE = "#PR（楽天アフィリエイトリンクを含みます）"


def ensure_pr_notice(text: str) -> str:
    """PR表記が省略・変形されていても必ず正式表記で終わるように補正する（景表法対応）"""
    if PR_NOTICE in text:
        return text
    lines = text.rstrip().splitlines()
    while lines and (not lines[-1].strip() or lines[-1].strip().lower().startswith("#pr")):
        lines.pop()
    return "\n".join(lines).rstrip() + "\n\n" + PR_NOTICE


def build_reply_text(item: dict) -> str:
    """価格・レビュー情報を含むリプライテキストを生成する"""
    review_str = f"⭐ {item.get('review_average', '?')}（レビュー{(item.get('review_count') or 0):,}件）"
    price_str = f"💴 {(item.get('price') or 0):,}円"
    return (
        f"▼ 楽天で詳細・購入はこちら（PR・楽天アフィリエイトリンク含む）\n\n"
        f"{review_str}\n"
        f"{price_str}\n\n"
        f"{item['item_url']}"
    )


def build_main_prompt(item: dict, category: str, post_type: str) -> str:
    target = CATEGORY_TARGET_MAP.get(category, "楽天でお得に買い物したい人")
    now_jst = datetime.now(timezone(timedelta(hours=9)))
    month = now_jst.month
    season_hint = _SEASON_HINTS.get(month, "")
    # 保存型・ランキング型は箇条書きを含むぶん少しだけ長さを許容する
    length_hint = (
        "250文字前後（箇条書きを含むため）"
        if post_type in ("保存型", "ランキング型")
        else "120〜200文字"
    )

    return f"""
【商品情報】
商品名: {item["item_name"]}
価格: {(item.get("price") or 0):,}円
カテゴリ: {category}
現在の時期: {month}月 - {season_hint}

【投稿タイプ】
{post_type}

【読み手のイメージ】
{target}

【文字数の目安】
{length_hint}（#PR表記を含む）。これより長くしないこと。
詳しい価格・レビュー・リンクはリプ欄に別途載せるので、本文に詰め込まない。

上記の情報をもとに、Threads投稿の本文のみを出力してください。
セクションラベルや余分な説明文は不要です。
""".strip()


def generate_product_draft() -> None:
    supabase = get_supabase()

    # 30日以内に投稿済みのitem_codeを取得
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    posted_codes = {
        row["item_code"]
        for row in supabase.table("posts")
        .select("item_code")
        .eq("post_type", "product")
        .gte("posted_at", cutoff)
        .not_.is_("item_code", "null")
        .execute()
        .data
    }

    # 未投稿商品を取得
    all_products = supabase.table("products").select("*").execute().data
    candidates = [p for p in all_products if p["item_code"] not in posted_codes]

    if not candidates:
        raise Exception("未投稿商品がありません")

    # スコア最大の商品を選定
    item = max(candidates, key=calc_score)
    category = get_category(item["keyword"])
    post_type = determine_post_type(item)

    print(f"選定商品: {item['item_name']} (カテゴリ: {category}, 投稿タイプ: {post_type})")

    # 投稿文生成（ガイドライン準拠のシステムプロンプトを使用）
    main_text = ensure_pr_notice(
        generate_with_fallback(
            build_main_prompt(item, category, post_type),
            system_instruction=GEMINI_SYSTEM_PROMPT,
        )
    )
    reply_text = build_reply_text(item)

    print("===== メイン投稿 =====")
    print(main_text)
    print("===== リプ投稿 =====")
    print(reply_text)

    # draftsに保存（item_url は reply_post テキストに埋め込み済みのため除外）
    supabase.table("drafts").upsert(
        {
            "item_code": item["item_code"],
            "main_post": main_text,
            "reply_post": reply_text,
            "image_url": item.get("image_url"),
            "status": "pending",
            "post_type": "product",
        },
        on_conflict="item_code",
    ).execute()

    print("✅ draft保存完了")


if __name__ == "__main__":
    generate_product_draft()
