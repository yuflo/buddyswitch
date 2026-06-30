# Task Sys Side-Frame Lifecycle Fix Plan

Date: 2026-06-30

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` to implement this plan task-by-task. Use `superpowers:verification-before-completion` before claiming completion. Steps use checkbox (`- [ ]`) syntax for tracking.

## Task Goal And Standard

Fix the Task Sys side-frame lifecycle as a forward replacement, not a compatibility layer.

The target product contract is:

```text
External/user source
  -> Task Sys task
  -> one fresh ephemeral side thread for one task_sys.side_frame
  -> side either completes the source task or hands it to parent
  -> side thread is retired and unregistered
  -> task state is explicit, observable, and recoverable
```

This plan replaces the current reusable side-thread behavior. It must not preserve a second long-lived reuse path for Task Sys side frames.

The standard is:

- Programmatic lifecycle stages must not lose source/task facts, must not report false success, must not leak side-thread resources, and must leave a recoverable state on failure.
- Codex LLM execution after a side turn starts must not be runtime-retried by launching another side thread.
- Tool/runtime feedback must be clear enough for the LLM to decide within the active frame.
- Live surfaces must stop teaching that Task Sys side frames reuse existing side threads.
- Verification must prove behavior, surface cleanup, and resource cleanup.

## Bitter Lessons Applied

This plan intentionally applies the durable lessons in `docs/bitter/`:

- `2026-05-18-tool-skill-layering-principles.md`
  - Do not compensate for weak runtime/tool contracts with prompt bulk.
  - Tool/runtime feedback must state actual effect, state change, failure reason, retryability, and state unchanged guarantees.
- `2026-05-26-test-resource-lifecycle-principles.md`
  - Any service-starting smoke must include process/resource ownership and post-run residual checks.
  - Broad live verification is blocked until lifecycle cleanup is proven.
- `2026-05-28-parallel-change-boundary-principles.md`
  - Keep the change in the owning Task Sys/runtime lifecycle boundary.
  - Do not route this through scattered interface-specific helpers.
- `2026-06-02-residue-cleanup-principles.md`
  - Semantic replacement requires behavior tests and scoped live-surface residue scans.
  - Historical docs are evidence; live prompts, tests, tools, and role/runtime guidance must be current.
- `2026-06-02-wrong-boundary-narrowness-principles.md`
  - Small fixes at the wrong shared boundary are still wrong.
  - Runtime lifecycle ownership belongs in Task Sys runtime/domain boundaries, not in each ingress handler.
- `2026-06-25-built-in-product-interface-principles.md`
  - Task Sys is the product core; CLI, Web, daemon handlers, and env tools are projections.
  - Product state semantics must live in Task Sys domain/runtime, not in incidental interface adapters.
- `2026-06-25-end-to-end-contract-slice-principles.md`
  - Unit slices are not enough.
  - The final acceptance must prove a consumer-visible source can flow through wake, side frame, reply/handoff, and status without residue.

## Current Code Review Findings

### Finding 1: Task Sys Runtime Still Reuses Open Side Threads

`tools/launcher/task_sys_runtime.py::_execute_start_side()` currently calls:

```text
side_thread_registry.find_open_side_thread(...)
```

If an open row exists, it sends the next side frame through `app_server.input_turn()` instead of creating a fresh side thread.

That is the direct source of the observed stale-thread failures:

- old actor: registry said open, app-server returned `thread not loaded`;
- fresh actor second IM: first task closed, registry still had an open ephemeral side thread, second task hit `ephemeral threads do not support thread/turns/list`.

### Finding 2: Task Close And Side Thread Retirement Are Separate

`scripts/env/domain/task_sys.py::record_task_close()` only changes the durable Task Sys task record.

It does not:

- close the physical side thread;
- unregister `instance.json.side_threads[]`;
- record cleanup status;
- prevent the side thread from being reused later.

`scripts/env/tools/task_sys/_impl.py::close()` and `need_parent()` call Task Sys domain transitions but do not retire the side thread after side completion or side handoff.

### Finding 3: There Is No Side Runtime Failure State

`TASK_STATUSES` currently has:

```text
new, side_processing, closed, needs_parent, parent_processing, checkpoint
```

A side dispatch failure leaves the task in `side_processing`. That is wrong because the side worker is no longer actually processing the task.

The runtime needs explicit non-success terminal or recovery states for side lifecycle failures.

### Finding 4: Programmatic Dispatch And LLM Execution Are Not Separated In State

Current execution treats `start_side` as one opaque runtime instruction.

For lifecycle correctness, it must distinguish:

```text
before side turn starts
  -> programmatic runtime dispatch phase

