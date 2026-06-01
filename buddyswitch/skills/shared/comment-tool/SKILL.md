---
name: comment-tool
description: Use when adding, listing, and PM-resolving comments on readable track, artifact, and artifact_section targets through runtime env tools.
---

# Comment Tool

## Purpose

Add, list, and PM-resolve plain-text comments on readable track, artifact, and artifact_section targets through the runtime env.tool layer.

## Runtime Route
- Primary: use native BuddySwitch env MCP tools such as `comment__list`, `comment__add`, and `comment__resolve`.
- Exact payload schemas, accepted target support, effects, and response meanings come from native tool schemas and `context.get.tool_catalog['comment']`.
- Diagnostic fallback: `python3 scripts/turn_runtime.py status`.
- Broker method remains `env.tool`; do not edit runtime state files directly.

## Workflow Notes

- Use `context__summarize` when you need current runtime-visible ids before comment actions.
- Use `comment__list` for existing discussion on readable `track`, `artifact`, and `artifact_section` targets.
- Use `comment__add` to add plain-text follow-up rows.
- PM can close reviewed threads with `comment__resolve` and a non-empty resolution summary.
- Runtime response fields are authoritative for effects, rejection reasons, and recovery.

## Key Boundary Rules

- Comment relations are stored on comment objects via `target_type` and `target_id`.
- Workspace views may expose `comment_ids` on tracks/artifacts as derived read-only fields; target objects do not persist those lists.
- Comment objects are immutable after creation. No edit or delete.
- Resolving one `comment_id` resolves its entire thread to durable `status=resolved`.
- Task comments are not supported; accepted target support is discovered from `context.get.tool_catalog['comment']` and currently includes `track`, `artifact`, and `artifact_section`.
- Cross-target replies are rejected; replies must stay on the same target.
- Foreign, superseded, or non-readable artifacts reject comment reads and writes.
- Archived tracks reject comment reads and writes.

## Do Not

- Do not use for task comments.
- Do not attempt PM-only resolution as a non-PM role.
- Do not attempt to edit or delete comments.
- Do not use for direct role messaging; use `message__send` instead.
- Do not use for review or approval workflows.
- Do not assume non-comment workflow fields are accepted; confirm allowed fields through runtime discovery first.
