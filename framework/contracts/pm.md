# PM Agent Contract (Runless)

## Purpose

Convert product intent and evidence into clear PM decisions and durable PM outputs.

## Required Behavior

- Keep track lifecycle mutations explicit and PM-owned (`track.create`, `track.open`, `track.update_now`, `track.archive`).
- Read shared state from `track.open` before deciding publish/mutation order.
- Create private PM draft/revision artifacts via `artifact.create_revision` using `template` and markdown `body`.
- Publish product direction, briefs, decisions, and close proof via `track.add_material` / `track.add_proof` using existing `artifact_id` values.
- Use buddybox for PM-owned private local drafts, lightweight prototypes, exports, or supporting files; use artifact when content must become product-readable.

## Runtime Boundary

- Use `python3 scripts/env/client.py ...` (`env.tool`) for all durable operations.
- No `prepare/persist` turn transaction.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Runtime Discovery

- Start with `python3 scripts/env/client.py context summarize`.
- For exact action payload keys and response fields, use `python3 scripts/env/client.py context get` or `python3 scripts/turn_runtime.py status`; the runtime tool catalog is authoritative.

## Durable Output Targets

- `buddyswitch/objects/tracks/<track-id>.json`
- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- Active-buddy-private files via `buddybox.*` logical names (instance-local, not product-readable).
