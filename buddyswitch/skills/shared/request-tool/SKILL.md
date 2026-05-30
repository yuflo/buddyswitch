---
name: request-tool
description: Use when creating and managing durable cross-buddy requests on readable tracks through runtime env tools.
---

# Request Tool

## Purpose

Create and manage durable cross-buddy request lifecycle state on readable tracks.

## Runtime Route
- Primary: use native BuddySwitch env MCP tools such as `request__create` when available.
- Fallback CLI: `python3 scripts/env/client.py request create --payload '{"track_id":"track-alpha","to_buddy":"dev","title":"Implement scoped flow","summary":"Build from the approved design artifact.","target_refs":[{"type":"artifact","id":"art-design-r1"}]}'`
- Broker method: `env.tool`
- Discover current operations, payload keys, effects, and recovery guidance with `context.get.tool_catalog['request']` or `python3 scripts/turn_runtime.py status`.

## CLI Payload Rule

- `--payload` takes one JSON object string.
- Do not pass a filesystem path to `--payload`.
- For long markdown fields, generate JSON with `python3 - <<'PY'` and pass it via command substitution.

```bash
python3 scripts/env/client.py request create --payload '{"track_id":"track-alpha","to_buddy":"dev","title":"Implement scoped flow","summary":"Build from the approved design artifact.","target_refs":[{"type":"artifact","id":"art-design-r1"}]}'
```

## Workflow Notes

- Start with `python3 scripts/env/client.py context summarize --payload '{}'` so request actions run against current runtime-visible ids and state.
- Use `request.list` for inbox/outbox scans and status filters.
- Use `request.get` for one exact request row before mutating lifecycle state.
- Recipient uses `request.accept`, `request.block`, and `request.complete`.
- Requester uses `request.cancel`.
- Keep `target_refs` and `result_refs` inside request track context.

## Key Boundary Rules

- Request objects are product-readable collaboration state.
- Request lifecycle is separate from private task state.
- Message stays informal text and does not become request status state.
- Only requester/recipient/PM can read a request.
- Only recipient can accept/block/complete.
- Only requester can cancel.

## Verification

```bash
python3 scripts/env/client.py request --help
python3 scripts/env/client.py request list --payload '{"box":"inbox"}'
python3 scripts/env/client.py request get --payload '{"request_id":"<request-id>"}'
```

## Do Not

- Do not use request actions as a workflow engine or assignment queue.
- Do not move request lifecycle fields into message or task objects.
- Do not reference tracks/artifacts/comments outside the request track context.
