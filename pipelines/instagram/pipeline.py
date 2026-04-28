"""
Instagram Reels Agent Pipeline
================================
Steps:
1. Topic research     — trending Reels topics in niche
2. Script generation  — 30-60 sec hook-based script
3. Voiceover          — OpenAI TTS
4. Video clips        — Seedance 9:16 vertical
5. Video assembly     — FFmpeg stitch clips + audio
6. Caption burn       — text overlay on video
7. Cover generation   — Reels cover frame
8. Upload             — Instagram Graph API
9. Notify             — NestJS notification + email
10. Cleanup           — free disk space

Usage:
    from pipelines.instagram.pipeline import run_instagram_pipeline
    run_instagram_pipeline(user_id, user_module_config)
"""
import os
import sys
import json
import subprocess
import datetime
import traceback

from core.config import OUTPUT_BASE, DEFAULT_NICHE
from core.script_writer import generate_reels_script, generate_topic_ideas
from core.audio_generator import generate_voiceover, get_audio_duration
from core.video_generator import generate_clips_batch, get_scene_prompts
from core.nestjs_client import (
    create_pipeline_run, update_pipeline_run,
    notify_complete, notify_failed,
)
from core.utils import (
    create_run_folder, find_resumable_folder,
    load_metadata, save_metadata, cleanup_large_files,
)
from pipelines.instagram.caption_burner import burn_captions
from pipelines.instagram.cover_generator import generate_cover, extract_first_frame
from pipelines.instagram.uploader import upload_reel, validate_token


# Reels config
NUM_CLIPS        = 4    # Fewer clips for short vertical video
CLIP_DURATION    = 5    # seconds each
TARGET_DURATION  = 35   # ~35 second Reel


