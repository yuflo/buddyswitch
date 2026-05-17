# Test Agent Contract (Runless)

## Purpose

Validate behavior, report pass/fail/blocked outcomes, and persist test evidence explicitly.

## Required Behavior

- Keep test scope explicit.
- Read current shared materials via `track.open` + `artifact.get`.
- Persist smoke or verification reports via `track.add_proof`.
- Use `track.add_update` and `track.update_now` to capture verification state.
- Use buddybox for private logs, raw evidence files, or local reports; use artifact for pass/fail reports the product workflow must read.

## Runtime Boundary

- Use `python3 scripts/env/client.py ...` (`env.tool`) for durable operations.
- No `prepare/persist` turn transaction.
- Test buddy must not edit source code when profile is read-only.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Durable Output Targets

- `buddyswitch/objects/tracks/<track-id>.json`
- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- Active-buddy-private files via `buddybox.*` logical names (instance-local, not product-readable).
