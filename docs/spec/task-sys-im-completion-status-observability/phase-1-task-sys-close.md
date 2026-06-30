# Phase 1: Task Sys Close Semantic Replacement

Date: 2026-06-30

## 1. Phase Goal

Replace side-only close handling with a Task Sys frame close operation: `task_sys.close(task_id=...)` closes tasks in `side_processing` or `parent_processing`, records close metadata, clears `active_processor`, and is retry-safe for already closed tasks.

## 2. Current Code Investigation Results

- Before this phase, `scripts/env/domain/task_sys.py` allowed both close and need-parent through the side-result outcome list.
- Before this phase, the side-result domain function owned both side close and need-parent handoff.
- Before this phase, `scripts/env/tools/task_sys/_impl.py` implemented `close(...)` through the side-result close path.
- `scripts/env/tools/task_sys/tool.py` describes the tool as side-result reporting and describes close as side-only.
- `tests/test_task_sys_side_processing.py` currently has `test_side_close_marks_task_closed_without_parent_handoff`, which asserts the old side-result close record.
- `tests/test_task_sys_substrate.py` covers need-parent and parent handoff, but not a shared close operation for parent-processing tasks.
- Env tool schema and semantic contract tests already expect a public action named `task_sys.close`; this phase keeps the action name and corrects its semantics.

## 3. Owning Module And System Boundary

- Owning product module: `scripts/env/domain/task_sys.py`.
- Tool projection: `scripts/env/tools/task_sys/_impl.py` and `scripts/env/tools/task_sys/tool.py`.
- Tests may inspect persisted Task Sys JSON through test helpers, but product code changes must go through the Task Sys domain operation.
- `task_sys.need_parent` remains side-owned. Parent handoff and runtime submission behavior are not reworked in this phase.

## 4. Explicit Non-Goals

- Do not change parent frame prompt text in this phase.
- Do not change daemon status, human status, or runtime logs in this phase.
- Do not add auto-close from parent turn completion or message disposition.
- Do not preserve the old side-result close call shape as a compatibility path.
- Do not modify prohibited parallel iMessage channel/API files.

## 5. Planned File Changes

- Modify `scripts/env/domain/task_sys.py`
  - Add `TASK_CLOSE_STATUSES = ("side_processing", "parent_processing", "closed")`.
  - Add `record_task_close(task_id, update)`.
  - Add `record_side_need_parent(task_id, result)`.
  - Remove close from `SIDE_RESULT_OUTCOMES`.
  - Narrow the side-result compatibility function away or replace its callers so close cannot be accepted as a side result.
- Modify `scripts/env/tools/task_sys/_impl.py`
  - Route `close(...)` to `record_task_close(...)`.
  - Route `need_parent(...)` to `record_side_need_parent(...)`.
  - Update success summary wording so close is a Task Sys close, not a side result.
- Modify `scripts/env/tools/task_sys/tool.py`
  - Update Task Sys description, scope, authority, visibility, success effect, preconditions, and use/do-not-use wording for shared frame close.
- Modify `tests/test_task_sys_substrate.py`
  - Add domain tests for side close, parent close, invalid statuses, checkpoint rejection, and closed retry safety.
- Modify `tests/test_task_sys_side_processing.py`
  - Replace old side-result close test with tool/domain tests for shared close and need-parent handoff.
- Modify `tests/test_env_tool_schema_contract.py`
  - Update text assertions if they currently encode side-only close.
- Modify `tests/test_env_tool_semantic_contract.py`
  - Update semantic assertions if they currently encode side-only close.

## 6. Test Plan

Write these failing tests first:

- `tests/test_task_sys_substrate.py::TaskSysSubstrateTests::test_record_task_close_closes_side_processing_task`
  - Covers side-processing close through the new domain operation.
  - Expected failure before implementation: `record_task_close` does not exist.
- `tests/test_task_sys_substrate.py::TaskSysSubstrateTests::test_record_task_close_closes_parent_processing_task`
  - Covers parent-processing close through the same domain operation.
  - Expected failure before implementation: `record_task_close` does not exist.
- `tests/test_task_sys_substrate.py::TaskSysSubstrateTests::test_record_task_close_rejects_needs_parent_task`
  - Proves close cannot skip the parent frame after side requested parent.
  - Expected failure before implementation: `record_task_close` does not exist.
- `tests/test_task_sys_substrate.py::TaskSysSubstrateTests::test_record_task_close_rejects_checkpoint_task`
  - Proves checkpoint tasks remain owned by `task_sys.checkpoint_update`.
  - Expected failure before implementation: `record_task_close` does not exist.
- `tests/test_task_sys_substrate.py::TaskSysSubstrateTests::test_record_task_close_is_retry_safe_for_closed_task`
  - Proves retrying close after a successful source-bound action does not error or reopen state.
  - Expected failure before implementation: `record_task_close` does not exist.
