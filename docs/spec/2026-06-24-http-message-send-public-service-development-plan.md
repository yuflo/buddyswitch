# HTTP Message Send Public Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move reusable direct-message send semantics into `scripts/env/services/messages.py` and expose web-user sending through `POST /api/messages/send`.

**Architecture:** The public message service owns validation, reachability, durable row creation, delivery, cleanup, and reply disposition updates. `message.send` and `web_user_actor.send_web_user_message` are adapters over that service. `web_management.py` is only an HTTP adapter that validates `actor_id + content`, resolves the target actor, and maps structured service results to HTTP.

**Tech Stack:** Python stdlib, existing env tool runtime context, existing message domain/repo modules, `pytest`/`unittest`, Node built-in test runner for static UI contract tests.

---

## Files And Responsibilities

- Create `scripts/env/services/messages.py`: public message send service.
- Create `scripts/env/services/__init__.py`: package marker and service import boundary.
- Create `tests/test_message_service.py`: service-level behavior and cleanup tests with fake daemon access.
- Modify `scripts/env/tools/message/_impl.py`: keep contacts/get/list/mark tool logic; delegate `message.send` to service.
- Modify `tools/launcher/web_user_actor.py`: call public service, stop importing tool `_impl`.
- Modify `tools/launcher/web_management.py`: add `/api/messages/send`, strict schema, old route removal.
- Modify `tools/launcher/assets/web-management/app.js`: post `{actor_id, content}` to `/api/messages/send`.
- Modify `tests/test_message_env_tool.py`: retain env tool behavior and add boundary assertion.
- Modify `tests/test_web_user_actor.py`: assert public service boundary.
- Modify `tests/test_web_management.py`: replace old-route compatibility tests with new direct API tests and old-route 404 test.
- Modify `tests/web_management_ui_contract.test.js` and `tests/web_management_ui_state.test.js`: assert new endpoint/payload and existing UI behavior.
- Modify `tests/test_daemon_communication_boundary.py` only if a boundary assertion needs the new forbidden strings.

## Task 1: Public Message Service Red Tests

**Files:**
- Create: `tests/test_message_service.py`
- Create expected later: `scripts/env/services/messages.py`

- [ ] Write tests for successful send, target-not-online no-op, delivery cleanup, cleanup indeterminate, reply disposition update, and manifest role enforcement.
- [ ] Use `RuntimeWorkspaceTestMixin` and fake context objects. Do not start real daemons.
- [ ] Run:

```bash
python -m pytest tests/test_message_service.py -q
```

Expected now: fail because `env.services.messages` cannot be imported.

## Task 2: Extract Public Message Service

**Files:**
- Create: `scripts/env/services/__init__.py`
- Create: `scripts/env/services/messages.py`
- Modify: `scripts/env/tools/message/_impl.py`

- [ ] Move reusable send helpers from `scripts/env/tools/message/_impl.py` into `scripts/env/services/messages.py`.
- [ ] Keep result shape equivalent to existing `send_message_from_actor`.
- [ ] Expose:

```python
def send_from_actor(*, args, context, source_actor_address, active_actor, active_role, require_active_role_manifest=True, action="message.send") -> dict[str, Any]:
    ...

def send_from_web_user(*, context, target_actor_address, content, web_user_actor_address, reply_to=None) -> dict[str, Any]:
    ...
```

- [ ] Leave `_impl.py` with tool-owned response helpers for non-send actions and make `send_message` call `message_service.send_from_actor(...)`.
- [ ] Run:

```bash
python -m pytest tests/test_message_service.py -q
python -m pytest tests/test_message_env_tool.py -q
```

Expected: pass after service extraction.

## Task 3: Web-User Adapter Boundary

**Files:**
- Modify: `tools/launcher/web_user_actor.py`
- Modify: `tests/test_web_user_actor.py`

- [ ] Add or update a test proving `web_user_actor.py` does not import `env.tools.message._impl`.
- [ ] Update `send_web_user_message` to call `env.services.messages.send_from_web_user`.
- [ ] Preserve `_run_with_shared_state_root`, `WEB_USER_ACTOR_ADDRESS`, and sink lifecycle behavior.
- [ ] Run:

```bash
python -m pytest tests/test_web_user_actor.py -q
```

Expected: pass with no lingering socket/thread.

## Task 4: Direct HTTP Send API Red Tests

**Files:**
- Modify: `tests/test_web_management.py`

