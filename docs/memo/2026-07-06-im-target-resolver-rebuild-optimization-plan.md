# IM Target Resolver Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Central IM send target resolution so actor and external identities are resolved by one sender-facing IM target resolver, without building a contact layer or preserving the old actor-row send path.

**Architecture:** `resolve_im_send_target(sender_identity, target_identity_id, actor_reachability_checker=...)` becomes the single authority for new-message send targets. Identity owns static actor/external profiles, central daemon owns actor runtime online status, `external_session` owns API auth/cursor only, `message.contacts` remains a discovery view only, and post-write delivery stays after durable IM write.

**Tech Stack:** Python 3, `env.services.messages`, `env.repos.identities`, actor runtime `DaemonAccess.check_reachability`, launcher IM projections, pytest/unittest, repo consistency scans.

---

## Read-In Summary

`docs/bitter` was reviewed as a directory of principle notes. Requirements applied to this task:

- Fix the layer that owns the wrong contract: send target semantics belong in IM product core, not prompt text or contact/list views.
- Do not let an interface layer own product semantics: `ActorImClient`, `ExternalImSession`, HTTP router, and Web UI are projections of Central IM.
- For semantic replacement, prove behavior and live-surface cleanup: add behavior tests and scoped residue scans.
- Keep the end-to-end contract alive: actor action -> Central IM write -> external observable event must be proven.
- Avoid wrong-boundary narrowness: do not add one more special-case path beside the old actor-row resolver.
- No dual-track compatibility: delete the old send target resolver and old tests that teach `ext-*` rejection as correct.

## Task Objective

Replace this current behavior:

```text
message.send(target_identity_id=...)
  -> list online actors
  -> scan actor runtime rows
  -> accept only matching online actor row
  -> reject ext-*
```

With this behavior:

```text
message.send(target_identity_id=...)
  -> resolve_im_send_target(sender_identity, target_identity_id)
  -> actor: identity profile exists + daemon.check_reachability is online
  -> external: identity profile exists + IM visible event is writable
  -> send_im_message(sender_identity, target_identity)
  -> post-write delivery / read-ack branch
```

## Core Requirements

- Do not create a new contact table, contact registry, or contact authority.
- Do not put `ext-*` into central daemon registry.
- Do not make `external_session` a reachability source.
- Do not preserve `identity_for_current_send_target(actor_rows, ...)` as a compatibility path.
- Do not let `message.send` call `list_online_actors` or scan actor rows.
- Keep `message.contacts` as a read-only discovery view; it must not decide send permission.
- Keep `send_im_message` durable-write only; target resolution stays before it, actor/external delivery stays after it.
- Keep actor-to-actor behavior: only existing online actor targets are accepted.
- Open actor-to-external at Central IM / `/api/im/*` level: existing external identity targets are accepted and visible through external event read/ack.
- Channel adapter outbound push is out of scope; this plan only guarantees Central IM visible events.

## Current Code Findings

- Actor send currently resolves targets through `ActorImClient._send_target_identity` -> `_online_actor_rows` -> `message_service.identity_for_current_send_target(...)`.
  - `scripts/env/tool_runtime/im_client.py:36`
  - `scripts/env/tool_runtime/im_client.py:98`
- The current resolver rejects `ext-*` directly and scans actor runtime rows.
  - `scripts/env/services/messages.py:85`
- External API send uses the same actor-row resolver through `ExternalImSession._actor_target_identity`.
  - `tools/launcher/external_im_session.py:46`
  - `tools/launcher/external_im_session.py:145`
- HTTP/Web projections inject `actor_lister`; today that lister serves both `/api/im/actors` and send target validation.
  - `tools/launcher/im_http_router.py:27`
  - `tools/launcher/web_management.py:287`
- `send_im_message` already accepts identity-shaped actor/external targets and writes identity-addressed conversation/message/event rows.
  - `scripts/env/services/messages.py:249`
