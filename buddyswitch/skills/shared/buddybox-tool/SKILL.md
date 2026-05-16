---
name: buddybox-tool
description: Use when the active buddy needs private files such as drafts, prototypes, exports, logs, reports, or binary outputs, and needs to operate buddybox through BuddySwitch env tools.
---

# buddybox-tool

## What Buddybox Is

- Buddybox is the active buddy private file capability and is operated through `env.tool`.
- Other buddies cannot list/read/write/delete these files.
- Buddybox logical names are not cross-buddy payload authority.
- Product-readable or cross-buddy-readable content must be carried by artifact or another explicit product object.

## Use It When

- When to use buddybox: private drafts, lightweight prototypes, exports, logs, reports, generated files, or binary outputs are needed.
- You need local iterative file work before deciding whether anything should be promoted.

## Do Not Use It When

- When not to use buddybox: you are producing product deliverables that other buddies must read.
- You are editing shared source or transport payloads for handoff.
- You are mutating `buddyswitch/objects/**` or directly editing `buddyswitch/local/buddybox/**`.

## Commands

```bash
python3 scripts/env/client.py buddybox desc
python3 scripts/env/client.py buddybox list --logical-name prototypes --recursive
python3 scripts/env/client.py buddybox read --logical-name prototypes/landing.html
python3 scripts/env/client.py buddybox write --payload /tmp/buddybox-write.json
python3 scripts/env/client.py buddybox delete --logical-name tmp/obsolete.txt
```

## Logical Name Rules

- Use `logical_name` relative to the active buddy private file capability (example: `prototypes/landing.html`).
- Do not use absolute paths, traversal (`../`), or any buddy id as the first segment.

## Payload Rules

- Text write payload:

```json
{"logical_name":"prototypes/landing.html","content":"<!doctype html>","content_type":"text/html"}
```

- Binary write payload:

```json
{"logical_name":"assets/snapshot.png","content_base64":"<base64>","content_type":"image/png"}
```

- `content` is UTF-8 text.
- `content_base64` is for binary or non-UTF-8 bytes.
- `content` and `content_base64` are mutually exclusive.
- `content_type` is a MIME hint.
- `read --encoding` supports `auto`, `utf-8`, or `base64`.

## Response Checks

- Inspect `ok`, `state_changed`, `durability`, and `logical_name`.
- Inspect `allowed_next_actions` and `allowed_next_action_options` before selecting follow-ups.
- Use created/overwrote/deleted fields to verify target effects.
- Trust structured rejection feedback for boundary-safe retries.

## Promotion Rule

- Use `artifact.create_revision` only when content must become product-readable or cross-buddy-readable.

## Runtime Closing

- Summarize which private buddybox files were written, updated, or deleted.
- Summarize artifact or handoff status.
- If blocked, include the tool rejection reason and the next action.

## Common Flows

- Write/update: `write` then `read` for one exact file and inspect `allowed_next_actions`.
- List/read: `list` for summaries, then `read` for one exact logical name.
- Search-or-inspect: `buddybox.read` is exact-file read and `buddybox.list` returns summaries only. For keyword or regex search, inspect `context.get.tool_catalog['buddybox']` or `python3 scripts/turn_runtime.py status`; use `buddybox.search` only when available. In the current runless catalog, use `list` then exact `read`. Do not shell-search buddybox roots as the normal buddy workflow.
- Delete cleanup: `delete` stale private files and verify `state_changed`.
- Promotion: call `artifact.create_revision` only when readability must move beyond active-buddy-private scope.
- Rejection recovery: read `allowed_next_action_options`, correct logical_name/payload shape, and retry through `python3 scripts/env/client.py buddybox <operation>`.
