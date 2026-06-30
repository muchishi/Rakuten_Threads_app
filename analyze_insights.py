# analyze_insights.py
"""
post_insights と posts・drafts を結合してパフォーマンスレポートを生成する

実行方法:
  $env:PYTHONIOENCODING="utf-8"; python analyze_insights.py
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from supabase_client import get_supabase
from gemini_client import generate_with_fallback


def fetch_joined_records() -> list[dict]:
    supabase = get_supabase()

    insights = supabase.table("post_insights").select("*").execute().data
    posts = {p["id"]: p for p in supabase.table("posts").select("*").execute().data}
    drafts = {d["id"]: d for d in supabase.table("drafts").select("*").execute().data}

    records = []
    for ins in insights:
        post = posts.get(ins["post_id"])
        if not post:
            continue
        draft = drafts.get(post.get("draft_id")) or {}

        hour_jst = None
        posted_at = post.get("posted_at")
        if posted_at:
            try:
                dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
                hour_jst = (dt.hour + 9) % 24
            except Exception:
                pass

        main_post = draft.get("main_post") or ""
        records.append({
            "post_id":      ins["post_id"],
            "views":        ins.get("views") or 0,
            "likes":        ins.get("likes") or 0,
            "replies_count": ins.get("replies_count") or 0,
            "reposts":      ins.get("reposts") or 0,
            "quotes":       ins.get("quotes") or 0,
            "post_type":    post.get("post_type", "unknown"),
            "topic":        post.get("topic"),
            "posted_at":    posted_at,
            "hour_jst":     hour_jst,
            "main_post":    main_post,
            "post_length":  len(main_post),
        })

    return records


def avg(values: list) -> float:
    return sum(values) / len(values) if values else 0.0


def median(values: list) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    return (s[n // 2 - 1] + s[n // 2]) / 2 if n % 2 == 0 else s[n // 2]


def sep(title: str = "") -> None:
    if title:
        print(f"\n{'━'*52}")
        print(f"  {title}")
        print('━' * 52)
    else:
        print('━' * 52)


def generate_report(records: list[dict]) -> None:
    if not records:
        print("⚠️  post_insights にデータがありません。")
        print("   collect_insights.py を実行後、再度お試しください。")
        return

    total = len(records)
    all_views = [r["views"] for r in records]

    # ── サマリー ─────────────────────────────
    sep("サマリー")
    print(f"  分析対象投稿数 : {total} 件")
    print(f"  平均 views     : {avg(all_views):.1f}")
    print(f"  中央値 views   : {median(all_views):.1f}")
    print(f"  最大 views     : {max(all_views)}")
    print(f"  最小 views     : {min(all_views)}")

    # ── 投稿タイプ別 ──────────────────────────
    sep("投稿タイプ別 平均 views")
    by_type: dict[str, list] = defaultdict(list)
    for r in records:
        by_type[r["post_type"]].append(r["views"])
    for ptype, views in sorted(by_type.items(), key=lambda x: avg(x[1]), reverse=True):
        bar = "█" * int(avg(views) / max(avg(v) for v in by_type.values()) * 20)
        print(f"  {ptype:8s} {bar:<20s} 平均 {avg(views):6.1f} views  ({len(views)} 件)")

    # ── カジュアル: トピック別 ──────────────────
    casual = [r for r in records if r["post_type"] == "casual" and r["topic"]]
    if casual:
        sep("カジュアル投稿: トピック別 平均 views（上位 10）")
        by_topic: dict[str, list] = defaultdict(list)
        for r in casual:
            by_topic[r["topic"]].append(r["views"])
        ranked = sorted(by_topic.items(), key=lambda x: avg(x[1]), reverse=True)
        for i, (topic, views) in enumerate(ranked[:10], 1):
            print(f"  {i:2}. {topic:25s} 平均 {avg(views):6.1f} views  ({len(views)} 件)")

    # ── 時間帯別（JST） ───────────────────────
    timed = [r for r in records if r["hour_jst"] is not None]
    if timed:
        sep("時間帯別 平均 views（JST・上位 6）")
        by_hour: dict[int, list] = defaultdict(list)
        for r in timed:
            by_hour[r["hour_jst"]].append(r["views"])
        ranked_h = sorted(by_hour.items(), key=lambda x: avg(x[1]), reverse=True)
        for hour, views in ranked_h[:6]:
            print(f"  {hour:02d}:00  平均 {avg(views):6.1f} views  ({len(views)} 件)")

    # ── 文字数 vs views ───────────────────────
    sep("投稿文字数 vs 平均 views")
    bins: dict[str, list] = {
        "〜100字":   [],
        "101〜200字": [],
        "201〜300字": [],
        "301字〜":    [],
    }
    for r in records:
        l = r["post_length"]
        if l <= 100:
            bins["〜100字"].append(r["views"])
        elif l <= 200:
            bins["101〜200字"].append(r["views"])
        elif l <= 300:
            bins["201〜300字"].append(r["views"])
        else:
            bins["301字〜"].append(r["views"])
    for label, views in bins.items():
        if views:
            print(f"  {label:10s}  平均 {avg(views):6.1f} views  ({len(views)} 件)")

    # ── エンゲージメント率 ────────────────────
    sep("エンゲージメント指標（全体平均・views > 0 のみ）")
    with_views = [r for r in records if r["views"] > 0]
    if with_views:
        like_rate   = avg([r["likes"]         / r["views"] * 100 for r in with_views])
        reply_rate  = avg([r["replies_count"]  / r["views"] * 100 for r in with_views])
        repost_rate = avg([r["reposts"]        / r["views"] * 100 for r in with_views])
        print(f"  いいね率     : {like_rate:.2f}%")
        print(f"  コメント率   : {reply_rate:.2f}%")
        print(f"  リポスト率   : {repost_rate:.2f}%")
    else:
        print("  views > 0 のデータなし")

    # ── TOP 投稿一覧 ──────────────────────────
    sep("views TOP 投稿（最大 10 件）")
    top = sorted(records, key=lambda x: x["views"], reverse=True)[:10]
    for i, r in enumerate(top, 1):
        snippet = (r["main_post"] or "").replace("\n", " ")[:55]
        print(f"  {i:2}. [{r['post_type']:8s}] views:{r['views']:5d}  {snippet}…")

    # ── Gemini パターン分析 ───────────────────
    top_with_text = [r for r in top if r.get("main_post")]
    if len(top_with_text) >= 2:
        sep("Gemini による高 views 投稿のパターン分析")
        posts_text = "\n\n".join([
            f"【{i+1}位 / {r['post_type']} / views:{r['views']} / {r['post_length']}字】\n{r['main_post']}"
            for i, r in enumerate(top_with_text)
        ])
        prompt = f"""
以下は日本の Threads（スレッズ）への自動投稿のうち、閲覧数（views）が高かった投稿です。

{posts_text}

これらの投稿に共通する特徴・傾向を以下の観点で日本語で分析してください。

1. 【冒頭フックの特徴】スクロールを止めている書き出しの共通パターン
2. 【本文構成の特徴】流れや構成上の共通点
3. 【エンゲージメント要因】共感・感情・問いかけなどのどの要素が効いているか
4. 【改善提案】今後の投稿に活かせる具体的なアドバイスを3点以内で

簡潔に、箇条書きで答えてください（余分な前置きは不要）。
""".strip()
        print("  分析中...")
        analysis = generate_with_fallback(prompt)
        print()
        print(analysis)
    else:
        print("\n  ※ 本文データが不足しているため Gemini 分析をスキップしました")


def main() -> None:
    print("データ取得中...")
    records = fetch_joined_records()
    print(f"インサイトデータ取得完了: {len(records)} 件\n")
    generate_report(records)
    print()


if __name__ == "__main__":
    main()
