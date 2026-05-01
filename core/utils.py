"""
Shared utilities — folder management, metadata, cleanup.
"""
import os
import json
import shutil
import datetime


def create_run_folder(base_dir: str, pipeline_type: str, user_id: str) -> str:
    """Create a new timestamped output folder."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uid = user_id[:8] if user_id else "unknown"
    folder_name = f"{pipeline_type}_{short_uid}_{timestamp}"
    folder_path = os.path.join(base_dir, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    print(f"[Utils] Created folder: {folder_path}", flush=True)
    return folder_path


def find_resumable_folder(base_dir: str, pipeline_type: str, user_id: str) -> str | None:
    """
    Find most recent incomplete run folder for this user.
    Only resume if:
    - Folder exists
    - Has metadata.json
    - Status is not 'uploaded', 'complete', or 'failed'
    - Less than 2 hours old (Railway clears /tmp on restart)
    """
    if not os.path.exists(base_dir):
        return None

    short_uid = user_id[:8] if user_id else "unknown"
    prefix = f"{pipeline_type}_{short_uid}_"
    now = datetime.datetime.now()

    candidates = []
    for name in os.listdir(base_dir):
        if not name.startswith(prefix):
            continue
        folder_path = os.path.join(base_dir, name)
        meta_path = os.path.join(folder_path, "metadata.json")
        if not os.path.exists(meta_path):
            continue

        # Check age — Railway /tmp is cleared on restart
        try:
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(meta_path))
            age_hours = (now - mtime).total_seconds() / 3600
            if age_hours > 2:
                continue
        except Exception:
            continue

        # Check status
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            status = meta.get("status", "")
            if status in ("uploaded", "complete", "failed", "success"):
                continue
        except Exception:
            continue

        candidates.append((folder_path, os.path.getmtime(meta_path)))

    if not candidates:
        return None

    # Return most recent
    candidates.sort(key=lambda x: x[1], reverse=True)
    folder = candidates[0][0]
    print(f"[Utils] Found resumable folder: {folder}", flush=True)
    return folder


def save_metadata(folder_path: str, metadata: dict) -> None:
    """Save pipeline metadata to JSON."""
    meta_path = os.path.join(folder_path, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)


def load_metadata(folder_path: str) -> dict:
    """Load pipeline metadata from JSON."""
    meta_path = os.path.join(folder_path, "metadata.json")
    if not os.path.exists(meta_path):
        return {}
    with open(meta_path) as f:
        return json.load(f)


def cleanup_large_files(folder_path: str, delete_all: bool = False) -> None:
    """
    Production (delete_all=True): delete entire output folder after upload.
    Local: keep metadata, script, thumbnail for records.
    """
    is_production = os.getenv("NODE_ENV") == "production" or delete_all

    if is_production:
        try:
            shutil.rmtree(folder_path, ignore_errors=True)
            print(f"[Cleanup] ✓ Deleted folder: {folder_path}", flush=True)
        except Exception as e:
            print(f"[Cleanup] Failed to delete: {e}", flush=True)
        return

    # Local — keep important files
    keep_extensions = {".json", ".txt", ".jpg", ".jpeg", ".png"}
    keep_files = {"metadata.json", "script.txt", "thumbnail.jpg"}
    removed_mb = 0.0

    for fname in os.listdir(folder_path):
        fpath = os.path.join(folder_path, fname)
        ext = os.path.splitext(fname)[1].lower()
        if fname in keep_files or ext in keep_extensions:
            continue
        try:
            if os.path.isfile(fpath):
                removed_mb += os.path.getsize(fpath) / (1024 * 1024)
                os.remove(fpath)
            elif os.path.isdir(fpath):
                shutil.rmtree(fpath)
        except Exception:
            pass

    print(f"[Cleanup] Freed {removed_mb:.1f} MB", flush=True)