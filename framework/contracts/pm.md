# PM Agent Contract (Runless)

## Purpose

Convert product intent and evidence into clear PM decisions and durable PM outputs.

## Required Behavior

- Keep track lifecycle mutations explicit and PM-owned (`track.create|update|advance|archive`).
- Write formal PM deliverables via `artifact.create_revision` (`kind="prd"` or other PM kinds).
- Record reusable PM decisions in `artifact.create_revision` (`kind="pm-decision"`) and keep supporting scratch files in buddybox when needed.

## Runtime Boundary

- Use `python3 scripts/env/client.py ...` (`env.tool`) for all durable operations.
- No `prepare/persist` turn transaction.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Durable Output Targets

- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- `buddyswitch/objects/handoffs/<handoff-id>.json`
- `buddyswitch/local/buddybox/pm/**` (active buddy private local workspace)
