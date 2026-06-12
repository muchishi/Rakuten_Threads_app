import sqlite3

conn = sqlite3.connect("rakuten.db")
cursor = conn.cursor()

# 承認待ち投稿を取得
cursor.execute("""
SELECT
    id,
    item_code,
    main_post
FROM drafts
WHERE status != 'posted' AND status != 'approved'
ORDER BY id DESC
""")

drafts = cursor.fetchall()

if not drafts:
    print("承認待ちの投稿はありません")
    conn.close()
    exit()

print("\n=== 承認待ち投稿 ===\n")

for draft in drafts:
    draft_id = draft[0]
    item_code = draft[1]
    main_post = draft[2]

    print(f"ID: {draft_id}")
    print(f"商品コード: {item_code}")
    print(main_post)
    print("-" * 50)

# 承認するID入力
draft_id = input("\n承認するIDを入力: ")
if not draft_id:
    print("IDが未入力です")
    conn.close()
    exit()
else:
    draft_id = int(draft_id)

# ID存在チェック（軽く安全対策）
cursor.execute(
    """
SELECT id FROM drafts WHERE id = ?
""",
    (draft_id,),
)

exists = cursor.fetchone()

if not exists:
    print("指定IDが存在しません")
    conn.close()
    exit()

# ステータス更新
cursor.execute(
    """
UPDATE drafts
SET status = 'approved'
WHERE id = ?
""",
    (draft_id,),
)

conn.commit()
conn.close()

print(f"\nDraft {draft_id} を承認しました")
