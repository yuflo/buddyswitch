---
name: message-tool
description: Use when sending and reading direct buddy-to-buddy inbox messages through runtime env tools.
---

# Message Tool

## Purpose

Send and read direct buddy-to-buddy inbox messages through the runtime env.tool layer.

## Runtime Route
- CLI: `python3 scripts/env/client.py message send --payload '{"to_buddy":"design","content":"Please review track-alpha."}'`
- Broker method: `env.tool`
- Discover current operations, payload keys, effects, and recovery guidance with `context.get.tool_catalog['message']` or `python3 scripts/turn_runtime.py status`.

## CLI Payload Rule

- `--payload` takes one JSON object string.
- Do not pass a filesystem path to `--payload`.
- For long markdown bodies, generate JSON with `python3 - <<'PY'` and pass it via command substitution.

```bash
python3 scripts/env/client.py message send --payload '{"to_buddy":"design","content":"Please review the PRD on track-alpha."}'
```

## Workflow Notes

- Use this tool for direct buddy-to-buddy inbox communication.
- Start with `python3 scripts/env/client.py context summarize` so message actions run against current runtime-visible buddy ids and state.
- For exact operations, payload keys, optional keys, and response fields, inspect `context.get.tool_catalog['message']` or `python3 scripts/turn_runtime.py status`.

## Key Boundary Rules

- Messages are direct buddy-to-buddy only. Each has exactly `from_buddy` and `to_buddy`.
- Message objects are immutable after creation. No edit or delete.
- Active buddy cannot send to itself.
- Reply envelopes must stay within the same conversation pair.
- List returns only inbox (to_buddy = active_buddy), not outbox.

## Verification

```bash
python3 scripts/env/client.py message --help
python3 scripts/env/client.py message list
```

## Do Not

- Do not use for broadcast, group messaging, or multi-recipient sends.
- Do not use for read receipts, unread counts, or message status tracking.
- Do not use for object-level discussion; use `comment.add` for track/artifact comments.
- Do not attempt to edit or delete sent messages.
- Do not assume extra status or object-linking fields are accepted in send payloads; confirm allowed keys through runtime discovery first.
