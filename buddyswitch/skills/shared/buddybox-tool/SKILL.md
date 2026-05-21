---
name: buddybox-tool
description: Use when the active buddy needs private files such as drafts, prototypes, exports, logs, reports, or binary outputs, and needs to operate buddybox through BuddySwitch env tools.
---

# buddybox-tool

## Purpose
- Buddybox is the active buddy private file capability operated through `env.tool`.
- Use it for drafts, lightweight prototypes, exports, logs, reports, generated files, and binary outputs.
- Other buddies cannot list/read/write/delete these files.

## Runtime Route
- CLI: `python3 scripts/env/client.py buddybox write --payload '{"logical_name":"prototypes/landing.html","content":"<!doctype html>","content_type":"text/html"}'`
- Broker method: `env.tool`
- Discover current operations, payload keys, effects, and recovery guidance with `context.get.tool_catalog['buddybox']` or `python3 scripts/turn_runtime.py status`.

## CLI Payload Rule
- `--payload` takes one JSON object string.
- Do not pass a filesystem path to `--payload`.
- For long markdown bodies, generate JSON with `python3 - <<'PY'` and pass it via command substitution.

## Logical Name Rules
- Use `logical_name` relative to the active buddy private file capability.
- Do not use absolute paths, traversal (`../`), or a buddy id prefix.

## Operation Semantics
- `desc`, `list`, and `read` are discovery/read paths for active-buddy private files.
- `write` and `delete` mutate active-instance-local private files only (never product objects).
- For exact payload keys, encoding options, and response fields, inspect `context.get.tool_catalog['buddybox']` or `python3 scripts/turn_runtime.py status`.
- Start with `python3 scripts/env/client.py context summarize --payload '{}'` so buddybox actions run against current runtime-visible state.

## Response Rules
- Trust runtime feedback fields: `state_changed`, `durability`, `allowed_next_action_options`, `correctable_fields`, and `alternative_capabilities`.
- `buddybox` writes/deletes mutate active-instance-local private files, not product objects.
- Use `artifact.create_revision` only when the host decides private content must become product-readable.

## Runtime Authority
- For action payloads and return meanings, inspect `context.get.tool_catalog['buddybox']` or `python3 scripts/turn_runtime.py status`; runtime response fields are authoritative for effects and recovery.
