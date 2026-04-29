"""
Seedance video clip generator — shared across all pipelines.
Supports both 16:9 (YouTube) and 9:16 (Reels/Shorts/TikTok).
"""
import os
import time
import random
import requests
from core.config import ATLAS_API_KEY

GENERATE_URL = "https://api.atlascloud.ai/api/v1/model/generateVideo"
POLL_URL     = "https://api.atlascloud.ai/api/v1/model/prediction/{prediction_id}"

# Scene category prompts — varied per video to avoid repetition
SCENE_CATEGORIES = {
    "cinematic": [
        "cinematic dramatic close-up shot, shallow depth of field, professional lighting",
        "aerial establishing shot, sweeping camera movement, golden hour lighting",
        "slow motion reveal shot, dramatic lighting, high contrast",
    ],
    "urban": [
        "modern city timelapse, busy streets, neon lights reflection",
        "corporate office environment, professional setting, natural light",
        "abstract geometric patterns, clean minimal background",
    ],
    "nature": [
        "dramatic storm clouds forming over ocean, time-lapse",
        "forest path with light rays, mystical atmosphere",
        "mountain landscape, cinematic drone shot",
    ],
    "psychological": [
        "dramatic shadow play on wall, noir lighting, mysterious atmosphere",
        "close-up of human eye reflecting light, intense and focused",
        "silhouette against bright window, contemplative mood",
    ],
    "abstract": [
        "flowing liquid metal, abstract artistic, 4K",
        "particle system exploding, energy burst, dark background",
        "geometric shapes morphing, clean 3D animation style",
    ],
}


def get_scene_prompts(niche: str, count: int, aspect_ratio: str = "16:9") -> list[str]:
    """Generate varied scene prompts based on niche."""
    niche_lower = niche.lower()

    if "psychology" in niche_lower or "behavior" in niche_lower or "dark" in niche_lower:
        primary = "psychological"
        secondary = "cinematic"
    elif "finance" in niche_lower or "business" in niche_lower:
        primary = "urban"
        secondary = "cinematic"
    elif "fitness" in niche_lower or "health" in niche_lower:
        primary = "nature"
        secondary = "cinematic"
    else:
        primary = "cinematic"
        secondary = "abstract"

    suffix = "vertical 9:16 format, mobile optimized" if aspect_ratio == "9:16" else "widescreen 16:9 cinematic"

    prompts = []
    all_prompts = SCENE_CATEGORIES[primary] + SCENE_CATEGORIES[secondary] + SCENE_CATEGORIES["abstract"]
    random.shuffle(all_prompts)

    for i in range(count):
        base = all_prompts[i % len(all_prompts)]
        prompts.append(f"{base}, {suffix}, no text overlay, no watermark")

    return prompts


def generate_clip(
    prompt: str,
    duration: int = 5,
    output_path: str = None,
    aspect_ratio: str = "16:9",
    resolution: str = "720p",
) -> str:
    """Generate a single video clip via Seedance."""
    headers = {
        "Authorization": f"Bearer {ATLAS_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "bytedance/seedance-v1.5-pro/text-to-video",
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "duration": duration,
        "resolution": resolution,
        "camera_fixed": False,
    }

    print(f"  [Seedance] Generating: {prompt[:60]}...")
    resp = requests.post(GENERATE_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()

    resp_json = resp.json()
    prediction_id = (
        resp_json.get("id") or
        resp_json.get("prediction_id") or
        resp_json.get("data", {}).get("id")  # ← Atlas wraps in "data"
    )
    if not prediction_id:
        raise Exception(f"No prediction_id returned: {resp.text}")

    # Poll until complete
    resp_data = resp.json().get("data", {})
    poll_url = resp_data.get("urls", {}).get("get") or POLL_URL.format(prediction_id=prediction_id)
    
    for attempt in range(60):
        time.sleep(15)
        poll = requests.get(poll_url, headers=headers, timeout=20)
        data = poll.json()
        inner = data.get("data", data)
        status = inner.get("status", "")
        if status == "succeeded":
            outputs = inner.get("outputs")
            video_url = outputs[0] if isinstance(outputs, list) and outputs else inner.get("output") or inner.get("video_url")
            if isinstance(video_url, list):
                video_url = video_url[0]
            break
        elif status == "failed":
            raise Exception(f"Seedance generation failed: {data}")

        if attempt % 4 == 0:
            print(f"  [Seedance] Waiting... attempt {attempt+1}/60")
    else:
        raise Exception("Seedance timed out after 15 minutes")

    # Download
    if not output_path:
        output_path = f"/tmp/clip_{prediction_id}.mp4"

    vid_resp = requests.get(video_url, timeout=120)
    vid_resp.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(vid_resp.content)

    print(f"  [Seedance] ✓ Saved to {output_path}")
    return output_path


def generate_clips_batch(
    prompts: list[str],
    output_dir: str,
    aspect_ratio: str = "16:9",
    duration: int = 5,
) -> list[str]:
    """Generate multiple clips sequentially."""
    paths = []
    for i, prompt in enumerate(prompts):
        output_path = os.path.join(output_dir, f"clip_{i:03d}.mp4")
        try:
            path = generate_clip(
                prompt=prompt,
                duration=duration,
                output_path=output_path,
                aspect_ratio=aspect_ratio,
            )
            paths.append(path)
        except Exception as e:
            print(f"  [Seedance] Clip {i} failed: {e} — skipping")
    return paths