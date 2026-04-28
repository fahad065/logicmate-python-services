"""
Instagram Graph API uploader for Reels.
Requires: Instagram Business Account + Facebook App + access token.
"""
import os
import time
import requests
from core.config import NESTJS_URL


def upload_reel(
    video_path: str,
    cover_path: str,
    caption: str,
    access_token: str,
    instagram_account_id: str,
    share_to_feed: bool = True,
) -> dict:
    """
    Upload a video as Instagram Reel using Graph API.

    Steps:
    1. Create media container (upload video URL)
    2. Wait for processing
    3. Publish the container

    Returns: {"id": "reel_id", "url": "instagram_url"}
    """
    graph_url = "https://graph.facebook.com/v19.0"

    # Step 1: Create container
    print(f"  [Instagram] Creating Reel container...")
    container_resp = requests.post(
        f"{graph_url}/{instagram_account_id}/reels",
        params={
            "video_url": _get_public_url(video_path),
            "caption": caption,
            "share_to_feed": share_to_feed,
            "cover_url": _get_public_url(cover_path) if cover_path else None,
            "access_token": access_token,
        },
        timeout=60,
    )
    container_resp.raise_for_status()
    container_data = container_resp.json()
    container_id = container_data.get("id")

    if not container_id:
        raise Exception(f"Failed to create container: {container_data}")

    print(f"  [Instagram] Container ID: {container_id} — waiting for processing...")

    # Step 2: Poll until ready
    for attempt in range(20):
        time.sleep(15)
        status_resp = requests.get(
            f"{graph_url}/{container_id}",
            params={
                "fields": "status_code,status",
                "access_token": access_token,
            },
            timeout=20,
        )
        status_data = status_resp.json()
        status_code = status_data.get("status_code", "")

        if status_code == "FINISHED":
            print(f"  [Instagram] ✓ Processing complete")
            break
        elif status_code == "ERROR":
            raise Exception(f"Instagram processing failed: {status_data}")

        if attempt % 4 == 0:
            print(f"  [Instagram] Still processing... ({attempt+1}/20)")
    else:
        raise Exception("Instagram processing timed out")

    # Step 3: Publish
    print(f"  [Instagram] Publishing Reel...")
    publish_resp = requests.post(
        f"{graph_url}/{instagram_account_id}/media_publish",
        params={
            "creation_id": container_id,
            "access_token": access_token,
        },
        timeout=30,
    )
    publish_resp.raise_for_status()
    publish_data = publish_resp.json()
    reel_id = publish_data.get("id")

    if not reel_id:
        raise Exception(f"Failed to publish: {publish_data}")

    reel_url = f"https://www.instagram.com/reel/{reel_id}/"
    print(f"  [Instagram] ✓ Published: {reel_url}")

    return {"id": reel_id, "url": reel_url}


def get_long_lived_token(short_token: str, app_id: str, app_secret: str) -> str:
    """Exchange short-lived token for long-lived token (60 days)."""
    resp = requests.get(
        "https://graph.facebook.com/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("access_token", "")


def _get_public_url(file_path: str) -> str:
    """
    Get a public URL for the file.
    In production: upload to S3/Cloudflare R2 and return URL.
    For now: uses ngrok tunnel if available.
    """
    ngrok_domain = os.getenv("NGROK_DOMAIN", "")
    if ngrok_domain:
        filename = os.path.basename(file_path)
        # Serve files via a simple file server (add to main.py)
        return f"https://{ngrok_domain}/files/{filename}"

    # Fallback: direct file path (only works if server is publicly accessible)
    raise Exception(
        "No public URL available. Set NGROK_DOMAIN or configure S3 bucket "
        "for Instagram upload. Instagram requires a public video URL."
    )


def validate_token(access_token: str, instagram_account_id: str) -> bool:
    """Validate Instagram access token."""
    try:
        resp = requests.get(
            f"https://graph.facebook.com/v19.0/{instagram_account_id}",
            params={"fields": "id,name", "access_token": access_token},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False