- Actor post-write delivery is already split behind `attach_post_write_delivery_status`.
  - `scripts/env/services/messages.py:375`
- Identity repositories already expose actor/external profile reads.
  - `scripts/env/repos/identities.py:38`
  - `scripts/env/repos/identities.py:61`
- Daemon exposes direct actor reachability by identity id.
  - `scripts/env/tool_runtime/context.py:363`
  - `scripts/env/tool_runtime/daemon_client.py:378`

## Target Module Boundaries

| Module | Owns | Must Not Own |
|---|---|---|
| `env.repos.identities` | static actor/external profile existence | online state, delivery, session cursor |
| central daemon | actor process presence and mailbox endpoint | external user identity, IM conversation semantics |
| `env.services.messages` | IM target resolution, durable message write, external session event cursor | daemon registry row parsing for send, channel push |
| `ActorImClient` | actor tool projection and context injection | target rules, actor row scanning |
| `ExternalImSession` | external API session projection | actor-row send validation, external reach state |
| `message.contacts` | optional target discovery view | send permission authority |

## Acceptance Contract

Primary end-to-end contract:

```text
actor calls message.send(target_identity_id=ext-...)
  -> IM resolver accepts existing external identity
  -> Central IM writes message/event
  -> external session read_events returns the actor-created message event
```

Actor-to-actor preservation contract:

```text
actor calls message.send(target_identity_id=act-...)
  -> IM resolver accepts existing online actor identity
  -> Central IM writes message/event
  -> post-write delivery submits actor wake payload
```

Negative contract:

```text
actor calls message.send(target_identity_id=missing/offline act-...)
  -> resolver rejects before durable IM write
```

## Task 1: Add Target Resolver Behavior Tests

**Files:**
- Modify: `tests/test_im_product_core.py`
- Modify: `tests/test_message_tool_im_client.py`
- Modify: `tests/test_external_im_session.py`
- Modify: `tests/test_im_http_router.py`

- [ ] **Step 1: Add focused service tests for resolver behavior**

Add tests near the existing current send target tests in `tests/test_im_product_core.py`.

```python
    def test_resolve_im_send_target_accepts_external_identity_without_actor_reachability(self) -> None:
        actor_id = self._runtime_actor_id(role="dev", label="act-dev-resolve-external")
        _created, _external_session, external = self._external_session(display_name="resolver external")
        calls: list[dict[str, object]] = []

        def check_actor_reachability(**kwargs: object) -> dict[str, object]:
            calls.append(dict(kwargs))
            self.fail("external target resolution must not query actor reachability")

        response = message_service.resolve_im_send_target(
            sender_identity={"id": actor_id, "type": "actor"},
            target_identity_id=external["id"],
            actor_reachability_checker=check_actor_reachability,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response["target_identity"], external)
        self.assertEqual(calls, [])
```

```python
    def test_resolve_im_send_target_accepts_existing_online_actor_identity(self) -> None:
        sender_id = self._runtime_actor_id(role="dev", label="act-dev-resolve-actor-source")
        target_id = self._runtime_actor_id(role="market", label="act-market-resolve-actor-target")
        calls: list[dict[str, object]] = []

        def check_actor_reachability(**kwargs: object) -> dict[str, object]:
            calls.append(dict(kwargs))
            return {"reachability_status": "online", "target_identity_id": target_id, "record": {"identity_id": target_id}}

        response = message_service.resolve_im_send_target(
            sender_identity={"id": sender_id, "type": "actor"},
            target_identity_id=target_id,
            actor_reachability_checker=check_actor_reachability,
        )

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response["target_identity"], {"id": target_id, "type": "actor"})
        self.assertEqual(calls, [{"target_identity_id": target_id}])
```

