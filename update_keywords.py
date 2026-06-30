# update_keywords.py
"""
keywords.json を定期的に更新するスクリプト
.github/workflows/update_keywords.yml から週次で自動実行される

処理フロー:
1. 低パフォーマンスキーワード3つを脱落
   （products テーブルのスコア × 投稿率 が低いもの）
2. 楽天ランキングAPIで売れ筋トレンドを取得
3. Gemini + Google Search でThreadsトレンドをリサーチ
4. 新キーワード3つを追加して keywords.json を更新
"""
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from supabase_client import get_supabase
from gemini_client import get_client
from config import RAKUTEN_APP_ID, RAKUTEN_ACCESS_KEY, RAKUTEN_API_URL, KEYWORDS, SCORE_WEIGHTS, CATEGORY_RULES

KEYWORDS_FILE = Path(__file__).parent / "keywords.json"
MIN_KEYWORDS = 8  # これ以上削除しない安全下限


# ── ユーティリティ ──────────────────────────────────────

def load_keywords() -> list[str]:
    if KEYWORDS_FILE.exists():
        return json.loads(KEYWORDS_FILE.read_text(encoding="utf-8"))
    return list(KEYWORDS)


def save_keywords(keywords: list[str]) -> None:
    KEYWORDS_FILE.write_text(
        json.dumps(keywords, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def calc_score(item: dict) -> float:
    w = SCORE_WEIGHTS
    return (
        (item.get("review_count") or 0) * w["review_count"]
        + (item.get("review_average") or 0) * w["review_average"]
        + (item.get("point_rate") or 0) * w["point_rate"]
        + (item.get("affiliate_rate") or 0) * w["affiliate_rate"]
        + (item.get("price") or 0) * w.get("price", 0)
    )


# ── Step 1: 低パフォーマンス検出 ───────────────────────

def find_low_performing_keywords(current_keywords: list[str], n: int = 3) -> list[str]:
    """
    低パフォーマンスキーワードを検出する。

    優先指標（データがある場合）:
      post_insights.views の平均 × 投稿数ボーナス
    フォールバック（insights がない場合）:
      products テーブルの平均スコア × (1 + 90日以内の投稿率)
    """
    supabase = get_supabase()
    cutoff90 = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

    # posts テーブルから90日以内の product 投稿を取得
    posts_rows = (
        supabase.table("posts")
        .select("id, item_code")
        .eq("post_type", "product")
        .gte("posted_at", cutoff90)
        .not_.is_("item_code", "null")
        .execute()
        .data
    )
    post_item_map = {row["id"]: row["item_code"] for row in posts_rows}

    # post_insights から views を取得（post_id ごとの最大値）
    post_views: dict[int, int] = {}
    if post_item_map:
        insights_rows = (
            supabase.table("post_insights")
            .select("post_id, views")
            .in_("post_id", list(post_item_map.keys()))
            .execute()
            .data
        )
        for row in insights_rows:
            pid = row["post_id"]
            v = row.get("views") or 0
            if pid not in post_views or v > post_views[pid]:
                post_views[pid] = v

    # products テーブルからスコアとキーワードマップを構築
    products = (
        supabase.table("products")
        .select("item_code, keyword, review_count, review_average, point_rate, affiliate_rate")
        .execute()
        .data
    )
    item_keyword = {p["item_code"]: p.get("keyword", "") for p in products}

    # キーワード別集計
    stats: dict[str, dict] = {
        kw: {"views": [], "post_count": 0, "scores": []}
        for kw in current_keywords
    }

    for pid, item_code in post_item_map.items():
        kw = item_keyword.get(item_code or "", "")
        if kw not in stats:
            continue
        stats[kw]["post_count"] += 1
        if pid in post_views:
            stats[kw]["views"].append(post_views[pid])

    for p in products:
        kw = p.get("keyword", "")
        if kw in stats:
            stats[kw]["scores"].append(calc_score(p))

    def perf(kw: str) -> float:
        s = stats.get(kw, {})
        # views データがあれば優先
        if s.get("views"):
            avg_views = sum(s["views"]) / len(s["views"])
            return avg_views * (1 + s["post_count"] * 0.1)
        # なければ product スコア × 投稿率
        if s.get("scores"):
            avg_score = sum(s["scores"]) / len(s["scores"])
            post_rate = s["post_count"] / len(s["scores"])
            return avg_score * (1 + post_rate)
        return 0.0

    # 全キーワードの指標が 0 なら投稿・商品データ不足 → 除外しない
    if all(perf(kw) == 0.0 for kw in current_keywords):
        print("  投稿・商品データが不足しているため除外をスキップ（全指標 0）")
        return []

    ranked = sorted(current_keywords, key=perf)
    low = ranked[:n]

    for kw in low:
        s = stats.get(kw, {})
        avg_v = f"{sum(s['views'])/len(s['views']):.0f}" if s.get("views") else "N/A"
        print(
            f"  除外候補: {kw!r}  "
            f"(投稿数:{s.get('post_count', 0)}, "
            f"平均views:{avg_v}, "
            f"指標:{perf(kw):.1f})"
        )
    return low


# ── Step 2: 楽天売れ筋取得 ───────────────────────────

def fetch_rakuten_ranking_items() -> list[str]:
    """
    楽天APIでレビュー数上位の商品名リストを返す。
    複数カテゴリを横断して取得しGeminiへのコンテキストにする。
    """
    search_words = ["美容", "コスメ", "日用品", "健康"]
    all_names: list[str] = []
    for i, word in enumerate(search_words):
        if i > 0:
            time.sleep(2.0)  # 429 レートリミット対策
        params = {
            "applicationId": RAKUTEN_APP_ID,
            "accessKey": RAKUTEN_ACCESS_KEY,
            "keyword": word,
            "hits": 8,
            "format": "json",
        }
        try:
            res = requests.get(RAKUTEN_API_URL, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            items = data.get("Items", [])
            for row in items:
                name = (row.get("Item") or row).get("itemName", "")
                if name:
                    all_names.append(name)
        except Exception as e:
            print(f"  楽天検索エラー [{word}]: {e}")
    return all_names


# ── Step 3: Gemini + Google Search でトレンドリサーチ ───

def research_new_keywords(
    current_keywords: list[str],
    remove_keywords: list[str],
    rakuten_top_items: list[str],
    n: int = 3,
) -> list[str]:
    """
    Gemini + Google Search grounding で Threads・楽天のトレンドを調査し
    新しい検索キーワードをn個返す。
    """
    from google.genai import types

    month = datetime.now().month
    season_map = {
        1: "冬", 2: "冬", 3: "春", 4: "春", 5: "春",
        6: "夏", 7: "夏", 8: "夏", 9: "秋", 10: "秋",
        11: "秋", 12: "冬",
    }
    season = season_map[month]

    rakuten_summary = "\n".join(f"・{name}" for name in rakuten_top_items[:15])

    prompt = f"""
あなたは楽天アフィリエイトとThreadsマーケティングの専門家です。

以下の情報をもとに、楽天市場の検索キーワードとして使えるトレンドキーワードを{n}つ提案してください。

【現在使用中のキーワード（重複不可・除外対象のキーワードも含む）】
{', '.join(current_keywords)}

【楽天ランキング上位商品名（参考）】
{rakuten_summary}

【季節・時期】{season}（{month}月）

【調査してほしいこと】
・現在の日本のThreads・Instagram で美容・ライフスタイル系ユーザーが話題にしている商品カテゴリ
・楽天市場で今月売れ筋のジャンル（上記ランキングも参考に）
・季節性トレンド（{season}に需要が高まる商品カテゴリ）

【キーワード選定条件】
・楽天市場の検索1語として機能すること（例：「シャンプー」「日焼け止め」「プロテイン」）
・美容・コスメ・日用品・健康・食品・ライフスタイルのカテゴリ
・現在使用中のキーワードと重複しない
・楽天でレビュー数が多い人気商品が存在するカテゴリ

以下のJSON形式のみで出力してください（説明文不要）:
{{"keywords": ["キーワード1", "キーワード2", "キーワード3"]}}
"""

    client = get_client()
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
    )

    try:
        res = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=config,
        )
        text = res.text
    except Exception as e:
        print(f"Search grounding 失敗、通常モードで再試行: {e}")
        from gemini_client import generate_with_fallback
        text = generate_with_fallback(prompt)

    # JSON抽出
    cleaned = text.strip()
    if "```" in cleaned:
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    # JSON部分のみ抽出（余分なテキストが混入する場合に対応）
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        cleaned = cleaned[start:end]

    data = json.loads(cleaned)
    return [kw.strip() for kw in data["keywords"][:n]]


# ── メイン処理 ────────────────────────────────────────

def run_keyword_update() -> None:
    print("===== キーワード更新開始 =====\n")

    current = load_keywords()
    print(f"現在のキーワード ({len(current)}件): {current}\n")

    # Step 1: 低パフォーマンス検出
    print("[Step 1] 低パフォーマンスキーワードを特定中...")
    if len(current) <= MIN_KEYWORDS:
        print(f"  キーワード数が安全下限({MIN_KEYWORDS})以下のため除外スキップ")
        low_performers: list[str] = []
    else:
        remove_n = min(3, len(current) - MIN_KEYWORDS)
        low_performers = find_low_performing_keywords(current, n=remove_n)

    # Step 2: 楽天ランキング取得
    print("\n[Step 2] 楽天ランキングを取得中...")
    rakuten_items: list[str] = []
    try:
        rakuten_items = fetch_rakuten_ranking_items()
        print(f"  取得件数: {len(rakuten_items)}件")
    except Exception as e:
        print(f"  楽天APIエラー（スキップ）: {e}")

    # Step 3: Gemini でリサーチ
    print("\n[Step 3] Gemini + Google Search でトレンドリサーチ中...")
    try:
        new_keywords = research_new_keywords(current, low_performers, rakuten_items, n=3)
        print(f"  追加候補: {new_keywords}")
    except Exception as e:
        print(f"  Geminiリサーチ失敗: {e}")
        new_keywords = []

    # Step 4: 更新して保存
    updated = [kw for kw in current if kw not in low_performers]
    for kw in new_keywords:
        # current に含まれるキーワード（除外候補を含む）は追加しない
        if kw and kw not in current and kw not in updated:
            updated.append(kw)

    save_keywords(updated)

    print("\n===== 更新完了 =====")
    print(f"  除外 ({len(low_performers)}件): {low_performers}")
    print(f"  追加 ({len(new_keywords)}件): {new_keywords}")
    print(f"  変更前 ({len(current)}件): {current}")
    print(f"  変更後 ({len(updated)}件): {updated}")


if __name__ == "__main__":
    run_keyword_update()
