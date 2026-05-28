# Daemon Core / Task TUI Decoupling Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` before implementation, then use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract daemon core from the first Task TUI daemon implementation so daemon becomes an independent instance-level background container, while STOP Task TUI remains available through a separate Task Checkout Handler.

**Architecture:** Keep `tools/launcher/instance_daemon.py` as the CLI entrypoint used by `daemon.sh`. Move daemon lifecycle/runtime logic into `tools/launcher/daemon_core.py`. Move STOP Task TUI business logic into `tools/launcher/task_checkout_handler.py`. Wire them with an explicit in-process handler list; do not introduce plugins, dynamic registration, event bus, or message-team behavior.

**Tech Stack:** Python standard library, existing `tools/launcher/app_server.py` client, existing Bash launcher, pytest/unittest, fake Codex integration tests.

---

## Current Bottleneck

`tools/launcher/instance_daemon.py` currently does too much:

- daemon lifecycle: start, stop, status, run loop;
- runtime foundation: app-server connection, main-thread bind, notification reading, ready state, pid/log/state;
- Task TUI business: completed-turn filtering, task snapshot reading, STOP prompt rendering, checkout `turn/start`, task-specific state.

That makes daemon look owned by Task TUI. The first daemon-team task is to move forward by replacing this all-in-one structure with a clear module boundary, not by adding wrappers or compatibility layers.

## Target File Structure

Create:

- `tools/launcher/daemon_core.py`
  - daemon runtime path helpers;
  - `DaemonContext`;
  - `DaemonState`;
  - app-server main-thread binding;
  - notification dispatch loop;
  - `start_daemon`, `stop_daemon`, `daemon_status`, `run_daemon`;
  - no imports from `env.domain.task_management` or `env.domain.task_tui`.

- `tools/launcher/task_checkout_handler.py`
  - imports `task_management` and `task_tui`;
  - parses real `turn/completed` notifications;
  - filters main-thread completed user-origin turns;
  - builds STOP Task TUI prompt;
  - sends app-server `turn/start`;
  - records daemon-origin turn id and task checkout handler state.

- `tests/test_daemon_core_decoupling.py`
  - architecture boundary tests.

- `tests/test_daemon_core.py`
  - daemon state, lifecycle, binding, and run loop tests.

- `tests/test_task_checkout_handler.py`
  - Task Checkout Handler filter and send-path tests.

- `tests/test_instance_daemon_entrypoint.py`
  - thin entrypoint wiring tests.

Modify:

- `tools/launcher/instance_daemon.py`
  - keep CLI command parsing;
  - import daemon core;
  - import Task Checkout Handler;
  - pass `[TaskCheckoutHandler()]` to daemon core for `run`;
  - expose existing command functions only if needed by tests, delegating to daemon core.

- `tests/test_stop_task_daemon.py`
  - delete after its coverage is moved into the focused daemon core and task checkout handler tests.
  - do not keep a compatibility smoke test for the old all-in-one module boundary.

- `tests/test_buddyswitch_launcher.py`
  - update state assertions from old task-specific top-level fields to the new handler-owned state location.

Do not modify:

- `tools/launcher/task_input_context.py`
- `scripts/env/domain/task_tui.py`, except if tests expose a real renderer bug unrelated to the split.
- `scripts/env/domain/task_management.py`
- launcher thread bootstrap behavior.

## State Shape

Use one state file at the existing path:

```text
<instance_root>/runtime/daemon/state.json
```

Target shape:

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
  "last_error": {
    "origin_turn_id": "turn-user-1",
    "handler": "task_checkout",
    "message": "turn/start failed",
    "at": "2026-05-28T00:00:00Z"
  },
  "handlers": {
    "task_checkout": {
      "last_origin_turn_id": "turn-user-1",
      "last_checkout_turn_id": "turn-daemon-1",
      "last_error": null
    }
  }
}
```

Rules:

- `daemon_origin_turn_ids`, `ready`, and top-level `last_error` are daemon generic state.
- `handlers.task_checkout.*` is Task Checkout Handler state.
- Do not keep old top-level `last_origin_turn_id` / `last_stop_tui_turn_id` as compatibility mirrors.
- Preserve existing user-visible behavior through CLI and status; internal state tests should move to the clean shape.

## Task 1: Add Boundary And Core Tests First

**Files:**

- Create: `tests/test_daemon_core_decoupling.py`
- Create: `tests/test_daemon_core.py`

- [ ] **Step 1: Add architecture import boundary test**

Write a test that imports `tools/launcher/daemon_core.py` while blocking `env.domain.task_management` and `env.domain.task_tui`. Expected red result before implementation: `daemon_core.py` does not exist.

- [ ] **Step 2: Add AST import ownership test**

Write a test that scans `tools/launcher/daemon_core.py`, `tools/launcher/instance_daemon.py`, and `tools/launcher/task_checkout_handler.py`. Expected rule:

- `daemon_core.py` has no Task TUI imports or task business strings;
- `task_checkout_handler.py` is the daemon-side module allowed to import `task_management` and `task_tui`;
- `instance_daemon.py` may import `task_checkout_handler` only to build the explicit default handler list.

- [ ] **Step 3: Add daemon core state tests**

Move generic state tests out of `tests/test_stop_task_daemon.py` into `tests/test_daemon_core.py` and adjust them to the target state shape.

- [ ] **Step 4: Add daemon core dispatch tests**

Use fake handlers and fake clients to prove:

- notifications are dispatched to handlers;
- an empty handler list does not send `turn/start`;
- handler exceptions record `last_error` and the loop continues.

- [ ] **Step 5: Run red tests**

```bash
python3 -m pytest tests/test_daemon_core_decoupling.py tests/test_daemon_core.py -q
```

Expected: fails because `daemon_core.py` does not exist and old state/loop still live in `instance_daemon.py`.

## Task 2: Extract Daemon Core

**Files:**

- Create: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/instance_daemon.py`

