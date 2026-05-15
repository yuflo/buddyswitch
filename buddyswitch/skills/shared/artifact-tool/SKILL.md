---
name: artifact-tool
description: Use when you need artifact summaries, full artifact reads by id, artifact revision writes, or artifact metadata updates through runtime-owned env tools.
---

# artifact-tool

## Purpose
- Manage artifact reads and writes through broker-routed env tools.
- Use `artifact get --artifact-id` for full-body artifact reads.
- Keep writes scoped to active-buddy task ownership and manifest artifact kinds.

## Runtime Contract
- CLI: `python3 scripts/env/client.py artifact <operation>`
- Broker method: `env.tool`
- Operations: `list`, `get`, `validate-payload`, `create-revision`, `update-metadata`

## Payload Hints
- `create-revision`: `{"task_id":"...", "kind":"...", "title":"...", "summary":"...", "content":{}, "source_refs":[...]}`
- `task_id` is required for `create-revision`.
- `source_refs` are optional provenance/context refs; they do not grant write authority.
- `update-metadata` accepts `artifact_id` plus optional `title`, `summary`, `source_refs`.

## Verification
- Confirm response JSON has `ok=true` and expected `artifact.id`.
- For failures, follow structured feedback (`permission_boundary`, `why_blocked`, `retry_guidance`, `allowed_next_actions`).
- Do not edit runtime state files directly.
