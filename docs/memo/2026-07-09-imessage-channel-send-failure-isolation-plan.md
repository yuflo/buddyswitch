# iMessage Channel Send Failure Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the iMessage channel response path so `/actors`, numeric selection, and actor-required prompts are delivered through a channel-local retryable delivery state, while inbound watching keeps running and actor selection state is activated only after the relevant iMessage response is confirmed sent.

**Architecture:** Keep the change inside `tools/launcher/imessage_channel.py` and `tests/test_imessage_channel.py`. The iMessage channel owns external contact route state, actor selection UX state, and iMessage control response delivery; IM core and Web remain projections over `/api/im/*` and do not learn `/actors`, selected actor, or retry semantics. This is a forward rebuild of the iMessage channel state contract, not a provider migration or compatibility wrapper.

**Tech Stack:** Python stdlib, file-backed iMessage channel state JSON, `imsg` command adapter, existing worker threads, `unittest`, `pytest`, scoped `rg` residue scans.

---

## 1. Task Target

The current user-visible failure is:

```text
iMessage user sends /actors
-> BuddySwitch computes actor choices
-> BuddySwitch saves pending_actor_choices before sending the actor list
-> imsg / AppleScript send fails or times out
-> inbound worker exits
-> later /actors messages are not processed
-> state may contain pending choices for a list the user never received
```

The target behavior is:

```text
iMessage user sends /actors
-> channel creates a pending control delivery for the actor list
-> outbound channel delivery loop sends it with finite retry
-> only after confirmed send, pending_actor_choices becomes active
-> if delivery fails after finite retry, failure is explicit in channel state and logs
-> inbound worker keeps processing later iMessage rows
-> user can send /actors again, replacing the failed control delivery with a new current one
```

This is a channel reliability upgrade. It is not a Central IM product rewrite, Web UI feature, task system change, actor runtime change, or `imsg` replacement.

## 2. Bitter Principles Applied

Read and apply these files before implementation:

- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`
- `docs/bitter/2026-07-07-guarded-residue-boundary-principles.md`

Direct implications:

- Fix the owning layer. The owning layer is `tools/launcher/imessage_channel.py`.
- Do not teach `/actors` or selected-actor state to Web, IM core, actor tools, external session core, or Task Sys.
- Do not add provider abstraction, BlueBubbles, mautrix, `platform-imessage`, Matrix, or a parallel delivery stack in this change.
- Do not keep the old synchronous control-send path beside a new queued path.
- Do not accept retired state schemas in active code. Bump the channel state schema and require reset for old local state.
- Prove behavior and live surface cleanup. Unit behavior tests alone are not enough.
- Prove the real loop: inbound `/actors` can fail to send once and a later `/actors` can still be processed by the same worker.

## 3. Current Code Audit

### Current owner

File: `tools/launcher/imessage_channel.py`

The iMessage channel currently owns:

- `SCHEMA_VERSION = 4`
- contact route state
- external session binding
- `/actors`
- numeric actor choice
- selected actor TTL
- pending choice TTL
- inbound dedupe
- outbound actor-to-iMessage event polling
- `CommandImsgClient.send(...)`
- `ImessageChannelWorker`

This remains the correct owner. Do not move these semantics out.

### Failure source

Current `/actors` path:

```text
ImessageChannelController.handle_inbound_message(row)
-> _handle_actors(...)
-> api.list_actors(...)
-> _set_pending_choices(contact, choices, now=now)
-> state_store.save(state)
-> imsg.send(route=route, text=actor_list)
```

The wrong ordering is `save pending choices` before `imsg.send`.

Current worker path:

```text
ImessageChannelWorker.run_forever()
-> controller.imsg.status()
-> for row in controller.imsg.watch_messages():
     controller.handle_inbound_message(row)

