# Phase 05 - Checkpoint And InnerTUI

## Phase Objective

Rebuild turn-complete checkpoint as Task Sys UI, not a daemon prompt. Checkpoint must expose current task context, pending task context, legal operations, required params, and constraints without recommending work or making decisions for Codex.

## Current Code Findings

- Phase 2 turn-complete checkout now records a closed `app_server.turn_completed` Task Sys task with `no_actor_action`.
- Old `scripts/env/domain/task_tui.py` still contains `[TASK CHECKPOINT]` rendering and existing tests.
- No Task Sys checkpoint UI/tool loop exists yet.

## Old Paths To Remove

- Old turn complete to `[TASK CHECKPOINT]` prompt path.
- Taskbox-backed checkpoint UI as the runtime source of truth.
- Checkpoint copy that recommends tasks or makes task decisions.

## New Main Path

- Task Sys reads task state and produces a lightweight checkpoint frame.
- A minimal Task Sys tool updates task state from checkpoint actions.
- Checkpoint UI is Task Sys innerTUI context only; Codex still decides which legal operation to call.

## Implementation Steps

- [x] Add failing tests for turn-complete entering Task Sys checkpoint state.
- [x] Add minimal checkpoint frame renderer in Task Sys.
- [x] Add one Task Sys checkpoint/update tool action.
- [x] Route completed-turn no-op from Phase 2 into checkpoint processing.
- [x] Remove or mark old `task_tui` checkpoint renderer as obsolete.

## Test Plan

- Focused Task Sys checkpoint domain/tool tests.
- Daemon completion integration tests proving no `[TASK CHECKPOINT]` prompt.
- Residue tests for old taskbox checkpoint dependency.

## Residue Search Plan

- `rg -n "\\[TASK CHECKPOINT\\]|render_stop_task_tui|task_tui|task_management" tools scripts tests -S`
- `rg -n "checkpoint|innerTUI|task_sys.checkpoint" tools scripts tests -S`

## Verification Commands

- Red check before implementation:
  - `python -m pytest tests/test_task_sys_checkpoint.py tests/test_task_sys_runtime_executor.py tests/test_task_checkout_handler.py::TaskCheckoutHandlerSendTests::test_accepted_completed_turn_ingests_task_without_parent_prompt tests/test_task_checkout_handler.py::TaskCheckoutHandlerSendTests::test_task_checkout_records_checkpoint_turn_as_daemon_origin -q`
  - Failed because `initial_processor=checkpoint`, `record_checkpoint_update`, checkpoint tool action, checkpoint frame rendering, and checkpoint daemon-origin tracking did not exist.
- Focused green check:
  - `python -m pytest tests/test_task_sys_checkpoint.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py tests/test_task_checkout_handler.py::TaskCheckoutHandlerSendTests::test_accepted_completed_turn_ingests_task_without_parent_prompt tests/test_task_checkout_handler.py::TaskCheckoutHandlerSendTests::test_task_checkout_records_checkpoint_turn_as_daemon_origin tests/test_task_checkout_handler.py::TaskCheckoutHandlerSendTests::test_second_completed_turn_records_second_task_without_prompt_retry_state -q`
- Broader green check:
  - `python -m pytest tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_checkpoint.py tests/test_task_sys_runtime_executor.py tests/test_task_checkout_handler.py tests/test_daemon_core_decoupling.py tests/test_daemon_service_contract.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_role_action_auth.py tests/test_task_input_context.py tests/test_task_management_skill_architecture.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_fake_codex_real_completed_event_records_task_sys_completion tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_daemon_origin_completion_real_shape_does_not_loop tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_daemon_ignores_other_thread_real_completion_in_fake_codex -q`
- Compile check:
  - `python -m py_compile scripts/env/domain/task_sys.py scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py tools/launcher/task_sys_runtime.py tools/launcher/task_sys_ingress.py tools/launcher/task_checkout_handler.py scripts/env/tool_runtime/role_auth.py`

## Actual Modification Summary

