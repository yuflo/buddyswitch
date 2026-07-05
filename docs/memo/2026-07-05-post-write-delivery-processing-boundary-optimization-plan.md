# Post-Write Delivery Processing Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the post-write IM boundary so sender projections stop owning target-side delivery details, Central IM write stays pure, actor delivery is one concrete post-write adapter, actor processing remains target-local Task Sys ingress, and external delivery remains connection event read/ack through the IM API surface.

**Architecture:** Keep the flow as `Ingress / Reach -> Central IM Write -> Delivery -> Target-side Processing`. This task replaces duplicated actor delivery payload construction in sender projections with one concrete post-write delivery helper; it does not open actor active send to `ext-*`, does not add a generic event bus, and does not make channel a parallel IM path. Channel remains a `/api/im/*` client/adapter.

**Tech Stack:** Python 3, `unittest`, `pytest`, `rg`, BuddySwitch runtime helpers, Central IM JSON state.

---

## Scope Lock

This task implements the boundary described by `docs/memo/2026-07-05-post-write-delivery-processing-boundary-brief.html`.

### In Scope

- Replace duplicated actor post-write delivery code in:
  - `scripts/env/tool_runtime/im_client.py`
  - `tools/launcher/external_im_session.py`
- Introduce one concrete IM post-write delivery helper under `scripts/env/services/`.
- Rename internal callback language from `actor_message_handler` to `actor_delivery_handler`.
- Keep `send_im_message` as pure Central IM write.
- Keep actor target delivery based on daemon-service capability:
  - `wake_im_actor`
  - `mailbox.local_trigger`
- Keep actor target processing based on:
  - `ImMessageCreatedHandler`
  - `task_sys_ingress.ingest_im_message`
- Keep external target delivery as visible connection events exposed through read/ack.
- Keep channel as `/api/im/*` client/adapter.
- Add behavior tests and live-surface residue gates for the new boundary.

### Out Of Scope

- Do not open `message.send(target_identity_id="ext-*")` from actor active send.
- Do not change current actor-only reach policy.
- Do not add external outbound channel routing.
- Do not add a delivery queue, workflow engine, event bus, or generic router framework.
- Do not rebuild Task Sys.
- Do not move daemon-service ownership of wake/mailbox into IM.
- Do not preserve `actor_message_handler` as an alias.

---

## Bitter Principles Applied

- **Residue cleanup:** A semantic replacement is incomplete while live surfaces still teach the old boundary. This plan includes scoped scans for stale post-write handling in sender projections.
- **Wrong-boundary narrowness:** The fix must be small at the correct boundary. The correct boundary is post-write delivery, not a new special case in reach, write, channel, or Task Sys.
- **Built-in product interface:** IM owns message semantics; HTTP/Web/channel are projections. Channel must not import Central IM internals or bypass `/api/im/*`.
- **End-to-end contract slice:** Component tests are not enough. The final verification keeps the user-visible loops intact: external -> actor, actor -> actor, actor reply -> external read/ack.
- **Test lifecycle:** This task should use fast unit/integration tests only. It should not introduce service-starting tests or long-lived worker tests.

---

## Current Code Audit

### Confirmed Stable Pieces

- `scripts/env/services/messages.py:252` `send_im_message(...)` writes conversation, message, state, and visible events.
- `send_im_message` no longer accepts `target_role_id` or `wake_actor`.
- `scripts/env/tool_runtime/daemon_client.py:404` `wake_im_actor(...)` accepts only target actor identity plus message refs, derives role from identity profile, checks daemon reachability, then submits `mailbox.local_trigger`.
- `tools/launcher/im_wake_handler.py:39` `ImMessageCreatedHandler` is the actor local processing boundary.
- `tools/launcher/task_sys_ingress.py:96` turns `im.message.created` into Task Sys ingress.
- `tools/launcher/imessage_channel.py:95` `BuddySwitchImApi` calls `/api/im/*`; channel is not a parallel message API.

### Confirmed Boundary Gap

Actor post-write delivery is still duplicated in sender-side projections:

- `scripts/env/tool_runtime/im_client.py:113` builds `im.message.created` payload in `_with_actor_handling_status`.
- `tools/launcher/external_im_session.py:148` builds the same payload in `_with_actor_handling_status`.

