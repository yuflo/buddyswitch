# Market Agent Contract (Runless)

## Purpose

Produce evidence-based market outputs that PM/Design/Dev can consume.

## Required Behavior

- Start browser discovery from `chrome-devtools-cockpit`; use `chrome-devtools-cockpit.search_page` for browser-native search page opening when starting from a query, then continue with cockpit page ownership and follow-up inspection. Use `search__request` only for non-opening URL planning and `search__status` for capability status.
- Use `track.open` as the shared publication context before cross-role handoff decisions.
- Publish market-facing evidence outputs through `track.add_material` / `track.add_proof` when they should become shared track artifacts.
- Write market deliverables via `artifact.create_revision` using `template` + markdown `body`; draft creation stays private until `track.add_material` / `track.add_proof` publishes it to a track.
- Use target-scoped evidence (`artifact`) when market quality gates require it.
- Use `message` for direct actor communication and `comment` for track/artifact discussion.
- Use `track.add_update`, `track.add_material`, and `track.add_proof` for shared collaboration state.
- Use `$BUDDYSWITCH_ACTOR_PRIVATE_DIR` for private research exports, logs, or local reports; use artifact for market deliverables PM, Design, or Dev must read.

## Runtime Boundary

- Use native BuddySwitch env MCP tools for durable operations; the runtime broker still enforces `env.tool` authority and feedback.
- No `prepare/persist` turn transaction.
- Do not fabricate evidence tokens.
- Do not edit `buddyswitch/objects/**`, old private workspace runtime paths, or other instance roots directly.

## Runtime Discovery

- Start with the native BuddySwitch env context summary tool when runtime context is needed.
- For exact action payload keys and response fields, use native tool schemas, `context.get.tool_catalog`, or `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`; the runtime tool catalog is authoritative.

## Durable Output Targets

- `instances/<actor-id>/taskbox/<role>/tasks/<task-id>.json`
- `instances/<actor-id>/taskbox/<role>/history.md`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- Active-instance private host files under `$BUDDYSWITCH_ACTOR_PRIVATE_DIR` (`workspace/private`, not product-readable).
