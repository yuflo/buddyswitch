# Daemon Turn Provenance Task Checkout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix taskTUI checkout so effective daemon-started work turns can trigger checkout while task checkout's own daemon turns still cannot self-loop.

**Architecture:** Keep daemon core business-neutral. Daemon core records which handler submitted each daemon-origin turn and exposes provenance query helpers; task checkout owns the business decision about which handler-origin turns to ignore. No goal event system, plugin system, event bus, or task-specific daemon branch is introduced.

**Tech Stack:** Python daemon launcher code, JSON daemon state, pytest/unittest tests.

---

## Execution Status

- [x] Root cause restated: task checkout ignored all daemon-origin turns.
- [x] Decoupling reviewed: daemon core only records neutral provenance; task checkout owns taskTUI filtering policy.
- [x] Regression tests added for provenance recording, task-checkout-origin ignore, and message-available-origin acceptance.
- [x] Implementation completed in daemon state, action gateway, and task checkout filter.
- [x] Focused, boundary, and launcher integration verification passed.

## Task Target

Current taskTUI filtering treats every daemon-origin turn as ignorable:

```python
if state.is_daemon_origin_turn(turn_id):
    return None
```

That is too broad. A `message_available` handler turn can read messages, perform real work, update durable state, and complete the user's task. The only daemon-origin turn that task checkout must ignore is a turn submitted by `task_checkout` itself, because that prevents taskTUI from triggering another taskTUI.

Target behavior:

```python
if state.is_daemon_origin_turn_from(turn_id, "task_checkout"):
    return None
```

## Decoupling Review

Daemon core remains generic:

- It records provenance facts: `turn_id`, `handler_name`, `origin_turn_id`, and `created_at`.
- It exposes query helpers over those facts.
- It does not import `task_tui`, `task_management`, or any task domain module.
- It does not decide which handler origins are business noise.

Task checkout remains the business owner:

- It decides to ignore only `task_checkout`-origin turns.
- It continues to accept ordinary user turns.
- It now accepts daemon-origin turns from other handlers such as `message_available`.

This keeps the boundary clean: daemon core supplies neutral facts; task checkout applies taskTUI policy.

## File Responsibility Map

- `tools/launcher/daemon_core.py`
  - Load and normalize daemon state.
  - Persist daemon-origin turn ids.
  - Persist daemon-origin turn provenance records.
  - Provide `daemon_turn_record(turn_id)` and `is_daemon_origin_turn_from(turn_id, handler_name)`.
  - Record provenance inside `ActionGateway.submit_turn(...)`.

- `tools/launcher/task_checkout_handler.py`
  - Keep notification filtering local to task checkout.
  - Replace all-daemon-origin ignore with task-checkout-origin ignore.

- `tests/test_daemon_core.py`
  - Cover state persistence, trimming, lookup helpers, and legacy daemon-origin state behavior.

- `tests/test_daemon_service_contract.py`
  - Cover `ActionGateway.submit_turn(...)` provenance recording contract.

- `tests/test_task_checkout_handler.py`
  - Cover task checkout accepting `message_available` daemon turns and ignoring `task_checkout` daemon turns.

- `docs/spec/2026-06-01-daemon-turn-provenance-task-checkout-plan.md`
  - Store this task target, decoupling review, implementation plan, and verification commands.

## State Shape

Keep existing `daemon_origin_turn_ids` for the simple membership API and status compatibility. Add a keyed record map:

```json
{
  "daemon_origin_turn_ids": ["turn-daemon-1"],
  "daemon_origin_turns": {
    "turn-daemon-1": {
      "turn_id": "turn-daemon-1",
      "handler_name": "message_available",
      "origin_turn_id": "msg-1",
      "created_at": "2026-06-01T00:00:00Z"
    }
  }
}
```

Trim `daemon_origin_turns` to the same latest 50 ids retained in `daemon_origin_turn_ids`.

Legacy rule: if a turn id is present in old `daemon_origin_turn_ids` but has no provenance record, `state.is_daemon_origin_turn_from(turn_id, handler_name)` returns `True` only for `handler_name == "task_checkout"`. This is conservative for old state because the main risk is task checkout self-looping on pre-provenance task checkout turns.

## Implementation Tasks

### Task 1: Add daemon state provenance tests

**Files:**

- Modify: `tests/test_daemon_core.py`

- [ ] Step 1: Add a failing test for provenance persistence and lookup.

Test behavior:

