# Message Tool

## Purpose

Send and read direct buddy-to-buddy inbox messages through the runtime env.tool layer.

## Runtime Route

```
env.tool → message.send | message.list
```

The CLI entry point is:

```bash
python3 scripts/env/client.py message <operation>
```

## Operations

### message.send

Send a direct message to another declared manifest buddy.

**Payload:**

```json
{
  "to_buddy": "design",
  "content": "Plain text message body",
  "reply_to": "msg-abc123def456"
}
```

**Rules:**
- `to_buddy` is required and must be a buddy declared in `buddyswitch/manifest.toml`.
- `to_buddy` must not equal the active buddy (no self-send).
- `content` is required, plain text, non-empty after trimming.
- `reply_to` is optional. When present, it must reference an existing message in the same {active_buddy, to_buddy} conversation pair where the active buddy is a participant.

**Returns:** `message_id` and full `message` object.

### message.list

Read inbox messages sent to the active buddy.

**Payload:**

```json
{
  "buddy": "design"
}
```

**Rules:**
- Returns only messages where `to_buddy == active_buddy`.
- Optional `buddy` filter narrows results by `from_buddy`.
- No status filter, no sent-mail view, no unread/read differentiation.
- Read-only: does not mutate message state or create read receipts.

**Returns:** `messages` list and `discovery_summary`.

## Key Boundary Rules

- Messages are direct buddy-to-buddy only. Each has exactly `from_buddy` and `to_buddy`.
- Message objects are immutable after creation. No edit or delete.
- Active buddy cannot send to itself.
- Reply envelopes must stay within the same conversation pair.
- List returns only inbox (to_buddy = active_buddy), not outbox.

## Verification

```bash
python3 scripts/env/client.py message --help
python3 scripts/env/client.py message list
```

## Do Not

- Do not use for broadcast, group messaging, or multi-recipient sends.
- Do not use for read receipts, unread counts, or message status tracking.
- Do not use for object-level discussion; use `comment.add` for track/artifact comments.
- Do not attempt to edit or delete sent messages.
- Do not include `track_id`, `task_id`, `artifact_id`, `status`, `read_at`, or `broadcast` fields in send payloads.
