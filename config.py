# config.py
"""
定数・設定の一元管理
環境変数のロードもここで行う
"""
import os
from dotenv import load_dotenv

load_dotenv()  # ← 全ファイルで呼ぶ代わりにここ1箇所でOK

# ── 楽天 ──────────────────────────────
RAKUTEN_APP_ID: str = os.environ["RAKUTEN_APP_ID"]
RAKUTEN_ACCESS_KEY: str = os.environ["RAKUTEN_ACCESS_KEY"]
RAKUTEN_API_URL: str = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"

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
    # 追加したいキーワードはここに
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
]
