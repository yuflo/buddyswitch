# Web User Actor Message Network

Date: 2026-06-23
Status: task memo for implementation

## Summary

This memo defines the first web-interface message task.

The goal is to let the local BuddySwitch web interface send durable direct messages to runtime
actors by participating in the existing actor message network as one special external actor:

```text
{"role_id": "user", "actor_id": "act-user-local"}
```

This is not a replacement for the daemon communication architecture. It is a thin web ingress over
the already available message, central-daemon, signal, mailbox, and instance-daemon capabilities.

The implementation must keep infrastructure modules generic. The daemon layer must not learn web,
user, UI, or message business semantics.

## Decision

Use the existing actor-message model for web-to-actor messages.

The web interface sends messages as:

```text
from_actor_address = {"role_id": "user", "actor_id": "act-user-local"}
to_actor_address   = target runtime actor address
```

The target actor receives the existing `message.available` event. Its instance daemon handles the
event through the existing message inbound path and decides parent vs side handling.

The first implementation does not need a web conversation UI or reply inbox UI. It should still keep
`act-user-local` reachable through a minimal sink endpoint so actor replies do not fail at delivery
time. The sink may acknowledge incoming `message.available` and leave durable reply reading for a
later task.

## Current Capabilities

The needed foundation already exists:

- durable message rows with `from_actor_address`, `to_actor_address`, content, reply metadata, and
  disposition;
- central daemon actor registry, reachability checks, heartbeat, and `signal.deliver`;
- generic daemon mailbox delivery through `DaemonSignalEnvelope`;
- `message.available` inbound registration;
- `MessageAvailableHandler`, which routes message attention to parent or side work;
- web-management HTTP API shell for local browser interaction.

The missing work is the web-user actor adapter and the web API route that uses it.

## Bitter Compliance Check

This design is compatible with `docs/bitter` only if the boundaries below are enforced.

### Tool, Skill, And Prompt Layering

Do not solve this with prompt instructions or AGENTS text. The behavior belongs in runtime
contracts:

- message creation and delivery must have structured responses that report state changes,
  message id, delivery status, and handling status;
- actor reply failures must be surfaced as runtime delivery failures, not hidden by prompt wording;
- web UI affordances should consume runtime response fields instead of inferring success from
  `ok=true`.

### Parallel Change Boundary

Do not route this through broad shared files as the default.

The owning slice is web-user message ingress. Routine implementation should stay around:

```text
tools/launcher/web_user_actor.py
tools/launcher/web_management.py
scripts/env/domain/messages.py
tests/test_web_user_actor.py
tests/test_web_management.py
tests/test_message_env_tool.py
```

Touch daemon or central-daemon files only if a generic infrastructure contract is missing. Do not add
web-user cases to daemon routers.

### Wrong-Boundary Narrowness

The tempting wrong change is adding a narrow method such as:

```text
central_daemon.send_web_message
daemon_mailbox.web_message
message_available_for_user
```

Do not do that. It would be small at the wrong boundary.

The correct shape is:

```text
stable ingress
  -> generic signal.deliver / mailbox.deliver
  -> message-owned handler
  -> explicit message action
```

Business variation belongs behind the message/web-user module, not inside the daemon protocol.

### Residue Cleanup

This is a semantic shift for the web input surface.

After implementation, live surfaces should not continue teaching that web-to-actor work is only
thread input or steering. Scoped scans should check only live surfaces such as:

```text
tools/launcher/assets/web-management
tools/launcher/web_management.py
README.md
relevant tests
```

Historical memos do not need cleanup.

### Test Resource Lifecycle

If tests start web servers, central daemon processes, instance daemons, app-server, runtime broker,
or browser helpers, they must own cleanup before broad verification.

Prefer unit-level tests with fake central-daemon clients and mailbox sinks first. Only add
service-starting integration tests when they register pids, clean sockets, stop process groups, and
check for residue.

## Architecture Review Addendum

