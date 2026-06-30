# Phase 2: Parent Frame Completion Contract

Date: 2026-06-30

## 1. Phase Goal

Make `task_sys.parent_frame` explicitly require parent actors to complete source-bound work and then call `task_sys.close(task_id=..., summary=...)`, while cleaning side-frame and skill wording so `task_sys.close` is no longer taught as a side-only result.

## 2. Current Code Investigation Results

- Before this phase, `tools/launcher/task_sys_runtime.py::render_parent_frame(...)` rendered source, inbound context, side handoff details, parent handoff params, and a generic required action. It did not require `task_sys.close`.
- `render_parent_frame(...)` does not name the IM closure order: `message.send` or `message.mark` first, then `task_sys.close`, and retry close without duplicate replies if close fails.
- `render_parent_frame(...)` does not explicitly forbid `task_sys.checkpoint_update`.
- Before this phase, `render_side_frame(...)` still used stale side-result wording around close; Phase 1 made close a frame close, so that live prompt wording needed cleanup.
- `buddyswitch/skills/shared/task-management/SKILL.md` still says side frames finish with a side result and parent frames only process parent task context; it does not require parent source-task closure.
- `tests/test_task_sys_runtime_executor.py` only checks broad parent-frame shape today.
- `tests/test_task_management_skill_architecture.py` checks that the task-management skill mentions Task Sys operations, but not the corrected side/parent/checkpoint frame split.

## 3. Owning Module And System Boundary

- Runtime frame owning module: `tools/launcher/task_sys_runtime.py`.
- Durable lifecycle state remains owned by `scripts/env/domain/task_sys.py`; this phase must not add any parent auto-close rule.
- Skill guidance may describe the repeated workflow, but exact schemas and state effects remain owned by env tool catalog and responses.
- Parent frame actors own deciding when source-bound work is complete and must record that decision with `task_sys.close`.

## 4. Explicit Non-Goals

- Do not change Task Sys state transitions in this phase; Phase 1 already replaced close semantics.
- Do not make parent turn completion close tasks automatically.
- Do not make message disposition close tasks automatically.
- Do not change daemon status or runtime breadcrumb logging in this phase.
- Do not modify prohibited parallel iMessage channel/API files.

## 5. Planned File Changes

- Modify `tools/launcher/task_sys_runtime.py`
  - Update side frame section label from side-result close wording to frame-completion operations.
  - Expand parent frame text with required close contract, IM source order, checkpoint-update prohibition, duplicate-reply retry rule, and allowed operation list.
- Modify `tests/test_task_sys_runtime_executor.py`
  - Add failing tests for parent close requirement, IM closure order, checkpoint-update prohibition, and side-frame stale wording cleanup.
- Modify `buddyswitch/skills/shared/task-management/SKILL.md`
  - Update principles and frame judgment to include parent-frame `task_sys.close` after source-bound completion.
  - Remove wording that describes close as a side result.
- Modify `tests/test_task_management_skill_architecture.py`
  - Add tests that the skill teaches side/parent/checkpoint operation split and does not teach close as a side result.

## 6. Test Plan

Write these failing tests first:

- `tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests::test_render_parent_frame_requires_task_sys_close`
  - Covers the required parent-frame close instruction.
  - Expected failure before implementation: parent frame text has no `task_sys.close`.
- `tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests::test_render_parent_frame_names_im_closure_order`
  - Covers `message.send` / `message.mark` before close and duplicate-reply avoidance.
  - Expected failure before implementation: parent frame text has no IM closure order.
- `tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests::test_render_parent_frame_forbids_checkpoint_update`
  - Covers checkpoint-only boundary in parent frames.
  - Expected failure before implementation: parent frame text does not forbid `task_sys.checkpoint_update`.
- `tests/test_task_sys_runtime_executor.py::TaskSysRuntimeExecutorTests::test_render_side_frame_no_longer_calls_close_a_side_result`
  - Covers live side-frame prompt residue cleanup.
  - Expected failure before implementation: side prompt says close is a side result.
- `tests/test_task_management_skill_architecture.py::TaskManagementSkillArchitectureTests::test_task_management_skill_teaches_frame_specific_task_sys_operations`
  - Covers skill surface cleanup and parent close workflow.
  - Expected failure before implementation: skill still teaches stale side-result wording and lacks parent close order.

