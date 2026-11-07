# Implementation guide — python-services slice

Full phase plan: `ai-agents-automations-backend/ai/implementation-guide.md`.
This service only has work in **Phase 7**.

## Phase 7 — when it actually arrives
1. Confirm the backend has already migrated `userservices` (type:
   agent/automation) and `pipeline_runs` per its `architecture.md` — don't
   start against a moving target.
2. Update `PipelineRequest` (or whatever the request model is called by
   then) to accept a `userservice_id` and read run config from
   `userservices.config{}` (schedule, custom prompt, YouTube channel ID,
   etc. — see the backend's `architecture.md` for the exact config shape
   per service).
3. Update `nestjs_client.py`'s reporting calls to write into the new
   `pipeline_runs` shape — same fields as today's `PipelineRun`
   (status/steps/cost/output paths) minus the dangling `agentId` reference,
   with `pipelineType` as a plain snapshot string instead of the old
   narrower enum.
4. This is also the point to fold in the separately-planned pipeline
   rewrite — build it against the new schema directly, don't rewrite
   against the old one first.

## Before Phase 7
Nothing to do here. If asked to work on this repo before Phase 7 is
reached (check `traces.md`), the task is probably unrelated to this
migration — proceed normally, just don't start migration work early.
