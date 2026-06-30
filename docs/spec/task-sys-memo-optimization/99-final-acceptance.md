# Task Sys Memo Optimization Final Acceptance

Source memos:

- `docs/memo/2026-06-29-web-management-input-residue-cleanup.md`
- `docs/memo/2026-06-29-task-sys-interrupt-submit-parent-idle-bug.md`
- `docs/memo/2026-06-30-task-sys-side-thread-resource-boundary-prompt.md`

## Required Review

Read before implementation:

- `AGENTS.md`
- all `docs/bitter/*` principle notes
- the three source memos above
- existing Task Sys proactive rebuild records under `docs/spec/task-sys-proactive-rebuild/`

## Phase Status

| Phase | Record | Status | Evidence |
| --- | --- | --- | --- |
| 01 | `phase-01-web-input-api-cleanup.md` | Accepted | Web management input API removed; Web IM path still verified. |
| 02 | `phase-02-side-frame-resource-boundary.md` | Accepted | Every rendered side frame carries resource-boundary policy. |
| 03 | `phase-03-parent-idle-interrupt-submit.md` | Accepted | Idle/race interrupt handoff submits parent frames; runtime failure no longer orphans `parent_processing`. |

## Memo Completion Audit

### Web Management Input Residue Cleanup

Completed:

- Removed Web backend route handling for `POST /api/instances/<actor-id>/input`.
- Removed `/input` parsing from Web management instance action routing.
- Removed `_send_input()`, `_send_input_under_lock()`, and `_run_input_command()`.
- Removed the obsolete Web-only `Instance input blocked:` command-error mapping.
- Replaced Web input success/error tests with a 404/no-launcher-call removal test.
- Preserved WebUI IM send path through `/api/web/im/messages`.
- Preserved CLI `instance input` outside Web management scope.

### Side Thread Resource Boundary Prompt

Completed:

- Expanded `render_side_frame()` with the memo resource model.
- Kept dynamic `task_id`, source JSON, context JSON, and allowed result actions in every frame.
- Clarified allowed side resources: frame/source reads, bounded read-only inspection, exact current-source IM reply/absorbed closure, and one Task Sys result.
- Clarified forbidden side resources: parent continuity, workspace, browser/web/research, Track shared-state writes/comments, artifacts/evidence, checkpoint state, runtime raw writes, permission changes, and non-source outbound communication.
- Kept `SIDE_BOUNDARY_PROMPT` and `SIDE_DEVELOPER_INSTRUCTIONS` unchanged.
- Did not add tool-layer hard resource isolation.

### Parent Idle Interrupt Submit Bug

Completed:

- Added no-active-turn detection in Task Sys runtime interrupt submit.
- `interrupt_submit_parent` now treats idle/no-active-turn interrupt failure as a no-op and still submits the parent frame.
- Existing running-parent behavior still interrupts before submit and returns `interrupted_turn_id`.
- `parent_handoff_instruction()` now builds the parent instruction without advancing durable task state.
- Added `record_parent_handoff_started()` and call it only after parent runtime execution succeeds.
- Runtime failure before parent submit leaves the task in `needs_parent` with no active processor.
- Did not restore old raw IM-to-parent prompt paths or route through the legacy daemon submit helper.

## End-To-End Contracts

- WebUI message composer action -> `/api/web/im/messages` -> IM send/wake path remains covered; old `/api/instances/<actor>/input` Web API is absent.
- Task Sys side start -> fresh task-bound side thread -> `task_sys.side_frame` prompt -> side
  receives resource-boundary rules on every frame.
- Side `task_sys.need_parent(params.interrupt=true)` with idle parent -> Task Sys runtime treats missing active turn as no-op interrupt -> parent frame is submitted and a parent `turn_id` is returned.
- Side `task_sys.need_parent(params.interrupt=true)` with running parent -> Task Sys runtime interrupts first -> parent frame is submitted and both parent `turn_id` and `interrupted_turn_id` are returned.
- Parent runtime failure before submit -> task remains `needs_parent`, avoiding a no-turn `parent_processing` orphan.

## Verification Summary

Phase 01:

- `python -m pytest -q tests/test_web_management.py`
  - Result: `63 passed, 39 subtests passed`.
