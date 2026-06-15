import random
import sys

from generate_product_select import fetch_and_upsert_products
from generate_product_post import generate_product_draft
from generate_casual_post import generate_casual_draft
from post_product import post_product
from post_casual import post_casual

# ── 投稿タイプ決定（casual:40% / product:60%）──
post_type = "casual" if random.random() < 0.4 else "product"
# post_type = "casual"  # テスト時はここで固定

print(f"\n===== ポストタイプ: {post_type} =====\n")

try:
    # ── 生成フェーズ ──────────────────────
    if post_type == "product":
        fetch_and_upsert_products()
        generate_product_draft()
    elif post_type == "casual":
        generate_casual_draft()

    # ── 投稿フェーズ ──────────────────────
    if post_type == "product":
        post_product()
    elif post_type == "casual":
        post_casual()

    print("\n===== 完了 =====")

except Exception as e:
    print(f"\n❌ エラー: {e}")
    sys.exit(1)
