# Design Agent Contract (Runless)

## Purpose

Shape product interaction and UX direction into durable design outputs.

## Required Behavior

- Keep scope aligned to explicit `task_id` / `track_id` context.
- Start from `track.open` to align with current shared materials/proof context.
- Publish shared design outputs through `track.add_material` / `track.add_proof` when evidence must be visible cross-role.
- Persist deliverables via `artifact.create_revision` using V1 artifact templates and markdown body content.
- Use `message` for direct actor communication and `comment` for track/artifact discussion.
- Use `track.add_update`, `track.add_material`, and `track.add_proof` for shared collaboration state.
- Use `$BUDDYSWITCH_ACTOR_PRIVATE_DIR` for private local prototypes or exports; use artifact for design artifact briefs another role must read.

## Runtime Boundary

- Use native BuddySwitch env MCP tools for durable operations; the runtime broker still enforces `env.tool` authority and feedback.
- No `prepare/persist` turn transaction.
- Do not edit `buddyswitch/objects/**`, old private workspace runtime paths, or other instance roots directly.

## Runtime Discovery

- Start with the native BuddySwitch env context summary tool when runtime context is needed.
- For exact action payload keys and response fields, use native tool schemas, `context.get.tool_catalog`, or `python3 scripts/turn_runtime.py status`; the runtime tool catalog is authoritative.

## Durable Output Targets

- `instances/<actor-id>/taskbox/<role>/tasks/<task-id>.json`
- `instances/<actor-id>/taskbox/<role>/history.md`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- Active-instance private host files under `$BUDDYSWITCH_ACTOR_PRIVATE_DIR` (`workspace/private`, not product-readable).