- `node --test tests/web_management_ui_contract.test.js`
  - Result: pass.
- `python -m py_compile tools/launcher/web_management.py`
  - Result: pass.

Phase 02:

- `python -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py tests/test_task_sys_substrate.py`
  - Result: `21 passed, 16 subtests passed` before phase 03 additions; final Task Sys run after phase 03: `25 passed, 16 subtests passed`.
- `python -m py_compile tools/launcher/task_sys_runtime.py`
  - Result: pass.

Phase 03:

- Focused idle/race/running interrupt tests: `3 passed`.
- Focused parent state transition tests: `2 passed`.
- Focused `task_sys.need_parent` success/failure tests: `2 passed`.
- Broader Task Sys/message/env-tool/daemon/runtime-broker boundary pytest set:
  - Result: `109 passed, 483 subtests passed`.
- `python -m py_compile tools/launcher/task_sys_runtime.py scripts/env/domain/task_sys.py scripts/env/tools/task_sys/_impl.py`
  - Result: pass.

Final gates:

- `python -m pytest -q`
  - Result: `1097 passed, 1605 subtests passed in 615.57s`.
- `node --test tests/web_management_ui_contract.test.js`
  - Result: pass.
- `python -m py_compile tools/launcher/web_management.py tools/launcher/task_sys_runtime.py scripts/env/domain/task_sys.py scripts/env/tools/task_sys/_impl.py`
  - Result: pass.
- `git diff --check`
  - Result: pass.

## Residue Scans

Web input cleanup:

```bash
rg -n "/api/instances/.*/input|action == \"input\"|_send_input|_run_input_command|instance input for|Instance input blocked" tools/launcher tests -S
```

Result: no hits.

Old side triage prompt/outcome:

```bash
rg -n "\[IM MESSAGE TRIAGE|\[TRACK COMMENT TRIAGE|side_interrupt" tools/launcher/task_sys_runtime.py tests/test_task_sys_runtime_executor.py -S
```

Result: no hits.

Side resource-boundary presence:

```bash
rg -n "Core policy: decide by required resources|Allowed side resources|Forbidden side resources|task_sys.checkpoint_update" tools/launcher/task_sys_runtime.py tests/test_task_sys_runtime_executor.py -S
```

Result: hits only in `tools/launcher/task_sys_runtime.py` and `tests/test_task_sys_runtime_executor.py`.

Old direct parent prompt path:

```bash
rg -n "request_parent_message_handling|\[MESSAGE NEEDS PARENT\]|message\.mark\(needs_parent\)|parent_prompt_submitted" tools scripts tests -S
```

Result: no hits.

Legacy parent submit helper:

```bash
rg -n "submit_parent_prompt\(" tools/launcher scripts/env tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py -S
```

Result: only the legacy daemon physical actuator definition and a test fake that fails if `task_sys.need_parent` uses it.

## Final Git Status

```text
 M scripts/env/domain/task_sys.py
 M scripts/env/tools/task_sys/_impl.py
 M tests/test_task_sys_runtime_executor.py
 M tests/test_task_sys_side_processing.py
 M tests/test_task_sys_substrate.py
 M tests/test_web_management.py
 M tools/launcher/task_sys_runtime.py
 M tools/launcher/web_management.py
?? docs/memo/2026-06-29-task-sys-interrupt-submit-parent-idle-bug.md
?? docs/memo/2026-06-29-web-management-input-residue-cleanup.md
?? docs/memo/2026-06-30-task-sys-side-thread-resource-boundary-prompt.md
?? docs/spec/task-sys-memo-optimization/
```

## Remaining Risk

- Manual WebUI product smoke was not run because the automated tests cover the route removal and IM Web path without starting long-lived services. A manual smoke can be run later with explicit lifecycle cleanup checks.
- The legacy daemon physical submit helper remains as a generic actuator covered by old daemon tests; Task Sys runtime does not call it for this path.

## Final Acceptance Decision

Accepted. The three memo tasks are implemented, live surfaces no longer expose the stale Web input API, side frames include the resource-boundary prompt, parent idle/no-active-turn interrupt handoff submits parent frames, no required old-path residue remains in scoped live surfaces, and final verification passed.
