"""
YouTube thumbnail generator using Atlas/Seedance image API + PIL text overlay.
Cross-platform: works on macOS and Linux/Railway.
"""
import os
import time
import random
import requests
from io import BytesIO
from core.config import ATLAS_API_KEY

GENERATE_URL = "https://api.atlascloud.ai/api/v1/model/generateImage"
POLL_BASE    = "https://api.atlascloud.ai/api/v1/model/prediction/{id}"

STYLES = [
    {"bg": "dramatic dark cinematic background, deep shadows, professional studio lighting"},
    {"bg": "abstract dark purple gradient, geometric patterns, modern minimalist"},
    {"bg": "mysterious foggy atmosphere, dark moody lighting, cinematic look"},
    {"bg": "bold high contrast black background, dramatic spotlight"},
    {"bg": "dark urban environment, neon lights reflection, noir style"},
    {"bg": "cosmic space background, stars and nebula, epic scale"},
]

NICHE_PROMPTS = {
    "psychology": "psychological thriller atmosphere, human silhouette, dramatic shadows",
    "finance":    "financial charts, money, success visualization, corporate style",
    "fitness":    "athletic achievement, dynamic motion, energy and power",
    "marketing":  "brand identity, professional business, clean corporate design",
    "education":  "knowledge and learning, books and light, academic achievement",
}


def generate_thumbnail(
    title: str,
    niche: str,
    output_path: str,
) -> str:
    """Generate YouTube thumbnail using Atlas image API."""
    style = random.choice(STYLES)

    # Pick niche-specific prompt
    niche_prompt = "cinematic dramatic background"
    for key, prompt in NICHE_PROMPTS.items():
        if key in niche.lower():
            niche_prompt = prompt
            break

    prompt = (
        f"YouTube thumbnail background. {niche_prompt}. "
        f"{style['bg']}. "
        f"16:9 aspect ratio. No text. No watermark. "
        f"Professional, eye-catching, high contrast."
    )

    headers = {
        "Authorization": f"Bearer {ATLAS_API_KEY}",
        "Content-Type": "application/json",
    }

    print(f"  [Thumbnail] Generating background image...")
    resp = requests.post(GENERATE_URL, headers=headers, json={
        "model": "black-forest-labs/FLUX.1-schnell",
        "prompt": prompt,
        "width": 1280,
        "height": 720,
    }, timeout=30)
    resp.raise_for_status()

    prediction_id = resp.json().get("id") or resp.json().get("prediction_id")

    # Poll
    poll_url = POLL_BASE.format(id=prediction_id)
    image_url = None
    for _ in range(30):
        time.sleep(8)
        poll = requests.get(poll_url, headers=headers, timeout=15)
        data = poll.json()
        if data.get("status") == "succeeded":
            output = data.get("output")
            image_url = output[0] if isinstance(output, list) else output
            break
        elif data.get("status") == "failed":
            raise Exception(f"Thumbnail generation failed: {data}")

    if not image_url:
        raise Exception("Thumbnail timed out")

    # Download image
    img_resp = requests.get(image_url, timeout=30)
    img_bytes = BytesIO(img_resp.content)

    # Add text overlay using PIL if available, else save raw
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageEnhance
        img = Image.open(img_bytes).convert("RGB")
        img = _add_text_overlay(img, title)
        img.save(output_path, "JPEG", quality=95)
    except ImportError:
        # PIL not available — save raw image
        with open(output_path, "wb") as f:
            f.write(img_resp.content)
        print("  [Thumbnail] PIL not available, saved raw image")

    print(f"  [Thumbnail] ✓ Saved: {output_path}")
    return output_path


def _add_text_overlay(img, title: str):
    """Add title text overlay to thumbnail image."""
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance

    draw = ImageDraw.Draw(img)
    width, height = img.size

    # Darken bottom area for text readability
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle(
        [0, height // 2, width, height],
        fill=(0, 0, 0, 140)
    )
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Find font
    font = _get_font(60)
    font_small = _get_font(40)

    # Wrap title
    words = title.split()
    lines = []
    current = []
    for word in words:
        current.append(word)
        if len(" ".join(current)) > 25:
            lines.append(" ".join(current[:-1]))
            current = [word]
    if current:
        lines.append(" ".join(current))

    # Draw text
    y = height - (len(lines) * 70) - 40
    for line in lines[:2]:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        # Shadow
        draw.text((x+3, y+3), line, font=font, fill=(0, 0, 0, 200))
        draw.text((x, y), line, font=font, fill="white")
        y += 70

    return img


def _get_font(size: int):
    """Get font — try system fonts, fallback to default."""
    from PIL import ImageFont
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()