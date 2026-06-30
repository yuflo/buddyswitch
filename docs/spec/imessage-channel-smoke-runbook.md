# iMessage Channel Smoke Runbook

Date: 2026-06-28

## Purpose

Prove the current user-visible iMessage channel contract with the Web-managed lifecycle:

```text
start ./buddyswitch-codex web
  -> Apple ID A sends /actors
  -> Apple ID A selects an actor by number
  -> Apple ID A sends a normal message
  -> Apple ID A immediately sends /actors before the actor reply arrives
  -> the actor list returns promptly
  -> the actor reply returns to the same iMessage chat with the channel prefix
  -> Apple ID B repeats the flow with independent connection and actor selection
```

## Preconditions

- Mac is logged into the BuddySwitch iMessage account in Messages.app.
- `imsg status` reports basic send, receive, and history available.
- `./buddyswitch-codex web` starts successfully.
- At least one BuddySwitch actor is online and appears through the Integration External IM actor list.
- Two sender identities are available for the isolation check.

## Commands

Terminal:

```bash
./buddyswitch-codex web --port 8765
```

Local readiness checks:

```bash
imsg status
imsg chats --limit 1 --json
```

Manual iMessage flow:

```text
1. From Apple ID A, send /actors to the Mac Messages account.
2. Confirm the reply contains numbered rows in the form [n] role_id actor_id.
3. Reply with one number.
4. Confirm the reply is the selected actor id.
5. Send one normal message.
6. Immediately send /actors before the actor reply arrives.
7. Confirm the actor list returns promptly.
8. Confirm the original actor reply still arrives once in the same chat.
9. Confirm the actor reply starts with [Message From act-...].
10. Repeat 1-9 from Apple ID B.
11. Confirm Apple ID B has an independent actor selection and reply route.
```

## Evidence To Record

- Web command and port.
- `imsg status` summary.
- Redacted Apple ID A and Apple ID B sender identities.
- Numbered actor list received by each sender.
- Selected actor id for each sender.
- The normal message id created by BuddySwitch if visible in logs.
- The prompt `/actors` reply received after the normal message and before or independently of the actor reply.
- The outbound prefixed reply text, with sensitive content redacted.
- Whether Apple ID A and B stayed isolated.

## Failure Classification

- Web command fails: BuddySwitch Web or central daemon lifecycle.
- `imsg status` fails: local `imsg` installation, macOS permissions, or Messages account state.
- `/actors` gets no reply: iMessage worker lifecycle, `imsg watch`, or `/api/im/actors`.
- Number selection fails: channel pending choice state.
- Normal message does not reach actor: channel active actor state or `/api/im/messages`.
- `/actors` after a normal message is delayed: inbound worker and outbound poll loop separation.
- Actor reply is not returned: per-sender event polling, route storage, or `imsg send`.
- `imsg send` reports command success but Messages.app shows a failed outbound: local Messages.app send state; inspect the `message` row for `error`, `is_sent`, `is_finished`, and delivery fields.
- Reply lacks prefix: channel outbound projection.
- Sender A/B cross: per-sender state isolation.

## Current Status

Automated channel, Web lifecycle, External IM, Node UI, compile, and residue tests pass.

Manual Apple ID A and Apple ID B smoke passed on 2026-06-29.

## Readiness Evidence 2026-06-29

- `command -v imsg` returned `/opt/homebrew/bin/imsg`.
- `imsg status` reported version `0.11.1` with basic send, receive, and history available.
- `imsg chats --limit 1 --json` returned a readable 1:1 iMessage chat.
- `./buddyswitch-codex web --port 18765` started and served `/api/health`.
- `/api/im/connections` created a connection key through the Web-managed service.
- With actor `act-market-d627587226e7` running, `/api/im/actors` returned one active actor row.
- The temporary actor was stopped after readiness verification.
- The Web server was stopped after readiness verification.

## Second-Sender Audit 2026-06-29

Resolved. Apple ID B live isolation passed with redacted sender `h***@126.com` in chat `3213`.

