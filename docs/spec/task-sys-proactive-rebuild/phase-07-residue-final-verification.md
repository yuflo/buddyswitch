# Phase 07 - Residue And Final Verification

## Phase Objective

Remove old task/daemon actor-driving residue, rewrite tests that still encode old behavior, and close with full verification. Deletion is part of acceptance.

## Current Code Findings

- Phase 0 residue map identifies old direct inbound, side, parent, checkpoint, and taskbox paths.
- Phases 1-6 progressively replace those paths.
- Generic physical daemon/app-server actuators may remain only if they are Task Sys instruction executors, not business semantic owners.

## Old Paths To Remove

- Old/new dual task systems.
- Raw inbound to actor turn.
- Business handler direct side/parent submit.
- Side direct parent submit or interrupt.
- Interrupt as a side outcome.
- Old checkpoint recommendation prompt path.
- Taskbox as actor-facing task truth.

## New Main Path

- All actor-driving inbound enters Task Sys.
- Task Sys owns task state, side result, parent handoff, checkpoint UI, and actor-facing task operations.
- Daemon/launcher owns only physical instruction execution.

## Implementation Steps

- [x] Run full old-path residue searches.
- [x] Delete obsolete modules/tests/docs or rewrite them to Task Sys.
- [x] Run focused suites by boundary.
- [x] Run broader relevant suite.
- [x] Record final residue with explicit allowed physical actuator internals.

## Test Plan

- Full focused suites from all previous phases.
- Broader integration suites for launcher, daemon service, web management, env tool registry, and task sys.
- `git diff --check`, compile checks, and targeted residue searches.

## Residue Search Plan

- `rg -n "submit_turn|submit_parent_prompt|submit_side_triage_prompt|TASK CHECKPOINT|taskbox|task_management|task_tui|needs_parent_disposition|side_interrupt" tools scripts tests buddyswitch docs -S`
- `rg -n "task_sys|task-sys|task_sys.side_frame|task_sys.parent_frame|task_sys.checkpoint" tools scripts tests buddyswitch docs -S`

## Verification Commands

- `python -m py_compile scripts/env/domain/task_sys.py scripts/env/domain/track_comments.py scripts/env/tool_runtime/registry.py scripts/env/tool_runtime/context.py scripts/env/tool_runtime/role_auth.py scripts/env/tools/context/_impl.py scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py tools/launcher/web_management.py`
- `python -m pytest tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_checkpoint.py tests/test_task_sys_runtime_executor.py -q`
- `python -m pytest tests/test_task_management_skill_architecture.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_schema_contract.py tests/test_env_tool_active_task_gate.py tests/test_env_native_mcp_server.py tests/test_env_native_mcp_projection.py tests/test_web_management.py::WebManagementProductApiTests::test_actor_console_api_composes_runtime_task_sys_track_and_im_projection -q`
- `python -m pytest tests/test_env_tool_router.py tests/test_black_box_tool_runtime.py tests/test_env_tool_package_independence.py tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_candidate_tasks_use_task_sys_metadata_and_ignore_legacy_shared_tasks tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_get_applies_filters tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_context_summarize_projects_runless_decision_surface -q`
- `python -m pytest tests/test_role_action_auth.py tests/test_run_env_tool.py tests/test_runless_runtime_contract.py tests/test_runtime_skills.py -q`
- `python -m pytest tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_checkpoint.py tests/test_task_sys_runtime_executor.py tests/test_submit_turn.py tests/test_im_wake_handler.py tests/test_track_comment_added_handler.py tests/test_task_checkout_handler.py tests/test_message_tool_im_client.py tests/test_env_tool_response_contract.py tests/test_env_tool_payload_contract.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_role_action_auth.py tests/test_task_management_skill_architecture.py tests/test_runtime_skills.py tests/test_daemon_core_decoupling.py tests/test_daemon_service_contract.py tests/test_env_tool_router.py tests/test_black_box_tool_runtime.py tests/test_env_tool_package_independence.py tests/test_env_tool_active_task_gate.py -q`
- `python -m pytest tests/test_web_management.py::WebManagementHTTPTests::test_input_route_delegates_and_reports_task_sys_task tests/test_web_management.py::WebManagementProductApiTests::test_actor_console_api_composes_runtime_task_sys_track_and_im_projection -q`
- `python -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_does_not_create_private_taskbox_for_active_role tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_fake_codex_real_completed_event_records_task_sys_completion tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_daemon_origin_completion_real_shape_does_not_loop tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_daemon_ignores_other_thread_real_completion_in_fake_codex -q`
- `python -m pytest -q`
- `git diff --check`
- Residue searches:
  - `rg -n "task\.current|task\.capture|task\.checkout|task__current|task__checkout|TaskViewModel|E_ACTIVE_TASK_REQUIRED|task\.active_anchor|taskbox|task_management" scripts tools buddyswitch docs/arch -S`
  - `rg -n "submit_parent_prompt|submit_side_triage_prompt|\[TASK CHECKPOINT\]|task_tui|request_parent_message_handling|message\.mark\(needs_parent\)|needs_parent_disposition|side_interrupt" scripts tools buddyswitch docs/arch -S`
  - `rg -n "submit_parent_prompt\(|submit_side_triage_prompt\(" tools/launcher/im_wake_handler.py tools/launcher/track_comment_added_handler.py tools/launcher/task_checkout_handler.py scripts/env -S`

