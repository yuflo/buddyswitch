---
name: handoff-tool
description: Use when you need explicit cross-buddy handoff validation or creation with product-object references.
---

# handoff-tool

## Purpose
- Validate and persist explicit cross-buddy handoff records using readable product-object references.

## Runtime Route
- CLI: `python3 scripts/env/client.py handoff <operation>`
- Broker method: `env.tool`
- Operations: `list`, `validate`, `create`

## Workflow Notes
- `validate` is read-only normalization; `create` persists one durable handoff record.
- Buddybox logical names are private provenance and are not target-readable handoff payloads.
- For action payloads and return meanings, inspect `context.get.tool_catalog['handoff']` or `python3 scripts/turn_runtime.py status`; runtime response fields are authoritative for effects and recovery.

## Verification
- Confirm `ok=true`, returned ids, and `state_changes` on create.
- On rejection, trust `permission_boundary`, `why_blocked`, `state_changed`, `durability`, `correctable_fields`, and `alternative_capabilities`.
- Do not edit runtime state files directly.
