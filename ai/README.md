# `ai/` folder — start here

Same purpose as the other two repos' `ai/` folders: lets any Claude Code
session, in any environment, pick up the database architecture migration
without replaying the conversation that designed it.

**The full schema lives in the backend repo** —
`ai-agents-automations-backend/ai/architecture.md` is the single source of
truth for all 13 collections. Read that first.

| File | Purpose |
|---|---|
| `overview.md` | What this service does, and what changes here because of the redesign. |
| `rules.md` | Constraints specific to this service for the migration. |
| `implementation-guide.md` | The python-services slice of the phase plan. |
| `traces.md` | Running, dated log. Newest entry first. |

This repo's `CLAUDE.md` documents the pipeline flow and the multi-instance
scalability work already done — read that for "how does the pipeline work
today."

**Branch**: `fahad-development`, not `main`. Do not push to `main` unless
explicitly told to.
