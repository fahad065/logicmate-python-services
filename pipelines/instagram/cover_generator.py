"""
Instagram Reels cover/thumbnail generator.
Creates a visually striking cover frame for the Reel.
Uses Seedance for background + PIL for text overlay.
"""
import os
import subprocess
from openai import OpenAI
from core.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


def generate_cover(
    topic: str,
    cover_text: str,
    niche: str,
    color: str,
    output_path: str,
) -> str:
    """
    Generate a Reels cover image using DALL-E 3.
    9:16 aspect ratio, bold text overlay.
    """
    prompt = (
        f"Vertical Instagram Reels cover image, 9:16 aspect ratio. "
        f"Topic: {topic}. Niche: {niche}. "
        f"Dark dramatic background, cinematic lighting, no text, no watermark. "
        f"Professional content creator style. High contrast, eye-catching."
    )

    try:
        print(f"  [Cover] Generating cover image...")
        resp = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1792",  # closest to 9:16
            quality="standard",
            n=1,
        )
        image_url = resp.data[0].url

        # Download image
        import requests
        img_resp = requests.get(image_url, timeout=30)
        img_path = output_path.replace(".jpg", "_raw.jpg")
        with open(img_path, "wb") as f:
            f.write(img_resp.content)

        # Add text overlay using FFmpeg
        _add_text_overlay(img_path, cover_text, output_path)
        if os.path.exists(img_path):
            os.remove(img_path)

        print(f"  [Cover] ✓ Cover saved: {output_path}")
        return output_path

    except Exception as e:
        print(f"  [Cover] Cover generation failed: {e} — using placeholder")
        return _create_placeholder_cover(cover_text, output_path)


def _add_text_overlay(img_path: str, text: str, output_path: str):
    """Add bold text overlay to cover image using FFmpeg."""
    font_file = _find_font()
    text_safe = text.replace("'", "\\'").replace(":", "\\:")

    if font_file:
        drawtext = (
            f"drawtext=fontfile={font_file}:"
            f"text='{text_safe}':"
            f"fontsize=80:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:"
            f"shadowcolor=black:shadowx=3:shadowy=3"
        )
    else:
        drawtext = (
            f"drawtext=text='{text_safe}':"
            f"fontsize=80:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:"
            f"shadowcolor=black:shadowx=3:shadowy=3"
        )

    subprocess.run([
        "ffmpeg", "-y", "-i", img_path,
        "-vf", drawtext,
        output_path
    ], capture_output=True, check=True)


def _create_placeholder_cover(text: str, output_path: str) -> str:
    """Create a simple colored placeholder cover."""
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "color=c=0x7c3aed:size=1080x1920:rate=1",
        "-frames:v", "1",
        output_path
    ], capture_output=True)
    return output_path


def _find_font() -> str | None:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def extract_first_frame(video_path: str, output_path: str) -> str:
    """Extract first frame from video as cover (fallback)."""
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path,
            "-ss", "00:00:01",
            "-vframes", "1",
            output_path
        ], capture_output=True, check=True)
        return output_path
    except Exception:
        return ""