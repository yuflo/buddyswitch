# IM Connection Key Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the external Central IM contract with one stable `connection_key` so external clients no longer see `external_id`, `participant_token`, `event_cursor`, `next_cursor`, or `client_kind`.

**Architecture:** Central IM product core owns the new external connection record. HTTP, WebManagement, and the terminal smoke harness become projections of that single contract. Actor-side `message.list` keeps its internal cursor feed because it is not the external HTTP contract.

**Tech Stack:** Python stdlib services and unittest tests under `scripts/env` and `tools/launcher`; browser management JavaScript under `tools/launcher/assets/web-management`; Node asset contract tests.

---

### Task 1: Define Product-Core Connection Contract

**Files:**
- Modify: `tests/test_im_product_core.py`
- Modify: `scripts/env/repos/messages.py`
- Modify: `scripts/env/services/messages.py`

- [x] **Step 1: Write failing tests**

Replace old external registration tests with tests that call:

```python
connection = message_service.create_external_connection(display_name="local smoke")
auth = message_service.authenticate_external_connection_key(connection["connection_key"])
```

Required assertions:

```python
self.assertTrue(connection["ok"])
self.assertIn("connection_key", connection)
self.assertTrue(connection["connection_key"].startswith("imck-"))
self.assertNotIn("participant", connection)
self.assertNotIn("participant_token", connection)
self.assertNotIn("event_cursor", connection)
self.assertTrue(auth["ok"])
self.assertEqual(auth["participant"]["kind"], "external")
```

Add a persistence assertion that `state/im/connections/*.json` stores `connection_key_hash`, `participant`, `display_name`, `last_event_id`, `created_at`, and `last_used_at`, and does not store the plaintext key.

- [x] **Step 2: Run red test**

Run:

```bash
python -m unittest tests.test_im_product_core.ImProductCoreTests.test_create_external_connection_returns_only_connection_key_and_persists_internal_state -v
```

Expected: fail because `create_external_connection` does not exist.

- [x] **Step 3: Implement repository support**

Add concrete connection repo helpers:

```python
def save_im_connection(connection: dict[str, Any]) -> dict[str, Any]: ...
def get_im_connection_by_key_hash(key_hash: str) -> dict[str, Any] | None: ...
```

The file path is `state/im/connections/sha256-<digest>.json`; the stored payload uses `connection_key_hash: "sha256:<digest>"`.

- [x] **Step 4: Implement service support**

Add:

```python
def create_external_connection(*, display_name: str) -> dict[str, Any]: ...
def authenticate_external_connection_key(connection_key: str) -> dict[str, Any]: ...
```

`create_external_connection` generates `imck-...`, creates one internal external participant, initializes `last_event_id` to `INITIAL_IM_EVENT_CURSOR`, saves the connection, and returns only `{"ok": True, "connection_key": ...}`.

- [x] **Step 5: Run green test**

Run the same unittest command and expect PASS.

### Task 2: Move External Event Position Into Connection

**Files:**
- Modify: `tests/test_im_product_core.py`
- Modify: `scripts/env/services/messages.py`

- [x] **Step 1: Write failing tests**

Add product-core tests for:

```python
send = message_service.send_external_connection_message(connection=auth["connection"], to=actor, content="ping", wake_actor=...)
events = message_service.read_external_connection_events(connection=auth["connection"], wait_ms=0)
repeat = message_service.read_external_connection_events(connection=auth["connection"], wait_ms=0)
```

Required assertions:

```python
self.assertNotIn("next_cursor", send)
self.assertEqual(events["events"], [])
self.assertEqual(repeat["events"], [])
```

Then send an actor reply to the same internal external participant and assert:

```python
self.assertEqual([event["message_id"] for event in first_reply_read["events"]], [reply["message"]["id"]])
self.assertEqual(second_reply_read["events"], [])
self.assertNotIn("next_cursor", first_reply_read)
self.assertNotIn("participant", first_reply_read)
```

- [x] **Step 2: Run red test**

Run:

```bash
python -m unittest tests.test_im_product_core.ImProductCoreTests.test_external_connection_reads_actor_reply_once_without_client_cursor -v
```

Expected: fail because external connection send/read helpers do not exist.

- [x] **Step 3: Implement connection helpers**

Add:

```python
def send_external_connection_message(*, connection: dict[str, Any], to: dict[str, Any], content: str, wake_actor: Any | None = None) -> dict[str, Any]: ...
def read_external_connection_events(*, connection: dict[str, Any], limit: int = 50, wait_ms: int = 0) -> dict[str, Any]: ...
```

`send_external_connection_message` delegates to `send_im_message`, advances `connection.last_event_id` to the send event, persists the connection, and removes external `next_cursor` from the response.

`read_external_connection_events` calls existing `read_im_events` with the connection's internal `last_event_id`, persists the returned last event id only when events are returned, and returns `{"ok": True, "events": [...]}` without `next_cursor` or participant identity.

- [x] **Step 4: Run green test**

Run the same unittest command and expect PASS.

