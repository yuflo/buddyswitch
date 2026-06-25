# BuddySwitch IM Central Contract Boundary Review

## Purpose

This memo supplements [buddyswitch-im-gateway-rebuild.md](./buddyswitch-im-gateway-rebuild.md).

It answers the review questions that must be settled before implementation:

1. whether user/external address and actor address belong to one system;
2. where physical message storage lives and who owns it;
3. what happens to side/parent message handling and innerTUI-driven actor processing;
4. how fake `user-actor` is removed without dual-track compatibility;
5. which message-driven surrounding surfaces are preserved, migrated, or deleted;
6. whether the rebuilt IM system is maintainable inside BuddySwitch rather than scattered across unrelated modules.

Status: design review document. It records target design from current code inspection. It does not claim the code already implements the target.

## Code Facts Checked

Current implementation has these concrete paths:

- [tools/launcher/web_user_actor.py](../../tools/launcher/web_user_actor.py)
  - defines `WEB_USER_ACTOR_ADDRESS = {"role_id": "user", "actor_id": "act-user-local"}`;
  - builds a fake mailbox sink;
  - registers that fake actor through `daemon_client.register_actor`;
  - sends web messages through `message_service.send_from_web_user`.

- [tools/launcher/web_management.py](../../tools/launcher/web_management.py)
  - imports `web_user_actor`;
  - exposes `POST /api/messages/send`;
  - starts `WebUserActorRuntime` in `main()`.

- [scripts/env/services/messages.py](../../scripts/env/services/messages.py)
  - has `send_from_web_user`;
  - `send_from_actor` writes a message row through `context.repos.message.create_message`;
  - then calls `context.daemon.deliver_message_available`;
  - deletes the just-created message if signal delivery fails.

- [scripts/env/repos/messages.py](../../scripts/env/repos/messages.py)
  - stores message rows as physical JSON files under `runtime_files.MESSAGES_DIR`;
  - one row currently mixes content, sender, receiver, `reply_to`, and disposition.

- [tools/launcher/central_daemon_core.py](../../tools/launcher/central_daemon_core.py)
  - owns actor registry, `contacts.list`, reachability, and generic `signal.deliver`;
  - currently delivers signals to `daemon_mailbox_socket`;
  - does not own message truth yet.

- [tools/launcher/daemon_mailbox.py](../../tools/launcher/daemon_mailbox.py)
  - validates and dispatches generic signal envelopes over local sockets;
  - is runtime transport, not durable message storage.

- [tools/launcher/message_available_handler.py](../../tools/launcher/message_available_handler.py)
  - handles `message.available`;
  - converts it into parent handling or side triage;
  - contains runtime handling experience that must be preserved, but the event contract must be replaced.

- [tools/launcher/message_inbound.py](../../tools/launcher/message_inbound.py)
  - registers `message.available` as a message-owned inbound notification.

- [scripts/env/tools/message/_impl.py](../../scripts/env/tools/message/_impl.py)
  - reads conversation from `context.repos.message.list_messages`;
  - currently depends on old message repo semantics.

These facts mean the existing system is not just one HTTP endpoint. The old message path is a chain:

```text
web/user adapter or actor tool
  -> old message service
  -> old message JSON row
  -> central signal.deliver
  -> daemon mailbox
  -> message.available handler
  -> parent/side runtime
```

The rebuild must replace this chain as a main path, not add a second chain beside it.

## Design Decision 0: IM Is a Built-In Product, Not a Launcher Interface

The IM rebuild must follow this boundary:

```text
product core -> interface projection -> consumer surface
```

For this task:

```text
IM product core
  scripts/env/services/messages.py
  scripts/env/domain/messages.py
  scripts/env/repos/messages.py
  owns model, storage, rules, and business contracts

Interface projections
  scripts/env/tools/message/*
  /api/im/* HTTP router
  WebManagement UI
  innerTUI wake prompt surface
  adapt product capability for one consumer

Host/control plane
  tools/launcher/central_daemon_core.py
  actor registry / reachability
  HTTP mounting
  runtime wake bridge
  delegates IM business operations to product core
```

This is a correction to any wording that makes `tools/launcher` look like the owner of IM semantics.