after side turn_id exists
  -> Codex LLM execution phase
```

This boundary decides whether bounded runtime retry is safe.

### Finding 5: Status Projects Active Task Residue, But Not Failed/Recoverable Task State

`daemon_core._task_sys_status_payload()` reports active task summaries only.

Once side failures move out of active `side_processing`, status must still expose failed/recoverable task summaries so operators can see:

- task id;
- source type/ref;
- failure stage;
- error;
- retryable;
- cleanup result;
- updated timestamp.

### Finding 6: Existing Tests Cover Slices, Not The Full Lifecycle Contract

Existing tests prove:

- side frame prompt text exists;
- `start_side` can call physical `side_start`;
- registry can register/unregister rows;
- parent runtime failure leaves task `needs_parent`.

Missing coverage:

- stale open registry row is not reused by Task Sys;
- every Task Sys side frame gets a fresh side thread;
- side close/handoff retires the side thread;
- runtime dispatch failure performs bounded fresh retry then records explicit failure;
- side turn started means no runtime retry;
- failed side lifecycle status remains host-visible after it is no longer active;
- live surfaces no longer teach reusable Task Sys side frames.

## Architecture Decision

Replace Task Sys side-frame reuse with a single-task side lease model.

```text
Task Sys domain
  owns durable task states, failure metadata, and active/recoverable task summaries

Task Sys runtime executor
  owns physical side-thread creation, dispatch attempts, side lease registration, and cleanup

Task Sys env tool
  owns LLM-facing task result operations and clear feedback after close/need_parent/checkpoint_update

Daemon / Web status
  projects active and recoverable Task Sys state without owning it

Manual side CLI/Web side routes
  may keep their human side-conversation behavior, but must not define Task Sys side-frame semantics
```

Do not create:

- a reusable side-thread pool;
- a compatibility fallback that retries old open side threads;
- a generic workflow engine;
- a daemon-owned second Task Sys state machine;
- a watcher that auto-closes tasks from message disposition;
- a broad retry framework;
- a prompt-only fix.

## Lifecycle Model

### Stage 1: Create Side Thread

Runtime creates one fresh ephemeral side thread for the current task.

Expected behavior:

```text
thread/fork succeeds
  -> create a side lease row bound to task_id and side_thread_id
  -> continue to Stage 2

thread/fork fails
  -> no side worker exists
  -> bounded fresh retry is allowed
  -> final failure records runtime_failed
```

### Stage 2: Initialize And Dispatch Side Frame

Runtime injects side boundary and sends the rendered `task_sys.side_frame`.

Expected behavior:

```text
turn_id returned
  -> side turn has started
  -> continue to Stage 3

failure before turn_id
  -> cleanup this side lease
  -> bounded fresh retry is allowed
  -> final failure records runtime_failed
```

### Stage 3: Codex LLM Side Execution

The side turn is now running. Runtime must not launch a new side thread as an automatic retry.

Expected behavior:

```text
side calls task_sys.close
  -> source task completed in side
  -> continue to Stage 4 cleanup

side calls task_sys.need_parent
  -> parent handoff is attempted through Task Sys runtime
  -> continue to Stage 4 cleanup after successful handoff or recorded recoverable parent-ready state

side produces no legal Task Sys result
  -> no runtime retry
  -> record side_no_result or side_timed_out through an explicit recovery path
  -> cleanup side lease
