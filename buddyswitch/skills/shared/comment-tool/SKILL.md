---
name: comment-tool
description: Use when adding and listing comments on readable track and artifact targets through runtime env tools.
---

# Comment Tool

## Purpose

Add and list plain-text comments on readable track and artifact targets through the runtime env.tool layer.

## Runtime Route

```
env.tool → comment.add | comment.list
```

The CLI entry point is:

```bash
python3 scripts/env/client.py comment <operation>
```

## CLI Payload Rule

- `--payload` takes one JSON object string.
- Do not pass a filesystem path to `--payload`.
- For long markdown bodies, generate JSON with `python3 - <<'PY'` and pass it via command substitution.

```bash
python3 scripts/env/client.py comment add --payload '{"target_type":"track","target_id":"track-alpha","content":"Design direction is ready."}'
```

## Operations

- `comment.add` writes one plain-text comment on a readable `track` or `artifact` target.
- `comment.list` reads comments on the same readable target classes.
- For exact payload keys, optional keys, and response fields, inspect `context.get.tool_catalog['comment']` or `python3 scripts/turn_runtime.py status`.
- Start with `python3 scripts/env/client.py context summarize` so comment operations run against current runtime-visible ids and state.

## Key Boundary Rules

- Comment relations are stored on comment objects via `target_type` and `target_id`.
- Workspace views may expose `comment_ids` on tracks/artifacts as derived read-only fields; target objects do not persist those lists.
- Comment objects are immutable after creation. No edit or delete.
- Task comments are not supported; only `track` and `artifact` targets are accepted.
- Cross-target replies are rejected (reply must stay on the same target).
- Foreign, superseded, or non-readable artifacts reject comment reads and writes.
- Archived tracks reject comment reads and writes.

## Verification

```bash
python3 scripts/env/client.py comment --help
python3 scripts/env/client.py comment list --target-type track --target-id <track_id>
```

## Do Not

- Do not use for task comments; only track and artifact targets are accepted.
- Do not use for resolution workflows, status tracking (`resolved`, `status`), or assignment.
- Do not attempt to edit or delete comments.
- Do not use for direct buddy messaging; use `message.send` instead.
- Do not use for review or approval workflows.
- Do not assume non-comment workflow fields are accepted by comment payloads; confirm allowed keys through runtime discovery first.
