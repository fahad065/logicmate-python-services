"""
Shared utilities — file management, metadata, cleanup.
"""
import os
import glob
import json
import shutil
import datetime


def load_metadata(folder_path: str) -> dict:
    path = os.path.join(folder_path, "metadata.json")
    with open(path, 'r') as f:
        return json.load(f)


def save_metadata(folder_path: str, metadata: dict):
    path = os.path.join(folder_path, "metadata.json")
    with open(path, 'w') as f:
        json.dump(metadata, f, indent=2)


def normalize(s: str) -> str:
    """Remove non-breaking spaces and unicode issues."""
    if not s:
        return ""
    return (
        str(s)
        .replace('\xa0', ' ')
        .replace('\u200b', '')
        .replace('\u00a0', ' ')
        .strip()
    )


def create_run_folder(output_base: str, pipeline_type: str, user_id: str) -> str:
    """Create timestamped folder for this pipeline run."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{pipeline_type}_{user_id[:8]}_{ts}"
    folder_path = os.path.join(output_base, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


def find_resumable_folder(output_base: str, pipeline_type: str, user_id: str) -> str | None:
    """
    Find an existing incomplete pipeline folder.
    Prevents Atlas over-billing by resuming instead of restarting.
    """
    if not os.path.exists(output_base):
        return None

    pattern = os.path.join(output_base, f"{pipeline_type}_{user_id[:8]}_*")
    folders = sorted(glob.glob(pattern), reverse=True)

    for folder in folders:
        metadata_path = os.path.join(folder, "metadata.json")
        if not os.path.exists(metadata_path):
            continue
        try:
            with open(metadata_path) as f:
                meta = json.load(f)
            status = meta.get("status", "")
            # Only resume if not completed/failed
            if status not in ["uploaded", "complete", "failed"]:
                print(f"[Resume] Found resumable folder: {folder} (status={status})")
                return folder
        except Exception:
            continue
    return None


def cleanup_large_files(folder_path: str):
    """
    Delete large video/audio files after successful upload.
    Keeps metadata.json, thumbnail, script for records.
    Saves ~1.5GB per video.
    """
    keep_extensions = {".json", ".txt", ".jpg", ".jpeg", ".png"}
    keep_files = {"metadata.json", "script.txt", "thumbnail.jpg", "cover.jpg"}

    removed_mb = 0
    for fname in os.listdir(folder_path):
        fpath = os.path.join(folder_path, fname)
        ext = os.path.splitext(fname)[1].lower()
        if fname in keep_files or ext in keep_extensions:
            continue
        try:
            size_mb = os.path.getsize(fpath) / (1024 * 1024)
            os.remove(fpath)
            removed_mb += size_mb
        except Exception:
            pass

    print(f"[Cleanup] Freed {removed_mb:.1f} MB")


def get_file_size_mb(path: str) -> float:
    try:
        return os.path.getsize(path) / (1024 * 1024)
    except Exception:
        return 0.0