```python
state.record_daemon_origin_turn(
    "turn-daemon-1",
    handler_name="message_available",
    origin_turn_id="msg-1",
)

saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))

self.assertEqual(saved["daemon_origin_turn_ids"], ["turn-daemon-1"])
self.assertEqual(saved["daemon_origin_turns"]["turn-daemon-1"]["handler_name"], "message_available")
self.assertEqual(saved["daemon_origin_turns"]["turn-daemon-1"]["origin_turn_id"], "msg-1")
self.assertEqual(saved["daemon_origin_turns"]["turn-daemon-1"]["turn_id"], "turn-daemon-1")
self.assertRegex(saved["daemon_origin_turns"]["turn-daemon-1"]["created_at"], r"^\d{4}-\d{2}-\d{2}T")
self.assertEqual(state.daemon_turn_record("turn-daemon-1")["handler_name"], "message_available")
self.assertTrue(state.is_daemon_origin_turn_from("turn-daemon-1", "message_available"))
self.assertFalse(state.is_daemon_origin_turn_from("turn-daemon-1", "task_checkout"))
```

Run:

```bash
python3 -m pytest tests/test_daemon_core.py::DaemonCoreStateTests::test_recording_daemon_origin_turn_persists_provenance -q
```

Expected before implementation: fail because `record_daemon_origin_turn` does not accept provenance fields and lookup helpers do not exist.

- [ ] Step 2: Add a failing test for legacy fallback.

Test behavior:

```python
state.record_daemon_origin_turn("turn-legacy-1")

self.assertTrue(state.is_daemon_origin_turn("turn-legacy-1"))
self.assertIsNone(state.daemon_turn_record("turn-legacy-1"))
self.assertTrue(state.is_daemon_origin_turn_from("turn-legacy-1", "task_checkout"))
self.assertFalse(state.is_daemon_origin_turn_from("turn-legacy-1", "message_available"))
```

Run:

```bash
python3 -m pytest tests/test_daemon_core.py::DaemonCoreStateTests::test_legacy_daemon_origin_without_provenance_is_only_task_checkout_filtered -q
```

Expected before implementation: fail because lookup helpers do not exist.

- [ ] Step 3: Add trimming assertions to the existing latest-50 test.

After recording 55 turns with handler names, assert:

```python
self.assertEqual(len(saved["daemon_origin_turns"]), 50)
self.assertNotIn("turn-daemon-4", saved["daemon_origin_turns"])
self.assertEqual(saved["daemon_origin_turns"]["turn-daemon-54"]["handler_name"], "task_checkout")
```

Run:

```bash
python3 -m pytest tests/test_daemon_core.py::DaemonCoreStateTests::test_daemon_origin_turn_ids_keep_latest_50 -q
```

Expected before implementation: fail because `daemon_origin_turns` is missing.

### Task 2: Add ActionGateway provenance contract test

**Files:**

- Modify: `tests/test_daemon_service_contract.py`

- [ ] Step 1: Extend `test_action_gateway_records_daemon_origin_and_handler_action_state_from_submit_turn`.

After `actions.submit_turn("daemon prompt", handler_name="fake", origin_turn_id="turn-user-1")`, assert:

```python
self.assertEqual(saved["daemon_origin_turn_ids"], ["turn-daemon-1"])
self.assertEqual(saved["daemon_origin_turns"]["turn-daemon-1"]["handler_name"], "fake")
self.assertEqual(saved["daemon_origin_turns"]["turn-daemon-1"]["origin_turn_id"], "turn-user-1")
self.assertEqual(saved["daemon_origin_turns"]["turn-daemon-1"]["turn_id"], "turn-daemon-1")
self.assertRegex(saved["daemon_origin_turns"]["turn-daemon-1"]["created_at"], r"^\d{4}-\d{2}-\d{2}T")
```

Run:

```bash
python3 -m pytest tests/test_daemon_service_contract.py::DaemonServiceContractTests::test_action_gateway_records_daemon_origin_and_handler_action_state_from_submit_turn -q
```

Expected before implementation: fail because `daemon_origin_turns` is missing.

### Task 3: Add task checkout filtering regression tests

**Files:**

- Modify: `tests/test_task_checkout_handler.py`

- [ ] Step 1: Replace the broad daemon-origin ignore test with a task-checkout-origin ignore test.

Test behavior:

```python
state.record_daemon_origin_turn(
    "turn-daemon-1",
    handler_name="task_checkout",
    origin_turn_id="turn-user-1",
)

previous_turn = self.task_checkout_handler.completed_turn_for_checkout(
    self._completed(turn_id="turn-daemon-1"),
    state,
)

self.assertIsNone(previous_turn)
```

Run:

```bash
python3 -m pytest tests/test_task_checkout_handler.py::TaskCheckoutHandlerFilterTests::test_task_checkout_origin_turn_is_ignored -q
```

Expected before implementation: fail until the test name and provenance API exist.

- [ ] Step 2: Add a regression test for `message_available` daemon-origin turns.

Test behavior:

```python
state.record_daemon_origin_turn(
    "turn-daemon-1",
    handler_name="message_available",
    origin_turn_id="msg-1",
)

previous_turn = self.task_checkout_handler.completed_turn_for_checkout(
    self._completed(turn_id="turn-daemon-1"),
    state,
)

self.assertEqual(
    previous_turn,
    {"thread_id": "thr-main", "turn_id": "turn-daemon-1", "status": "completed"},
)
```

