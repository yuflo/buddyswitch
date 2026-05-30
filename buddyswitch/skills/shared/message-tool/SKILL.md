---
name: message-tool
description: Use when sending and reading direct runtime actor-address messages through env.tool.
---

# Message Tool

## Purpose

Send direct messages to online runtime actor addresses and read message context through the runtime env.tool layer.

## Runtime Route

- Primary: use native BuddySwitch env MCP tools such as `message__contacts`, `message__send`, `message__list`, and `message__conversation` when available.
- Fallback CLI: `python3 scripts/env/client.py message <action> --payload '<json-object>'`
- Broker method: `env.tool`
- Discover exact operations, payload keys, effects, and recovery guidance with `context.get.tool_catalog['message']` or `python3 scripts/turn_runtime.py status`.

## CLI Payload Rule

- `--payload` takes one JSON object string.
- Do not pass a filesystem path to `--payload`.
- For long markdown bodies, generate JSON with `python3 - <<'PY'` and pass it via command substitution.

## Workflow Notes

Find an online target actor first:

```bash
python3 scripts/env/client.py message contacts --payload '{"buddy":"market"}'
```

Send by copying `contact.actor_address` into `target_actor_address`:

```bash
python3 scripts/env/client.py message send --payload '{"target_actor_address":{"buddy_id":"market","instance_id":"inst-market-ae219d1e9e24"},"content":"Please review track-alpha."}'
```

Read active actor inbox messages:

```bash
python3 scripts/env/client.py message list --payload '{}'
```

Read active actor visible bidirectional context with a target buddy or exact actor:

```bash
python3 scripts/env/client.py message conversation --payload '{"buddy":"market","limit":20}'
```

## Key Boundary Rules

- `message.contacts` returns online contact rows with `contact.actor_address`.
- `message.send` requires `target_actor_address` copied from a current contact row.
- `message.list` reads only the active actor inbox; it does not accept `box`.
- `message.conversation` reads active actor visible bidirectional messages with a selected target buddy or actor.
- Message objects are immutable after creation. No edit or removal workflow exists for normal users.
- Active buddy cannot send to another actor with the same buddy id.
- Reply envelopes must stay within the same two-actor conversation pair.
- Use `request.list` when you need inbox/outbox request filtering.

## Verification

```bash
python3 scripts/env/client.py message --help
python3 scripts/env/client.py message list --payload '{}'
```

## Do Not

- Do not use for broadcast, group messaging, or multi-recipient sends.
- Do not use for read receipts, unread counts, or message status tracking.
- Do not use for object-level discussion; use `comment.add` for track/artifact comments.
- Do not assume extra status or object-linking fields are accepted in send payloads; confirm allowed keys through runtime discovery first.
