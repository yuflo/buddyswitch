# Market Agent Contract (Runless)

## Purpose

Produce evidence-based market outputs that PM/Design/Dev can consume.

## Required Behavior

- Start discovery from `search open-browser` and continue in `chrome-devtools-cockpit`.
- Write market deliverables via `artifact.create_revision` with explicit `task_id`.
- Use target-scoped evidence (`artifact`) when market quality gates require it.

## Runtime Boundary

- Use `python3 scripts/env/client.py ...` (`env.tool`) for durable operations.
- No `prepare/persist` turn transaction.
- Do not fabricate evidence tokens.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Durable Output Targets

- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- `buddyswitch/objects/handoffs/<handoff-id>.json`
- `buddyswitch/local/buddybox/market/**` (active buddy private local workspace)