```python
    def test_resolve_im_send_target_rejects_offline_actor_without_writing_im_state(self) -> None:
        sender_id = self._runtime_actor_id(role="dev", label="act-dev-resolve-offline-source")
        target_id = self._runtime_actor_id(role="market", label="act-market-resolve-offline-target")
        before = {
            name: sorted(path.name for path in (self.runtime_state_root / "im" / name).glob("*.json"))
            for name in ("conversations", "messages", "events", "message_states")
        }

        response = message_service.resolve_im_send_target(
            sender_identity={"id": sender_id, "type": "actor"},
            target_identity_id=target_id,
            actor_reachability_checker=lambda **_kwargs: {
                "reachability_status": "registered_offline",
                "target_identity_id": target_id,
                "record": {"identity_id": target_id},
            },
        )

        after = {
            name: sorted(path.name for path in (self.runtime_state_root / "im" / name).glob("*.json"))
            for name in ("conversations", "messages", "events", "message_states")
        }
        self.assertFalse(response.get("ok"), msg=response)
        self.assertEqual(response.get("error", {}).get("code"), "E_IM_TARGET")
        self.assertIn("not online", response.get("error", {}).get("message", ""))
        self.assertEqual(after, before)
```

- [ ] **Step 2: Replace old external rejection actor-client test with actor -> external E2E read test**

Replace `test_actor_send_external_target_rejection_is_reach_policy_not_actor_signature` in `tests/test_message_tool_im_client.py`.

```python
    def test_actor_send_external_target_writes_message_visible_to_external_session(self) -> None:
        actor_id = self._runtime_actor_id(role="dev", label="act-dev-im-ext-send")
        created = message_service.create_external_session(display_name="external target")
        self.assertTrue(created.get("ok"), msg=created)
        auth = message_service.authenticate_external_session_key(str(created["external_session_key"]))
        self.assertTrue(auth.get("ok"), msg=auth)
        external_id = auth["identity"]["id"]

        class _Daemon:
            def __init__(self) -> None:
                self.reachability_calls: list[dict[str, object]] = []
                self.wake_calls: list[dict[str, object]] = []

            def check_reachability(self, *, target_identity_id: str) -> dict[str, object]:
                self.reachability_calls.append({"target_identity_id": target_identity_id})
                return {"reachability_status": "online", "target_identity_id": target_identity_id, "record": {"identity_id": target_identity_id}}

            def list_online_actors(self, *, role_id: str | None = None) -> dict[str, object]:
                self.fail("message.send must not list actors to resolve an explicit target")

            def wake_im_actor(self, payload: dict[str, object]) -> dict[str, object]:
                self.wake_calls.append(dict(payload))
                return {"actor_handling_status": "submitted"}

        daemon = _Daemon()
        client = im_client_module.ActorImClient(_RealImContext(identity_id=actor_id, role_id="dev", daemon=daemon))

        response = client.send({"target_identity_id": external_id, "content": "hello external"})
        events = message_service.read_external_session_events(external_session=auth["external_session"], limit=20, wait_ms=0)

        self.assertTrue(response.get("ok"), msg=response)
        self.assertEqual(response["target_identity"], auth["identity"])
        self.assertEqual(response["actor_handling_status"], "not_applicable")
        self.assertEqual(daemon.reachability_calls, [])
        self.assertEqual(daemon.wake_calls, [])
        self.assertEqual([row["message_id"] for row in events["events"]], [response["message"]["id"]])
```

- [ ] **Step 3: Update actor -> actor client test to prove direct reachability checker is used**

In `tests/test_message_tool_im_client.py`, update `test_actor_send_calls_message_service_with_identity_only_target` so the fake daemon exposes `check_reachability` and fails on `list_online_actors`.

```python
            def check_reachability(self, *, target_identity_id: str) -> dict[str, object]:
                self.assertEqual(target_identity_id, target_id)
                return {"reachability_status": "online", "target_identity_id": target_id, "record": {"identity_id": target_id}}

            def list_online_actors(self, *, role_id: str | None = None) -> dict[str, object]:
                self.fail("message.send must not call list_online_actors")
```

- [ ] **Step 4: Update external API session tests so send uses reachability checker, not actor list**

