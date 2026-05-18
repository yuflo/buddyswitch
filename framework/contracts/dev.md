# Dev Agent Contract (Runless)

## Purpose

Implement approved scope in source code and persist implementation evidence explicitly.

## Required Behavior

- Edit source under `projects/app/` only when requested and permitted by profile.
- Read upstream shared materials via `track.open` + `artifact.get`.
- Persist implementation reports via `track.add_material`.
- Use `track.add_update` and `track.update_now` for progress and blockers.
- Use buddybox for private logs, generated files, binary outputs, or local reports; use artifact for implementation reports and technical conclusions the product workflow must read.

## Runtime Boundary

- Use `python3 scripts/env/client.py ...` (`env.tool`) for durable runtime objects.
- No `prepare/persist` turn transaction.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Durable Output Targets

- `buddyswitch/objects/tracks/<track-id>.json`
- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- Active-buddy-private files via `buddybox.*` logical names (instance-local, not product-readable).
