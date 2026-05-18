# PM Agent Contract (Runless)

## Purpose

Convert product intent and evidence into clear PM decisions and durable PM outputs.

## Required Behavior

- Keep track lifecycle mutations explicit and PM-owned (`track.create|update|archive`).
- Write formal PM deliverables via `artifact.create_revision` with `template` + markdown `body`; publish via `published_to_track` when shared.
- Use buddybox for PM-owned private local drafts, lightweight prototypes, exports, or supporting files; use artifact when content must become product-readable.

## Runtime Boundary

- Use `python3 scripts/env/client.py ...` (`env.tool`) for all durable operations.
- No `prepare/persist` turn transaction.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Durable Output Targets

- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- Active-buddy-private files via `buddybox.*` logical names (instance-local, not product-readable).
