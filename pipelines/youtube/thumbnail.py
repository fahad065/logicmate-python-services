"""
YouTube thumbnail generator.
Fallback chain: DALL-E 3 → DALL-E 2 → FFmpeg placeholder
Creates eye-catching dark psychology thumbnails with bold text overlay.
"""
import os
import requests
from openai import OpenAI
from core.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

# Dark psychology thumbnail prompts — MrBeast/top creator style
THUMBNAIL_STYLES = {
    "dark":       "cinematic dark background, dramatic spotlight, mysterious hooded figure in shadows, fog atmosphere",
    "psychology": "extreme close-up shocked human face expression, dark dramatic lighting, high contrast",
    "mind":       "split brain illuminated on one side dark on other, psychological concept, dramatic",
    "control":    "puppet strings on human silhouette, dark moody background, dramatic lighting",
    "secret":     "vault door partially open with light inside, dark dramatic atmosphere, mystery",
    "default":    "dramatic dark cinematic background, intense lighting, mysterious atmosphere, high contrast",
}


def generate_thumbnail(title: str, niche: str, output_path: str) -> str:
    """Generate eye-catching thumbnail with fallback chain."""
    methods = [
        ("DALL-E 3", _dalle3),
        ("DALL-E 2", _dalle2),
        ("Placeholder", _placeholder),
    ]

    for name, method in methods:
        try:
            print(f"  [Thumbnail] Trying {name}...", flush=True)
            result = method(title, niche, output_path)
            if result and os.path.exists(result) and os.path.getsize(result) > 100:
                print(f"  [Thumbnail] ✓ Generated with {name}", flush=True)
                return result
        except Exception as e:
            print(f"  [Thumbnail] {name} failed: {e} — trying next...", flush=True)

    return output_path


def _get_thumbnail_prompt(title: str, niche: str) -> str:
    """Get niche-specific dramatic thumbnail prompt."""
    title_lower = title.lower()
    niche_lower = niche.lower()

    # Pick style based on keywords
    style = THUMBNAIL_STYLES["default"]
    for key, prompt in THUMBNAIL_STYLES.items():
        if key in title_lower or key in niche_lower:
            style = prompt
            break

    return (
        f"YouTube thumbnail, {style}. "
        f"Professional YouTube thumbnail style like MrBeast or top psychology channels. "
        f"16:9 widescreen 1280x720. Extremely eye-catching and clickable. "
        f"Bold dramatic composition. Dark moody color palette with contrast. "
        f"IMPORTANT: No text, no watermarks, no logos, no borders."
    )


def _dalle3(title: str, niche: str, output_path: str) -> str:
    resp = client.images.generate(
        model="dall-e-3",
        prompt=_get_thumbnail_prompt(title, niche),
        size="1792x1024",
        quality="hd",
        style="vivid",
        n=1,
    )
    return _download_and_add_text(resp.data[0].url, title, output_path)


def _dalle2(title: str, niche: str, output_path: str) -> str:
    # DALL-E 2 shorter prompt
    prompt = (
        f"YouTube thumbnail dark psychology, dramatic cinematic, "
        f"mysterious atmosphere, high contrast, no text"
    )
    resp = client.images.generate(
        model="dall-e-2",
        prompt=prompt[:1000],
        size="1024x1024",
        n=1,
    )
    return _download_and_add_text(resp.data[0].url, title, output_path)


def _download_and_add_text(image_url: str, title: str, output_path: str) -> str:
    """Download image, resize to 1280x720 and add bold text overlay."""
    img_resp = requests.get(image_url, timeout=30)
    img_resp.raise_for_status()

    try:
        from PIL import Image, ImageDraw, ImageFilter
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
    """Add bold yellow/white text overlay — YouTube thumbnail style."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

    w, h = img.size

    # Dark gradient overlay at bottom
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    # Gradient from transparent to black at bottom 40%
    for y in range(int(h * 0.55), h):
        alpha = int(200 * (y - h * 0.55) / (h * 0.45))
        draw_overlay.line([(0, y), (w, y)], fill=(0, 0, 0, min(alpha, 200)))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    # Wrap title into 2 lines max
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

    # Large bold font
    font_large = _get_font(72)
    font_small = _get_font(56)

    y = h - (len(lines) * 80) - 30

    for i, line in enumerate(lines):
        font = font_large if i == 0 else font_small
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (w - text_w) // 2

        # Bold shadow (multiple offsets for thick shadow)
        for dx, dy in [(-3,-3),(3,-3),(-3,3),(3,3),(0,-3),(0,3),(-3,0),(3,0)]:
            draw.text((x+dx, y+dy), line, font=font, fill=(0, 0, 0))

        # Yellow text (YouTube thumbnail style)
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
    """Dark gradient placeholder — always works."""
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