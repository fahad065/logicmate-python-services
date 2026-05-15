"""
YouTube thumbnail generator.
Live model detection + fallback chain.
Auto-detects available OpenAI image models via API.
"""
import os
import requests
from openai import OpenAI
from core.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

# Known OpenAI image models — newest first
KNOWN_IMAGE_MODELS = [
    "gpt-image-2",
    "gpt-image-1",
    "gpt-image-1-mini",
    "chatgpt-image-latest",
    "dall-e-3",
    "dall-e-2",
]

_available_models_cache: list[str] = []


def get_available_image_models() -> list[str]:
    """Fetch live list of available OpenAI image models."""
    global _available_models_cache
    if _available_models_cache:
        return _available_models_cache
    try:
        models = client.models.list()
        available_ids = {m.id for m in models.data}
        available = [m for m in KNOWN_IMAGE_MODELS if m in available_ids]
        if available:
            _available_models_cache = available
            print(f"  [Thumbnail] Available image models: {available}", flush=True)
            return available
    except Exception as e:
        print(f"  [Thumbnail] Could not fetch live models: {e}", flush=True)
    return KNOWN_IMAGE_MODELS


def _get_image_kwargs(model: str, prompt: str) -> dict:
    """Build API kwargs for each model."""
    base = {"model": model, "prompt": prompt, "n": 1}

    if model in ("gpt-image-2", "gpt-image-1", "gpt-image-1-mini",
                 "gpt-image-1.5", "chatgpt-image-latest"):
        return {**base, "size": "1536x1024", "quality": "high"}

    if model == "dall-e-3":
        return {**base, "size": "1792x1024", "quality": "hd", "style": "vivid"}

    # dall-e-2 fallback
    return {**base, "size": "1024x1024"}


def _get_cost(model: str) -> float:
    cost_map = {
        "gpt-image-2":          0.04,
        "gpt-image-1":          0.04,
        "gpt-image-1-mini":     0.02,
        "chatgpt-image-latest": 0.04,
        "dall-e-3":             0.04,
        "dall-e-2":             0.02,
    }
    return cost_map.get(model, 0.04)


THUMBNAIL_STYLES = {
    "dark":       "cinematic dark background, dramatic spotlight, mysterious hooded figure in shadows, fog atmosphere",
    "psychology": "extreme close-up shocked human face expression, dark dramatic lighting, high contrast",
    "mind":       "split brain illuminated on one side dark on other, psychological concept, dramatic",
    "control":    "puppet strings on human silhouette, dark moody background, dramatic lighting",
    "secret":     "vault door partially open with light inside, dark dramatic atmosphere, mystery",
    "default":    "dramatic dark cinematic background, intense lighting, mysterious atmosphere, high contrast",
}


def _get_thumbnail_prompt(title: str, niche: str) -> str:
    title_lower = title.lower()
    niche_lower = niche.lower()
    style = THUMBNAIL_STYLES["default"]
    for key, prompt in THUMBNAIL_STYLES.items():
        if key in title_lower or key in niche_lower:
            style = prompt
            break
    return (
        f"YouTube thumbnail, {style}. "
        f"Professional YouTube thumbnail style like MrBeast or top psychology channels. "
        f"16:9 widescreen. Extremely eye-catching and clickable. "
        f"Bold dramatic composition. Dark moody color palette with contrast. "
        f"IMPORTANT: No text, no watermarks, no logos, no borders."
    )


def generate_thumbnail(title: str, niche: str, output_path: str) -> float:
    """Generate thumbnail with live model detection + fallback. Returns cost."""
    models = get_available_image_models()
    prompt = _get_thumbnail_prompt(title, niche)

    for model in models:
        try:
            print(f"  [Thumbnail] Trying {model}...", flush=True)
            kwargs = _get_image_kwargs(model, prompt)
            resp = client.images.generate(**kwargs)
            image_url = resp.data[0].url

            if not image_url:
                raise Exception("No image URL returned")

            result = _download_and_add_text(image_url, title, output_path)
            if result and os.path.exists(result) and os.path.getsize(result) > 100:
                print(f"  [Thumbnail] ✓ Generated with {model}", flush=True)
                return _get_cost(model)

        except Exception as e:
            print(f"  [Thumbnail] {model} failed: {e} — trying next...", flush=True)
            if model in _available_models_cache:
                _available_models_cache.remove(model)
            continue

    print(f"  [Thumbnail] All models failed — using placeholder", flush=True)
    _placeholder(title, niche, output_path)
    return 0.0


def _download_and_add_text(image_url: str, title: str, output_path: str) -> str:
    img_resp = requests.get(image_url, timeout=60)
    img_resp.raise_for_status()
    try:
        from PIL import Image
        from io import BytesIO
        img = Image.open(BytesIO(img_resp.content)).convert("RGB")
        img = img.resize((1280, 720), Image.LANCZOS)
        img = _add_bold_text(img, title)
        img.save(output_path, "JPEG", quality=95)
    except ImportError:
        with open(output_path, "wb") as f:
            f.write(img_resp.content)
    return output_path


def _add_bold_text(img, title: str):
    from PIL import Image, ImageDraw
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    for y in range(int(h * 0.55), h):
        alpha = int(200 * (y - h * 0.55) / (h * 0.45))
        draw_overlay.line([(0, y), (w, y)], fill=(0, 0, 0, min(alpha, 200)))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)
    words = title.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        if len(test) > 22 and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    lines = lines[:2]
    font_large = _get_font(72)
    font_small = _get_font(56)
    y = h - (len(lines) * 80) - 30
    for i, line in enumerate(lines):
        font = font_large if i == 0 else font_small
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (w - text_w) // 2
        for dx, dy in [(-3,-3),(3,-3),(-3,3),(3,3),(0,-3),(0,3),(-3,0),(3,0)]:
            draw.text((x+dx, y+dy), line, font=font, fill=(0, 0, 0))
        color = "#FFD700" if i == 0 else "#FFFFFF"
        draw.text((x, y), line, font=font, fill=color)
        y += 85
    return img


def _get_font(size: int):
    from PIL import ImageFont
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _placeholder(title: str, niche: str, output_path: str) -> str:
    import subprocess
    try:
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "color=c=0x0d0d1a:size=1280x720:rate=1",
            "-frames:v", "1", output_path
        ], capture_output=True, check=True)
    except Exception:
        open(output_path, 'wb').close()
    return output_path