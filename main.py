"""
LogicMate Python Services — Main Entry Point
============================================
Handles pipeline execution requests from NestJS backend.
Supports: youtube, instagram (more coming)
"""
import os
import sys
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="LogicMate Pipeline Service", version="2.0.0")

NESTJS_TOKEN = os.getenv("NESTJS_SERVICE_TOKEN", "")

# Thread pool for background pipeline execution
executor = ThreadPoolExecutor(max_workers=3)


# ── Request models ────────────────────────────────────────────
class PipelineRequest(BaseModel):
    pipeline_type: str
    user_id: str
    niche: str
    user_module_id: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    instagram_account_id: Optional[str] = None
    instagram_access_token: Optional[str] = None
    custom_prompt: Optional[str] = None      # ← ADD
    use_custom_prompt: bool = False           # ← ADD
    run_id: Optional[str] = None              # ← ADD
    video_model: Optional[str] = "auto"   # ← add



class PipelineResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None


# ── Auth ──────────────────────────────────────────────────────
def verify_token(authorization: str = Header(None)):
    if not NESTJS_TOKEN:
        return True
    if not authorization or authorization != f"Bearer {NESTJS_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


# ── Health ────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "logicmate-pipelines",
        "version": "2.0.0"
    }


# ── Pipeline run — returns immediately, runs in background ────
@app.post("/pipeline/run", response_model=PipelineResponse)
async def run_pipeline(req: PipelineRequest, authorization: str = Header(None)):
    verify_token(authorization)
 
    print(f"\n[Main] Pipeline request: {req.pipeline_type} for user {req.user_id}", flush=True)
 
    if req.pipeline_type not in ["youtube", "instagram"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown pipeline: {req.pipeline_type}. Supported: youtube, instagram"
        )
 
    if req.pipeline_type == "instagram":
        if not req.instagram_account_id or not req.instagram_access_token:
            raise HTTPException(
                status_code=400,
                detail="instagram_account_id and instagram_access_token are required"
            )
 
    # Capture all values before thread starts
    pipeline_type   = req.pipeline_type
    user_id         = req.user_id
    niche           = req.niche
    user_module_id  = req.user_module_id
    yt_channel_id   = req.youtube_channel_id
    ig_account_id   = req.instagram_account_id
    ig_access_token = req.instagram_access_token
 
    def run_in_background():
        import sys
        try:
            print(f"[Background] ━━━ Starting {pipeline_type} pipeline for user {user_id} ━━━", flush=True)
            sys.stdout.flush()
 
            if pipeline_type == "youtube":
                from pipelines.youtube.pipeline import run_youtube_pipeline
                result = run_youtube_pipeline(
                    user_id=user_id,
                    niche=niche,
                    youtube_channel_id=yt_channel_id,
                    user_module_id=user_module_id,
                    run_id=req.run_id,          # ← add
                    custom_prompt=req.custom_prompt,     # ← add
                    use_custom_prompt=req.use_custom_prompt,  # ← add
                    video_model=req.video_model,   # ← add
                )
 
            elif pipeline_type == "instagram":
                from pipelines.instagram.pipeline import run_instagram_pipeline
                result = run_instagram_pipeline(
                    user_id=user_id,
                    niche=niche,
                    instagram_account_id=ig_account_id,
                    access_token=ig_access_token,
                    user_module_id=user_module_id,
                )
 
            print(f"[Background] ✓ Pipeline completed: {result.get('status')}", flush=True)
            sys.stdout.flush()
 
        except Exception as e:
            import traceback
            print(f"[Background] ❌ Pipeline error: {e}", flush=True)
            print(traceback.format_exc(), flush=True)
            sys.stdout.flush()
 
    # Start background thread
    import threading
    thread = threading.Thread(target=run_in_background, daemon=True)
    thread.start()
    print(f"[Main] Background thread started for {pipeline_type}", flush=True)
 
    return PipelineResponse(
        status="started",
        message=f"{pipeline_type} pipeline started in background",
        data={"user_id": user_id, "pipeline_type": pipeline_type},
    )


# ── Pipeline status ───────────────────────────────────────────
@app.get("/pipeline/status/{run_id}")
def get_pipeline_status(run_id: str, authorization: str = Header(None)):
    verify_token(authorization)
    from core.config import OUTPUT_BASE
    import glob, json

    pattern = os.path.join(OUTPUT_BASE, f"*{run_id}*", "metadata.json")
    matches = glob.glob(pattern)
    if not matches:
        raise HTTPException(status_code=404, detail="Run not found")

    with open(matches[0]) as f:
        metadata = json.load(f)

    return {
        "run_id": run_id,
        "status": metadata.get("status"),
        "pipeline_type": metadata.get("pipeline_type"),
        "title": metadata.get("title") or metadata.get("topic"),
        "youtube_url": metadata.get("youtube_url"),
        "reel_url": metadata.get("reel_url"),
        "error": metadata.get("error"),
    }


# ── CLI mode ──────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LogicMate Pipeline Runner")
    parser.add_argument("--pipeline", required=True, choices=["youtube", "instagram"])
    parser.add_argument("--user_id", required=True)
    parser.add_argument("--niche", default=os.getenv("NICHE", "dark psychology"))
    parser.add_argument("--instagram_account_id", default="")
    parser.add_argument("--instagram_token", default="")
    parser.add_argument("--user_module_id", default="")
    args = parser.parse_args()

    if args.pipeline == "youtube":
        from pipelines.youtube.pipeline import run_youtube_pipeline
        result = run_youtube_pipeline(
            user_id=user_id,
            niche=niche,
            youtube_channel_id=yt_channel_id,
            user_module_id=user_module_id,
            run_id=req.run_id,          # ← add
            custom_prompt=req.custom_prompt,     # ← add
            use_custom_prompt=req.use_custom_prompt,  # ← add
        )
    elif args.pipeline == "instagram":
        from pipelines.instagram.pipeline import run_instagram_pipeline
        result = run_instagram_pipeline(
            user_id=args.user_id,
            niche=args.niche,
            instagram_account_id=args.instagram_account_id,
            access_token=args.instagram_token,
            user_module_id=args.user_module_id or None,
        )

    print(f"\nResult: {result}")