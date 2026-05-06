"""
YouTube Agent Pipeline
========================
Steps:
1. Topic research
2. Script generation
3. Voiceover
4. Video clips
5. Video assembly
6. Thumbnail
7. Shorts creation
8. Upload to YouTube
9. Notify + Cleanup
"""
import os
import datetime

from core.config import OUTPUT_BASE, NUM_SHORTS
from core.script_writer import generate_youtube_script, generate_topic_ideas
from core.audio_generator import generate_voiceover, get_audio_duration
from core.video_generator import generate_clips_batch, get_scene_prompts, expand_custom_prompt
from core.nestjs_client import (
    update_pipeline_step,
    complete_pipeline_run,
    fail_pipeline_run,
    notify_complete,
    notify_failed,
)
from core.utils import (
    create_run_folder, find_resumable_folder,
    load_metadata, save_metadata, cleanup_large_files,
)

try:
    from pipelines.youtube.thumbnail import generate_thumbnail
    from pipelines.youtube.uploader import upload_to_youtube, upload_short
    from pipelines.youtube.assembler import assemble_video, create_shorts
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
    run_id: str = None,
    custom_prompt: str = None,
    use_custom_prompt: bool = False,
    console=None,
) -> dict:
    """Main YouTube pipeline orchestrator."""
    log = console.print if console else print
    log("\n━━━ LogicMate YouTube Agent Pipeline ━━━")

    folder_path = None
    # NOTE: do NOT override run_id here — use the one passed in from NestJS

    try:
        # Check for resumable run
        folder_path = find_resumable_folder(OUTPUT_BASE, "youtube", user_id)
        if folder_path:
            log(f"[Resume] Resuming: {folder_path}")
            metadata = load_metadata(folder_path)
        else:
            folder_path = create_run_folder(OUTPUT_BASE, "youtube", user_id)
            metadata = {
                "pipeline_type": "youtube",
                "user_id": user_id,
                "niche": niche,
                "run_id": run_id,
                "status": "starting",
                "started_at": datetime.datetime.now().isoformat(),
            }
            save_metadata(folder_path, metadata)

        # ── Step 1 & 2: Topic + Script ────────────────────────
        if not metadata.get("title"):
            log("\n[Step 1/9] Researching topics...")
            update_pipeline_step(run_id, 1, "Researching topics")
            topics = generate_topic_ideas(niche, count=3, format_type="youtube")
            topic = topics[0] if topics else f"The dark truth about {niche}"

            log(f"\n[Step 2/9] Writing script for: {topic}")
            update_pipeline_step(run_id, 2, f"Writing script: {topic[:50]}")
            script_data = generate_youtube_script(niche, topic)
            metadata.update({
                "title":          script_data["title"],
                "description":    script_data["description"],
                "tags":           script_data["tags"],
                "script":         script_data["script"],
                "thumbnail_text": script_data.get("thumbnail_text", ""),
                "status":         "script_done",
            })
            save_metadata(folder_path, metadata)
            log(f"  ✓ Script: {len(metadata['script'].split())} words")

        # ── Step 3: Voiceover ─────────────────────────────────
        audio_path = os.path.join(folder_path, "voiceover.mp3")
        if not os.path.exists(audio_path):
            log("\n[Step 3/9] Generating voiceover...")
            update_pipeline_step(run_id, 3, "Generating voiceover")
            generate_voiceover(
                script=metadata["script"],
                output_path=audio_path,
                folder_path=folder_path,
                target_duration=TARGET_DURATION,
            )
            metadata["audio_path"] = audio_path
            metadata["status"]     = "audio_done"
            save_metadata(folder_path, metadata)

        audio_duration  = get_audio_duration(audio_path)
        actual_duration = int(audio_duration) + 2

        # ── Step 4: Video clips ───────────────────────────────
        clips_dir = os.path.join(folder_path, "clips")
        os.makedirs(clips_dir, exist_ok=True)
        existing_clips = sorted([
            os.path.join(clips_dir, f)
            for f in os.listdir(clips_dir) if f.endswith(".mp4")
        ])

        if len(existing_clips) < NUM_CLIPS:
            log(f"\n[Step 4/9] Generating {NUM_CLIPS} video clips...")
            update_pipeline_step(run_id, 4, f"Generating {NUM_CLIPS} video clips")

            if use_custom_prompt and custom_prompt:
                prompts = expand_custom_prompt(custom_prompt, NUM_CLIPS)
            else:
                prompts = get_scene_prompts(niche, NUM_CLIPS, aspect_ratio="16:9")

            clips = generate_clips_batch(
                prompts=prompts,
                output_dir=clips_dir,
                aspect_ratio="16:9",
                duration=CLIP_DURATION,
            )
            metadata["clips"]  = clips
            metadata["status"] = "clips_done"
            save_metadata(folder_path, metadata)
        else:
            clips = existing_clips
            log(f"  [Resume] {len(clips)} clips already exist")

        # ── Step 5: Assemble ──────────────────────────────────
        final_video = os.path.join(folder_path, "final_video.mp4")
        if not os.path.exists(final_video):
            log("\n[Step 5/9] Assembling video...")
            update_pipeline_step(run_id, 5, "Assembling video")
            assemble_video(clips, audio_path, final_video, actual_duration)
            metadata["final_video"] = final_video
            metadata["status"]      = "assembled"
            save_metadata(folder_path, metadata)

        # ── Step 6: Thumbnail ─────────────────────────────────
        thumbnail_path = os.path.join(folder_path, "thumbnail.jpg")
        if not os.path.exists(thumbnail_path):
            log("\n[Step 6/9] Generating thumbnail...")
            update_pipeline_step(run_id, 6, "Generating thumbnail")
            try:
                generate_thumbnail(
                    title=metadata["title"],
                    niche=niche,
                    output_path=thumbnail_path,
                )
                metadata["thumbnail"] = thumbnail_path
                save_metadata(folder_path, metadata)
                log("  ✓ Thumbnail generated")
            except Exception as e:
                log(f"  [Thumbnail] Failed (non-critical): {e}")
                thumbnail_path = None
                metadata["thumbnail"] = None
                save_metadata(folder_path, metadata)
        else:
            log("  [Resume] Thumbnail exists")

        # ── Step 7: Shorts ────────────────────────────────────
        shorts_dir = os.path.join(folder_path, "shorts")
        os.makedirs(shorts_dir, exist_ok=True)
        if not metadata.get("shorts"):
            log(f"\n[Step 7/9] Creating {NUM_SHORTS} Shorts...")
            update_pipeline_step(run_id, 7, "Creating Shorts")
            try:
                shorts = create_shorts(final_video, audio_path, shorts_dir, NUM_SHORTS)
                metadata["shorts"] = shorts
                metadata["status"] = "shorts_done"
                save_metadata(folder_path, metadata)
                log(f"  ✓ {len(shorts)} Shorts created")
            except Exception as e:
                log(f"  [Shorts] Failed (non-critical): {e}")
                metadata["shorts"] = []
                save_metadata(folder_path, metadata)
        else:
            log("  [Resume] Shorts exist")

        # ── Step 8: Upload ────────────────────────────────────
        if not metadata.get("youtube_url"):
            log("\n[Step 8/9] Uploading to YouTube...")
            update_pipeline_step(run_id, 8, "Uploading to YouTube")
            yt_result = upload_to_youtube(
                video_path=final_video,
                thumbnail_path=thumbnail_path,
                title=metadata["title"],
                description=metadata["description"],
                tags=metadata["tags"],
                user_id=user_id,
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
                        user_id=user_id,
                    )
                    log(f"  ✓ Short {i+1} uploaded")
                except Exception as e:
                    log(f"  [Short {i+1}] Upload failed (non-critical): {e}")

        # ── Step 9: Notify + Complete ─────────────────────────
        log("\n[Step 9/9] Notifying...")
        complete_pipeline_run(
            run_id=run_id,
            youtube_url=metadata.get("youtube_url", ""),
            title=metadata.get("title", ""),
            cost=1.32,
        )
        notify_complete(run_id, user_id, metadata["title"], metadata.get("youtube_url", ""))

        # ── Cleanup ───────────────────────────────────────────
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
        fail_pipeline_run(run_id, error_msg)
        notify_failed(run_id, user_id, error_msg)
        return {"status": "failed", "error": error_msg}