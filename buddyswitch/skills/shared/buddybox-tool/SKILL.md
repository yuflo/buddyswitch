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
- CLI:

```bash
python3 scripts/env/client.py buddybox desc
python3 scripts/env/client.py buddybox list --logical-name prototypes --recursive
python3 scripts/env/client.py buddybox read --logical-name prototypes/landing.html
python3 scripts/env/client.py buddybox write --payload /tmp/buddybox-write.json
python3 scripts/env/client.py buddybox delete --logical-name tmp/obsolete.txt
```

## Logical Name Rules
- Use `logical_name` relative to the active buddy private file capability.
- Do not use absolute paths, traversal (`../`), or a buddy id prefix.

## Payload Examples
- Text write:

```json
{"logical_name":"prototypes/landing.html","content":"<!doctype html>","content_type":"text/html"}
```

- Binary write:

```json
{"logical_name":"assets/snapshot.png","content_base64":"<base64>","content_type":"image/png"}
```

- `content` and `content_base64` are mutually exclusive.
- `read --encoding` supports `auto`, `utf-8`, and `base64`.

## Response Rules
- Trust runtime feedback fields: `state_changed`, `durability`, `allowed_next_action_options`, `correctable_fields`, and `alternative_capabilities`.
- `buddybox` writes/deletes mutate active-instance-local private files, not product objects.
- Use `artifact.create_revision` only when the host decides private content must become product-readable.

## Runtime Authority
- For action payloads and return meanings, inspect `context.get.tool_catalog['buddybox']` or `python3 scripts/turn_runtime.py status`; runtime response fields are authoritative for effects and recovery.
