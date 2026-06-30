# Phase 01 Task Sys Failure States Plan

Date: 2026-06-30

## Current Problem And Evidence

`scripts/env/domain/task_sys.py` only defines:

```text
new, side_processing, closed, needs_parent, parent_processing, checkpoint
```

`ACTIVE_TASK_STATUSES` includes every non-closed workflow state and there is no recoverable failure
query. A side dispatch failure therefore has no durable state except leaving the task in
`side_processing`, which falsely says side work is still active.

Evidence inspected:

- `TASK_STATUSES` and `ACTIVE_TASK_STATUSES` lack `runtime_failed`, `side_no_result`, and
  `side_timed_out`.
- `record_task_close()` accepts `side_processing`, `parent_processing`, and already `closed`; it
  rejects other non-active states but has no explicit failure-state coverage.
- `daemon_core._task_sys_status_payload()` filters only `ACTIVE_TASK_STATUSES`, so recoverable
  failure projection cannot be implemented until the domain has a recoverable status query.
- Exploratory acceptance log `docs/spec/task-sys-exploratory-acceptance/01-run-log.md` records
  stale side-thread dispatch failures that left tasks in `side_processing`.

## Target Behavior

Task Sys domain records side lifecycle failures as durable, recoverable, non-active task states:

```text
runtime_failed
side_no_result
side_timed_out
```

The domain exposes:

- `RECOVERABLE_TASK_STATUSES`;
- `recoverable_tasks_for_actor(actor_target)`;
- `record_side_runtime_failure(task_id, failure)`.

`record_side_runtime_failure()` must:

- require the task to currently be `side_processing`;
- require a valid failure `status` in the recoverable set;
- set `active_processor` to `None`;
- record `failure_result`;
- preserve `source_type`, `source_ref`, `actor_target`, and `inbound_context`;
- return a normal task mutation result with `state_changed=True`.

Failed side runtime tasks must not be closable as success.

## Files

- Modify: `scripts/env/domain/task_sys.py`
- Modify: `tests/test_task_sys_substrate.py`

## Old Path / Residue Definition

Old residue for this phase is any Task Sys side dispatch failure that can only remain in
`side_processing`, and any active-task query that treats recoverable side failures as active work.

This phase does not yet remove side-thread reuse. It creates the durable state contract that later
runtime phases will call.

## Implementation Steps

1. Add failing substrate tests for recoverable statuses and failure recording.
2. Run focused tests to verify the new tests fail because the API/statuses do not exist.
3. Add `RECOVERABLE_TASK_STATUSES` and extend `TASK_STATUSES`.
4. Add `recoverable_tasks_for_actor(actor_target)`.
5. Add `record_side_runtime_failure(task_id, failure)`.
6. Run focused tests until green.
7. Run compile gate.

## Test Plan

Focused red/green command:

```bash
python -m pytest -q tests/test_task_sys_substrate.py
```

Expected red before implementation:

- tests fail because `RECOVERABLE_TASK_STATUSES`, `recoverable_tasks_for_actor`, or
  `record_side_runtime_failure` is missing.

Expected green after implementation:

- substrate tests pass.

Compile gate:

```bash
python -m py_compile scripts/env/domain/task_sys.py
```

## Residue Scan Plan

After implementation:

```bash
rg -n "runtime_failed|side_no_result|side_timed_out|RECOVERABLE_TASK_STATUSES|recoverable_tasks_for_actor|record_side_runtime_failure" scripts/env/domain/task_sys.py tests/test_task_sys_substrate.py -S
```

Expected:

- hits exist only in the new domain constants/API and tests for this phase.

## Acceptance Criteria

- `runtime_failed`, `side_no_result`, and `side_timed_out` are valid Task Sys statuses.
- Recoverable statuses are not included in `ACTIVE_TASK_STATUSES`.
- A recoverable failed side task is returned by `recoverable_tasks_for_actor()` and not by
  `active_tasks_for_actor()`.
- Failure metadata is persisted under `failure_result`.
- Original task source and actor fields survive failure recording unchanged.
- `record_task_close()` rejects recoverable failure tasks.
- Focused substrate tests and `py_compile` pass.

## Test Resource Lifecycle Requirements

Phase 01 is domain-only. It must not start daemons, actors, app servers, browser processes, workers,
or runtime brokers. No live resource baseline or cleanup is required beyond normal temporary
runtime-root test isolation.

## Actual Changes

- Added `runtime_failed`, `side_no_result`, and `side_timed_out` to `TASK_STATUSES`.
- Added `RECOVERABLE_TASK_STATUSES` and `recoverable_tasks_for_actor(actor_target)`.
- Added `record_side_runtime_failure(task_id, failure)` with side-processing precondition,
  recoverable status validation, `failure_result` persistence, `active_processor` clearing, and
  original source/actor/context preservation.
- Added regression coverage proving recoverable side failures are queryable, not active, preserve
  source facts, and cannot be closed as successful task completion.

## Actual Verification

- Red check:
  - `python -m pytest -q tests/test_task_sys_substrate.py`
  - Result: failed as expected with
    `AttributeError: module 'env.domain.task_sys' has no attribute 'record_side_runtime_failure'`.
- Focused green check:
  - `python -m pytest -q tests/test_task_sys_substrate.py`
  - Result: `15 passed, 20 subtests passed`.
- Compile gate:
  - `python -m py_compile scripts/env/domain/task_sys.py`
  - Result: pass.
- Residue scan:
  - `rg -n "runtime_failed|side_no_result|side_timed_out|RECOVERABLE_TASK_STATUSES|recoverable_tasks_for_actor|record_side_runtime_failure" scripts/env/domain/task_sys.py tests/test_task_sys_substrate.py -S`
  - Result: hits only in the new domain constants/API and phase tests.

## Acceptance Status

Accepted for Phase 01. Task Sys can now represent recoverable side lifecycle failures without
leaving failed work falsely active in `side_processing`.