- Added `initial_processor="checkpoint"` to Task Sys ingest. Completed turns now create a `checkpoint` task with `active_processor="checkpoint"` and `checkpoint_metadata.state="awaiting_update"`.
- Added `task_sys.checkpoint` frame generation with completed turn context, empty current/pending task contexts, legal operations, required params, and constraints. The frame explicitly avoids recommending a next task.
- Added `task_sys.record_checkpoint_update(task_id, update)` for the minimal checkpoint UI loop.
- Added `task_sys.checkpoint_update` native tool action and role permission.
- Extended `tools/launcher/task_sys_runtime.py` so `submit_parent` can render and submit either `task_sys.parent_frame` or `task_sys.checkpoint`.
- Changed `ingest_turn_completed()` to request checkpoint processing instead of `no_actor_action`.
- Changed `task_checkout_handler` to record the submitted checkpoint turn as daemon-origin for `task_checkout`, preventing checkpoint completion loops.
- Removed obsolete `scripts/env/domain/task_tui.py`.
- Isolated launcher test helper subprocess environment from inherited `BUDDYSWITCH_SHARED_ROOT` / `BUDDYSWITCH_STATE_ROOT` to keep broad test runs deterministic.

## Deleted Old Paths

- Deleted the old `[TASK CHECKPOINT]` renderer file `scripts/env/domain/task_tui.py`.
- Removed the old `task_tui.render_stop_task_tui` test.
- Completed-turn handling no longer records a closed no-op task; it now creates a Task Sys checkpoint frame and submits it through Task Sys runtime execution.

## Tests Added Or Changed

- Added `tests/test_task_sys_checkpoint.py` for checkpoint ingest, checkpoint update, and action registration.
- Updated `tests/test_task_sys_runtime_executor.py` with checkpoint frame rendering and submit execution tests.
- Updated `tests/test_task_checkout_handler.py` to assert checkpoint instruction execution and daemon-origin loop guard.
- Updated completed-turn tests in `tests/test_buddyswitch_launcher.py` to assert `task_sys.checkpoint` frame submission and no `[TASK CHECKPOINT]` text.
- Updated semantic/schema/role tests for `task_sys.checkpoint_update`.
- Removed obsolete task TUI renderer expectations from `tests/test_task_input_context.py` and `tests/test_task_management_skill_architecture.py`.

## Actual Verification

- `python -m pytest tests/test_task_sys_checkpoint.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py tests/test_task_checkout_handler.py::TaskCheckoutHandlerSendTests::test_accepted_completed_turn_ingests_task_without_parent_prompt tests/test_task_checkout_handler.py::TaskCheckoutHandlerSendTests::test_task_checkout_records_checkpoint_turn_as_daemon_origin tests/test_task_checkout_handler.py::TaskCheckoutHandlerSendTests::test_second_completed_turn_records_second_task_without_prompt_retry_state -q`
  - `20 passed in 0.16s`
- `python -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_fake_codex_real_completed_event_records_task_sys_completion tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_daemon_origin_completion_real_shape_does_not_loop tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_daemon_ignores_other_thread_real_completion_in_fake_codex -q`
  - `3 passed in 17.08s`
- `python -m pytest tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_checkpoint.py tests/test_task_sys_runtime_executor.py tests/test_task_checkout_handler.py tests/test_daemon_core_decoupling.py tests/test_daemon_service_contract.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_role_action_auth.py tests/test_task_input_context.py tests/test_task_management_skill_architecture.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_fake_codex_real_completed_event_records_task_sys_completion tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_daemon_origin_completion_real_shape_does_not_loop tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_daemon_ignores_other_thread_real_completion_in_fake_codex -q`
  - `112 passed, 605 subtests passed in 18.45s`
- `python -m py_compile scripts/env/domain/task_sys.py scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py tools/launcher/task_sys_runtime.py tools/launcher/task_sys_ingress.py tools/launcher/task_checkout_handler.py scripts/env/tool_runtime/role_auth.py`
  - Passed.
- Residue searches:
  - `rg -n "\\[TASK CHECKPOINT\\]|render_stop_task_tui|task_tui" tools scripts tests -S`
    - Only negative assertions and forbidden-token lists remain.
  - `rg -n "checkpoint|innerTUI|task_sys.checkpoint" tools scripts tests -S`
    - Live hits are the new Task Sys checkpoint frame/tool path plus old taskbox wording scheduled for Phase 6.

## Acceptance Status

Accepted for Phase 5. Completed turns now enter Task Sys checkpoint state and submit a `task_sys.checkpoint` frame; the old `[TASK CHECKPOINT]` renderer has been removed.
