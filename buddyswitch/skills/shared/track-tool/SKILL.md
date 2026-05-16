---
name: track-tool
description: Use when you need explicit track context, PM lifecycle actions, or task-track relation updates through runtime env tools.
---

# track-tool

## Purpose
- Read track context and maintain explicit task-track relations.
- Apply PM-owned lifecycle updates when authority allows.

## Runtime Route
- CLI: `python3 scripts/env/client.py track <operation>`
- Broker method: `env.tool`
- Operations: `list`, `get`, `join`, `create`, `update`, `advance`, `archive`, `attach-task`, `detach-task`

## Workflow Notes
- `join` creates, attaches, or reuses task relations without hidden binding state.
- For action payloads and return meanings, inspect `context.get.tool_catalog['track']` or `python3 scripts/turn_runtime.py status`; runtime response fields are authoritative for effects and recovery.

## Verification
- Confirm `ok=true`, returned ids, and `state_changes` for relation/lifecycle mutations.
- On rejection, trust `permission_boundary`, `why_blocked`, `state_changed`, `durability`, `correctable_fields`, and `alternative_capabilities`.
- Do not edit runtime state files directly.
