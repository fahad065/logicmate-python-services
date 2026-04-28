"""
NexAgent Cron Runner
=====================
Scheduled job runner — called by system cron or Railway cron.
Finds active user modules and triggers their pipelines.

Supports resume: checks for existing running pipeline
before creating new folder (prevents Atlas over-billing).
"""
import os
import sys
import json
import requests
import traceback
import datetime
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import NESTJS_URL, OUTPUT_BASE, DEFAULT_NICHE
from core.nestjs_client import get_auth_headers
from core.utils import normalize


def get_active_user_modules(pipeline_type: str = None) -> list[dict]:
    """Fetch all active user modules from NestJS."""
    try:
        headers = get_auth_headers()
        params = {"status": "active", "limit": "100"}
        if pipeline_type:
            params["pipelineType"] = pipeline_type

        resp = requests.get(
            f"{NESTJS_URL}/usermodules",
            headers=headers,
            params=params,
            timeout=15,
        )
        data = resp.json()
        return data.get("data", [])
    except Exception as e:
        print(f"[Cron] Failed to fetch user modules: {e}")
        return []


def should_run_now(user_module: dict) -> bool:
    """Check if this module should run based on schedule."""
    schedule = user_module.get("scheduleFrequency", "manual")
    if schedule == "manual":
        return False

    schedule_time = user_module.get("scheduleTime", "08:00")
    now = datetime.datetime.now()
    current_time = now.strftime("%H:%M")

    if schedule == "daily":
        # Run if current time matches schedule time (within 15 min window)
        scheduled_hour, scheduled_min = map(int, schedule_time.split(":"))
        scheduled_minutes = scheduled_hour * 60 + scheduled_min
        current_minutes = now.hour * 60 + now.minute
        return abs(current_minutes - scheduled_minutes) <= 15

    elif schedule == "weekly":
        # Run on Monday at scheduled time
        return now.weekday() == 0 and abs(
            (now.hour * 60 + now.minute) -
            (int(schedule_time.split(":")[0]) * 60 + int(schedule_time.split(":")[1]))
        ) <= 15

    return False


def run_pipeline_for_module(user_module: dict):
    """Run the appropriate pipeline for a user module."""
    pipeline_type = user_module.get("pipelineType", "custom")
    user_id       = str(user_module.get("userId", ""))
    niche         = normalize(user_module.get("niche", DEFAULT_NICHE))
    module_id     = user_module.get("_id", "")

    print(f"\n[Cron] Running {pipeline_type} pipeline for user {user_id[:8]}...")

    if pipeline_type == "youtube":
        from pipelines.youtube.pipeline import run_youtube_pipeline
        result = run_youtube_pipeline(
            user_id=user_id,
            niche=niche,
            user_module_id=module_id,
        )

    elif pipeline_type == "instagram":
        # Get Instagram credentials from module config
        config = user_module.get("config", {})
        account_id   = config.get("instagramAccountId", "")
        access_token = config.get("instagramAccessToken", "")

        if not account_id or not access_token:
            print(f"[Cron] Instagram module {module_id} missing credentials — skipping")
            return

        from pipelines.instagram.pipeline import run_instagram_pipeline
        result = run_instagram_pipeline(
            user_id=user_id,
            niche=niche,
            instagram_account_id=account_id,
            access_token=access_token,
            user_module_id=module_id,
        )

    else:
        print(f"[Cron] Pipeline type '{pipeline_type}' not implemented yet — skipping")
        return

    status = result.get("status", "unknown")
    print(f"[Cron] Pipeline {status} for user {user_id[:8]}")


def run_all_scheduled():
    """Main cron function — run all modules that are due."""
    print(f"\n{'='*50}")
    print(f"[Cron] Starting scheduled run at {datetime.datetime.now().isoformat()}")
    print(f"{'='*50}")

    modules = get_active_user_modules()
    print(f"[Cron] Found {len(modules)} active modules")

    ran = 0
    for module in modules:
        if should_run_now(module):
            try:
                run_pipeline_for_module(module)
                ran += 1
            except Exception as e:
                print(f"[Cron] Error running module: {e}")
                traceback.print_exc()

    print(f"\n[Cron] Done. Ran {ran} pipelines.")


def run_specific(pipeline_type: str, user_id: str = None):
    """Run a specific pipeline type manually."""
    modules = get_active_user_modules(pipeline_type)
    if user_id:
        modules = [m for m in modules if str(m.get("userId", "")) == user_id]

    if not modules:
        print(f"[Cron] No active {pipeline_type} modules found")
        return

    for module in modules[:1]:  # Run one at a time
        run_pipeline_for_module(module)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["scheduled", "manual"], default="scheduled")
    parser.add_argument("--pipeline", default=None)
    parser.add_argument("--user_id", default=None)
    args = parser.parse_args()

    if args.mode == "scheduled":
        run_all_scheduled()
    elif args.pipeline:
        run_specific(args.pipeline, args.user_id)
    else:
        print("Specify --pipeline (youtube/instagram) for manual mode")