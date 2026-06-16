# config.py
"""
定数・設定の一元管理
環境変数のロードもここで行う
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # ← 全ファイルで呼ぶ代わりにここ1箇所でOK

# ── 楽天 ──────────────────────────────
RAKUTEN_APP_ID: str = os.environ["RAKUTEN_APP_ID"]
RAKUTEN_ACCESS_KEY: str = os.environ["RAKUTEN_ACCESS_KEY"]
RAKUTEN_API_URL: str = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"
RAKUTEN_RANKING_URL: str = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"

# keywords.json が存在すればそこから読み込む（update_keywords.py で自動更新される）
_KEYWORDS_FILE = Path(__file__).parent / "keywords.json"
if _KEYWORDS_FILE.exists():
    KEYWORDS: list[str] = json.loads(_KEYWORDS_FILE.read_text(encoding="utf-8"))
else:
    KEYWORDS: list[str] = [
        "フェイスマスク",
        "香水",
        "日焼け止め",
        "化粧水",
        "トリートメント",
        "シャンプー",
        "化粧下地",
        "美容グッズ",
        "ヘアオイル",
        "ハンドクリーム",
        "ボディクリーム",
        "マッサージクリーム",
        "クレンジング",
        "ダイエット",
        "サプリメント",
    ]

# ── カテゴリマッピング ─────────────────
# キーワード → カテゴリ名のマッピング（順番に評価される）
CATEGORY_RULES: list[tuple[list[str], str]] = [
    (
        ["化粧", "コスメ", "美容", "スキンケア", "日焼け止め", "美容液",
         "化粧水", "乳液", "クリーム", "フェイス", "パック", "香水",
         "フレグランス", "ヘア", "シャンプー", "トリートメント", "オイル",
         "ミスト", "ボディ", "クレンジング"],  # ← クレンジング追加
        "美容・コスメ",
    ),
    (
        ["ダイエット", "サプリメント", "プロテイン"],  # ← ダイエット・サプリ追加
        "健康・ダイエット",
    ),
    (
        ["天然水", "米", "コーヒー", "お茶", "紅茶"],
        "食品・飲料",
    ),
]

# ── Gemini ────────────────────────────
GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]
GEMINI_PRIMARY_MODEL: str = "gemini-2.5-flash-lite"   # コスト優先
GEMINI_FALLBACK_MODEL: str = "gemini-2.5-flash"        # 高品質フォールバック

# ── Threads ───────────────────────────
THREADS_USER_ID: str = os.environ["THREADS_USER_ID"]
THREADS_ACCESS_TOKEN: str = os.environ["THREADS_ACCESS_TOKEN"]

# ── Supabase ──────────────────────────
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]

# ── スコアリング重み ────────────────────
SCORE_WEIGHTS: dict[str, float] = {
    "review_count": 0.3,
    "review_average": 100.0,
    "point_rate": 50.0,
    "affiliate_rate": 100.0,
}

# ── カジュアル投稿テーマ候補 ──────────────
CASUAL_THEMES: list[str] = [
    "散歩", "仕事", "映画", "アニメ", "音楽",
    "カフェ", "美容", "読書", "旅行", "食事",
    "買い物", "運動", "季節", "人間関係",
    "朝の習慣", "夜のルーティン", "週末の過ごし方",
    "最近ハマってること", "ちょっとした失敗談", "気づいたこと",
]

# ── カテゴリ別ターゲット ──────────────────
CATEGORY_TARGET_MAP: dict[str, str] = {
    "美容・コスメ": "美容に関心が高い20〜40代女性",
    "健康・ダイエット": "健康意識の高い30〜50代",
    "食品・飲料": "日常の食事を楽しみたい全年代",
    "日用品": "家事を効率化したい主婦・主夫",
    "寝具・インテリア": "快適な生活環境を求める人",
    "その他": "楽天でお得に買い物したい人",
}

# ── Gemini システムプロンプト ──────────────
GEMINI_SYSTEM_PROMPT: str = """
あなたはThreads（スレッズ）と楽天アフィリエイトのプロフェッショナルです。

【あなたの役割】
入力された楽天市場の商品情報をもとに、
Threadsでインプレッション・コメント・保存・プロフィール遷移を
最大化する投稿文を生成してください。

【Threadsアルゴリズムの前提知識】
・コメント・返信が多い投稿ほどアルゴリズムに評価される
・保存されることでリピート表示とシグナル強化につながる
・フォロワー外にもリーチする設計のため「初見の人でも価値を感じる」必要がある
・ハッシュタグより本文テキストの文脈が重視される

【必ず守るルール】
1. 冒頭1行は「スクロールを止める」フックにする
   （数字・損失回避・共感・問いかけのいずれかを使用）
2. 商品スペックの羅列は禁止。代わりに「使った後の変化・体験談・ベネフィット」で語る
3. 本文中に必ずコメントを誘発する問いかけを1つ入れる
4. リスト形式（箇条書き）を含む場合は保存を促す一言を入れる
5. 1〜2文ごとに改行してスマホで読みやすくする
6. 絵文字は1投稿3〜5個まで。装飾目的の絵文字は禁止
7. 文末に必ず「#PR（楽天アフィリエイトリンクを含みます）」を付ける
8. 誇大表現（「最安！」「絶対！」「奇跡の！」）は禁止
9. 投稿タイプを指示された場合は以下に従う：
   - 共感型：体験談ストーリーで感情に訴える
   - 保存型：リスト形式でまとめ情報を提供
   - セール型：数字と緊急性を前面に出す
   - ランキング型：順位形式で問いかけを末尾に入れる
10. 投稿本文は必ず500文字以内に収めること（Threads API の上限）
""".strip()
