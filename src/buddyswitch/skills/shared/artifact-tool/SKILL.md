---
name: artifact-tool
description: Use when you need artifact summaries, full artifact reads by id, artifact revision writes, or artifact metadata updates through runtime-owned env tools.
---

# artifact-tool

## Purpose
- Manage product-readable artifact summaries, full-body reads, private draft revisions, attachments, and artifact metadata.

## Runtime Route
- Primary: use native BuddySwitch env MCP tools such as `artifact__list`, `artifact__get`, `artifact__create_revision`, `artifact__update_metadata`, `artifact__attach_file`, `artifact__list_attachments`, and `artifact__get_attachment`.
- Exact payload schemas, allowed fields, effects, and response meanings come from native tool schemas and `context.get.tool_catalog['artifact']`.
- Diagnostic fallback: `"$BUDDYSWITCH_PYTHON" -m buddyswitch.application.entrypoints.diagnostics status`.
- Broker method remains `env.tool`; do not edit runtime state files directly.

## Workflow Notes
- Use `artifact__list` for readable summary discovery. Summary rows do not contain full artifact bodies.
- Use `artifact__get` before claiming full artifact content was read.
- Use `artifact__create_revision` for active actor private draft or revision content.
- Shared track visibility starts only after `track__add_material` or `track__add_proof` creates a Track-owned artifact relation. Historical CLI wording was track.add-material / track.add-proof, but the product path is the native track tool.
- Use `artifact__attach_file`, `artifact__list_attachments`, and `artifact__get_attachment` for explicit attachments; use `$BUDDYSWITCH_ACTOR_PRIVATE_DIR` for private local files that should not become product-readable.
- For action details and recovery guidance, inspect `context.get.tool_catalog['artifact']` or `"$BUDDYSWITCH_PYTHON" -m buddyswitch.application.entrypoints.diagnostics status`; runtime response fields are authoritative.

## Verification
- Confirm `ok=true`, returned ids, and `state_changes` for mutating actions.
- On rejection, trust `permission_boundary`, `why_blocked`, `state_changed`, `durability`, `correctable_fields`, and `alternative_capabilities`.
- Do not edit `buddyswitch/objects/**` or instance runtime state directly.
