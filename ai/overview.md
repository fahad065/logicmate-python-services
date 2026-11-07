# What this service does, and what's changing

FastAPI microservice that does the actual AI pipeline execution (video
generation, script writing, audio, social posting) for agents and
automations, called by the NestJS backend. See `CLAUDE.md` for the full
pipeline flow and the multi-instance scalability hardening already done.

Chatbots do **not** go through this service — they're a live HTTP engine
inside the NestJS backend, answering in real time. Nothing here changes
because of chatbots; this service only matters once the migration reaches
the agents/automations phase.

## What the database redesign changes here

Two things, both deferred until Phase 7 (see
`ai-agents-automations-backend/ai/implementation-guide.md`):

1. **Read `userservices` (type: agent/automation) instead of
   `usermodules`.** The request shape this service receives from the
   backend (`PipelineRequest`) will need to change to carry a
   `userservice_id` instead of whatever `UserModule`-specific identifiers it
   uses today — and the run config (schedule, custom prompt, etc.) comes
   from `userservices.config{}` instead of individual `UserModule` fields.

2. **Report back into the new `pipeline_runs` shape.** Mostly the same
   fields as today's `PipelineRun` (status, steps, cost breakdown, output
   paths), minus the dangling `agentId` reference and the old narrower
   `pipelineType` enum — see the backend's `architecture.md` for the exact
   shape and why it changed.

**The planned Python pipeline rewrite** (mentioned separately, not part of
this redesign conversation) should happen *against the new schema*, not
against `usermodules` — otherwise it gets rewritten twice. Don't start the
rewrite until Phase 7 is actually reached; build it against whatever the
backend's `userservices`/`pipeline_runs` shape is at that time.
