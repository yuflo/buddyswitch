# HTTP Message Send Public Service

Date: 2026-06-24
Status: final task memo for implementation

## Summary

**Core task:** converge actor message send into a public message service module, then expose the
web-user send capability through one direct HTTP API.

The web/browser user sends messages as the fixed local web-user actor:

```text
{"role_id": "user", "actor_id": "act-user-local"}
```

The target actor receives a normal durable direct message and is notified through the existing
`message.available` daemon path.

**Important:** HTTP is the user/web transport boundary. It is not the internal capability layer.
The internal capability layer is the public message service.

## Final Architecture

```text
Web UI / local HTTP client
  -> POST /api/messages/send
  -> web-management HTTP adapter
  -> web-user actor adapter
  -> public message service
  -> message domain rules
  -> message repo
  -> daemon generic signal delivery
  -> target actor daemon
  -> target actor
```

Actor-originated sends use the same service without HTTP:

```text
Actor env tool: message.send
  -> public message service
  -> message domain rules
  -> message repo
  -> daemon generic signal delivery
  -> target actor daemon
```

**Boundary rule:** web/user entry and actor/tool entry are different adapters over the same public
message service. They must not duplicate send logic.

## Current State

Current implementation is close, but not fully converged:

- `message.send` and `web_user_actor.send_web_user_message` reuse shared send behavior;
- that shared behavior currently lives in `scripts/env/tools/message/_impl.py` as
  `send_message_from_actor`;
- `web_user_actor.py` imports private `_impl.py`, which is not a clean public boundary;
- the web UI currently calls `POST /api/instances/<actor_id>/messages`;
- the desired direct HTTP send API does not yet exist as the single web send entry.

## Decisions

### Public Message Service Is The Capability Layer

Create a public service module for message send:

```text
scripts/env/services/messages.py
```

It owns the reusable send capability currently represented by `send_message_from_actor`.

The service should expose a small public contract, such as:

```text
send_from_actor(...)
send_from_web_user(...)
```

Exact names may follow local style, but callers should not import `env.tools.message._impl` for send
capability.

### HTTP Send Is The User/Web Transport API

Add one direct HTTP API:

```http
POST /api/messages/send
Content-Type: application/json
```

Request body:

```json
{
  "actor_id": "act-dev-demo",
  "content": "Please check this."
}
```

Request rules:

- **only** `actor_id` and `content` are accepted;
- `actor_id` is required and must be a valid actor id;
- `content` is required and must be non-empty after trimming;
- `role_id` is not accepted;
- `from_actor_address` is not accepted;
- `reply_to` is not accepted in v1;
- metadata, priority, attachments, session fields, and client request ids are not accepted in v1.

The server resolves `actor_id` to the target actor address:

```text
{"role_id": resolved_role, "actor_id": actor_id}
```

The sender is always:

```text
{"role_id": "user", "actor_id": "act-user-local"}
```

### Send Is Asynchronous

The HTTP response reports message creation and delivery acceptance, not an actor reply.

The send request means:

```text
create durable message row
  -> deliver message.available
  -> return delivery_status and handling_status
```

It does not wait for target actor business completion or reply content.

Reply collection, inbox reads, polling, SSE, or WebSocket events are separate future tasks.

### Remove The Old Web Send Route

Because this is forward development and there is no external compatibility contract, do not preserve
the old route as a wrapper:

```http
OLD ROUTE TO REMOVE: POST /api/instances/<actor_id>/messages
```

**Delete this route or make it return not found.**

The web UI should call:

```http
POST /api/messages/send
```

This avoids maintaining two HTTP send surfaces and satisfies residue cleanup.

## HTTP Contract

### Success Response

Return `200` when the durable message was created and target daemon delivery accepted it.

```json
{
  "ok": true,
  "message_id": "msg-...",
  "from_actor_address": {
    "role_id": "user",
    "actor_id": "act-user-local"
  },
  "target_actor_address": {
    "role_id": "dev",
    "actor_id": "act-dev-demo"
  },
  "delivery_status": "delivered",
  "handling_status": "handled",
  "state_changed": true,
  "durability": "durable"
}
```

The response may include current instance status if already available, but callers must not need it
to understand send success.

### Error Response

Use structured runtime feedback. Do not return only `ok=false`.

```json
{
  "ok": false,
  "error": {
    "code": "E_MESSAGE_TARGET_NOT_ONLINE",
    "message": "target actor is not online"
  },
  "target_actor_address": {
    "role_id": "dev",
    "actor_id": "act-dev-demo"
  },
  "state_changed": false,
  "delivery_status": "target_not_online"
}
```

Status mapping:

