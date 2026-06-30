# Phase 04 Side Lease Retirement Plan

Date: 2026-06-30

## Current Problem And Evidence

Phase 02 creates task-bound side leases and Phase 03 cleans pre-turn failed attempts, but successful
side LLM results still do not retire the side lease:

- `scripts/env/tools/task_sys/_impl.py::close()` records task close only.
- `scripts/env/tools/task_sys/_impl.py::need_parent()` records parent handoff and starts parent
  runtime only.
- `record_task_close()` and `record_side_need_parent()` do not record cleanup metadata.
- There is no runtime operation that can locate the task-bound side lease by `task_id`, call
  physical `side_close`, and unregister the lease after side completion or handoff.

## Target Behavior

When a side frame calls `task_sys.close`:

```text
record closed -> retire task-bound side lease -> record cleanup on close_result
```

When a side frame calls `task_sys.need_parent`:

```text
record needs_parent -> attempt parent runtime -> record parent_processing if submit succeeds
  -> retire task-bound side lease -> record cleanup on side_result
```

If parent runtime fails before submit, the task remains `needs_parent`, but the side lease is still
retired and cleanup metadata is recorded. Physical close is best effort; registry unregister must run
even if physical close fails.

## Files

- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `tools/launcher/side_thread_registry.py`
- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env/tools/task_sys/_impl.py`
- Modify: `scripts/env/domain/task_sys.py`
- Modify: `tests/test_task_sys_runtime_executor.py`
- Modify: `tests/test_task_sys_side_processing.py`
- Modify: `tests/test_task_sys_substrate.py`

## Old Path / Residue Definition

Old residue for this phase is any task-bound `purpose: task_sys.side_frame` lease that remains open
after side calls `task_sys.close` or `task_sys.need_parent`, including when physical side close fails.

## Implementation Steps

1. Add failing runtime test for `cleanup_task_sys_side_lease(context, task_id)` unregistering a
   task-bound lease even if `app_server.side_close()` fails.
2. Add failing domain test for recording cleanup metadata on side close and need-parent side result.
3. Add failing tool tests proving `task_sys.close` and `task_sys.need_parent` invoke the cleanup hook
   and persist cleanup metadata.
4. Run focused tests and confirm expected failures.
5. Add task-bound lease lookup in `side_thread_registry.py`.
6. Add runtime cleanup helper in `task_sys_runtime.py`.
7. Expose the helper through `DaemonAccess.cleanup_task_sys_side_lease(task_id)`.
8. Add `task_sys.record_side_cleanup(task_id, cleanup)` in the domain.
9. Call cleanup from task_sys tool `close()` and `need_parent()` after durable side result mutation.
10. Run focused tests, compile gate, and residue scan.

## Test Plan

Focused red/green command:

```bash
python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py tests/test_task_sys_substrate.py
```

Expected red before implementation:

- cleanup helper is missing;
- domain cleanup recorder is missing;
- tool results do not include cleanup metadata.

Focused green expectation:

- runtime executor, side-processing, and substrate tests pass.

Compile gate:

```bash
python -m py_compile tools/launcher/task_sys_runtime.py tools/launcher/side_thread_registry.py scripts/env/tool_runtime/context.py scripts/env/tools/task_sys/_impl.py scripts/env/domain/task_sys.py
```

## Residue Scan Plan

```bash
rg -n "cleanup_task_sys_side_lease|record_side_cleanup|find_task_side_thread|physical_close_ok|registry_unregistered" tools/launcher scripts/env tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py tests/test_task_sys_substrate.py -S
```

Expected:

- hits define or assert side lease cleanup and persisted cleanup metadata.

## Acceptance Criteria

- Runtime can locate a task-bound side lease by `task_id`.
- Runtime cleanup unregisters the lease even when physical `side_close` fails.
- `task_sys.close` from side records cleanup metadata on `close_result`.
- `task_sys.need_parent` records cleanup metadata on `side_result` after successful parent submit.
- Parent runtime failure leaves the task `needs_parent` and still records side cleanup.
- Focused tests and compile gate pass.

## Test Resource Lifecycle Requirements

Phase 04 uses unit fakes and temporary instance/task JSON only. It must not start daemons, actors,
app servers, browser processes, workers, runtime brokers, or real side threads.

## Actual Changes

- Added `side_thread_registry.find_task_side_thread()` for locating open task-bound
  `task_sys.side_frame` leases by `task_id`.
- Added `task_sys_runtime.cleanup_task_sys_side_lease(context, task_id)` that best-effort closes the
  physical side thread and unregisters the lease even when close fails.
- Exposed cleanup through `ToolContext.daemon.cleanup_task_sys_side_lease(task_id)`.
- Added `task_sys.record_side_cleanup(task_id, cleanup)` to persist cleanup metadata on side
  `close_result` or `side_result`.
- Updated `task_sys.close` to cleanup side leases only for side-processor close results.
- Updated `task_sys.need_parent` to cleanup side leases after successful parent submit and also when
  parent runtime fails before submit.
- Added runtime, domain, and tool regression tests for cleanup persistence and unregister-on-close
  failure.

## Actual Verification

- Red check:
  - `python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py tests/test_task_sys_substrate.py`
  - Result: failed as expected because cleanup helper, cleanup recorder, and tool cleanup hook were
    missing.
- Focused green check:
  - `python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py tests/test_task_sys_substrate.py`
  - Result: `47 passed, 20 subtests passed`.
- Adjacent focused check:
  - `python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py tests/test_task_sys_substrate.py tests/test_side_thread_registry.py`
  - Result: `56 passed, 20 subtests passed`.
- Compile gate:
  - `python -m py_compile tools/launcher/task_sys_runtime.py tools/launcher/side_thread_registry.py scripts/env/tool_runtime/context.py scripts/env/tools/task_sys/_impl.py scripts/env/domain/task_sys.py`
  - Result: pass.
- Cleanup scan:
  - `rg -n "cleanup_task_sys_side_lease|record_side_cleanup|find_task_side_thread|physical_close_ok|registry_unregistered" tools/launcher scripts/env tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py tests/test_task_sys_substrate.py -S`
  - Result: hits define or assert side lease cleanup and persisted cleanup metadata.

## Acceptance Status

Accepted for Phase 04. Side close and side parent-handoff paths now retire task-bound side leases and
persist cleanup facts, including best-effort physical close failures.