Focused RED command:

```bash
python3 -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_management_skill_architecture.py
```

## 7. Implementation Steps

1. Add the failing runtime renderer and skill architecture tests.
2. Run the focused RED command and confirm failures match stale parent frame and side-result wording.
3. Update `render_side_frame(...)` labels and allowed operations so `task_sys.close` is a frame close, while `task_sys.need_parent` remains side-owned.
4. Update `render_parent_frame(...)` with required source-bound completion instructions, IM-specific ordering, close retry guidance, allowed operation list, and checkpoint-update prohibition.
5. Update the task-management skill to teach side, parent, and checkpoint frame-specific operations.
6. Run the focused tests until green.
7. Run the phase residue scan and remove any live stale wording.
8. Run py_compile for `tools/launcher/task_sys_runtime.py`.
9. Update this document with actual RED/GREEN verification output summary and residue results.

## 8. Verification Commands

```bash
python3 -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_management_skill_architecture.py
python3 -m py_compile tools/launcher/task_sys_runtime.py
```

## 9. Residue Scan Commands

```bash
parent_prompt_residue_regex="$(printf '%s%s%s%s%s%s' 'side result.*task_sys.cl' 'ose|task_sys.checkpoint_update.*parent_' 'frame|Do not recom' 'mend the next task')"
skill_residue_regex="$(printf '%s%s%s%s' 'side result.*cl' 'ose|finish with exactly one Task Sys side ' 'result')"
rg -n "${parent_prompt_residue_regex}" tools/launcher/task_sys_runtime.py tests docs/spec -S
rg -n "${skill_residue_regex}" buddyswitch/skills/shared/task-management/SKILL.md tests docs/spec -S
git diff --name-only | rg "imessage_channel.py|external_im_session.py|im_http_router.py|web_management.py|test_imessage_channel.py|test_external_im_session.py|test_im_http_router.py|test_im_web_management_projection.py" -S
```

Expected residue results:

- No side or parent prompt describes `task_sys.close` as a side result.
- No parent-frame surface tells actors to use `task_sys.checkpoint_update`.
- The checkpoint “do not recommend” phrase remains checkpoint-specific and must not appear outside checkpoint-frame tests/code.
- The prohibited-file scan returns no output.

## 10. Exit Criteria

- Focused runtime renderer and task-management skill architecture tests pass.
- `tools/launcher/task_sys_runtime.py` compiles.
- Residue scans match expected output or every remaining hit is recorded here as valid checkpoint-only semantics.
- `git diff --name-only` does not include prohibited parallel iMessage files.
- This document includes actual RED failure summary, final verification summary, residue summary, and any implementation deviations.

## 11. Actual Phase Result

RED verification:

- Command: `python3 -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_management_skill_architecture.py`
- Result before implementation: 6 failed, 16 passed, 36 subtests passed.
- Expected failures were observed: parent frame lacked close requirement, IM closure order, and checkpoint-update prohibition; side frame and task-management skill still taught stale side-result wording.

Implementation summary:

- Updated side frame prompt wording to legal frame operations: side close or side need-parent.
- Updated parent frame prompt wording to require source-bound completion and explicit `task_sys.close`.
- Added IM-source ordering: reply or absorb first, then close, and retry close without duplicate replies.
- Added parent-frame checkpoint-update prohibition without adding any auto-close rule.
- Updated shared task-management skill to teach side, parent, and checkpoint frame-specific operations.

Final verification:

- `python3 -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_management_skill_architecture.py` passed: 22 passed, 36 subtests passed.
- `python3 -m py_compile tools/launcher/task_sys_runtime.py` passed.

Residue summary:

- Parent/side runtime prompt and current task-management skill surfaces no longer describe `task_sys.close` as a side result.
- The parent-frame checkpoint-update residue scan now only reports the checkpoint fixture in `tests/test_task_sys_runtime_executor.py`, where the phrase is checkpoint-specific.
- The skill side-result scan reports only older historical docs under other `docs/spec` tasks; current Phase 2 spec and live skill surfaces are clean.
- The prohibited-file scan returned no output.
