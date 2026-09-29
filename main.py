"""
LogicMate Python Services — Main Entry Point
============================================
Handles pipeline execution requests from NestJS backend.
Supports: youtube, instagram (more coming)
"""
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

NESTJS_TOKEN = os.getenv("NESTJS_SERVICE_TOKEN", "")

# Thread pool for background pipeline execution — bounds how many pipelines
# (ffmpeg/video-generation, CPU + memory heavy) can run at once on this
# instance. Previously a plain `threading.Thread(daemon=True)` was spawned
# per request with no cap at all — a burst of pipeline triggers (the
# per-minute NestJS cron scanning every due module, for example) could spin
# up unboundedly many concurrent heavy jobs on one process.
MAX_CONCURRENT_PIPELINES = int(os.getenv("MAX_CONCURRENT_PIPELINES", "3"))
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_PIPELINES)

# In-flight run tracking, so a shutdown (Railway SIGTERM on redeploy) can at
# least tell NestJS which runs got interrupted instead of leaving them
# silently stuck at status="running" forever. A `daemon=True` thread (the
# old approach) is killed outright on process exit with zero notice to
# anything — the pipeline-runs record in Mongo would never learn the job
# died. This can't make a 15-25 minute video-generation job survive a
# deploy, but it makes the failure visible and retryable instead of a
# silent black hole.
_inflight_lock = threading.Lock()
_inflight_runs: dict[str, dict] = {}
_shutting_down = threading.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # ── Shutdown: stop accepting new work, flag in-flight runs as
    # interrupted so NestJS doesn't leave them stuck "running" forever ──
    _shutting_down.set()
    with _inflight_lock:
        interrupted = list(_inflight_runs.items())
    if interrupted:
        print(f"[Shutdown] {len(interrupted)} pipeline(s) still running — notifying NestJS", flush=True)
        from core.nestjs_client import fail_pipeline_run
        for run_id, info in interrupted:
            if not run_id:
                continue
            try:
                fail_pipeline_run(run_id, "Service restarted mid-run — please retry")
            except Exception as e:
                print(f"[Shutdown] Failed to report interrupted run {run_id}: {e}", flush=True)
    # Give the executor a bounded moment to let any run that's already
    # finishing wrap up, then let the process exit — daemon threads that
    # are still mid-job at this point are killed with the process either
    # way; there is no way to safely pause/resume a live ffmpeg job.
    executor.shutdown(wait=False, cancel_futures=False)


app = FastAPI(title="LogicMate Pipeline Service", version="2.0.0", lifespan=lifespan)


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
    # Reports 503 once shutdown has started, so Railway's health-check-gated
    # deploy stops considering this instance ready and routes new traffic
    # (including new /pipeline/run triggers) to the incoming instance instead.
    if _shutting_down.is_set():
        return JSONResponse(status_code=503, content={"status": "shutting_down"})
    return {
        "status": "ok",
        "service": "logicmate-pipelines",
        "version": "2.0.0",
        "inflight": len(_inflight_runs),
    }


# ── Pipeline run — returns immediately, runs in background ────
@app.post("/pipeline/run", response_model=PipelineResponse)
async def run_pipeline(req: PipelineRequest, authorization: str = Header(None)):
    verify_token(authorization)

    if _shutting_down.is_set():
        raise HTTPException(status_code=503, detail="Service is shutting down — retry against another instance")

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
    run_id          = req.run_id

    def run_in_background():
        import sys
        if run_id:
            with _inflight_lock:
                _inflight_runs[run_id] = {"user_id": user_id, "pipeline_type": pipeline_type}
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
        finally:
            if run_id:
                with _inflight_lock:
                    _inflight_runs.pop(run_id, None)

    # Bounded concurrency via the shared executor instead of an unbounded
    # raw thread per request.
    executor.submit(run_in_background)
    print(f"[Main] Background job queued for {pipeline_type} ({len(_inflight_runs)} in flight)", flush=True)

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

    # NOTE — this reads OUTPUT_BASE off LOCAL disk (defaults to /tmp, which
    # is ephemeral and instance-local). That's fine on a single instance,
    # but the moment this service runs 2+ replicas, a status poll routed to
    # a different instance than the one actually running the job will find
    # nothing here and report a false "Run not found" even though the
    # pipeline is alive elsewhere. The durable, replica-safe source of
    # truth is the NestJS pipeline-runs record, kept current in real time
    # via core/nestjs_client.py's update_pipeline_step/complete_pipeline_run/
    # fail_pipeline_run push calls during the run — NestJS's own
    # GET /pipeline-runs/my reads that, not this endpoint. Treat this route
    # as a same-instance debugging/fallback view, not the source of truth,
    # until output storage moves to something shared (S3/R2/etc).
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
            user_id=args.user_id,
            niche=args.niche,
            youtube_channel_id=None,
            user_module_id=args.user_module_id or None,
            run_id=None,
            custom_prompt=None,
            use_custom_prompt=False,
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
