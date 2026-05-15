---
name: buddybox-tool
description: Use when you need to describe, list, read, write, or delete active-buddy private local files through runtime env tools.
---

# buddybox-tool

## Purpose

- Manage active buddy private local files through broker-routed env tools (`env.tool`).
- Use for private drafts, lightweight prototypes, exports, reports, logs, generated files, and binary outputs.
- Use `artifact.create_revision` when readable content must become product-readable or cross-buddy-readable.

## Runtime Contract

- CLI: `python3 scripts/env/client.py buddybox <operation>`
- Broker method: `env.tool`
- Operations: `desc`, `list`, `read`, `write`, `delete`
- Path convention: every path stays under `<active_buddy>/...`, such as `pm/prototypes/landing.html`.

## Payload Hints

- `write` accepts exactly one of `content` or `content_base64`.
- `content` is UTF-8 text.
- `content_base64` is for binary or non-UTF-8 payloads.
- `content_type` is a MIME hint for the file, not a product contract.
- `read --encoding` accepts `auto`, `utf-8`, or `base64`.

## Response Checks

- Confirm response JSON has `ok=true` before relying on file operation output.
- `desc` and `list` return semantic/summary payloads, not file bodies.
- `write` reports whether the file was created or overwritten.
- `delete` reports whether the file was deleted or already absent.
- Follow `allowed_next_actions` and `allowed_next_action_options`.
- Do not bypass env tools by touching `buddyswitch/local/buddybox/**` paths.
