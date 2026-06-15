# CLAUDE.md

## 言語
常に日本語で回答してください。

---

## プロジェクト概要

Threads（スレッズ）に自動投稿し、楽天アフィリエイトで収益化するPythonボット。
GitHub Actionsで3時間ごとに自動実行される。

**目標：商品紹介ではなく、インプレッション・コメント・保存を最大化する投稿を自動生成すること。**

---

## スタック

| 項目 | 内容 |
|------|------|
| 言語 | Python 3.11 |
| DB | Supabase（PostgreSQL） |
| AI生成 | Google Gemini API（`google-genai` パッケージ） |
| 投稿先 | Threads Graph API（`graph.threads.net/v1.0`） |
| 商品取得 | 楽天市場 API（`openapi.rakuten.co.jp`） |
| 実行環境 | GitHub Actions（3時間ごと） / ローカル（.envで実行） |

---

## 詳細ドキュメント

作業内容に応じて必要なファイルだけ参照すること。

| 作業 | 参照先 |
|------|--------|
| ファイル役割・テーブル構成・環境変数 | `.claude/ARCHITECTURE_MAP.md` |
| バグが起きやすい箇所・過去修正履歴 | `.claude/COMMON_MISTAKES.md` |
| コマンド・GitHub Actions・投稿フロー | `.claude/QUICK_START.md` |
| 投稿設計方針・プロンプトルール | `.claude/POST_GUIDELINES.md` |

---

## 触らないファイル

| ファイル | 理由 |
|----------|------|
| `.venv/` | 仮想環境（変更不要） |
| `keywords.json` | `update_keywords.py` が自動上書きする |
| `requirements.txt` | パッケージ追加時のみ編集 |
| `.github/workflows/` | 変更時はワークフローの動作を必ず確認すること |
