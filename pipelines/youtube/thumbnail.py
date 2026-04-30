"""
YouTube thumbnail generator.
Fallback chain: DALL-E 3 → DALL-E 2 → FFmpeg placeholder
"""
import os
import requests
from openai import OpenAI
from core.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

NICHE_PROMPTS = {
    "psychology": "dark psychological atmosphere, human silhouette, dramatic noir shadows",
    "finance":    "financial success, money and charts, corporate professional dark theme",
    "fitness":    "athletic achievement, dynamic energy, powerful motion, dark background",
    "marketing":  "bold brand identity, modern design, professional dark corporate",
    "education":  "knowledge and wisdom, books and golden light rays, academic",
    "real estate":"luxury property, architectural photography, golden hour dramatic",
    "dark":       "mysterious dark atmosphere, shadows, psychological tension, cinematic",
}


def generate_thumbnail(title: str, niche: str, output_path: str) -> str:
    """Generate thumbnail with fallback chain."""

    # Try each method in order
    methods = [
        ("DALL-E 3", _dalle3),
        ("DALL-E 2", _dalle2),
        ("Placeholder", _placeholder),
    ]

    for name, method in methods:
        try:
            print(f"  [Thumbnail] Trying {name}...", flush=True)
            result = method(title, niche, output_path)
            if result and os.path.exists(result):
                print(f"  [Thumbnail] ✓ Generated with {name}", flush=True)
                return result
        except Exception as e:
            print(f"  [Thumbnail] {name} failed: {e} — trying next...", flush=True)

    # Should never reach here since placeholder always works
    return output_path


def _get_niche_prompt(niche: str) -> str:
    niche_lower = niche.lower()
    for key, prompt in NICHE_PROMPTS.items():
        if key in niche_lower:
            return prompt
    return "cinematic dramatic dark background, professional high contrast"


def _dalle3(title: str, niche: str, output_path: str) -> str:
    prompt = (
        f"YouTube thumbnail background. {_get_niche_prompt(niche)}. "
        f"16:9 widescreen, eye-catching, no text, no watermarks, no logos. "
        f"High contrast cinematic photography style."
    )
    resp = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1792x1024",
        quality="standard",
        n=1,
    )
    return _download_and_process(resp.data[0].url, title, output_path)


def _dalle2(title: str, niche: str, output_path: str) -> str:
    prompt = (
        f"YouTube thumbnail background, {_get_niche_prompt(niche)}, "
        f"dramatic lighting, no text, professional photography"
    )
    resp = client.images.generate(
        model="dall-e-2",
        prompt=prompt[:1000],
        size="1024x1024",
        n=1,
    )
    return _download_and_process(resp.data[0].url, title, output_path)


def _download_and_process(image_url: str, title: str, output_path: str) -> str:
    """Download image and add text overlay."""
    img_resp = requests.get(image_url, timeout=30)
    img_resp.raise_for_status()

    try:
        from PIL import Image, ImageDraw
        from io import BytesIO

        img = Image.open(BytesIO(img_resp.content)).convert("RGB")
        img = img.resize((1280, 720))
        img = _add_text_overlay(img, title)
        img.save(output_path, "JPEG", quality=95)
    except ImportError:
        with open(output_path, "wb") as f:
            f.write(img_resp.content)

    return output_path


def _add_text_overlay(img, title: str):
    """Add title text to bottom of thumbnail."""
    from PIL import Image, ImageDraw

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    w, h = img.size
    draw_overlay.rectangle([0, h // 2, w, h], fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    font = _get_font(52)

    # Wrap title
    words = title.split()
    lines, current = [], []
    for word in words:
        current.append(word)
        if len(" ".join(current)) > 28:
            lines.append(" ".join(current[:-1]))
            current = [word]
    if current:
        lines.append(" ".join(current))
    lines = lines[:2]

    y = h - (len(lines) * 68) - 24
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (w - (bbox[2] - bbox[0])) // 2
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill="white")
        y += 68

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


def _placeholder(title: str, niche: str, output_path: str) -> str:
    """Create colored placeholder — always works."""
    import subprocess
    try:
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "color=c=0x1a1a2e:size=1280x720:rate=1",
            "-frames:v", "1", output_path
        ], capture_output=True, check=True)
    except Exception:
        open(output_path, 'wb').close()
    return output_path