`tools/launcher` may host HTTP and wake runtime integration. It must not own participant rules, conversation rules, message state, cursor semantics, or durable IM store writes.

## Design Decision 1: One IM Participant System, Two Address Forms

User/external address and actor address belong to the same IM participant system, but they are not the same address type.

Target participant union:

```text
IM Participant
  ActorParticipant
    actor_address = {role_id, actor_id}
    has actor registry record
    can be reached through runtime wake

  ExternalParticipant
    external_id
    participant_token
    display_name
    has no actor registry record
    receives through event cursor / long-poll
```

Rules:

- `display_name` is observability only. It is not an address and not a routing key.
- `external_id` is the IM address for an external participant.
- `participant_token` authenticates access for that `external_id`.
- `event_cursor` is a read position, not identity.
- external participants must not be registered through `daemon.register`.
- `role_id=user` must not be accepted as an actor role compatibility escape.

The unified model is:

```text
participant -> Central IM -> participant
```

Concrete cases:

```text
external -> actor
  ExternalParticipant -> Central IM HTTP Contract -> ActorParticipant

actor -> actor
  ActorParticipant -> Central IM HTTP Contract -> ActorParticipant
```

The sending model is the same. The receiving mechanics differ:

- actor participant can be woken by the runtime;
- external participant reads via event cursor / long-poll.

## Design Decision 2: IM Product Core Owns Physical Message Truth

Message physical storage moves from the old single-row `messages/*.json` model into a central IM store.

Target store root:

```text
state/im/
  participants/
  sessions/
  conversations/
  messages/
  message_states/
  events/
  cursors/
```

Ownership:

- IM product core owns all writes to `state/im/*`.
- The owning code should live in `scripts/env/services/messages.py`, `scripts/env/domain/messages.py`, and `scripts/env/repos/messages.py`, or a narrow message-owned split under the same `scripts/env` product layer if the file size forces it.
- Actor tools do not write message files directly.
- WebManagement does not construct message rows.
- daemon mailbox does not store IM messages.
- instance daemons do not own per-actor inbox truth.
- `tools/launcher` modules do not write IM store directly.

Minimum physical objects:

```text
participants/{external_id}.json
  external participant profile and display metadata

sessions/{token_hash}.json
  token hash -> external_id binding

conversations/{conversation_id}.json
  participant set and direct conversation metadata

messages/{message_id}.json
  immutable-ish message body, sender, recipients, reply_to, timestamps

message_states/{message_id}--{participant_key}.json
  per participant disposition, processing state, updated_at

events/{event_id}.json
  participant-visible event item

cursors/{participant_key}.json
  server-side high-water cursor metadata for long-poll support
```

Participant keys are normalized strings derived from participant identity:

```text
actor:market:act-market-607eca23170c
external:ext-01jabc000001
```

The exact filename escaping belongs in implementation. The architectural rule is that actor and external participants share the same IM store model.

## Design Decision 3: Central Daemon Service Becomes the Host Control Plane

Current `central_daemon_core.py` already owns actor registry and reachability. The rebuild extends that host/control plane instead of creating a separate distributed message truth.

Target central responsibility:

```text
central-daemon-service
  actor registry / reachability
  HTTP host for Central IM Contract
  IM runtime wake adapter
  delegates participant/conversation/message/event/cursor operations
```

Module boundary:

```text
scripts/env/services/messages.py
  IM product service
  owns send/read/reply/events/disposition contract semantics

scripts/env/domain/messages.py
  IM product domain
  owns participant, conversation, message, cursor, disposition rules

scripts/env/repos/messages.py
  IM product repo
  owns state/im/* physical normalization and persistence

tools/launcher/central_daemon_core.py
  existing daemon RPC server and actor registry
  host control plane for reachability and wake

optional tools/launcher/central_im_host.py
  thin host adapter only if implementation needs one
  delegates to scripts/env IM product core
  owns no message model, store, or rules

tools/launcher/im_http_router.py
  parses /api/im/* HTTP requests
  validates auth surface
  calls IM product service through the host boundary
  shapes HTTP responses
```

`WebManagementService` can mount the router, but it must not own IM semantics.

