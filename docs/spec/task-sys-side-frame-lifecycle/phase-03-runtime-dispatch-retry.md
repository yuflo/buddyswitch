# Phase 03 Runtime Dispatch Retry And Failure Recording Plan

Date: 2026-06-30

## Current Problem And Evidence

After Phase 02, Task Sys creates a fresh side thread for each frame, but the dispatch is still
opaque: `task_sys_runtime._execute_start_side()` delegates fork, boundary injection, and side input
to `app_server.side_start()`. The runtime cannot distinguish:

- fork failure before a side worker exists;
- boundary injection failure after a side thread exists;
- side input failure before a `turn_id` exists;
- successful side turn start where runtime retry is no longer safe.

Phase 01 added recoverable failure states, but runtime does not call
`task_sys.record_side_runtime_failure()`. A final dispatch failure can still bubble out and leave
the task in `side_processing`.

## Target Behavior

`start_side` execution owns explicit stages:

```text
side_fork -> side_inject -> side_input -> side_turn_started
```

Retry policy:

- max attempts: 2;
- each retry uses a fresh side thread;
- retry is allowed only before a side `turn_id` exists;
- failed attempts with a side thread are cleaned up before the next attempt;
- after all pre-turn attempts fail, Task Sys records `runtime_failed`;
- after a `turn_id` exists, runtime returns success and does not start another side thread.

Returned runtime payloads include attempt summaries with stage, side thread id when known, error,
cleanup result, and retryability.

## Files

- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `tests/test_task_sys_runtime_executor.py`
- Covered by existing Phase 01 domain API in `scripts/env/domain/task_sys.py`

## Old Path / Residue Definition

Old residue for this phase is any Task Sys pre-turn dispatch failure that:

- leaves the task in `side_processing`;
- does not record `runtime_failed`;
- retries after a side `turn_id` exists;
- retries by reusing an existing side thread;
- leaves a failed attempt lease registered as open.

## Implementation Steps

1. Update start-side runtime tests to expect lower-level `thread_fork`, `thread_inject_items`, and
   `input_turn` calls instead of opaque `side_start`.
2. Add failing tests for:
   - fork failure followed by fresh retry success;
   - input failure before `turn_id` followed by cleanup and final `runtime_failed`;
   - no retry/cleanup after `turn_id` is returned.
3. Run focused tests and confirm failures against the old opaque `side_start()` implementation.
4. Replace `_execute_start_side()` with explicit attempt execution.
5. Add best-effort failed-attempt cleanup that calls `app_server.side_close()` when a side thread id
   exists and unregisters the task-bound lease regardless of close success.
6. Call `task_sys.record_side_runtime_failure()` after bounded pre-turn attempts fail.
7. Run focused tests, compile gate, and residue scan.

## Test Plan

Focused red/green command:

```bash
python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_sys_substrate.py
```

Expected red before implementation:

- runtime tests fail because `_execute_start_side()` still calls `app_server.side_start()`;
- runtime failure tests fail because final failure is not recorded as `runtime_failed`.

Focused green expectation:

- runtime executor and substrate tests pass.

Compile gate:

```bash
python -m py_compile tools/launcher/task_sys_runtime.py scripts/env/domain/task_sys.py
```

## Residue Scan Plan

```bash
rg -n "side_fork|side_inject|side_input|side_turn_started|runtime_failed|record_side_runtime_failure" tools/launcher/task_sys_runtime.py tests/test_task_sys_runtime_executor.py -S
```

Expected:

- hits define or assert explicit dispatch stages and failure recording.

```bash
rg -n "app_server\\.side_start" tools/launcher/task_sys_runtime.py tests/test_task_sys_runtime_executor.py -S
```

Expected:

- no hits in `task_sys_runtime.py`; tests may mention the old helper only in negative/residue
  assertions.

## Acceptance Criteria

- Fork, inject, and input failures before `turn_id` are represented in attempt summaries.
- A pre-turn failure uses a fresh side thread on retry.
- Failed pre-turn attempts unregister their side lease even if physical close fails.
- Exhausted pre-turn attempts persist `runtime_failed` with `failure_result`.
- Once input returns a `turn_id`, runtime does not retry or cleanup as a failure.
- Focused tests and compile gate pass.

## Test Resource Lifecycle Requirements

Phase 03 uses unit fakes and temporary instance/task JSON only. It must not start daemons, actors,
app servers, browser processes, workers, runtime brokers, or real side threads.

## Actual Changes

- Replaced Task Sys `start_side` use of opaque `app_server.side_start()` with explicit
  `thread_fork`, task-bound lease registration, `thread_inject_items`, and `input_turn` stages.
- Added bounded `MAX_START_SIDE_ATTEMPTS = 2` retry for pre-turn dispatch failures.
- Added best-effort failed-attempt cleanup that calls `app_server.side_close()` and unregisters the
  task-bound side lease even when physical close fails.
- Added final `runtime_failed` recording through `task_sys.record_side_runtime_failure()` when all
  pre-turn attempts fail.
- Added returned attempt summaries for success and failure paths.
- Updated runtime tests to assert staged dispatch rather than the old opaque `side_start()` helper.

## Actual Verification

- Red check:
  - `python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_sys_substrate.py`
  - Result: failed as expected because the old implementation still called `app_server.side_start()`
    instead of `thread_fork` / `thread_inject_items` / `input_turn`.
- Focused green check:
  - `python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_sys_substrate.py`
  - Result: `35 passed, 20 subtests passed`.
- Adjacent focused check:
  - `python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_sys_substrate.py tests/test_side_thread_registry.py`
  - Result: `44 passed, 20 subtests passed`.
- Compile gate:
  - `python -m py_compile tools/launcher/task_sys_runtime.py scripts/env/domain/task_sys.py`
  - Result: pass.
- Stage/failure scan:
  - `rg -n "side_fork|side_inject|side_input|side_turn_started|runtime_failed|record_side_runtime_failure" tools/launcher/task_sys_runtime.py tests/test_task_sys_runtime_executor.py -S`
  - Result: hits define or assert explicit dispatch stages and failure recording.
- Old opaque helper scan:
  - `rg -n "app_server\\.side_start" tools/launcher/task_sys_runtime.py tests/test_task_sys_runtime_executor.py -S`
  - Result: no hits in `task_sys_runtime.py`; hits remain only in negative test hooks that fail if
    Task Sys uses the old helper.

## Acceptance Status

Accepted for Phase 03. Programmatic pre-turn side dispatch has bounded fresh retry, cleans failed
leases, records `runtime_failed` on exhaustion, and stops retrying once a side `turn_id` exists.
