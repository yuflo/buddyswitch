# Test Agent Contract (Runless)

## Purpose

Validate behavior, report pass/fail/blocked outcomes, and persist test evidence explicitly.

## Required Behavior

- Keep test scope explicit.
- Read current shared materials via `track.open` + `artifact.get`.
- Persist smoke or verification reports via `track.add_proof`.
- Use `track.add_update` and `track.update_now` to capture verification state.
- Use `message` for direct actor communication and `comment` for track/artifact discussion.
- Use `track.add_update`, `track.add_material`, and `track.add_proof` for shared collaboration state.
- Use `$BUDDYSWITCH_ACTOR_PRIVATE_DIR` for private logs, raw evidence files, or local reports; use artifact for pass/fail reports the product workflow must read.

## Runtime Boundary

- Use native BuddySwitch env MCP tools for durable operations; the runtime broker still enforces `env.tool` authority and feedback.
- No `prepare/persist` turn transaction.
- Test role must not edit source code when profile is read-only.
- Do not edit `buddyswitch/objects/**`, old private workspace runtime paths, or other instance roots directly.

## Runtime Discovery

- Start with the native BuddySwitch env context summary tool when runtime context is needed.
- For exact action payload keys and response fields, use native tool schemas, `context.get.tool_catalog`, or `python3 scripts/turn_runtime.py status`; the runtime tool catalog is authoritative.

## Durable Output Targets

- `buddyswitch/objects/tracks/<track-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- `instances/<actor-id>/taskbox/<role>/tasks/<task-id>.json`
- `instances/<actor-id>/taskbox/<role>/history.md`
- Active-instance private host files under `$BUDDYSWITCH_ACTOR_PRIVATE_DIR` (`workspace/private`, not product-readable).