In `tests/test_external_im_session.py`, adjust `_session(...)` to pass both a lister for `list_actors` and a checker for `send_message`.

```python
        def check_actor_reachability(*, target_identity_id: str) -> dict[str, object]:
            for row in actor_rows:
                if row.get("identity_id") == target_identity_id:
                    status = row.get("status") if isinstance(row.get("status"), str) else "online"
                    return {
                        "reachability_status": "online" if status == "online" else "registered_offline",
                        "target_identity_id": target_identity_id,
                        "record": dict(row),
                    }
            return {"reachability_status": "never_registered", "target_identity_id": target_identity_id, "record": None}

        return external_im_session.ExternalImSession(
            actor_lister=list_actors,
            actor_reachability_checker=check_actor_reachability,
            actor_delivery_handler=handle_actor,
        )
```

- [ ] **Step 5: Add HTTP projection test that POST `/api/im/messages` does not call actor lister**

Add to `tests/test_im_http_router.py`.

```python
    def test_external_http_send_uses_reachability_checker_not_actor_lister(self) -> None:
        actor_identity = self._actor_identity()
        list_calls: list[str | None] = []
        reachability_calls: list[str] = []

        def list_actors(role_id: str | None) -> list[dict[str, object]]:
            list_calls.append(role_id)
            return [{**actor_identity, "status": "online"}]

        def check_actor_reachability(*, target_identity_id: str) -> dict[str, object]:
            reachability_calls.append(target_identity_id)
            return {
                "reachability_status": "online",
                "target_identity_id": target_identity_id,
                "record": {**actor_identity, "status": "online"},
            }

        router = im_http_router.ImHttpRouter(
            actor_lister=list_actors,
            actor_reachability_checker=check_actor_reachability,
            actor_delivery_handler=lambda _payload: {"actor_handling_status": "submitted"},
        )
        status, created = router.handle("POST", "/api/im/external-sessions", b'{"display_name":"local smoke"}', {})
        self.assertEqual(status, 200)
        key = created["external_session_key"]

        status, sent = router.handle(
            "POST",
            "/api/im/messages",
            json.dumps({"target_identity_id": actor_identity["identity_id"], "content": "ping"}).encode("utf-8"),
            {"Authorization": f"Bearer {key}"},
        )

        self.assertEqual(status, 200)
        self.assertTrue(sent.get("ok"), msg=sent)
        self.assertEqual(list_calls, [])
        self.assertEqual(reachability_calls, [actor_identity["identity_id"]])
```

- [ ] **Step 6: Run focused failing tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_im_product_core.py::ImProductCoreTests::test_resolve_im_send_target_accepts_external_identity_without_actor_reachability \
  tests/test_im_product_core.py::ImProductCoreTests::test_resolve_im_send_target_accepts_existing_online_actor_identity \
  tests/test_im_product_core.py::ImProductCoreTests::test_resolve_im_send_target_rejects_offline_actor_without_writing_im_state \
  tests/test_message_tool_im_client.py::ActorImClientMarkTests::test_actor_send_external_target_writes_message_visible_to_external_session \
  tests/test_im_http_router.py::ImHttpRouterTests::test_external_http_send_uses_reachability_checker_not_actor_lister \
  -q
```

Expected before implementation: failures for missing `resolve_im_send_target`, stale daemon fake assumptions, or `ext-*` rejection.

## Task 2: Implement `resolve_im_send_target` in IM Service

**Files:**
- Modify: `scripts/env/services/messages.py`

- [ ] **Step 1: Add resolver error helper and actor reachability callable type**

Near the existing helper declarations in `scripts/env/services/messages.py`, add:

```python
ActorReachabilityChecker = Callable[..., dict[str, Any]]


def _im_target_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": "E_IM_TARGET", "message": message}}
```

- [ ] **Step 2: Add identity profile helpers**

Add local helpers that read identity profiles without writing state:

```python
def _actor_profile_exists(identity_id: str) -> bool:
    from env.repos import identities as identity_repo

    return isinstance(identity_repo.get_actor_identity_profile(identity_id), dict)


