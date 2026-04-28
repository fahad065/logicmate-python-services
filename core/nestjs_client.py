"""
NestJS API client — shared across all pipelines.
Handles auth, pipeline run updates, notifications.
"""
import requests
from core.config import NESTJS_URL, NESTJS_TOKEN, ADMIN_EMAIL, ADMIN_PASSWORD


def get_auth_headers() -> dict:
    """Use service token if available, otherwise login."""
    if NESTJS_TOKEN:
        return {"Authorization": f"Bearer {NESTJS_TOKEN}"}
    # Fallback: login with admin credentials
    try:
        resp = requests.post(f"{NESTJS_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        }, timeout=15)
        token = resp.json().get("accessToken", "")
        return {"Authorization": f"Bearer {token}"}
    except Exception as e:
        print(f"[NestJS] Auth failed: {e}")
        return {}


def update_pipeline_run(run_id: str, data: dict) -> bool:
    """Update a pipeline run record in NestJS."""
    try:
        headers = get_auth_headers()
        resp = requests.patch(
            f"{NESTJS_URL}/pipeline-runs/{run_id}",
            json=data,
            headers=headers,
            timeout=15,
        )
        return resp.status_code < 300
    except Exception as e:
        print(f"[NestJS] Pipeline update failed: {e}")
        return False


def create_pipeline_run(data: dict) -> dict | None:
    """Create a new pipeline run record."""
    try:
        headers = get_auth_headers()
        resp = requests.post(
            f"{NESTJS_URL}/pipeline-runs",
            json=data,
            headers=headers,
            timeout=15,
        )
        return resp.json() if resp.status_code < 300 else None
    except Exception as e:
        print(f"[NestJS] Create pipeline run failed: {e}")
        return None


def notify_complete(run_id: str, user_id: str, title: str, url: str):
    """Send pipeline complete notification."""
    try:
        headers = get_auth_headers()
        requests.post(
            f"{NESTJS_URL}/notifications",
            json={
                "userId": user_id,
                "type": "pipeline_complete",
                "title": "Pipeline completed ✅",
                "message": f'"{title}" has been uploaded successfully.',
                "actionUrl": url,
                "icon": "✅",
                "sendEmail": True,
            },
            headers=headers,
            timeout=10,
        )
    except Exception as e:
        print(f"[NestJS] Notify complete failed: {e}")


def notify_failed(run_id: str, user_id: str, error: str):
    """Send pipeline failure notification."""
    try:
        headers = get_auth_headers()
        requests.post(
            f"{NESTJS_URL}/notifications",
            json={
                "userId": user_id,
                "type": "pipeline_failed",
                "title": "Pipeline failed ❌",
                "message": f"Error: {error[:200]}",
                "actionUrl": "/dashboard/pipeline-logs",
                "icon": "❌",
                "sendEmail": True,
            },
            headers=headers,
            timeout=10,
        )
    except Exception as e:
        print(f"[NestJS] Notify failed error: {e}")


def get_user_module(user_id: str, pipeline_type: str) -> dict | None:
    """Fetch active user module config for a pipeline type."""
    try:
        headers = get_auth_headers()
        resp = requests.get(
            f"{NESTJS_URL}/usermodules/my?moduleType=agent",
            headers=headers,
            timeout=10,
        )
        if resp.status_code < 300:
            modules = resp.json().get("data", [])
            for m in modules:
                if m.get("pipelineType") == pipeline_type:
                    if m.get("status") in ["active", "trial"]:
                        return m
    except Exception as e:
        print(f"[NestJS] Get user module failed: {e}")
    return None