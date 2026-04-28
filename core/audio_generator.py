"""
OpenAI TTS audio generator — shared across all pipelines.
Replaces macOS `say` command for cross-platform compatibility (Railway/Linux).
"""
import os
import re
import random
import subprocess
from openai import OpenAI
from core.config import OPENAI_API_KEY, IS_MACOS

client = OpenAI(api_key=OPENAI_API_KEY)

# EQ audio profiles for variety
AUDIO_PROFILES = [
    {
        "name": "deep_authoritative",
        "speed": 0.95,
        "voice": "onyx",
        "description": "Slower, deeper — authoritative",
    },
    {
        "name": "crisp_direct",
        "speed": 1.0,
        "voice": "nova",
        "description": "Normal pace, crisp and clear",
    },
    {
        "name": "measured_calm",
        "speed": 0.9,
        "voice": "alloy",
        "description": "Calm, measured delivery",
    },
    {
        "name": "energetic",
        "speed": 1.05,
        "voice": "shimmer",
        "description": "Slightly faster, energetic",
    },
]


def get_profile(folder_path: str) -> dict:
    """Pick a consistent profile based on folder path hash."""
    idx = hash(folder_path) % len(AUDIO_PROFILES)
    return AUDIO_PROFILES[idx]


def clean_script(text: str) -> str:
    """Remove markdown and formatting from script."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'#+\s', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    return text.strip()


def generate_voiceover(
    script: str,
    output_path: str,
    folder_path: str = "",
    target_duration: int = 180,
) -> str:
    """
    Generate voiceover using OpenAI TTS.
    Works on both macOS and Linux (Railway).
    """
    profile = get_profile(folder_path)
    cleaned = clean_script(script)

    print(f"  [TTS] Generating voiceover ({profile['name']}, voice={profile['voice']})...")

    # OpenAI TTS — works on all platforms
    response = client.audio.speech.create(
        model="tts-1-hd",
        voice=profile["voice"],
        input=cleaned,
        speed=profile["speed"],
    )

    # Save raw mp3
    raw_path = output_path.replace(".mp3", "_raw.mp3")
    with open(raw_path, "wb") as f:
        f.write(response.content)

    # Apply FFmpeg EQ enhancement
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_path,
            "-af", "bass=g=2:f=100:w=50,loudnorm",
            "-ar", "44100",
            output_path
        ], capture_output=True, check=True)
        os.remove(raw_path)
    except Exception:
        # Fallback: use raw file if FFmpeg fails
        os.rename(raw_path, output_path)

    print(f"  [TTS] ✓ Voiceover saved: {output_path}")
    return output_path


def get_audio_duration(path: str) -> float:
    """Get audio duration in seconds using FFprobe."""
    try:
        result = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", path
        ], capture_output=True, text=True)
        import json
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                return float(stream.get("duration", 0))
    except Exception:
        pass
    return 0.0