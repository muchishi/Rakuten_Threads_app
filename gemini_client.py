# gemini_client.py
"""
Gemini API の共通ラッパー
generate_with_retry が各ファイルに重複していたのをここに集約
"""
import time
from google import genai
from config import GEMINI_API_KEY, GEMINI_PRIMARY_MODEL, GEMINI_FALLBACK_MODEL

_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def generate_with_retry(
    prompt: str,
    model: str,
    retry: int = 6,
    sleep_sec: float = 7.0,
) -> str | None:
    """
    指定モデルで生成を試みる。失敗時はリトライ。
    全リトライ失敗時は None を返す。
    """
    client = get_client()
    for attempt in range(retry):
        try:
            res = client.models.generate_content(model=model, contents=prompt)
            return res.text
        except Exception as e:
            print(f"[{model}] retry {attempt + 1}/{retry} failed: {e}")
            if attempt < retry - 1:
                time.sleep(sleep_sec)
    return None


def generate_with_fallback(
    prompt: str,
    primary_model: str = GEMINI_PRIMARY_MODEL,
    fallback_model: str = GEMINI_FALLBACK_MODEL,
    primary_retry: int = 6,
    fallback_retry: int = 10,
) -> str:
    """
    プライマリモデルで生成を試み、失敗時はフォールバックモデルに切替。
    両方失敗した場合は Exception を送出。
    """
    text = generate_with_retry(prompt, primary_model, retry=primary_retry)
    if text:
        return text

    print(f"{primary_model} 失敗 → {fallback_model} へフォールバック")
    text = generate_with_retry(prompt, fallback_model, retry=fallback_retry, sleep_sec=10.0)
    if text:
        return text

    raise Exception(f"両モデル（{primary_model} / {fallback_model}）とも生成失敗")
