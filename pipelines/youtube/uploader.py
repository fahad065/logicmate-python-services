"""
YouTube Data API v3 uploader.
Handles video + shorts upload with OAuth2 token.
Token file path updated to work from any directory.
"""
import os
import pickle
import datetime
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from core.config import NESTJS_URL

# Token lives in python-services root (not pipelines/youtube/)
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOKEN_PATH = os.path.join(BASE_DIR, "token.pickle")


def _get_youtube_service():
    """Build authenticated YouTube service from token.pickle."""
    if not os.path.exists(TOKEN_PATH):
        raise Exception(
            f"token.pickle not found at {TOKEN_PATH}. "
            "Run get_youtube_token.py first to authenticate."
        )
    with open(TOKEN_PATH, "rb") as f:
        creds = pickle.load(f)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


def upload_to_youtube(
    video_path: str,
    thumbnail_path: str,
    title: str,
    description: str,
    tags: list[str],
    category_id: str = "22",
    privacy: str = "public",
) -> dict:
    """Upload main video to YouTube."""
    print(f"  [YouTube] Uploading: {title[:50]}...")

    youtube = _get_youtube_service()

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
                print(f"  [YouTube] Upload progress: {pct}%")

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
            print(f"  [YouTube] Thumbnail failed (non-critical): {e}")

    return {"id": video_id, "url": video_url}


def upload_short(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    privacy: str = "public",
) -> dict:
    """Upload a YouTube Short."""
    # Add #Shorts to make it discoverable
    short_title = f"{title[:90]} #Shorts"
    short_desc  = f"{description}\n\n#Shorts #Short"

    return upload_to_youtube(
        video_path=video_path,
        thumbnail_path=None,
        title=short_title,
        description=short_desc,
        tags=tags + ["Shorts", "Short"],
        privacy=privacy,
    )