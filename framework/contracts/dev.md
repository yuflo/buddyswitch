# Dev Agent Contract (Runless)

## Purpose

Implement approved scope in source code and persist implementation evidence explicitly.

## Required Behavior

- Edit source under `projects/app/` only when requested and permitted by profile.
- Read upstream shared materials via `track.open` + `artifact.get`.
- Persist implementation reports via `track.add_material`.
- Use `track.add_update` and `track.update_now` for progress and blockers.
- Use `request.list` / `request.get` for durable inbound/outbound request state on tracks.
- For requests assigned to Dev, use `request.accept`, `request.block`, and `request.complete` with result refs.
- Use `$BUDDYSWITCH_BUDDYBOX_DIR` for private logs, generated files, binary outputs, or local reports; use artifact for implementation reports and technical conclusions the product workflow must read.

## Runtime Boundary

- Use native BuddySwitch env MCP tools for durable runtime objects; the runtime broker still enforces `env.tool` authority and feedback.
- No `prepare/persist` turn transaction.
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
