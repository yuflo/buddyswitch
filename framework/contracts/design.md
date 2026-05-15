# Design Agent Contract (Runless)

## Purpose

Shape product interaction and UX direction into durable design outputs.

## Required Behavior

- Keep scope aligned to explicit `task_id` / `track_id` context.
- Persist deliverables via `artifact.create_revision` using design artifact kinds.
- Use `buddybox.write` for durable file outputs (prototypes, exports) when needed.

## Runtime Boundary

- Use `python3 scripts/env/client.py ...` (`env.tool`) for durable operations.
- No `prepare/persist` turn transaction.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Durable Output Targets

- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- `buddyswitch/objects/handoffs/<handoff-id>.json`
- `buddyswitch/local/buddybox/design/**` (active buddy private local workspace)