Forbidden split:

```text
tools/launcher/central_im_service.py
  owns participants, conversations, messages, states, events, cursors
```

That would place product semantics in a launcher interface layer, which violates the built-in product boundary.

## Design Decision 4: HTTP Is the IM Business Contract

HTTP rebuild means IM business operations move to `/api/im/*`.

It does not mean central daemon and instance daemon runtime control must become HTTP.

Separation:

```text
IM business layer
  external / web / innerTUI / actor tool
    -> Central IM HTTP Contract

runtime control layer
  Central IM accepted message
    -> runtime wake adapter
    -> instance daemon / app-server / innerTUI / parent-side handling
```

Required HTTP endpoints:

```text
POST /api/im/external-participants
GET  /api/im/actors?role_id=market
POST /api/im/messages
GET  /api/im/messages/{message_id}
GET  /api/im/messages/{message_id}/replies
GET  /api/im/conversations/direct?kind=actor&role_id=market&actor_id=act-market-607eca23170c
GET  /api/im/events?cursor=imev-000000000000&limit=50&wait_ms=25000
PATCH /api/im/messages/{message_id}/disposition
```

External caller:

```text
Authorization: Bearer impt_01jabc_secret
```

Actor tool caller:

```text
runtime actor identity from active actor context
```

Actor tools use a local client:

```text
scripts/env/tool_runtime/im_client.py
```

This client is a projection adapter. It should shape authenticated actor-tool requests into the Central IM HTTP Contract. It should not implement participant rules, conversation rules, cursor semantics, or durable store writes.

The actor tool names can remain stable:

```text
message__send
message__get
message__list
message__conversation
message__mark
message__contacts
```

Their implementation must call the Central IM contract, not the old repo/signal path. `scripts/env/tools/message/tool.py` must also describe the IM participant/conversation/message/event model instead of the old direct actor-address inbox-row model.

## Minimum Phase-Level Schema / Contract

This section defines the target schema needed before implementation. It is not a description of current behavior.

### Common Primitives

Actor address keeps the existing runtime identity shape:

```json
{
  "role_id": "market",
  "actor_id": "act-market-607eca23170c"
}
```

Validation source:

```text
role_id  -> /^[a-z][a-z0-9-]*$/
actor_id -> /^act-[A-Za-z0-9._-]+$/
```

Participant reference:

```json
{
  "kind": "actor",
  "actor_address": {
    "role_id": "market",
    "actor_id": "act-market-607eca23170c"
  }
}
```

```json
{
  "kind": "external",
  "external_id": "ext-01jabc000001"
}
```

Participant profile for external participants:

```json
{
  "kind": "external",
  "external_id": "ext-01jabc000001",
  "client_kind": "script",
  "display_name": "local smoke",
  "created_at": "2026-06-25T00:00:00Z",
  "last_seen_at": "2026-06-25T00:00:00Z"
}
```

`participant_token` is never stored in plain text. The session store uses a token hash.

### Phase 1: External Registration

Request:

```http
POST /api/im/external-participants
Content-Type: application/json
```

```json
{
  "client_kind": "script",
  "display_name": "local smoke"
}
```

Response:

```json
{
  "ok": true,
  "participant": {
    "kind": "external",
    "external_id": "ext-01jabc000001",
    "client_kind": "script",
    "display_name": "local smoke"
  },
  "participant_token": "impt_01jabc_secret",
  "event_cursor": "imev-000000000000"
}
```

Store writes:

```text
state/im/participants/ext-01jabc000001.json
state/im/sessions/sha256-3f4a8d1c2b7e90aa.json
state/im/cursors/external--ext-01jabc000001.json
```

Session object:

```json
{
  "token_hash": "sha256:3f4a8d1c2b7e90aa",
  "participant": {
    "kind": "external",
    "external_id": "ext-01jabc000001"
  },
  "created_at": "2026-06-25T00:00:00Z",
  "last_used_at": "2026-06-25T00:00:00Z"
}
```

Cursor object:

```json
{
  "participant": {
    "kind": "external",
    "external_id": "ext-01jabc000001"
  },
  "last_event_id": "imev-000000000000",
  "updated_at": "2026-06-25T00:00:00Z"
}
```