## Actual Modification Summary

- Task Sys is now the single task-state and actor-driving substrate for user input, IM wakes, track comments, side processing, parent handoff, and checkpoint updates.
- Inbound launcher and handler paths ingest envelopes into Task Sys and execute explicit runtime instructions instead of rendering actor prompts directly.
- Actor-facing task actions moved to `task_sys.close`, `task_sys.need_parent`, and `task_sys.checkpoint_update`.
- Runtime context, tool auth, tool registry, web management projection, role instructions, and the shared task-management skill now point at Task Sys only.
- Checkpoint handling is a Task Sys frame with explicit actor update outcome, not a daemon-generated recommendation prompt.
- The daemon/app-server layer is left as a physical instruction executor only.

## Deleted Old Paths

- `scripts/env/domain/task_management.py`
- `scripts/env/domain/task_tui.py`
- `scripts/env/repos/tasks.py`
- `scripts/env/tools/task/`
- Taskbox creation during instance start/resume.
- Old direct parent-message request path from `message.mark(needs_parent)`.
- Old track-comment prompt rendering helpers.
- Obsolete old task-tool tests that encoded `task.current`/`task.capture`.

## Tests Added Or Changed

- Added Task Sys substrate, side-processing, checkpoint, and runtime-executor tests.
- Rewrote launcher, IM wake, track comment, task checkout, web management, env tool, role auth, native MCP, runtime skill, and context tests around Task Sys.
- Added negative coverage for retired `task` tool exposure, old active-task guidance, unsupported side interrupt outcome, and direct parent handoff bypasses.
- Full-suite residue cleanup rewrote remaining env store, identity ownership, IM external wake bridge, context capability snapshot, and repo consistency expectations away from the deleted task repo and old parent-prompt task surface.

## Actual Verification

- Compile checks passed for the changed Task Sys, runtime context/tool, and launcher modules.
- Task Sys focused suite passed: `24 passed, 16 subtests passed`.
- Phase 6 env/tool/web slice passed: `42 passed, 472 subtests passed`.
- Router/package/context/host slice passed: `26 passed, 22 subtests passed`.
- Role/run/runtime-skills slice passed: `59 passed, 368 subtests passed`.
- Broad relevant integration suite passed: `211 passed, 966 subtests passed`.
- Web management focused nodes passed: `2 passed, 2 subtests passed`.
- Launcher focused nodes passed: `4 passed`.
- Full pytest passed: `1096 passed, 1607 subtests passed`.
- `git diff --check` passed.
- Old taskbox/task action residue search over `scripts`, `tools`, `buddyswitch`, and `docs/arch` returned no hits.
- Direct caller search for `submit_parent_prompt(` and `submit_side_triage_prompt(` in handlers and `scripts/env` returned no hits.
- The only live old submit-name hits are `tools/launcher/daemon_core.py::submit_parent_prompt` and `tools/launcher/daemon_core.py::submit_side_triage_prompt`. These are retained as generic physical daemon actuators; they no longer own business task semantics or handler policy.
- Remaining old-path terms in tests/spec docs are intentional negative assertions, fakes, daemon physical-actuator contract coverage, or historical phase/memo records.

## Acceptance Status

Accepted.
