# Task Sys Proactive Rebuild Final Acceptance

Source memo: `docs/memo/2026-06-29-task-sys-proactive-rebuild.md`

## Required Source Review

- Read `docs/memo/2026-06-29-task-sys-proactive-rebuild.md`.
- Read `AGENTS.md`.
- Read all current `docs/bitter/*` principle notes.
- Read the task-sys rebuild spec records in this directory.

This document is an acceptance record for the implementation evidence. It does not restate the memo as a second source of truth.

## Phase Status

| Phase | Record | Status | Evidence |
| --- | --- | --- | --- |
| 0 | `phase-00-boundary-residue.md` | Accepted | Orientation, survey, master plan, old path map, and runtime-maintenance classification exist. |
| 1 | `phase-01-minimal-task-sys-substrate.md` | Accepted | Task Sys record, ingest, state transitions, and runtime instruction substrate verified. |
| 2 | `phase-02-inbound-ingress.md` | Accepted | CLI/Web input, IM wake, Track comment wake, and turn-complete checkout enter Task Sys first. |
| 3 | `phase-03-side-fast-processing.md` | Accepted | Side processing uses `task_sys.side_frame`; side outcomes are only `close` and `need_parent(params)`. |
| 4 | `phase-04-parent-handoff-interrupt.md` | Accepted | Parent handoff and interrupt flow through Task Sys parent frames and runtime instructions. |
| 5 | `phase-05-checkpoint-innertui.md` | Accepted | Completed turns create `task_sys.checkpoint` frames; old `[TASK CHECKPOINT]` renderer is removed. |
| 6 | `phase-06-actor-facing-task-skill-tool.md` | Accepted | Actor-facing task truth is Task Sys; old taskbox tool/domain/repo path is removed. |
| 7 | `phase-07-residue-final-verification.md` | Accepted | Final residue cleanup and full relevant verification recorded. |

## Global Old Path Deletion List

- Deleted `scripts/env/domain/task_management.py`.
- Deleted `scripts/env/domain/task_tui.py`.
- Deleted `scripts/env/repos/tasks.py`.
- Deleted `scripts/env/tools/task/`.
- Deleted obsolete taskbox-backed tests `tests/test_task_env_tool.py` and `tests/test_task_input_context.py`.
- Removed taskbox creation during instance start/resume.
- Removed direct raw `instance input` submission through `submit_turn.py`; input now creates a Task Sys task and executes a Task Sys runtime instruction.
- Removed IM and Track handler prompt rendering as actor-driving business logic.
- Removed Track comment prompt renderers from `scripts/env/domain/track_comments.py`.
- Removed the direct `message.mark(needs_parent)` parent-submit path; parent handoff now uses `task_sys.need_parent`.
- Replaced old active-task gate language and code with Task Sys active-task validation.
- Rewrote role guidance, shared task-management skill, native MCP projection, web management projection, and runtime context to expose Task Sys instead of taskbox.

## Test Coverage Matrix

| Requirement | Primary evidence |
| --- | --- |
| Task Sys substrate creates records and runtime instructions without daemon ownership | `tests/test_task_sys_substrate.py` |
| Side result model is limited to `close` and `need_parent(params)` | `tests/test_task_sys_side_processing.py`, `tests/test_task_sys_runtime_executor.py` |
| Parent handoff and interrupt are Task Sys runtime instructions | `tests/test_task_sys_side_processing.py`, `tests/test_task_sys_runtime_executor.py`, `tests/test_message_tool_im_client.py`, `tests/test_daemon_service_contract.py` |
| Checkpoint is Task Sys UI, not daemon recommendation prompt | `tests/test_task_sys_checkpoint.py`, `tests/test_task_checkout_handler.py`, `tests/test_buddyswitch_launcher.py` |
| CLI/Web user input enters Task Sys first | `tests/test_buddyswitch_launcher.py`, `tests/test_submit_turn.py`, `tests/test_web_management.py` |
| IM and Track actor-driving inbound enter Task Sys first | `tests/test_im_wake_handler.py`, `tests/test_im_external_reply_loop.py`, `tests/test_track_comment_added_handler.py` |
| Actor-facing task tool/skill surface is Task Sys-only | `tests/test_task_management_skill_architecture.py`, `tests/test_env_tool_schema_contract.py`, `tests/test_env_tool_semantic_contract.py`, `tests/test_role_action_auth.py`, `tests/test_runtime_skills.py` |
| Active-task gate uses Task Sys state | `tests/test_env_tool_active_task_gate.py`, `tests/test_runtime_broker.py` |
| Context, native MCP, and web projections expose Task Sys | `tests/test_context_binding_env_tool.py`, `tests/test_env_native_mcp_server.py`, `tests/test_env_native_mcp_projection.py`, `tests/test_web_management.py` |
| Old taskbox/task action residue is not live guidance | `tests/test_repo_consistency.py`, scoped `rg` residue searches |

