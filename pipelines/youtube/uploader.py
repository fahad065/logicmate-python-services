"""
YouTube Data API v3 uploader.
Fetches OAuth tokens from NestJS API (stored in MongoDB).
No token.pickle needed — works for any user.
"""
import os
import requests as http_requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from core.config import NESTJS_URL, ADMIN_EMAIL, ADMIN_PASSWORD


def _get_admin_token() -> str:
    """Get NestJS admin JWT token."""
    try:
        resp = http_requests.post(f"{NESTJS_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        }, timeout=15)
        return resp.json().get("accessToken", "")
    except Exception as e:
        print(f"  [YouTube] Auth failed: {e}")
        return ""


def _get_youtube_service(user_id: str):
    """Build authenticated YouTube service using tokens from NestJS."""
    admin_token = _get_admin_token()
    if not admin_token:
        raise Exception("Failed to get admin token from NestJS")

    # Fetch user's YouTube tokens from NestJS
    resp = http_requests.get(
        f"{NESTJS_URL}/auth/youtube/tokens/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )

    if resp.status_code != 200:
        raise Exception(f"Failed to fetch YouTube tokens: {resp.text}")

    token_data = resp.json()
    print(f"  [YouTube] Token data received for user {user_id[:8]}")

    # Build Google credentials from stored tokens
    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=[
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube",
        ],
    )

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        print(f"  [YouTube] Refreshing expired token...")
        creds.refresh(Request())

    return build("youtube", "v3", credentials=creds)


def upload_to_youtube(
    video_path: str,
    thumbnail_path: str,
    title: str,
    description: str,
    tags: list,
    user_id: str,
    category_id: str = "22",
    privacy: str = "public",
) -> dict:
    """Upload main video to YouTube."""
    print(f"  [YouTube] Uploading: {title[:50]}...")

    youtube = _get_youtube_service(user_id)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:500],
            "categoryId": category_id,
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=50 * 1024 * 1024,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            if pct % 20 == 0:
                print(f"  [YouTube] Upload progress: {pct}%", flush=True)

    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"  [YouTube] ✓ Uploaded: {video_url}")

    # Set thumbnail
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
            ).execute()
            print(f"  [YouTube] ✓ Thumbnail set")
        except Exception as e:
            print(f"  [YouTube] Thumbnail upload failed (non-critical): {e}")

    return {"id": video_id, "url": video_url}


def upload_short(
    video_path: str,
    title: str,
    description: str,
    tags: list,
    user_id: str,
    privacy: str = "public",
) -> dict:
    """Upload a YouTube Short."""
    short_title = f"{title[:90]} #Shorts"
    short_desc  = f"{description}\n\n#Shorts #Short"

    return upload_to_youtube(
        video_path=video_path,
        thumbnail_path=None,
        title=short_title,
        description=short_desc,
        tags=tags + ["Shorts", "Short"],
        user_id=user_id,
        privacy=privacy,
    )