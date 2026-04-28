"""
NexAgent Python Services — Main Entry Point
============================================
Handles pipeline execution requests from NestJS backend.
Supports: youtube, instagram (more coming)

Run:
    python main.py --pipeline youtube --user_id xxx --niche "dark psychology"
    python main.py --pipeline instagram --user_id xxx --niche "fitness"

Or via HTTP (FastAPI):
    uvicorn main:app --port 8001
"""
import os
import sys
import argparse
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="NexAgent Pipeline Service", version="2.0.0")

NESTJS_TOKEN = os.getenv("NESTJS_SERVICE_TOKEN", "")


# ── Request models ────────────────────────────────────────────
class PipelineRequest(BaseModel):
    pipeline_type: str          # "youtube" | "instagram"
    user_id: str
    niche: str
    user_module_id: Optional[str] = None
    # YouTube specific
    youtube_channel_id: Optional[str] = None
    # Instagram specific
    instagram_account_id: Optional[str] = None
    instagram_access_token: Optional[str] = None


class PipelineResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None


# ── Auth ──────────────────────────────────────────────────────
def verify_token(authorization: str = Header(None)):
    if not NESTJS_TOKEN:
        return True  # No token configured = skip auth (dev mode)
    if not authorization or authorization != f"Bearer {NESTJS_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


# ── Routes ────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "nexagent-pipelines", "version": "2.0.0"}


@app.post("/pipeline/run", response_model=PipelineResponse)
async def run_pipeline(req: PipelineRequest, authorization: str = Header(None)):
    verify_token(authorization)

    print(f"\n[Main] Pipeline request: {req.pipeline_type} for user {req.user_id}")

    if req.pipeline_type == "youtube":
        from pipelines.youtube.pipeline import run_youtube_pipeline
        result = run_youtube_pipeline(
            user_id=req.user_id,
            niche=req.niche,
            youtube_channel_id=req.youtube_channel_id,
            user_module_id=req.user_module_id,
        )

    elif req.pipeline_type == "instagram":
        if not req.instagram_account_id or not req.instagram_access_token:
            raise HTTPException(
                status_code=400,
                detail="instagram_account_id and instagram_access_token are required"
            )
        from pipelines.instagram.pipeline import run_instagram_pipeline
        result = run_instagram_pipeline(
            user_id=req.user_id,
            niche=req.niche,
            instagram_account_id=req.instagram_account_id,
            access_token=req.instagram_access_token,
            user_module_id=req.user_module_id,
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown pipeline type: {req.pipeline_type}. Supported: youtube, instagram"
        )

    if result.get("status") == "success":
        return PipelineResponse(
            status="success",
            message=f"{req.pipeline_type} pipeline completed",
            data=result,
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Pipeline failed")
        )


@app.get("/pipeline/status/{run_id}")
def get_pipeline_status(run_id: str, authorization: str = Header(None)):
    """Check status of a running pipeline."""
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
    parser = argparse.ArgumentParser(description="NexAgent Pipeline Runner")
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
            user_id=args.user_id,
            niche=args.niche,
            user_module_id=args.user_module_id or None,
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