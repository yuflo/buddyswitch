---
name: artifact-tool
description: Use when you need artifact summaries, full artifact reads by id, artifact revision writes, or artifact metadata updates through runtime-owned env tools.
---

# artifact-tool

## Purpose
- Manage product-readable artifact summaries, full-body reads, and durable artifact writes.

## Runtime Route
- CLI: `python3 scripts/env/client.py artifact <operation>`
- Broker method: `env.tool`
- Operations: `list`, `get`, `validate-payload`, `create-revision`, `update-metadata`

## Workflow Notes
- `list` returns summaries; `get` returns one full artifact body by `artifact_id`.
- `validate-payload` is read-only; `create-revision` and `update-metadata` persist durable artifact state.
- For action payloads and return meanings, inspect `context.get.tool_catalog['artifact']` or `python3 scripts/turn_runtime.py status`; runtime response fields are authoritative for effects and recovery.

## Verification
- Confirm `ok=true`, returned ids, and `state_changes` for mutating actions.
- On rejection, trust `permission_boundary`, `why_blocked`, `state_changed`, `durability`, `correctable_fields`, and `alternative_capabilities`.
- Do not edit runtime state files directly.
