# HTTP Message Send Public Service Test Plan

Source: `docs/memo/2026-06-24-http-message-send-public-service.md`

## Goal

Prove that direct-message send semantics live behind a public message service, while web/browser send is a strict HTTP adapter over that service.

The user-facing outcome is:

- web UI and local HTTP clients send `POST /api/messages/send`;
- the only accepted HTTP request body is `{"actor_id": "...", "content": "..."}`;
- the sender is always `{"role_id": "user", "actor_id": "act-user-local"}`;
- the target actor receives a normal durable `message.available` direct message;
- actor-to-actor `message.send` and web-user sends share one service path;
- the old `/api/instances/<actor_id>/messages` live send route is removed.

## Resource Lifecycle Guard

This plan follows `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

Default test style is unit-level with fake daemon reachability and delivery. Tests must not start central daemons, instance daemons, app-server, runtime broker servers, browser helpers, or persistent subprocesses unless the test owns registration, teardown, pid or socket cleanup, and post-run residue checks.

The only acceptable service-style test in this slice is the existing web-user mailbox socket compatibility test, which uses `TemporaryDirectory`, closes the server, joins the thread, and asserts the socket is removed. Do not broaden service-starting verification until that lifecycle proof remains intact.

## Functional Coverage

### 1. Public Message Service

File: `tests/test_message_service.py`

Cover the service as the shared capability layer:

- `send_from_actor` creates one durable message row with normalized content, source actor, target actor, and optional `reply_to`;
- reachability is checked before message creation;
- `message.available` delivery is invoked after creation;
- delivery failure deletes the created row and returns a structured rejection;
- cleanup failure returns indeterminate durable state with the created `message_id`;
- reply sends update the original inbound message disposition to `replied`;
- active manifest role enforcement is enabled for actor sends and disabled for web-user sends only when explicitly requested;
- response includes `message_id`, `delivery_status`, `handling_status`, `target_actor_address`, `state_changed`, and `durability`.

Negative cases:

- unknown fields are rejected before reachability and before message creation;
- empty content is rejected before reachability and before message creation;
- unknown target role is rejected by message domain rules;
- self-send is rejected;
- target not online creates no message row.

The tests use fake context objects or `ToolContext` plus monkey-patched daemon functions. They must not use the real central daemon.

### 2. Env Tool Adapter

File: `tests/test_message_env_tool.py`

Cover that `message.send` remains behavior-compatible while calling the public service:

- successful actor send still produces the same durable message and structured tool response shape;
- payload validation still rejects unsupported fields and empty content;
- reachability rejection still creates no message;
- delivery failure cleanup still removes the created message;
- reply to the external web-user participant still works;
- conversation/list/get/mark behavior remains in the tool layer and is not moved into the service.

Boundary assertions:

- `scripts/env/tools/message/_impl.py` imports `env.services.messages`;
- production callers outside `scripts/env/tools/message/_impl.py` and tests do not import `env.tools.message._impl` for send capability.

### 3. Web-User Actor Adapter

File: `tests/test_web_user_actor.py`

Cover that the web-user adapter owns only identity and sink behavior:

- `send_web_user_message` sends as `WEB_USER_ACTOR_ADDRESS`;
- it calls the public message service, not `env.tools.message._impl`;
- it keeps shared runtime state-root behavior from the source web process;
- target-not-online and delivery-failure responses mirror service rejections;
- actor replies to `act-user-local` are acknowledged by the mailbox-compatible sink;
- the sink server starts and closes with no lingering thread or socket.

### 4. HTTP API

File: `tests/test_web_management.py`

Cover the new direct HTTP route:

- `POST /api/messages/send` rejects empty content before instance status lookup;
- it rejects unknown fields such as `role_id`, `from_actor_address`, `reply_to`, `text`, metadata, priority, attachments, session fields, and client request ids;
- it rejects missing or invalid `actor_id`;
- it resolves `actor_id` to `{"role_id": instance.role, "actor_id": instance.actor_id}`;
- it calls the injected web message sender with exactly `target_actor_address` and trimmed `content`;
- success response includes `ok`, `message_id`, `from_actor_address`, `target_actor_address`, `delivery_status`, `handling_status`, `state_changed`, and `durability`;
- known adapter rejection maps to `409`;
- actor-id resolution failure maps to `404`;
- malformed runtime dependency result maps to `502`;
- the old `POST /api/instances/<actor_id>/messages` route returns 404 and does not call status lookup or the sender.

Boundary assertions:

- `web_management.py` must not import message repos;
- `web_management.py` must not call `create_message`, `save_message`, or `delete_message`;
- `web_management.py` must not construct `message.available` signals or call `daemon_client.deliver_signal`.

### 5. Web UI Assets

Files:

- `tests/web_management_ui_contract.test.js`
- `tests/web_management_ui_state.test.js`

Cover browser-facing behavior without starting a browser:

- `app.js` posts to `/api/messages/send`;
- request payload contains only `actor_id` and `content`;
- UI copy describes direct-message delivery, not thread steering or instruction injection;
- old `/api/instances/<actor_id>/messages` is absent from live UI assets;
- send enablement and feedback rendering still work from DOM-level contract tests.

### 6. Daemon Boundary Protection

Files:

- `tests/test_daemon_communication_boundary.py`
- `tests/test_daemon_mailbox.py`

Cover that daemon infrastructure remains generic:

- no web-user business strings appear in `daemon_core.py`, `daemon_mailbox.py`, `daemon_triggers.py`, `central_daemon_core.py`, or `scripts/env/tool_runtime/daemon_client.py`;
- daemon mailbox still carries generic `message.available` signals;
- no special `web_message`, `message_available_for_user`, or web-user branch is introduced.

## Focused Verification Commands

Run in this order:

```bash
python -m pytest tests/test_message_service.py -q
python -m pytest tests/test_message_env_tool.py -q
python -m pytest tests/test_web_user_actor.py -q
python -m pytest tests/test_web_management.py -q
node --test tests/web_management_ui_contract.test.js
node --test tests/web_management_ui_state.test.js
python -m pytest tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py -q
```

After the socket-owning web-user tests, check for residue:

```bash
pgrep -fl "web-user-mailbox|web-user-runtime|DaemonMailboxServer" || true
```

Expected: no leftover BuddySwitch web-user mailbox process. The tests should use threads in-process, so a matching persistent process indicates a leak.

## Boundary And Residue Scans

```bash
rg "act-user-local|web_user|web-user|send_web_message|role_id.*user" tools/launcher/daemon_core.py tools/launcher/daemon_mailbox.py tools/launcher/daemon_triggers.py tools/launcher/central_daemon_core.py scripts/env/tool_runtime/daemon_client.py
rg "env\\.repos\\.messages|create_message|save_message|delete_message|message\\.available|signal_id|daemon_client\\.deliver_signal" tools/launcher/web_management.py
rg "/api/instances/.*/messages|/messages'|/messages\"" tools/launcher/assets/web-management tools/launcher/web_management.py README.md
rg "from env\\.tools\\.message import _impl|message_impl\\.send_message_from_actor" tools scripts tests
```

Expected:

- first scan returns no daemon infrastructure web-user business strings;
- second scan returns no direct message storage or signal construction in `web_management.py`;
- third scan returns no live old send route and no UI `/messages` shorthand send route;
- fourth scan returns no production import of message tool `_impl` as the public send capability.

## Broader Verification

After focused tests pass, run the smallest broader suite that covers touched surfaces without starting broad persistent runtime paths:

```bash
python -m pytest tests/test_message_env_tool.py tests/test_web_user_actor.py tests/test_web_management.py tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Do not run the full launcher suite until the focused commands and residue checks are clean.

## Review Checklist

- Tests are derived from the memo behavior, not from current private implementation details.
- New service tests fail against the current code because `scripts/env/services/messages.py` does not exist.
- New HTTP tests fail against the current code because `/api/messages/send` does not exist and old route still exists.
- No test starts a persistent service without cleanup proof.
- All old-route tests are rewritten as removal tests, not compatibility tests.
- Boundary scans are part of acceptance, not optional cleanup.
