# Web User Actor Message Network Test Plan

Date: 2026-06-23
Source: `docs/memo/2026-06-23-web-user-actor-message-network.md`
Status: Phase 3 completed and verified

## Goal

Prove the local web interface can send a durable direct message to a runtime actor as the external actor address `{"role_id":"user","actor_id":"act-user-local"}` while the daemon and central-daemon layers stay generic.

The tests must prove product behavior from requirements, not mirror a chosen implementation detail. The central behavior is one normal actor-address message flow:

```text
web HTTP request -> web-user adapter -> message-owned send semantics -> generic signal.deliver -> target mailbox message.available
```

## Resource Safety

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

Default validation is unit-level and fake-daemon based:

```bash
python -m pytest tests/test_web_user_actor.py -q
python -m pytest tests/test_web_management.py -q
python -m pytest tests/test_message_env_tool.py -q
python -m pytest tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py -q
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Do not start real instance daemons, app-server, runtime broker, browser helpers, or long-lived central daemons for the default loop. If a test uses a mailbox socket thread, it must use a temp directory, call `server.close()`, join the thread, and assert the thread stopped before broad verification.

## Phase 3 Verification Result

Completed on 2026-06-23 with the planned resource-safe loop. Passing evidence:

```bash
python -m pytest tests/test_web_user_actor.py tests/test_web_management.py tests/test_message_env_tool.py -q
python -m pytest tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py -q
python -m pytest tests/test_message_available_handler.py tests/test_central_daemon_service.py tests/test_daemon_core_decoupling.py -q
node tests/web_management_ui_contract.test.js && node tests/web_management_ui_state.test.js
git diff --check
```

Boundary scans found no web-user business strings in daemon infrastructure, no direct message writes or signal construction in `web_management.py`, no launchable manifest `user` role, no stale primary `/input` UI send path, and no matching BuddySwitch socket residue under `/tmp`.

## Functional Requirements To Prove

1. `act-user-local` is a valid external message participant with actor address `{"role_id":"user","actor_id":"act-user-local"}`.
2. `user` is not added as a launchable manifest role and cannot act as a normal env-tool active role.
3. Web-user sends create normal durable message rows with `from_actor_address`, `to_actor_address`, content, `reply_to`, and normal `unseen` disposition.
4. Web-user sends check target reachability before creating a message.
5. Web-user sends deliver only the generic `message.available` signal payload `{"message_id": ...}` through the existing central daemon signal path.
6. Delivery failure after message creation uses the same cleanup semantics as normal `message.send`.
7. Actor replies to `act-user-local` with `message.send(reply_to=...)` succeed when the web-user sink is reachable.
8. Actor `message.conversation` works with the external user participant so prompts that suggest conversation lookup are not broken.
9. The web-user reply sink is mailbox-compatible and acknowledges incoming `message.available` without requiring a reply inbox UI.
10. `POST /api/instances/<actor_id>/messages` validates text, resolves the target actor address from instance status, calls the adapter, and returns structured message/delivery/handling/instance fields.
11. The browser UI sends the existing selected-instance text box through `/messages`, not `/input`, and no visible copy teaches that the primary web-to-actor path is thread input or steering.
12. `web_management.py` remains an HTTP adapter: it must not import message repos, write message rows, or construct daemon signals inline.
13. Daemon, central-daemon, mailbox, and daemon-client modules must not contain web-user business branches or special endpoint methods.

## Focused Test Matrix

### Web-User Adapter Tests

Target file: `tests/test_web_user_actor.py`.

Add unit tests with isolated runtime workspace and fake daemon access:

- `test_web_user_actor_address_is_external_user`
  - Assert `WEB_USER_ACTOR_ADDRESS == {"role_id": "user", "actor_id": "act-user-local"}`.
  - Assert no manifest role named `user` is required.

- `test_send_web_user_message_creates_normal_message_and_delivers_signal`
  - Arrange a fake online target `{"role_id":"dev","actor_id":"act-dev-target"}`.
  - Send text `"Please review this from the browser."`.
  - Assert result `ok is True`, `message_id` is present, `delivery_status == "delivered"`, and `handling_status` is propagated.
  - Assert exactly one durable message row exists with web-user sender, target recipient, content, `reply_to is None`, and `disposition == "unseen"`.
  - Assert daemon calls are `reachability` then `deliver`.
  - Assert delivered signal type is `message.available`, source is web-user, target is target actor, payload is only `{"message_id": ...}`, and signal has no content/from_role/to_role fields.

- `test_send_web_user_message_target_not_online_creates_no_message`
  - Fake reachability `registered_offline`.
  - Assert result is rejected with `delivery_status`/reachability metadata from message-owned semantics.
  - Assert no message row is created and no deliver call is made.

- `test_send_web_user_message_delivery_failure_cleans_created_message`
  - Fake reachability online and delivery `delivery_failed`.
  - Assert result is rejected with `cleanup_status == "cleaned"` and no durable row remains.

- `test_web_user_sink_acknowledges_message_available`
  - Dispatch a mailbox-compatible `message.available` signal to the sink dispatcher without creating a real socket.
  - Assert response has `accepted is True`, `handled_count == 1`, `matched_count == 1`, and `handling_status == "acknowledged"`.

- `test_web_user_sink_socket_is_mailbox_compatible_and_cleaned_up`
  - Start the sink in a temp directory only.
  - Deliver through `daemon_client.request_mailbox("mailbox.deliver", ...)`.
  - Close and join the thread.
  - Assert delivery response is ok, handling is acknowledged, socket is gone, and thread is not alive.

Focused command:

```bash
python -m pytest tests/test_web_user_actor.py -q
```

Expected red result before implementation:

```text
ERROR ... expected module to exist: tools/launcher/web_user_actor.py
```

### Message Participant Tests

Target file: `tests/test_message_env_tool.py`.

Add regression tests:

- `test_message_send_reply_to_accepts_external_user_participant`
  - Seed an inbound message from web-user to a dev actor.
  - Dispatch `message.send` from the dev actor with `target_actor_address` set to web-user and `reply_to` set to the inbound message id.
  - Fake reachability online and delivery delivered.
  - Assert reply is durable, original message is marked `replied`, and delivery target is web-user.

- `test_message_conversation_accepts_external_user_participant`
  - Seed bidirectional messages between dev and web-user.
  - Dispatch `message.conversation` from dev with target web-user.
  - Assert the visible conversation rows are returned in chronological order.

- `test_message_active_user_role_is_not_manifest_declared`
  - Call `ensure_active_role_is_manifest_declared(active_role="user", manifest_role_ids=manifest roles)`.
  - Assert it still raises `MessageScopeError`.

Focused command:

```bash
python -m pytest \
  tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_reply_to_accepts_external_user_participant \
  tests/test_message_env_tool.py::MessageEnvToolTests::test_message_conversation_accepts_external_user_participant \
  tests/test_message_env_tool.py::MessageEnvToolTests::test_message_active_user_role_is_not_manifest_declared \
  -q