def _external_profile_exists(identity_id: str) -> bool:
    from env.repos import identities as identity_repo

    return isinstance(identity_repo.get_external_profile(identity_id), dict)
```

- [ ] **Step 3: Add the new resolver**

Add:

```python
def resolve_im_send_target(
    *,
    sender_identity: dict[str, Any],
    target_identity_id: Any,
    actor_reachability_checker: ActorReachabilityChecker | None = None,
) -> dict[str, Any]:
    try:
        sender = _identity_ref(sender_identity, "sender_identity")
    except ValueError as exc:
        return _im_payload_error(str(exc))

    identity_id = target_identity_id.strip() if isinstance(target_identity_id, str) and target_identity_id.strip() else ""
    if not identity_id:
        return _im_payload_error("target_identity_id is required")
    if identity_id == sender["id"]:
        return _im_payload_error("target_identity_id must not be the sender identity")

    try:
        target = _identity_ref(identity_id, "target_identity_id")
    except ValueError as exc:
        return _im_payload_error(str(exc))

    if target["type"] == "external":
        if not _external_profile_exists(target["id"]):
            return _im_target_error(f"external identity profile not found: {target['id']}")
        return {"ok": True, "target_identity": target}

    if target["type"] == "actor":
        if not _actor_profile_exists(target["id"]):
            return _im_target_error(f"actor identity profile not found: {target['id']}")
        if actor_reachability_checker is None:
            return _im_target_error("actor reachability checker is required for actor targets")
        try:
            reachability = actor_reachability_checker(target_identity_id=target["id"])
        except Exception as exc:
            return _im_target_error(str(exc))
        if not isinstance(reachability, dict):
            return _im_target_error("actor reachability response must be an object")
        if reachability.get("reachability_status") != "online":
            status = reachability.get("reachability_status")
            return _im_target_error(f"actor target is not online: {status}")
        return {"ok": True, "target_identity": target}

    return _im_payload_error("target_identity_id must be actor or external identity")
```

- [ ] **Step 4: Delete old send resolver**

Remove `identity_for_current_send_target(...)` entirely. Do not keep an alias or wrapper.

- [ ] **Step 5: Run focused service tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_im_product_core.py -q
```

Expected after implementation: service resolver tests pass; old tests that still refer to `identity_for_current_send_target` must be updated or removed, not kept.

## Task 3: Rebuild Actor Tool Send Path

**Files:**
- Modify: `scripts/env/tool_runtime/im_client.py`
- Modify: `tests/test_message_tool_im_client.py`
- Modify: `tests/test_im_external_reply_loop.py`

- [ ] **Step 1: Replace `_send_target_identity` implementation**

In `ActorImClient._send_target_identity`, replace actor row lookup with resolver call:

```python
    def _send_target_identity(self, value: Any) -> dict[str, Any]:
        return message_service.resolve_im_send_target(
            sender_identity=self._identity,
            target_identity_id=value,
            actor_reachability_checker=getattr(self._context.daemon, "check_reachability", None),
        )
```

- [ ] **Step 2: Keep `_online_actor_rows` only for `contacts`**

Do not call `_online_actor_rows` from `send`. It may remain only because `message.contacts` is still an actor discovery view.

- [ ] **Step 3: Update `_conversation_target_identity` so old resolver is gone**

Replace the actor branch with identity profile reads, not send reach:

```python
    def _conversation_target_identity(self, value: Any) -> dict[str, Any]:
        identity_id = value.strip() if isinstance(value, str) and value.strip() else ""
        if not identity_id:
            return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "target_identity_id is required"}}
        if identity_id == self._current_identity_payload().get("id"):
            return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "target_identity_id must not be the active actor identity"}}
        return message_service.identity_target_for_direct_conversation(identity_id)
```

