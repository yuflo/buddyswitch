# Phase 03 Parent Idle Interrupt Submit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:systematic-debugging` for root-cause discipline and `superpowers:test-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `interrupt_submit_parent` so idle/no-active-turn parent threads still receive a Task Sys parent frame, while runtime failures do not leave tasks silently stuck in `parent_processing`.

**Architecture:** Keep Task Sys parent handoff as `side result -> parent instruction -> runtime executor -> parent_processing state`. The runtime executor owns physical interrupt/submit semantics; the Task Sys domain owns durable task state.

**Tech Stack:** `tools/launcher/task_sys_runtime.py`, `scripts/env/domain/task_sys.py`, `scripts/env/tools/task_sys/_impl.py`, `tests/test_task_sys_runtime_executor.py`, `tests/test_task_sys_substrate.py`, `tests/test_task_sys_side_processing.py`, pytest, `py_compile`, scoped residue scans.

---

## 1. Background And Goal

This phase resolves `docs/memo/2026-06-29-task-sys-interrupt-submit-parent-idle-bug.md`.

Current bottleneck:

- `task_sys.need_parent(params.interrupt=true)` produces an `interrupt_submit_parent` instruction.
- `task_sys.parent_handoff_instruction()` currently persists the task as `parent_processing` before the runtime submit happens.
- `tools/launcher/task_sys_runtime.py::_execute_submit_parent(interrupt=True)` calls `app_server.interrupt_turn()` before `submit_turn()`.
- `app_server.interrupt_turn()` raises `AppServerUnavailableError("thread ... has no active in-progress turn")` when the parent thread is idle.
- The exception prevents parent submit and can leave the task as `parent_processing` without a parent turn.

Observable behavior change:

- Parent idle plus `interrupt_submit_parent` becomes interrupt no-op plus parent frame submit.
- Parent running plus `interrupt_submit_parent` still interrupts first, then submits.
- Active/no-active-turn race plus `interrupt_submit_parent` becomes interrupt no-op plus parent frame submit.
- Runtime failures before parent submit leave the task in `needs_parent`, not orphaned `parent_processing`.

## 2. Code Current-State Investigation

Relevant files:

- `tools/launcher/task_sys_runtime.py`
  - `_execute_submit_parent(context, instruction, interrupt=True)` unconditionally calls `app_server.interrupt_turn()` and raises on any interrupt failure.
  - Existing test `test_execute_interrupt_submit_parent_interrupts_before_submit` covers only successful interrupt.
- `tools/launcher/app_server.py`
  - `interrupt_turn()` raises `AppServerUnavailableError("thread {thread_id} has no active in-progress turn")` when there is no active turn id.
  - `input_turn()` uses a related active/no-in-progress error string: `"thread {thread_id} is active but no in-progress turn was found"`.
- `tools/launcher/daemon_core.py`
  - Old `DaemonRuntime.submit_parent_prompt(..., interrupt_policy="ensure_stopped")` is a working reference:
    - idle parent: submit without interrupt;
    - running parent: interrupt, wait idle, submit;
    - no-active-turn race: wait idle, submit.
- `scripts/env/domain/task_sys.py`
  - `parent_handoff_instruction(task_id)` currently moves `needs_parent` to `parent_processing` before returning the runtime instruction.
- `scripts/env/tools/task_sys/_impl.py`
  - `need_parent()` records side result, asks for parent instruction, executes runtime, then reads the task record.

Old path or residue path:

- Do not restore `request_parent_message_handling`.
- Do not restore `[MESSAGE NEEDS PARENT]` raw parent prompts.
- Do not route through `DaemonRuntime.submit_parent_prompt()` as a compatibility wrapper.

Existing coverage and gaps:

- Existing runtime executor coverage proves successful interrupt before submit.
- Missing runtime executor coverage for idle parent and no-active-turn race.
- Existing side-processing coverage proves `task_sys.need_parent` reaches parent runtime, but does not cover runtime failure rollback.
- Existing substrate coverage expects `parent_handoff_instruction()` to mark `parent_processing` before runtime; this must be replaced with explicit post-submit state transition coverage.

