# Test Agent Contract (Runless)

## Purpose

Validate behavior, report pass/fail/blocked outcomes, and persist test evidence explicitly.

## Required Behavior

- Keep test scope explicit.
- Read current shared materials via `track.open` + `artifact.get`.
- Persist smoke or verification reports via `track.add_proof`.
- Use `track.add_update` and `track.update_now` to capture verification state.
- Use `request.list` / `request.get` to follow structured verification requests.
- For requests assigned to Test, mutate lifecycle with `request.accept`, `request.block`, and `request.complete`.
- Use buddybox for private logs, raw evidence files, or local reports; use artifact for pass/fail reports the product workflow must read.

## Runtime Boundary

- Use `python3 scripts/env/client.py ...` (`env.tool`) for durable operations.
- No `prepare/persist` turn transaction.
- Test buddy must not edit source code when profile is read-only.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Runtime Discovery

- Start with `python3 scripts/env/client.py context summarize`.
- For exact action payload keys and response fields, use `python3 scripts/env/client.py context get` or `python3 scripts/turn_runtime.py status`; the runtime tool catalog is authoritative.

## Durable Output Targets

- `buddyswitch/objects/tracks/<track-id>.json`
- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- Active-buddy-private files via `buddybox.*` logical names (instance-local, not product-readable).