```

Expected red result before implementation:

```text
FAILED ... unknown target actor role: user
```

### Web Management API Tests

Target file: `tests/test_web_management.py`.

Add service-level tests with an injected fake `web_message_sender`:

- `test_messages_route_rejects_empty_text_before_status_lookup`
  - `POST /api/instances/act-dev-demo/messages` with blank text.
  - Assert HTTP 400, no launcher command, no adapter call.

- `test_messages_route_resolves_target_from_instance_status_and_calls_adapter`
  - Fake instance status includes `actor_id:"act-dev-demo"` and `role:"dev"`.
  - Fake adapter returns `ok`, `message_id`, `delivery_status`, `handling_status`, and `target_actor_address`.
  - Assert response includes `ok`, `message_id`, `delivery_status`, `handling_status`, `target_actor_address`, and `instance`.
  - Assert adapter received target actor address from status, not from request body.

- `test_messages_route_maps_adapter_rejection_to_structured_error`
  - Fake adapter returns a normal message-owned rejection such as `E_MESSAGE_TARGET_NOT_ONLINE`.
  - Assert HTTP 409 with structured error details and instance status.

- `test_web_management_does_not_write_message_rows_or_construct_signals`
  - Source scan `tools/launcher/web_management.py`.
  - Assert no `env.repos.messages`, `create_message`, `save_message`, `delete_message`, `message.available`, `signal_id`, or `daemon_client.deliver_signal` appears outside imported adapter invocation.

Focused command:

```bash
python -m pytest tests/test_web_management.py -q
```

Expected red result before implementation:

```text
FAILED ... API route not found
```

### Web UI Contract Tests

Target files:

- `tests/web_management_ui_contract.test.js`
- `tests/web_management_ui_state.test.js`

Update contract tests:

- Keep the selected-instance text box and send button.
- Assert production JavaScript uses `/messages`.
- Assert production JavaScript no longer sends selected-instance text to `/input`.
- Assert visible copy uses direct-message wording such as `Message`.
- Assert visible copy does not describe the primary send action as `Instruction`, `steer`, or `thread input`.
- State tests still prove active healthy selected instances enable send when draft text is present.

Focused command:

```bash
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Expected red result before implementation:

