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

### comment.add

Add a comment to a readable track or artifact.

**Payload:**

```json
{
  "target_type": "artifact",
  "target_id": "art-dev-example",
  "content": "Plain text comment body",
  "reply_to": "comment-abc123def456"
}
```

**Rules:**
- `target_type` must be exactly `track` or `artifact`. Task targets are rejected.
- `target_id` is required.
- `content` is required, plain text, non-empty after trimming.
- `reply_to` is optional. When present, it must reference an existing comment on the same target (same `target_type` and `target_id`).
- The active buddy must have read access to the target:
  - Tracks: track must exist and not be archived.
  - Artifacts: reuse existing artifact visibility rules (ownership, track relation, currentness).

**Returns:** `comment_id`, full `comment` object, `target_type`, `target_id`.

### comment.list

List comments attached to a readable track or artifact.

**Payload:**

```json
{
  "target_type": "track",
  "target_id": "track-alpha"
}
```

**Rules:**
- Same target type and read access rules as `comment.add`.
- Returns only comments whose stored `target_type` and `target_id` match the target.
- Read-only: does not mutate comment or target state.

**Returns:** `comments` list, `target_type`, `target_id`, `discovery_summary`.

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
- Do not include `resolved`, `resolved_at`, `status`, `edit_history`, `attachment`, or `task_id` fields in add payloads.
