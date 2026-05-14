"""
core/model_health.py
====================
Live model health checker for all AI providers.
Checks OpenAI, Atlas API for available models.
Used by all pipelines to pick best available model.
Cache results for 1 hour to avoid excessive API calls.
"""
import time
import requests
import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
ATLAS_API_KEY = os.getenv("ATLAS_API_KEY", "")

# Cache: {model_id: (is_available, timestamp)}
_model_cache: dict[str, tuple[bool, float]] = {}
CACHE_TTL = 3600  # 1 hour


def is_model_available(model_id: str, provider: str = "openai") -> bool:
    """Check if a model is currently available. Uses 1hr cache."""
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
        if provider == "openai":
            models = client.models.list()
            available_ids = {m.id for m in models.data}
            return model_id in available_ids
        elif provider == "atlas":
            resp = requests.get(
                "https://api.atlascloud.ai/api/v1/models",
                headers={"Authorization": f"Bearer {ATLAS_API_KEY}"},
                timeout=8,
            )
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                available_ids = {m.get("model") for m in models}
                return model_id in available_ids
    except Exception as e:
        print(f"  [ModelHealth] Check failed for {model_id}: {e}", flush=True)
    return False


def get_best_openai_chat_model() -> str:
    """Get best available OpenAI chat model."""
    candidates = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
    for model in candidates:
        if is_model_available(model, "openai"):
            return model
    return "gpt-4o-mini"  # last resort


def get_best_openai_tts_model() -> str:
    """Get best available OpenAI TTS model."""
    candidates = ["tts-1-hd", "tts-1"]
    for model in candidates:
        if is_model_available(model, "openai"):
            return model
    return "tts-1"


def get_best_openai_image_model() -> str:
    """Get best available OpenAI image model."""
    candidates = ["gpt-image-1", "gpt-image-1-mini", "dall-e-3", "dall-e-2"]
    for model in candidates:
        if is_model_available(model, "openai"):
            return model
    return None  # use placeholder


def get_available_atlas_video_models() -> list[str]:
    """Get available Atlas video models sorted by price."""
    try:
        resp = requests.get(
            "https://api.atlascloud.ai/api/v1/models",
            headers={"Authorization": f"Bearer {ATLAS_API_KEY}"},
            timeout=8,
        )
        if resp.status_code == 200:
            all_models = resp.json().get("data", [])
            video_models = [
                m for m in all_models
                if m.get("type") == "Video"
                and m.get("display_console") is True
                and m.get("price", {}).get("actual", {}).get("base_price")
                and any(c in m.get("categories", []) for c in ["TEXT-TO-VIDEO"])
            ]
            # Sort by price
            video_models.sort(key=lambda m: float(m["price"]["actual"]["base_price"]))
            return [m["model"] for m in video_models[:8]]
    except Exception as e:
        print(f"  [ModelHealth] Atlas models fetch failed: {e}", flush=True)

    # Fallback
    return [
        "alibaba/wan-2.6/text-to-video",
        "bytedance/seedance-2.0-fast/text-to-video",
        "bytedance/seedance-2.0/text-to-video",
    ]


def log_model_status():
    """Print current model availability — useful for debugging."""
    print("\n[ModelHealth] Checking all models...", flush=True)
    print(f"  Chat:  {get_best_openai_chat_model()}", flush=True)
    print(f"  TTS:   {get_best_openai_tts_model()}", flush=True)
    print(f"  Image: {get_best_openai_image_model()}", flush=True)
    atlas = get_available_atlas_video_models()
    print(f"  Video: {atlas[:3]}", flush=True)
    print("[ModelHealth] ✓ Done\n", flush=True)