```

Tool/runtime feedback in this phase must be precise:

- success must say whether durable state changed and which task id changed;
- rejection must say why it was blocked and whether state changed;
- failures must provide retryability and recovery guidance;
- `ok=true` without state impact is insufficient for Task Sys frame operations.

### Stage 4: Retire Side Lease

Every successful or failed side lifecycle path retires the side lease.

Expected behavior:

```text
physical side_close succeeds
  -> unregister lease
  -> record cleanup ok

physical side_close fails because the side thread is gone/unloaded
  -> unregister lease anyway
  -> record best-effort close failure
  -> do not leave a reusable open row
```

Registry cleanup is mandatory for Task Sys side leases. Physical close is best effort.

## Durable State Model

Update Task Sys domain state with explicit lifecycle outcomes.

Recommended status set:

```text
new
side_processing
closed
needs_parent
parent_processing
checkpoint
runtime_failed
side_no_result
side_timed_out
```

`ACTIVE_TASK_STATUSES` should include only genuinely active work:

```text
new
side_processing
needs_parent
parent_processing
checkpoint
```

`RECOVERABLE_TASK_STATUSES` should include side lifecycle failures that need operator or controlled recovery:

```text
runtime_failed
side_no_result
side_timed_out
```

Failure metadata should be stored on the task record in a clear shape:

```json
{
  "failure_result": {
    "stage": "side_fork | side_inject | side_input | side_turn | side_cleanup",
    "processor": "side",
    "error": "short error string",
    "retryable": true,
    "attempts": 2,
    "last_side_thread_id": "thread-id-if-known",
    "cleanup": {
      "registry_unregistered": true,
      "physical_close_ok": false,
      "physical_close_error": "short error string"
    },
    "updated_at": "iso timestamp"
  }
}
```

Successful side completion should also retain cleanup metadata without changing the meaning of `closed`:

```json
{
  "close_result": {
    "processor": "side",
    "summary": "Handled in side.",
    "side_thread_id": "thread-id",
    "cleanup": {
      "registry_unregistered": true,
      "physical_close_ok": true
    },
    "updated_at": "iso timestamp"
  }
}
```

Keep the domain pure:

- Task Sys domain records task state and cleanup facts.
- It must not import `app_server`, daemon runtime, launcher shell helpers, or side registry internals.

## Side Lease Registry Model

Replace reusable open side rows for Task Sys with task-bound lease rows.

Minimum lease fields:

```json
{
  "thread_id": "thr-side",
  "parent_thread_id": "thr-main",
  "task_id": "task-im-message-created-...",
  "purpose": "task_sys.side_frame",
  "status": "open",
  "created_at": "iso timestamp",
  "updated_at": "iso timestamp"
}
```

Rules:

- A Task Sys lease belongs to one task.
- A Task Sys lease is never selected for another task.
- There is no Task Sys `find_open_side_thread()` reuse path.
- Unregister removes the task-bound lease after close, handoff, dispatch failure, or timeout.
- Manual side-conversation routes may retain their own side registry behavior, but Task Sys runtime must not consume manual side rows as reusable workers.

## Bounded Runtime Retry Policy

Only programmatic pre-turn phases may retry automatically.

Allowed bounded retry:

- side fork failure;
- side boundary injection failure;
- side frame input failure before a `turn_id` is returned;
- transient app-server unavailable errors before a side turn exists.

Not allowed:

- retry after `turn_id` exists;
- retry after side may have called tools;
- retry after any source-bound side effect may have happened;
- retry permission, schema, wrong-actor, malformed instruction, or role-action policy errors.

Default retry shape:

```text
max_attempts = 2
attempt 1: fresh side thread
attempt 2: cleanup attempt 1, fresh side thread
all attempts fail: runtime_failed
```

Each attempt must record:

- attempt number;
- stage;
- side_thread_id if known;
- error;
- cleanup outcome.

## Implementation Plan

### Task 1: Add Task Sys Failure States

**Files:**

- Modify: `scripts/env/domain/task_sys.py`
- Modify: `tests/test_task_sys_substrate.py`

- [x] Add `runtime_failed`, `side_no_result`, and `side_timed_out` to `TASK_STATUSES`.
- [x] Add `RECOVERABLE_TASK_STATUSES`.
- [x] Keep recoverable statuses out of `ACTIVE_TASK_STATUSES`.
- [x] Add `record_side_runtime_failure(task_id, failure)` that:
  - requires the task to be `side_processing`;
  - sets `status` to the requested failure status;
  - sets `active_processor` to `None`;
  - records `failure_result`;
  - preserves `source_type`, `source_ref`, `actor_target`, and `inbound_context`.
- [x] Add tests proving `runtime_failed` is not active but remains queryable as recoverable.
- [x] Add tests proving failed side runtime tasks cannot be `task_sys.close`d as success.

Focused verification:

```bash
python -m pytest -q tests/test_task_sys_substrate.py
python -m py_compile scripts/env/domain/task_sys.py
```

### Task 2: Replace Task Sys Reuse With Fresh Side Lease

**Files:**

- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `tools/launcher/side_thread_registry.py`
- Modify: `tests/test_task_sys_runtime_executor.py`
- Modify: `tests/test_side_thread_registry.py`

- [x] Extend registry rows with optional `task_id` and `purpose`.
- [x] Add a task-bound register function or parameters for Task Sys leases.
- [x] Keep manual `instance side` command compatibility only for manual side conversations; do not let Task Sys consume old open rows.
- [x] Remove `find_open_side_thread()` use from `task_sys_runtime._execute_start_side()`.
- [x] Add a failing test where `instance.json.side_threads[]` contains a stale open row and Task Sys still calls `app_server.side_start()`, not `input_turn()`.
- [x] Add a test proving two sequential `start_side` instructions create two different fresh side starts.

Focused verification:

```bash
python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_side_thread_registry.py
python -m py_compile tools/launcher/task_sys_runtime.py tools/launcher/side_thread_registry.py
```

### Task 3: Add Runtime Dispatch Retry And Failure Recording

**Files:**

- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `scripts/env/domain/task_sys.py`
- Modify: `tests/test_task_sys_runtime_executor.py`
- Modify: `tests/test_task_sys_substrate.py`

- [x] Split `start_side` execution into explicit attempt stages:
  - `side_fork`;
  - `side_inject`;
  - `side_input`;
  - `side_turn_started`.
- [x] Retry only failures before a side `turn_id` exists.
- [x] Use fresh side thread for each retry attempt.
- [x] Cleanup the failed attempt before the next attempt.
- [x] After all attempts fail, call the domain failure recorder with `runtime_failed`.
- [x] Include attempts, stage, error, side thread id, and cleanup result in the returned runtime payload.
- [x] Add tests for fork failure, inject/input failure before `turn_id`, and final `runtime_failed`.
- [x] Add a test proving no fresh retry happens once a `turn_id` has been returned.

Focused verification:

```bash
python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_sys_substrate.py
python -m py_compile tools/launcher/task_sys_runtime.py scripts/env/domain/task_sys.py
```

### Task 4: Retire Side Lease After Side Completion Or Handoff

**Files:**

- Modify: `scripts/env/tools/task_sys/_impl.py`
- Modify: `scripts/env/domain/task_sys.py`
- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `tests/test_task_sys_side_processing.py`
- Modify: `tests/test_task_sys_runtime_executor.py`

- [x] Provide a Task Sys runtime cleanup operation that can be called after side `task_sys.close` and `task_sys.need_parent`.
- [x] Make cleanup unregister the side lease even if physical `side_close` fails.
- [x] Record cleanup result in `close_result` or `side_result` metadata.
- [x] Ensure `task_sys.need_parent` cleans up the side lease after side has recorded the parent-ready result:
  - if parent runtime execution succeeds, task moves to `parent_processing`;
  - if parent runtime execution fails before submit, task remains recoverably `needs_parent`;
  - in both cases, the side lease is retired and the tool/runtime feedback exposes the parent runtime outcome.
- [x] Add tests proving `task_sys.close` from side retires the side lease.
- [x] Add tests proving `task_sys.need_parent` retires the side lease after parent handoff.
- [x] Add tests proving cleanup failure does not preserve an open reusable lease.

Focused verification:

```bash
python -m pytest -q tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py
python -m py_compile scripts/env/tools/task_sys/_impl.py scripts/env/domain/task_sys.py tools/launcher/task_sys_runtime.py
```

### Task 5: Make Tool Feedback Clear For LLM Execution

**Files:**

- Modify: `scripts/env/tools/task_sys/tool.py`
- Modify: `scripts/env/tools/task_sys/_impl.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_task_sys_side_processing.py`

- [x] Update `task_sys.close` response extra fields to expose:
  - `task_id`;
  - `task_status`;
  - `state_changed`;
  - `processor`;
  - `side_thread_id` when available;
  - cleanup result when available.
- [x] Update `task_sys.need_parent` response extra fields to expose parent runtime result and side cleanup result.
- [x] Update rejection/failure feedback to state whether Task Sys state changed.
- [x] Keep workflow sequencing out of tool definitions; the tool should describe atomic action semantics.
- [x] Add tests that assert response feedback is strong enough for host decision-making, not merely `ok=true`.

Focused verification:

```bash
python -m pytest -q tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_task_sys_side_processing.py
python -m py_compile scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py
```

### Task 6: Expose Recoverable Side Failures In Status

**Files:**

- Modify: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_daemon_service_contract.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_web_management.py`