```text
not ok ... Expected asset content to include: /messages
```

### Boundary And Residue Tests

Targets:

- `tests/test_daemon_communication_boundary.py`
- new or updated scans in `tests/test_web_user_actor.py` or `tests/test_web_management.py`

Add or update scans:

- Daemon and central-daemon infrastructure files must not contain:
  - `act-user-local`
  - `web_user`
  - `web-user`
  - `send_web_message`
  - `message.available` special branches outside existing generic validation and message-owned handlers.
- `scripts/env/tool_runtime/daemon_client.py` must stay generic.
- `web_management.py` must not import message repos or construct signals.
- `buddyswitch/manifest.toml` must not include role id `user`.

Focused command:

```bash
python -m pytest tests/test_daemon_communication_boundary.py tests/test_web_user_actor.py tests/test_web_management.py -q
```

## Broader Verification

After focused tests pass:

```bash
python -m pytest tests/test_web_user_actor.py tests/test_web_management.py tests/test_message_env_tool.py -q
python -m pytest tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py -q
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

If these pass without service residue, run the smallest broader Python suite that does not start long-lived services unexpectedly:

```bash
python -m pytest tests/test_message_available_handler.py tests/test_central_daemon_service.py tests/test_daemon_core_decoupling.py -q
```

Do not run a full broad launcher suite until any service-starting helpers have explicit cleanup and a residual process/socket check.

## Phase 1 Review

Spec coverage:

- The tests cover web-user send, actor reply, conversation lookup, HTTP adaptation, UI send behavior, sink reachability, and boundary scans.
- The tests explicitly prove `user` is external-only: valid as a participant, invalid as a launchable active runtime role.
- The tests cover delivery failure cleanup, not only happy-path message creation.
- The tests preserve daemon genericity and prevent web-management direct storage/signal ownership.

Resource lifecycle:

- Default tests use isolated runtime workspaces and fake daemon access.
- The one socket compatibility test owns close, join, socket cleanup, and thread liveness assertion.
- No planned test starts a real instance daemon, app-server, browser, runtime broker, or persistent central daemon.

Forward check:

- The plan factors existing message-owned send semantics instead of duplicating a second create-and-deliver path.
- It replaces the visible web send path with `/messages` instead of preserving thread input as the primary UI path.
- It does not add a workflow engine, event bus, compatibility switch, web inbox UI, read receipts, or special daemon endpoint.
