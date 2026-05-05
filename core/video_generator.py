"""
Atlas Cloud / Seedance video clip generator.
Generates cinematic dark psychology scene clips.
Model fallback chain for reliability.
"""
import os
import time
import random
import requests
from core.config import ATLAS_API_KEY

ATLAS_BASE    = "https://api.atlascloud.ai/api/v1"
GENERATE_URL  = f"{ATLAS_BASE}/model/prediction"
HEADERS       = {"Authorization": f"Bearer {ATLAS_API_KEY}", "Content-Type": "application/json"}

# ── Text-to-video model fallback chain ───────────────────────
VIDEO_MODELS = [
    "bytedance/seedance-v1-5-pro/text-to-video",   # primary — best quality
    "bytedance/seedance-v1-5-lite/text-to-video",  # fallback 1 — faster
    "wan/wanx2-1-t2v-turbo/text-to-video",         # fallback 2
]

# ── Dark Psychology scene prompts ─────────────────────────────
# Cinematic, action-oriented, no copyright issues
DARK_PSYCH_SCENES = [
    # Psychological tension
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
    # Action and tension
    "fast cut montage of city lights at night, time-lapse, noir atmosphere, 4K widescreen",
    "dramatic slow motion of dominoes falling in dark room, single spotlight, chain reaction",
    "extreme close-up of lock being picked, hands in shadow, thriller atmosphere, 4K",
    "dark water ripples in slow motion, single drop creating waves, psychological metaphor",
    "person walking through crowd, everyone frozen in time, Matrix-style effect, cinematic",
    "close-up of newspaper headlines spinning, dark dramatic lighting, revelation theme",
    "dramatic low angle shot of skyscrapers at night, power and control theme, 4K",
    "silhouette figure pulling strings above marionette crowd, dark control theme, cinematic",
]

ABSTRACT_SCENES = [
    "particle system forming human brain shape, dark background, blue energy, 4K cinematic",
    "geometric patterns morphing into maze, dark psychological thriller aesthetic, 4K",
    "DNA helix spinning in darkness, glowing blue, scientific mystery atmosphere",
    "neural network visualization, dark background, synapses firing in slow motion",
    "binary code rain forming human face, dark Matrix-style, cinematic 4K",
]


def get_scene_prompts(niche: str, count: int, aspect_ratio: str = "16:9") -> list[str]:
    """Generate varied cinematic dark psychology scene prompts."""
    suffix = "widescreen 16:9, no text overlay, no watermark, no logos, photorealistic"

    # Mix dark psychology scenes with abstract
    all_prompts = DARK_PSYCH_SCENES + ABSTRACT_SCENES
    random.shuffle(all_prompts)

    prompts = []
    for i in range(count):
        base = all_prompts[i % len(all_prompts)]
        prompts.append(f"{base}, {suffix}")

    return prompts


def _generate_clip_with_model(model: str, prompt: str, duration: int) -> dict:
    """Try to generate clip with specific model."""
    payload = {
        "model": model,
        "input": {
            "prompt": prompt,
            "duration": duration,
            "aspect_ratio": "16:9",
            "resolution": "1080p",
        }
    }

    resp = requests.post(GENERATE_URL, json=payload, headers=HEADERS, timeout=30)

    if resp.status_code not in (200, 201):
        raise Exception(f"API error {resp.status_code}: {resp.text[:200]}")

    resp_json = resp.json()
    resp_data = resp_json.get("data", resp_json)

    prediction_id = (
        resp_data.get("id") or
        resp_json.get("id") or
        resp_json.get("prediction_id")
    )

    if not prediction_id:
        raise Exception(f"No prediction_id returned: {resp.text[:200]}")

    poll_url = resp_data.get("urls", {}).get("get") or f"{ATLAS_BASE}/model/prediction/{prediction_id}"

    return {"prediction_id": prediction_id, "poll_url": poll_url}


def _poll_for_result(poll_url: str, max_attempts: int = 40) -> str:
    """Poll until clip is ready. Returns video URL."""
    for attempt in range(max_attempts):
        time.sleep(30)
        poll = requests.get(poll_url, headers=HEADERS, timeout=20)
        data = poll.json()
        inner = data.get("data", data)
        status = inner.get("status", "")

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

        if attempt % 2 == 0:
            print(f"  [Seedance] Waiting... attempt {attempt+1}/{max_attempts}", flush=True)

    raise Exception(f"Timed out after {max_attempts * 30 / 60:.0f} minutes")


def generate_clip(prompt: str, output_path: str, duration: int = 5) -> str:
    """Generate single clip with model fallback chain."""

    for model in VIDEO_MODELS:
        try:
            print(f"  [Seedance] Generating with {model.split('/')[1]}...", flush=True)
            result = _generate_clip_with_model(model, prompt, duration)
            video_url = _poll_for_result(result["poll_url"])

            # Download clip
            video_resp = requests.get(video_url, timeout=120)
            video_resp.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(video_resp.content)

            print(f"  [Seedance] ✓ Saved to {output_path}", flush=True)
            return output_path

        except Exception as e:
            print(f"  [Seedance] {model} failed: {e} — trying next model...", flush=True)
            continue

    raise Exception(f"All video models failed for prompt: {prompt[:50]}")


def generate_clips_batch(
    prompts: list[str],
    output_dir: str,
    aspect_ratio: str = "16:9",
    duration: int = 5,
) -> list[str]:
    """Generate multiple clips sequentially with fallback."""
    os.makedirs(output_dir, exist_ok=True)
    clips = []

    for i, prompt in enumerate(prompts):
        short_prompt = prompt[:80] + "..." if len(prompt) > 80 else prompt
        print(f"  [Seedance] Generating: {short_prompt}", flush=True)

        output_path = os.path.join(output_dir, f"clip_{i:03d}.mp4")

        # Skip if already exists (resume support)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            print(f"  [Seedance] ✓ Resuming — clip {i} already exists", flush=True)
            clips.append(output_path)
            continue

        try:
            clip = generate_clip(prompt, output_path, duration)
            clips.append(clip)
        except Exception as e:
            print(f"  [Seedance] Clip {i} failed all models: {e} — skipping", flush=True)

    return clips

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
            messages=[{
                "role": "user",
                "content": f"""Create {count} cinematic video clip descriptions based on this concept:
                "{custom_prompt}"
                
                Requirements:
                - Each should be a distinct camera angle or moment from the concept
                - Cinematic, detailed, visual
                - No text overlays, no watermarks
                - 16:9 widescreen
                
                Return ONLY valid JSON: {{"prompts": ["description 1", "description 2", ...]}}"""
            }],
            response_format={"type": "json_object"},
            temperature=0.8,
        )
        data = json.loads(resp.choices[0].message.content)
        prompts = data.get("prompts", [])
        # Ensure we have enough prompts
        while len(prompts) < count:
            prompts.extend(prompts)
        return [f"{p}, {suffix}" for p in prompts[:count]]
    except Exception as e:
        print(f"  [Custom Prompt] Failed to expand: {e} — using default scenes", flush=True)
        return get_scene_prompts(custom_prompt, count)