## Global Residue Search Results

Final scoped live-surface searches:

```bash
rg -n "task\.current|task\.capture|task\.checkout|task__current|task__checkout|TaskViewModel|E_ACTIVE_TASK_REQUIRED|task\.active_anchor|taskbox|task_management" scripts tools buddyswitch docs/arch -S
```

Result: no hits.

```bash
rg -n "submit_parent_prompt|submit_side_triage_prompt|\[TASK CHECKPOINT\]|task_tui|request_parent_message_handling|message\.mark\(needs_parent\)|needs_parent_disposition|side_interrupt" scripts tools buddyswitch docs/arch -S
```

Result: only `tools/launcher/daemon_core.py::submit_parent_prompt` and `tools/launcher/daemon_core.py::submit_side_triage_prompt` remain. These are generic physical daemon actuators, not business handler policy or Task Sys bypasses.

```bash
rg -n "submit_parent_prompt\(|submit_side_triage_prompt\(" tools/launcher/im_wake_handler.py tools/launcher/track_comment_added_handler.py tools/launcher/task_checkout_handler.py scripts/env -S
```

Result: no hits.

Remaining old-path words in tests and phase documents are negative assertions, fakes, daemon physical-actuator contract tests, or historical implementation records.

## Final Verification

Fresh final verification after the last implementation edits:

```bash
python -m py_compile scripts/env/domain/task_sys.py scripts/env/domain/track_comments.py scripts/env/tool_runtime/registry.py scripts/env/tool_runtime/context.py scripts/env/tool_runtime/im_client.py scripts/env/tool_runtime/role_auth.py scripts/env/tools/context/_impl.py scripts/env/tools/message/tool.py scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py tools/launcher/task_sys_ingress.py tools/launcher/task_sys_runtime.py tools/launcher/im_wake_handler.py tools/launcher/track_comment_added_handler.py tools/launcher/task_checkout_handler.py tools/launcher/web_management.py
```

Result: passed.

```bash
python -m pytest -q
```

Result: `1096 passed, 1607 subtests passed`.

```bash
git diff --check
```

Result: passed.

## Remaining Risk

- The daemon runtime still exposes `submit_parent_prompt` and `submit_side_triage_prompt` method names as low-level physical actuators covered by daemon service tests. Current live handler and env-tool paths no longer call them directly for business decisions.
- The implementation intentionally stays minimal: Task Sys has concrete records, frames, and simple state transitions, but no workflow engine, event bus, priority system, recommendation system, or plugin scheduler.
- Scheduled/browser maintenance remains daemon-owned when it does not drive actor work. Future actor-driving scheduled/browser events must enter Task Sys at ingress.

## Final Acceptance Decision

Accepted. Current evidence shows the rebuild target is satisfied: actor-driving inbound enters Task Sys first, actor runtime receives Task Sys-framed input, side results are constrained to Task Sys outcomes, parent/interrupt/checkpoint flow through Task Sys runtime instructions, old taskbox truth is removed, and no raw inbound actor-driving compatibility path remains in live source surfaces.
