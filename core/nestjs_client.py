"""
NestJS API client — shared across all pipelines.
Handles auth, pipeline run updates, notifications.
"""
import os
import requests

NESTJS_URL     = os.getenv("NESTJS_URL", "http://localhost:4000/api/v1")
ADMIN_EMAIL    = os.getenv("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# Cache token to avoid re-login on every call
_cached_token = None


def get_auth_headers() -> dict:
    global _cached_token
    if _cached_token:
        return {"Authorization": f"Bearer {_cached_token}"}
    try:
        resp = requests.post(
            f"{NESTJS_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            print(f"[NestJS] Login failed ({resp.status_code})", flush=True)
            return {}
        data = resp.json()
        token = data.get("accessToken") or data.get("access_token") or data.get("token")
        if not token:
            return {}
        _cached_token = token
        print(f"[NestJS] ✓ Admin authenticated", flush=True)
        return {"Authorization": f"Bearer {token}"}
    except Exception as e:
        print(f"[NestJS] Auth error: {e}", flush=True)
        return {}


def update_pipeline_step(run_id: str, step: int, label: str = "") -> bool:
    """Update pipeline step progress."""
    if not run_id:
        return False
    try:
        headers = get_auth_headers()
        if not headers:
            return False
        resp = requests.patch(
            f"{NESTJS_URL}/pipeline-runs/{run_id}/status",
            json={"status": "running", "currentStep": step, "stepLabel": label},
            headers=headers,
            timeout=10,
        )
        return resp.status_code < 300
    except Exception as e:
        print(f"[NestJS] Step update error: {e}", flush=True)
        return False


def complete_pipeline_run(run_id: str, youtube_url: str = "", title: str = "", cost: float = 0) -> bool:
    """Mark pipeline run as complete."""
    if not run_id:
        return False
    try:
        headers = get_auth_headers()
        if not headers:
            return False
        resp = requests.patch(
            f"{NESTJS_URL}/pipeline-runs/{run_id}/status",
            json={
                "status": "complete",
                "youtubeUrl": youtube_url,
                "title": title,
                "totalCost": cost,
            },
            headers=headers,
            timeout=10,
        )
        print(f"[NestJS] ✓ Run marked complete", flush=True)
        return resp.status_code < 300
    except Exception as e:
        print(f"[NestJS] Complete error: {e}", flush=True)
        return False


def fail_pipeline_run(run_id: str, error: str) -> bool:
    """Mark pipeline run as failed."""
    if not run_id:
        return False
    try:
        headers = get_auth_headers()
        if not headers:
            return False
        resp = requests.patch(
            f"{NESTJS_URL}/pipeline-runs/{run_id}/status",
            json={"status": "failed", "errorMessage": error[:500]},
            headers=headers,
            timeout=10,
        )
        print(f"[NestJS] ✓ Run marked failed", flush=True)
        return resp.status_code < 300
    except Exception as e:
        print(f"[NestJS] Fail error: {e}", flush=True)
        return False


def notify_complete(run_id: str, user_id: str, title: str, url: str):
    """Send pipeline complete notification."""
    try:
        headers = get_auth_headers()
        if not headers:
            return
        requests.post(
            f"{NESTJS_URL}/notifications",
            json={
                "userId": user_id,
                "type": "pipeline_complete",
                "title": "🎬 Video uploaded!",
                "message": f'"{title}" is now live on YouTube.',
                "actionUrl": url,
                "icon": "✅",
                "sendEmail": True,
            },
            headers=headers,
            timeout=10,
        )
        print(f"[NestJS] ✓ Notification sent", flush=True)
    except Exception as e:
        print(f"[NestJS] Notify error: {e}", flush=True)


def notify_failed(run_id: str, user_id: str, error: str):
    """Send pipeline failure notification."""
    try:
        headers = get_auth_headers()
        if not headers:
            return
        requests.post(
            f"{NESTJS_URL}/notifications",
            json={
                "userId": user_id,
                "type": "pipeline_failed",
                "title": "❌ Pipeline failed",
                "message": f"Error: {error[:200]}. Please try again.",
                "actionUrl": "/dashboard/pipeline-logs",
                "icon": "❌",
                "sendEmail": True,
            },
            headers=headers,
            timeout=10,
        )
    except Exception as e:
        print(f"[NestJS] Notify failed error: {e}", flush=True)