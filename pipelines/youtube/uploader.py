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


def _get_nestjs_url() -> str:
    return os.getenv("NESTJS_URL", "http://localhost:4000/api/v1")


def _get_admin_token() -> str:
    """Get NestJS admin JWT token."""
    nestjs_url = _get_nestjs_url()
    admin_email    = os.getenv("ADMIN_EMAIL", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")

    print(f"  [YouTube] Logging in as admin: {admin_email[:20]}...", flush=True)
    print(f"  [YouTube] NestJS URL: {nestjs_url}", flush=True)

    if not admin_email or not admin_password:
        raise Exception("ADMIN_EMAIL or ADMIN_PASSWORD env vars not set in Railway")

    try:
        resp = http_requests.post(
            f"{nestjs_url}/auth/login",
            json={"email": admin_email, "password": admin_password},
            timeout=30,
        )
        print(f"  [YouTube] Login response status: {resp.status_code}", flush=True)

        if resp.status_code != 200 and resp.status_code != 201:
            raise Exception(f"Login failed ({resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        token = data.get("accessToken") or data.get("access_token") or data.get("token")

        if not token:
            raise Exception(f"No token in login response: {list(data.keys())}")

        print(f"  [YouTube] ✓ Admin token obtained", flush=True)
        return token

    except Exception as e:
        raise Exception(f"Failed to get admin token from NestJS: {e}")


def _get_youtube_service(user_id: str):
    """Build authenticated YouTube service using tokens from NestJS."""
    nestjs_url  = _get_nestjs_url()
    admin_token = _get_admin_token()

    print(f"  [YouTube] Fetching tokens for user {user_id[:8]}...", flush=True)

    resp = http_requests.get(
        f"{nestjs_url}/auth/youtube/tokens/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )

    print(f"  [YouTube] Token fetch status: {resp.status_code}", flush=True)

    if resp.status_code != 200:
        raise Exception(
            f"Failed to fetch YouTube tokens (status {resp.status_code}): {resp.text[:300]}"
        )

    token_data = resp.json()

    access_token  = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    if not access_token:
        raise Exception(f"No access_token in response. Keys: {list(token_data.keys())}")

    print(f"  [YouTube] ✓ Tokens received for channel: {token_data.get('channel_title', 'unknown')}", flush=True)

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
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
        print(f"  [YouTube] Refreshing expired token...", flush=True)
        creds.refresh(Request())

    return build("youtube", "v3", credentials=creds)


def upload_to_youtube(
    video_path: str,
    thumbnail_path: str,
    title: str,
    description: str,
    tags: list,
    user_id: str,
) -> dict:
    """Upload video to YouTube with full SEO metadata."""
    print(f"  [YouTube] Uploading: {title[:50]}...", flush=True)
 
    credentials = get_user_credentials(user_id)
 
    youtube = build("youtube", "v3", credentials=credentials)
 
    # Ensure tags are within YouTube limits (500 chars total)
    tag_str = ""
    final_tags = []
    for tag in tags:
        if len(tag_str) + len(tag) + 2 <= 490:
            final_tags.append(tag)
            tag_str += tag + ", "
        else:
            break
 
    print(f"  [YouTube] Using {len(final_tags)} tags ({len(tag_str)} chars)", flush=True)
 
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": final_tags,
            "categoryId": "22",  # People & Blogs
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        }
    }
 
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=5 * 1024 * 1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
 
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  [YouTube] Upload progress: {int(status.progress() * 100)}%", flush=True)
 
    video_id  = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"  [YouTube] ✓ Uploaded: {video_url}", flush=True)
 
    # Set thumbnail
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
            ).execute()
            print(f"  [YouTube] ✓ Thumbnail set", flush=True)
        except Exception as e:
            print(f"  [YouTube] Thumbnail failed (non-critical): {e}", flush=True)
 
    return {"id": video_id, "url": video_url}
 
 
def upload_short(
    video_path: str,
    title: str,
    description: str,
    tags: list,
    user_id: str,
) -> dict:
    """Upload YouTube Short with SEO metadata."""
    print(f"  [YouTube] Uploading Short: {title[:50]}...", flush=True)
 
    credentials = get_user_credentials(user_id)
    youtube = build("youtube", "v3", credentials=credentials)
 
    # Add Shorts-specific tags
    shorts_tags = tags[:30] + ["Shorts", "YouTubeShorts", "Short", "Viral", "DarkPsychology"]
 
    # Shorts description — add #Shorts at start for algorithm
    shorts_description = f"#Shorts #YouTubeShorts\n\n{description[:400]}\n\n#Psychology #DarkPsychology #HumanBehavior #Viral #Trending"
 
    body = {
        "snippet": {
            "title": f"{title[:80]} #Shorts",
            "description": shorts_description,
            "tags": shorts_tags,
            "categoryId": "22",
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        }
    }
 
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
 
    response = None
    while response is None:
        _, response = request.next_chunk()
 
    video_id  = response["id"]
    video_url = f"https://www.youtube.com/shorts/{video_id}"
    print(f"  [YouTube] ✓ Short uploaded: {video_url}", flush=True)
    return {"id": video_id, "url": video_url}