## 3. Root Cause And Hypothesis

Root cause:

- The new Task Sys runtime executor copied the "interrupt before submit" happy path but did not copy the old daemon `ensure_stopped` semantics for idle/no-active-turn parent state.
- The Task Sys domain persists `parent_processing` at instruction construction time, before runtime actuation has evidence of a submitted parent turn.

Working reference:

- `DaemonRuntime._ensure_parent_stopped()` checks parent activity first and treats no-active-turn races as recoverable before submit.

Hypothesis:

- If `_execute_submit_parent(interrupt=True)` treats only no-active-turn `AppServerUnavailableError` as a recoverable interrupt no-op, submit will run for idle/race cases without weakening real interrupt failures.
- If `parent_processing` is recorded only after `_execute_parent_instruction()` returns a parent runtime result, failed runtime actuation will leave the task in `needs_parent` and avoid orphaned parent state.

## 4. Solution Design

Minimal direct change:

1. Add failing runtime executor tests:
   - idle parent interrupt failure message -> submit still runs, no `interrupted_turn_id`;
   - active/no-in-progress race message -> submit still runs, no `interrupted_turn_id`;
   - existing running-parent test remains unchanged.
2. Add failing Task Sys domain/tool tests:
   - `parent_handoff_instruction()` builds a parent instruction but leaves task `needs_parent`;
   - new domain transition, `record_parent_handoff_started(task_id)`, marks `parent_processing`;
   - `task_sys.need_parent` marks `parent_processing` only after daemon runtime execution succeeds;
   - failed daemon runtime execution leaves task `needs_parent`.
3. Implement `_is_no_active_turn_interrupt_error()` in `tools/launcher/task_sys_runtime.py`.
4. In `_execute_submit_parent()`, catch `app_server.AppServerUnavailableError` from `interrupt_turn()` only when it is a no-active-turn condition, then continue to `submit_turn()`.
5. Move durable parent-processing transition out of `parent_handoff_instruction()` and into a new explicit domain function called after successful runtime execution from `scripts/env/tools/task_sys/_impl.py`.

No compatibility or abstraction:

- Do not call old `DaemonRuntime.submit_parent_prompt()`.
- Do not introduce a scheduler, retry engine, or workflow status framework.
- Do not silently swallow non-no-active-turn interrupt errors.

Boundary with other memo phases:

- Phase 01 Web API cleanup is already complete.
- Phase 02 side-frame prompt is already complete.
- This phase does not change side prompt policy or WebUI routes.

## 5. Test Plan

### Red Tests

Run after adding tests and before production edits:

```bash
python -m pytest -q tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests::test_execute_interrupt_submit_parent_idle_parent_submits_without_interrupted_turn tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests::test_execute_interrupt_submit_parent_no_active_turn_race_submits_without_interrupted_turn
```

Expected red result:

- Both fail because `_execute_submit_parent()` propagates `AppServerUnavailableError` and never calls `submit_turn()`.

```bash
python -m pytest -q tests/test_task_sys_substrate.py::TaskSysSubstrateTests::test_parent_instruction_from_need_parent_task_stays_parent_ready_until_runtime_start tests/test_task_sys_substrate.py::TaskSysSubstrateTests::test_record_parent_handoff_started_marks_parent_processing
```

Expected red result:

- The renamed first test fails because `parent_handoff_instruction()` still writes `parent_processing`.
- The second test fails because `record_parent_handoff_started()` does not exist.

```bash
python -m pytest -q tests/test_task_sys_side_processing.py::TaskSysSideProcessingTests::test_task_sys_need_parent_tool_leaves_task_parent_ready_when_parent_runtime_fails
```

Expected red result:

- The test fails because runtime failure leaves the task as `parent_processing`.

### Focused Tests

After implementation:

```bash
python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py
```

Expected:

