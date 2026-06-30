# Phase 02 Fresh Task Sys Side Lease Plan

Date: 2026-06-30

## Current Problem And Evidence

`tools/launcher/task_sys_runtime.py::_execute_start_side()` calls
`side_thread_registry.find_open_side_thread()` before creating a new side thread. When a stale open
row exists, Task Sys sends the next side frame through `app_server.input_turn()` on the old side
thread. The exploratory acceptance log records two user-visible failures from that path:

- `thread not loaded` on an old actor with a stale open side row;
- `ephemeral threads do not support thread/turns/list` on a second IM to a fresh actor after the
  first side task closed.

`tools/launcher/side_thread_registry.py` rows currently have only thread/parent/status/timestamps,
so Task Sys leases are indistinguishable from manual side-conversation rows.

## Target Behavior

Task Sys `start_side` always creates a fresh ephemeral side thread for the current
`task_sys.side_frame`.

The registry supports task-bound lease metadata:

```json
{
  "task_id": "task-...",
  "purpose": "task_sys.side_frame"
}
```

Manual side-conversation lookup can continue to use `find_open_side_thread()`, but that lookup must
not select task-bound Task Sys lease rows.

## Files

- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `tools/launcher/side_thread_registry.py`
- Modify: `tests/test_task_sys_runtime_executor.py`
- Modify: `tests/test_side_thread_registry.py`

## Old Path / Residue Definition

Old Task Sys residue for this phase is any runtime path where Task Sys consumes an existing open
side-thread row, especially:

- `task_sys_runtime._execute_start_side()` calling `find_open_side_thread()`;
- Task Sys `start_side` calling `app_server.input_turn()` instead of `app_server.side_start()`;
- registry lookup selecting task-bound Task Sys lease rows for reusable manual side sends.

The `find_open_side_thread()` symbol may remain for manual side conversations only.

## Implementation Steps

1. Add failing runtime tests proving a stale open row is ignored and `side_start()` is called.
2. Add a failing runtime test proving two sequential Task Sys `start_side` instructions create two
   fresh side thread ids.
3. Add failing registry tests for optional `task_id`/`purpose` metadata and manual lookup excluding
   task-bound leases.
4. Run focused tests and confirm the expected failures.
5. Extend `register_side_thread()` with optional `task_id` and `purpose` fields.
6. Update `find_open_side_thread()` to ignore task-bound lease rows.
7. Replace Task Sys `_execute_start_side()` reuse logic with unconditional `side_start()` and
   task-bound registry registration.
8. Run focused tests, compile gate, and residue scan.

## Test Plan

Red/green command:

```bash
python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_side_thread_registry.py
```

Expected red before implementation:

- stale-row runtime test fails because old Task Sys runtime tries `input_turn()`;
- sequential runtime test fails because the second `start_side` reuses the first side row;
- registry metadata/manual-lookup tests fail because row metadata is absent or task-bound rows are
  selected.

Focused green expectation:

- both files pass.

Compile gate:

```bash
python -m py_compile tools/launcher/task_sys_runtime.py tools/launcher/side_thread_registry.py
```

## Residue Scan Plan

```bash
rg -n "find_open_side_thread|input_turn\\(" tools/launcher/task_sys_runtime.py tests/test_task_sys_runtime_executor.py -S
```

Expected:

- no `find_open_side_thread` hits in `tools/launcher/task_sys_runtime.py`;
- `input_turn(` may remain only in a test fake that would fail if Task Sys reuse returns.

Registry scan:

```bash
rg -n "task_sys.side_frame|task_id|purpose" tools/launcher/side_thread_registry.py tools/launcher/task_sys_runtime.py tests/test_side_thread_registry.py tests/test_task_sys_runtime_executor.py -S
```

Expected:

- hits define or assert task-bound lease metadata.

## Acceptance Criteria

- Task Sys `start_side` ignores stale open side-thread rows.
- Two sequential Task Sys side frames create two distinct fresh side threads.
- Task Sys side registry rows include `task_id` and `purpose: task_sys.side_frame`.
- Manual side lookup does not return task-bound Task Sys rows.
- Manual side registry compatibility remains intact for untagged rows.
- Focused tests, compile gate, and residue scans pass.

## Test Resource Lifecycle Requirements

Phase 02 uses unit-level fakes and temporary instance JSON files only. It must not start daemons,
actors, app servers, browser processes, workers, runtime brokers, or real side threads.

## Actual Changes

- Removed the `find_open_side_thread()` reuse branch from Task Sys `_execute_start_side()`.
- Task Sys `start_side` now always calls `app_server.side_start()` and registers the returned side
  thread as a task-bound lease with `task_id` and `purpose: task_sys.side_frame`.
- Extended `side_thread_registry.register_side_thread()` with optional `task_id` and `purpose`
  metadata.
- Updated `find_open_side_thread()` so manual reusable side-conversation lookup skips task-bound
  Task Sys lease rows.
- Added runtime regression coverage for stale open rows and sequential Task Sys side frames.
- Added registry coverage for task-bound metadata and manual lookup exclusion.

## Actual Verification

- Red check:
  - `python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_side_thread_registry.py`
  - Result: failed as expected in four places:
    - stale open row test hit the old `app_server.input_turn()` path;
    - sequential Task Sys side-frame test hit the old reuse path on the second frame;
    - registry metadata test failed because `register_side_thread()` did not accept `task_id`;
    - manual lookup test selected the task-bound row.
- Focused green check:
  - `python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_side_thread_registry.py`
  - Result: `26 passed`.
- Compile gate:
  - `python -m py_compile tools/launcher/task_sys_runtime.py tools/launcher/side_thread_registry.py`
  - Result: pass.
- Reuse residue scan:
  - `rg -n "find_open_side_thread|input_turn\\(" tools/launcher/task_sys_runtime.py tests/test_task_sys_runtime_executor.py -S`
  - Result: no `find_open_side_thread` hits in `task_sys_runtime.py`; `input_turn(` hits only in
    test fakes that fail if Task Sys reuse returns.
- Task-bound lease scan:
  - `rg -n "task_sys.side_frame|task_id|purpose" tools/launcher/side_thread_registry.py tools/launcher/task_sys_runtime.py tests/test_side_thread_registry.py tests/test_task_sys_runtime_executor.py -S`
  - Result: hits define or assert task-bound lease metadata.

## Acceptance Status

Accepted for Phase 02. Task Sys no longer consumes old reusable open side-thread rows and each
`start_side` call creates a fresh task-bound lease.