Add `identity_target_for_direct_conversation(...)` in `messages.py` because direct-conversation target identity rules belong to Central IM service, not an actor runtime projection:

```python
def identity_target_for_direct_conversation(target_identity_id: Any) -> dict[str, Any]:
    identity_id = target_identity_id.strip() if isinstance(target_identity_id, str) and target_identity_id.strip() else ""
    if not identity_id:
        return _im_payload_error("target_identity_id is required")
    try:
        target = _identity_ref(identity_id, "target_identity_id")
    except ValueError as exc:
        return _im_payload_error(str(exc))
    if target["type"] == "actor" and not _actor_profile_exists(target["id"]):
        return _im_target_error(f"actor identity profile not found: {target['id']}")
    if target["type"] == "external" and not _external_profile_exists(target["id"]):
        return _im_target_error(f"external identity profile not found: {target['id']}")
    return {"ok": True, "identity": target}
```

- [ ] **Step 4: Run actor tool tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_message_tool_im_client.py tests/test_im_external_reply_loop.py -q
```

Expected: actor -> actor still writes and wakes; actor -> external writes and is visible to external read/ack; `list_online_actors` is not called by `message.send`.

## Task 4: Rebuild External Session and HTTP Projection Send Path

**Files:**
- Modify: `tools/launcher/external_im_session.py`
- Modify: `tools/launcher/im_http_router.py`
- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_external_im_session.py`
- Modify: `tests/test_im_http_router.py`
- Modify: `tests/test_web_management.py`
- Modify: `tests/test_external_im_projection_contract.py`

- [ ] **Step 1: Add reachability checker type to `ExternalImSession`**

In `tools/launcher/external_im_session.py`:

```python
ActorReachabilityChecker = Callable[..., dict[str, Any]]
```

Update constructor:

```python
    def __init__(
        self,
        *,
        actor_lister: ActorLister | None = None,
        actor_reachability_checker: ActorReachabilityChecker | None = None,
        actor_delivery_handler: ActorDeliveryHandler | None = None,
    ) -> None:
        self._actor_lister = actor_lister or (lambda _role_id: [])
        self._actor_reachability_checker = actor_reachability_checker
        self._actor_delivery_handler = actor_delivery_handler
```

- [ ] **Step 2: Replace `_actor_target_identity` with `_send_target_identity`**

Replace:

```python
    def _actor_target_identity(self, value: Any, *, field: str) -> dict[str, Any]:
        return message_service.identity_for_current_send_target(
            self._actor_lister(None),
            value,
            field=field,
        )
```

With:

```python
    def _send_target_identity(self, external_session: dict[str, Any], value: Any) -> dict[str, Any]:
        identity_response = _external_identity_from_session(external_session)
        if identity_response.get("ok") is not True:
            return identity_response
        resolved = message_service.resolve_im_send_target(
            sender_identity=identity_response["identity"],
            target_identity_id=value,
            actor_reachability_checker=self._actor_reachability_checker,
        )
        if resolved.get("ok") is not True:
            return resolved
        return {"ok": True, "identity": resolved["target_identity"]}
```

Update `send_message(...)` to call `_send_target_identity(external_session, target_identity_id)`.

- [ ] **Step 3: Update direct conversation target lookup**

`get_direct_conversation(...)` should not use send reach. Use `message_service.identity_target_for_direct_conversation(identity_id)` and reject missing profiles with `E_IM_TARGET`.

- [ ] **Step 4: Update router constructor**

In `tools/launcher/im_http_router.py`, add `actor_reachability_checker` and pass it into `ExternalImSession`:

```python
    def __init__(
        self,
        *,
        actor_lister: Callable[[str | None], list[dict[str, Any]]],
        actor_reachability_checker: Callable[..., dict[str, Any]] | None = None,
        actor_delivery_handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        im_session: Any | None = None,
        web_external_session_provider: WebExternalSessionProvider | None = None,
    ) -> None:
        self._session = im_session or external_im_session.ExternalImSession(
            actor_lister=actor_lister,
            actor_reachability_checker=actor_reachability_checker,
            actor_delivery_handler=actor_delivery_handler,
        )
```

