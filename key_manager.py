import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEYS = [
    os.getenv("OPENAI_KEY_1"),
    os.getenv("OPENAI_KEY_2"),
    os.getenv("OPENAI_KEY_3"),
    os.getenv("OPENAI_KEY_4"),
    os.getenv("OPENAI_KEY_5"),
]

# None 제거
API_KEYS = [k for k in API_KEYS if k]

if not API_KEYS:
    raise RuntimeError("OPENAI_KEY가 없습니다.")

_current = 0


def get_client():
    print(f"[AI] using key index: {_current}")
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=API_KEYS[_current],
    )


def next_client():
    global _current

    if _current >= len(API_KEYS) - 1:
        return False

    _current += 1
    print(f"[AI] switched to key index: {_current}")

    return True