---
name: artifact-tool
description: Use when you need artifact summaries, full artifact reads by id, artifact revision writes, or artifact metadata updates through runtime-owned env tools.
---

# artifact-tool

## Purpose
- Manage product-readable artifact summaries, full-body reads, and durable artifact writes.

## Runtime Route
- CLI: `python3 scripts/env/client.py artifact create-revision --payload '{"title":"Design Direction","summary":"Draft","template":"design","body":"# Design Direction\\n\\nLong markdown body."}'`
- Broker method: `env.tool`
- Discover current operations, payload keys, effects, and recovery guidance with `context.get.tool_catalog['artifact']` or `python3 scripts/turn_runtime.py status`.

## CLI Payload Rule
- `--payload` takes one JSON object string.
- Do not pass a filesystem path to `--payload`.
- For long markdown bodies, generate JSON with `python3 - <<'PY'` and pass it via command substitution.

```bash
python3 scripts/env/client.py artifact create-revision --payload "$(python3 - <<'PY'
import json
print(json.dumps({
  "title": "Design Direction",
  "summary": "Draft",
  "template": "design",
  "body": "# Design Direction\n\nLong markdown body."
}))
PY
)"
```

## Workflow Notes
- `get` returns one full artifact body by `artifact_id`.
- `create-revision` creates an active-buddy private draft/revision only.
- Shared publication starts only after `track.add-material` or `track.add-proof` succeeds.
- For action payloads and return meanings, inspect `context.get.tool_catalog['artifact']` or `python3 scripts/turn_runtime.py status`; runtime response fields are authoritative for effects and recovery.

## Verification
- Confirm `ok=true`, returned ids, and `state_changes` for mutating actions.
- On rejection, trust `permission_boundary`, `why_blocked`, `state_changed`, `durability`, `correctable_fields`, and `alternative_capabilities`.
- Do not edit runtime state files directly.