- `tests/test_task_sys_side_processing.py::TaskSysSideProcessingTests::test_task_sys_close_tool_closes_parent_processing_task`
  - Proves env tool `task_sys.close` uses the shared close operation and closes parent-processing tasks.
  - Expected failure before implementation: tool still calls side-result close.
- `tests/test_task_sys_side_processing.py::TaskSysSideProcessingTests::test_task_sys_need_parent_tool_still_marks_parent_processing_after_runtime_submit`
  - Proves the need-parent path remains intact after close replacement.
  - Expected failure before implementation only if the replacement breaks the handoff path.
- `tests/test_task_sys_side_processing.py::TaskSysSideProcessingTests::test_record_side_result_no_longer_accepts_close_outcome`
  - Proves no live domain API still treats close as a side result.
  - Expected failure before implementation: current `record_side_result` accepts `outcome="close"`.

Focused RED command:

```bash
python3 -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py
```

## 7. Implementation Steps

1. Add the failing domain and env tool tests listed above.
2. Run the focused RED command and confirm failures match missing `record_task_close` and stale side-result close semantics.
3. Implement `record_task_close(...)` in `scripts/env/domain/task_sys.py`.
4. Implement `record_side_need_parent(...)` and make the old side-result function unable to accept close. If keeping that function temporarily for existing need-parent call sites is shorter, narrow it to need-parent only and update tests to prove close is rejected.
5. Update `_impl.close(...)` to call `record_task_close(...)`.
6. Update `_impl.need_parent(...)` to call `record_side_need_parent(...)` or the narrowed need-parent-only operation.
7. Update `_success(...)` wording for close, need-parent, and checkpoint update so close is not called a side result.
8. Update `tool.py` action docs and task id descriptions to describe frame close, side need-parent, and checkpoint-only update accurately.
9. Run the focused tests until green.
10. Run env tool schema and semantic contract tests.
11. Run the phase py_compile command.
12. Run the residue scan and remove any live side-only close residue introduced or left by this phase.
13. Update this phase doc with actual RED/GREEN verification output summary and any deviations from the plan.

## 8. Verification Commands

```bash
python3 -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py
python3 -m pytest -q tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py
python3 -m py_compile scripts/env/domain/task_sys.py scripts/env/tools/task_sys/_impl.py scripts/env/tools/task_sys/tool.py
```

## 9. Residue Scan Commands

```bash
close_residue_regex="$(printf '%s%s%s%s%s' 'record_side_result\\(' '.*cl' 'ose|outcome.*cl' 'ose.*side result|side result.*task_sys.cl' 'ose')"
tool_doc_residue_regex="$(printf '%s%s%s%s%s%s' 'SIDE_RESULT_OUTCOMES = .*cl' 'ose|Task Sys side-result act' 'ions|Close a Task Sys task from side proc' 'essing|side processor completed the task without par' 'ent')"
rg -n "${close_residue_regex}" scripts tools tests docs/spec docs/memo -S
rg -n "${tool_doc_residue_regex}" scripts/env tests docs/spec -S
git diff --name-only | rg "imessage_channel.py|external_im_session.py|im_http_router.py|web_management.py|test_imessage_channel.py|test_external_im_session.py|test_im_http_router.py|test_im_web_management_projection.py" -S
```

Expected residue results:

- No live code path handles close through the old side-result close call shape.
- No live tool docs describe `task_sys.close` as side-only.
- The prohibited-file scan returns no output.

## 10. Exit Criteria

- Focused Task Sys substrate and side-processing tests pass.
- Env tool schema and semantic contract tests pass.
- Phase py_compile passes.
- Residue scans match expected output or every remaining hit is recorded here as valid current semantics.
- `git diff --name-only` does not include prohibited parallel iMessage files.
- This document includes actual RED failure summary, final verification summary, residue summary, and any implementation deviations.

## 11. Actual Phase Result

RED verification:

- Command: `python3 -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py`
- Result before implementation: 11 failed, 10 passed, 16 subtests passed.
- Expected failures were observed: missing `record_task_close`, missing `record_side_need_parent`, and the stale side-result close call still succeeding.

Implementation summary:

- Added `record_task_close(...)` as the shared side/parent close domain operation.
- Added `record_side_need_parent(...)` as the need-parent-only domain operation.
- Narrowed the old side-result function so close is rejected with guidance to use `task_sys.close`.
- Updated env tool `close` and `need_parent` to call the new domain operations.
- Updated the Task Sys tool catalog so `task_sys.close` is a frame close, not a side-only result.

Final verification:

- `python3 -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py` passed: 21 passed, 16 subtests passed.
- `python3 -m pytest -q tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py` passed: 23 passed, 400 subtests passed.
- `python3 -m py_compile scripts/env/domain/task_sys.py scripts/env/tools/task_sys/_impl.py scripts/env/tools/task_sys/tool.py` passed.

Residue summary:

- Live code and test surfaces no longer contain an old side-result close call path.
- Tool docs no longer describe `task_sys.close` as side-only.
- The prohibited-file scan returned no output.
- The target memo still contains historical old-semantics references; those remain source material, not live runtime surface.