- [x] Extend Task Sys status projection with recoverable task summaries.
- [x] Keep daemon status as a projection only; do not move state ownership into daemon.
- [x] Include failure metadata summary without raw message content.
- [x] Update Web actor console task projection to include recoverable count/summaries.
- [x] Add tests proving active and recoverable task counts are distinct.

Focused verification:

```bash
python -m pytest -q tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_task_sys_active_summary tests/test_web_management.py::WebManagementTests::test_actor_console_api_composes_runtime_task_sys_track_and_im_projection
python -m py_compile tools/launcher/daemon_core.py tools/launcher/web_management.py
```

### Task 7: Remove Live-Surface Residue For Reusable Task Sys Side Threads

**Files:**

- Review and modify these live surfaces during this task:
  - `tools/launcher/task_sys_runtime.py`
  - `tests/test_task_sys_runtime_executor.py`
  - `tests/test_buddyswitch_launcher.py`
  - `docs/spec/task-sys-memo-optimization/phase-02-side-frame-resource-boundary.md`
  - `docs/spec/task-sys-memo-optimization/99-final-acceptance.md`
  - `buddyswitch/skills/shared/task-management/SKILL.md`

- [x] Define old live semantics:
  - Task Sys may reuse an existing open side thread.
  - Resource boundary must be repeated because reused side threads do not receive boundary prompt again.
