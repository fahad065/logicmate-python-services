"""
core/model_health.py
====================
Live model health checker for all AI providers.
Cache results for 1 hour to avoid excessive API calls.
Always returns fallback values on any error — never crashes.
"""
import time
import requests
import os
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ATLAS_API_KEY  = os.getenv("ATLAS_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

_model_cache: dict[str, tuple[bool, float]] = {}
CACHE_TTL = 3600

FALLBACK_VIDEO_MODELS = [
    "alibaba/wan-2.6/text-to-video",
    "bytedance/seedance-2.0-fast/text-to-video",
    "bytedance/seedance-2.0/text-to-video",
]


def is_model_available(model_id: str, provider: str = "openai") -> bool:
    now = time.time()
    if model_id in _model_cache:
        available, ts = _model_cache[model_id]
        if now - ts < CACHE_TTL:
            return available
    available = _check_model(model_id, provider)
    _model_cache[model_id] = (available, now)
    return available


def _check_model(model_id: str, provider: str) -> bool:
    try:
        if provider == "openai" and client:
            models = client.models.list()
            available_ids = {m.id for m in (models.data or [])}
            return model_id in available_ids
        elif provider == "atlas" and ATLAS_API_KEY:
            resp = requests.get(
                "https://api.atlascloud.ai/api/v1/models",
                headers={"Authorization": f"Bearer {ATLAS_API_KEY}"},
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                models_list = data.get("data") or data.get("models") or []
                available_ids = {m.get("model") for m in models_list if m and isinstance(m, dict)}
                return model_id in available_ids
    except Exception as e:
        print(f"  [ModelHealth] Check failed for {model_id}: {e}", flush=True)
    return False


def get_best_openai_chat_model() -> str:
    for model in ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]:
        try:
            if is_model_available(model, "openai"):
                return model
        except Exception:
            continue
    return "gpt-4o-mini"


def get_best_openai_tts_model() -> str:
    for model in ["tts-1-hd", "tts-1"]:
        try:
            if is_model_available(model, "openai"):
                return model
        except Exception:
            continue
    return "tts-1-hd"


def get_best_openai_image_model() -> str:
    for model in ["gpt-image-2", "gpt-image-1", "gpt-image-1-mini", "dall-e-3"]:
        try:
            if is_model_available(model, "openai"):
                return model
        except Exception:
            continue
    return None


def get_available_atlas_video_models() -> list[str]:
    """Always returns a valid list — never raises."""
    if not ATLAS_API_KEY:
        print("  [ModelHealth] No ATLAS_API_KEY — using fallback models", flush=True)
        return FALLBACK_VIDEO_MODELS
    try:
        resp = requests.get(
            "https://api.atlascloud.ai/api/v1/models",
            headers={"Authorization": f"Bearer {ATLAS_API_KEY}"},
            timeout=8,
        )
        if resp.status_code != 200:
            return FALLBACK_VIDEO_MODELS

        data = resp.json()
        all_models = data.get("data") or data.get("models") or []

        if not all_models or not isinstance(all_models, list):
            return FALLBACK_VIDEO_MODELS

        video_models = []
        for m in all_models:
            if not m or not isinstance(m, dict):
                continue
            categories = m.get("categories") or []
            if not isinstance(categories, list):
                continue
            try:
                if (
                    m.get("type") == "Video"
                    and m.get("display_console") is True
                    and "TEXT-TO-VIDEO" in categories
                    and m.get("price", {}).get("actual", {}).get("base_price")
                    and m.get("model")
                ):
                    video_models.append(m)
            except Exception:
                continue

        if not video_models:
            return FALLBACK_VIDEO_MODELS

        video_models.sort(key=lambda m: float(m["price"]["actual"]["base_price"]))
        result = [m["model"] for m in video_models[:8]]
        return result if result else FALLBACK_VIDEO_MODELS

    except Exception as e:
        print(f"  [ModelHealth] Atlas fetch failed: {e} — using fallback", flush=True)
        return FALLBACK_VIDEO_MODELS