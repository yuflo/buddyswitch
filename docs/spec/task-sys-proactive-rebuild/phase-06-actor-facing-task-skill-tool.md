# Phase 06 - Actor-Facing Task Skill And Tool

## Phase Objective

Move actor-facing task behavior from old taskbox/task-management surfaces to Task Sys. Skills and tools must describe Task Sys operations and preserve the four-layer boundary.

## Current Code Findings

- Old actor-facing task tool/skill surfaces still describe `task.current`, `task.capture`, `task.select`, `task.checkout`, and old taskbox semantics.
- Task Sys now owns task records, side results, and soon parent/checkpoint state.
- Role AGENTS files list old task tools as preferred env tools.

## Old Paths To Remove

- Actor-facing instructions that treat taskbox as source of truth.
- Old task tool semantics that conflict with Task Sys state.
- Prose mirrors of runtime behavior outside source/tests/contracts.

## New Main Path

- Task Sys tool and skill expose legal Task Sys operations.
- Actor-facing docs tell actors to use Task Sys tools for task state and side/parent/checkpoint results.
- Old taskbox tool is removed, replaced, or clearly quarantined until full removal.

## Implementation Steps

- [x] Survey task skill/tool references after Phases 4 and 5.
- [x] Add failing tests for Task Sys tool catalog/actions expected by actor roles.
- [x] Update role-facing guidance and skills to point at Task Sys.
- [x] Remove old taskbox-backed tool actions from actor-facing discovery.
- [x] Verify context/tool catalog output surfaces Task Sys correctly.

## Test Plan

- Tool registry/catalog tests.
- Role AGENTS/source guidance residue tests.
- Existing task tool tests rewritten or removed as old behavior is replaced.

## Residue Search Plan

- `rg -n "taskbox|task_management|task__|task\\.current|task\\.checkout|task-management" tools scripts buddyswitch tests docs -S`
- `rg -n "task_sys|task_sys\\." tools scripts buddyswitch tests docs -S`

## Verification Commands

```bash
python -m py_compile scripts/env/domain/task_sys.py scripts/env/domain/track_comments.py scripts/env/tool_runtime/registry.py scripts/env/tool_runtime/context.py scripts/env/tool_runtime/role_auth.py scripts/env/tools/context/_impl.py scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py tools/launcher/web_management.py
python -m pytest tests/test_task_management_skill_architecture.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_schema_contract.py tests/test_env_tool_active_task_gate.py tests/test_env_native_mcp_server.py tests/test_env_native_mcp_projection.py tests/test_web_management.py::WebManagementProductApiTests::test_actor_console_api_composes_runtime_task_sys_track_and_im_projection -q
python -m pytest tests/test_env_tool_router.py tests/test_black_box_tool_runtime.py tests/test_env_tool_package_independence.py tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_candidate_tasks_use_task_sys_metadata_and_ignore_legacy_shared_tasks tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_get_applies_filters tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_context_summarize_projects_runless_decision_surface -q
python -m pytest tests/test_role_action_auth.py tests/test_run_env_tool.py tests/test_runless_runtime_contract.py tests/test_runtime_skills.py -q
```

## Actual Modification Summary

- Retired the old `task` env tool from registry discovery and role permissions.
- Deleted `scripts/env/tools/task/*`, `scripts/env/domain/task_management.py`, and `scripts/env/repos/tasks.py`.
- Replaced the active-task pre-dispatch check with a Task Sys active-record check.
- Added Task Sys active task listing helpers.
- Moved actor-facing guidance to `task_sys.close`, `task_sys.need_parent`, and `task_sys.checkpoint_update`.
- Updated `context.get`, `context.summarize`, native MCP projection tests, role AGENTS, runtime skills, and web actor console to expose Task Sys instead of taskbox.
- Removed startup creation of per-instance `taskbox` directories.
- Removed old Track comment prompt renderers that still taught taskbox-era task actions.

## Deleted Old Paths

- `scripts/env/tools/task/tool.py`
- `scripts/env/tools/task/_impl.py`
- `scripts/env/tools/task/__init__.py`
- `scripts/env/domain/task_management.py`
- `scripts/env/repos/tasks.py`
- `scripts/env/domain/track_comments.py` prompt renderer section
- `tools/launcher/env.sh` `buddyswitch_instance_ensure_taskbox`
- Launcher calls that created taskbox state during instance start/resume

## Tests Added Or Changed

- Rewrote task-management architecture tests around Task Sys catalog and retired task-tool rejection.
- Rewrote semantic/schema/native-MCP tests to expect `task_sys` and not `task`.
- Rewrote active-task gate tests to expect `E_TASK_SYS_ACTIVE_TASK_REQUIRED` and `task_sys.active_task`.
- Converted shared and local task fixtures to Task Sys task records.
- Deleted obsolete taskbox/TaskViewModel test suites.

## Actual Verification

- `python -m py_compile ...` passed.
- `python -m pytest tests/test_task_management_skill_architecture.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_schema_contract.py tests/test_env_tool_active_task_gate.py tests/test_env_native_mcp_server.py tests/test_env_native_mcp_projection.py tests/test_web_management.py::WebManagementProductApiTests::test_actor_console_api_composes_runtime_task_sys_track_and_im_projection -q` passed: 42 tests, 472 subtests.
- `python -m pytest tests/test_env_tool_router.py tests/test_black_box_tool_runtime.py tests/test_env_tool_package_independence.py tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_candidate_tasks_use_task_sys_metadata_and_ignore_legacy_shared_tasks tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_get_applies_filters tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_context_summarize_projects_runless_decision_surface -q` passed: 26 tests, 22 subtests.
- `python -m pytest tests/test_role_action_auth.py tests/test_run_env_tool.py tests/test_runless_runtime_contract.py tests/test_runtime_skills.py -q` passed: 59 tests, 368 subtests.
- Live-source residue search for `task.current`, `task.capture`, `task.checkout`, `task__current`, `taskbox`, `TaskViewModel`, `E_ACTIVE_TASK_REQUIRED`, `task.active_anchor`, and `task_management` across `scripts`, `tools`, and `buddyswitch` returned no matches.

## Acceptance Status

Accepted. Actor-facing task truth is Task Sys. The old taskbox tool/domain/repo path is removed from live runtime discovery and startup no longer creates taskbox state.
