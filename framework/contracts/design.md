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
- Use buddybox for private local prototypes or exports; use artifact for design artifact briefs another buddy must read.

## Runtime Boundary

- Use `python3 scripts/env/client.py ...` (`env.tool`) for durable operations.
- No `prepare/persist` turn transaction.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Runtime Discovery

- Start with `python3 scripts/env/client.py context summarize`.
- For exact action payload keys and response fields, use `python3 scripts/env/client.py context get` or `python3 scripts/turn_runtime.py status`; the runtime tool catalog is authoritative.

## Durable Output Targets

- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- Active-buddy-private files via `buddybox.*` logical names (instance-local, not product-readable).
