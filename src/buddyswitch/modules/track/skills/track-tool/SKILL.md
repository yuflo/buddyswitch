---
name: track-tool
description: Use when you need shared track-page context, Track-scoped comments, PM lifecycle actions, and direct material/update/proof publication through runtime env tools.
---

# track-tool

## Purpose
- Read shared track pages.
- Add, list, and PM-resolve Track-scoped collaboration comments.
- Publish current materials, timeline updates, and close proof directly on tracks.
- Apply PM-owned lifecycle create/archive when authority allows.

## Runtime Route
- Primary: use native BuddySwitch env MCP tools such as `track__list`, `track__open`, `track__add_comment`, `track__list_comments`, `track__resolve_comment_thread`, `track__create`, `track__update_now`, `track__add_material`, `track__add_update`, `track__add_proof`, and `track__archive`.
- Exact payload schemas, allowed fields, effects, and response meanings come from native tool schemas and `context.get.tool_catalog['track']`.
- Diagnostic fallback: `"$BUDDYSWITCH_PYTHON" -m buddyswitch.application.entrypoints.diagnostics status`.
- Broker method remains `env.tool`; do not edit runtime state files directly.

## Workflow Notes
- Shared collaboration path is `track__open` -> shared materials -> `artifact__get`.
- `track__add_material` and `track__add_proof` publish existing draft artifact ids. Historical CLI wording for these actions was add-material / add-proof; the product path is the native track tool.
- `track__add_update` records timeline progress.
- `track__update_now` records current next step or blocker.
- `track__add_comment` and `track__list_comments` operate only inside one Track; replies must stay in the same Track.
- PM can close reviewed Track comment threads with `track__resolve_comment_thread`.
- `track__open` returns refs and summaries; use `artifact__get` for full markdown bodies.
- `track__open` includes compact comment cues; use `track__list_comments` for full comment rows.
- Tasks are private hints and never required for shared material reads.
- For action details and recovery guidance, inspect `context.get.tool_catalog['track']` or `"$BUDDYSWITCH_PYTHON" -m buddyswitch.application.entrypoints.diagnostics status`; runtime response fields are authoritative.

## Verification
- Confirm `ok=true`, returned ids, and `state_changes` for relation/lifecycle mutations.
- On rejection, trust `permission_boundary`, `why_blocked`, `state_changed`, `durability`, `correctable_fields`, and `alternative_capabilities`.
- Do not edit `buddyswitch/objects/**` or instance runtime state directly.
