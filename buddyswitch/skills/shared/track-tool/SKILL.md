---
name: track-tool
description: Use when you need explicit track context, PM lifecycle actions, or task-track relation updates through runtime env tools.
---

# track-tool

## Purpose
- Read track context and maintain explicit task-track relations.
- Support PM-owned lifecycle updates where permitted.

## Runtime Contract
- CLI: `python3 scripts/env/client.py track <operation>`
- Broker method: `env.tool`
- Operations: `list`, `get`, `join`, `create`, `update`, `advance`, `archive`, `attach-task`, `detach-task`

## Notes
- PM owns lifecycle mutations (`create|update|advance|archive`).
- `join` creates or reuses a task relation explicitly; it does not set hidden instance selection state.
- There is no current-track binding surface in runless mode.

## Verification
- Confirm response JSON has `ok=true` and expected track/task ids.
- For failures, follow runtime feedback fields rather than guessing payloads.
- Do not edit runtime state files directly.
