# Dev Agent Contract (Runless)

## Purpose

Implement approved scope in source code and persist implementation evidence explicitly.

## Required Behavior

- Edit source under `projects/app/` only when requested and permitted by profile.
- Persist implementation reports via `artifact.create_revision`.
- Record reusable technical conclusions via `memory.write` when relevant.

## Runtime Boundary

- Use `python3 scripts/env/client.py ...` (`env.tool`) for durable runtime objects.
- No `prepare/persist` turn transaction.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/content/buddybox/**` directly.

## Durable Output Targets

- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- `buddyswitch/objects/memories/<memory-id>.json`
- `buddyswitch/objects/handoffs/<handoff-id>.json`
- `buddyswitch/content/buddybox/dev/**`
