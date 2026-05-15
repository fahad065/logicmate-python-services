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
    target_duration: int = 420,
) -> str:
    """Assemble clips + audio into final video."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Loop clips to fill target duration
    total_clip_duration = len(clip_paths) * 5
    looped_clips = list(clip_paths)

    while total_clip_duration < target_duration + 5:
        looped_clips.extend(clip_paths)
        total_clip_duration += len(clip_paths) * 5

    print(f"  [Assembler] {len(looped_clips)} clips → {target_duration}s video", flush=True)

    # Create concat file
    concat_file = output_path.replace(".mp4", "_concat.txt")
    with open(concat_file, "w") as f:
        for clip in looped_clips:
            f.write(f"file '{clip}'\n")

    # Concat clips
    concat_output = output_path.replace(".mp4", "_concat.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        concat_output
    ], capture_output=True, check=True)

    # Mix with audio — loop both to fill exact target_duration
    subprocess.run([
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", concat_output,
        "-stream_loop", "-1", "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", str(target_duration),
        "-c:v", "libx264", "-preset", "ultrafast",
        "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        output_path
    ], capture_output=True, check=True)

    # Cleanup temp files
    os.remove(concat_file)
    os.remove(concat_output)

    print(f"  [Assembler] ✓ Video assembled: {output_path}", flush=True)
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
    ], capture_output=True, text=True, timeout=30)
    duration = float(json.loads(result.stdout).get("format", {}).get("duration", 420))

    print(f"[Assembler] Video duration: {duration:.1f}s", flush=True)

    short_duration = 45

    # Ensure all shorts fit within video duration
    max_shorts = int(duration // short_duration)
    num_shorts  = min(num_shorts, max_shorts)

    segment = duration / num_shorts

    for i in range(num_shorts):
        start_time = int(i * segment)
        actual_duration = min(short_duration, int(duration - start_time - 2))

        if actual_duration < 20:
            print(f"[Assembler] Short {i+1} skipped — not enough video left ({actual_duration}s)", flush=True)
            continue

        output_path = os.path.join(output_dir, f"short_{i+1}.mp4")

        print(f"[Assembler] Short {i+1}: start={start_time}s duration={actual_duration}s", flush=True)

        try:
            result = subprocess.run([
                "ffmpeg", "-y",
                "-ss", str(start_time),   # seek video to start_time
                "-i", main_video_path,
                "-ss", str(start_time),   # seek audio to start_time
                "-i", audio_path,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-t", str(actual_duration),
                "-vf", "crop=ih*9/16:ih,scale=1080:1920",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-crf", "28",
                "-b:v", "800k",
                "-c:a", "aac", "-b:a", "96k",
                "-threads", "2",
                output_path
            ], capture_output=True, timeout=180)

            # Check ffmpeg exit code
            if result.returncode != 0:
                stderr = result.stderr.decode()[:300]
                print(f"[Assembler] Short {i+1} ffmpeg error: {stderr}", flush=True)
                continue

            # Verify file exists and has content
            if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                shorts.append(output_path)
                print(f"[Assembler] ✓ Short {i+1} created ({actual_duration}s, {os.path.getsize(output_path)//1024}KB)", flush=True)
            else:
                size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
                stderr = result.stderr.decode()[:200]
                print(f"[Assembler] Short {i+1} file too small ({size} bytes): {stderr}", flush=True)

        except subprocess.TimeoutExpired:
            print(f"[Assembler] Short {i+1} timed out after 180s", flush=True)
        except Exception as e:
            print(f"[Assembler] Short {i+1} failed: {e}", flush=True)

    print(f"[Assembler] ✓ Created {len(shorts)}/{num_shorts} shorts", flush=True)
    return shorts