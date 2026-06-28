# iMessage Bridge Smoke Runbook

Date: 2026-06-28

## Purpose

Prove the MVP user-visible contract:

```text
allowlisted iPhone sender sends text
  -> Mac imsg watch sees inbound row
  -> bridge POSTs to /api/im/messages
  -> target actor wakes and replies through Central IM
  -> bridge reads /api/im/events and sends reply through imsg
  -> iPhone sees reply in the same chat
```

This runbook is not a substitute for the real smoke. It defines the exact
evidence needed to accept Stage 4.

## Preconditions

- Mac is logged into the BuddySwitch iMessage account in Messages.app.
- `imsg status` reports basic send/receive/history available.
- `imsg chats --limit 1 --json` can read at least one chat.
- A target BuddySwitch actor is available from `/api/im/actors`.
- One sender handle is explicitly allowlisted.
- The sender can send a live test message from iPhone to this Mac account.

## Current Local Evidence

Command:

```bash
imsg status
```

Observed on 2026-06-28:

```text
imsg 0.11.1
Basic features (send, receive, history): Available
Advanced features (typing, read receipts): Not available
```

Command:

```bash
imsg chats --limit 1 --json
```

Observed on 2026-06-28:

```text
Returned one 1:1 iMessage chat. Handles/account identifiers are redacted from this runbook.
```

Command:

```bash
python -m pytest tests/test_im_external_reply_loop.py tests/test_imessage_bridge.py -q
```

Observed on 2026-06-28:

```text
13 passed
```

Command:

```bash
imsg chats --limit 1 --json
imsg history --chat-id <redacted_chat_id> --limit 1 --json
```

Observed on 2026-06-28:

```text
Read access confirmed for one 1:1 iMessage chat and one redacted history row.
```

Command:

```bash
imsg watch --json
```

Observed on 2026-06-28 with a 2 second non-mutating timeout:

```text
watch_started=true; no stderr; no live message arrived during the timeout.
```

## Real Smoke Commands

Terminal 1:

```bash
./buddyswitch-codex web --port 8765
```

Terminal 2:

```bash
./buddyswitch-codex imessage bridge \
  --server http://127.0.0.1:8765 \
  --target-identity-id <actor_identity_id> \
  --allow-sender <iphone_sender_phone_or_email>
```

iPhone:

```text
Send one plain text message from <iphone_sender_phone_or_email> to the Mac Messages account.
```

## Evidence To Record

- Exact `target_identity_id`.
- Redacted allowlisted sender handle.
- Bridge startup output or log.
- The inbound `imsg` row fields needed for routing:
  - `rowid` or `guid`
  - `chat_id`, `chat_identifier`, or `chat_guid`
  - `sender`
  - `is_from_me=false`
- BuddySwitch `/api/im/messages` accepted response:
  - message id
  - event id
  - wake status
- Actor reply message id.
- Bridge outbound event id.
- `imsg send` target route.
- iPhone observation that the reply arrived in the same chat.

## Failure Classification

Classify failures before changing code:

- `imsg status` fails: local `imsg` or macOS permissions.
- `imsg chats` fails: Messages database access or Full Disk Access.
- `imsg watch` sees no inbound after iPhone sends: Apple/Messages sync or watch filtering.
- Bridge rejects sender: allowlist/config issue.
- Bridge cannot validate target actor: BuddySwitch actor availability or wrong `target_identity_id`.
- `/api/im/messages` fails: Integration External IM HTTP API or External IM Session issue.
- Actor does not reply: actor runtime/message tool/wake issue.
- `/api/im/events` has no reply: Central IM event visibility/cursor issue.
- `imsg send` fails: Messages.app send permission, route, or account issue.
- iPhone receives nothing after `imsg send` succeeds: Apple delivery/account state.

## Stage 4 Status

Accepted.

Automated acceptance, local `imsg` status/read/history/watch checks, and a live
allowlisted sender run passed.

Machine-side evidence:

- `target_identity_id`: `act-market-89316cc41041`.
- allowlisted sender: redacted `yuflo2024@...` iMessage identity.
- bridge state recorded inbound `guid:7653DB45-805C-4056-8773-256F58898952`.
- bridge routed the inbound message to BuddySwitch message `msg-a91192cbfcca`.
- actor replied with `msg-360dbc552871`.
- bridge consumed outbound event `imev-48739eadd35b`.
- local Messages history shows a same-chat outbound iMessage row with
  `is_from_me=true` and content `Buddyswitch smoke ack 2026-06-28`.
- User confirmed the iPhone saw that reply in the same iMessage chat.

Stage 4 is accepted.
