# External Session Naming Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the misleading `IM connection` / `connection_key` terminology with explicit `external session` / `external_session_key` terminology across live product code, API routes, tests, and residue gates.

**Architecture:** This is a pure naming and boundary rebuild. The external API session remains the auth/session/cursor object for `/api/im/*` callers; it is not an IM contact, not reach, not online presence, and not channel delivery. No compatibility aliases are kept.

**Tech Stack:** Python 3, `pytest`, Node `node --test`, BuddySwitch Central IM JSON state, `rg` residue scans.

---

## Scope Lock

This task exists because `IM connection` is now an architectural liability. The name suggests a general IM connectivity concept that actor and external identities might both use. In code, however, the object only serves external API caller session concerns:

- auth key hash;
- bound external identity id;
- event cursor;
- display metadata;
- timestamps.

The next reach/contact rebuild has not started. This task must not implement contact unification, actor-to-external active send, external online status, channel routing, or iMessage outbound behavior.

## Current Problem

### Current Live Names

```text
create_external_connection
authenticate_external_connection_key
send_external_connection_message
read_external_connection_events
ack_external_connection_event
save_im_connection
get_im_connection_by_key_hash
connection
connection_key
connection_key_hash
/api/im/connections
state/im/connections
```

### Why They Are Wrong

`connection` reads like a generic IM communication primitive. That interpretation is false in the current code:

- actor reach uses actor runtime presence and daemon registry;
- external API session uses a key and cursor;
- channel adapters may store their own route state;
- future unified contacts should be a separate reach/contact projection.

Keeping `connection` will keep pulling future design discussions back into the wrong boundary.

## Target Names

Use `external_session` consistently for the API caller session object.

| Old | New |
| --- | --- |
| `create_external_connection` | `create_external_session` |
| `authenticate_external_connection_key` | `authenticate_external_session_key` |
| `send_external_connection_message` | `send_external_session_message` |
| `read_external_connection_events` | `read_external_session_events` |
| `ack_external_connection_event` | `ack_external_session_event` |
| `save_im_connection` | `save_external_session` |
| `get_im_connection_by_key_hash` | `get_external_session_by_key_hash` |
| `connection` variable for this object | `external_session` |
| `connection_key` | `external_session_key` |
| `connection_key_hash` | `external_session_key_hash` |
| `/api/im/connections` | `/api/im/external-sessions` |
| `state/im/connections/` | `state/im/external_sessions/` |

Key prefix changes from `imck-` to `imsk-`.

## Target Boundary

```text
external caller / web server-owned caller / channel adapter
  -> POST /api/im/external-sessions
  -> receives external_session_key
  -> Authorization: Bearer <external_session_key>
  -> /api/im/messages / events / ack / messages/{id}
  -> Central IM sees an external identity from the authenticated external session
```

The external session object is not discoverable as a contact and is not used by actor sender reach.

## Out Of Scope

- Do not add `IM contacts`.
- Do not modify `identity_for_current_send_target` beyond names directly forced by the session rename.
- Do not allow actor active send to `ext-*`.
- Do not make external session status mean online.
- Do not inspect channel route availability.
- Do not keep `/api/im/connections` as an alias.
- Do not keep old Python helper aliases.
- Do not migrate historical docs or old memo text.
- Do not add a data migration path for old local runtime state.

## Files To Change

### Product Core

- Modify: `scripts/env/repos/messages.py`
- Modify: `scripts/env/services/messages.py`

### Projections

- Modify: `tools/launcher/external_im_session.py`
- Modify: `tools/launcher/im_http_router.py`
- Modify: `tools/launcher/web_im_identity.py`
- Modify: `tools/launcher/imessage_channel.py`
- Modify: `tools/launcher/assets/web-management/app.js`

### Tests

