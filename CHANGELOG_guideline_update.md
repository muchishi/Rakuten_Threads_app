# ガイドライン対応 変更ログ
> 対象ファイル：`threads_rakuten_affiliate_guideline.md` に基づく改修
> 実施日：2026年6月15日

---

## 変更サマリー

| ファイル | 変更の種類 | 概要 |
|----------|-----------|------|
| `gemini_client.py` | 機能追加 | `system_instruction` 対応 |
| `config.py` | 定数追加 | システムプロンプト・ターゲットマップ |
| `generate_product_post.py` | ロジック追加・プロンプト刷新 | 投稿タイプ自動判定 + 高品質プロンプト |
| `generate_casual_post.py` | プロンプト改善・パーサー修正 | CTA追加 + JSON改行バグ修正 |
| `run.py` | 比率変更 | product 60% → 30% |
| `CLAUDE.md` | ドキュメント更新 | 比率の記述を修正 |

---

## 詳細

---

### 1. `gemini_client.py` — `system_instruction` 対応

**変更前：**
```python
def generate_with_retry(prompt: str, model: str, retry: int = 6, ...) -> str | None:
    res = client.models.generate_content(model=model, contents=prompt)
```

**変更後：**
```python
def generate_with_retry(
    prompt: str,
    model: str,
    system_instruction: str | None = None,  # ← 追加
    retry: int = 6,
    ...
) -> str | None:
    config = types.GenerateContentConfig(system_instruction=system_instruction) if system_instruction else None
    res = client.models.generate_content(model=model, contents=prompt, config=config)
```

**理由：**
ガイドラインの Section 6 に「Geminiへ渡すシステムプロンプト」として詳細なプロンプトが定義されている。
Gemini API の `system_instruction` を使うことで、ユーザープロンプトとは別に「役割・ルール」をモデルに強く意識させられる。

---

### 2. `config.py` — 定数3種を追加

#### 追加① `GEMINI_SYSTEM_PROMPT`
ガイドライン Section 6 の汎用版システムプロンプトをそのまま定数化。

```
・冒頭1行でスクロールを止めるフックを必須化
・商品スペック羅列の禁止
・コメント誘発CTAの必須化
・絵文字3〜5個ルール
・誇大表現（「最安！」「絶対！」）禁止
・#PR表記の必須化
・投稿タイプ別ルール（共感型/保存型/セール型/ランキング型）
```

#### 追加② `CATEGORY_TARGET_MAP`
カテゴリ別のターゲット層を定義。Gemini にターゲットを明示することで文体・訴求の精度が上がる。

```python
CATEGORY_TARGET_MAP = {
    "美容・コスメ":   "美容に関心が高い20〜40代女性",
    "健康・ダイエット": "健康意識の高い30〜50代",
    "食品・飲料":    "日常の食事を楽しみたい全年代",
    "日用品":       "家事を効率化したい主婦・主夫",
    ...
}
```

#### 追加③ `CASUAL_THEMES` 拡充
6テーマ追加（「朝の習慣」「夜のルーティン」「週末の過ごし方」「最近ハマってること」「ちょっとした失敗談」「気づいたこと」）

---

### 3. `generate_product_post.py` — 投稿タイプ判定 + プロンプト刷新

#### 追加：`determine_post_type()`
ガイドラインの「投稿タイプ自動判定ロジック」に基づき新規実装。

| 条件 | 投稿タイプ |
|------|-----------|
| レビュー件数 > 500件 | ランキング型（人気を数字で見せる） |
| 日用品・キッチン系キーワード | 保存型（リストで後で使える設計） |
| それ以外 | 共感型（体験談ストーリー） |

#### 変更：`build_main_prompt()`

**変更前（問題点）：**
- 120文字以内の制限（短すぎてフック+本文+CTA+PR表記が入らない）
- PR表記・URL を禁止していた（リプ欄誘導すら案内できなかった）
- 投稿タイプの概念なし

**変更後：**
```
【商品情報】商品名・価格・レビュー評価・カテゴリ
【投稿タイプ】共感型 / 保存型 / ランキング型
【ターゲット】カテゴリ別ターゲット層
【リンク誘導】↓リプ欄のリンクから
→ 本文のみを出力（セクションラベル不要）
```

システムプロンプトを `GEMINI_SYSTEM_PROMPT` として分離し、`generate_with_fallback()` に渡すように変更。

---

### 4. `generate_casual_post.py` — CTA追加 + JSONパーサー修正

#### 変更①：プロンプトのCTA必須化

**変更前：** コメント誘発なし（10〜120文字の短い日常投稿のみ）

**変更後：**
```
・80〜200文字程度（内容を充実させる）
・必ず末尾にコメントを誘発する問いかけを1つ入れる
  （例：「同じ経験した人いる？」「みんなはどうしてる？」）
・絵文字は意味のある箇所のみ2〜3個
```

**理由：**
ガイドラインに「コメント・返信が最重要アルゴリズムシグナル」と明記。
casual 投稿でもコメントが来ないと拡散しない。

#### 変更②：`_escape_json_newlines()` を追加・パーサー強化

**発見したバグ：** Gemini が JSON 文字列値の中に生の改行（`\n`）を含む不正な JSON を返すことがある。
これにより `json.loads()` が `Invalid control character` エラーを起こしていた。

**修正内容：**
```python
def _escape_json_newlines(s: str) -> str:
    # 文字列値の中の生の改行をエスケープ
    # ダブルクォート・バックスラッシュを正しく追跡しながら変換
```
加えて、Gemini が `<br>` タグを改行代わりに使う場合の変換も追加。

---

### 5. `run.py` — 投稿比率変更

**変更前：**
```python
post_type = "casual" if random.random() < 0.4 else "product"  # casual 40%
```

**変更後：**
```python
post_type = "casual" if random.random() < 0.7 else "product"  # casual 70%
```

**理由（ガイドライン Section 1 より）：**
> アフィリエイト投稿だけを繰り返すと「広告アカウント」認定されアルゴリズムから嫌われる

成功アカウントの分析では **アフィリエイト投稿は 30% 以下** が適切とされている。

---

## テスト実行結果

```
===== ポストタイプ: casual =====

===== casual topic =====
人間関係

===== casual post =====
最近、ちょっとしたことで人間関係の深さを感じることが増えたな。

特に、何でもない日常の会話から、相手の考え方や価値観が垣間見えた時。

共感できる部分があると、すごく嬉しくなる。

逆に、少し考え方の違いを感じても、それを尊重できる関係性って大切だなと改めて思った。

皆さんは、人間関係で「あ、この人とは良い関係を築けそう」って感じる瞬間、どんな時ですか？🤔✨

✅ casual draft保存完了
✅ カジュアル投稿完了
===== 完了 =====
```

→ エラーなし。コメント誘発の問いかけが末尾に生成されていることを確認。

---

## 既知の注意点

- `python run.py` を Windows ターミナルで実行する際、絵文字の出力で文字化けする場合がある。
  環境変数 `PYTHONIOENCODING=utf-8` を設定するか、GitHub Actions 上で実行すれば問題なし。
- `product` タイプ時のプロンプト品質は実際の投稿文を確認して継続的にチューニング推奨。