Rules:

- `display_name` must not become route identity.
- external registration must not call `daemon.register`.
- external registration must not create mailbox socket files.

### Phase 1: Actor Address Discovery

Request:

```http
GET /api/im/actors?role_id=market
Authorization: Bearer impt_01jabc_secret
```

Response:

```json
{
  "ok": true,
  "actors": [
    {
      "participant": {
        "kind": "actor",
        "actor_address": {
          "role_id": "market",
          "actor_id": "act-market-607eca23170c"
        }
      },
      "reachability_status": "online"
    }
  ],
  "count": 1
}
```

Source of truth:

```text
central daemon actor registry / reachability
```

Rules:

- actor discovery returns actor participants, not external participants.
- external participant registration does not affect actor discovery.

### Phase 1: Send Message

External request:

```http
POST /api/im/messages
Authorization: Bearer impt_01jabc_secret
Content-Type: application/json
```

```json
{
  "to": {
    "kind": "actor",
    "actor_address": {
      "role_id": "market",
      "actor_id": "act-market-607eca23170c"
    }
  },
  "content": "你好，收到后请回复 pong",
  "reply_to": null
}
```

Actor request uses the same body shape, but sender identity comes from active actor runtime context rather than `Authorization: Bearer`.

Response:

```json
{
  "ok": true,
  "message": {
    "id": "msg-01jabc000001",
    "conversation_id": "conv-01jabc000001",
    "reply_to": null
  },
  "event_id": "imev-01jabc000001",
  "delivery_status": "accepted",
  "wake_status": "submitted",
  "next_cursor": "imev-01jabc000001"
}
```

Allowed `wake_status` values:

```text
submitted
target_not_online
wake_failed
not_applicable
```

Rules:

- `delivery_status=accepted` means the message and event are durable in IM product store.
- `wake_status` reports runtime wake only.
- wake failure must not delete the message.
- sender cannot submit `from` in the request body.
- `reply_to` must reference a visible message in the same conversation.

### Phase 1: Store Objects Created by Send

Conversation:

```json
{
  "id": "conv-01jabc000001",
  "type": "direct",
  "participants": [
    {
      "kind": "external",
      "external_id": "ext-01jabc000001"
    },
    {
      "kind": "actor",
      "actor_address": {
        "role_id": "market",
        "actor_id": "act-market-607eca23170c"
      }
    }
  ],
  "created_at": "2026-06-25T00:00:00Z",
  "updated_at": "2026-06-25T00:00:00Z",
  "last_message_id": "msg-01jabc000001"
}
```

Message:

```json
{
  "id": "msg-01jabc000001",
  "conversation_id": "conv-01jabc000001",
  "from": {
    "kind": "external",
    "external_id": "ext-01jabc000001"
  },
  "to": [
    {
      "kind": "actor",
      "actor_address": {
        "role_id": "market",
        "actor_id": "act-market-607eca23170c"
      }
    }
  ],
  "content": "你好，收到后请回复 pong",
  "reply_to": null,
  "created_at": "2026-06-25T00:00:00Z"
}
```

Message state:

```json
{
  "message_id": "msg-01jabc000001",
  "participant": {
    "kind": "actor",
    "actor_address": {
      "role_id": "market",
      "actor_id": "act-market-607eca23170c"
    }
  },
  "disposition": "unseen",
  "reason": null,
  "processed_by": null,
  "updated_at": "2026-06-25T00:00:00Z"
}
```

Event:

```json
{
  "event_id": "imev-01jabc000001",
  "type": "message.created",
  "participant": {
    "kind": "actor",
    "actor_address": {
      "role_id": "market",
      "actor_id": "act-market-607eca23170c"
    }
  },
  "message_id": "msg-01jabc000001",
  "conversation_id": "conv-01jabc000001",
  "created_at": "2026-06-25T00:00:00Z"
}
```

For direct messages, Central IM creates participant-visible events for every participant that needs to observe the change.

### Phase 1: Read Events

Request:

```http
GET /api/im/events?cursor=imev-000000000000&limit=50&wait_ms=25000
Authorization: Bearer impt_01jabc_secret
```

Response:

```json
{
  "ok": true,
  "events": [
    {
      "event_id": "imev-01jabc000002",
      "type": "message.created",
      "message_id": "msg-01jabc000002",
      "conversation_id": "conv-01jabc000001",
      "from": {
        "kind": "actor",
        "actor_address": {
          "role_id": "market",
          "actor_id": "act-market-607eca23170c"
        }
      },
      "to": [
        {
          "kind": "external",
          "external_id": "ext-01jabc000001"
        }
      ],
      "reply_to": "msg-01jabc000001",
      "created_at": "2026-06-25T00:00:05Z"
    }
  ],
  "next_cursor": "imev-01jabc000002"
}
```

Rules:

- events are scoped by authenticated participant;
- event bodies contain routing metadata and ids;
- message content is read through `GET /api/im/messages/{message_id}`;
- repeated calls with the same cursor are stable.

### Phase 1: Read Message and Replies

```http
GET /api/im/messages/msg-01jabc000002
Authorization: Bearer impt_01jabc_secret
```

```json
{
  "ok": true,
  "message": {
    "id": "msg-01jabc000002",
    "conversation_id": "conv-01jabc000001",
    "from": {
      "kind": "actor",
      "actor_address": {
        "role_id": "market",
        "actor_id": "act-market-607eca23170c"
      }
    },
    "to": [
      {
        "kind": "external",
        "external_id": "ext-01jabc000001"
      }
    ],
    "content": "pong",
    "reply_to": "msg-01jabc000001",
    "created_at": "2026-06-25T00:00:05Z"
  }
}
```

```http
GET /api/im/messages/msg-01jabc000001/replies
Authorization: Bearer impt_01jabc_secret
```

```json
{
  "ok": true,
  "message_id": "msg-01jabc000001",
  "replies": [
    {
      "id": "msg-01jabc000002",
      "conversation_id": "conv-01jabc000001",
      "reply_to": "msg-01jabc000001",
      "created_at": "2026-06-25T00:00:05Z"
    }
  ]
}
```

### Phase 1: Disposition

Request:

```http
PATCH /api/im/messages/msg-01jabc000002/disposition
Authorization: Bearer impt_01jabc_secret
Content-Type: application/json
```

```json
{
  "disposition": "absorbed",
  "reason": "reply consumed by local script"
}
```

Response:

```json
{
  "ok": true,
  "message_id": "msg-01jabc000002",
  "participant": {
    "kind": "external",
    "external_id": "ext-01jabc000001"
  },
  "disposition": "absorbed",
  "state_changed": true
}
```

Allowed dispositions:

```text
unseen
absorbed
replied
needs_parent
```

`needs_parent` is valid for actor processing. External participants should only use `absorbed` for Phase 1.

### Phase 2: Runtime Wake Contract

Wake request:

```json
{
  "type": "im.message.created",
  "wake_id": "imwake-01jabc000001",
  "target_actor_address": {
    "role_id": "market",
    "actor_id": "act-market-607eca23170c"
  },
  "message_id": "msg-01jabc000001",
  "conversation_id": "conv-01jabc000001",
  "event_id": "imev-01jabc000001",
  "created_at": "2026-06-25T00:00:00Z"
}
```

Wake result:

```json
{
  "wake_status": "submitted",
  "target_actor_address": {
    "role_id": "market",
    "actor_id": "act-market-607eca23170c"
  },
  "runtime_target": "parent",
  "runtime_call_id": "daemon-runtime-call-1",
  "error": null
}
```

Allowed `runtime_target` values:

```text
parent
side
none
```

Rules:

- wake request contains ids only;
- wake does not carry message content;
- wake does not create or mutate IM message state by itself;
- wake result is recorded for observability, not treated as message durability.

### Phase 3: Actor Tool Contract Mapping

Actor tools preserve names and route to Central IM:

| Tool action | Central IM operation |
| --- | --- |
| `message__contacts` | `GET /api/im/actors` |
| `message__send` | `POST /api/im/messages` |
| `message__get` | `GET /api/im/messages/{message_id}` |
| `message__list` | participant-scoped message/event query |
| `message__conversation` | `GET /api/im/conversations/direct?kind=actor&role_id=market&actor_id=act-market-607eca23170c` |
| `message__mark` | `PATCH /api/im/messages/{message_id}/disposition` |