- [x] Define new live semantics:
  - Task Sys creates one fresh ephemeral side thread per side frame.
  - Side frame still carries resource policy because it is the current task contract, not because of reuse.
- [x] Add/update tests and scoped scans so live surfaces do not teach the old reuse model.
- [x] Do not edit historical memos just to erase history.
- [x] Keep current docs/spec history only if it is clearly historical and not used as current execution guidance.

Scoped residue scan:

```bash
rg -n "reuse|reused|existing side thread|find_open_side_thread|open side thread|side thread can be reused" \
  tools/launcher tests buddyswitch/skills docs/spec/task-sys-memo-optimization -S
```

Every remaining hit must be either:

- a test proving old reuse is rejected;
- a historical note outside live execution guidance;
- an implementation symbol that is not consumed by Task Sys runtime.

### Task 8: End-To-End Acceptance And Resource-Gated Smoke

**Files:**

- Modify: `docs/spec/task-sys-exploratory-acceptance/00-test-plan.md`
- Create or modify a focused smoke helper only after its lifecycle cleanup proof is in place.

- [x] Write one contract sentence:

```text
External IM send -> IM wake -> Task Sys side frame -> fresh side thread -> exact reply/close -> status active_count=0 and no Task Sys side lease remains.
```

- [x] Prove the sentence with a focused acceptance smoke after unit/integration tests pass.
- [x] Before running live smoke, inspect lifecycle cleanup per `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.
- [x] After live smoke, verify:
  - no test-owned actors are left running;
  - no test-owned side leases remain;
  - no unexpected `side_processing` tasks remain;
  - External IM reply is source-bound and acked.
- [x] Do not expand the matrix until the single loop passes with clean resources.
- [x] Do not claim product readiness without this acceptance loop. If the environment cannot safely run it, report the lifecycle blocker instead of marking the fix done.

Focused live verification gate:

```text
behavior passes + Task Sys residue count returns to baseline + host resources return to baseline
```

## Required Residue Scans

Run these before declaring implementation complete:

```bash
rg -n "find_open_side_thread\\(" tools/launcher/task_sys_runtime.py tests -S
```

Expected:

- no production Task Sys runtime use;
- only tests that prove old reuse is rejected, if any.

```bash
rg -n "thread not loaded|ephemeral threads do not support thread/turns/list|side_processing.*residue|Task Sys.*reuse" \
  tools tests scripts/env buddyswitch/skills docs/spec/task-sys-memo-optimization -S