Review result: this design is compatible with `docs/bitter` if the implementation keeps the gates
below. The boundary is clean because web ingress, message business semantics, durable storage, and
daemon delivery each have a separate owner.

Ownership summary:

- web ingress belongs to `web_user_actor` plus `web_management`;
- message validation, reply scope, disposition, delivery cleanup semantics, and structured message
  results belong to the message module;
- durable message rows belong to the message repo only;
- daemon and central daemon remain generic actor registry, reachability, signal, and mailbox
  infrastructure.

**Hard implementation gates. Treat any violation as a blocker:**

- **Do not add web, user, or message business branches to daemon or central-daemon modules.**
  `central_daemon.send_web_message`, `daemon_mailbox.web_message`, `web_user_endpoint`, and similar
  special-case entrypoints are wrong-boundary changes.
- **Do not reimplement a partial `message.send` chain inside `web_user_actor`.** The web-user adapter
  must reuse or factor message-owned send semantics for scope validation, reachability check, durable
  row creation, `message.available` delivery, failed-delivery cleanup, and structured success/rejection
  results.
- **Keep the `act-user-local` reply sink mailbox-compatible.** Current delivery infrastructure routes
  generic signals to mailbox sockets. If the sink needs an endpoint, prefer a minimal
  `daemon_mailbox_socket`-compatible sink over extending central daemon delivery rules.
- **Keep `web_management.py` as an HTTP adapter only.** Direct imports of message repos, direct
  `create_message`/`save_message` calls, inline signal construction, or disposition policy in
  `web_management.py` should fail review.
- **Keep `user` as an external message participant, not a launchable runtime role.** The change belongs
  in message scope rules, not in manifest role discovery or launcher role startup behavior.

The review evidence to preserve during implementation is:

- boundary tests proving daemon communication stays generic;
- residue scans proving daemon and central-daemon files contain no web-user business strings;
- scans proving `web_management.py` does not directly write message rows.

## Module Ownership

### `tools/launcher/web_user_actor.py`

Owns the web-user actor adapter.

Responsibilities:

- define `WEB_USER_ACTOR_ADDRESS = {"role_id": "user", "actor_id": "act-user-local"}`;
- register and unregister the web-user actor with the central daemon;
- expose a send helper that uses message-owned send semantics to create a durable message from
  web-user to a target actor;
- deliver `message.available` to the target actor through the existing central daemon signal path,
  including the same failed-delivery cleanup behavior as normal message sends;
- expose a minimal sink endpoint for incoming `message.available` replies;
- return structured delivery results to callers.

It should not:

- directly duplicate message scope, reachability, delivery cleanup, or reply disposition rules;
- submit or steer Codex turns;
- inspect app-server threads;
- own parent/side routing;
- mutate daemon state directly;
- import web-management UI code.

### `tools/launcher/web_management.py`

Owns HTTP adaptation only.

Responsibilities:

- parse and validate HTTP request bodies;
- validate target actor ids;
- call `web_user_actor` helpers;
- return message id, delivery status, handling status, and instance status where useful.

It should not:

- directly write message JSON files;
- construct daemon signals inline when a helper exists;
- interpret message disposition policy;
- contain daemon handler logic;
- become the owner of `act-user-local` lifecycle beyond invoking the adapter.

### `scripts/env/domain/messages.py`

Owns message scope rules.

Required adjustment:

- allow the external `user` role as a valid direct-message participant without making it a
  manifest-declared launchable role.

It should not:

- add UI-read fields;
- add web-only disposition values;
- treat web messages as a separate message object shape.

### `scripts/env/repos/messages.py`

Owns durable message rows.

Keep the existing generic actor-address shape. A web-user message is still a normal direct message
with an actor-address sender.

Do not add:

```text
web_status
ui_seen
read_at
session_id
broadcast
recipients
```

Those belong in a later UI inbox surface if needed, not in the first message-network task.

### Daemon And Central Daemon Modules