- [ ] Replace old route success/rejection tests with `POST /api/messages/send` tests.
- [ ] Add strict unknown-field tests for `role_id`, `from_actor_address`, `reply_to`, `text`, `metadata`, `priority`, `attachments`, `session_id`, and `client_request_id`.
- [ ] Add old route removal test: `POST /api/instances/act-dev-demo/messages` returns 404 and calls neither status lookup nor sender.
- [ ] Run:

```bash
python -m pytest tests/test_web_management.py::WebManagementServiceTests::test_messages_send_route_rejects_empty_content_before_status_lookup -q
python -m pytest tests/test_web_management.py::WebManagementServiceTests::test_instances_messages_route_is_removed -q
```

Expected now: fail because the new route does not exist and the old route still exists.

## Task 5: Implement HTTP API

**Files:**
- Modify: `tools/launcher/web_management.py`

- [ ] In `handle_api`, route `POST /api/messages/send` before instance-action parsing.
- [ ] Add `_send_message_http(body)` that accepts exactly `actor_id` and `content`.
- [ ] Validate actor id with existing `validate_actor_id`.
- [ ] Trim content and reject empty content before `_get_instance_status`.
- [ ] Resolve target from `_get_instance_status(actor_id)` using instance `role` and `actor_id`.
- [ ] Call `_web_message_sender(target_actor_address=..., content=...)`.
- [ ] Return success with service fields and `from_actor_address` when present.
- [ ] Map service rejection with `_web_message_http_error`.
- [ ] Remove `/messages` from `_parse_instance_action_path` so old route is 404.
- [ ] Run:

```bash
python -m pytest tests/test_web_management.py -q
```

Expected: pass.

## Task 6: Web UI Endpoint And Payload

**Files:**
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tests/web_management_ui_contract.test.js`
- Modify: `tests/web_management_ui_state.test.js`

- [ ] Update send request to:

```javascript
fetchJson('/api/messages/send', {
  method: 'POST',
  body: JSON.stringify({
    actor_id: state.selectedInstanceId,
    content: text
  })
})
```

- [ ] Keep response handling asynchronous: delivery status and handling status are feedback, not actor reply content.
- [ ] Remove old `/api/instances/<actor_id>/messages` from assets.
- [ ] Run:

```bash
node --test tests/web_management_ui_contract.test.js
node --test tests/web_management_ui_state.test.js
```

Expected: pass.

## Task 7: Boundary And Residue Tests

**Files:**
- Modify: `tests/test_daemon_communication_boundary.py`
- Modify existing tests only as needed.

- [ ] Add or keep assertions forbidding web-user business strings in daemon infrastructure.
- [ ] Add scan-style tests forbidding production imports of `env.tools.message._impl` as public send boundary.
- [ ] Run:

```bash
python -m pytest tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py -q
rg "from env\\.tools\\.message import _impl|message_impl\\.send_message_from_actor" tools scripts tests
```

Expected: tests pass; scan returns no production import.

## Task 8: Focused Verification

- [ ] Run the focused verification from the test plan:

```bash
python -m pytest tests/test_message_service.py -q
python -m pytest tests/test_message_env_tool.py -q
python -m pytest tests/test_web_user_actor.py -q
python -m pytest tests/test_web_management.py -q
node --test tests/web_management_ui_contract.test.js
node --test tests/web_management_ui_state.test.js
python -m pytest tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py -q
```

- [ ] Run boundary scans:

```bash
rg "act-user-local|web_user|web-user|send_web_message|role_id.*user" tools/launcher/daemon_core.py tools/launcher/daemon_mailbox.py tools/launcher/daemon_triggers.py tools/launcher/central_daemon_core.py scripts/env/tool_runtime/daemon_client.py
rg "env\\.repos\\.messages|create_message|save_message|delete_message|message\\.available|signal_id|daemon_client\\.deliver_signal" tools/launcher/web_management.py
rg "/api/instances/.*/messages|/messages'|/messages\"" tools/launcher/assets/web-management tools/launcher/web_management.py README.md
rg "from env\\.tools\\.message import _impl|message_impl\\.send_message_from_actor" tools scripts tests
```

- [ ] If any command fails, inspect root cause before changing code.

## Self-Review Notes

- Scope matches the memo: public service, env tool adapter, web-user adapter, direct HTTP route, web UI, old route removal, daemon boundary protection.
- No compatibility wrapper is planned for the old route.
- Resource-heavy tests are avoided; fake daemon calls are preferred.
- Reply UI, polling, SSE, WebSocket, multi-user sessions, authentication, and arbitrary sender impersonation remain out of scope.