### Task 3: Replace External HTTP Contract

**Files:**
- Modify: `tests/test_im_http_router.py`
- Modify: `tests/test_im_external_reply_loop.py`
- Modify: `tests/test_im_web_management_projection.py`
- Modify: `tests/test_web_management.py`
- Modify: `tools/launcher/im_http_router.py`

- [x] **Step 1: Write failing HTTP tests**

Replace old registration route tests with:

```python
status, created = router.handle("POST", "/api/im/connections", b'{"display_name":"local smoke"}', {})
key = created["connection_key"]
```

Required assertions:

```python
self.assertEqual(status, 200)
self.assertNotIn("participant", created)
self.assertNotIn("participant_token", created)
self.assertNotIn("event_cursor", created)
```

Assert:

```python
self.assertEqual(router.handle("POST", "/api/im/external-participants", b"{}", {})[0], 404)
self.assertEqual(router.handle("GET", "/api/im/events?cursor=imev-old&wait_ms=0", b"", {"Authorization": f"Bearer {key}"})[0], 400)
```

- [x] **Step 2: Run red tests**

Run:

```bash
python -m unittest tests.test_im_http_router tests.test_im_external_reply_loop tests.test_im_web_management_projection tests.test_web_management -v
```

Expected: fail because HTTP still exposes old route and external cursor mode.

- [x] **Step 3: Implement router replacement**

Change `ImHttpRouter`:

```python
POST /api/im/connections -> message_service.create_external_connection(display_name=...)
_authenticate -> message_service.authenticate_external_connection_key(...)
POST /api/im/messages -> message_service.send_external_connection_message(...)
GET /api/im/events -> reject query cursor with 400 E_IM_PAYLOAD, otherwise message_service.read_external_connection_events(...)
POST /api/im/external-participants -> 404
```

Keep `/api/im/actors`, `/api/im/messages/{id}`, `/api/im/messages/{id}/replies`, `/api/im/messages/{id}/disposition`, and `/api/im/conversations/direct` authenticated by the connection participant.

- [x] **Step 4: Run green tests**

Run the same unittest command and expect PASS.

### Task 4: Update WebManagement Consumer

**Files:**
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tests/web_management_ui_contract.test.js`
- Modify: `tools/launcher/assets/web-management/app.js`

- [x] **Step 1: Write failing asset tests**

Replace cursor URL tests with:

```javascript
assert.equal(app.buildImEventsUrl(15000), '/api/im/events?wait_ms=15000');
```

Add contract exclusions:

```javascript
assertExcludes(appJs, '/api/im/external-participants');
assertExcludes(appJs, 'participant_token');
assertExcludes(appJs, 'event_cursor');
assertExcludes(appJs, 'imEventCursor');
assertExcludes(appJs, 'cursor=');
```

- [x] **Step 2: Run red tests**

Run:

```bash
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
```

Expected: fail against old JS.

- [x] **Step 3: Implement WebManagement JS**

Rename state and methods:

```javascript
imParticipantToken -> imConnectionKey
ensureImParticipant -> ensureImConnection
```

Use localStorage key `buddyswitch.imConnectionKey`. Create a connection through `/api/im/connections` with `{ display_name: 'BuddySwitch Web' }`. Poll via `/api/im/events?wait_ms=15000`. Never store or send an external cursor.

- [x] **Step 4: Run green tests**

Run the same Node command and expect PASS.

### Task 5: Update Terminal Smoke Harness

**Files:**
- Modify: `tmp/im_reply_console.py`

- [x] **Step 1: Implement ignored harness update**

Use a local profile containing only:

```json
{"connection_key": "imck-..."}
```

First run creates `/api/im/connections`; later runs reuse `connection_key`. Poll `/api/im/events?wait_ms=15000`. Do not store `external_id`, token, or cursor.

- [x] **Step 2: Verify syntax**

Run:

```bash
python -m py_compile tmp/im_reply_console.py
```

Expected: PASS.

### Task 6: Residue Scan and Focused Verification

**Files:**
- All files touched above.

- [x] **Step 1: Run residue scan**

Run:

```bash
rg "external-participants|participant_token|event_cursor|imEventCursor|cursor=" \
  tools/launcher/im_http_router.py \
  tools/launcher/assets/web-management/app.js \
  tmp/im_reply_console.py \
  tests
```

Expected: no hits except actor-tool cursor tests that do not touch external HTTP/Web/terminal.

- [x] **Step 2: Run focused Python tests**

Run:

```bash
python -m unittest tests.test_im_product_core tests.test_im_http_router tests.test_im_external_reply_loop tests.test_im_web_management_projection tests.test_web_management tests.test_message_tool_im_client -v
```

Expected: PASS.

- [x] **Step 3: Run focused Node tests**

Run:

```bash
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
```

Expected: PASS.

- [x] **Step 4: Final review**

Confirm the only external IM identity visible in live HTTP/Web/terminal surfaces is `connection_key`, and confirm old API compatibility was not kept.
