import random
import sys

from generate_product_post import generate_product_draft
from generate_casual_post import generate_casual_draft
from post_product import post_product
from post_casual import post_casual

# ── 投稿タイプ決定（casual:70% / product:30%）──
# ガイドライン準拠：アフィリエイト投稿は全体の30%以下
post_type = "casual" if random.random() < 0.5 else "product"
# post_type = "casual"  # テスト時はここで固定

print(f"\n===== ポストタイプ: {post_type} =====\n")

try:
    # ── 生成フェーズ ──────────────────────
    if post_type == "product":
        try:
            generate_product_draft()
        except Exception as e:
            if "未投稿商品がありません" in str(e):
                print("⚠️ 未投稿商品なし → casualに切り替え")
                post_type = "casual"
            else:
                raise

    if post_type == "casual":
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
