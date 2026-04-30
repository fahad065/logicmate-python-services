"""
YouTube Agent Pipeline
========================
Steps:
1. Topic research     — trending topics in niche
2. Script generation  — 3-5 min YouTube script
3. Voiceover          — OpenAI TTS
4. Video clips        — Seedance 16:9
5. Video assembly     — FFmpeg
6. Thumbnail          — DALL-E 3
7. Shorts creation    — cut 3 vertical shorts
8. Upload             — YouTube Data API v3
9. Notify             — NestJS
10. Cleanup           — free disk space

Usage:
    from pipelines.youtube.pipeline import run_youtube_pipeline
"""
import os
import sys
import json
import datetime
import traceback

from core.config import OUTPUT_BASE, DEFAULT_NICHE, NUM_SHORTS
from core.script_writer import generate_youtube_script, generate_topic_ideas
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

# Import YouTube-specific modules (kept from original)
# These stay in pipelines/youtube/ folder
try:
    from pipelines.youtube.thumbnail import generate_thumbnail
    from pipelines.youtube.uploader import upload_to_youtube, upload_short
    from pipelines.youtube.assembler import assemble_video, create_shorts
    from pipelines.youtube.assembler import assemble_video
except ImportError as e:
    print(f"[Warning] YouTube module import failed: {e}")


NUM_CLIPS       = 12
CLIP_DURATION   = 5
TARGET_DURATION = 180


def run_youtube_pipeline(
    user_id: str,
    niche: str,
    youtube_channel_id: str = None,
    user_module_id: str = None,
    console=None,
) -> dict:
    """Main YouTube pipeline orchestrator."""
    log = console.print if console else print
    log("\n━━━ LogicMate YouTube Agent Pipeline ━━━")

    folder_path = None
    run_id = None

    try:
        # Check for resumable run
        folder_path = find_resumable_folder(OUTPUT_BASE, "youtube", user_id)
        if folder_path:
            log(f"Resuming: {folder_path}")
            metadata = load_metadata(folder_path)
        else:
            folder_path = create_run_folder(OUTPUT_BASE, "youtube", user_id)
            metadata = {
                "pipeline_type": "youtube",
                "user_id": user_id,
                "niche": niche,
                "status": "starting",
                "started_at": datetime.datetime.now().isoformat(),
            }
            save_metadata(folder_path, metadata)

        # Create NestJS run record
        run_record = create_pipeline_run({
            "userId": user_id,
            "userModuleId": user_module_id,
            "moduleType": "agent",
            "pipelineType": "youtube",
            "niche": niche,
            "status": "running",
            "runId": os.path.basename(folder_path),
        })
        run_id = run_record.get("_id") if run_record else None

        # Step 1: Topic
        if not metadata.get("title"):
            log("\n[Step 1/9] Researching topics...")
            topics = generate_topic_ideas(niche, count=3, format_type="youtube")
            topic = topics[0] if topics else f"The truth about {niche}"
            # Generate full script
            log(f"\n[Step 2/9] Writing script for: {topic}")
            script_data = generate_youtube_script(niche, topic)
            metadata.update({
                "title":       script_data["title"],
                "description": script_data["description"],
                "tags":        script_data["tags"],
                "script":      script_data["script"],
                "thumbnail_text": script_data.get("thumbnail_text", ""),
                "status":      "script_done",
            })
            save_metadata(folder_path, metadata)
            log(f"  ✓ Script: {len(metadata['script'].split())} words")

        # Step 3: Voiceover
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

        audio_duration = get_audio_duration(audio_path)
        actual_duration = int(audio_duration) + 2

        # Step 4: Video clips
        clips_dir = os.path.join(folder_path, "clips")
        os.makedirs(clips_dir, exist_ok=True)
        existing_clips = sorted([
            os.path.join(clips_dir, f)
            for f in os.listdir(clips_dir) if f.endswith(".mp4")
        ])

        if len(existing_clips) < NUM_CLIPS:
            log(f"\n[Step 4/9] Generating {NUM_CLIPS} video clips...")
            prompts = get_scene_prompts(niche, NUM_CLIPS, aspect_ratio="16:9")
            clips = generate_clips_batch(
                prompts=prompts,
                output_dir=clips_dir,
                aspect_ratio="16:9",
                duration=CLIP_DURATION,
            )
            metadata["clips"] = clips
            metadata["status"] = "clips_done"
            save_metadata(folder_path, metadata)
        else:
            clips = existing_clips

        # Step 5: Assemble
        final_video = os.path.join(folder_path, "final_video.mp4")
        if not os.path.exists(final_video):
            log("\n[Step 5/9] Assembling video...")
            assemble_video(clips, audio_path, final_video, actual_duration)
            metadata["final_video"] = final_video
            metadata["status"]      = "assembled"
            save_metadata(folder_path, metadata)

        # Step 6: Thumbnail
        thumbnail_path = os.path.join(folder_path, "thumbnail.jpg")
        if not os.path.exists(thumbnail_path):
            log("\n[Step 6/9] Generating thumbnail...")
            generate_thumbnail(
                title=metadata["title"],
                niche=niche,
                output_path=thumbnail_path,
            )
            metadata["thumbnail"] = thumbnail_path
            save_metadata(folder_path, metadata)

        # Step 7: Shorts
        shorts_dir = os.path.join(folder_path, "shorts")
        os.makedirs(shorts_dir, exist_ok=True)
        if not metadata.get("shorts"):
            log(f"\n[Step 7/9] Creating {NUM_SHORTS} Shorts...")
            shorts = create_shorts(final_video, audio_path, shorts_dir, NUM_SHORTS)
            metadata["shorts"] = shorts
            metadata["status"] = "shorts_done"
            save_metadata(folder_path, metadata)

        # Step 8: Upload
        if not metadata.get("youtube_url"):
            log("\n[Step 8/9] Uploading to YouTube...")
            yt_result = upload_to_youtube(
                video_path=final_video,
                thumbnail_path=thumbnail_path,
                title=metadata["title"],
                description=metadata["description"],
                tags=metadata["tags"],
            )
            metadata["youtube_url"] = yt_result["url"]
            metadata["youtube_id"]  = yt_result["id"]
            metadata["status"]      = "uploaded"
            save_metadata(folder_path, metadata)
            log(f"  ✓ Uploaded: {yt_result['url']}")

            # Upload shorts
            for i, short_path in enumerate(metadata.get("shorts", [])):
                try:
                    upload_short(
                        video_path=short_path,
                        title=f"{metadata['title']} #Shorts {i+1}",
                        description=metadata["description"][:500],
                        tags=metadata["tags"],
                    )
                except Exception as e:
                    log(f"  [Short {i+1}] Upload failed: {e}")

        # Step 9: Notify
        if run_id:
            update_pipeline_run(run_id, {
                "status": "uploaded",
                "title": metadata["title"],
                "youtubeUrl": metadata.get("youtube_url"),
            })
        notify_complete(run_id, user_id, metadata["title"], metadata.get("youtube_url", ""))

        # Step 10: Cleanup
        cleanup_large_files(folder_path, delete_all=True)

        log("\n✅ YouTube pipeline complete!")
        return {
            "status": "success",
            "youtube_url": metadata.get("youtube_url"),
            "title": metadata.get("title"),
        }

    except Exception as e:
        error_msg = str(e)
        log(f"\n❌ Pipeline failed: {error_msg}")
        if folder_path:
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