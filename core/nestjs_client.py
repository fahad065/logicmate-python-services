# core/nestjs_client.py — v3
# Handles all NestJS API calls from Python pipeline

import os
import requests
from typing import Optional

NESTJS_BASE = os.getenv("NESTJS_API_URL", "https://api.logicmate.io")
API_SECRET  = os.getenv("PIPELINE_SECRET", "")

HEADERS = {
    "Content-Type": "application/json",
    "x-pipeline-secret": API_SECRET,
}


def update_pipeline_step(run_id: str, step: int, label: str) -> None:
    """Update current step in pipeline run."""
    try:
        requests.patch(
            f"{NESTJS_BASE}/pipeline-runs/{run_id}/status",
            json={"currentStep": step, "stepLabel": label, "status": "running"},
            headers=HEADERS, timeout=8,
        )
    except Exception as e:
        print(f"[NestJS] update_step failed: {e}", flush=True)


def append_log(run_id: str, message: str) -> None:
    """Append log line to pipeline run."""
    if not run_id:
        return
    try:
        requests.patch(
            f"{NESTJS_BASE}/pipeline-runs/{run_id}/log",
            json={"message": message},
            headers=HEADERS, timeout=8,
        )
    except Exception as e:
        print(f"[NestJS] append_log failed: {e}", flush=True)


def complete_pipeline_run(
    run_id: str,
    youtube_url: str = "",
    title: str = "",
    cost: float = 0,
) -> bool:
    """Mark pipeline run as completed."""
    try:
        resp = requests.patch(
            f"{NESTJS_BASE}/pipeline-runs/{run_id}/status",
            json={
                "status": "completed",
                "youtubeUrl": youtube_url,
                "title": title,
                "cost": cost,
            },
            headers=HEADERS, timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[NestJS] complete_pipeline_run failed: {e}", flush=True)
        return False


def fail_pipeline_run(run_id: str, error: str) -> bool:
    """Mark pipeline run as failed."""
    try:
        resp = requests.patch(
            f"{NESTJS_BASE}/pipeline-runs/{run_id}/status",
            json={"status": "failed", "errorMessage": error[:500]},
            headers=HEADERS, timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[NestJS] fail_pipeline_run failed: {e}", flush=True)
        return False


def notify_complete(
    run_id: str,
    user_id: str,
    title: str,
    youtube_url: str,
) -> None:
    """Notify NestJS to send pipeline complete email + notification."""
    try:
        requests.post(
            f"{NESTJS_BASE}/pipeline-runs/{run_id}/notify-complete",
            json={"userId": user_id, "title": title, "youtubeUrl": youtube_url},
            headers=HEADERS, timeout=10,
        )
    except Exception as e:
        print(f"[NestJS] notify_complete failed: {e}", flush=True)


def notify_failed(run_id: str, user_id: str, error: str) -> None:
    """Notify NestJS to send pipeline failed email + notification."""
    try:
        requests.post(
            f"{NESTJS_BASE}/pipeline-runs/{run_id}/notify-failed",
            json={"userId": user_id, "error": error[:300]},
            headers=HEADERS, timeout=10,
        )
    except Exception as e:
        print(f"[NestJS] notify_failed failed: {e}", flush=True)