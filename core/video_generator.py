"""
Atlas Cloud video clip generator.
Wan 2.6 as primary (cheapest), Seedance 2.0 Fast as fallback.
Supports preferred_model selection from frontend.
"""
import os
import time
import random
import requests
from core.config import ATLAS_API_KEY
from core.model_health import get_available_atlas_video_models

ATLAS_BASE   = "https://api.atlascloud.ai/api/v1"
GENERATE_URL = f"{ATLAS_BASE}/model/generateVideo"
HEADERS      = {"Authorization": f"Bearer {ATLAS_API_KEY}", "Content-Type": "application/json"}

# ── Default model fallback chain — cheapest first ────────────
VIDEO_MODELS = get_available_atlas_video_models()

# Atlas pricing per second per model
ATLAS_PRICE_PER_SEC = {
    "alibaba/wan-2.6/text-to-video":              0.07,   # $0.35 for 5s
    "alibaba/happyhorse-1.0/text-to-video":       0.07,
    "bytedance/seedance-2.0-fast/text-to-video":  0.156,  # $0.78 for 5s
    "bytedance/seedance-2.0/text-to-video":       0.194,  # $0.97 for 5s
    "auto":                                        0.07,   # default cheapest
}

# ── Dark Psychology scene prompts ─────────────────────────────
DARK_PSYCH_SCENES = [
    "extreme close-up of human eye dilating in darkness, intense psychological thriller atmosphere, 4K cinematic",
    "silhouette of figure standing in dimly lit corridor, fog, dramatic shadows, noir film style, widescreen 16:9",
    "dramatic overhead shot of chess pieces on dark board, one piece falling in slow motion, cinematic 4K",
    "close-up of hands shuffling cards under spotlight, dark background, psychological thriller style",
    "person sitting alone in dark room, single light beam from window, dust particles, cinematic depth",
    "slow motion smoke forming human face shape, dark background, mysterious atmosphere, 4K",
    "extreme close-up of mouth whispering, dark dramatic lighting, secrets and deception theme",
    "surveillance camera POV of empty corridor, flickering lights, psychological horror atmosphere",
    "broken mirror reflection showing distorted face, dark psychology theme, cinematic close-up",
    "hourglass with dark sand falling, extreme close-up, dramatic lighting, time pressure",
    "dramatic shot of puppet strings being cut, dark background, freedom from manipulation theme",
    "close-up of brain scan glowing on dark screen, blue light, scientific thriller atmosphere",
    "fast cut montage of city lights at night, time-lapse, noir atmosphere, 4K widescreen",
    "dramatic slow motion of dominoes falling in dark room, single spotlight, chain reaction",
    "extreme close-up of lock being picked, hands in shadow, thriller atmosphere, 4K",
    "dark water ripples in slow motion, single drop creating waves, psychological metaphor",
    "close-up of newspaper headlines spinning, dark dramatic lighting, revelation theme",
    "dramatic low angle shot of skyscrapers at night, power and control theme, 4K",
    "silhouette figure pulling strings above marionette crowd, dark control theme, cinematic",
    "person walking through crowd, everyone frozen in time, Matrix-style effect, cinematic",
]

ABSTRACT_SCENES = [
    "particle system forming human brain shape, dark background, blue energy, 4K cinematic",
    "geometric patterns morphing into maze, dark psychological thriller aesthetic, 4K",
    "DNA helix spinning in darkness, glowing blue, scientific mystery atmosphere",
    "neural network visualization, dark background, synapses firing in slow motion",
    "binary code rain forming human face, dark Matrix-style, cinematic 4K",
]

def get_clip_cost(model: str, duration: int) -> float:
    """Calculate exact clip cost based on model and duration."""
    price_per_sec = ATLAS_PRICE_PER_SEC.get(model, 0.07)
    return round(price_per_sec * duration, 4)


def get_scene_prompts(niche: str, count: int, aspect_ratio: str = "16:9") -> list[str]:
    """Generate varied cinematic dark psychology scene prompts."""
    suffix = "widescreen 16:9, no text overlay, no watermark, no logos, photorealistic"
    all_prompts = DARK_PSYCH_SCENES + ABSTRACT_SCENES
    random.shuffle(all_prompts)
    return [f"{all_prompts[i % len(all_prompts)]}, {suffix}" for i in range(count)]


def _generate_clip_with_model(model: str, prompt: str, duration: int) -> dict:
    """Try to generate clip with specific model."""
    payload = {
        "model": model,
        "prompt": prompt,
        "width": 1920,
        "height": 1080,
        "duration": min(duration, 3),  # cap at 3s to control cost
        "fps": 24,
    }

    resp = requests.post(GENERATE_URL, json=payload, headers=HEADERS, timeout=30)

    if resp.status_code not in (200, 201):
        raise Exception(f"API error {resp.status_code}: {resp.text[:200]}")

    resp_json = resp.json()
    prediction_id = resp_json.get("data", {}).get("id") or resp_json.get("id")

    if not prediction_id:
        raise Exception(f"No prediction_id: {resp.text[:200]}")

    poll_url = f"{ATLAS_BASE}/model/prediction/{prediction_id}"
    return {"prediction_id": prediction_id, "poll_url": poll_url}


