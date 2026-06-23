# Web User Actor Message Network Development Plan

Date: 2026-06-23
Source: `docs/memo/2026-06-23-web-user-actor-message-network.md`
Status: Phase 3 completed and verified

## Goal

Let the local web UI send normal durable direct messages to runtime actors as `{"role_id":"user","actor_id":"act-user-local"}`, with actor replies deliverable to a minimal mailbox-compatible sink.

## Architecture

Message semantics stay message-owned. `scripts/env/domain/messages.py` owns participant validation, and `scripts/env/tools/message/_impl.py` owns reachability, durable row creation, generic `message.available` delivery, cleanup, reply disposition, and structured results. `tools/launcher/web_user_actor.py` adapts the web-user actor into that message-owned helper and owns the minimal reply sink. `tools/launcher/web_management.py` only parses HTTP, resolves target instance status, calls the adapter, and formats HTTP responses.

## Files

Create:

- `tools/launcher/web_user_actor.py`: web-user actor constants, message send adapter, register/unregister helpers, mailbox-compatible sink.
- `tests/test_web_user_actor.py`: adapter, sink, lifecycle, and boundary tests.

Modify:

- `scripts/env/domain/messages.py`: allow external `user` as a direct-message participant without declaring it as an active manifest role.
- `scripts/env/tools/message/_impl.py`: factor the existing `message.send` body into a reusable message-owned helper that can be called by web-user ingress without duplicating send semantics.
- `tools/launcher/web_management.py`: add `/api/instances/<actor_id>/messages`, inject adapter for tests, keep HTTP-only ownership.
- `tools/launcher/assets/web-management/index.html`: change visible selected-instance send copy from instruction/thread wording to direct-message wording.
- `tools/launcher/assets/web-management/app.js`: post selected-instance send text to `/messages` and display structured delivery feedback.
- `tests/test_message_env_tool.py`: external user reply/conversation/active-role regressions.
- `tests/test_web_management.py`: web messages route, structured errors, and web-management boundary tests.
- `tests/web_management_ui_contract.test.js`: UI route/copy contract.
- `tests/web_management_ui_state.test.js`: keep send enablement behavior aligned after route change.
- `tests/test_daemon_communication_boundary.py`: add web-user business-string boundary coverage if not already covered elsewhere.

Do not modify:

- `tools/launcher/daemon_core.py`
- `tools/launcher/central_daemon_core.py`
- `tools/launcher/daemon_mailbox.py`
- `tools/launcher/daemon_triggers.py`
- `scripts/env/tool_runtime/daemon_client.py`
- `buddyswitch/manifest.toml`
- role AGENTS files or prompt instructions

## Implementation Tasks

### Task 1: Add failing web-user adapter tests

Create `tests/test_web_user_actor.py`.

Test helpers:

- Load `tools/launcher/web_user_actor.py` by importlib, matching existing launcher tests.
- Use `RuntimeWorkspaceTestMixin` for isolated durable message rows.
- Use small fake daemon/context objects for reachability and delivery.
- For the sink socket test, use `tempfile.TemporaryDirectory`, start one daemon mailbox server thread, call close and join in cleanup, and assert the thread stops.

Required tests are the six web-user adapter tests listed in the test plan.

Run:

```bash
python -m pytest tests/test_web_user_actor.py -q
```

Expected before implementation:

```text
ERROR ... expected module to exist: tools/launcher/web_user_actor.py
```

### Task 2: Add failing external participant regressions

Edit `tests/test_message_env_tool.py`.

Add:

- `test_message_send_reply_to_accepts_external_user_participant`
- `test_message_conversation_accepts_external_user_participant`
- `test_message_active_user_role_is_not_manifest_declared`

Use the existing `_patch_daemon`, `_dispatch`, `_actor_address`, and runtime workspace helpers. Define the web-user payload inline as:

```python
web_user = {"role_id": "user", "actor_id": "act-user-local"}
```

Run the three focused tests:

```bash
python -m pytest \
  tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_reply_to_accepts_external_user_participant \
  tests/test_message_env_tool.py::MessageEnvToolTests::test_message_conversation_accepts_external_user_participant \
  tests/test_message_env_tool.py::MessageEnvToolTests::test_message_active_user_role_is_not_manifest_declared \
  -q
```

Expected before implementation:

```text
FAILED ... unknown target actor role: user
```

### Task 3: Add failing web-management and UI tests

Edit `tests/test_web_management.py`.

Add an injected fake adapter callback to `WebManagementService` construction in tests, then add:

- blank `/messages` request rejects before status lookup;
- success path resolves target from instance status and calls adapter;
- adapter rejection maps to structured HTTP error;
- source scan proving no direct message repo writes or inline signal construction.

Edit `tests/web_management_ui_contract.test.js`:

- Require `/messages`.
- Forbid selected text submission to `/input` from production JavaScript.
- Require direct-message wording and forbid primary send copy that says `Instruction`, `steer`, or `thread input`.

