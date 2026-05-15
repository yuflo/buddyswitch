---
name: handoff-tool
description: Use when you need explicit cross-buddy handoff validation or creation with product-object references.
---

# handoff-tool

## Purpose
- Create explicit collaboration handoff records between buddies.
- Keep handoff provenance object-based (`artifact_ids`, `memory_ids`, `buddybox_paths`, `source_refs`).

## Runtime Contract
- CLI: `python3 scripts/env/client.py handoff <operation>`
- Broker method: `env.tool`
- Operations: `list`, `validate`, `create`

## Notes
- Handoff payloads must be explicit; no run-scoped source fields.
- Handoff records transfer context; they do not mutate track lifecycle implicitly.

## Verification
- Confirm response JSON has `ok=true` and a durable handoff id.
- For failures, follow structured rejection fields (`permission_boundary`, `why_blocked`, `retry_guidance`).
- Do not edit runtime state files directly.
