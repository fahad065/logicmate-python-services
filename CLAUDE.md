# LogicMate — Python Pipeline Services

## Platform overview
LogicMate is a B2B AI automation marketplace. This Python service handles the heavy AI pipeline execution — video generation, script writing, audio, and social media posting. It runs as a FastAPI microservice called by the NestJS backend.

## GitHub repos (all three services)
- **Frontend (Next.js):** https://github.com/fahad065/ai-agents-automations-frontend.git
- **Backend (NestJS):** https://github.com/fahad065/ai-agents-automations-backend.git
- **This repo (Python pipelines):** https://github.com/fahad065/logicmate-python-services.git

## Stack
- **API:** FastAPI (port 8001)
- **AI:** OpenAI (GPT-4, TTS), Anthropic Claude, Replicate / image generation
- **Video:** MoviePy or equivalent video assembly
- **Deployment:** Docker (`Dockerfile` present)

## Running locally
```bash
cd python-services
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## Environment variables (.env in python-services/)
Key vars needed (copy from .env.example or .env.save — never commit .env):
```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
NESTJS_SERVICE_TOKEN=...     # shared secret with NestJS backend
NESTJS_BASE_URL=http://localhost:4000/api/v1
REPLICATE_API_TOKEN=...
```

## Entry point — main.py
FastAPI app with three main endpoints:

```
GET  /health                   — liveness check
POST /pipeline/run             — trigger a pipeline (returns immediately, runs in background thread)
GET  /pipeline/status/{run_id} — poll run status by checking output metadata.json
```

### PipelineRequest body
```python
{
  "pipeline_type": "youtube" | "instagram",
  "user_id": str,
  "niche": str,
  "user_module_id": str | None,
  "youtube_channel_id": str | None,
  "instagram_account_id": str | None,
  "instagram_access_token": str | None,
  "custom_prompt": str | None,
  "use_custom_prompt": bool,
  "run_id": str | None,
  "video_model": "auto" | str
}
```

Auth: NestJS sends `Authorization: Bearer <NESTJS_SERVICE_TOKEN>` header.

## Pipeline structure
```
pipelines/
  youtube/
    pipeline.py      — run_youtube_pipeline() — main orchestrator
    ...
  instagram/
    pipeline.py      — run_instagram_pipeline() — main orchestrator
    caption_burner.py — burns captions onto video frames
    ...
core/
  config.py          — env vars, OUTPUT_BASE path, model settings
  script_writer.py   — GPT/Claude prompt → script generation
  audio_generator.py — OpenAI TTS → audio file
  video_generator.py — assembles images/audio → video file
  nestjs_client.py   — HTTP client to report run status back to NestJS
  model_health.py    — checks which AI models are available
  utils.py           — shared helpers