Those classes should adapt sender-side entrypoints. They should not each own target-side delivery payload rules.

### Current User-Visible Behavior To Preserve

- actor -> actor send writes IM and triggers actor delivery.
- external -> actor send writes IM and triggers actor delivery.
- actor reply to external writes IM and does not trigger actor delivery.
- external connection reads actor reply through `/api/im/events` and acknowledges it.
- actor active send to `ext-*` remains rejected by reach policy.

---

## Target Runtime Shape

```text
sender entrypoint
  -> reach
  -> send_im_message(...)
       writes conversation / message / state / events
       returns message_id / conversation_id / event_id / target_identity
  -> im_delivery.attach_post_write_delivery_status(...)
       actor target: call actor_delivery_handler with im.message.created refs
       external target: actor_handling_status = not_applicable
  -> target-side processing
       actor: mailbox.local_trigger -> ImMessageCreatedHandler -> Task Sys
       external: connection event read/ack by external client or channel adapter
```

Concrete rule:

```text
Central IM write records message facts.
Post-write delivery exposes the message to the target side.
Target-side processing decides what the target does with the message.
```

---

## Files To Change

- Create: `scripts/env/services/im_delivery.py`
- Modify: `scripts/env/tool_runtime/im_client.py`
- Modify: `tools/launcher/external_im_session.py`
- Modify: `tools/launcher/im_http_router.py`
- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_im_product_core.py`
- Modify: `tests/test_message_tool_im_client.py`
- Modify: `tests/test_external_im_session.py`
- Modify: `tests/test_im_http_router.py`
- Modify: `tests/test_im_web_management_projection.py`
- Modify: `tests/test_external_im_projection_contract.py`
- Modify: `tests/test_web_management.py`
- Modify: `tests/test_im_external_reply_loop.py`
- Modify: `tests/test_repo_consistency.py`

---

## Public Boundary Design

### New Concrete Helper

Create `scripts/env/services/im_delivery.py`.

The helper is concrete, not a framework:

```python
#!/usr/bin/env python3
"""Post-write delivery helpers for Central IM messages."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from env.domain.identity import IdentityRef

ActorDeliveryHandler = Callable[[dict[str, Any]], dict[str, Any]]


def attach_post_write_delivery_status(
    result: dict[str, Any],
    *,
    target_identity: dict[str, Any] | None = None,
    actor_delivery_handler: ActorDeliveryHandler | None = None,
) -> dict[str, Any]:
    if result.get("ok") is not True:
        return result
    target = _delivery_target(result, target_identity)
    if target is None or target.get("type") != "actor":
        result["actor_handling_status"] = "not_applicable"
        return result
    if actor_delivery_handler is None:
        result["actor_handling_status"] = "handling_failed"
        return result
    try:
        payload = _actor_message_created_payload(result, target)
    except ValueError:
        result["actor_handling_status"] = "handling_failed"
        return result
    handling = actor_delivery_handler(payload)
    if isinstance(handling, dict) and isinstance(handling.get("actor_handling_status"), str):
        result["actor_handling_status"] = handling["actor_handling_status"]
    else:
        result["actor_handling_status"] = "handling_failed"
    return result


def _delivery_target(result: dict[str, Any], explicit_target: dict[str, Any] | None) -> dict[str, str] | None:
    for candidate in (explicit_target, result.get("target_identity")):
        if isinstance(candidate, dict):
            try:
                return IdentityRef.from_payload(candidate).to_payload()
            except ValueError:
                continue
    return None


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _actor_message_created_payload(result: dict[str, Any], target: dict[str, str]) -> dict[str, Any]:
    message = result.get("message")
    if not isinstance(message, dict):
        raise ValueError("post-write IM delivery requires message refs")
    return {
        "type": "im.message.created",
        "target_identity_id": target["id"],
        "message_id": _required_text(message.get("id"), "message.id"),
        "conversation_id": _required_text(message.get("conversation_id"), "message.conversation_id"),
        "event_id": _required_text(result.get("event_id"), "event_id"),
    }
```

The helper must not import daemon, Task Sys, channel, HTTP, Web, or message repos.

---

## Task 1: Add Failing Tests For The Concrete Delivery Helper

**Files:**
- Create: `tests/test_im_delivery.py`
- Create: `scripts/env/services/im_delivery.py`

- [ ] **Step 1: Add a failing actor delivery payload test**

Create `tests/test_im_delivery.py`:

```python
#!/usr/bin/env python3

from __future__ import annotations

import unittest
from typing import Any

from env.services import im_delivery


class ImDeliveryTests(unittest.TestCase):
    def test_actor_target_delivery_uses_only_identity_and_message_refs(self) -> None:
        calls: list[dict[str, Any]] = []
        result = {
            "ok": True,
            "message": {"id": "msg-1", "conversation_id": "conv-1", "reply_to": None},
            "target_identity": {"id": "act-target", "type": "actor"},
            "event_id": "imev-1",
            "delivery_status": "accepted",
        }

        delivered = im_delivery.attach_post_write_delivery_status(
            result,
            actor_delivery_handler=lambda payload: calls.append(dict(payload))
            or {"actor_handling_status": "submitted"},
        )

        self.assertIs(delivered, result)
        self.assertEqual(delivered["actor_handling_status"], "submitted")
        self.assertEqual(
            calls,
            [
                {
                    "type": "im.message.created",
                    "target_identity_id": "act-target",
                    "message_id": "msg-1",
                    "conversation_id": "conv-1",
                    "event_id": "imev-1",
                }
            ],
        )
        self.assertNotIn("target_role_id", calls[0])
        self.assertNotIn("content", calls[0])
        self.assertNotIn("sender_identity", calls[0])
```

- [ ] **Step 2: Add a failing external target test**

Append:

```python
    def test_external_target_does_not_call_actor_delivery(self) -> None:
        calls: list[dict[str, Any]] = []
        result = {
            "ok": True,
            "message": {"id": "msg-2", "conversation_id": "conv-2", "reply_to": "msg-1"},
            "target_identity": {"id": "ext-target", "type": "external"},
            "event_id": "imev-2",
            "delivery_status": "accepted",
        }

        delivered = im_delivery.attach_post_write_delivery_status(
            result,
            actor_delivery_handler=lambda payload: calls.append(dict(payload))
            or {"actor_handling_status": "submitted"},
        )

        self.assertEqual(delivered["actor_handling_status"], "not_applicable")
        self.assertEqual(calls, [])
```

- [ ] **Step 3: Add a malformed write result test**

Append:

```python
    def test_actor_target_missing_message_refs_fails_without_delivery_call(self) -> None:
        calls: list[dict[str, Any]] = []
        result = {
            "ok": True,
            "target_identity": {"id": "act-target", "type": "actor"},
            "event_id": "imev-3",
        }

        delivered = im_delivery.attach_post_write_delivery_status(
            result,
            actor_delivery_handler=lambda payload: calls.append(dict(payload))
            or {"actor_handling_status": "submitted"},
        )

        self.assertEqual(delivered["actor_handling_status"], "handling_failed")
        self.assertEqual(calls, [])
```

Close the file with:

```python

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run the new tests and confirm failure**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_im_delivery.py -q
```

Expected before implementation: FAIL because `env.services.im_delivery` does not exist.

- [ ] **Step 5: Create the helper implementation**

Create `scripts/env/services/im_delivery.py` using the helper shown in "Public Boundary Design". Wrap `_actor_message_created_payload(...)` in `try/except ValueError` inside `attach_post_write_delivery_status` so malformed write results return `handling_failed` and do not call the actor delivery handler.

- [ ] **Step 6: Run the new tests and confirm pass**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_im_delivery.py -q
```

Expected after implementation:

```text
3 passed
```

---

## Task 2: Replace ActorImClient's Local Delivery Payload Builder

**Files:**
- Modify: `scripts/env/tool_runtime/im_client.py`
- Modify: `tests/test_message_tool_im_client.py`

- [ ] **Step 1: Update imports**

In `scripts/env/tool_runtime/im_client.py`, change:

```python
from env.services import messages as message_service
```

to:

```python
from env.services import im_delivery
from env.services import messages as message_service
```

- [ ] **Step 2: Replace `_with_actor_handling_status` usage**

Replace:

```python
        return self._with_actor_handling_status(
            result,
            self._result_target_identity(result, target if isinstance(target, dict) else None),
        )
```

with:

```python
        return im_delivery.attach_post_write_delivery_status(
            result,
            target_identity=self._result_target_identity(result, target if isinstance(target, dict) else None),
            actor_delivery_handler=getattr(self._context.daemon, "wake_im_actor", None),
        )
```

- [ ] **Step 3: Delete the local delivery method**

Remove `ActorImClient._with_actor_handling_status`.

Keep `_result_target_identity` because it chooses the final target for explicit and `reply_to` sends.

- [ ] **Step 4: Run the actor client tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_message_tool_im_client.py -q
```

Expected:

```text
passed
```

The existing tests must still prove:

- actor -> actor sends call actor delivery after write;
- actor replies to external return `actor_handling_status="not_applicable"`;
- actor replies to actor use the resolved final target from `send_im_message`;
- actor active send to `ext-*` remains rejected by reach policy.

---

## Task 3: Replace ExternalImSession's Local Delivery Payload Builder

**Files:**
- Modify: `tools/launcher/external_im_session.py`
- Modify: `tools/launcher/im_http_router.py`
- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_external_im_session.py`
- Modify: `tests/test_im_http_router.py`
- Modify: `tests/test_im_web_management_projection.py`
- Modify: `tests/test_external_im_projection_contract.py`
- Modify: `tests/test_web_management.py`
- Modify: `tests/test_im_external_reply_loop.py`

- [ ] **Step 1: Rename callback type and constructor parameter**

In `tools/launcher/external_im_session.py`, replace:

```python
ActorMessageHandler = Callable[[dict[str, Any]], dict[str, Any]]
```

with:

```python
ActorDeliveryHandler = Callable[[dict[str, Any]], dict[str, Any]]
```

Replace constructor parameter and attribute:

```python
actor_message_handler: ActorMessageHandler | None = None
self._actor_message_handler = actor_message_handler
```

with:

```python
actor_delivery_handler: ActorDeliveryHandler | None = None
self._actor_delivery_handler = actor_delivery_handler
```

No `actor_message_handler` alias should remain.

- [ ] **Step 2: Import the delivery helper**

In `tools/launcher/external_im_session.py`, change:

```python
from env.services import messages as message_service
```

to:

```python
from env.services import im_delivery
from env.services import messages as message_service
```

- [ ] **Step 3: Replace local post-write handling**

Replace:

```python
        return self._with_actor_handling_status(result, handling_target)
```

with:

```python
        return im_delivery.attach_post_write_delivery_status(
            result,
            target_identity=handling_target,
            actor_delivery_handler=self._actor_delivery_handler,
        )
```

Delete `ExternalImSession._with_actor_handling_status`.

- [ ] **Step 4: Rename the router parameter**

In `tools/launcher/im_http_router.py`, replace constructor parameter:

```python
actor_message_handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None
```

with:

```python
actor_delivery_handler: Callable[[dict[str, Any]], dict[str, Any]] | None = None
```

Replace session construction:

```python
actor_message_handler=actor_message_handler,
```

with:

```python
actor_delivery_handler=actor_delivery_handler,
```

- [ ] **Step 5: Rename Web Management wiring**

In `tools/launcher/web_management.py`, replace:

```python
actor_message_handler=self._wake_im_actor,
```

with:

```python
actor_delivery_handler=self._wake_im_actor,
```

This preserves daemon-service delivery capability while removing message-processing terminology from sender ingress.

- [ ] **Step 6: Update tests and fakes**

Replace all constructor uses of:

```python
actor_message_handler=
```

with:

```python
actor_delivery_handler=
```

Targets:

- `tests/test_external_im_session.py`
- `tests/test_im_http_router.py`
- `tests/test_web_management.py`
- `tests/test_im_external_reply_loop.py`

Update any fake call log label from `actor_message_handler` to `actor_delivery_handler` only where the label is testing constructor semantics.

- [ ] **Step 7: Run external/session/http/web tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_external_im_session.py \
  tests/test_im_http_router.py \
  tests/test_im_web_management_projection.py \
  tests/test_external_im_projection_contract.py \
  tests/test_web_management.py \
  tests/test_im_external_reply_loop.py \
  -q
```

Expected:

```text
passed
```

---

## Task 4: Lock External Delivery And Channel Boundaries

**Files:**
- Modify: `tests/test_external_im_session.py`
- Modify: `tests/test_imessage_channel.py`
- Modify: `tests/test_im_web_management_projection.py`

- [ ] **Step 1: Add an external delivery naming test**

In `tests/test_external_im_session.py`, add:

```python
    def test_external_delivery_is_connection_read_ack_not_actor_processing(self) -> None:
        actor_identity = self._actor_identity()
        session = self._session([{**actor_identity, "status": "online"}])
        _key, connection, identity = self._connection(session)
        sent = session.send_message(
            connection=connection,
            target_identity_id=actor_identity["identity_id"],
            content="ping",
            reply_to=None,
        )
        actor_reply = message_service.send_im_message(
            sender_identity=actor_identity,
            to=identity,
            content="pong",
            reply_to=sent["message"]["id"],
        )

        events = session.read_events(connection=connection, limit=50, wait_ms=0)
        ack = session.ack_event(connection=connection, event_id=actor_reply["event_id"])

        self.assertEqual([event["message_id"] for event in events["events"]], [actor_reply["message"]["id"]])
        self.assertTrue(ack.get("ok"), msg=ack)
        self.assertNotIn("actor_handling_status", events)
        self.assertNotIn("task_sys", str(events))
```

- [ ] **Step 2: Keep channel as IM API adapter**

`tests/test_imessage_channel.py` already checks `imessage_channel.py` does not import Central IM internals. Keep and extend that residue test if implementation introduces any new delivery imports.

Forbidden in `tools/launcher/imessage_channel.py`:

```text
env.services.messages
env.services.im_delivery
env.repos.messages
send_im_message
read_external_connection_events
ack_external_connection_event
```

- [ ] **Step 3: Run channel/web projection tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_imessage_channel.py \
  tests/test_im_web_management_projection.py \
  tests/test_external_im_projection_contract.py \
  -q
```

Expected:

```text
passed
```

---

## Task 5: Add Live-Surface Residue Gates For Post-Write Boundary

**Files:**
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add a residue test for sender projections**

Add a test:

```python
    def test_im_post_write_delivery_is_not_reimplemented_in_sender_projections(self) -> None:
        targets = [
            "scripts/env/tool_runtime/im_client.py",
            "tools/launcher/external_im_session.py",
            "tools/launcher/im_http_router.py",
            "tools/launcher/web_management.py",
        ]
        forbidden = [
            r"def _with_actor_handling_status",
            r"actor_message_handler",
            r"[\"']type[\"']\s*:\s*[\"']im\.message\.created[\"']",
        ]
        hits: list[str] = []
        for pattern in forbidden:
            hits.extend(self._scan_targets(pattern, targets))
        self.assertEqual(hits, [], msg="\\n".join(hits))
```

Allowed current locations for `im.message.created` payload semantics are:

- `scripts/env/services/im_delivery.py`
- `scripts/env/tool_runtime/daemon_client.py`
- `tools/launcher/im_wake_handler.py`
- `tools/launcher/task_sys_ingress.py`
- focused tests proving the boundary

- [ ] **Step 2: Add a write-layer boundary residue test**

Add:

```python
    def test_central_im_write_does_not_import_delivery_or_processing(self) -> None:
        source = (ROOT / "scripts" / "env" / "services" / "messages.py").read_text(encoding="utf-8")
        forbidden = (
            "im_delivery",
            "wake_im_actor",
            "mailbox.local_trigger",
            "task_sys_ingress",
            "ImMessageCreatedHandler",
            "imessage_channel",
        )
        hits = [term for term in forbidden if term in source]
        self.assertEqual(hits, [])
```

- [ ] **Step 3: Add an IM delivery helper boundary residue test**

Add:

```python
    def test_im_delivery_helper_does_not_import_processing_or_channel(self) -> None:
        source = (ROOT / "scripts" / "env" / "services" / "im_delivery.py").read_text(encoding="utf-8")
        forbidden = (
            "task_sys_ingress",
            "ImMessageCreatedHandler",
            "imessage_channel",
            "web_management",
            "im_http_router",
            "env.repos.messages",
            "send_im_message",
        )
        hits = [term for term in forbidden if term in source]
        self.assertEqual(hits, [])
```

- [ ] **Step 4: Run the residue tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_im_post_write_delivery_is_not_reimplemented_in_sender_projections \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_central_im_write_does_not_import_delivery_or_processing \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_im_delivery_helper_does_not_import_processing_or_channel \
  -q
```

Expected:

```text
passed
```

---

## Task 6: End-To-End Contract Verification

**Files:**
- Modify only if a focused behavior test fails for a real product issue.

- [ ] **Step 1: Run the focused IM contract suite**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_im_delivery.py \
  tests/test_im_product_core.py \
  tests/test_message_tool_im_client.py \
  tests/test_external_im_session.py \
  tests/test_im_http_router.py \
  tests/test_external_im_projection_contract.py \
  tests/test_im_web_management_projection.py \
  tests/test_im_external_reply_loop.py \
  tests/test_im_wake_handler.py \
  tests/test_imessage_channel.py \
  -q
```

Expected:

```text
passed
```

- [ ] **Step 2: Run repo consistency**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_repo_consistency.py -q
```

Expected:

```text
passed
```

- [ ] **Step 3: Run exact no-hit scans**

Run:

```bash
rg -n "_with_actor_handling_status|actor_message_handler" \
  scripts/env/tool_runtime/im_client.py \
  tools/launcher/external_im_session.py \
  tools/launcher/im_http_router.py \
  tools/launcher/web_management.py \
  tests/test_external_im_session.py \
  tests/test_im_http_router.py \
  tests/test_web_management.py \
  tests/test_im_external_reply_loop.py
```

Expected: no output.

Run:

```bash
rg -n "env\\.services\\.(messages|im_delivery)|send_im_message|read_external_connection_events|ack_external_connection_event" \
  tools/launcher/imessage_channel.py
```

Expected: no output.

Run:

```bash
rg -n "im_delivery|wake_im_actor|mailbox\\.local_trigger|task_sys_ingress|ImMessageCreatedHandler|imessage_channel" \
  scripts/env/services/messages.py
```

Expected: no output.

- [ ] **Step 4: Preserve actor/ext-user communication stage**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_message_tool_im_client.py::MessageToolImClientTests::test_actor_send_external_target_rejection_is_reach_policy_not_actor_signature \
  tests/test_message_tool_im_client.py::MessageToolImClientTests::test_actor_can_reply_to_external_origin_message_with_reply_to_only \
  tests/test_external_im_session.py::ExternalImSessionTests::test_session_create_auth_send_event_conversation_and_disposition_flow \
  -q
```

Expected:

```text
passed
```

This proves the task did not silently open actor active send to external, while preserving external -> actor and actor reply -> external loops.

---

## Acceptance Criteria

- `send_im_message remains pure write`: it does not import or call delivery/processing code.
- `ActorImClient` and `ExternalImSession` no longer define `_with_actor_handling_status`.
- No live sender projection contains `actor_message_handler`.
- Actor delivery payload construction exists in one concrete helper only.
- Actor delivery payload includes only:
  - `type`
  - `target_identity_id`
  - `message_id`
  - `conversation_id`
  - `event_id`
- Actor processing still enters `ImMessageCreatedHandler -> task_sys_ingress`.
- External delivery still uses connection event read/ack.
- Channel still accesses IM through `/api/im/*`.
- actor active send to `ext-*` remains blocked: reach policy is not opened in this task.
- Focused IM suite and repo consistency pass.
- Exact no-hit scans pass.

---

## Self-Review Checklist

- Spec coverage: the plan covers delivery, processing, external ingress distinction, channel via im-api, and actor/ext-user scope.
- No dual compatibility: `actor_message_handler` is renamed and removed, not aliased.
- No speculative abstraction: one concrete helper replaces duplicate sender projection logic; no queue, event bus, generic router, or channel framework.
- Boundary correctness: write stays write, delivery does not call Task Sys, processing stays target-local.
- End-to-end proof: focused tests preserve external -> actor, actor -> actor, and actor reply -> external read/ack.