Run:

```bash
python3 -m pytest tests/test_task_checkout_handler.py::TaskCheckoutHandlerFilterTests::test_message_available_daemon_origin_turn_is_accepted -q
```

Expected before implementation: fail because current filter ignores all daemon-origin turns.

- [ ] Step 3: Update ignored notification coverage so only the task-checkout-origin daemon turn is ignored.

The ignored list should use a turn recorded with `handler_name="task_checkout"`. Do not include `message_available` daemon-origin turns in ignored cases.

Run:

```bash
python3 -m pytest tests/test_task_checkout_handler.py::TaskCheckoutHandlerFilterTests::test_handler_returns_ignored_result_for_ignored_notifications -q
```

Expected before implementation: fail if the new provenance API is missing.

### Task 4: Implement daemon provenance

**Files:**

- Modify: `tools/launcher/daemon_core.py`

- [ ] Step 1: Add `daemon_origin_turns` to `_state_payload`.

Implementation:

```python
"daemon_origin_turns": {},
```

- [ ] Step 2: Normalize loaded `daemon_origin_turns`.

Keep only dict records keyed by retained turn ids where:

- key is a non-empty string
- record is a dict
- `turn_id` is either absent or equal to the key
- `handler_name` is a non-empty string

Normalize each retained record to:

```python
{
    "turn_id": turn_id,
    "handler_name": handler_name,
    "origin_turn_id": origin_turn_id_or_none,
    "created_at": created_at_or_utc_now,
}
```

- [ ] Step 3: Change `record_daemon_origin_turn(...)` signature.

Implementation contract:

```python
def record_daemon_origin_turn(
    self,
    turn_id: str,
    *,
    handler_name: str | None = None,
    origin_turn_id: str | None = None,
) -> None:
```

Existing calls without keyword provenance remain valid and write only the legacy id list.

- [ ] Step 4: Add query helpers.

Implementation contract:

```python
def daemon_turn_record(self, turn_id: str) -> dict[str, Any] | None:
    ...

def is_daemon_origin_turn_from(self, turn_id: str, handler_name: str) -> bool:
    ...
```

Legacy fallback:

```python
if self.is_daemon_origin_turn(turn_id) and self.daemon_turn_record(turn_id) is None:
    return handler_name == "task_checkout"
```

- [ ] Step 5: Update `ActionGateway.submit_turn(...)`.

Implementation:

```python
self.state.record_daemon_origin_turn(
    turn_id,
    handler_name=handler_name,
    origin_turn_id=origin_turn_id,
)
```

### Task 5: Implement task checkout filter

**Files:**

- Modify: `tools/launcher/task_checkout_handler.py`

- [ ] Step 1: Replace the broad daemon-origin filter.

Implementation:

```python
if state.is_daemon_origin_turn_from(turn_id, "task_checkout"):
    return None
```

No task-specific code is added to daemon core.

## Verification Plan

Run focused red/green checks while implementing:

```bash
python3 -m pytest tests/test_daemon_core.py::DaemonCoreStateTests::test_recording_daemon_origin_turn_persists_provenance -q
python3 -m pytest tests/test_daemon_core.py::DaemonCoreStateTests::test_legacy_daemon_origin_without_provenance_is_only_task_checkout_filtered -q
python3 -m pytest tests/test_daemon_core.py::DaemonCoreStateTests::test_daemon_origin_turn_ids_keep_latest_50 -q
python3 -m pytest tests/test_daemon_service_contract.py::DaemonServiceContractTests::test_action_gateway_records_daemon_origin_and_handler_action_state_from_submit_turn -q
python3 -m pytest tests/test_task_checkout_handler.py::TaskCheckoutHandlerFilterTests::test_message_available_daemon_origin_turn_is_accepted -q
python3 -m pytest tests/test_task_checkout_handler.py::TaskCheckoutHandlerFilterTests::test_task_checkout_origin_turn_is_ignored -q
```

Run broader relevant checks before acceptance:

```bash
python3 -m pytest tests/test_daemon_core.py tests/test_daemon_service_contract.py tests/test_task_checkout_handler.py -q
python3 -m pytest tests/test_daemon_core_decoupling.py tests/test_message_available_handler.py tests/test_instance_daemon_entrypoint.py -q
```

Completion evidence:

- `message_available` daemon-origin completed turn is accepted by task checkout filtering.
- `task_checkout` daemon-origin completed turn is ignored.
- `ActionGateway.submit_turn(...)` records handler provenance for new daemon turns.
- Legacy no-provenance daemon-origin turns are conservatively treated as task-checkout-origin for filtering.
- Daemon core decoupling test proves task domain imports stay outside daemon core.
