# COMMON_MISTAKES.md
> 実際のコードを読んで特定したバグ・落とし穴の記録

---

## 1. generate_casual_post.py — プロンプトが f-string になっていなかった

**症状：** `used_topics` が展開されず、Gemini に「なし」と伝わる  
**場所：** `build_casual_prompt()`

```python
# ❌ Before
prompt = """
最近使用したテーマ（避けてください）: {used_topics_str}
...
"""

# ✅ After
prompt = f"""
最近使用したテーマ（避けてください）: {used_topics_str}
...
"""
```

---

## 2. generate_casual_post.py — Gemini が JSON 内に生の改行を含むレスポンスを返す

**症状：** `json.loads()` が `Invalid control character` エラーで失敗  
**原因：** Gemini が `"post"` 値の中に `\n`（エスケープされていないリテラル改行）を含む不正な JSON を返すことがある  
**場所：** `parse_casual_response()`

```python
# ❌ Before（生の改行に対応していない）
data = json.loads(cleaned)

# ✅ After（_escape_json_newlines で前処理してから parse）
cleaned = _escape_json_newlines(cleaned)
data = json.loads(cleaned)
```

`_escape_json_newlines()` は文字ごとにダブルクォートのネストを追跡し、文字列値内の `\n` / `\r` のみをエスケープシーケンスに変換する。バックスラッシュエスケープ（`\"`など）も正しく処理している。

また Gemini が `<br>` タグを改行代わりに使うケースもあるため、parse 後に `.replace("<br>", "\n")` も行っている。

---

## 3. generate_product_select.py — upsert に on_conflict 指定がなかった

**症状：** 同じ `item_code` を再 upsert すると主キー（`id`）で重複判定されて UniqueConstraint エラー  
**場所：** `fetch_and_upsert_products()` 内の upsert 呼び出し

```python
# ❌ Before
supabase.table("products").upsert({...}).execute()

# ✅ After
supabase.table("products").upsert({...}, on_conflict="item_code").execute()
```

`drafts` テーブルへの upsert も同様に `on_conflict="item_code"` が必要。

---

## 4. get_category() — キーワード判定漏れ

**症状：** `クレンジング` / `ダイエット` / `サプリメント` が「その他」に分類されていた  
**場所：** `generate_product_post.py` の `CATEGORY_RULES`（現在は `config.py` に移動済み）

```python
# ❌ Before（ルールに含まれていなかった）
CATEGORY_RULES = [
    (["化粧", "コスメ", ...], "美容・コスメ"),
    (["プロテイン"], "健康・ダイエット"),
    ...
]

# ✅ After
CATEGORY_RULES = [
    (["化粧", "コスメ", ..., "クレンジング"], "美容・コスメ"),  # クレンジング追加
    (["ダイエット", "サプリメント", "プロテイン"], "健康・ダイエット"),  # 追加
    ...
]
```

`get_category()` は `keyword.lower()` でマッチングする。**キーワードリストは小文字で登録しなくてもよい**（比較対象を lower() するため）。

---

## 5. Supabase — NULL フィルタの書き方

**症状：** `item_code` が NULL の行を除外するフィルタが効かない  
**原因：** Supabase（PostgREST）では SQL の `IS NOT NULL` を `.not_.is_("col", "null")` で表現する

```python
# ❌ 動かない
.neq("item_code", None)
.filter("item_code", "neq", None)

# ✅ 正しい
.not_.is_("item_code", "null")
```

---

## 6. gemini_client.py — generate_with_retry が各ファイルに重複していた

**症状：** 片方を修正してももう片方が古いまま残る  
**対応：** `gemini_client.py` に集約し、各ファイルから `from gemini_client import generate_with_fallback` でインポートする

**現在の呼び出し規約：**

```python
# system_instruction なし（カジュアル投稿など）
text = generate_with_fallback(prompt)

# system_instruction あり（商品投稿）
text = generate_with_fallback(prompt, system_instruction=GEMINI_SYSTEM_PROMPT)
```

---

## 7. Windows ターミナル — 絵文字で UnicodeEncodeError

**症状：** `print()` が `UnicodeEncodeError: 'cp932' codec can't encode character` で落ちる  
**原因：** Windows PowerShell のデフォルトエンコーディングが cp932（Shift-JIS）

```powershell
# ❌ そのまま実行
python run.py

# ✅ UTF-8 を明示
$env:PYTHONIOENCODING="utf-8"; python run.py
```

GitHub Actions（Ubuntu）では発生しない。

---

## 8. posts テーブル — マイグレーションデータを Insights API に送らない

**症状：** `migrated_` プレフィックスの media_id を Threads API に送ると 400 エラー  
**場所：** `collect_insights.py`

```python
# ✅ マイグレーションデータをスキップ
target_posts = [p for p in target_posts if not p["media_id"].startswith("migrated_")]
```

旧 `posted_products` から移行したデータは `media_id = 'migrated_' || item_code` という値で保存されている。

---

## 9. Gemini JSON レスポンス — コードブロックが含まれる場合

**症状：** Gemini がコードブロック（`` ```json `` ）付きで返すと `json.loads()` が失敗  
**対応：** `parse_casual_response()` と `research_new_keywords()` でコードブロック除去を先に行う

```python
cleaned = text.strip()
if cleaned.startswith("```"):
    cleaned = cleaned.split("```")[1]
    if cleaned.startswith("json"):
        cleaned = cleaned[4:]
    cleaned = cleaned.strip()
```

また JSON 以外のテキストが前後に混入するケースでは `{` / `}` の位置を探して切り出す：

```python
start = cleaned.find("{")
end = cleaned.rfind("}") + 1
if start != -1 and end > start:
    cleaned = cleaned[start:end]
```

---

## 10. drafts テーブル — casual 投稿は insert、product 投稿は upsert

```python
# product: item_code UNIQUE があるため upsert（同一商品の再生成に対応）
supabase.table("drafts").upsert({...}, on_conflict="item_code").execute()

# casual: item_code が NULL のため insert（UNIQUE 制約は NULL を除外するため複数行可）
supabase.table("drafts").insert({...}).execute()
```

casual に upsert を使うと `on_conflict` の対象がなく動作が不定になるので注意。
