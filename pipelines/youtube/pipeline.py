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

from core.config import OUTPUT_BASE, NUM_SHORTS, NUM_CLIPS, CLIP_DURATION, TARGET_DURATION
from core.script_writer import generate_youtube_script, generate_topic_ideas
from core.audio_generator import generate_voiceover, get_audio_duration
from core.video_generator import generate_clips_batch, get_scene_prompts, expand_custom_prompt
from core.nestjs_client import (
    update_pipeline_step,
    complete_pipeline_run,
    fail_pipeline_run,
    notify_complete,
    notify_failed,
    append_log,
    record_module_run,
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


def run_youtube_pipeline(
    user_id: str,
    niche: str,
    youtube_channel_id: str = None,
    user_module_id: str = None,
    run_id: str = None,
    custom_prompt: str = None,
    use_custom_prompt: bool = False,
    video_model: str = "auto",
    console=None,
) -> dict:
    """Main YouTube pipeline orchestrator."""
    log = console.print if console else print
    log("\n━━━ LogicMate YouTube Agent Pipeline ━━━")

    folder_path = None

    try:
        # ── Cost tracker — real costs from each API ───────────
        cost_tracker = {
            "openai_topics": 0.0,
            "openai_script": 0.0,
            "openai_tts":    0.0,
            "atlas_clips":   0.0,
            "openai_image":  0.0,
        }

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

        append_log(run_id, f"━━━ YouTube Pipeline Started ━━━")
        append_log(run_id, f"Niche: {niche}")
        append_log(run_id, f"Model: {video_model}")

        # ── Step 1 & 2: Topic + Script ────────────────────────
        if not metadata.get("title"):
            log("\n[Step 1/9] Researching topics...")
            append_log(run_id, "[Step 1/9] Researching trending topics...")
            update_pipeline_step(run_id, 1, "Researching topics")

            topics, topic_cost = generate_topic_ideas(niche, count=3, format_type="youtube")
            cost_tracker["openai_topics"] = topic_cost
            topic = topics[0] if topics else f"The dark truth about {niche}"
            append_log(run_id, f"  Topic selected: {topic}")

            log(f"\n[Step 2/9] Writing script for: {topic}")
            append_log(run_id, f"[Step 2/9] Writing script: {topic[:60]}")
            update_pipeline_step(run_id, 2, "Writing script")

            script_data, script_cost = generate_youtube_script(niche, topic)
            cost_tracker["openai_script"] = script_cost

            metadata.update({
                "title":          script_data["title"],
                "description":    script_data["description"],
                "tags":           script_data["tags"],
                "script":         script_data["script"],
                "thumbnail_text": script_data.get("thumbnail_text", ""),
                "status":         "script_done",
            })
            save_metadata(folder_path, metadata)
            append_log(run_id, f"  ✓ Script: {len(metadata['script'].split())} words")
            append_log(run_id, f"  Title: {metadata['title']}")
            log(f"  ✓ Script: {len(metadata['script'].split())} words")

        # ── Step 3: Voiceover ─────────────────────────────────
        audio_path = os.path.join(folder_path, "voiceover.mp3")
        if not os.path.exists(audio_path):
            log("\n[Step 3/9] Generating voiceover...")
            append_log(run_id, "[Step 3/9] Generating voiceover...")
            update_pipeline_step(run_id, 3, "Generating voiceover")

            _, tts_cost = generate_voiceover(
                script=metadata["script"],
                output_path=audio_path,
                folder_path=folder_path,
                target_duration=TARGET_DURATION,
            )
            cost_tracker["openai_tts"] = tts_cost
            metadata["audio_path"] = audio_path
            metadata["status"]     = "audio_done"
            save_metadata(folder_path, metadata)

        audio_duration  = get_audio_duration(audio_path)
        actual_duration = int(audio_duration) + 2
        append_log(run_id, f"  ✓ Voiceover ready ({int(audio_duration)}s)")

        # ── Step 4: Video clips ───────────────────────────────
        clips_dir = os.path.join(folder_path, "clips")
        os.makedirs(clips_dir, exist_ok=True)
        existing_clips = sorted([
            os.path.join(clips_dir, f)
            for f in os.listdir(clips_dir) if f.endswith(".mp4")
        ])

        if len(existing_clips) < NUM_CLIPS:
            log(f"\n[Step 4/9] Generating {NUM_CLIPS} video clips...")
            append_log(run_id, f"[Step 4/9] Generating {NUM_CLIPS} video clips (model: {video_model})...")
            update_pipeline_step(run_id, 4, f"Generating {NUM_CLIPS} video clips")

            if use_custom_prompt and custom_prompt:
                prompts = expand_custom_prompt(custom_prompt, NUM_CLIPS)
                append_log(run_id, f"  Using custom scene description")
            else:
                prompts = get_scene_prompts(niche, NUM_CLIPS, aspect_ratio="16:9")

            clips, atlas_cost = generate_clips_batch(
                prompts=prompts,
                output_dir=clips_dir,
                aspect_ratio="16:9",
                duration=CLIP_DURATION,
                preferred_model=video_model,
            )
            cost_tracker["atlas_clips"] = atlas_cost
            metadata["clips"]  = clips
            metadata["status"] = "clips_done"
            save_metadata(folder_path, metadata)
            append_log(run_id, f"  ✓ {len(clips)} clips generated (${atlas_cost:.4f})")
        else:
            clips = existing_clips
            append_log(run_id, f"  [Resume] {len(clips)} clips already exist")
            log(f"  [Resume] {len(clips)} clips already exist")

        # ── Step 5: Assemble ──────────────────────────────────
        final_video = os.path.join(folder_path, "final_video.mp4")
        if not os.path.exists(final_video):
            log("\n[Step 5/9] Assembling video...")
            append_log(run_id, "[Step 5/9] Assembling final video...")
            update_pipeline_step(run_id, 5, "Assembling video")

            assemble_video(clips, audio_path, final_video, TARGET_DURATION)
            metadata["final_video"] = final_video
            metadata["status"]      = "assembled"
            save_metadata(folder_path, metadata)
            append_log(run_id, "  ✓ Video assembled")

        # ── Step 6: Thumbnail ─────────────────────────────────
        thumbnail_path = os.path.join(folder_path, "thumbnail.jpg")
        if not os.path.exists(thumbnail_path):
            log("\n[Step 6/9] Generating thumbnail...")
            append_log(run_id, "[Step 6/9] Generating thumbnail...")
            update_pipeline_step(run_id, 6, "Generating thumbnail")
            try:
                image_cost = generate_thumbnail(
                    title=metadata["title"],
                    niche=niche,
                    output_path=thumbnail_path,
                )
                try:
                    cost_tracker["openai_image"] = float(image_cost) if image_cost else 0.04
                except (TypeError, ValueError):
                    cost_tracker["openai_image"] = 0.04
                metadata["thumbnail"] = thumbnail_path
                save_metadata(folder_path, metadata)
                append_log(run_id, "  ✓ Thumbnail generated")
                log("  ✓ Thumbnail generated")
            except Exception as e:
                log(f"  [Thumbnail] Failed (non-critical): {e}")
                append_log(run_id, f"  [Thumbnail] Failed (non-critical): {e}")
                cost_tracker["openai_image"] = 0.04
                thumbnail_path = None
                metadata["thumbnail"] = None
                save_metadata(folder_path, metadata)
        else:
            append_log(run_id, "  [Resume] Thumbnail exists")
            log("  [Resume] Thumbnail exists")

        # ── Step 7: Shorts ────────────────────────────────────
        shorts_dir = os.path.join(folder_path, "shorts")
        os.makedirs(shorts_dir, exist_ok=True)
        if not metadata.get("shorts"):
            log(f"\n[Step 7/9] Creating {NUM_SHORTS} Shorts...")
            append_log(run_id, f"[Step 7/9] Creating {NUM_SHORTS} Shorts...")
            update_pipeline_step(run_id, 7, "Creating Shorts")
            try:
                shorts = create_shorts(final_video, audio_path, shorts_dir, NUM_SHORTS)
                metadata["shorts"] = shorts
                metadata["status"] = "shorts_done"
                save_metadata(folder_path, metadata)
                append_log(run_id, f"  ✓ {len(shorts)} Shorts created")
                log(f"  ✓ {len(shorts)} Shorts created")
            except Exception as e:
                log(f"  [Shorts] Failed (non-critical): {e}")
                append_log(run_id, f"  [Shorts] Failed (non-critical): {e}")
                metadata["shorts"] = []
                save_metadata(folder_path, metadata)
        else:
            append_log(run_id, "  [Resume] Shorts exist")
            log("  [Resume] Shorts exist")

        # ── Step 8: Upload ────────────────────────────────────
        if not metadata.get("youtube_url"):
            log("\n[Step 8/9] Uploading to YouTube...")
            append_log(run_id, "[Step 8/9] Uploading to YouTube...")
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
            append_log(run_id, f"  ✓ Uploaded: {yt_result['url']}")
            log(f"  ✓ Uploaded: {yt_result['url']}")

            # Upload shorts
            valid_shorts = [s for s in metadata.get("shorts", []) if s and os.path.exists(s)]
            for i, short_path in enumerate(valid_shorts):
                try:
                    upload_short(
                        video_path=short_path,
                        title=f"{metadata['title']} #Shorts {i+1}",
                        description=metadata["description"][:500],
                        tags=metadata["tags"],
                        user_id=user_id,
                    )
                    append_log(run_id, f"  ✓ Short {i+1} uploaded")
                    log(f"  ✓ Short {i+1} uploaded")
                except Exception as e:
                    log(f"  [Short {i+1}] Upload failed (non-critical): {e}")
                    append_log(run_id, f"  [Short {i+1}] Upload failed: {e}")

        # ── Step 9: Notify + Complete ─────────────────────────
        log("\n[Step 9/9] Notifying...")
        append_log(run_id, "[Step 9/9] Pipeline complete! 🎉")

        # Calculate real total cost
        total_cost = round(sum(cost_tracker.values()), 4)
        openai_total = round(
            cost_tracker["openai_topics"] +
            cost_tracker["openai_script"] +
            cost_tracker["openai_tts"] +
            cost_tracker["openai_image"], 4
        )
        print(f"[Cost] Breakdown: {cost_tracker}", flush=True)
        print(f"[Cost] Total: ${total_cost}", flush=True)
        append_log(run_id, f"💰 Total: ${total_cost} | Atlas: ${cost_tracker['atlas_clips']:.4f} | OpenAI: ${openai_total:.4f}")

        complete_pipeline_run(
            run_id=run_id,
            youtube_url=metadata.get("youtube_url", ""),
            title=metadata.get("title", ""),
            cost=total_cost,
        )
        record_module_run(user_module_id=user_module_id, cost=total_cost)
        notify_complete(run_id, user_id, metadata["title"], metadata.get("youtube_url", ""))

        # ── Cleanup ───────────────────────────────────────────
        cleanup_large_files(folder_path, delete_all=True)

        log("\n✅ YouTube pipeline complete!")
        return {
            "status": "success",
            "youtube_url": metadata.get("youtube_url"),
            "title": metadata.get("title"),
            "cost": total_cost,
        }

    except Exception as e:
        error_msg = str(e)
        log(f"\n❌ Pipeline failed: {error_msg}")
        append_log(run_id, f"❌ Pipeline failed: {error_msg}")

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