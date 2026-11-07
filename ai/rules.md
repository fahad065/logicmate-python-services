# Rules for this migration — python-services

Read the backend repo's `ai/architecture.md` and `ai/rules.md` first.

1. **This service has no work to do until Phase 7.** Don't start migrating
   anything here, and don't start the planned pipeline rewrite, until the
   backend's Phase 1–6 are live (`services`, `userservices`, chatbot child
   data, billing, frontend "My Services," and the supporting collections).
   Check `traces.md` and the backend repo's `traces.md` for the current
   phase before touching anything.

2. **When Phase 7 does start: build the pipeline rewrite against the new
   schema from the start**, not against `usermodules`/the old
   `PipelineRun` shape. The backend's `ai/architecture.md` is the contract
   to build against.

3. **`totalCost`/`costBreakdown` reporting stays on `pipeline_runs`, not
   on `billing`.** This service's job is to report what it actually cost to
   run (OpenAI/Replicate/etc. spend) — that's internal cost tracking, not
   customer-facing money. Don't report cost data anywhere that implies it's
   a charge to the customer.

4. **BYOK is unchanged by this redesign.** This service already resolves
   provider keys per-customer (no platform fallback key) — nothing about
   the schema migration changes that; `userservice_id` replaces
   `usermodule_id`/whatever identifier is used today, the BYOK resolution
   logic itself doesn't change.

5. **No real customers yet** — the migration doesn't need a cautious
   dual-write approach. See the backend repo's `rules.md` #12 for the full
   reasoning; it applies here too.