- `400`: invalid payload, unknown fields, invalid actor id, empty content;
- `404`: actor id cannot be resolved to a current runtime actor;
- `409`: target actor is known but not online, scope blocked, or delivery failed cleanly;
- `502`: delivery state is indeterminate, cleanup failed, or a required runtime dependency failed.

## Module Ownership

### `scripts/env/services/messages.py`

Owns public message service behavior.

Responsibilities:

- validate send request through message domain rules;
- check target reachability;
- create durable message rows;
- deliver `message.available`;
- clean up the created message row when delivery fails cleanly;
- update reply disposition when reply support is used by actor tools;
- return structured success/rejection results.

It should not:

- parse HTTP;
- know web UI concepts;
- start or manage daemon processes;
- own message row storage directly instead of using the repo;
- include daemon transport special cases.

### `scripts/env/tools/message/_impl.py`

Owns env.tool adaptation only.

Responsibilities:

- adapt `message.send` tool payloads to the public message service;
- preserve existing tool response shape and permission feedback;
- keep contacts/list/get/mark/conversation tool behavior in the tool layer.

It should not:

- be imported by web-user or HTTP modules as the public send capability;
- be the only home of shared message send semantics.

### `tools/launcher/web_user_actor.py`

Owns the web-user actor identity adapter.

Responsibilities:

- define `WEB_USER_ACTOR_ADDRESS`;
- create the web-user service context;
- call the public message service as `act-user-local`;
- register and unregister the web-user reply sink;
- expose a mailbox-compatible sink that acknowledges incoming `message.available` replies.

It should not:

- duplicate message send semantics;
- import `env.tools.message._impl` as a service boundary;
- submit or steer Codex turns;
- own parent/side routing;
- mutate daemon state directly beyond generic register/unregister calls.

### `tools/launcher/web_management.py`

Owns HTTP adaptation.

Responsibilities:

- parse and validate `/api/messages/send`;
- resolve `actor_id` to a target actor address;
- call the web-user actor adapter or public service boundary;
- map structured message results to HTTP status and JSON response;
- remove the old `/api/instances/<actor_id>/messages` send route from live API behavior.

It should not:

- directly import message repos;
- call `create_message`, `save_message`, or `delete_message`;
- construct `message.available` signals inline;
- contain disposition, reply, reachability, or daemon delivery policy;
- become a business router for message semantics.

### `tools/launcher/assets/web-management`

Owns the web UI.

Responsibilities:

- call `POST /api/messages/send`;
- send only `actor_id` and `content`;
- treat the response as asynchronous delivery feedback, not an actor reply.

It should not:

- call the old `/api/instances/<actor_id>/messages` route;
- send `role_id`;
- send `from_actor_address`;
- infer success from `ok=true` alone when delivery fields are present.

### Daemon And Central Daemon Modules

Remain infrastructure only.

Do not add web, user, or message business branches to:

```text
tools/launcher/daemon_core.py
tools/launcher/daemon_mailbox.py
tools/launcher/daemon_triggers.py
tools/launcher/central_daemon_core.py
scripts/env/tool_runtime/daemon_client.py
```

They may validate and route generic actor addresses, endpoint records, signals, and mailbox requests.

## Target Flows

### Web UI Sends To Actor

```text
Web UI submit
  -> POST /api/messages/send {"actor_id": "act-dev-demo", "content": "..."}
  -> web_management validates HTTP payload
  -> web_management resolves actor_id to {"role_id": "dev", "actor_id": "act-dev-demo"}
  -> web_user_actor sends as {"role_id": "user", "actor_id": "act-user-local"}
  -> public message service creates msg-...
  -> public message service delivers message.available through daemon signal delivery
  -> target daemon handles message.available
  -> HTTP response reports message_id, delivery_status, handling_status
```

### Actor Sends To Actor

```text
actor calls message.send
  -> message tool adapter validates tool payload shape
  -> public message service sends as active actor
  -> same durable message and daemon delivery path
```

### Actor Replies To Web User

```text
actor calls message.send reply_to=msg-...
  -> public message service creates reply message to act-user-local
  -> daemon delivers message.available to web-user mailbox-compatible sink
  -> sink acknowledges
```

The first task still does not display replies in the web UI.

## Bitter Compliance Check

This design complies with `docs/bitter` if the implementation keeps the boundaries above.

### Tool, Skill, And Prompt Layering

The behavior belongs in public runtime service contracts and structured responses. Do not solve
unclear send semantics with AGENTS text or prompt wording.

The response must report:

- whether state changed;
- message id;
- delivery status;
- handling status;
- durability;
- failure reason;
- cleanup state when delivery fails.

### Parallel Change Boundary

The owning slice is message send plus web-user HTTP ingress.

Routine implementation should stay around:

