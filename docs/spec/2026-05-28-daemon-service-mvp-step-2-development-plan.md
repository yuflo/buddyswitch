# Daemon Service MVP Step 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` before implementation, then use `superpowers:executing-plans` or inline TDD to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote daemon core into a small Daemon Service MVP with a concrete handler contract, action gateway, handler state namespace, failure isolation, and handler status observability while preserving Task Checkout behavior.

**Architecture:** Keep `tools/launcher/instance_daemon.py` as the CLI entrypoint and keep handler wiring explicit. Extend `tools/launcher/daemon_core.py` with `HandlerResult`, `ActionGateway`, handler state helpers, and handler-aware status. Update `tools/launcher/task_checkout_handler.py` to use the contract/gateway instead of raw app-server request construction.

**Tech Stack:** Python standard library, existing app-server JSON-RPC client, pytest/unittest, fake Codex launcher tests.

---

## Current Bottleneck

Step 1 made daemon independent from Task TUI, but the service surface is still informal:

- handler return type is `bool`;
- handlers receive the raw app-server client and can duplicate daemon-side action logic;
- handler errors are mixed with top-level daemon errors;
- status cannot show registered handler health;
- Task Checkout Handler records task-specific `last_checkout_turn_id` instead of the service-standard `last_action_turn_id`.

Step 2 fixes that service surface directly. Do not add dynamic handler loading, plugin registry, event bus, message handler, workflow engine, or launcher bootstrap repair logic.

## Target File Structure

Create:

- `tests/test_daemon_service_contract.py`
  - handler result contract tests;
  - dispatch contract/failure isolation tests;
  - action gateway tests.

- `docs/spec/2026-05-28-daemon-service-mvp-step-2-test-plan.md`
  - requirements, coverage matrix, verification commands.

- `docs/spec/2026-05-28-daemon-service-mvp-step-2-development-plan.md`
  - this implementation plan.

- `docs/spec/2026-05-28-daemon-service-mvp-step-2-execution-prompt.md`
  - clean execution prompt for Phase 2.

Modify:

- `tools/launcher/daemon_core.py`
  - add `HandlerResult`;
  - add `ActionGateway`;
  - add handler registration/result/error state helpers;
  - dispatch handlers with `(context, state, actions, notification)`;
  - reserve top-level `last_error` for fatal daemon errors;
  - report registered/persisted handler observability in `daemon_status`.

- `tools/launcher/task_checkout_handler.py`
  - return `HandlerResult`;
  - use `ActionGateway.turn_start(...)`;
  - write service-standard handler fields only.

- `tools/launcher/instance_daemon.py`
  - pass default handlers to `run`, `start`, and `status`.

- `tests/test_daemon_core.py`
  - update dispatch/error/status tests for service contract.

- `tests/test_task_checkout_handler.py`
  - update handler tests for `ActionGateway` and explicit results.

- `tests/test_instance_daemon_entrypoint.py`
  - update status/start wiring tests.

- `tests/test_buddyswitch_launcher.py`
  - assert handler status observability and standard action state.

Do not modify:

- `tools/launcher/app_server.py` bootstrap behavior except if a regression test exposes an unrelated real bug.
- `tools/launcher/task_input_context.py`.
- `scripts/env/domain/task_tui.py` or `scripts/env/domain/task_management.py`.

## State Shape

Keep one daemon state file:

```text
<instance_root>/runtime/daemon/state.json
```

Service-standard target shape:

```json
{
  "instance_id": "inst-dev",
  "main_thread_id": "thr-main",
  "daemon_origin_turn_ids": ["turn-daemon-1"],
  "ready": {
    "pid": 1234,
    "main_thread_id": "thr-main",
    "at": "2026-05-28T00:00:00Z"
  },
  "last_error": null,
  "handlers": {
    "task_checkout": {
      "registered": true,
      "enabled": true,
      "active": true,
      "last_result": "handled",
      "last_handled_at": "2026-05-28T00:00:00Z",
      "last_origin_turn_id": "turn-user-1",
      "last_action_turn_id": "turn-daemon-1",
      "last_error": null
    }
  }
}
```

Rules:

- top-level `last_error` is daemon-fatal only;
- handler errors live under `handlers.<name>.last_error`;
- use `last_action_turn_id` for daemon actions;
- do not add `last_checkout_turn_id` compatibility mirrors.

## Task 1: Add Daemon Service Contract Tests

**Files:**

- Create: `tests/test_daemon_service_contract.py`
- Modify: `tests/test_daemon_core.py`

- [ ] **Step 1: Write handler result and dispatch tests**

Add tests that expect:

```python
result = daemon_core.HandlerResult.handled()
self.assertEqual(result.status, "handled")
```

and fake handlers with:

```python
def handle_notification(self, context, state, actions, notification):
    self.actions_type = type(actions).__name__
    return daemon_core.HandlerResult.handled()
```

- [ ] **Step 2: Run red contract tests**

```bash
python3 -m pytest tests/test_daemon_service_contract.py -q
```

Expected red result: `HandlerResult` / `ActionGateway` missing or old dispatch passes raw client.

- [ ] **Step 3: Add handler-aware status tests**

In `tests/test_daemon_core.py`, assert `daemon_status(..., handlers=[FakeHandler("task_checkout")])` returns:

```python
payload["handlers"]["registered"] == ["task_checkout"]
payload["handlers"]["items"]["task_checkout"]["enabled"] is True
```

- [ ] **Step 4: Run red status tests**

```bash
python3 -m pytest tests/test_daemon_core.py -q
```

Expected red result: daemon status has no handler observability.

## Task 2: Implement Handler Contract And Action Gateway

**Files:**

- Modify: `tools/launcher/daemon_core.py`

- [ ] **Step 1: Add explicit `HandlerResult`**

Add a small immutable result type:

```python
class HandlerResult:
    def __init__(self, status: str, message: str | None = None) -> None:
        if status not in {"ignored", "handled", "failed"}:
            raise ValueError(f"invalid handler result status: {status}")
        self.status = status
        self.message = message

    @classmethod
    def ignored(cls) -> "HandlerResult":
        return cls("ignored")

    @classmethod
    def handled(cls) -> "HandlerResult":
        return cls("handled")

    @classmethod
    def failed(cls, message: str) -> "HandlerResult":
        return cls("failed", message or "handler failed")
```

- [ ] **Step 2: Add `ActionGateway`**

Implement:

```python
class ActionGateway:
    def __init__(self, *, context: DaemonContext, state: DaemonState, client: Any) -> None:
        self.context = context
        self.state = state
        self.client = client

    def turn_start(self, text: str, *, handler_name: str, origin_turn_id: str | None) -> str:
        result = self.client.request(
            "turn/start",
            {
                "threadId": self.context.main_thread_id,
                "input": app_server.text_input_payload(text),
                "permissions": self.context.permissions,
            },
        )
        turn_id = _turn_id_from_start_result(result)
        if not turn_id:
            raise app_server.AppServerProtocolError("turn/start did not return a turn id")
        self.state.record_daemon_origin_turn(turn_id)
        self.state.update_handler_state(
            handler_name,
            {
                "last_origin_turn_id": origin_turn_id,
                "last_action_turn_id": turn_id,
                "last_error": None,
            },
        )
        return turn_id
```

- [ ] **Step 3: Add handler state helpers**

Add methods on `DaemonState`:

```python
def register_handlers(self, handler_names: list[str]) -> None:
    for name in handler_names:
        self.update_handler_state(name, {
            "registered": True,
            "enabled": True,
            "active": True,
            "last_error": self.handler_state(name).get("last_error"),
        })

def record_handler_result(self, handler_name: str, result: HandlerResult, *, origin_turn_id: str | None) -> None:
    values = {"last_result": result.status}
    if result.status == "handled":
        values["last_handled_at"] = _utc_now()
        values["last_origin_turn_id"] = origin_turn_id
        values["last_error"] = None
    elif result.status == "failed":
        values["last_error"] = {
            "origin_turn_id": origin_turn_id,
            "message": result.message or "handler failed",
            "at": _utc_now(),
        }
    self.update_handler_state(handler_name, values)
```

- [ ] **Step 4: Update dispatch**

Change dispatch to:

```python
actions = ActionGateway(context=context, state=state, client=client)
result = handler.handle_notification(context, state, actions, notification)
if not isinstance(result, HandlerResult):
    raise TypeError(...)
state.record_handler_result(handler_name, result, origin_turn_id=origin_turn_id)
```

Catch exceptions and write handler error only.

- [ ] **Step 5: Run focused contract tests**

```bash
python3 -m pytest tests/test_daemon_service_contract.py tests/test_daemon_core.py -q
```

Expected: pass after implementation.

## Task 3: Add Handler Observability To Status And Entrypoint

**Files:**

- Modify: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/instance_daemon.py`
- Modify: `tests/test_instance_daemon_entrypoint.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add status tests first**

Assert:

```python
payload = daemon_core.daemon_status(instance_json, handlers=[FakeHandler("task_checkout")])
self.assertEqual(payload["handlers"]["registered"], ["task_checkout"])
self.assertTrue(payload["handlers"]["items"]["task_checkout"]["active"])
```

- [ ] **Step 2: Implement `handler_status_payload(...)`**

In daemon core, merge registered handler names with persisted `state.payload["handlers"]`:

```python
{
  "registered": ["task_checkout"],
  "items": {
    "task_checkout": {
      "registered": True,
      "enabled": True,
      "active": True,
      ...
    }
  }
}
```