- [ ] **Step 5: Update WebManagement wiring**

In `tools/launcher/web_management.py`, add:

```python
    def _check_im_actor_reachability(self, *, target_identity_id: str) -> dict[str, Any]:
        return daemon_client.check_reachability(target_identity_id=target_identity_id)
```

Pass it to both the session and router:

```python
        self._im_session = im_session or external_im_session.ExternalImSession(
            actor_lister=self._external_im_actor_rows,
            actor_reachability_checker=self._check_im_actor_reachability,
            actor_delivery_handler=self._wake_im_actor,
        )
```

```python
        self._im_router = im_http_router.ImHttpRouter(
            actor_lister=self._external_im_actor_rows,
            actor_reachability_checker=self._check_im_actor_reachability,
            actor_delivery_handler=self._wake_im_actor,
            im_session=self._im_session,
            web_external_session_provider=self.ensure_web_im_identity,
        )
```

- [ ] **Step 6: Run external/API tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_external_im_session.py \
  tests/test_im_http_router.py \
  tests/test_external_im_projection_contract.py \
  tests/test_im_web_management_projection.py \
  tests/test_web_management.py \
  -q
```

Expected: external -> actor still works, external -> missing/offline actor rejects through resolver, HTTP send uses reachability checker and not actor list.

## Task 5: Update Tool Semantics and Live Surfaces

**Files:**
- Modify: `scripts/env/tools/message/tool.py`
- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_env_tool_response_contract.py`

- [ ] **Step 1: Update message tool definition**

Required semantic changes:

- Tool description must say Central IM sends use identity target resolution, not actor contact projection.
- Capability boundary must say external identities can be direct send targets when an external profile exists.
- `message.contacts` description must say optional actor discovery view, not prerequisite for send.
- `message.send` description must say `target_identity_id` is resolved by IM target resolver.
- Reads should include `identity profiles` and `actor runtime reachability for actor targets`.

Example replacement fragments:

```python
description='Message tools cover optional actor discovery views, Central IM target-identity sends, exact processable inbound reads, replies, conversation context, and disposition marking.'
```

```python
capability_boundary='Messages use identity-addressed Central IM conversations, messages, events, and per-identity dispositions. Actor and external identities are valid Central IM direct targets when resolved by IM target rules.'
```

```python
description='List online actor identity suggestions for target discovery; this is a read-only view and does not decide message.send permission.'
```

```python
'description': 'Target identity id. Required only for a new target-identity message; IM target resolver decides whether the identity can receive this Central IM message. Omit it when replying with reply_to.',
```

- [ ] **Step 2: Update compact context affordance**

In `scripts/env/tools/context/_impl.py`, replace:

```python
"Use message.contacts to discover actor-runtime-present IM actor target identities."
```

With:

```python
"Use message.contacts only when you need a target discovery view; message.send resolves explicit actor or external target_identity_id values through IM target rules."
```

- [ ] **Step 3: Update schema/semantic tests**

Update tests so they require:

- `message.contacts` is optional discovery.
- `message.send` target resolver text includes actor/external target identity semantics.
- No test claims contacts are required before send.

- [ ] **Step 4: Run tool contract tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_context_binding_env_tool.py \
  -q
