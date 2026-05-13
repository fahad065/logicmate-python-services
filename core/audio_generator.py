"""
OpenAI TTS audio generator — shared across all pipelines.
Uses bold, dramatic voices for dark psychology content.
"""
import os
import re
import subprocess
from openai import OpenAI
from core.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

# Bold dramatic profiles — dark psychology niche
AUDIO_PROFILES = [
    {
        "name": "bold_dramatic",
        "speed": 0.92,
        "voice": "onyx",
        "description": "Deep, bold, dramatic — perfect for dark content",
    },
    {
        "name": "intense_authoritative",
        "speed": 0.95,
        "voice": "echo",
        "description": "Intense, authoritative, commanding",
    },
    {
        "name": "mysterious_deep",
        "speed": 0.90,
        "voice": "fable",
        "description": "Mysterious, deep, storytelling",
    },
]

# TTS model fallback chain
TTS_MODELS = [
    "tts-1-hd",   # primary — best quality
    "tts-1",      # fallback — faster, slightly lower quality
]

# TTS pricing
TTS_PRICE_PER_CHAR = 0.000015   # $15 per 1M characters (tts-1-hd)
TTS_HD_PRICE       = 0.000030   # $30 per 1M characters (tts-1-hd premium)
 
def calculate_tts_cost(text: str, model: str = "tts-1-hd") -> float:
    """Calculate TTS cost based on character count."""
    price = TTS_HD_PRICE if model == "tts-1-hd" else TTS_PRICE_PER_CHAR
    return round(len(text) * price, 6)


def get_profile(folder_path: str) -> dict:
    """Pick consistent bold profile based on folder path hash."""
    idx = hash(folder_path) % len(AUDIO_PROFILES)
    return AUDIO_PROFILES[idx]


def clean_script(text: str) -> str:
    """Remove markdown and formatting from script."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'#+\s', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    return text.strip()


def generate_voiceover(
    script: str,
    output_path: str,
    folder_path: str = None,
    target_duration: int = 420,
) -> tuple[str, float]:
    """Generate voiceover. Returns (output_path, tts_cost)."""
    tts_cost = calculate_tts_cost(script)
    profile = get_profile(folder_path)
    cleaned = clean_script(script)

    print(f"  [TTS] Generating voiceover ({profile['name']}, voice={profile['voice']})...", flush=True)

    # Try each TTS model in order
    response = None
    for model in TTS_MODELS:
        try:
            response = client.audio.speech.create(
                model=model,
                voice=profile["voice"],
                input=cleaned,
                speed=profile["speed"],
            )
            print(f"  [TTS] Using model: {model}", flush=True)
            break
        except Exception as e:
            print(f"  [TTS] {model} failed: {e} — trying next...", flush=True)

    if not response:
        raise Exception("All TTS models failed")

    # Save raw mp3
    raw_path = output_path.replace(".mp3", "_raw.mp3")
    with open(raw_path, "wb") as f:
        f.write(response.content)

    # Apply FFmpeg audio enhancement — boost bass for dramatic effect
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_path,
            "-af", "bass=g=4:f=80:w=50,treble=g=2:f=8000,loudnorm=I=-14:LRA=7:TP=-2",
            "-ar", "44100",
            "-b:a", "192k",
            output_path
        ], capture_output=True, check=True)
        os.remove(raw_path)
    except Exception:
        os.rename(raw_path, output_path)

    print(f"  [TTS] ✓ Voiceover saved: {output_path}", flush=True)
    return output_path, tts_cost


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