Cleanup after smoke:

- no Web server listening on `8765`;
- no Web-owned `imsg watch --json` process remains;
- actor `act-market-d627587226e7` is inactive.

## Live Smoke Evidence 2026-06-29

Web lifecycle:

- Resumed actor: `act-market-d627587226e7`, role `market`.
- Started Web entrypoint: `./buddyswitch-codex web --port 8765`.
- `/api/health` returned `{"ok": true}`.
- `/api/im/actors` through the sender connection returned one active actor row for `act-market-d627587226e7`.
- Web-owned `imsg watch --json` process was running under the Web management process.

Apple ID A flow:

- Sender identity: redacted `y***@126.com`.
- Sender key in channel state: `sender:y***@126.com`.
- User sent `/actors`.
- iMessage reply: `[1] market act-market-d627587226e7`.
- User replied `1`.
- iMessage reply: `act-market-d627587226e7`.
- Channel state recorded `active_actor_id: act-market-d627587226e7` for Apple ID A.
- User sent `Please reply exactly: BuddySwitch channel smoke ack 2026-06-29` from the same iMessage chat. The observed Messages.app text used a fullwidth colon after `exactly`, which was preserved as the inbound message content.
- Channel delivered Central IM message `msg-630b82bd3b33` to `act-market-d627587226e7`.
- Actor reply created Central IM message `msg-cd2e190c3d70`, reply event `imev-c9eb5a77e666`, and updated `msg-630b82bd3b33` disposition to `replied`.
- Channel state recorded route `msg-630b82bd3b33 -> chat_id 3211` and outbound dedupe event `imev-c9eb5a77e666`.
- iMessage outbound reply arrived in the same chat:

```text
[Message From act-market-d627587226e7]

BuddySwitch channel smoke ack 2026-06-29
```

Apple ID B flow:

- Passed on 2026-06-29.
- Earlier same-iPhone email-alias attempts appeared in Messages.app as the original redacted `y***@126.com` sender and reused chat `3211`; they correctly did not prove B isolation.
- After the Mac receiving account was changed to redacted `y***@126.com`, a working B sender appeared as redacted `h***@126.com`, chat `3213`.
- The channel sender boundary follows the inbound `imsg` sender field exposed by macOS, not the Mac receiving account and not necessarily the user-visible email alias selected on the phone.
- First B ordinary message before actor selection, `helo`, received the minimal prompt `Send /actors to choose an actor.`
- B `/actors` reply: `[1] market act-market-d627587226e7`.
- B numeric selection reply: `act-market-d627587226e7`.
- B normal message created Central IM inbound `msg-ddb94d601124`.
- B actor reply event `imev-99ac12f48856` was sent back to chat `3213`.
- B iMessage outbound reply arrived:

```text
[Message From act-market-d627587226e7]

Buddyswitch B route smoke ack 2026-06-29
```

- Channel state recorded separate contacts for redacted `h***@126.com` and redacted `y***@126.com`, separate connection keys, separate routes, separate seen inbound keys, and separate outbound event ids.
- Automated tests cover two-sender state isolation for connection keys, pending choices, active actors, routes, and outbound dedupe.
- Final live A/B isolation is verified.

## Outbound Send Status Finding 2026-06-29

A direct send test exposed a lower-level status gap that must be covered before final Phase 4 acceptance:

```text
imsg send --json returned {"status":"sent"}
matching chat.db message row:
  error=22
  is_sent=0
  is_delivered=0
  is_finished=1
```

Successful nearby outbound rows showed `error=0` and `is_sent=1`. Therefore the runbook treats command-level `imsg send` success as submission evidence only. The channel must confirm the route-scoped Messages.app row before marking an outbound reply event as sent.

During live B smoke, row `26750` briefly appeared as `error=0,is_sent=0,is_delivered=0,is_finished=1` and later updated to `is_sent=1,is_delivered=1`. The channel therefore treats `error!=0` as immediate failure but keeps polling no-error unsent rows until success or timeout.
