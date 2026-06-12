import subprocess
import sys
import time
import random

# -------------------------
# ユーティリティ
# -------------------------
def run(cmd):
    result = subprocess.run([sys.executable] + cmd)
    if result.returncode != 0:
        raise Exception(f"❌ 失敗: {cmd}")

# -------------------------
# 投稿タイプ決定
# -------------------------
post_type = "casual" if random.random() < 0.4 else "product"
# post_type = "casual"  # テスト用固定

print(f"\n===== ポストタイプ =====: {post_type}")


# -------------------------
# 生成フェーズ
# -------------------------
def run_generation():
    if post_type == "product":
        run(["generate_product_select.py"])
        run(["generate_product_post.py"])

    elif post_type == "casual":
        run(["generate_casual_post.py"])


# -------------------------
# レビュー
# -------------------------
def run_review():
    run(["review_draft.py"])


# -------------------------
# 投稿フェーズ
# -------------------------
def run_post():
    if post_type == "product":
        run(["post_product.py"])
    elif post_type == "casual":
        run(["post_casual.py"])


# -------------------------
# メイン
# -------------------------
try:
    run_generation()
    run_review()
    run_post()

    print("\n===== 完了 =====")

except Exception as e:
    print(str(e))
    print("❌ BOT停止")
    sys.exit(1)