- [ ] **Step 1: Move generic constants and helpers**

Move these from `instance_daemon.py` to `daemon_core.py`:

- daemon runtime path helpers;
- pid/log/state helpers;
- pid liveness and termination helpers;
- `_utc_now`;
- `_string_field`;
- `_notification_turn_id`;
- daemon constants that are not Task TUI-specific.

- [ ] **Step 2: Move `DaemonContext` and `load_daemon_context`**

Keep app-server socket path resolution unchanged. `daemon_core.py` may import `app_server`; it must not import task modules.

- [ ] **Step 3: Replace task-specific state methods with generic methods**

Keep:

- `is_daemon_origin_turn(turn_id)`;
- `record_daemon_origin_turn(turn_id)`;
- `record_ready(pid, main_thread_id)`;
- `ready_for(pid, main_thread_id)`;
- `record_error(origin_turn_id, message, handler=None)`;
- `handler_state(handler_name)`;
- `update_handler_state(handler_name, values)`;
- `record_handler_error(handler_name, origin_turn_id, message)`.

Remove from daemon core:

- `record_stop_tui_turn`;
- any method name containing `stop_tui`, `task_tui`, or task semantics.

- [ ] **Step 4: Move binding and lifecycle**

Move:

- `bind_main_thread`;
- `daemon_status`;
- `start_daemon`;
- `stop_daemon`;
- core `run_daemon`.

`start_daemon(...)` must still spawn the existing entrypoint path, not `daemon_core.py`, so the shell command remains stable.

- [ ] **Step 5: Implement explicit handler dispatch**

`run_daemon(instance_json, handlers)` should:

1. load context and state;
2. connect with `app_server.AppServerClient(..., client_name="buddyswitch_daemon")`;
3. bind main thread;
4. record ready;
5. read notifications forever;
6. ignore idle timeout;
7. dispatch every notification to each handler in the explicit list;
8. catch handler exceptions, record error, continue;
9. return nonzero only on startup or fatal app-server failure.

- [ ] **Step 6: Make `instance_daemon.py` a thin command entrypoint**

Keep command names and JSON output. Delegate:

- `start` -> `daemon_core.start_daemon(...)`;
- `stop` -> `daemon_core.stop_daemon(...)`;
- `status` -> `daemon_core.daemon_status(...)`;
- `run` -> `daemon_core.run_daemon(..., handlers=[TaskCheckoutHandler()])`.

- [ ] **Step 7: Run focused core tests**

```bash
python3 -m pytest tests/test_daemon_core_decoupling.py tests/test_daemon_core.py -q
```

Expected: pass before moving Task Checkout Handler tests.

## Task 3: Extract Task Checkout Handler

**Files:**

- Create: `tools/launcher/task_checkout_handler.py`
- Create: `tests/test_task_checkout_handler.py`
- Modify: `tools/launcher/instance_daemon.py`
- Delete after coverage migration: `tests/test_stop_task_daemon.py`

- [ ] **Step 1: Add handler filter tests**

Write tests from the test plan using real nested Codex `turn/completed` notification shape.

- [ ] **Step 2: Move completed-turn parser**

Move `completed_turn_for_stop_tui(...)` logic into `task_checkout_handler.py`. Rename to a task-checkout name such as `completed_turn_for_checkout(...)`.

- [ ] **Step 3: Add send-path tests**

Test that accepted notification causes one `turn/start`, uses current thread and permissions, records daemon-origin turn id, and writes `handlers.task_checkout.last_checkout_turn_id`.

- [ ] **Step 4: Move STOP prompt send logic**

Move `send_stop_task_tui(...)` into `task_checkout_handler.py`. It should:

1. read snapshot with `task_management.current_snapshot(...)`;
2. render prompt with `task_tui.render_stop_task_tui(...)`;
3. call `client.request("turn/start", ...)`;
4. extract returned turn id;
5. call daemon state generic origin and handler-state methods;
6. record handler error and return `False` on app-server errors.

- [ ] **Step 5: Implement `TaskCheckoutHandler`**

Use a concrete class with:

```python
name = "task_checkout"

def handle_notification(self, context, state, client, notification) -> bool:
    ...
```

No base class or plugin registry is needed in Step 1.

- [ ] **Step 6: Wire default handler list**

`instance_daemon.py run` should pass exactly:

