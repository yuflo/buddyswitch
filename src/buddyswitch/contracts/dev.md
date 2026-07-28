# Dev Agent Contract (Runless)

## Purpose

Implement approved scope in source code and persist implementation evidence explicitly.

## Required Behavior

- Edit source under `projects/app/` only when requested and permitted by profile.
- Read upstream shared materials via `track.open` + `artifact.get`.
- Persist implementation reports via `track.add_material`.
- Use `track.add_update` for progress/blocker facts and `track.update_status` only when this actor is the exact Track owner.
- Use `message` for direct actor communication and `comment` for track/artifact discussion.
- Use `track.add_update`, `track.add_material`, and `track.add_proof` for shared collaboration state.
- Use `$BUDDYSWITCH_ACTOR_PRIVATE_DIR` for private logs, generated files, binary outputs, or local reports; use artifact for implementation reports and technical conclusions the product workflow must read.

## Runtime Boundary

- Use native BuddySwitch env MCP tools for durable runtime objects; the runtime broker still enforces `env.tool` authority and feedback.
- No `prepare/persist` turn transaction.
- Do not edit `buddyswitch/objects/**`, old private workspace runtime paths, or other instance roots directly.

## Runtime Discovery

- Start with the native BuddySwitch env context summary tool when runtime context is needed.
- For exact action payload keys and response fields, use native tool schemas, `context.get.tool_catalog`, or `"$BUDDYSWITCH_PYTHON" -m buddyswitch.application.entrypoints.diagnostics status`; the runtime tool catalog is authoritative.

## Durable Output Targets

- `buddyswitch/objects/tracks/<track-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- `instances/<actor-id>/taskbox/<role>/tasks/<task-id>.json`
- `instances/<actor-id>/taskbox/<role>/history.md`
- Active-instance private host files under `$BUDDYSWITCH_ACTOR_PRIVATE_DIR` (`workspace/private`, not product-readable).