Persisted but unregistered handler state appears with `registered: False`, `enabled: False`, `active: False`.

- [ ] **Step 3: Pass handlers through entrypoint**

Update:

```python
daemon_core.start_daemon(instance_json, handlers=default_handlers())
daemon_core.daemon_status(instance_json, handlers=default_handlers())
```

- [ ] **Step 4: Add human status line**

In `buddyswitch-codex`, add:

```python
handlers = daemon.get("handlers") if isinstance(daemon.get("handlers"), dict) else {}
registered = handlers.get("registered") if isinstance(handlers.get("registered"), list) else []
print(f"Daemon handlers: {', '.join(str(item) for item in registered) if registered else ''}")
```

- [ ] **Step 5: Run entrypoint and launcher status tests**

```bash
python3 -m pytest tests/test_instance_daemon_entrypoint.py tests/test_buddyswitch_launcher.py -k 'daemon or status' -q
```

Expected: pass.

## Task 4: Convert Task Checkout Handler To Standard Contract

**Files:**

- Modify: `tools/launcher/task_checkout_handler.py`
- Modify: `tests/test_task_checkout_handler.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Update Task Checkout tests first**

Expect ignored notifications to return `HandlerResult.ignored()`.

Expect accepted notification to call:

```python
actions.turn_start(prompt, handler_name="task_checkout", origin_turn_id="turn-user-1")
```

- [ ] **Step 2: Remove direct `client.request("turn/start", ...)` from handler**

Replace send logic with:

```python
turn_id = actions.turn_start(prompt, handler_name=self.name, origin_turn_id=origin_turn_id)
```

- [ ] **Step 3: Return explicit results**

Use:

```python
return daemon_core.HandlerResult.ignored()
return daemon_core.HandlerResult.handled()
return daemon_core.HandlerResult.failed(str(exc))
```

- [ ] **Step 4: Remove task-specific action state field**

Stop writing `last_checkout_turn_id`. The standard action gateway writes `last_action_turn_id`.

- [ ] **Step 5: Run handler tests**

```bash
python3 -m pytest tests/test_task_checkout_handler.py tests/test_daemon_service_contract.py -q
```

Expected: pass.

## Task 5: Preserve Launcher And Input Boundaries

**Files:**

- Modify tests only unless behavior is broken:
  - `tests/test_buddyswitch_launcher.py`
  - `tests/test_task_input_context.py`
  - `tests/test_app_server_client.py`

- [ ] **Step 1: Keep bootstrap regression tests green**

Run:

```bash
python3 -m pytest tests/test_app_server_client.py tests/test_buddyswitch_launcher.py -k 'bootstrap or daemon' -q
```

- [ ] **Step 2: Keep input Task TUI regression tests green**

Run:

```bash
python3 -m pytest tests/test_task_input_context.py tests/test_buddyswitch_launcher.py -k 'input or task' -q
```

- [ ] **Step 3: If a boundary breaks, fix only the direct break**

Do not move input Task TUI into daemon and do not make daemon call `thread/inject_items` / `thread/start`.

## Task 6: Final Verification And Review

**Files:**

- Inspect:
  - `tools/launcher/daemon_core.py`
  - `tools/launcher/task_checkout_handler.py`
  - `tools/launcher/instance_daemon.py`
  - `tools/launcher/app_server.py`
  - `tools/launcher/task_input_context.py`

- [ ] **Step 1: Run final related test suite**

```bash
python3 -m pytest tests/test_daemon_service_contract.py tests/test_daemon_core_decoupling.py tests/test_daemon_core.py tests/test_task_checkout_handler.py tests/test_instance_daemon_entrypoint.py tests/test_app_server_client.py tests/test_task_input_context.py tests/test_buddyswitch_launcher.py -q
```

- [ ] **Step 2: Run architecture grep review**

```bash
rg -n "task_tui|task_management|message handler|event bus|plugin registry|thread/inject_items|thread/start" tools/launcher/daemon_core.py tools/launcher/task_checkout_handler.py tools/launcher/instance_daemon.py
```

Expected:

- `daemon_core.py` has no task domain or bootstrap calls;
- `task_checkout_handler.py` has task domain imports only;
- no message handler, event bus, plugin registry, or workflow engine.

- [ ] **Step 3: Check git status**

```bash
git status --short
```

Expected: only Step 2 memo/spec/code/test changes in `fea-daemon`; main worktree untouched.

## Plan Review

- The plan covers every Step 2 memo requirement with tests before implementation.
- It keeps the handler list explicit and in-process.
- It does not implement message business behavior.
- It moves action construction into daemon service without changing user-facing Task Checkout behavior.
- It preserves launcher bootstrap and input Task TUI ownership.
