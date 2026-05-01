"""
NestJS API client — shared across all pipelines.
Handles auth, pipeline run updates, notifications.
"""
import os
import requests
from core.config import NESTJS_URL, ADMIN_EMAIL, ADMIN_PASSWORD

# Cache admin token to avoid re-login on every call
_cached_token = None


def get_auth_headers() -> dict:
    """Login with admin credentials and cache token."""
    global _cached_token

    if _cached_token:
        return {"Authorization": f"Bearer {_cached_token}"}

    try:
        print(f"[NestJS] Logging in as admin...", flush=True)
        resp = requests.post(
            f"{NESTJS_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            print(f"[NestJS] Login failed ({resp.status_code}): {resp.text[:100]}", flush=True)
            return {}

        data = resp.json()
        token = data.get("accessToken") or data.get("access_token") or data.get("token")
        if not token:
            print(f"[NestJS] No token in response: {list(data.keys())}", flush=True)
            return {}

        _cached_token = token
        print(f"[NestJS] ✓ Admin authenticated", flush=True)
        return {"Authorization": f"Bearer {token}"}

    except Exception as e:
        print(f"[NestJS] Auth error: {e}", flush=True)
        return {}


def create_pipeline_run(data: dict) -> dict | None:
    """Create a new pipeline run record in NestJS."""
    try:
        headers = get_auth_headers()
        if not headers:
            return None
        resp = requests.post(
            f"{NESTJS_URL}/pipeline-runs",
            json=data,
            headers=headers,
            timeout=15,
        )
        if resp.status_code < 300:
            result = resp.json()
            print(f"[NestJS] ✓ Pipeline run created: {result.get('_id', 'unknown')}", flush=True)
            return result
        else:
            print(f"[NestJS] Create run failed ({resp.status_code}): {resp.text[:100]}", flush=True)
            return None
    except Exception as e:
        print(f"[NestJS] Create pipeline run error: {e}", flush=True)
        return None


def update_pipeline_run(run_id: str, data: dict) -> bool:
    """Update a pipeline run record in NestJS."""
    if not run_id:
        return False
    try:
        headers = get_auth_headers()
        if not headers:
            return False
        resp = requests.patch(
            f"{NESTJS_URL}/pipeline-runs/{run_id}/status",
            json=data,
            headers=headers,
            timeout=15,
        )
        return resp.status_code < 300
    except Exception as e:
        print(f"[NestJS] Update pipeline run error: {e}", flush=True)
        return False


def notify_complete(run_id: str, user_id: str, title: str, url: str):
    """Send pipeline complete notification to user."""
    try:
        headers = get_auth_headers()
        if not headers:
            return
        requests.post(
            f"{NESTJS_URL}/notifications",
            json={
                "userId": user_id,
                "type": "pipeline_complete",
                "title": "🎬 Video uploaded successfully!",
                "message": f'"{title}" is now live on YouTube.',
                "actionUrl": url,
                "icon": "✅",
                "sendEmail": True,
            },
            headers=headers,
            timeout=10,
        )
        print(f"[NestJS] ✓ Complete notification sent", flush=True)
    except Exception as e:
        print(f"[NestJS] Notify complete error: {e}", flush=True)


def notify_failed(run_id: str, user_id: str, error: str):
    """Send pipeline failure notification to user."""
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
                "message": f"Error: {error[:200]}. Please try again or contact support.",
                "actionUrl": "/dashboard/pipeline-logs",
                "icon": "❌",
                "sendEmail": True,
            },
            headers=headers,
            timeout=10,
        )
        print(f"[NestJS] ✓ Failure notification sent", flush=True)
    except Exception as e:
        print(f"[NestJS] Notify failed error: {e}", flush=True)