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

## What is next to build
- Chatbot pipeline support (`pipeline_type: "chatbot"`)
- WhatsApp message pipeline
- More niche-specific pipeline variants
