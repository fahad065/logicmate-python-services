"""
YouTube thumbnail generator using DALL-E 3 + PIL text overlay.
Switched from Atlas to DALL-E 3 for reliability.
"""
import os
import requests
from openai import OpenAI
from core.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

NICHE_PROMPTS = {
    "psychology": "dark psychological atmosphere, human silhouette, dramatic shadows, noir style",
    "finance":    "financial success visualization, money and charts, corporate professional",
    "fitness":    "athletic achievement, dynamic energy, powerful motion blur",
    "marketing":  "bold brand identity, clean professional design, modern corporate",
    "education":  "knowledge and wisdom, books and light rays, academic achievement",
}


def generate_thumbnail(
    title: str,
    niche: str,
    output_path: str,
) -> str:
    """Generate YouTube thumbnail using DALL-E 3."""

    # Pick niche-specific prompt
    niche_prompt = "cinematic dramatic background, dark moody atmosphere"
    for key, prompt in NICHE_PROMPTS.items():
        if key in niche.lower():
            niche_prompt = prompt
            break

    prompt = (
        f"YouTube thumbnail background image. {niche_prompt}. "
        f"16:9 aspect ratio, high contrast, eye-catching, professional. "
        f"No text, no watermarks, no logos. Dark dramatic lighting."
    )

    print(f"  [Thumbnail] Generating with DALL-E 3...")

    try:
        resp = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",  # closest to 16:9
            quality="standard",
            n=1,
        )
        image_url = resp.data[0].url

        # Download image
        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()

        # Try to add text overlay with PIL
        try:
            from PIL import Image, ImageDraw
            from io import BytesIO

            img = Image.open(BytesIO(img_resp.content)).convert("RGB")
            img = img.resize((1280, 720))
            img = _add_text_overlay(img, title)
            img.save(output_path, "JPEG", quality=95)
        except ImportError:
            # PIL not available — save raw
            with open(output_path, "wb") as f:
                f.write(img_resp.content)

        print(f"  [Thumbnail] ✓ Saved: {output_path}")
        return output_path

    except Exception as e:
        print(f"  [Thumbnail] DALL-E failed: {e} — creating placeholder")
        return _create_placeholder(output_path)


def _add_text_overlay(img, title: str):
    """Add title text to thumbnail."""
    from PIL import Image, ImageDraw, ImageFont

    # Darken bottom half
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    w, h = img.size
    draw_overlay.rectangle([0, h // 2, w, h], fill=(0, 0, 0, 140))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    # Get font
    font = _get_font(52)

    # Wrap title to 2 lines
    words = title.split()
    lines = []
    current = []
    for word in words:
        current.append(word)
        if len(" ".join(current)) > 28:
            lines.append(" ".join(current[:-1]))
            current = [word]
    if current:
        lines.append(" ".join(current))
    lines = lines[:2]

    y = h - (len(lines) * 65) - 30
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (w - text_w) // 2
        # Shadow
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill="white")
        y += 65

    return img


def _get_font(size: int):
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


def _create_placeholder(output_path: str) -> str:
    """Create solid color placeholder thumbnail."""
    try:
        import subprocess
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "color=c=0x1a1a2e:size=1280x720:rate=1",
            "-frames:v", "1", output_path
        ], capture_output=True, check=True)
    except Exception:
        # Last resort — write empty file
        open(output_path, 'wb').close()
    return output_path