```

Expected:

- no live guidance recommending reuse;
- failure strings only in regression tests or historical acceptance notes.

```bash
rg -n "task_sys\\.close.*side-only|side result.*close|record_side_result\\(.*close" \
  tools tests scripts/env buddyswitch/skills docs/spec -S
```

Expected:

- no live surface describes `task_sys.close` as side-only or as old side result semantics.

## Final Verification Set

Focused tests:

```bash
python -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py tests/test_side_thread_registry.py
```

Tool and response contract tests:

```bash
python -m pytest -q tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_task_management_skill_architecture.py
```

Daemon/Web status tests:

```bash
python -m pytest -q tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py tests/test_web_management.py
```

Compile gate:

```bash
python -m py_compile \
  scripts/env/domain/task_sys.py \
  scripts/env/tools/task_sys/tool.py \
  scripts/env/tools/task_sys/_impl.py \
  tools/launcher/task_sys_runtime.py \
  tools/launcher/side_thread_registry.py \
  tools/launcher/daemon_core.py \
  tools/launcher/web_management.py
```

Acceptance smoke:

```text
Run only after focused tests pass and resource lifecycle ownership is checked.
Use the External IM API path only.
Do not use iMessage or /api/web/im/* for this Task Sys lifecycle acceptance.
Stop immediately on first lifecycle residue.
```

## Definition Of Done

This fix is done only when all of these are true:

- Task Sys side frames no longer reuse old open side threads.
- Every side frame creates a fresh ephemeral side thread.
- Every side thread lease is task-bound.
- `task_sys.close` and `task_sys.need_parent` retire the side lease.
- Pre-turn dispatch failures perform bounded fresh retry and then record `runtime_failed` if still failing.
- Post-turn LLM execution is not runtime-retried by launching another side thread.
- Side no-result/timeout has an explicit non-success state.
- Active `side_processing` means actual active side processing, not stale residue.
- Recoverable failures are visible in status/management surfaces.
- Tool feedback is strong enough for the LLM/host to decide without reading service code.
- Live surfaces no longer teach the old Task Sys side reuse semantics.
- Focused tests, residue scans, compile checks, and resource-gated acceptance pass.
- No runtime object files under `buddyswitch/objects/**` are edited directly.

## Out Of Scope

- iMessage phone delivery polling.
- External IM API redesign.
- WebUI message composer redesign.
- Generic side-thread pooling.
- Generic workflow/retry engine.
- Long-lived side conversation UX for manual `/side` usage, except where registry fields need to coexist safely with Task Sys task-bound leases.
- Direct cleanup of historical runtime residue by editing `buddyswitch/objects/**`.

## Short Restatement

Task Sys side frames should behave like single-task workers:

```text
fresh create
  -> clear dispatch
  -> no runtime retry after LLM turn starts
  -> explicit task result or explicit failure
  -> mandatory resource cleanup
  -> visible recovery state
```

The engineering bottom line is:

```text
do not lose, do not fake success, do not leak, do not hang, and do not teach the old reuse path.
```
