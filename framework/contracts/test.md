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
- Use `$BUDDYSWITCH_BUDDYBOX_DIR` for private logs, raw evidence files, or local reports; use artifact for pass/fail reports the product workflow must read.

## Runtime Boundary

- Use native BuddySwitch env MCP tools for durable operations; the runtime broker still enforces `env.tool` authority and feedback.
- No `prepare/persist` turn transaction.
- Test buddy must not edit source code when profile is read-only.
- Do not edit `buddyswitch/objects/**`, old buddybox runtime paths, or other instance roots directly.

## Runtime Discovery

- Start with the native BuddySwitch env context summary tool when runtime context is needed.
- For exact action payload keys and response fields, use native tool schemas, `context.get.tool_catalog`, or `python3 scripts/turn_runtime.py status`; the runtime tool catalog is authoritative.

## Durable Output Targets

- `buddyswitch/objects/tracks/<track-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- `instances/<instance-id>/taskbox/<buddy>/tasks/<task-id>.json`
- `instances/<instance-id>/taskbox/<buddy>/history.md`
- Active-instance private host files under `$BUDDYSWITCH_BUDDYBOX_DIR` (`workspace/buddybox`, not product-readable).
