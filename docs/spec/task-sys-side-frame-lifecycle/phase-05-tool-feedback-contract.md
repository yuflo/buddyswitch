# Phase 05 Tool Feedback Contract Plan

Date: 2026-06-30

## Current Problem And Evidence

Phase 04 persists side cleanup metadata, but the LLM-facing tool response is still only partially
explicit. `task_sys._impl._success()` exposes `task_id`, `outcome`, and `task_status`; it now also
passes through nested `close_result`/`side_result`, but the tool catalog and response tests do not
yet require the key host-decision fields directly:

- `state_changed`;
- `processor`;
- `side_thread_id`;
- side cleanup;
- parent runtime result for `need_parent`;
- clear state-unchanged rejection feedback.

## Target Behavior

`task_sys.close` success responses expose:

- `task_id`;
- `task_status`;
- `state_changed`;
- `processor`;
- `side_thread_id` when available;
- `side_cleanup` when available;
- `close_result`.

`task_sys.need_parent` success responses expose:

- `task_id`;
- `task_status`;
- `state_changed`;
- `processor: side`;
- `side_thread_id` when available;
- `side_cleanup`;
- `side_result`;
- `parent_handoff_params`;
- `parent_instruction`;
- `parent_runtime`.

Payload rejections continue to state `state_changed=False` and why no state changed.

## Files

- Modify: `scripts/env/tools/task_sys/tool.py`
- Modify: `scripts/env/tools/task_sys/_impl.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_task_sys_side_processing.py`

## Old Path / Residue Definition

Old feedback residue is any Task Sys tool success where the host must infer processor, side lease,
or cleanup effect from nested implementation details or a generic `ok=true`.

## Implementation Steps

1. Add failing tests for `task_sys.close` response top-level processor, side thread id, and cleanup.
2. Add failing tests for task_sys catalog returns naming state/processor/cleanup fields.
3. Run focused tests and confirm failures.
4. Add top-level response fields in `_success()` from `close_result` and `side_result`.
5. Update tool action return metadata.
6. Run focused tests, compile gate, and semantic scans.

## Test Plan

Focused red/green command:

```bash
python -m pytest -q tests/test_task_sys_side_processing.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py
```

Expected red before implementation:

- response tests fail because `processor` / `side_thread_id` are not top-level fields;
- semantic tests fail because Task Sys tool returns do not name the new feedback fields.

Focused green expectation:

- all three files pass.

Compile gate:

```bash
python -m py_compile scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py
```

## Residue Scan Plan

```bash
rg -n "processor|side_thread_id|side_cleanup|parent_runtime|state_changed" scripts/env/tools/task_sys tests/test_task_sys_side_processing.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py -S
```

Expected:

- hits define or assert explicit Task Sys feedback fields.

## Acceptance Criteria

- `task_sys.close` response has direct processor, side thread, cleanup, task status, and state change
  fields when side cleanup applies.
- `task_sys.need_parent` response has direct side cleanup and parent runtime outcome fields.
- Tool catalog return semantics list those fields.
- Payload rejection feedback still states no Task Sys state changed.
- Focused tests and compile gate pass.

## Test Resource Lifecycle Requirements

Phase 05 uses runtime-broker/tool unit dispatch with patched cleanup hooks only. It must not start
daemons, actors, app servers, browser processes, workers, runtime brokers, or real side threads.

## Actual Changes

- Lifted `processor` and `side_thread_id` from `close_result` / `side_result` into top-level
  Task Sys tool success responses.
- Kept top-level `side_cleanup`, `close_result`, `side_result`, `parent_instruction`, and
  `parent_runtime` in success responses.
- Added actionable success guidance telling the host to use returned status/processor/cleanup fields.
- Updated Task Sys tool catalog `returns` metadata for `close` and `need_parent`.
- Added direct tool tests, broker-level response-contract coverage, and semantic catalog coverage.

## Actual Verification

- Red check:
  - `python -m pytest -q tests/test_task_sys_side_processing.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py`
  - Result: failed as expected because `processor` / `side_thread_id` were missing at top level and
    tool catalog `returns` omitted the new feedback fields.
- Focused green check:
  - `python -m pytest -q tests/test_task_sys_side_processing.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py`
  - Result: `43 passed, 420 subtests passed`.
- Compile gate:
  - `python -m py_compile scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py`
  - Result: pass.
- Feedback-field scan:
  - `rg -n "processor|side_thread_id|side_cleanup|parent_runtime|state_changed" scripts/env/tools/task_sys tests/test_task_sys_side_processing.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py -S`
  - Result: hits define or assert explicit Task Sys feedback fields.

## Acceptance Status

Accepted for Phase 05. Task Sys tool responses and catalog semantics now expose direct state,
processor, side-thread, cleanup, and parent-runtime fields instead of relying on generic success.