Actor caller identity:

```text
context.actor_address -> ActorParticipant
```

Forbidden in Phase 3:

```text
context.repos.message.create_message
context.repos.message.list_messages as conversation source
context.daemon.deliver_message_available
role_id=user
```

### Phase 4: Deletion Contract

The old path is considered deleted only when these runtime entry points are gone:

```text
POST /api/messages/send
WebUserActorRuntime
send_from_web_user
deliver_message_available as IM send path
message.available as IM delivery contract
EXTERNAL_MESSAGE_ROLE_IDS = {"user"}
```

Final behavior:

```text
POST /api/messages/send -> 404
POST /api/im/messages  -> active IM send path
```

## Design Decision 5: Runtime Wake Preserves Side/Parent and innerTUI

The actor processing model is preserved. The data source and trigger contract are replaced.

Current path:

```text
message.available
  -> message_available_handler
  -> parent idle: submit parent prompt
  -> parent running: submit side triage
  -> actor uses message__get / message__conversation
```

Target path:

```text
Central IM message accepted
  -> IM runtime wake request
  -> actor daemon-service checks parent activity
  -> parent idle: submit parent handling workflow
  -> parent running: submit side triage workflow
  -> actor uses message__get / message__conversation
  -> tools read IM product store
```

Runtime wake request contains ids only:

```json
{
  "type": "im.message.created",
  "wake_id": "imwake-01jabc000001",
  "target_actor_address": {
    "role_id": "market",
    "actor_id": "act-market-607eca23170c"
  },
  "message_id": "msg-01jabc000001",
  "conversation_id": "conv-01jabc000001",
  "event_id": "imev-01jabc000001",
  "created_at": "2026-06-25T00:00:00Z"
}
```

Rules:

- no message body in wake payload;
- no `from` message content in wake payload;
- no disposition mutation in the instance daemon before actor action;
- actor reads through `message__get` / `message__conversation`;
- actor replies through `message__send(reply_to=original_message_id)`;
- actor marks through `message__mark`.

Preserved:

- parent idle handling;
- running parent side triage;
- `needs_parent`;
- app-server thread execution;
- innerTUI as human-facing runtime client surface.

Removed/replaced:

- `message.available` as IM delivery contract;
- `deliver_message_available`;
- `message_inbound` default IM registration;
- `message_available_handler` old event/payload semantics.

## Design Decision 6: Fake User Actor Must Be Deleted, Not Wrapped

The fake user actor path is not a compatibility layer. It is the old design to remove.

Delete:

```text
tools/launcher/web_user_actor.py
tests/test_web_user_actor.py
send_from_web_user
WebUserActorRuntime startup in web_management.py
act-user-local central actor registry semantics
/api/messages/send public route
```

Do not replace it with:

```text
external-user actor
web actor
user role in ActorAddress
mailbox sink for external users
adapter that still calls send_from_actor with role_id=user
```

Replacement:

```text
POST /api/im/external-participants
POST /api/im/messages
GET  /api/im/events
```

This gives user/external access without actor registry, daemon runtime, fake mailbox, or fake role.

## Surrounding Surface Impact

Not every message-adjacent surface is preserved unchanged. The split is:

| Surface | Target treatment |
| --- | --- |
| `message__send/get/list/conversation/mark/contacts` names | Preserve names, migrate implementation to Central IM |
| actor parent/side handling | Preserve behavior, replace trigger/data source |
| app-server thread execution | Preserve |
| innerTUI runtime client surface | Preserve |
| Track/Task/Artifact/Comment | Preserve outside IM |
| `track.comment.added` | Preserve as non-IM lightweight notification |
| WebManagement instance lifecycle APIs | Preserve |
| WebManagement message send route | Replace `/api/messages/send` with `/api/im/*` |
| Web UI message feature | Migrate to external participant + event polling |
| fake `web_user_actor` | Delete |
| old message repo direct access from tools | Delete from main path |
| daemon mailbox | Keep only for non-IM/local runtime triggers |
| `message.available` | Delete from IM main path |

