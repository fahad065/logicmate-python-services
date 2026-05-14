"""
OpenAI TTS audio generator — shared across all pipelines.
Uses bold, dramatic voices for dark psychology content.
"""
import os
import re
import subprocess
from openai import OpenAI
from core.config import OPENAI_API_KEY
from core.model_health import get_best_openai_tts_model

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
TTS_MODELS = [get_best_openai_tts_model(), "tts-1"]

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


def chunk_text(text: str, max_chars: int = 4000) -> list[str]:
    """Split text into chunks of max_chars, splitting on sentence boundaries."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current += (" " if current else "") + sentence
        else:
            if current:
                chunks.append(current)
            # If single sentence is too long, split by words
            if len(sentence) > max_chars:
                words = sentence.split()
                current = ""
                for word in words:
                    if len(current) + len(word) + 1 <= max_chars:
                        current += (" " if current else "") + word
                    else:
                        chunks.append(current)
                        current = word
            else:
                current = sentence
    if current:
        chunks.append(current)
    return chunks
 
 
def merge_audio_chunks(chunk_paths: list[str], output_path: str) -> None:
    """Merge multiple mp3 files into one using FFmpeg."""
    if len(chunk_paths) == 1:
        import shutil
        shutil.copy(chunk_paths[0], output_path)
        return
 
    # Create concat file
    concat_file = output_path.replace(".mp3", "_concat.txt")
    with open(concat_file, "w") as f:
        for path in chunk_paths:
            f.write(f"file '{path}'\n")
 
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file, "-c", "copy", output_path
    ], capture_output=True, check=True)
 
    os.remove(concat_file)
    for path in chunk_paths:
        try:
            os.remove(path)
        except Exception:
            pass
 
 
def generate_voiceover(
    script: str,
    output_path: str,
    folder_path: str = None,
    target_duration: int = 420,
) -> tuple[str, float]:
    """Generate voiceover with chunking for long scripts. Returns (output_path, tts_cost)."""
    tts_cost = calculate_tts_cost(script)
    profile = get_profile(folder_path)
    cleaned = clean_script(script)
 
    print(f"  [TTS] Script length: {len(cleaned)} chars", flush=True)
    print(f"  [TTS] Generating voiceover ({profile['name']}, voice={profile['voice']})...", flush=True)
 
    # Split into chunks of 4000 chars max
    chunks = chunk_text(cleaned, max_chars=4000)
    print(f"  [TTS] Split into {len(chunks)} chunks", flush=True)
 
    chunk_paths = []
 
    for i, chunk in enumerate(chunks):
        chunk_raw = output_path.replace(".mp3", f"_chunk_{i}_raw.mp3")
        chunk_path = output_path.replace(".mp3", f"_chunk_{i}.mp3")
 
        # Try each TTS model
        response = None
        for model in TTS_MODELS:
            try:
                response = client.audio.speech.create(
                    model=model,
                    voice=profile["voice"],
                    input=chunk,
                    speed=profile["speed"],
                )
                print(f"  [TTS] Chunk {i+1}/{len(chunks)} done (model: {model})", flush=True)
                break
            except Exception as e:
                print(f"  [TTS] {model} chunk {i+1} failed: {e} — trying next...", flush=True)
 
        if not response:
            raise Exception(f"All TTS models failed for chunk {i+1}")
 
        # Save chunk
        with open(chunk_raw, "wb") as f:
            f.write(response.content)
 
        # Apply audio enhancement
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", chunk_raw,
                "-af", "bass=g=4:f=80:w=50,treble=g=2:f=8000,loudnorm=I=-14:LRA=7:TP=-2",
                "-ar", "44100", "-b:a", "192k",
                chunk_path
            ], capture_output=True, check=True)
            os.remove(chunk_raw)
        except Exception:
            os.rename(chunk_raw, chunk_path)
 
        chunk_paths.append(chunk_path)
 
    # Merge all chunks
    print(f"  [TTS] Merging {len(chunk_paths)} audio chunks...", flush=True)
    merge_audio_chunks(chunk_paths, output_path)
 
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