```

## YouTube pipeline flow (run_youtube_pipeline)
1. Generate script via GPT/Claude based on `niche` and `custom_prompt`
2. Generate voiceover audio (OpenAI TTS)
3. Generate images (Replicate / DALL-E)
4. Assemble video (MoviePy)
5. Upload to YouTube via OAuth (`client_secrets.json` + token)
6. Report result back to NestJS via `nestjs_client.py`
7. Write `metadata.json` to output folder for status polling

## Instagram pipeline flow (run_instagram_pipeline)
1. Generate short-form script
2. Generate audio (TTS)
3. Generate images / short video clip
4. Burn captions with `caption_burner.py`
5. Post Reel via Instagram Graph API using `instagram_access_token`
6. Report result to NestJS

## Output storage
- `OUTPUT_BASE` (from `core/config.py`) — local directory where each run writes files
- Each run gets its own subfolder named with `run_id`
- `metadata.json` in each folder tracks: `status`, `title`, `youtube_url`, `reel_url`, `error`

## YouTube OAuth
- `client_secrets.json` — Google OAuth credentials for YouTube upload
- `get_youtube_token.py` — run this manually to generate/refresh the OAuth token
- Token is stored locally — must be refreshed if expired

## Cron runner
`cron_runner.py` — can be used to trigger pipelines on a schedule outside of API calls.
`logs/cron.log` — cron execution log.

## How NestJS communicates with this service
NestJS backend (`pipeline-runs` module) calls:
```
POST PYTHON_SERVICE_URL/pipeline/run
Authorization: Bearer NESTJS_SERVICE_TOKEN
```
This service runs the pipeline in a background thread and returns `{"status": "started"}` immediately. NestJS polls `/pipeline/status/{run_id}` or waits for a callback from `nestjs_client.py`.

## Multi-instance scalability audit + fixes (implemented, 2026-09)
Follow-up to the same audit done on the NestJS backend (see backend CLAUDE.md's "Multi-tenant scalability audit + zero-downtime / multi-replica fixes") — user asked for the same pass here. This service turned out to have sharper versions of the same class of problem, since it runs long (15-25 min), heavy (ffmpeg/CPU-bound) background jobs rather than short HTTP request/response cycles.

**Findings:**
1. **No concurrency bound on pipeline execution — a real, live bug, not hypothetical.** `main.py` created a `ThreadPoolExecutor(max_workers=3)` at module scope but never actually used it — `POST /pipeline/run` spawned a raw, unbounded `threading.Thread(daemon=True)` per request instead. A burst of triggers (e.g. NestJS's per-minute `usermodules.cron.ts` scanning every module due in the same window) could spin up unboundedly many concurrent ffmpeg/video-generation jobs on one instance with no cap at all — a real resource-exhaustion risk, independent of replica count.
2. **No graceful shutdown for in-flight jobs — worse here than on the backend.** `daemon=True` threads are killed outright the instant the process exits, with zero notice to anything. On the NestJS side an HTTP request in flight during a deploy is at most a few seconds of work; here it's a 15-25 minute video job. Before this fix, a Railway redeploy mid-run silently destroyed that job with **no failure notification sent anywhere** — the corresponding NestJS `pipeline-runs` record would stay stuck at `status: "running"` forever, since nothing ever called `fail_pipeline_run()` for a thread that just vanished.
3. **`OUTPUT_BASE` (default `/tmp/nexagent/output`, see `core/config.py`) is local, ephemeral, per-instance disk — a real single-instance architecture assumption, not fixed in this pass.** Two places read it: `GET /pipeline/status/{run_id}` (globs for `metadata.json`) and `pipelines/youtube/pipeline.py`'s `find_resumable_folder()` (the "resume" logic `cron_runner.py`'s docstring says exists specifically "to prevent Atlas over-billing" from double-triggering the same user's pipeline). Both silently stop working correctly the moment this runs on 2+ replicas: a status poll or a resume-check routed to a different instance than the one actually running the job finds nothing on that instance's local disk and behaves as if no run exists — for the status endpoint that's a wrong 404 (mitigated, see below); for the resume check that's the exact double-billing scenario it was built to prevent. **Not fixed in this pass** — the real fix is moving run state/output to shared storage (S3/R2/a shared volume) or making resume-detection consult the NestJS `pipeline-runs` DB (already replica-safe, see backend audit) instead of local disk; that's a genuine data-model change, not a quick patch, so it's documented here rather than papered over.
   - **Mitigating factor**: `GET /pipeline/status/{run_id}` is not the sole source of truth — `core/nestjs_client.py`'s `update_pipeline_step()`/`complete_pipeline_run()`/`fail_pipeline_run()` push real-time status into NestJS's own `pipeline-runs` Mongo collection (properly indexed and tenant-scoped per the backend audit) during every run, and that's what `GET /pipeline-runs/my` on the NestJS side actually reads. Treat this service's own `/pipeline/status/{run_id}` as a same-instance debugging/fallback view, not the durable record.
4. **`cron_runner.py` has no cross-invocation dedupe of its own** — `should_run_now()` is a pure 15-minute time-window check with no "already triggered this window" guard at the script level (unlike the NestJS-side crons, which the backend audit hardened with atomic `findOneAndUpdate` claims). This script is architecturally different from the NestJS `@Cron` decorators though — it's a one-shot script invoked externally by a scheduler (Railway Cron or similar), not a handler running inside a persistent multi-replica server process, so the "two replicas both firing the same in-process cron" failure mode doesn't directly apply here. The real risk is the same one as point 3: if this script is ever invoked more than once concurrently for the same schedule (overlapping manual runs, a misconfigured double-trigger), its only dedupe protection is the local-disk `find_resumable_folder()` check inside the pipeline itself — the same ephemeral, non-shared mechanism flagged above. **Not fixed in this pass** — flagged as depending on the same shared-storage fix as point 3.

**Fixes shipped, same session:**
- **`main.py`** — `POST /pipeline/run` now submits to the existing `executor` (`ThreadPoolExecutor`, size configurable via `MAX_CONCURRENT_PIPELINES` env var, default 3) instead of spawning a raw unbounded thread.
- **In-flight run tracking + best-effort shutdown notification** — a module-level `_inflight_runs` dict (guarded by a lock) tracks `run_id → {user_id, pipeline_type}` for the duration of each background job. A FastAPI `lifespan` shutdown handler now runs on SIGTERM: sets a `_shutting_down` flag and calls `fail_pipeline_run(run_id, "Service restarted mid-run — please retry")` for every still-in-flight run, so a job killed by a redeploy is left as a clearly-failed, retryable state in NestJS instead of stuck "running" forever with no explanation. This cannot make a live ffmpeg job survive the deploy — daemon threads still die with the process — but it makes the failure visible and actionable instead of a silent black hole.
- **`GET /health` reports 503 once shutdown has started** (`{"status": "shutting_down"}`), and `POST /pipeline/run` itself starts rejecting new work with a 503 at the same point — together these mean a Railway health-check-gated rollout correctly treats a draining instance as not-ready and routes new triggers to the incoming instance instead of the one about to die. `/health`'s normal response also now reports `inflight` count, useful for spotting a stuck/overloaded instance from the outside.
- **Real pre-existing bug fixed while rewriting this file, unrelated to scaling**: the `if __name__ == "__main__":` CLI-mode block's `youtube` branch referenced `user_id`/`niche`/`yt_channel_id`/`req` — none of which exist in that scope (leftover from a copy-paste of the HTTP handler above it) — so invoking `python main.py --pipeline youtube ...` directly would have crashed with a `NameError` before ever calling the pipeline. Fixed to use the already-parsed `args.user_id`/`args.niche`, matching the working `instagram` branch right below it.

**Not touched / deliberately out of scope**: the YouTube OAuth setup (`client_secrets.json` + `get_youtube_token.py`'s locally-stored token) — worth a look in a future session for whether it's genuinely per-customer (the backend's BYOK model would require it) or a single shared credential, but that's a distinct question from this scaling audit and wasn't investigated here.

**Verified**: syntax-checked (`ast.parse`), then actually import- and runtime-checked in a throwaway venv with `fastapi`/`uvicorn`/`python-dotenv`/`httpx` installed (this sandbox has no way to install the full `requirements.txt` — no `moviepy`/`replicate`/etc. — so the real pipeline modules can't run here) via `fastapi.testclient.TestClient`: confirmed `/health` returns 200 normally and 503 after the lifespan shutdown fires, a bad `pipeline_type` and missing Instagram credentials both still return 400 as before, a valid submission returns 200 immediately and the job actually runs on the executor (observed it fail fast with `ModuleNotFoundError: No module named 'openai'` in this minimal venv, which is expected — confirms the job really executes in the background rather than silently no-op'ing), and that `_inflight_runs` correctly adds/removes the run around that execution.

## Frontend scalability audit — no server-side surface, Vercel's deploy model already covers this (checked, 2026-09)
Checked whether any of the same concerns apply to the Next.js frontend. They don't, for a structural reason rather than luck: the frontend has **no backend of its own** to audit — `find src/app -type d -name api` and a grep for `export async function GET/POST`/`NextRequest`/`NextResponse` across `src/` turn up nothing except `src/proxy.ts`, which is stateless Next.js middleware (reads an `accessToken` cookie, redirects to `/auth/login` if missing — no DB, no shared state, no cron). Every actual data operation goes through the NestJS backend via `lib/api.ts`/`api-client.ts`/`dashboard-api.ts`.
- **Zero-downtime deploys**: Vercel's deployment model is atomic and immutable per-deployment by design — there's no persistent server process on this side to gracefully drain on SIGTERM the way the NestJS backend needed; the old deployment's serverless/edge functions keep serving in-flight requests while a new deployment activates. Nothing to configure here.
- **Per-tenant rate limiting / monitoring**: not applicable — there's no shared mutable state or database on this side that one visitor's traffic could contend for; all of that risk lives on the NestJS backend, already addressed there.
- **One (benign) observation, not a bug**: `src/components/keep-alive.tsx`, mounted in the root layout (`app/layout.tsx`), pings the backend's `/health` every 4 minutes from **every open browser tab** — marketing visitors and logged-in dashboard users alike — to stop the Railway backend from cold-sleeping. At scale this is many independent, uncoordinated clients hitting one shared endpoint, but `/health` is a trivial, stateless GET well within the backend's now-confirmed IP-based throttle (100 req/60s per `ThrottlerModule.forRoot()`, see backend CLAUDE.md), so it poses no real risk — flagged here only because it's the one place this repo does repeatedly call the shared backend on a timer, and worth knowing about if `/health` ever needs to do more than return a static JSON blob.

## What is next to build
- Chatbot pipeline support (`pipeline_type: "chatbot"`)
- WhatsApp message pipeline
- More niche-specific pipeline variants
