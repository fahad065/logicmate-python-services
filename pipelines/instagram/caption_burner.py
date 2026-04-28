"""
Caption/subtitle burner for Instagram Reels.
Burns text captions directly onto video using FFmpeg.
Cross-platform: works on macOS and Linux/Railway.
"""
import os
import subprocess
import tempfile


def burn_captions(
    video_path: str,
    script: str,
    output_path: str,
    font_size: int = 52,
    font_color: str = "white",
    outline_color: str = "black",
    position: str = "bottom",  # "bottom", "center", "top"
) -> str:
    """
    Burn subtitles/captions onto a vertical video.
    Splits script into timed segments and overlays them.
    """
    # Split script into caption chunks (~5 words each)
    words = script.split()
    chunks = []
    chunk_size = 5
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i+chunk_size]))

    # Get video duration
    duration = get_video_duration(video_path)
    if duration <= 0:
        return video_path

    time_per_chunk = duration / max(len(chunks), 1)

    # Create SRT subtitle file
    srt_path = video_path.replace(".mp4", "_captions.srt")
    with open(srt_path, "w") as f:
        for i, chunk in enumerate(chunks):
            start = i * time_per_chunk
            end = (i + 1) * time_per_chunk
            f.write(f"{i+1}\n")
            f.write(f"{format_srt_time(start)} --> {format_srt_time(end)}\n")
            f.write(f"{chunk}\n\n")

    # Vertical position
    if position == "bottom":
        y_pos = "(h-text_h-120)"
    elif position == "center":
        y_pos = "(h-text_h)/2"
    else:
        y_pos = "120"

    # Try system fonts (Linux/Railway)
    font_path = find_font()

    # FFmpeg subtitle filter
    try:
        cmd = ["ffmpeg", "-y", "-i", video_path]

        if font_path:
            # Burn using drawtext with SRT timing
            subtitle_filter = (
                f"subtitles={srt_path}:force_style='"
                f"FontSize={font_size},"
                f"PrimaryColour=&H00FFFFFF,"
                f"OutlineColour=&H00000000,"
                f"Outline=3,"
                f"Bold=1,"
                f"Alignment=2'"
            )
        else:
            subtitle_filter = f"subtitles={srt_path}"

        cmd += ["-vf", subtitle_filter, "-c:a", "copy", output_path]
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        print(f"  [Captions] ✓ Burned captions onto video")

    except Exception as e:
        print(f"  [Captions] Caption burn failed: {e} — using video without captions")
        import shutil
        shutil.copy(video_path, output_path)
    finally:
        if os.path.exists(srt_path):
            os.remove(srt_path)

    return output_path


def find_font() -> str | None:
    """Find a suitable font file on the system."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def get_video_duration(path: str) -> float:
    """Get video duration in seconds."""
    try:
        import json
        result = subprocess.run([
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", path
        ], capture_output=True, text=True)
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0))
    except Exception:
        return 0.0


def format_srt_time(seconds: float) -> str:
    """Format seconds to SRT timestamp HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"