- Modify: `tests/test_im_product_core.py`
- Modify: `tests/test_external_im_session.py`
- Modify: `tests/test_im_http_router.py`
- Modify: `tests/test_external_im_projection_contract.py`
- Modify: `tests/test_im_web_management_projection.py`
- Modify: `tests/test_im_external_reply_loop.py`
- Modify: `tests/test_imessage_channel.py`
- Modify: `tests/test_web_management.py`
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tests/web_management_ui_contract.test.js`
- Modify: `tests/test_repo_consistency.py`

### Live Docs

- Modify: `docs/arch/web-interface-call-architecture.md`

Historical `docs/memo/**` and completed `docs/spec/**` files are evidence, not cleanup targets.

---

## Task 1: Product-Core Test Rename First

**Files:**

- Modify: `tests/test_im_product_core.py`

- [ ] **Step 1: Rename product-core helper and test expectations**

Change `_external_connection(...)` to `_external_session(...)`.

Expected helper shape:

```python
def _external_session(
    self,
    *,
    display_name: str = "local smoke",
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    created = message_service.create_external_session(display_name=display_name)
    self.assertTrue(created.get("ok"), msg=created)
    external_session_key = created.get("external_session_key")
    self.assertIsInstance(external_session_key, str, msg=created)
    assert isinstance(external_session_key, str)
    auth = message_service.authenticate_external_session_key(external_session_key)
    self.assertTrue(auth.get("ok"), msg=auth)
    external_session = auth.get("external_session")
    identity = auth.get("identity")
    self.assertIsInstance(external_session, dict, msg=auth)
    self.assertIsInstance(identity, dict, msg=auth)
    assert isinstance(external_session, dict)
    assert isinstance(identity, dict)
    return created, external_session, identity
```

In `test_create_external_connection_returns_only_connection_key_and_persists_internal_state`, rename the test to:

```python
def test_create_external_session_returns_only_session_key_and_persists_internal_state(self) -> None:
```

Expected assertions:

```python
response = message_service.create_external_session(display_name="local smoke")

self.assertTrue(response.get("ok"), msg=response)
external_session_key = response.get("external_session_key")
self.assertIsInstance(external_session_key, str, msg=response)
assert isinstance(external_session_key, str)
self.assertTrue(external_session_key.startswith("imsk-"), msg=response)
self.assertNotIn("connection_key", response)
self.assertNotIn("external_connection", response)
self.assertNotIn("connection", response)

auth = message_service.authenticate_external_session_key(external_session_key)
self.assertTrue(auth.get("ok"), msg=auth)
identity = auth.get("identity")
external_session = auth.get("external_session")
self.assertIsInstance(identity, dict, msg=auth)
self.assertIsInstance(external_session, dict, msg=auth)
assert isinstance(identity, dict)
assert isinstance(external_session, dict)
self.assertEqual(identity.get("type"), "external")
external_id = identity.get("id")
self.assertIsInstance(external_id, str, msg=auth)
assert isinstance(external_id, str)

profile_path = self.runtime_state_root / "buddyswitch" / "objects" / "identities" / "externals" / f"{external_id}.json"
self.assertTrue(profile_path.is_file())

session_files = sorted((self.runtime_state_root / "im" / "external_sessions").glob("*.json"))
self.assertEqual(len(session_files), 1)
session_text = session_files[0].read_text(encoding="utf-8")
self.assertNotIn(external_session_key, session_text)
session_row = json.loads(session_text)
self.assertEqual(session_row["identity_id"], external_id)
self.assertEqual(session_row["display_name"], "local smoke")
self.assertEqual(session_row["last_event_id"], "imev-000000000000")
self.assertTrue(str(session_row["external_session_key_hash"]).startswith("sha256:"))
self.assertNotIn("connection_key_hash", session_row)
self.assertNotIn("connection", session_row)
```

- [ ] **Step 2: Rename behavior tests in the same file**

Use these new test names:

```text
test_external_session_reads_actor_reply_once_without_client_cursor
test_external_session_send_requires_canonical_target_identity_only
test_external_session_ack_rejects_non_visible_event_without_advancing_cursor
test_external_session_ack_rejects_out_of_order_consumable_event
test_external_session_events_waits_for_new_visible_events_until_timeout
```

Replace calls:

```text
send_external_connection_message -> send_external_session_message
read_external_connection_events -> read_external_session_events
ack_external_connection_event -> ack_external_session_event
connection= -> external_session=
```

- [ ] **Step 3: Run red product-core test**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_im_product_core.py -q
```

Expected: FAIL because `create_external_session` and related helpers do not exist yet.

---

## Task 2: Product-Core Implementation Rename

**Files:**

- Modify: `scripts/env/repos/messages.py`
- Modify: `scripts/env/services/messages.py`

- [ ] **Step 1: Rename repo helpers and storage path**

In `scripts/env/repos/messages.py`, replace connection helpers with:

```python
def save_external_session(external_session: dict[str, Any]) -> dict[str, Any]:
    key_hash = _require_non_empty_text(
        external_session.get("external_session_key_hash"),
        "external_session.external_session_key_hash",
    )
    if not key_hash.startswith("sha256:"):
        raise ValueError("external_session.external_session_key_hash must start with sha256:")
    normalized = dict(
        external_session_key_hash=key_hash,
        identity_id=runtime_files.require_id(str(external_session.get("identity_id") or ""), "external_session.identity_id"),
        display_name=_require_non_empty_text(external_session.get("display_name"), "external_session.display_name"),
        last_event_id=_require_non_empty_text(external_session.get("last_event_id"), "external_session.last_event_id"),
        created_at=_require_non_empty_text(external_session.get("created_at"), "external_session.created_at"),
        last_used_at=_require_non_empty_text(external_session.get("last_used_at"), "external_session.last_used_at"),
    )
    _require_im_write_root()
    runtime_files.write_json_object(_im_dir("external_sessions") / f"{key_hash.replace(':', '-', 1)}.json", normalized)
    return normalized


def get_external_session_by_key_hash(key_hash: str) -> dict[str, Any] | None:
    normalized = _require_non_empty_text(key_hash, "external_session_key_hash")
    if not normalized.startswith("sha256:"):
        raise ValueError("external_session_key_hash must start with sha256:")
    path = _im_dir("external_sessions") / f"{normalized.replace(':', '-', 1)}.json"
    if not path.exists():
        return None
    return runtime_files.read_json_object(path)
```

Remove:

```text
save_im_connection
get_im_connection_by_key_hash
```

- [ ] **Step 2: Rename service creation/auth helpers**

In `scripts/env/services/messages.py`, replace:

```python
def create_external_connection(...)
def _im_connection_key_hash(...)
def authenticate_external_connection_key(...)
```

with:

```python
def create_external_session(*, display_name: str) -> dict[str, Any]:
    from env.repos import identities as identity_repo
    from env.repos import messages as message_repo

    normalized_display_name = display_name.strip() if isinstance(display_name, str) else ""
    if not normalized_display_name:
        return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "display_name must be a non-empty string"}}

    external_identity_id = f"ext-{uuid.uuid4().hex[:12]}"
    now = message_repo.runtime_files.now_iso()
    identity_repo.save_external_profile(
        {
            "identity": {"id": external_identity_id, "type": "external"},
            "display_name": normalized_display_name,
            "created_at": now,
        }
    )
    external_session_key = f"imsk-{secrets.token_hex(24)}"
    external_session_key_hash = _external_session_key_hash(external_session_key)
    message_repo.save_external_session(
        {
            "external_session_key_hash": external_session_key_hash,
            "identity_id": external_identity_id,
            "display_name": normalized_display_name,
            "last_event_id": message_repo.INITIAL_IM_EVENT_CURSOR,
            "created_at": now,
            "last_used_at": now,
        }
    )
    return {
        "ok": True,
        "external_session_key": external_session_key,
        "identity": {"id": external_identity_id, "type": "external"},
    }


def _external_session_key_hash(external_session_key: str) -> str:
    return "sha256:" + hashlib.sha256(external_session_key.encode("utf-8")).hexdigest()


def authenticate_external_session_key(external_session_key: str) -> dict[str, Any]:
    from env.repos import messages as message_repo

    if not isinstance(external_session_key, str) or not external_session_key.strip():
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": "external_session_key is required"}}
    external_session = message_repo.get_external_session_by_key_hash(
        _external_session_key_hash(external_session_key.strip())
    )
    if external_session is None:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": "external_session_key is invalid"}}
    try:
        identity = _identity_ref(external_session.get("identity_id"), "external_session.identity_id")
    except ValueError as exc:
        return {"ok": False, "error": {"code": "E_IM_AUTH", "message": str(exc)}}
    updated = dict(external_session)
    updated["identity_id"] = identity["id"]
    updated["last_used_at"] = message_repo.runtime_files.now_iso()
    saved = message_repo.save_external_session(updated)
    return {
        "ok": True,
        "identity": identity,
        "external_session": saved,
    }
```

- [ ] **Step 3: Rename external-session send/read/ack helpers**

Replace:

```text
_connection_identity_ref
_save_connection_last_event
send_external_connection_message
read_external_connection_events
ack_external_connection_event
```

with:

```text
_external_session_identity_ref
_save_external_session_last_event
send_external_session_message
read_external_session_events
ack_external_session_event
```

The public signatures become:

```python
def send_external_session_message(
    *,
    external_session: dict[str, Any],
    target_identity: dict[str, Any],
    content: str,
    reply_to: str | None = None,
) -> dict[str, Any]:
```

```python
def read_external_session_events(
    *,
    external_session: dict[str, Any],
    limit: int = 50,
    wait_ms: int = 0,
) -> dict[str, Any]:
```

```python
def ack_external_session_event(
    *,
    external_session: dict[str, Any],
    event_id: str,
) -> dict[str, Any]:
```

Error messages must use `external_session`, not `connection`:

```text
event is not visible to the external session
event is not consumable by the external session
event_id is not the next unacknowledged event for the external session
```

- [ ] **Step 4: Run product-core tests green**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_im_product_core.py -q
```

Expected: PASS.

---

## Task 3: External Session Projection Rename

**Files:**

- Modify: `tools/launcher/external_im_session.py`
- Modify: `tests/test_external_im_session.py`
- Modify: `tests/test_external_im_projection_contract.py`

- [ ] **Step 1: Rename projection method and parameter names**

In `tools/launcher/external_im_session.py`:

```text
create_connection -> create_external_session
authenticate(connection_key) -> authenticate_external_session_key(external_session_key)
connection parameter -> external_session parameter
_external_identity_from_connection -> _external_identity_from_session
```

The class name `ExternalImSession` can stay because it describes the projection boundary.

Expected method surface:

```python
def create_external_session(self, *, display_name: str) -> dict[str, Any]:
    return message_service.create_external_session(display_name=display_name)


def authenticate_external_session_key(self, external_session_key: str) -> dict[str, Any]:
    return message_service.authenticate_external_session_key(external_session_key)
```

Calls to message service must use:

```text
send_external_session_message
read_external_session_events
ack_external_session_event
```

- [ ] **Step 2: Update projection tests**

In `tests/test_external_im_session.py`, replace helper `_connection(...)` with `_external_session(...)`.

Expected helper return:

```python
return external_session_key, external_session, identity
```

All assertions should use `external_session`, not `connection`.

- [ ] **Step 3: Run projection tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_external_im_session.py tests/test_external_im_projection_contract.py -q
```

Expected: PASS.

---

## Task 4: HTTP API Contract Rename

**Files:**

- Modify: `tools/launcher/im_http_router.py`
- Modify: `tests/test_im_http_router.py`
- Modify: `tests/test_external_im_projection_contract.py`
- Modify: `tests/test_im_web_management_projection.py`

- [ ] **Step 1: Replace route**

In `tools/launcher/im_http_router.py`:

```text
POST /api/im/connections
```

becomes:

```text
POST /api/im/external-sessions
```

Old route must return 404.

- [ ] **Step 2: Replace auth wording and resolved object name**

`Authorization` stays the same Bearer mechanism, but the token name changes:

```text
Authorization: Bearer external_session_key
```

Error messages become:

```text
Authorization: Bearer external_session_key is required
Web IM external session is unavailable
```

Router-local variables:

```text
connection -> external_session
web_connection_provider -> web_external_session_provider
```

The resolved auth payload should be:

```python
resolved = {
    "ok": True,
    "identity": identity,
    "external_session": external_session,
}
```

- [ ] **Step 3: Update HTTP tests**

Replace test calls:

```python
router.handle("POST", "/api/im/connections", ...)
```

with:

```python
router.handle("POST", "/api/im/external-sessions", ...)
```

Expected response:

```python
self.assertIn("external_session_key", created)
self.assertNotIn("connection_key", created)
```

Add or keep a hard deletion assertion:

```python
status, payload = router.handle("POST", "/api/im/connections", b'{"display_name":"Bridge"}', {})
self.assertEqual(status, 404)
```

- [ ] **Step 4: Run HTTP tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_im_http_router.py tests/test_external_im_projection_contract.py tests/test_im_web_management_projection.py -q
```

Expected: PASS.

---

## Task 5: Web And Channel Adapter Rename

**Files:**

- Modify: `tools/launcher/web_im_identity.py`
- Modify: `tools/launcher/imessage_channel.py`
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tests/test_web_management.py`
- Modify: `tests/test_im_web_management_projection.py`
- Modify: `tests/test_imessage_channel.py`
- Modify: `tests/web_management_ui_state.test.js`
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] **Step 1: Rename Web server-owned session fields**

In `tools/launcher/web_im_identity.py`, local persisted record changes:

```text
connection_key -> external_session_key
connection -> external_session
```

Keep file path `im-session.json`; that name is now correct.

Error messages become:

```text
Unable to create Web Management IM external session.
Web Management IM external session creation returned an invalid key.
Web Management IM external session could not be authenticated.
Web Management IM authentication returned an invalid identity.
```

- [ ] **Step 2: Rename iMessage channel API adapter**

In `tools/launcher/imessage_channel.py`:

```text
create_connection -> create_external_session
connection_key parameter -> external_session_key
contact["connection_key"] -> contact["external_session_key"]
_contact_connection_key -> _contact_external_session_key
/api/im/connections -> /api/im/external-sessions
```

Channel contact state remains channel-owned. Only the BuddySwitch API session key field is renamed.

- [ ] **Step 3: Rename Web frontend language**

In `tools/launcher/assets/web-management/app.js`, replace exposed state names and tests:

```text
connection-wide events -> external-session event stream
connection_key -> external_session_key
```

Browser responses must still not expose `external_session_key`.

- [ ] **Step 4: Run Web and channel tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_imessage_channel.py -q
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
```

Expected: PASS.

---

## Task 6: Live Documentation And Residue Gates

**Files:**

- Modify: `docs/arch/web-interface-call-architecture.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Update live architecture doc**

Replace live architecture wording:

```text
Web Management supplies a server-owned Web IM connection
```

with:

```text
Web Management supplies a server-owned external IM session
```

Do not edit historical memos or completed execution evidence.

- [ ] **Step 2: Add targeted residue test**

Add a repo consistency test that scans only live source surfaces:

```python
def test_external_session_naming_has_no_live_connection_residue(self) -> None:
    surfaces = (
        ROOT / "scripts" / "env" / "repos" / "messages.py",
        ROOT / "scripts" / "env" / "services" / "messages.py",
        ROOT / "tools" / "launcher" / "external_im_session.py",
        ROOT / "tools" / "launcher" / "im_http_router.py",
        ROOT / "tools" / "launcher" / "web_im_identity.py",
        ROOT / "tools" / "launcher" / "imessage_channel.py",
        ROOT / "tools" / "launcher" / "assets" / "web-management" / "app.js",
        ROOT / "docs" / "arch" / "web-interface-call-architecture.md",
    )
    forbidden = (
        "create_external_" + "connection",
        "authenticate_external_" + "connection_key",
        "send_external_" + "connection_message",
        "read_external_" + "connection_events",
        "ack_external_" + "connection_event",
        "save_im_" + "connection",
        "get_im_" + "connection_by_key_hash",
        "connection_" + "key",
        "connection_" + "key_hash",
        "/api/im/" + "connections",
        "state/im/" + "connections",
        "im/" + "connections",
        "Web IM " + "connection",
    )
    for surface in surfaces:
        source = surface.read_text(encoding="utf-8")
        for fragment in forbidden:
            with self.subTest(surface=str(surface.relative_to(ROOT)), fragment=fragment):
                self.assertNotIn(fragment, source)
```

This test deliberately does not scan old docs under `docs/memo/**` or `docs/spec/**`.

- [ ] **Step 3: Run residue test**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_external_session_naming_has_no_live_connection_residue -q
```

Expected: PASS.

---

## Task 7: Focused End-To-End Verification

**Files:**

- No new files.

- [ ] **Step 1: Run focused Python suite**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_im_product_core.py \
  tests/test_external_im_session.py \
  tests/test_im_http_router.py \
  tests/test_external_im_projection_contract.py \
  tests/test_im_web_management_projection.py \
  tests/test_im_external_reply_loop.py \
  tests/test_imessage_channel.py \
  tests/test_web_management.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run focused Web asset suite**

Run:

```bash
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
```

Expected: PASS.

- [ ] **Step 3: Run repo consistency suite**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_repo_consistency.py -q
```

Expected: PASS.

- [ ] **Step 4: Run live-source no-hit scans**

Run:

```bash
rg -n "create_external_connection|authenticate_external_connection_key|send_external_connection_message|read_external_connection_events|ack_external_connection_event|save_im_connection|get_im_connection_by_key_hash|connection_key|connection_key_hash|/api/im/connections|state/im/connections|im/connections" \
  scripts/env \
  tools/launcher/external_im_session.py \
  tools/launcher/im_http_router.py \
  tools/launcher/web_im_identity.py \
  tools/launcher/imessage_channel.py \
  tools/launcher/assets/web-management/app.js \
  docs/arch/web-interface-call-architecture.md
```

Expected: no output.

---

## Acceptance Criteria

The task is complete only when all of these are true:

- `/api/im/external-sessions` is the only live route for external API session creation.
- `/api/im/connections` is not accepted, not aliased, and not documented in live surfaces.
- External API auth uses `external_session_key`.
- Product-core storage path is `state/im/external_sessions`.
- Product-core stored key field is `external_session_key_hash`.
- Runtime variables use `external_session` for this object.
- No live source teaches `IM connection` as an external API caller session.
- Actor reach/contact logic is unchanged.
- Actor active send to `ext-*` remains unresolved after this task.
- Channel route behavior is unchanged after this task.
- Focused Python, Web asset, repo consistency, and live-source no-hit scans pass.

## Post-Task State

After this task, the codebase should be easier to reason about:

```text
external_session = external API caller auth/session/cursor
contact = future reach/contact projection
identity = stable actor/external identity
channel route = adapter-owned external transport route
```

The original actor/external free messaging problem is still not solved by this task. The next task can then focus on unified contacts/reach without the misleading `IM connection` name pulling the design back into the wrong boundary.