```

Expected: live tool surfaces teach resolver semantics, not contact-as-authority semantics.

## Task 6: Add Residue Checks

**Files:**
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add scoped scan for retired send resolver**

Add a repo consistency test over live source surfaces:

```python
    def test_im_target_resolver_rebuild_has_no_old_send_resolver_residue(self) -> None:
        targets = [
            "scripts/env/services/messages.py",
            "scripts/env/tool_runtime/im_client.py",
            "tools/launcher/external_im_session.py",
            "tools/launcher/im_http_router.py",
            "tools/launcher/web_management.py",
            "scripts/env/tools/message/tool.py",
            "scripts/env/tools/context/_impl.py",
            "tests/test_im_product_core.py",
            "tests/test_message_tool_im_client.py",
            "tests/test_external_im_session.py",
            "tests/test_im_http_router.py",
        ]
        patterns = [
            r"\bidentity_for_current_send_target\b",
            r"not a reachable target identity under current reach policy",
            r"external target_identity_id requires reply_to conversation routing context",
            r"message\.send.*must.*message\.contacts",
            r"contacts.*decide.*send",
        ]
        hits: list[str] = []
        for pattern in patterns:
            hits.extend(self._scan_targets(pattern, targets))
        self.assertEqual(hits, [], msg="\n".join(hits))
```

- [ ] **Step 2: Add scoped scan that send path does not list actors**

Use precise target source checks rather than banning `list_online_actors` globally, because contacts and track tools may still use actor list views.

```python
    def test_im_send_paths_do_not_use_actor_list_as_target_resolver(self) -> None:
        targets = [
            "scripts/env/tool_runtime/im_client.py",
            "tools/launcher/external_im_session.py",
        ]
        multiline_patterns = [
            r"def _send_target_identity[\s\S]{0,800}_online_actor_rows",
            r"def send_message[\s\S]{0,1000}_actor_lister",
            r"def send_message[\s\S]{0,1000}list_im_actor_contacts",
        ]
        hits: list[str] = []
        for pattern in multiline_patterns:
            hits.extend(self._scan_target_text(pattern, targets, flags=re.MULTILINE))
        self.assertEqual(hits, [], msg="\n".join(hits))
```

- [ ] **Step 3: Run consistency tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_repo_consistency.py -q
```

Expected: residue tests pass after all live surfaces are updated.

## Task 7: End-To-End Verification

**Files:**
- No new files required unless focused smoke helpers are needed.

- [ ] **Step 1: Run focused IM behavior suite**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_im_product_core.py \
  tests/test_message_tool_im_client.py \
  tests/test_external_im_session.py \
  tests/test_im_http_router.py \
  tests/test_im_external_reply_loop.py \
  tests/test_external_im_projection_contract.py \
  tests/test_im_web_management_projection.py \
  tests/test_web_management.py \
  -q
```

Expected:

- actor -> actor still writes, wakes actor, and preserves actor handling status.
- actor -> external writes a Central IM message and external session reads the visible event.
- external -> actor still writes and wakes actor.
- missing/offline actor targets reject before durable write.
- `message.contacts` still lists actor suggestions but is not send authority.

- [ ] **Step 2: Run tool/catalog/contract suite**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_repo_consistency.py \
  -q
```

Expected:

- live tool surfaces describe IM target resolver semantics.
- residue scans have no old send resolver hits.

- [ ] **Step 3: Run Web UI contract tests**

Run:

```bash
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
```

Expected: Web management IM route builders and polling semantics remain intact.

## Final Definition Of Done

- `resolve_im_send_target` exists and is the only authority for new-message target resolution.
- `identity_for_current_send_target` is deleted from live source and tests.
- `ActorImClient.send` does not call `_online_actor_rows` or `list_online_actors`.
- `ExternalImSession.send_message` does not call `_actor_lister` or `list_im_actor_contacts`.
- Actor targets require actor profile + `check_reachability == online`.
- External targets require external profile and are accepted as Central IM visible-event targets.
- `message.contacts` remains a read-only discovery view and does not appear as a send precondition.
- No central daemon registry changes add external identities.
- No external session fields become reach/contact fields.
- Focused behavior tests, tool contract tests, repo consistency tests, and Web UI JS tests pass.

## Known Non-Goals

- Do not implement iMessage/channel outbound push for actor -> external messages.
- Do not create a new `/api/im/contacts` endpoint.
- Do not migrate central daemon registry to a generic identity registry.
- Do not add compatibility aliases for the old resolver name.
- Do not rewrite unrelated track/comment/task messaging paths.
