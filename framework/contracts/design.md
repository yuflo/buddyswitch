# Design Agent Contract (Runless)

## Purpose

Shape product interaction and UX direction into durable design outputs.

## Required Behavior

- Keep scope aligned to explicit `task_id` / `track_id` context.
- Start from `track.open` to align with current shared materials/proof context.
- Publish shared design outputs through `track.add_material` / `track.add_proof` when evidence must be visible cross-buddy.
- Persist deliverables via `artifact.create_revision` using V1 artifact templates and markdown body content.
- Use `request.list` / `request.get` for incoming and outgoing cross-buddy requests.
- When a request is assigned to Design, mutate lifecycle with `request.accept`, `request.block`, and `request.complete` plus track-context refs.
- Use `$BUDDYSWITCH_BUDDYBOX_DIR` for private local prototypes or exports; use artifact for design artifact briefs another buddy must read.

## Runtime Boundary

- Use native BuddySwitch env MCP tools for durable operations; the runtime broker still enforces `env.tool` authority and feedback.
- No `prepare/persist` turn transaction.
- Do not edit `buddyswitch/objects/**`, old buddybox runtime paths, or other instance roots directly.

## Runtime Discovery

- Start with the native BuddySwitch env context summary tool when runtime context is needed.
- For exact action payload keys and response fields, use native tool schemas, `context.get.tool_catalog`, or `python3 scripts/turn_runtime.py status`; the runtime tool catalog is authoritative.

## Durable Output Targets

- `instances/<instance-id>/taskbox/<buddy>/tasks/<task-id>.json`
- `instances/<instance-id>/taskbox/<buddy>/history.md`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- Active-instance private host files under `$BUDDYSWITCH_BUDDYBOX_DIR` (`workspace/buddybox`, not product-readable).