_run_with_error_capture(...)
-> catches any exception only at thread top
-> prints "iMessage channel inbound worker stopped: ..."
-> thread exits
```

The wrong failure boundary is that one row-level send failure can stop the whole inbound loop.

### Current tests

File: `tests/test_imessage_channel.py`

Current coverage already proves:

- schema v4 state starts empty;
- first sender creates and reuses an external session;
- contacts keep external session, external identity, route, pending choices, active actor, dedupe, and outbound sent ids isolated;
- `/actors` lists reachable actors and writes pending choices with TTL;
- numeric choice sets active actor TTL and clears pending choices;
- expired active actor prompts and clears active state;
- expired pending choice is not used;
- successful ordinary inbound message refreshes active actor TTL;
- outbound actor reply uses contact route, not `reply_to`;
- outbound event send failure is not acked;
- ack failure does not duplicate iMessage send after event id is marked sent;
- inbound and outbound worker loops are split;
- Web and core do not contain iMessage selected-actor semantics.

Missing coverage for this incident:

- `/actors` send failure must not activate pending choices.
- `/actors` send failure must be recorded as a failed channel control delivery after finite retry.
- inbound worker must keep running after `/actors` response delivery fails.
- a later `/actors` must supersede the failed control delivery and be deliverable.
- numeric selection must not activate active actor until the selection confirmation is sent.
- no-actor prompt delivery failure must not stop inbound processing.
- outbound worker tick failures must not kill the outbound worker.
- source must not contain direct `self.imsg.send(...)` inside `_handle_actors`, `_handle_numeric_choice`, or `_handle_ordinary_message`.

## 4. System Boundary

### In scope

- `tools/launcher/imessage_channel.py`
- `tests/test_imessage_channel.py`
- Narrow residue tests that scan live iMessage channel source and selected live surfaces
- Existing `CommandImsgClient.send(...)` send-status verification
- Existing `ImessageChannelWorker` lifecycle

### Out of scope

- `platform-imessage` integration
- `imsg` replacement
- generic provider framework
- `scripts/env/services/messages.py`
- `scripts/env/repos/messages.py`
- `scripts/env/tool_runtime/*`
- `tools/launcher/im_http_router.py`
- Web UI state or routes
- Task Sys
- actor model config
- direct edits under `buddyswitch/objects/**` or old private runtime paths

If an implementation step appears to require an out-of-scope file, stop and re-check the boundary. The expected design pressure should be resolved inside the iMessage channel module.

## 5. Target State Contract

Bump iMessage channel state from schema v4 to schema v5.

Do not load schema v4 as current state. This is local adapter state and can be reset. Carrying v4 forward would preserve the possibility of already-active `pending_actor_choices` that were written before the user actually received the actor list.

Target contact shape:

```json
{
  "external_session_key": "imsk-example",
  "external_identity_id": "ext-example",
  "route": {
    "chat_id": "3213",
    "sender": "user@example.com"
  },
  "active_identity_id": "act-pm-example",
  "active_identity_expires_at": "2026-07-09T12:30:00Z",
  "pending_actor_choices": {
    "1": "act-market-example",
    "2": "act-pm-example"
  },
  "pending_actor_choices_expires_at": "2026-07-09T12:05:00Z",
  "control_delivery": {
    "id": "ctrl-guid-abc-actors",
    "kind": "actor_choices",
    "status": "pending",
    "route": {
      "chat_id": "3213",
      "sender": "user@example.com"
    },
    "text": "[1] market act-market-example\n[2] pm act-pm-example",
    "attempts": 0,
    "created_at": "2026-07-09T12:00:00Z",
    "updated_at": "2026-07-09T12:00:00Z",
    "next_attempt_at": "2026-07-09T12:00:00Z",
    "last_error": "",
    "effect": {
      "type": "set_pending_actor_choices",
      "choices": {
        "1": "act-market-example",
        "2": "act-pm-example"
      }
    }
  },
  "seen_inbound_keys": [
    "guid:inbound-example"
  ],
  "sent_outbound_event_ids": [
    "imev-outbound-example"
  ]
}
```

Rules:

- `control_delivery` is a single current delivery per contact.
- New `/actors`, numeric selection, or no-actor prompt supersedes any previous `control_delivery`.
- `pending_actor_choices` is set only by a successful `control_delivery` whose effect is `set_pending_actor_choices`.
- `active_identity_id` is set only by a successful `control_delivery` whose effect is `select_active_actor`.
- A failed `control_delivery` remains visible until a newer control message supersedes it.
- Successful control delivery removes `control_delivery` after applying its effect.
- Actor outbound replies still use existing event polling and `sent_outbound_event_ids`; they do not use `control_delivery`.

## 6. Target Control Delivery Kinds

Use these exact kinds:

```python
CONTROL_KIND_ACTOR_CHOICES = "actor_choices"
CONTROL_KIND_ACTOR_SELECTED = "actor_selected"
CONTROL_KIND_NEEDS_ACTOR_PROMPT = "needs_actor_prompt"
```

Use these exact statuses:

```python
CONTROL_STATUS_PENDING = "pending"
CONTROL_STATUS_RETRY_WAIT = "retry_wait"
CONTROL_STATUS_FAILED = "failed"
```

Use these retry constants:

```python
CONTROL_DELIVERY_MAX_ATTEMPTS = 3
CONTROL_DELIVERY_RETRY_SECONDS = 2
```

Retry means:

```text
attempt 1 fails -> status retry_wait, attempts 1, next_attempt_at now + 2s
attempt 2 fails -> status retry_wait, attempts 2, next_attempt_at now + 2s
attempt 3 fails -> status failed, attempts 3, no automatic retry until superseded
```

Do not add infinite retry. Do not fabricate success. Do not send an iMessage fallback that depends on the same failing iMessage automation surface.

## 7. Target Runtime Flow

### `/actors`

```text
handle_inbound_message(/actors)
-> bind external session and route
-> list actors through /api/im/actors
-> build actor list text and choices
-> write contact.control_delivery(kind=actor_choices, effect=set_pending_actor_choices)
-> save state
-> return queued status

run_outbound_forever tick
-> poll_control_delivery_once()
-> imsg.send(actor list)
-> on success, set pending_actor_choices with expiry from send success time
-> remove control_delivery
-> save state
```

### Numeric actor selection

```text
handle_inbound_message("1")
-> only reads currently active pending_actor_choices
-> selected actor becomes a control delivery effect
-> active_identity_id is not set yet
-> save state

run_outbound_forever tick
-> imsg.send(selected actor confirmation)
-> on success, set active_identity_id with expiry from send success time
-> clear pending_actor_choices
-> remove control_delivery
-> save state
```

### Ordinary message without active actor

```text
handle_inbound_message("hello")
-> no active actor
-> write control_delivery(kind=needs_actor_prompt)
-> save state
-> return needs_actor

run_outbound_forever tick
-> imsg.send("Send /actors to choose an actor.")
-> on success, remove control_delivery
-> save state
```

### Ordinary message with active actor

Keep the existing direct IM API send path:

```text
handle_inbound_message("hello")
-> active actor is valid
-> api.send_message(...)
-> on success, mark inbound key seen
-> refresh active actor idle TTL
-> save state
```

This path does not send an iMessage response and does not use `control_delivery`.

### Actor outbound reply

Keep the existing event path:

```text
poll_outbound_once()
-> read /api/im/events
-> fetch message
-> imsg.send("[Message From actor]\n\ncontent")
-> mark event id sent
-> save state
-> ack event
```

If `imsg.send(...)` fails here, the event remains unacked and the worker catches the tick error. The next outbound loop may retry through the same existing event path.

## 8. Worker Failure Boundary

Change worker behavior from thread-level-only error handling to row/tick isolation:

```text
run_forever()
-> status() still happens once before watching
-> for row in watch_messages():
     try handle_inbound_message(row)
     except Exception:
       log "iMessage channel inbound message failed: ..."
       continue

run_outbound_forever()
-> while not stopped:
     try poll_control_delivery_once()
     except Exception:
       log "iMessage channel control delivery failed: ..."
     try poll_outbound_once(...)
     except Exception:
       log "iMessage channel outbound poll failed: ..."
     wait
```

Keep `_run_with_error_capture(...)` as the final defensive guard for startup or generator-level failures. It should no longer be the normal path for a single send failure.

## 9. Implementation Tasks

### Task 1: Add regression tests for `/actors` delivery ordering

**Files:**

- Modify: `tests/test_imessage_channel.py`

- [ ] **Step 1: Add a fake imsg that fails then recovers**

Add this helper near `_FailingImsg`:

```python
class _RecoveringImsg(_FakeImsg):
    def __init__(self, *, failures: int) -> None:
        super().__init__()
        self.failures = failures

    def send(self, *, route: dict[str, Any], text: str) -> None:
        self.sent.append({"route": dict(route), "text": text})
        if self.failures > 0:
            self.failures -= 1
            raise imessage_channel.ChannelError("AppleEvent timed out -1712")
```

- [ ] **Step 2: Add failing test for `/actors` not activating choices before delivery succeeds**

Add this test to `ImessageChannelTests`:

```python
def test_actors_choices_activate_only_after_actor_list_delivery_succeeds(self) -> None:
    now = _fixed_now()
    with tempfile.TemporaryDirectory() as temp_root:
        imsg = _RecoveringImsg(failures=1)
        controller, _api, _imsg = _controller(Path(temp_root), imsg=imsg, now_fn=lambda: now)

        result = controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
        state_after_inbound = controller.state_store.load()
        first_delivery = controller.poll_control_delivery_once()
        state_after_failure = controller.state_store.load()
        imsg.failures = 0
        second_delivery = controller.poll_control_delivery_once()
        state_after_success = controller.state_store.load()

    contact_after_inbound = state_after_inbound["contacts"]["sender:user-a@example.com"]
    contact_after_failure = state_after_failure["contacts"]["sender:user-a@example.com"]
    contact_after_success = state_after_success["contacts"]["sender:user-a@example.com"]
    self.assertEqual(result["status"], "actors_list_queued")
    self.assertEqual(contact_after_inbound["pending_actor_choices"], {})
    self.assertEqual(contact_after_failure["pending_actor_choices"], {})
    self.assertEqual(first_delivery["sent"], 0)
    self.assertEqual(first_delivery["failed"], 0)
    self.assertEqual(first_delivery["retrying"], 1)
    self.assertEqual(second_delivery["sent"], 1)
    self.assertEqual(second_delivery["failed"], 0)
    self.assertEqual(contact_after_success["pending_actor_choices"], {"1": "act-market-demo"})
    self.assertNotIn("control_delivery", contact_after_success)
```

- [ ] **Step 3: Run the new test and verify it fails**

Run:

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelTests::test_actors_choices_activate_only_after_actor_list_delivery_succeeds -q
```

Expected before implementation:

```text
FAILED
AttributeError: 'ImessageChannelController' object has no attribute 'poll_control_delivery_once'
```

### Task 2: Add regression tests for worker survival

**Files:**

- Modify: `tests/test_imessage_channel.py`

- [ ] **Step 1: Add worker test for failed `/actors` response followed by successful `/actors`**

Add this test to `ImessageChannelTests`:

```python
def test_worker_keeps_processing_after_actors_response_send_failure(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        api = _FakeBuddySwitchImApi()
        imsg = _QueueImsg()
        original_send = imsg.send
        failures = {"remaining": 1}

        def fail_first_send(*, route: dict[str, Any], text: str) -> None:
            imsg.sent.append({"route": dict(route), "text": text})
            if failures["remaining"] > 0:
                failures["remaining"] -= 1
                raise imessage_channel.ChannelError("AppleEvent timed out -1712")

        imsg.send = fail_first_send  # type: ignore[method-assign]
        controller, _api, _imsg = _controller(Path(temp_root), api=api, imsg=imsg)
        worker = imessage_channel.ImessageChannelWorker(controller, reply_wait_ms=1)
        worker.start()
        self.addCleanup(worker.stop)

        self.assertTrue(imsg.watch_started.wait(timeout=1), "inbound watch did not start")
        imsg.push(_row(text="/actors", guid="guid-actors-1", chat_id="9"))
        self.assertTrue(
            _wait_until(lambda: len(imsg.sent) >= 1, timeout=1),
            "first actor list send was not attempted",
        )
        imsg.send = original_send  # type: ignore[method-assign]
        imsg.push(_row(text="/actors", guid="guid-actors-2", chat_id="9"))
        self.assertTrue(
            _wait_until(lambda: any(row["text"] == "[1] market act-market-demo" for row in imsg.sent), timeout=1),
            "second actor list was not delivered after first send failure",
        )
        worker.stop()

    self.assertTrue(imsg.stopped)
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelTests::test_worker_keeps_processing_after_actors_response_send_failure -q
```

Expected before implementation:

```text
FAILED
```

The failure is expected because the current worker lets `handle_inbound_message(...)` exceptions stop the inbound thread.

### Task 3: Add regression tests for selection activation after confirmation delivery

**Files:**

- Modify: `tests/test_imessage_channel.py`

- [ ] **Step 1: Add failing test for numeric selection not activating before confirmation send**

Add this test to `ImessageChannelTests`:

```python
def test_numeric_selection_activates_actor_only_after_confirmation_delivery(self) -> None:
    now = _fixed_now()
    with tempfile.TemporaryDirectory() as temp_root:
        imsg = _RecoveringImsg(failures=0)
        controller, _api, _imsg = _controller(Path(temp_root), imsg=imsg, now_fn=lambda: now)
        controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
        controller.poll_control_delivery_once()

        imsg.failures = 1
        selected = controller.handle_inbound_message(_row(text="1", guid="guid-select"))
        state_after_inbound = controller.state_store.load()
        first_delivery = controller.poll_control_delivery_once()
        state_after_failure = controller.state_store.load()
        imsg.failures = 0
        second_delivery = controller.poll_control_delivery_once()
        state_after_success = controller.state_store.load()

    contact_after_inbound = state_after_inbound["contacts"]["sender:user-a@example.com"]
    contact_after_failure = state_after_failure["contacts"]["sender:user-a@example.com"]
    contact_after_success = state_after_success["contacts"]["sender:user-a@example.com"]
    self.assertEqual(selected["status"], "actor_selection_queued")
    self.assertNotIn("active_identity_id", contact_after_inbound)
    self.assertNotIn("active_identity_id", contact_after_failure)
    self.assertEqual(contact_after_failure["pending_actor_choices"], {"1": "act-market-demo"})
    self.assertEqual(first_delivery["retrying"], 1)
    self.assertEqual(second_delivery["sent"], 1)
    self.assertEqual(contact_after_success["active_identity_id"], "act-market-demo")
    self.assertEqual(contact_after_success["pending_actor_choices"], {})
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelTests::test_numeric_selection_activates_actor_only_after_confirmation_delivery -q
```

Expected before implementation:

```text
FAILED
```

The current code writes `active_identity_id` before sending the selected actor confirmation.

### Task 4: Add current state schema v5 and control delivery normalization

**Files:**

- Modify: `tools/launcher/imessage_channel.py`
- Modify: `tests/test_imessage_channel.py`

- [ ] **Step 1: Update schema test to v5**

Change `test_default_state_path_uses_imessage_channel_schema_v4` to:

```python
def test_default_state_path_uses_imessage_channel_schema_v5(self) -> None:
    config = imessage_channel.ChannelConfig(server="http://127.0.0.1:8765")
    self.assertEqual(config.effective_state_path().parts[-2:], ("imessage-channel", "state.json"))

    with tempfile.TemporaryDirectory() as temp_root:
        store = imessage_channel.ImessageChannelStateStore(Path(temp_root) / "state.json")
        self.assertEqual(store.load(), {"schema_version": 5, "contacts": {}})
```

- [ ] **Step 2: Update implementation constants**

In `tools/launcher/imessage_channel.py`, change and add:

```python
SCHEMA_VERSION = 5
CONTROL_DELIVERY_MAX_ATTEMPTS = 3
CONTROL_DELIVERY_RETRY_SECONDS = 2
CONTROL_DELIVERY_FIELD = "control_delivery"
CONTROL_KIND_ACTOR_CHOICES = "actor_choices"
CONTROL_KIND_ACTOR_SELECTED = "actor_selected"
CONTROL_KIND_NEEDS_ACTOR_PROMPT = "needs_actor_prompt"
CONTROL_STATUS_PENDING = "pending"
CONTROL_STATUS_RETRY_WAIT = "retry_wait"
CONTROL_STATUS_FAILED = "failed"
```

- [ ] **Step 3: Add control delivery normalizer**

Add private helpers near `_normalize_contact(...)`:

```python
def _normalize_control_delivery(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    kind = str(value.get("kind") or "").strip()
    status = str(value.get("status") or "").strip()
    delivery_id = str(value.get("id") or "").strip()
    text = str(value.get("text") or "")
    route = value.get("route")
    created_at = _parse_utc(value.get("created_at"))
    updated_at = _parse_utc(value.get("updated_at"))
    next_attempt_at = _parse_utc(value.get("next_attempt_at"))
    effect = value.get("effect")
    if kind not in {CONTROL_KIND_ACTOR_CHOICES, CONTROL_KIND_ACTOR_SELECTED, CONTROL_KIND_NEEDS_ACTOR_PROMPT}:
        return None
    if status not in {CONTROL_STATUS_PENDING, CONTROL_STATUS_RETRY_WAIT, CONTROL_STATUS_FAILED}:
        return None
    if not delivery_id or not text or not isinstance(route, dict) or not _valid_route(route):
        return None
    if created_at is None or updated_at is None:
        return None
    if status != CONTROL_STATUS_FAILED and next_attempt_at is None:
        return None
    if not isinstance(effect, dict):
        return None
    normalized = {
        "id": delivery_id,
        "kind": kind,
        "status": status,
        "route": dict(route),
        "text": text,
        "attempts": max(int(value.get("attempts") or 0), 0),
        "created_at": _format_utc(created_at),
        "updated_at": _format_utc(updated_at),
        "last_error": str(value.get("last_error") or ""),
        "effect": _normalize_control_effect(effect),
    }
    if normalized["effect"] is None:
        return None
    if next_attempt_at is not None:
        normalized["next_attempt_at"] = _format_utc(next_attempt_at)
    return normalized
```

Also add:

```python
def _normalize_control_effect(value: dict[str, Any]) -> dict[str, Any] | None:
    effect_type = str(value.get("type") or "").strip()
    if effect_type == "set_pending_actor_choices":
        choices = _string_dict(value.get("choices"))
        if not choices:
            return None
        return {"type": effect_type, "choices": choices}
    if effect_type == "select_active_actor":
        actor_id = str(value.get("actor_id") or "").strip()
        if not actor_id:
            return None
        return {"type": effect_type, "actor_id": actor_id}
    if effect_type == "none":
        return {"type": effect_type}
    return None
```

- [ ] **Step 4: Wire normalizer into `_normalize_contact(...)`**

After `sent_outbound_event_ids` normalization:

```python
    control_delivery = _normalize_control_delivery(payload.get(CONTROL_DELIVERY_FIELD))
    if control_delivery is not None:
        contact[CONTROL_DELIVERY_FIELD] = control_delivery
```

- [ ] **Step 5: Run schema and normalizer tests**

Run:

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelTests::test_default_state_path_uses_imessage_channel_schema_v5 -q
```

Expected:

```text
1 passed
```

### Task 5: Replace synchronous control sends with current control delivery

**Files:**

- Modify: `tools/launcher/imessage_channel.py`
- Modify: `tests/test_imessage_channel.py`

- [ ] **Step 1: Add delivery creation helper**

Add helpers near `_set_pending_choices(...)`:

```python
def _set_control_delivery(
    contact: dict[str, Any],
    *,
    delivery_id: str,
    kind: str,
    route: dict[str, Any],
    text: str,
    effect: dict[str, Any],
    now: datetime,
) -> None:
    current = _as_utc(now)
    contact[CONTROL_DELIVERY_FIELD] = {
        "id": delivery_id,
        "kind": kind,
        "status": CONTROL_STATUS_PENDING,
        "route": dict(route),
        "text": text,
        "attempts": 0,
        "created_at": _format_utc(current),
        "updated_at": _format_utc(current),
        "next_attempt_at": _format_utc(current),
        "last_error": "",
        "effect": dict(effect),
    }
```

Add:

```python
def _clear_control_delivery(contact: dict[str, Any]) -> None:
    contact.pop(CONTROL_DELIVERY_FIELD, None)
```

- [ ] **Step 2: Change `_handle_actors(...)`**

Replace direct pending-choice activation and direct send with:

```python
        text = "\n".join(lines)
        _set_control_delivery(
            contact,
            delivery_id=f"{_inbound_key({'guid': 'actors-' + _format_utc(now)})}:{CONTROL_KIND_ACTOR_CHOICES}",
            kind=CONTROL_KIND_ACTOR_CHOICES,
            route=route,
            text=text,
            effect={"type": "set_pending_actor_choices", "choices": choices},
            now=now,
        )
        self.state_store.save(state)
        return {"ok": True, "status": "actors_list_queued", "count": len(lines)}
```

During implementation, use a deterministic helper for delivery id instead of rebuilding it inline:

```python
def _control_delivery_id(*, inbound_key: str, kind: str) -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in inbound_key).strip("-")
    return f"ctrl-{safe}-{kind}"
```

Then pass the real inbound key from `handle_inbound_message(...)` into `_handle_actors(...)`.

- [ ] **Step 3: Change `_handle_numeric_choice(...)`**

For selected choices, replace active state activation and direct send with:

```python
        _set_control_delivery(
            contact,
            delivery_id=_control_delivery_id(inbound_key=inbound_key, kind=CONTROL_KIND_ACTOR_SELECTED),
            kind=CONTROL_KIND_ACTOR_SELECTED,
            route=route,
            text=selected,
            effect={"type": "select_active_actor", "actor_id": selected},
            now=now,
        )
        self.state_store.save(state)
        return {"ok": True, "status": "actor_selection_queued", "actor_id": selected}
```

Pass `inbound_key` from `handle_inbound_message(...)` into `_handle_numeric_choice(...)`.

- [ ] **Step 4: Change no-active prompt path**

In `_handle_numeric_choice(...)` invalid choice path and `_handle_ordinary_message(...)` no-active path, replace direct prompt send with:

```python
        _set_control_delivery(
            contact,
            delivery_id=_control_delivery_id(inbound_key=inbound_key, kind=CONTROL_KIND_NEEDS_ACTOR_PROMPT),
            kind=CONTROL_KIND_NEEDS_ACTOR_PROMPT,
            route=route,
            text=DEFAULT_NO_ACTOR_PROMPT,
            effect={"type": "none"},
            now=now,
        )
        self.state_store.save(state)
        return {"ok": True, "status": "needs_actor"}
```

Pass `inbound_key` into `_handle_ordinary_message(...)`.

- [ ] **Step 5: Update existing direct-send assertions**

Existing tests that expected `imsg.sent` immediately after `/actors`, numeric selection, or prompt should call `controller.poll_control_delivery_once()` before asserting `imsg.sent`.

Example update:

```python
result = controller.handle_inbound_message(_row(text="/actors", guid="guid-actors"))
delivery = controller.poll_control_delivery_once()
state = controller.state_store.load()

self.assertEqual(result["status"], "actors_list_queued")
self.assertEqual(delivery["sent"], 1)
self.assertEqual(imsg.sent[0]["text"], "[1] market act-market-online\n[2] pm act-pm-online")
```

- [ ] **Step 6: Run focused existing tests**

Run:

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelTests::test_actors_control_message_lists_online_actors_and_stores_snapshot tests/test_imessage_channel.py::ImessageChannelTests::test_numeric_selection_uses_pending_snapshot_without_posting_message tests/test_imessage_channel.py::ImessageChannelTests::test_ordinary_message_without_active_actor_sends_minimal_actors_prompt -q
```

Expected:

```text
3 passed
```

### Task 6: Implement `poll_control_delivery_once()`

**Files:**

- Modify: `tools/launcher/imessage_channel.py`
- Modify: `tests/test_imessage_channel.py`

- [ ] **Step 1: Add method to controller**

Add this public method on `ImessageChannelController`:

```python
def poll_control_delivery_once(self) -> dict[str, Any]:
    now = _as_utc(self._now_fn())
    sent = 0
    retrying = 0
    failed = 0
    with self._state_lock:
        state = self.state_store.load()
        for contact in _contacts(state).values():
            delivery = _normalize_control_delivery(contact.get(CONTROL_DELIVERY_FIELD))
            if delivery is None:
                _clear_control_delivery(contact)
                continue
            if delivery["status"] == CONTROL_STATUS_FAILED:
                continue
            next_attempt_at = _parse_utc(delivery.get("next_attempt_at"))
            if next_attempt_at is not None and next_attempt_at > now:
                continue
            try:
                self.imsg.send(route=delivery["route"], text=delivery["text"])
            except Exception as exc:
                if _mark_control_delivery_failed_or_retrying(contact, delivery, str(exc), now=now):
                    failed += 1
                else:
                    retrying += 1
                self.state_store.save(state)
                continue
            _apply_control_delivery_effect(contact, delivery, now=now)
            _clear_control_delivery(contact)
            self.state_store.save(state)
            sent += 1
    return {"ok": True, "sent": sent, "retrying": retrying, "failed": failed}
```

- [ ] **Step 2: Add retry marker helper**

Add:

```python
def _mark_control_delivery_failed_or_retrying(
    contact: dict[str, Any],
    delivery: dict[str, Any],
    error_message: str,
    *,
    now: datetime,
) -> bool:
    attempts = int(delivery.get("attempts") or 0) + 1
    current = _as_utc(now)
    delivery["attempts"] = attempts
    delivery["updated_at"] = _format_utc(current)
    delivery["last_error"] = error_message
    if attempts >= CONTROL_DELIVERY_MAX_ATTEMPTS:
        delivery["status"] = CONTROL_STATUS_FAILED
        delivery.pop("next_attempt_at", None)
        contact[CONTROL_DELIVERY_FIELD] = delivery
        return True
    delivery["status"] = CONTROL_STATUS_RETRY_WAIT
    delivery["next_attempt_at"] = _format_utc(current + timedelta(seconds=CONTROL_DELIVERY_RETRY_SECONDS))
    contact[CONTROL_DELIVERY_FIELD] = delivery
    return False
```

- [ ] **Step 3: Add effect application helper**

Add:

```python
def _apply_control_delivery_effect(contact: dict[str, Any], delivery: dict[str, Any], *, now: datetime) -> None:
    effect = delivery.get("effect")
    if not isinstance(effect, dict):
        return
    effect_type = effect.get("type")
    if effect_type == "set_pending_actor_choices":
        choices = _string_dict(effect.get("choices"))
        _set_pending_choices(contact, choices, now=now)
        return
    if effect_type == "select_active_actor":
        actor_id = str(effect.get("actor_id") or "").strip()
        if actor_id:
            _set_active_identity(contact, actor_id, now=now)
            _clear_pending_choices(contact)
        return
```

- [ ] **Step 4: Run new ordering tests**

Run:

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelTests::test_actors_choices_activate_only_after_actor_list_delivery_succeeds tests/test_imessage_channel.py::ImessageChannelTests::test_numeric_selection_activates_actor_only_after_confirmation_delivery -q
```

Expected:

```text
2 passed
```

### Task 7: Isolate row and tick failures inside worker loops

**Files:**

- Modify: `tools/launcher/imessage_channel.py`
- Modify: `tests/test_imessage_channel.py`

- [ ] **Step 1: Change `run_forever()`**

Replace row handling with:

```python
for row in self.controller.imsg.watch_messages():
    if self._stop_event.is_set():
        break
    try:
        self.controller.handle_inbound_message(row)
    except Exception as exc:
        print(f"iMessage channel inbound message failed: {exc}", file=sys.stderr, flush=True)
```

- [ ] **Step 2: Change `run_outbound_forever()`**

Replace loop body with:

```python
while not self._stop_event.is_set():
    try:
        self.controller.poll_control_delivery_once()
    except Exception as exc:
        print(f"iMessage channel control delivery failed: {exc}", file=sys.stderr, flush=True)
    try:
        self.controller.poll_outbound_once(wait_ms=wait_ms)
    except Exception as exc:
        print(f"iMessage channel outbound poll failed: {exc}", file=sys.stderr, flush=True)
    self._stop_event.wait(0.01)
```

- [ ] **Step 3: Run worker survival tests**

Run:

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelTests::test_worker_keeps_processing_after_actors_response_send_failure tests/test_imessage_channel.py::ImessageChannelTests::test_worker_processes_actors_while_outbound_poll_is_blocked tests/test_imessage_channel.py::ImessageChannelTests::test_worker_delivers_late_reply_without_new_inbound_message -q
```

Expected:

```text
3 passed
```

### Task 8: Add residue tests for no synchronous control-send path

**Files:**

- Modify: `tests/test_imessage_channel.py`

- [ ] **Step 1: Add scoped source scan**

Add this test to `ImessageChannelResidueTests`:

```python
def test_control_handlers_do_not_send_imessage_synchronously(self) -> None:
    source = (ROOT / "tools" / "launcher" / "imessage_channel.py").read_text(encoding="utf-8")
    handler_names = ("_handle_actors", "_handle_numeric_choice", "_handle_ordinary_message")
    hits: list[str] = []
    for handler_name in handler_names:
        match = re.search(rf"def {handler_name}\([\\s\\S]*?\\n    def ", source)
        if match is None:
            hits.append(f"{handler_name}: missing")
            continue
        body = match.group(0)
        if "self.imsg.send" in body:
            hits.append(f"{handler_name}: synchronous imsg send")
    self.assertEqual(hits, [])
```

- [ ] **Step 2: Update schema residue test**

In `test_selected_actor_ttl_source_uses_expiry_helpers_not_permanent_paths`, add:

```python
"SCHEMA_VERSION = " + "4",
```

to retired paths.

- [ ] **Step 3: Add control delivery boundary scan**

Extend `test_channel_semantics_stay_out_of_web_http_and_core` forbidden terms with:

```python
"control_delivery",
"CONTROL_DELIVERY_MAX_ATTEMPTS",
"CONTROL_KIND_ACTOR_CHOICES",
```

- [ ] **Step 4: Run residue tests**

Run:

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests -q
```

Expected:

```text
7 passed
```

### Task 9: Run complete verification

**Files:**

- Verify only

- [ ] **Step 1: Run focused iMessage channel suite**

Run:

```bash
python -m pytest tests/test_imessage_channel.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 2: Run Web projection tests that guard iMessage boundary**

Run:

```bash
python -m pytest tests/test_web_management.py::WebManagementTests::test_web_management_source_does_not_parse_imessage_control_messages tests/test_web_management.py::WebManagementTests::test_serve_with_imessage_worker_keeps_web_server_alive_when_worker_start_fails -q
```

Expected:

```text
2 passed
```

- [ ] **Step 3: Run scoped residue scans**

Run:

```bash
rg -n "SCHEMA_VERSION = 4|self\\.imsg\\.send\\(" tools/launcher/imessage_channel.py
```

Expected:

```text
Only expected self.imsg.send hits remain inside poll_control_delivery_once and poll_outbound_once.
No SCHEMA_VERSION = 4 hit.
```

Run:

```bash
rg -n "control_delivery|CONTROL_DELIVERY_MAX_ATTEMPTS|CONTROL_KIND_ACTOR_CHOICES|pending_actor_choices|active_identity_expires_at|pending_actor_choices_expires_at" tools/launcher/web_management.py tools/launcher/im_http_router.py scripts/env/services scripts/env/repos scripts/env/tool_runtime
```

Expected:

```text
No matches.
```

## 10. Acceptance Criteria

The work is complete only when all of these are true:

1. `/actors` no longer writes active pending choices before the actor list is confirmed sent through iMessage.
2. Numeric actor selection no longer writes active actor state before the confirmation response is confirmed sent through iMessage.
3. Failed control response delivery is represented in iMessage channel state with attempts and last error.
4. Control response delivery retries at most three times and then fails explicitly.
5. A later `/actors` supersedes a failed control delivery and can be sent normally.
6. One iMessage send failure cannot stop the inbound worker from processing later rows.
7. One outbound tick failure cannot stop the outbound worker loop.
8. Actor outbound reply delivery still uses contact route and event ack semantics.
9. IM API, IM core, Web UI, actor tool runtime, and Task Sys do not contain iMessage selected-actor or control delivery semantics.
10. Existing local schema v4 state is rejected with the reset-oriented retired-schema error.

## 11. Explicit Non-Goals

- Do not add a second provider.
- Do not migrate to `platform-imessage`.
- Do not wrap `imsg` behind a generic provider interface.
- Do not add Web UI controls for this failure state in this change.
- Do not add rollback compatibility for schema v4.
- Do not add state migration from schema v4 to schema v5.
- Do not preserve direct synchronous control sends as a fallback path.
- Do not use iMessage to send a fallback failure message after iMessage delivery itself failed.

## 12. Key Risks And Boundaries

### Risk: retry could duplicate a message after an ambiguous provider timeout

The existing `CommandImsgClient.send(...)` already waits for chat.db send status before returning success. If it raises after command submission without confirmation, retry may duplicate text in rare ambiguous cases.

Boundary decision:

- For `/actors` and prompts, duplicate text is less damaging than silent channel death.
- Keep retry count small.
- Keep failed state explicit after three failures.
- Do not mark actor choices active unless one attempt returns confirmed success.

### Risk: control delivery state grows into a generic workflow queue

Boundary decision:

- Keep exactly one `control_delivery` per contact.
- Keep exactly three kinds.
- Keep effects allowlisted.
- New business workflows must not add more kinds in this task.

### Risk: worker catches too much and hides defects

Boundary decision:

- Row and tick exceptions are logged to stderr.
- State records control delivery failure details.
- Direct controller methods used by tests still expose return counts and state.
- Tests verify failure isolation and failure visibility.

## 13. Plan Self-Review

### Spec coverage

- Task goal is stated in Sections 1, 5, 7, and 10.
- No residual and no compatibility requirements are covered in Sections 2, 5, 8, 10, and 11.
- Module boundary is covered in Section 4 and residue tests in Task 8.
- Retry and failure fallback are covered in Sections 6, 7, 8, 10, and 12.
- Worker survival is covered in Task 2 and Task 7.
- Current code audit is covered in Section 3.

### Placeholder scan

This plan avoids placeholder wording, deferred implementation language, broad unspecified error handling, and generic future work. Each task names exact files, exact test names, exact commands, and expected results.

### Type and name consistency

The plan consistently uses:

- `control_delivery`
- `CONTROL_DELIVERY_FIELD`
- `CONTROL_KIND_ACTOR_CHOICES`
- `CONTROL_KIND_ACTOR_SELECTED`
- `CONTROL_KIND_NEEDS_ACTOR_PROMPT`
- `CONTROL_STATUS_PENDING`
- `CONTROL_STATUS_RETRY_WAIT`
- `CONTROL_STATUS_FAILED`
- `poll_control_delivery_once()`
- `actors_list_queued`
- `actor_selection_queued`

### Boundary validation

The plan modifies only:

- `tools/launcher/imessage_channel.py`
- `tests/test_imessage_channel.py`

The optional verification runs existing Web tests but does not modify Web. This keeps the implementation inside the iMessage module while proving the boundary stays clean.