```python
[task_checkout_handler.TaskCheckoutHandler()]
```

- [ ] **Step 7: Run handler tests**

```bash
python3 -m pytest tests/test_task_checkout_handler.py -q
```

Expected: pass.

## Task 4: Update Entry Point And Launcher Integration Tests

**Files:**

- Create: `tests/test_instance_daemon_entrypoint.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Delete after coverage migration: `tests/test_stop_task_daemon.py`

- [ ] **Step 1: Test entrypoint wiring**

Assert that `instance_daemon.py` delegates `run` to daemon core with Task Checkout Handler in the explicit handler list.

- [ ] **Step 2: Update daemon state assertions**

Replace old assertions:

- `last_origin_turn_id`
- `last_stop_tui_turn_id`

with:

- `handlers.task_checkout.last_origin_turn_id`
- `handlers.task_checkout.last_checkout_turn_id`

- [ ] **Step 3: Delete old all-in-one daemon test file**

After `tests/test_daemon_core.py` and `tests/test_task_checkout_handler.py` cover the moved behavior, delete:

```text
tests/test_stop_task_daemon.py
```

Do not leave a compatibility test that imports old task-specific functions from `instance_daemon.py`.

- [ ] **Step 4: Keep launcher lifecycle tests green**

Run the daemon/launcher subset:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'daemon or bootstrap' -q
```

Expected: pass.

- [ ] **Step 5: Keep fake Codex event-stream tests green**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'real_completed_event_triggers_one_stop_task_tui_prompt or daemon_origin_completion_real_shape_does_not_loop or daemon_ignores_other_thread_real_completion_in_fake_codex or requires_daemon_thread_resume_before_notifications' -q
```

Expected: pass.

## Task 5: Remove Old Coupling And Dead Structure

**Files:**

- Modify: `tools/launcher/instance_daemon.py`
- Modify: tests as needed.

- [ ] **Step 1: Remove direct task imports from daemon entry/core**

`instance_daemon.py` should not import `task_management` or `task_tui` directly. `daemon_core.py` must not import or mention them.

- [ ] **Step 2: Remove old task-specific functions from daemon core**

Delete these from daemon core / entrypoint:

- `completed_turn_for_stop_tui`;
- `send_stop_task_tui`;
- task-specific state methods;
- any old top-level state compatibility mirror.

- [ ] **Step 3: Keep thin wrapper only when it is the real command boundary**

Allowed: `instance_daemon.py` as CLI entrypoint.

Not allowed:

- compatibility wrapper modules that keep old all-in-one behavior alive;
- duplicate old and new dispatch paths;
- feature flags that switch between old and new daemon behavior.

- [ ] **Step 4: Run architecture boundary tests again**

```bash
python3 -m pytest tests/test_daemon_core_decoupling.py -q
```

Expected: pass.

## Task 6: Regression Verification

**Files:**

- No new feature files.

- [ ] **Step 1: Run focused daemon suite**

```bash
python3 -m pytest \
  tests/test_daemon_core_decoupling.py \
  tests/test_daemon_core.py \
  tests/test_task_checkout_handler.py \
  tests/test_instance_daemon_entrypoint.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run app-server and task input regression suites**

```bash
python3 -m pytest \
  tests/test_app_server_client.py \
  tests/test_task_input_context.py \
  -q
```

Expected: pass.

- [ ] **Step 3: Run launcher integration suite or relevant subset**

Shortest required subset:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k 'daemon or bootstrap or input' -q
```

Preferred final run when time permits:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected: pass.

- [ ] **Step 4: Static source check**

```bash
rg -n 'task_tui|task_management|stop_tui|render_stop_task_tui|current_snapshot' tools/launcher/daemon_core.py tools/launcher/instance_daemon.py
```

Expected:

- no matches in `daemon_core.py`;
- no direct `task_tui` or `task_management` imports in `instance_daemon.py`;
- `instance_daemon.py` may mention `task_checkout_handler` only as explicit handler wiring.

- [ ] **Step 5: Git pollution check**

```bash
git status --short
```

Expected: changes only inside the `fea-daemon` worktree.

## Non-Goals

- Do not build a plugin system.
- Do not add dynamic handler registration.
- Do not add a generic event bus or workflow engine.
- Do not implement message-team behavior.
- Do not change Task TUI prompt wording unless an existing test exposes a required behavior bug.
- Do not migrate input Task TUI into daemon.
- Do not move launcher thread bootstrap into daemon.
- Do not add daemon-side rollout repair.
- Do not keep old and new daemon paths behind a flag.

## Review Checklist

- Boundary: daemon core has no direct task imports or task business words.
- Behavior: STOP Task TUI still triggers once for completed user-origin main-thread turns.
- Loop guard: daemon-origin completions do not trigger another STOP prompt.
- Launcher boundary: start/clear bootstrap still happens before daemon `thread/resume`.
- State: generic daemon state and task checkout state have clear ownership.
- Forward principle: old all-in-one daemon logic is removed, not wrapped.
- Scope: no new product behavior, no message handler, no plugin mechanism.
- Verification: focused tests and launcher integration subset are explicitly listed.