def run_instagram_pipeline(
    user_id: str,
    niche: str,
    instagram_account_id: str,
    access_token: str,
    user_module_id: str = None,
    console=None,
) -> dict:
    """
    Main Instagram Reels pipeline orchestrator.
    Returns result dict with status and reel URL.
    """
    log = console.print if console else print
    log("\n[bold cyan]━━━ NexAgent Instagram Reels Pipeline ━━━[/bold cyan]" if console
        else "\n━━━ NexAgent Instagram Reels Pipeline ━━━")

    folder_path = None
    run_id = None

    try:
        # ── Check for resumable run ────────────────────────────
        folder_path = find_resumable_folder(OUTPUT_BASE, "instagram", user_id)
        if folder_path:
            log(f"[yellow]Resuming existing run: {folder_path}[/yellow]" if console
                else f"Resuming: {folder_path}")
            metadata = load_metadata(folder_path)
        else:
            folder_path = create_run_folder(OUTPUT_BASE, "instagram", user_id)
            metadata = {
                "pipeline_type": "instagram",
                "user_id": user_id,
                "niche": niche,
                "status": "starting",
                "started_at": datetime.datetime.now().isoformat(),
            }
            save_metadata(folder_path, metadata)

        # ── Create NestJS pipeline run record ──────────────────
        run_record = create_pipeline_run({
            "userId": user_id,
            "userModuleId": user_module_id,
            "moduleType": "agent",
            "pipelineType": "instagram",
            "niche": niche,
            "status": "running",
            "runId": os.path.basename(folder_path),
        })
        run_id = run_record.get("_id") if run_record else None

        # ── Step 1: Topic research ─────────────────────────────
        if not metadata.get("topic"):
            log("\n[Step 1/9] Researching trending Reels topics...")
            topics = generate_topic_ideas(niche, count=3, format_type="reels")
            topic = topics[0] if topics else f"Hidden truth about {niche}"
            metadata["topic"] = topic
            metadata["status"] = "topic_selected"
            save_metadata(folder_path, metadata)
            log(f"  ✓ Topic: {topic}")
        else:
            topic = metadata["topic"]
            log(f"  [Resume] Topic: {topic}")

        # ── Step 2: Script generation ──────────────────────────
        if not metadata.get("script"):
            log("\n[Step 2/9] Writing Reels script...")
            script_data = generate_reels_script(niche, topic)
            metadata["script"]     = script_data["script"]
            metadata["caption"]    = script_data["caption"]
            metadata["hashtags"]   = script_data["hashtags"]
            metadata["cover_text"] = script_data.get("cover_text", topic[:20])
            metadata["hook"]       = script_data.get("hook", "")
            metadata["status"]     = "script_done"
            save_metadata(folder_path, metadata)
            log(f"  ✓ Script written ({len(metadata['script'].split())} words)")
        else:
            log(f"  [Resume] Script ready")

        # ── Step 3: Voiceover ──────────────────────────────────
        audio_path = os.path.join(folder_path, "voiceover.mp3")
        if not os.path.exists(audio_path):
            log("\n[Step 3/9] Generating voiceover...")
            generate_voiceover(
                script=metadata["script"],
                output_path=audio_path,
                folder_path=folder_path,
                target_duration=TARGET_DURATION,
            )
            metadata["audio_path"] = audio_path
            metadata["status"]     = "audio_done"
            save_metadata(folder_path, metadata)
            log(f"  ✓ Voiceover generated")
        else:
            log(f"  [Resume] Voiceover exists")

        audio_duration = get_audio_duration(audio_path)
        actual_duration = int(audio_duration) + 2

        # ── Step 4: Video clips (9:16 vertical) ───────────────
        clips_dir = os.path.join(folder_path, "clips")
        os.makedirs(clips_dir, exist_ok=True)
        existing_clips = sorted([
            os.path.join(clips_dir, f)
            for f in os.listdir(clips_dir)
            if f.endswith(".mp4")
        ])

        if len(existing_clips) < NUM_CLIPS:
            log(f"\n[Step 4/9] Generating {NUM_CLIPS} vertical video clips (9:16)...")
            prompts = get_scene_prompts(niche, NUM_CLIPS, aspect_ratio="9:16")
            clips = generate_clips_batch(
                prompts=prompts,
                output_dir=clips_dir,
                aspect_ratio="9:16",
                duration=CLIP_DURATION,
            )
            metadata["clips"] = clips
            metadata["status"] = "clips_done"
            save_metadata(folder_path, metadata)
            log(f"  ✓ {len(clips)} clips generated")
        else:
            clips = existing_clips
            log(f"  [Resume] {len(clips)} clips exist")

        # ── Step 5: Video assembly ─────────────────────────────
        raw_video = os.path.join(folder_path, "reel_raw.mp4")
        if not os.path.exists(raw_video):
            log("\n[Step 5/9] Assembling vertical video...")
            _assemble_vertical_video(clips, audio_path, raw_video, actual_duration)
            metadata["raw_video"] = raw_video
            metadata["status"]    = "assembled"
            save_metadata(folder_path, metadata)
            log(f"  ✓ Video assembled ({actual_duration}s)")
        else:
            log(f"  [Resume] Raw video exists")

        # ── Step 6: Burn captions ──────────────────────────────
        captioned_video = os.path.join(folder_path, "reel_captioned.mp4")
        if not os.path.exists(captioned_video):
            log("\n[Step 6/9] Burning captions...")
            burn_captions(
                video_path=raw_video,
                script=metadata["script"],
                output_path=captioned_video,
                font_size=52,
                position="bottom",
            )
            metadata["captioned_video"] = captioned_video
            metadata["status"]          = "captioned"
            save_metadata(folder_path, metadata)
            log(f"  ✓ Captions burned")
        else:
            log(f"  [Resume] Captioned video exists")

        # ── Step 7: Cover image ────────────────────────────────
        cover_path = os.path.join(folder_path, "cover.jpg")
        if not os.path.exists(cover_path):
            log("\n[Step 7/9] Generating cover image...")
            generate_cover(
                topic=topic,
                cover_text=metadata["cover_text"],
                niche=niche,
                color="#7c3aed",
                output_path=cover_path,
            )
            metadata["cover_path"] = cover_path
            metadata["status"]     = "cover_done"
            save_metadata(folder_path, metadata)
            log(f"  ✓ Cover generated")
        else:
            log(f"  [Resume] Cover exists")

        # ── Step 8: Upload to Instagram ────────────────────────
        if not metadata.get("reel_url"):
            log("\n[Step 8/9] Uploading to Instagram...")

            # Build caption with hashtags
            hashtags = " ".join(metadata.get("hashtags", [])[:20])
            full_caption = f"{metadata['caption']}\n\n{hashtags}"

            result = upload_reel(
                video_path=captioned_video,
                cover_path=cover_path,
                caption=full_caption,
                access_token=access_token,
                instagram_account_id=instagram_account_id,
            )
            metadata["reel_id"]  = result["id"]
            metadata["reel_url"] = result["url"]
            metadata["status"]   = "uploaded"
            save_metadata(folder_path, metadata)
            log(f"  ✓ Reel uploaded: {result['url']}")
        else:
            log(f"  [Resume] Already uploaded: {metadata['reel_url']}")

        # ── Step 9: Notify NestJS ──────────────────────────────
        log("\n[Step 9/9] Sending notifications...")
        if run_id:
            update_pipeline_run(run_id, {
                "status": "uploaded",
                "title": topic,
                "instagramUrl": metadata["reel_url"],
                "caption": metadata["caption"],
            })
        notify_complete(run_id, user_id, topic, metadata["reel_url"])
        log(f"  ✓ Notifications sent")

        # ── Step 10: Cleanup ───────────────────────────────────
        log("\n[Cleanup] Freeing disk space...")
        cleanup_large_files(folder_path)

        log("\n[bold green]✅ Instagram Reel pipeline complete![/bold green]" if console
            else "\n✅ Instagram Reel pipeline complete!")
        log(f"  📱 Reel URL: {metadata['reel_url']}")

        return {
            "status": "success",
            "reel_url": metadata["reel_url"],
            "topic": topic,
            "caption": metadata["caption"],
        }

    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        log(f"\n[red]❌ Pipeline failed: {error_msg}[/red]" if console
            else f"\n❌ Pipeline failed: {error_msg}")
        print(tb)

        if folder_path and os.path.exists(folder_path):
            try:
                metadata = load_metadata(folder_path)
                metadata["status"] = "failed"
                metadata["error"]  = error_msg
                save_metadata(folder_path, metadata)
            except Exception:
                pass

        if run_id:
            update_pipeline_run(run_id, {"status": "failed", "error": error_msg})
        if user_id:
            notify_failed(run_id, user_id, error_msg)

        return {"status": "failed", "error": error_msg}


def _assemble_vertical_video(
    clips: list[str],
    audio_path: str,
    output_path: str,
    target_duration: int,
) -> str:
    """
    Assemble vertical 9:16 video from clips + audio using FFmpeg.
    Loops clips if needed to match audio duration.
    """
    if not clips:
        raise Exception("No clips to assemble")

    clips_dir = os.path.dirname(clips[0])
    concat_file = os.path.join(clips_dir, "concat_list.txt")

    # Loop clips to fill target duration
    total_clip_duration = len(clips) * 5  # 5 sec each
    clip_list = clips[:]
    while total_clip_duration < target_duration + 5:
        clip_list.extend(clips)
        total_clip_duration += len(clips) * 5

    with open(concat_file, "w") as f:
        for clip_path in clip_list:
            f.write(f"file '{clip_path}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(target_duration),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        "-shortest",
        output_path,
    ], check=True, capture_output=True)

    if os.path.exists(concat_file):
        os.remove(concat_file)

    return output_path