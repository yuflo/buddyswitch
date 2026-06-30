# Phase 04 - Parent Handoff And Interrupt

## Phase Objective

Rebuild parent handoff so parent turns receive only Task Sys framed input. `interrupt` must be driven by Task Sys state and runtime instructions, not by business handlers or side threads.

## Current Code Findings

- `task_sys.record_side_result(... need_parent ...)` now records `parent_handoff_params` and status `needs_parent`.
- `task_sys.runtime_instruction` already has `submit_parent` and `interrupt_submit_parent` shapes, but no transition currently creates those instructions from recorded handoff params.
- `tools/launcher/daemon_core.py` still owns generic physical parent submit/interrupt helpers.
- Actor-driving business handlers no longer call parent submit directly after Phase 2.

## Old Paths To Remove

- Any business handler direct call to parent submit.
- Side result paths that directly submit or interrupt parent.
- Parent prompts that are not traceable to a Task Sys task id.

## New Main Path

- Task Sys converts `needs_parent` task state into a parent frame and either `submit_parent` or `interrupt_submit_parent`.
- Daemon/launcher runtime executes those instructions physically.
- Parent frame includes task id, source refs, side result, and parent handoff params.

## Implementation Steps

- [x] Add failing domain tests for converting `need_parent(params)` into parent runtime instructions.
- [x] Add parent frame rendering with task id/source refs/handoff params.
- [x] Add runtime executor support for `submit_parent` and `interrupt_submit_parent`.
- [x] Route side `need_parent` tool result to produce/execute the parent instruction only through Task Sys.
- [x] Remove or quarantine any old side-to-parent escalation path.

## Test Plan

- Focused domain/tool/runtime tests for `need_parent -> parent instruction`.
- Handler residue tests proving no business handler parent submit calls.
- Daemon runtime tests for physical submit/interrupt execution from Task Sys instruction.

## Residue Search Plan

- `rg -n "submit_parent_prompt\\(" tools/launcher scripts tests -S`
- `rg -n "interrupt_policy|ensure_stopped|before_submit|interrupt_submit_parent|submit_parent" tools/launcher scripts tests -S`
- `rg -n "needs_parent|parent_handoff_params|task_sys.parent_frame" tools scripts tests -S`

## Verification Commands

- Red check before implementation:
  - `python -m pytest tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py -q`
  - Failed because `parent_handoff_instruction`, `render_parent_frame`, parent executor support, and tool-triggered parent runtime execution did not exist.
- Focused green checks:
  - `python -m pytest tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py -q`
  - `python -m pytest tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py tests/test_message_tool_im_client.py tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_message_mark_needs_parent_rejects_without_parent_submit tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_all_expected_actions_have_semantic_boundary_text tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_message_catalog_uses_identity_language tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_live_broker_message_needs_parent_rejects_without_parent_submit -q`
- Broader green check:
  - `python -m pytest tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py tests/test_message_tool_im_client.py tests/test_env_tool_response_contract.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_role_action_auth.py tests/test_daemon_core_decoupling.py tests/test_daemon_service_contract.py tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_live_broker_message_needs_parent_rejects_without_parent_submit -q`
- Compile check:
  - `python -m py_compile scripts/env/domain/task_sys.py scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py tools/launcher/task_sys_runtime.py scripts/env/tool_runtime/context.py scripts/env/tool_runtime/im_client.py scripts/env/tools/message/tool.py`

## Actual Modification Summary

- Added `task_sys.parent_handoff_instruction(task_id)`, which requires a `needs_parent` task, builds a `task_sys.parent_frame`, chooses `submit_parent` or `interrupt_submit_parent` from normalized handoff params, and moves the task to `parent_processing`.
- Added `task_sys.get_task(task_id)` for tool response readback after the handoff transition.
- Added `render_parent_frame()` and parent instruction execution to `tools/launcher/task_sys_runtime.py`.
- Added `DaemonAccess.execute_task_sys_instruction()` so env tools can pass Task Sys runtime instructions to the generic launcher executor.
- Updated `task_sys.need_parent` so the side result records state, asks Task Sys for the parent instruction, executes it through the daemon context, and returns the parent runtime result.
- Updated `message.mark` so `needs_parent` is rejected with guidance to use `task_sys.need_parent`; it no longer builds or submits parent prompts.
- Updated message and Task Sys tool catalog contracts to reflect the new parent handoff boundary.

## Deleted Old Paths

- Removed the IM client direct parent prompt rendering path for `message.mark(needs_parent)`.
- Removed `DaemonAccess.request_parent_message_handling`, the old semantic bridge from IM message disposition to parent prompt submit.
- Quarantined `DaemonRuntime.submit_parent_prompt` as a low-level legacy/generic actuator surface only; no business handler or message tool uses it in this phase.

## Tests Added Or Changed

- `tests/test_task_sys_substrate.py`
  - Added parent handoff instruction tests for `need_parent(params)` and invalid non-parent-ready tasks.
- `tests/test_task_sys_runtime_executor.py`
  - Added parent frame rendering, submit-parent execution, and interrupt-submit-parent execution tests.
- `tests/test_task_sys_side_processing.py`
  - Added a `task_sys.need_parent` tool test proving parent execution goes through `execute_task_sys_instruction`, not raw `submit_parent_prompt`.
- `tests/test_message_tool_im_client.py`
  - Replaced old prompt-submit failure expectation with rejection of `needs_parent` message disposition.
- `tests/test_env_tool_response_contract.py`
  - Replaced old parent prompt failure contract with a no-parent-submit rejection contract.
- `tests/test_runtime_broker.py`
  - Replaced live broker old parent-submit test with a rejection test that fails if the old projected `daemon_core` parent path is imported.
- `tests/test_env_tool_schema_contract.py` and `tests/test_env_tool_semantic_contract.py`
  - Updated catalog/schema expectations for absorbed-only `message.mark` and the new `task_sys` tool actions.

## Actual Verification

- `python -m pytest tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py -q`
  - `19 passed, 16 subtests passed in 0.09s`
- `python -m pytest tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py tests/test_message_tool_im_client.py tests/test_env_tool_response_contract.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_role_action_auth.py tests/test_daemon_core_decoupling.py tests/test_daemon_service_contract.py tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_live_broker_message_needs_parent_rejects_without_parent_submit -q`
  - `104 passed, 568 subtests passed in 2.10s`
- `python -m py_compile scripts/env/domain/task_sys.py scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py tools/launcher/task_sys_runtime.py scripts/env/tool_runtime/context.py scripts/env/tool_runtime/im_client.py scripts/env/tools/message/tool.py`
  - Passed.
- Residue searches:
  - `rg -n "request_parent_message_handling|\\[MESSAGE NEEDS PARENT\\]|message\\.mark\\(needs_parent\\)|parent_prompt_submitted" tools scripts tests -S`
    - Only a negative assertion for `[MESSAGE NEEDS PARENT]` remains.
  - `rg -n "submit_parent_prompt\\(" tools/launcher scripts tests -S`
    - Live code hit is `tools/launcher/daemon_core.py` generic actuator definition; other hits are tests/fakes.
  - `rg -n "interrupt_policy|ensure_stopped|before_submit|interrupt_submit_parent|submit_parent" tools/launcher scripts tests -S`
    - Task Sys hits are the new instruction contract/executor/tests; `DaemonRuntime` interrupt-policy hits remain in generic actuator tests.

## Acceptance Status

Accepted for Phase 4. Parent handoff now flows from Task Sys side result to Task Sys parent frame to Task Sys runtime instruction, and the old IM side-to-parent prompt path is removed.