def _poll_for_result(poll_url: str, max_attempts: int = 40) -> str:
    """Poll until clip is ready. Returns video URL."""
    for attempt in range(max_attempts):
        time.sleep(15)
        poll = requests.get(poll_url, headers=HEADERS, timeout=20)
        data = poll.json()
        inner = data.get("data", data)
        status = inner.get("status", "")

        if attempt % 2 == 0:
            print(f"  [Seedance] Attempt {attempt+1}/{max_attempts} status: {status}", flush=True)

        if status in ("succeeded", "success", "completed"):
            outputs = inner.get("outputs")
            if isinstance(outputs, list) and outputs:
                return outputs[0]
            video_url = inner.get("output") or inner.get("video_url")
            if video_url:
                return video_url
            raise Exception(f"No video URL in response: {inner}")

        elif status == "failed":
            raise Exception(f"Generation failed: {inner.get('error', 'unknown')}")

    raise Exception(f"Timed out after {max_attempts * 15 / 60:.0f} minutes")


def _build_model_list(preferred_model: str) -> list[str]:
    """Build model list with preferred model first, rest as fallback."""
    if not preferred_model or preferred_model == "auto":
        return VIDEO_MODELS
    # Put preferred first, then rest as fallback
    rest = [m for m in VIDEO_MODELS if m != preferred_model]
    return [preferred_model] + rest


def generate_clip(
    prompt: str,
    output_path: str,
    duration: int = 5,
    preferred_model: str = "auto",
) -> tuple[str, float]:
    """Generate single clip. Returns (output_path, cost)."""
    model_list = _build_model_list(preferred_model)
 
    for model in model_list:
        try:
            print(f"  [Seedance] Generating with {model.split('/')[1]}...", flush=True)
            result = _generate_clip_with_model(model, prompt, duration)
            video_url = _poll_for_result(result["poll_url"])
 
            video_resp = requests.get(video_url, timeout=120)
            video_resp.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(video_resp.content)
 
            cost = get_clip_cost(model, duration)
            print(f"  [Seedance] ✓ Saved to {output_path} (cost: ${cost})", flush=True)
            return output_path, cost
 
        except Exception as e:
            print(f"  [Seedance] {model} failed: {e} — trying next...", flush=True)
            continue
 
    raise Exception(f"All video models failed for prompt: {prompt[:50]}")


def generate_clips_batch(
    prompts: list[str],
    output_dir: str,
    aspect_ratio: str = "16:9",
    duration: int = 5,
    preferred_model: str = "auto",
) -> tuple[list[str], float]:
    """Generate multiple clips. Returns (clips, total_atlas_cost)."""
    os.makedirs(output_dir, exist_ok=True)
    clips = []
    total_cost = 0.0
 
    for i, prompt in enumerate(prompts):
        short_prompt = prompt[:80] + "..." if len(prompt) > 80 else prompt
        print(f"  [Seedance] Clip {i+1}/{len(prompts)}: {short_prompt}", flush=True)
 
        output_path = os.path.join(output_dir, f"clip_{i:03d}.mp4")
 
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            print(f"  [Seedance] ✓ Resuming — clip {i} already exists", flush=True)
            clips.append(output_path)
            total_cost += get_clip_cost(
                preferred_model if preferred_model != "auto" else VIDEO_MODELS[0],
                duration
            )
            continue
 
        try:
            clip, cost = generate_clip(prompt, output_path, duration, preferred_model)
            clips.append(clip)
            total_cost += cost
        except Exception as e:
            print(f"  [Seedance] Clip {i} failed all models: {e} — skipping", flush=True)
 
    print(f"  [Seedance] ✓ {len(clips)} clips, Atlas cost: ${total_cost:.4f}", flush=True)
    return clips, total_cost


def expand_custom_prompt(custom_prompt: str, count: int) -> list[str]:
    """Expand user's custom scene description into multiple cinematic variations."""
    from openai import OpenAI
    from core.config import OPENAI_API_KEY
    import json

    client = OpenAI(api_key=OPENAI_API_KEY)
    suffix = "widescreen 16:9, cinematic, no text overlay, no watermark, photorealistic"

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"""Create {count} cinematic video clip descriptions based on:
            "{custom_prompt}"

            Requirements: distinct camera angles, cinematic, no text, 16:9 widescreen.
            Return ONLY valid JSON: {{"prompts": ["description 1", ...]}}"""}],
            response_format={"type": "json_object"},
            temperature=0.8,
        )
        data = json.loads(resp.choices[0].message.content)
        prompts = data.get("prompts", [])
        while len(prompts) < count:
            prompts.extend(prompts)
        return [f"{p}, {suffix}" for p in prompts[:count]]
    except Exception as e:
        print(f"  [Custom Prompt] Failed: {e} — using default scenes", flush=True)
        return get_scene_prompts(custom_prompt, count)