So the claim is not “all message-driven surrounding applications are untouched.”

The correct claim is:

```text
actor runtime experience and non-IM collaboration systems are preserved;
old message business entry points and fake user actor infrastructure are migrated or deleted.
```

## Maintainability Shape

The rebuilt IM system is maintainable only if responsibilities settle like this:

```text
IM product core
  scripts/env/services/messages.py
  scripts/env/domain/messages.py
  scripts/env/repos/messages.py
  owns participant/conversation/message/state/event/cursor model
  owns send/read/reply/events/disposition rules
  owns physical JSON normalization and durable writes

HTTP projection
  tools/launcher/im_http_router.py
  owns request parsing, auth extraction, response shaping
  calls IM product core

Actor tools
  scripts/env/tools/message/*
  owns actor-facing tool definition and response shape
  calls im_client as projection, not repo/signal

Actor runtime wake
  IM wake handler/adapter
  owns parent/side runtime handoff
  reads ids and asks actor tools to fetch IM product state

Non-IM collaboration
  track/task/artifact/comment modules
  remain separate product systems
```

Forbidden maintainability failures:

- WebManagement writes IM store directly.
- actor tool writes IM store directly.
- `tools/launcher` owns IM participant/message/conversation/cursor semantics.
- `central_im_service.py` becomes a product core in launcher instead of a thin host adapter.
- central daemon uses `signal.deliver` as message delivery business path.
- external participant becomes an actor registry row.
- mailbox becomes durable message storage.
- `message.available` remains a required IM send assertion.
- Track comments are inserted into IM events.
- an adapter preserves both `/api/messages/send` and `/api/im/messages` as active send paths.

## Implementation Gate Tests

Before code implementation is considered aligned, tests must enforce:

1. `POST /api/im/external-participants` returns `external_id`, token, and cursor.
2. external participant does not appear in `daemon.registry`.
3. `POST /api/im/messages` persists message, message state, and participant-visible event.
4. send response separates `delivery_status=accepted` from `wake_status`.
5. wake failure does not delete durable message.
6. `message__send` calls Central IM client.
7. `message__send` does not call `context.repos.message.create_message`.
8. `message__send` does not call `deliver_message_available`.
9. actor wake payload contains ids only.
10. idle parent handling still routes to parent.
11. running parent still routes to side triage.
12. `track.comment.added` tests remain green.
13. `/api/messages/send` route returns 404.
14. `WebUserActorRuntime` is not started by `web_management.py`.
15. `role_id=user` is rejected as actor participant.
16. `scripts/env/tools/message/tool.py` describes IM participants/conversations/messages/events, not direct actor-address inbox rows.
17. `scripts/env/tools/message/_impl.py` does not use `context.repos.message` for IM truth reads or writes.
18. `tools/launcher/im_http_router.py` calls the IM product service and does not import the IM repo directly.
19. `tools/launcher/central_daemon_core.py` does not import the IM repo for store writes.
20. any launcher `central_im_*` file is a host adapter only and contains no participant/message/conversation store ownership.

Required cleanup searches:

```bash
rg "act-user-local|web-user|send_from_web_user|WebUserActorRuntime|deliver_message_available|/api/messages/send" tools scripts tests
rg "message.available" tools scripts tests
```

Allowed final `message.available` hits: none in IM main path. If daemon/mailbox generic tests still use the string during migration, they must be rewritten or isolated before final completion.

## Review Result

This design passes the current review questions if the next implementation plan keeps these invariants:

- user/external and actor are one IM participant system, but different address types;
- external registration issues IM identity, not actor identity;
- message truth is physical and central under `state/im/*`;
- IM product core under `scripts/env` owns store writes and message rules;
- central daemon-service owns host control-plane and wake orchestration only;
- instance daemon-service handles runtime attention only;
- side/parent and innerTUI-driven actor handling are preserved;
- fake user actor is deleted with no compatibility wrapper;
- surrounding non-IM collaboration systems stay outside IM;
- actor-to-actor and external-to-actor share the same Central IM business contract;
- old message repo/signal path is not kept beside the new path.

The remaining work after this memo is an implementation plan with exact test order and file edits. The current code still contains the old path.