- Runtime idle/race/running coverage passes.
- Domain state transition coverage passes.
- Tool-level success and failure behavior passes.

### Broader Relevant Tests

Run the focused Task Sys runtime/substrate/side suites plus the existing message, env-tool response/schema/semantic, role-auth, daemon-decoupling, daemon-service, and runtime-broker boundary suites that cover parent handoff.

Expected:

- Existing Task Sys/daemon/message boundary tests remain green.

### Product Smoke

Manual product smoke is optional for this phase because focused tests exercise the runtime failure precisely without starting long-lived services.

If run later, service lifecycle must be inspected first per `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

### Residue Scans

```bash
rg -n "request_parent_message_handling|\\[MESSAGE NEEDS PARENT\\]|message\\.mark\\(needs_parent\\)|parent_prompt_submitted" tools scripts tests -S
rg -n "submit_parent_prompt\\(" tools/launcher scripts/env tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py -S
```

Expected:

- No restored old IM direct parent prompt path.
- `submit_parent_prompt(` remains only in legacy daemon physical actuator tests/fakes, not Task Sys runtime implementation.

### Compile / Diff Checks

```bash
python -m py_compile tools/launcher/task_sys_runtime.py scripts/env/domain/task_sys.py scripts/env/tools/task_sys/_impl.py
git diff --check
```

Expected:

- Both pass.

## 6. Acceptance Criteria

Behavior acceptance:

- `interrupt_submit_parent` with parent idle still submits a `task_sys.parent_frame` and returns parent `turn_id`.
- `interrupt_submit_parent` with parent running still interrupts before submit and returns `interrupted_turn_id`.
- `interrupt_submit_parent` with active/no-in-progress race still submits and omits `interrupted_turn_id`.
- Non-no-active-turn interrupt failures still propagate and do not submit.

State acceptance:

- `parent_handoff_instruction()` no longer marks `parent_processing` before runtime submit.
- Successful `task_sys.need_parent` runtime execution marks the task `parent_processing`.
- Failed parent runtime execution leaves the task `needs_parent` with `active_processor=None`.
- No runtime object files under `buddyswitch/objects/**` are edited directly.

UI / CLI / WebUI observable acceptance:

- WebUI research/implementation IM requests that side routes to `need_parent(interrupt=true)` can start a parent turn even when the parent was idle.
- Existing CLI/Web Task Sys ingress contracts remain unchanged.

Live surface no-residue acceptance:

- No old raw IM needs-parent prompt path is restored.
- No business handler directly submits parent prompts.
- Task Sys runtime remains the parent handoff owner.

Actual Verification:

- Red checks before production edits:
  - `python -m pytest -q tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests::test_execute_interrupt_submit_parent_idle_parent_submits_without_interrupted_turn tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests::test_execute_interrupt_submit_parent_no_active_turn_race_submits_without_interrupted_turn`
  - Result: `2 failed`; both failures propagated `AppServerUnavailableError` before `submit_turn()`.
  - `python -m pytest -q tests/test_task_sys_substrate.py::TaskSysSubstrateTests::test_parent_instruction_from_need_parent_task_stays_parent_ready_until_runtime_start tests/test_task_sys_substrate.py::TaskSysSubstrateTests::test_record_parent_handoff_started_marks_parent_processing`
  - Result: `2 failed`; `parent_handoff_instruction()` still persisted `parent_processing`, and `record_parent_handoff_started()` did not exist.
  - `python -m pytest -q tests/test_task_sys_side_processing.py::TaskSysSideProcessingTests::test_task_sys_need_parent_tool_leaves_task_parent_ready_when_parent_runtime_fails`
  - Result: `1 failed`; runtime failure left the task as `parent_processing`.
- Focused green checks:
  - `python -m pytest -q tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests::test_execute_interrupt_submit_parent_idle_parent_submits_without_interrupted_turn tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests::test_execute_interrupt_submit_parent_no_active_turn_race_submits_without_interrupted_turn tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests::test_execute_interrupt_submit_parent_interrupts_before_submit`
  - Result: `3 passed`.
  - `python -m pytest -q tests/test_task_sys_substrate.py::TaskSysSubstrateTests::test_parent_instruction_from_need_parent_task_stays_parent_ready_until_runtime_start tests/test_task_sys_substrate.py::TaskSysSubstrateTests::test_record_parent_handoff_started_marks_parent_processing`
  - Result: `2 passed`.
  - `python -m pytest -q tests/test_task_sys_side_processing.py::TaskSysSideProcessingTests::test_task_sys_need_parent_tool_executes_parent_instruction_via_daemon_context tests/test_task_sys_side_processing.py::TaskSysSideProcessingTests::test_task_sys_need_parent_tool_leaves_task_parent_ready_when_parent_runtime_fails`
  - Result: `2 passed`.
- Final phase verification:
  - `python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py`
  - Result: `25 passed, 16 subtests passed`.
  - Broader Task Sys/message/env-tool/daemon/runtime-broker boundary pytest set.
  - Result: `109 passed, 483 subtests passed`.
  - `python -m py_compile tools/launcher/task_sys_runtime.py scripts/env/domain/task_sys.py scripts/env/tools/task_sys/_impl.py`
  - Result: pass.
  - `rg -n "request_parent_message_handling|\\[MESSAGE NEEDS PARENT\\]|message\\.mark\\(needs_parent\\)|parent_prompt_submitted" tools scripts tests -S`
  - Result: no hits.
  - `rg -n "submit_parent_prompt\\(" tools/launcher scripts/env tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py -S`
  - Result: only `tools/launcher/daemon_core.py` legacy actuator definition and `tests/test_task_sys_side_processing.py` guard fake.

## Actual Changes

- Added `_is_no_active_turn_interrupt_error()` in `tools/launcher/task_sys_runtime.py`.
- Updated `_execute_submit_parent(interrupt=True)` so only idle/no-active-turn `AppServerUnavailableError` is treated as a no-op interrupt; submit still runs and no `interrupted_turn_id` is returned.
- Kept non-no-active-turn interrupt failures as hard failures.
- Changed `scripts/env/domain/task_sys.py::parent_handoff_instruction()` to build the parent instruction without persisting `parent_processing`.
- Added `record_parent_handoff_started(task_id)` to mark `parent_processing` explicitly after runtime submit succeeds.
- Updated `scripts/env/tools/task_sys/_impl.py::need_parent()` to call `record_parent_handoff_started()` only after `_execute_parent_instruction()` returns.
- Added runtime tests for idle parent and no-active-turn race.
- Added domain tests for pre-submit `needs_parent` state and post-submit `parent_processing` transition.
- Added tool-level regression coverage proving runtime failure leaves the task `needs_parent`.

## Acceptance Status

Accepted for Phase 03. `interrupt_submit_parent` now submits parent frames for idle/no-active-turn parent states, still interrupts running parents first, and failed runtime actuation no longer leaves a task orphaned in `parent_processing`.

## 7. Appendix

Search commands used during investigation:

```bash
rg -n "parent_handoff_instruction\\(|parent_processing|needs_parent" scripts/env tools tests -S
rg -n "interrupt_submit_parent|_execute_submit_parent|AppServerUnavailableError|interrupt_turn" tools/launcher tests scripts/env -S
nl -ba tools/launcher/daemon_core.py | sed -n '999,1080p'
```

Key code references:

- `tools/launcher/task_sys_runtime.py::_execute_submit_parent()`
- `tools/launcher/app_server.py::interrupt_turn()`
- `scripts/env/domain/task_sys.py::parent_handoff_instruction()`
- `scripts/env/tools/task_sys/_impl.py::need_parent()`
- Old daemon-service `ensure_stopped` reference tests

Decision record:

- Catch only no-active-turn `AppServerUnavailableError` as recoverable. Other interrupt failures still fail the runtime instruction.
- Do not reuse old daemon submit helpers because that would route the new Task Sys runtime through a compatibility layer and blur ownership.