Run:

```bash
python -m pytest tests/test_web_management.py -q
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Expected before implementation:

```text
FAILED ... API route not found
not ok ... Expected asset content to include: /messages
```

### Task 4: Widen message participant rules narrowly

Edit `scripts/env/domain/messages.py`.

Add:

```python
EXTERNAL_MESSAGE_ROLE_IDS = {"user"}


def message_participant_role_ids(manifest_role_ids: set[str]) -> set[str]:
    return set(manifest_role_ids) | EXTERNAL_MESSAGE_ROLE_IDS
```

Use `message_participant_role_ids(manifest_role_ids)` for target/filter validation in:

- `prepare_send_request`
- `prepare_conversation_request`
- `prepare_list_request`
- `prepare_contacts_request`

Keep `ensure_active_role_is_manifest_declared` unchanged. That is the gate proving `user` is not an active launchable runtime role.

Run:

```bash
python -m pytest \
  tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_reply_to_accepts_external_user_participant \
  tests/test_message_env_tool.py::MessageEnvToolTests::test_message_conversation_accepts_external_user_participant \
  tests/test_message_env_tool.py::MessageEnvToolTests::test_message_active_user_role_is_not_manifest_declared \
  -q
```

Expected:

```text
3 passed
```

### Task 5: Factor message-owned send semantics

Edit `scripts/env/tools/message/_impl.py`.

Extract the existing body of `send_message` after local variable setup into a helper with this shape:

```python
def send_message_from_actor(
    *,
    args: dict[str, Any],
    context: MessageServiceContext,
    source_actor_address: Any,
    active_actor: dict[str, Any],
    active_role: str,
    require_active_role_manifest: bool = True,
    action: str = "message.send",
) -> dict[str, Any]:
    ...
```

The helper must:

- optionally call `ensure_active_role_is_manifest_declared` only when `require_active_role_manifest` is true;
- call `prepare_send_request`;
- call reachability before message creation;
- create the message through `context.repos.message.create_message`;
- deliver through `context.daemon.deliver_message_available`;
- clean up on delivery failure with the existing cleaned/indeterminate structured rejections;
- keep reply-to disposition behavior unchanged;
- return the same success/rejection shape as current `message.send`.

Change public `send_message` to call the helper with `require_active_role_manifest=True` and `source_actor_address=context.actor_address`.

Run:

```bash
python -m pytest tests/test_message_env_tool.py -q
```

Expected:

```text
all tests pass
```

### Task 6: Implement web-user actor adapter and sink

Create `tools/launcher/web_user_actor.py`.

Required public surface:

```python
WEB_USER_ACTOR_ADDRESS = {"role_id": "user", "actor_id": "act-user-local"}

def send_web_user_message(*, target_actor_address: dict[str, Any], content: str, reply_to: str | None = None) -> dict[str, Any]: ...
def register_web_user_actor(*, socket_path: Path | None = None, central_socket_path: Path | None = None) -> dict[str, Any]: ...
def unregister_web_user_actor(*, central_socket_path: Path | None = None) -> dict[str, Any]: ...
def web_user_mailbox_socket_path(shared_root: Path | None = None) -> Path: ...
def build_web_user_sink_server(*, socket_path: Path | None = None) -> daemon_mailbox.DaemonMailboxServer: ...
def web_user_sink_dispatcher(trigger: Any) -> dict[str, Any]: ...
```

Implementation notes:

- Import `scripts/env` and launcher helper paths the same way neighboring launcher modules do.
- Build a `ToolContext` for the external actor using `ActorProfile`/`ActorAddress`.
- Call `env.tools.message._impl.send_message_from_actor` with `require_active_role_manifest=False`.
- Do not import `env.repos.messages` directly from this module.
- Use `daemon_client.register_actor` with endpoint kind `daemon_mailbox_socket`.
- The sink dispatcher should acknowledge only `message.available` with a non-empty `message_id`; unknown signal types can be accepted with `handling_status:"ignored"`.
- Do not submit turns, route parent/side work, inspect app-server state, or mutate daemon registry files directly.

Run:

```bash
python -m pytest tests/test_web_user_actor.py -q
```

Expected:

```text
all tests pass
```

### Task 7: Add web-management `/messages` route

Edit `tools/launcher/web_management.py`.

Changes:

- Import `web_user_actor`.
- Add optional constructor parameter `web_message_sender`, defaulting to `web_user_actor.send_web_user_message`.
- Extend `_parse_instance_action_path` so `/api/instances/<actor_id>/messages` maps to action `messages`.
- Add `_send_message(actor_id, body)`:
  - parse JSON object;
  - require non-empty `text`;
  - reject unsupported request fields except `text`;
  - call `_get_instance_status(actor_id)`;
  - derive target actor address from status `role` and `actor_id`;
  - call the adapter with target and trimmed text;
  - return structured success fields plus latest instance status.
- Add a small mapper for adapter rejections:
  - reachability and delivery rejections should return HTTP 409;
  - invalid payload/scope should return HTTP 400;
  - indeterminate delivery cleanup should return HTTP 502;
  - include adapter result fields in error details without hiding runtime status.

Run:

```bash
python -m pytest tests/test_web_management.py -q
```

Expected:

```text
all tests pass
```

### Task 8: Switch the live web UI send path to messages

Edit `tools/launcher/assets/web-management/index.html`:

- Change label `Instruction` to `Message`.
- Change textarea hint text to `Send a direct message to the selected actor.`
- Change action panel subtitle from `Main-thread control and lifecycle recovery` to `Direct message and lifecycle controls`.
- Change the page summary from `Create, inspect, steer, and recover local role instances from one workspace.` to `Create, inspect, message, and recover local actor instances from one workspace.`

Edit `tools/launcher/assets/web-management/app.js`:

- Keep existing enablement rules for active healthy instances.
- Change the send-button fetch from `/input` to `/messages`.
- On success, set message banner to include `Sent message <message_id>.` and delivery status.
- Keep `/input` out of production asset route usage for selected text submission.

Run:

```bash
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Expected:

