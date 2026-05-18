---
name: track-tool
description: Use when you need shared track-page context, PM lifecycle actions, and direct material/update/proof publication through runtime env tools.
---

# track-tool

## Purpose
- Read shared track pages.
- Publish current materials, timeline updates, and close proof directly on tracks.
- Apply PM-owned lifecycle create/archive when authority allows.

## Runtime Route
- CLI: `python3 scripts/env/client.py track <operation>`
- Broker method: `env.tool`
- Operations: `create`, `list`, `open`, `update-now`, `add-material`, `add-update`, `add-proof`, `archive`

## Workflow Notes
- Shared collaboration path is `track.open -> shared_materials -> artifact.get`.
- `add-material` and `add-proof` publish existing draft `artifact_id` values.
- Track publication is the shared-state mutation path for artifact visibility.
- `track.open` returns refs/summaries; use `artifact.get` for full markdown bodies.
- Tasks are private hints and never required for shared material reads.
- For action payloads and return meanings, inspect `context.get.tool_catalog['track']` or `python3 scripts/turn_runtime.py status`; runtime response fields are authoritative for effects and recovery.

## Verification
- Confirm `ok=true`, returned ids, and `state_changes` for relation/lifecycle mutations.
- On rejection, trust `permission_boundary`, `why_blocked`, `state_changed`, `durability`, `correctable_fields`, and `alternative_capabilities`.
- Do not edit runtime state files directly.