Remain infrastructure only.

Do not add user/web/message business branches to:

```text
tools/launcher/daemon_core.py
tools/launcher/daemon_mailbox.py
tools/launcher/daemon_triggers.py
tools/launcher/central_daemon_core.py
scripts/env/tool_runtime/daemon_client.py
```

These modules may continue to validate and route generic actor addresses, endpoint records, signals,
and mailbox requests.

## Target Flow

### Web sends to actor

```text
POST /api/instances/<actor_id>/messages
  -> web_management parses {"text": "..."}
  -> web_user_actor resolves target ActorAddress from instance status/registry
  -> message repo creates msg-...
  -> central daemon delivers signal:
       type = "message.available"
       payload = {"message_id": "msg-..."}
  -> target instance daemon handles message.available
  -> response reports message_id, delivery_status, handling_status
```

### Actor replies to web-user actor

```text
actor calls message__send(reply_to=msg-..., target_actor_address=act-user-local)
  -> message repo creates reply message
  -> central daemon delivers message.available to act-user-local sink
  -> sink acknowledges
```

The first task does not need to show these replies in the UI. The reply rows remain durable and can
be surfaced later.

## Out Of Scope

Do not implement:

- multi-user web sessions;
- remote user authentication;
- a web reply inbox UI;
- unread counters;
- read receipts;
- message deletion or editing;
- WebSocket or SSE streaming;
- per-actor HTTP servers;
- a new user-message object family;
- generic workflow, rule, or event engines.

Do not change:

- parent/side message prompt content unless tests expose a direct need;
- Track comment inbound behavior;
- task checkout behavior;
- app-server goal semantics;
- central daemon registry semantics except generic endpoint support if already needed.

## Implementation Notes

Use the shortest validated path:

1. Add web-user actor constants and adapter tests.
2. Prove the adapter reuses or factors message-owned send semantics instead of duplicating a partial
   create-and-deliver flow.
3. Prove the adapter can create a normal message row from `act-user-local` to a target actor.
4. Prove it calls the existing `signal.deliver` path with a generic `message.available` signal and
   cleans up the durable row on delivery failure in the same way normal message sends do.
5. Prove message scope accepts `user` as an external participant but `user` is not a launchable role.
6. Add a minimal sink endpoint so actor replies to `act-user-local` can be delivered without UI
   support.
7. Add a web route that calls the adapter and returns structured message delivery output.
8. Add scoped residue checks so live web surfaces no longer teach direct thread input as the only
   web-to-actor path.

If a new endpoint kind is required for the web-user sink, keep it generic. Prefer a mailbox-compatible
endpoint before extending central daemon delivery rules.

## Verification

Focused tests:

```bash
python -m pytest tests/test_web_user_actor.py -q
python -m pytest tests/test_web_management.py -q
python -m pytest tests/test_message_env_tool.py -q
python -m pytest tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py -q
```

Boundary scans:

```bash
rg "act-user-local|web_user|web-user|role_id.*user" tools/launcher/daemon_core.py tools/launcher/daemon_mailbox.py tools/launcher/daemon_triggers.py tools/launcher/central_daemon_core.py scripts/env/tool_runtime/daemon_client.py
rg "env\\.repos\\.messages|create_message|save_message" tools/launcher/web_management.py
```

Expected scan results:

- no web-user business strings in daemon or central-daemon infrastructure files;
- no direct message repo writes in `web_management.py`.

If service-starting tests are added, also verify process and socket cleanup before broad test runs.

## Definition Of Done

The task is done only when:

- the web interface can send a durable actor-address message as `act-user-local`;
- the target actor daemon receives the normal `message.available` event;
- actor replies to `act-user-local` do not fail only because the web-user actor is unreachable;
- the web UI is not required to display replies in this task;
- `user` is accepted as an external message participant but not a launchable runtime role;
- daemon and central-daemon modules remain generic and pass boundary tests;
- focused tests and scoped residue scans pass.