```text
all tests pass
```

### Task 9: Add and run boundary/residue scans

Update `tests/test_daemon_communication_boundary.py` or focused scan tests to prove:

- no web-user business strings in daemon or central-daemon infrastructure;
- no direct message repo writes or signal construction in `web_management.py`;
- manifest roles still exclude `user`;
- live web assets no longer present selected-instance send as thread input/steering.

Run:

```bash
python -m pytest tests/test_daemon_communication_boundary.py tests/test_web_user_actor.py tests/test_web_management.py -q
```

Expected:

```text
all tests pass
```

### Task 10: Broader verification and review

Run:

```bash
python -m pytest tests/test_web_user_actor.py tests/test_web_management.py tests/test_message_env_tool.py -q
python -m pytest tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py -q
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Then run:

```bash
python -m pytest tests/test_message_available_handler.py tests/test_central_daemon_service.py tests/test_daemon_core_decoupling.py -q
```

Review checks:

- The only web-user ownership module is `tools/launcher/web_user_actor.py`.
- Message semantics were factored, not duplicated.
- Daemon and central-daemon infrastructure stayed generic.
- No new runtime object fields were added for UI inbox/read status.
- No service-starting test leaked threads, sockets, or processes.

## Phase 1 Review

Spec coverage:

- Each memo hard gate has a task and a test: message-owned semantics, HTTP-only web management, mailbox-compatible sink, external-only user role, and daemon boundary scans.
- The plan explicitly replaces the visible send path instead of leaving thread input as the primary web-to-actor route.
- Out-of-scope UI inbox, sessions, auth, WebSocket/SSE, read receipts, and new message object families are not included.

Ambiguity resolved:

- The selected-instance text box remains the first UI surface, but it now sends direct messages through `/messages`.
- The legacy `/input` route may remain as an internal/API capability if existing tests require it, but production UI must not use it for the primary send action.
- Adapter failures are HTTP errors with structured runtime details, not silent `ok=true` responses.

Resource lifecycle:

- Tests avoid real long-lived launcher paths.
- Socket tests have explicit close/join/residue assertions.
- Broad verification is limited to suites relevant to message, daemon boundary, and web UI contracts.

## Phase 3 Completion

Implemented:

- `tools/launcher/web_user_actor.py` as the only web-user actor adapter and mailbox-compatible reply sink owner.
- Message-owned send factoring in `scripts/env/tools/message/_impl.py`, reused by the web-user adapter without duplicating reachability, durable row creation, delivery, cleanup, or reply disposition rules.
- External `user` participant scope in `scripts/env/domain/messages.py` while keeping `user` out of manifest active-role validation.
- `POST /api/instances/<actor_id>/messages` in `tools/launcher/web_management.py`, with `web_management.py` kept as HTTP adaptation only.
- Live web UI send path switched from selected-instance `/input` submission to `/messages`.
- Root launcher `web` command ensures the central daemon lifecycle so the web-user actor can register before serving the UI.

Verified:

```bash
python -m pytest tests/test_web_user_actor.py tests/test_web_management.py tests/test_message_env_tool.py -q
python -m pytest tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py -q
python -m pytest tests/test_message_available_handler.py tests/test_central_daemon_service.py tests/test_daemon_core_decoupling.py -q
node tests/web_management_ui_contract.test.js && node tests/web_management_ui_state.test.js
git diff --check
```

Final boundary scans showed daemon and central-daemon infrastructure stayed generic, `web_management.py` does not write message rows or construct signals, `buddyswitch/manifest.toml` does not declare a `user` role, live web assets no longer teach the primary send path as thread input or steering, and the test loop left no matching BuddySwitch socket residue under `/tmp`.
