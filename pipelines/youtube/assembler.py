"""
FFmpeg video assembler — YouTube long-form video.
Stitches video clips + audio into final MP4.
"""
import os
import json
import subprocess


def assemble_video(
    clip_paths: list[str],
    audio_path: str,
    output_path: str,
    target_duration: int = 180,
) -> str:
    """Assemble video clips + audio — memory optimized for Railway."""
    print(f"\n[Assembler] Assembling {len(clip_paths)} clips...", flush=True)
 
    if not clip_paths:
        raise Exception("No clips to assemble")
 
    clips_dir = os.path.dirname(clip_paths[0])
    concat_file = os.path.join(clips_dir, "concat_list.txt")
 
    # Loop clips to fill target duration
    total_clip_duration = len(clip_paths) * 5
    clip_list = clip_paths[:]
    while total_clip_duration < target_duration + 5:
        clip_list.extend(clip_paths)
        total_clip_duration += len(clip_paths) * 5
 
    with open(concat_file, "w") as f:
        for clip_path in clip_list:
            f.write(f"file '{clip_path}'\n")
 
    # Memory-optimized FFmpeg — ultrafast preset, single thread, lower bitrate
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "ultrafast",   # ← prevent OOM SIGKILL
        "-crf", "28",             # ← lower quality = less memory
        "-b:v", "800k",           # ← cap video bitrate
        "-vf", "scale=1280:720",  # ← ensure consistent resolution
        "-c:a", "aac",
        "-b:a", "128k",           # ← reduce audio
        "-threads", "1",          # ← single thread = less RAM
        "-t", str(target_duration),
        "-shortest",
        output_path,
    ], check=True, capture_output=True, timeout=300)
 
    if os.path.exists(concat_file):
        os.remove(concat_file)
 
    print(f"[Assembler] ✓ Final video: {output_path}", flush=True)
    return output_path


def create_shorts(
    main_video_path: str,
    audio_path: str,
    output_dir: str,
    num_shorts: int = 3,
) -> list[str]:
    """Cut vertical 9:16 Shorts from the main horizontal video."""
    os.makedirs(output_dir, exist_ok=True)
    shorts = []

    # Get video duration
    result = subprocess.run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", main_video_path
    ], capture_output=True, text=True)
    duration = float(json.loads(result.stdout).get("format", {}).get("duration", 180))

    short_duration = 45  # ← reduce from 50 to 45s (safer margin)

    # Ensure all shorts fit within video duration
    max_shorts = int(duration // short_duration)
    num_shorts  = min(num_shorts, max_shorts)  # ← never exceed what fits

    segment = duration / num_shorts

    for i in range(num_shorts):
        start_time = int(i * segment)
        # Cap end time to not exceed video duration
        actual_duration = min(short_duration, int(duration - start_time - 1))
        if actual_duration < 20:  # ← skip if less than 20s available
            print(f"[Assembler] Short {i+1} skipped — not enough video left", flush=True)
            continue

        output_path = os.path.join(output_dir, f"short_{i+1}.mp4")

        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-ss", str(start_time),
                "-i", main_video_path,
                "-i", audio_path,
                "-map", "0:v:0", "-map", "1:a:0",
                "-ss", str(start_time),
                "-t", str(actual_duration),  # ← use actual_duration not fixed
                "-vf", "crop=ih*9/16:ih,scale=720:1280",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-crf", "28",
                "-b:v", "800k",
                "-c:a", "aac", "-b:a", "96k",
                "-threads", "1",
                output_path
            ], check=True, capture_output=True, timeout=120)
            shorts.append(output_path)
            print(f"[Assembler] ✓ Short {i+1} created ({actual_duration}s)", flush=True)
        except Exception as e:
            print(f"[Assembler] Short {i+1} failed: {e}", flush=True)

    return shorts