# QUICK_START.md

## よく使うコマンド

```powershell
# ── ローカル実行 ─────────────────────────────────────────────

# 通常実行（casual 70% / product 30% でランダム）
$env:PYTHONIOENCODING="utf-8"; python run.py

# 投稿タイプを固定してテスト（run.py の該当行を書き換える）
# post_type = "casual"
# post_type = "product"

# ── 個別スクリプト実行 ───────────────────────────────────────

# 楽天から商品を取得して products テーブルに保存
$env:PYTHONIOENCODING="utf-8"; python generate_product_select.py

# 商品投稿の下書きを生成（drafts に保存）
$env:PYTHONIOENCODING="utf-8"; python generate_product_post.py

# カジュアル投稿の下書きを生成（drafts に保存）
$env:PYTHONIOENCODING="utf-8"; python generate_casual_post.py

# Threads に投稿（drafts から pending を1件取り出す）
$env:PYTHONIOENCODING="utf-8"; python post_product.py
$env:PYTHONIOENCODING="utf-8"; python post_casual.py

# インプレッション収集（24〜30日前の投稿を対象）
$env:PYTHONIOENCODING="utf-8"; python collect_insights.py

# キーワード更新（低パフォーマンス3件除外 + 新規3件追加）
$env:PYTHONIOENCODING="utf-8"; python update_keywords.py

# ── スキーマ確認 ─────────────────────────────────────────────

# Supabase SQL エディターに貼り付ける SQL を出力
python database.py
```

---

## GitHub Actions の操作方法

### ワークフロー一覧

| ワークフロー | ファイル | トリガー |
|-------------|---------|---------|
| Threads Bot Run | `run.yml` | 3時間ごと（UTC 0,3,6,...時）/ 手動 |
| Weekly Keyword Update | `update_keywords.yml` | 毎週月曜 10:00 JST / 手動 |
| Product Select | `product_select.yml` | 12時間ごと（JST 10:00 / 22:00）/ 手動 |

### 手動実行

1. GitHub リポジトリ → **Actions** タブ
2. 左メニューからワークフロー名を選択
3. 右上の **Run workflow** ボタン → **Run workflow**

### 実行ログの確認

1. Actions タブ → 対象のワークフロー実行をクリック
2. `bot` ジョブ → 各ステップを展開してログを確認
3. エラー時は `Run bot` ステップのログを最初に確認する

### Secrets の設定

GitHub リポジトリ → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

必要な Secrets: `RAKUTEN_APP_ID`, `RAKUTEN_ACCESS_KEY`, `GEMINI_API_KEY`, `THREADS_USER_ID`, `THREADS_ACCESS_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY`

---

## 投稿フローの概要

### 通常実行（run.py）

```
run.py
 │
 ├─ [product 30%]
 │    ├─ generate_product_select.py  楽天APIで商品取得 → products テーブル
 │    ├─ generate_product_post.py    スコアリング → 投稿タイプ判定 → Gemini生成 → drafts
 │    └─ post_product.py             drafts(pending) → Threads投稿 → posts テーブル
 │
 └─ [casual 70%]
      ├─ generate_casual_post.py     Gemini生成（JSON） → drafts
      └─ post_casual.py              drafts(pending) → Threads投稿 → posts テーブル

 ↓ 実行後（run.yml の次ステップ）
collect_insights.py  24〜30日前の posts → Threads Insights API → post_insights テーブル
```

### キーワード更新（update_keywords.py）

```
update_keywords.py
 │
 ├─ Step 1: posts + post_insights から低パフォーマンスキーワード3件を特定
 │          （views データがあれば優先、なければ product スコア × 投稿率）
 │
 ├─ Step 2: 楽天 API（美容/コスメ/日用品/健康を sort=-reviewCount で検索）で売れ筋を取得
 │
 ├─ Step 3: Gemini + Google Search grounding でトレンドキーワード3件をリサーチ
 │
 └─ Step 4: keywords.json を更新 → GitHub Actions が自動コミット
```

### drafts のステータス遷移

```
pending → (メイン投稿成功) → posting_reply → (リプライ投稿成功) → posted
        → (メイン投稿失敗) → failed_main
        → (リプライ投稿失敗) → failed_reply
```

casual 投稿は `pending → posted`（リプライなし）。

---

## Supabase でよく使う操作

```sql
-- pending な下書き確認
SELECT * FROM drafts WHERE status = 'pending' ORDER BY created_at DESC;

-- 最近の投稿一覧
SELECT * FROM posts ORDER BY posted_at DESC LIMIT 20;

-- キーワード別インプレッション平均（update_keywords.py の判定ロジックと同じ）
SELECT
    pr.keyword,
    COUNT(po.id) AS post_count,
    AVG(pi.views) AS avg_views
FROM posts po
JOIN products pr ON po.item_code = pr.item_code
LEFT JOIN post_insights pi ON pi.post_id = po.id
WHERE po.post_type = 'product'
  AND po.posted_at >= NOW() - INTERVAL '90 days'
GROUP BY pr.keyword
ORDER BY avg_views DESC NULLS LAST;

-- failed な下書きを pending に戻す
UPDATE drafts SET status = 'pending' WHERE status LIKE 'failed%';
```
