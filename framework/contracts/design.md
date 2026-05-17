# Design Agent Contract (Runless)

## Purpose

Shape product interaction and UX direction into durable design outputs.

## Required Behavior

- Read shared collaboration state via `track.open`.
- Publish design deliverables via `track.add_material` using design artifact kinds.
- Use `track.add_update` and `track.update_now` for concise progress and blocker state.
- Use buddybox for private local prototypes or exports; use artifact for design artifact briefs another buddy must read.

## Runtime Boundary

- Use `python3 scripts/env/client.py ...` (`env.tool`) for durable operations.
- No `prepare/persist` turn transaction.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Durable Output Targets

- `buddyswitch/objects/tracks/<track-id>.json`
- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- Active-buddy-private files via `buddybox.*` logical names (instance-local, not product-readable).
