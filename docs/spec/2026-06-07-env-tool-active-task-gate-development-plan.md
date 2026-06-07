# Env Tool Active Task Gate Development Plan

Date: 2026-06-07
Source:
- `docs/spec/2026-06-07-env-tool-active-task-gate-test-plan.md`
- `docs/memo/2026-06-07-env-tool-active-task-gate-task.md`

## Goal

Add a central env.tool active-task pre-dispatch gate for task-owned actions, without adding handler-level checks or compatibility layers.

## Non-Negotiables

- Work only in `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`.
- Do not edit `buddyswitch/objects/**` or old runtime private state directly.
- Use tests first and verify the new tests fail before production implementation.
- Keep the gate in `scripts/env/tool_runtime/registry.py` after role authorization and args shape validation, before `_invoke_tool`.
- Do not add `task.start`; guidance must use existing `task.current`, `task.capture`, and `task.select`.
- Keep verification focused and avoid broad service-starting suites unless lifecycle cleanup is proven.

## File Responsibilities

- `scripts/env/tool_runtime/definition.py`: define `TASK_REQUIREMENT_FREE`, `TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED`, add required `ActionDefinition.task_requirement`, and validate allowed values.
- `scripts/env/tools/*/tool.py`: declare `task_requirement` for every registered action.
- `scripts/env/tool_runtime/registry.py`: expose `task_requirement` in catalog/semantics and enforce the active-task gate before handler dispatch.
- `tests/test_env_tool_active_task_gate.py`: focused gate behavior, ordering, and no-state-change tests.
- `tests/test_env_tool_semantic_contract.py`: declaration coverage, classification, validation, and semantic exposure tests.

## Implementation Sequence

### Task 1: Add Failing Contract Tests

Modify `tests/test_env_tool_semantic_contract.py`:

- Import `ActionDefinition`, `ToolDefinition`, `validate_definition`, `TASK_REQUIREMENT_FREE`, and `TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED`.
- Add expected free and active-task-required action sets exactly as listed in the test plan.
- Add tests for declaration coverage, valid values, classification, `operation_semantics`, `env_tools_description` action semantics, and invalid value validation.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py -q
```

Expected: fail because `ActionDefinition` has no `task_requirement` contract and semantics do not expose it.

### Task 2: Add Failing Gate Tests

Create `tests/test_env_tool_active_task_gate.py`:

- Build isolated runtime instances with `RuntimeWorkspaceTestMixin`.
- Dispatch through `dispatch_env_tool_request(...)`.
- Patch `_invoke_tool` for handler non-invocation and handler allowance assertions.
- Seed an active taskbox current anchor for the positive path.
- Snapshot relevant runtime state before and after rejected gated dispatch.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_active_task_gate.py -q
```

Expected: fail because the registry currently invokes gated handlers with no active task.

### Task 3: Add ActionDefinition Contract

Modify `scripts/env/tool_runtime/definition.py`:

- Add constants:
  - `TASK_REQUIREMENT_FREE = "free"`
  - `TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED = "active_task_required"`
- Add `_ALLOWED_TASK_REQUIREMENT_VALUES`.
- Add required `task_requirement: str` to `ActionDefinition`.
- In `validate_definition(...)`, reject action definitions whose `task_requirement` is outside the allowed set.

Run semantic contract tests. Expected: tool catalog load failures until every action declares the new field.

### Task 4: Declare Every Action

Modify all registered tool definitions:

- `scripts/env/tools/artifact/tool.py`
- `scripts/env/tools/comment/tool.py`
- `scripts/env/tools/context/tool.py`
- `scripts/env/tools/evidence/tool.py`
- `scripts/env/tools/message/tool.py`
- `scripts/env/tools/request/tool.py`
- `scripts/env/tools/search/tool.py`
- `scripts/env/tools/task/tool.py`
- `scripts/env/tools/track/tool.py`

Classification must match the test plan. For `task/tool.py`, the `_action(...)` helper may set `task_requirement=TASK_REQUIREMENT_FREE` because all task actions stay free.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py -q
```

Expected: remaining failures should be semantic exposure only.

### Task 5: Expose Task Requirement In Semantics

Modify `scripts/env/tool_runtime/registry.py`:

- Add `task_requirement` to `_action_spec_row(...)`.
- Add `task_requirement` to `_action_semantic_row(...)`.
- Add `task_requirement` to `operation_semantics()`.

Run semantic contract tests until they pass.

### Task 6: Enforce Central Gate

Modify `scripts/env/tool_runtime/registry.py`:

- Import task-management projection inside the gate path to avoid widening module import cycles.
- Add `_active_task_required_rejection(...)` near existing rejection helpers.
- Add `_has_active_task_anchor(...)` using `env.domain.task_management.current_view(...)`.
- After role auth and args-shape validation, build `ToolContext`.
- If `action_definition.task_requirement == TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED` and `current_view(...).current_anchor` is empty, return the canonical rejection.
- Only call `_invoke_tool(...)` after the gate passes.

Required rejection details:

- `code="E_ACTIVE_TASK_REQUIRED"`
- `message="active task is required for this env tool action"`
- `permission_boundary="task.active_anchor"`
- `human_summary="Active task is required for this action."`
- `why_blocked` names `{tool}.{action}` and `TaskViewModel.current_anchor`
- `impact="No env action ran and runtime state was unchanged."`
- `state_changed=False`
- `durability="none"`
- `retryable=True`
- guidance names `task.current`, `task.capture`, and `task.select`
- `alternative_capabilities` rows for `task.current`, `task.capture`, and `task.select`
- `extra` includes category, gate source, gate stage, executed flag, and task requirement

Run focused gate tests until they pass.

### Task 7: Focused Verification And Review

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_active_task_gate.py -q
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_tool_feedback.py \
  -q
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  scripts/env/tool_runtime/definition.py \
  scripts/env/tool_runtime/registry.py \
  scripts/env/tools/artifact/tool.py \
  scripts/env/tools/comment/tool.py \
  scripts/env/tools/context/tool.py \
  scripts/env/tools/evidence/tool.py \
  scripts/env/tools/message/tool.py \
  scripts/env/tools/request/tool.py \
  scripts/env/tools/search/tool.py \
  scripts/env/tools/task/tool.py \
  scripts/env/tools/track/tool.py
```

Review checklist:

- Classification table exactly matches registered actions.
- All registered actions declare one `task_requirement`.
- Runtime semantics expose the same value used by dispatch.
- Active-task-required actions reject before handler invocation with no active anchor.
- The same actions reach the handler with an active anchor.
- Free actions remain callable without active anchor.
- Role auth, payload shape, and unsupported action errors happen before the gate.
- Rejection response follows canonical shape and uses current task tool names.
- No broad service-starting verification was run without lifecycle proof.

## Acceptance

Implementation is complete only when Task 7 passes and the review checklist has no gaps.

## Plan Review

- Requirement coverage: all memo definition, dispatch, feedback, semantics, classification, ordering, and verification requirements are represented.
- Scope check: one central gate and one declaration field; no new workflow engine or handler-local compatibility path.
- Ambiguity resolved: task actions stay free even when they mutate taskbox because they are the path to create/select/close the active anchor.
