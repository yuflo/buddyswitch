---
name: comment-tool
description: Use when adding, listing, and PM-resolving comments on readable track, artifact, and artifact_section targets through runtime env tools.
---

# Comment Tool

## Purpose

Add, list, and PM-resolve plain-text comments on readable track, artifact, and artifact_section targets through the runtime env.tool layer.

## Runtime Route
- CLI: `python3 scripts/env/client.py comment add --payload '{"target_type":"track","target_id":"track-alpha","content":"Design direction is ready."}'`
- Broker method: `env.tool`
- Discover current operations, payload keys, effects, and recovery guidance with `context.get.tool_catalog['comment']` or `python3 scripts/turn_runtime.py status`.

## CLI Payload Rule

- `--payload` takes one JSON object string.
- Do not pass a filesystem path to `--payload`.
- For long markdown bodies, generate JSON with `python3 - <<'PY'` and pass it via command substitution.

```bash
python3 scripts/env/client.py comment add --payload '{"target_type":"track","target_id":"track-alpha","content":"Design direction is ready."}'
```

## Workflow Notes

- Use this tool for plain-text discussion on readable track, artifact, and artifact_section targets.
- Start with `python3 scripts/env/client.py context summarize --payload '{}'` so comment actions run against current runtime-visible ids and state.
- PM can close reviewed threads with `comment.resolve` and a non-empty `resolution_summary`.
- Non-PM buddies keep discussion open by adding follow-up rows with `comment.add`.
- For exact operations, payload keys, optional keys, and response fields, inspect `context.get.tool_catalog['comment']` or `python3 scripts/turn_runtime.py status`.

## Key Boundary Rules

- Comment relations are stored on comment objects via `target_type` and `target_id`.
- Workspace views may expose `comment_ids` on tracks/artifacts as derived read-only fields; target objects do not persist those lists.
- Comment objects are immutable after creation. No edit or delete.
- Resolving one `comment_id` resolves its entire thread to durable `status=resolved`.
- Task comments are not supported; accepted target support is discovered from `context.get.tool_catalog['comment']` and currently includes `track`, `artifact`, and `artifact_section`.
- Cross-target replies are rejected (reply must stay on the same target).
- Foreign, superseded, or non-readable artifacts reject comment reads and writes.
- Archived tracks reject comment reads and writes.

## Verification

```bash
python3 scripts/env/client.py comment --help
python3 scripts/env/client.py comment list --payload '{"target_type":"track","target_id":"<track_id>"}'
```

## Do Not

- Do not use for task comments; use runtime discovery for current accepted target support.
- Do not attempt PM-only resolution as a non-PM buddy.
- Do not attempt to edit or delete comments.
- Do not use for direct buddy messaging; use `message.send` instead.
- Do not use for review or approval workflows.
- Do not assume non-comment workflow fields are accepted by comment payloads; confirm allowed keys through runtime discovery first.
