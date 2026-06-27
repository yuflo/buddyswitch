---
name: message-tool
description: Use when sending and reading direct runtime identity messages through env.tool.
---

# Message Tool

## Purpose

Send direct messages to online actor identities and read message context through the runtime env.tool layer.

## Runtime Route

- Primary: use native BuddySwitch env MCP tools such as `message__contacts`, `message__send`, `message__get`, `message__mark`, `message__list`, and `message__conversation`.
- Exact payload schemas, allowed fields, effects, and response meanings come from native tool schemas and `context.get.tool_catalog['message']`.
- Diagnostic fallback: `python3 scripts/turn_runtime.py status`.
- Broker method remains `env.tool`; do not edit runtime state files directly.

## Workflow Notes

- Use `message__contacts` first when you need a current online target actor identity.
- Copy `contact.identity_id` from a contact row into `target_identity_id` for `message__send`.
- Use `message__get` when a prompt gives you an exact `message_id`; process that exact message.
- Use `message__mark` to finish an exact inbound message as `absorbed` or to mark `needs_parent` with a reason.
- Use `message__list` to read active actor inbox rows.
- Use `message__conversation` to read active actor visible bidirectional context with a selected target identity.
- Runtime response fields are authoritative for effects, rejection reasons, and recovery.

## Key Boundary Rules

- `message__contacts` returns online contact rows with `contact.identity_id`.
- `message__send` requires `target_identity_id` copied from current contact data.
- `message__send` with `reply_to` finishes a processable inbound message as `replied` after delivery succeeds.
- `message__get` reads one processable inbound message by exact id and returns disposition metadata.
- `message__mark` only accepts `absorbed` or `needs_parent`; `needs_parent` requires a reason.
- `message__list` reads only the active actor inbox; it does not accept `box`.
- `message__conversation` reads active actor visible bidirectional messages with a selected target identity.
- Message objects keep disposition metadata for processing. No edit or removal workflow exists for normal users.
- Active actor cannot send to itself; same role with a different actor is allowed.
- Reply envelopes must stay within the same direct identity conversation pair.

## Do Not

- Do not use for broadcast, group messaging, or multi-recipient sends.
- Do not use for read receipts, unread counts, or message status tracking.
- Do not use for Track discussion; use `track__add_comment` for Track-scoped comments.
- Do not assume extra status or object-linking fields are accepted in send payloads; confirm allowed keys through runtime discovery first.