```text
scripts/env/services/messages.py
scripts/env/tools/message/_impl.py
tools/launcher/web_user_actor.py
tools/launcher/web_management.py
tools/launcher/assets/web-management/app.js
tests/test_message_service.py
tests/test_message_env_tool.py
tests/test_web_user_actor.py
tests/test_web_management.py
tests/web_management_ui_contract.test.js
```

Touch daemon or central-daemon files only if a generic infrastructure contract is missing.

### Wrong-Boundary Narrowness

**Forbidden wrong-boundary changes:**

```text
central_daemon.send_web_message
daemon_mailbox.web_message
message_available_for_user
web_management.create_message
web_management.deliver_signal
```

Concrete first does not mean special-case at the shared infrastructure boundary.

### Residue Cleanup

This is a semantic replacement for web send.

Live surfaces must stop teaching or using:

```text
OLD LIVE SURFACE TO REMOVE: /api/instances/<actor_id>/messages
body {"text": "..."}
```

They should teach or use:

```text
/api/messages/send
body {"actor_id": "...", "content": "..."}
```

Historical memos do not need cleanup, but live code, UI assets, README references, and tests do.

### Test Resource Lifecycle

Prefer unit-level tests with fake reachability and delivery clients.

If tests start web servers, central daemons, instance daemons, app-server, runtime broker, or browser
helpers, they must own process registration, teardown, socket cleanup, and post-run residue checks.

## Out Of Scope

Do not implement:

- reply inbox UI;
- message read/listen HTTP APIs;
- polling, SSE, or WebSocket events;
- multi-user web sessions;
- remote authentication;
- arbitrary HTTP sender impersonation;
- `role_id` in HTTP send request;
- `reply_to` in HTTP send v1;
- attachments, priority, metadata, session ids, or client request ids;
- per-actor HTTP servers;
- new user-message object family;
- generic workflow, rule, or event engines.

Do not change:

- parent/side message prompt content unless focused tests expose a direct need;
- Track comment inbound behavior;
- task checkout behavior;
- app-server goal semantics;
- central daemon registry semantics.

## Implementation Steps

Use the shortest validated path:

1. Add `scripts/env/services/messages.py` with the public send service extracted from current
   shared send behavior.
2. Update `message.send` env tool to call the public service.
3. Update `web_user_actor.send_web_user_message` to call the public service, not `_impl.py`.
4. Add `POST /api/messages/send` with request schema `actor_id + content`.
5. Update the web UI to call `/api/messages/send`.
6. Remove the old `/api/instances/<actor_id>/messages` live route behavior.
7. Keep the web-user sink mailbox-compatible so actor replies to `act-user-local` can be delivered.
8. Add focused tests for service behavior, HTTP schema, UI route usage, residue cleanup, and daemon
   boundary protection.

## Verification

Focused tests:

```bash
python -m pytest tests/test_message_service.py -q
python -m pytest tests/test_message_env_tool.py -q
python -m pytest tests/test_web_user_actor.py -q
python -m pytest tests/test_web_management.py -q
python -m pytest tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py -q
node --test tests/web_management_ui_contract.test.js
```

Boundary and residue scans:

```bash
rg "act-user-local|web_user|web-user|role_id.*user" tools/launcher/daemon_core.py tools/launcher/daemon_mailbox.py tools/launcher/daemon_triggers.py tools/launcher/central_daemon_core.py scripts/env/tool_runtime/daemon_client.py
rg "env\\.repos\\.messages|create_message|save_message|delete_message|message\\.available|signal_id|daemon_client\\.deliver_signal" tools/launcher/web_management.py
rg "/api/instances/.*/messages|/messages'|/messages\"" tools/launcher/assets/web-management tools/launcher/web_management.py tests README.md
rg "from env\\.tools\\.message import _impl|message_impl\\.send_message_from_actor" tools/launcher scripts tests
```

Expected scan results:

- no web-user business strings in daemon or central-daemon infrastructure files;
- no direct message repo writes or inline signal construction in `web_management.py`;
- no live web UI call to `/api/instances/<actor_id>/messages`;
- no production import of `env.tools.message._impl` as the public send capability.

## Definition Of Done

The task is done only when:

- public message service owns send semantics;
- `message.send` env tool uses the public service;
- web-user actor send uses the public service;
- `POST /api/messages/send` exists and accepts only `actor_id + content`;
- HTTP sender is always `act-user-local`;
- HTTP request does not accept `role_id`, `from_actor_address`, or `reply_to`;
- web UI sends through `/api/messages/send`;
- old `/api/instances/<actor_id>/messages` live route behavior is removed;
- target actor receives the normal `message.available` event;
- actor replies to `act-user-local` do not fail only because the web-user actor is unreachable;
- daemon and central-daemon modules remain generic;
- focused tests and scoped residue scans pass.
