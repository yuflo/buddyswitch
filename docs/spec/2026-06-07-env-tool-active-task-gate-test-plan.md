# Env Tool Active Task Gate Test Plan

Date: 2026-06-07
Source:
- `docs/memo/2026-06-07-env-tool-active-task-gate-task.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

## Target

Prove that env.tool dispatch enforces one runtime-visible ownership boundary:

```text
task-owned env action requires TaskViewModel.current_anchor before handler dispatch
```

The gate belongs in `scripts/env/tool_runtime/registry.py` after tool/action resolution, role authorization, and args shape validation, and before any tool handler runs. Individual tool handlers must not implement their own active-task checks.

## Resource Lifecycle Guard

This plan uses registry-level and broker-free unit tests. These tests must not start daemon, app-server, browser, watcher, runtime broker daemon, or detached worker processes.

Do not run broad launcher/browser/app-server/daemon suites for this task unless their service-starting helpers have explicit process registration, teardown on assertion failure, pid/process-group termination, cleanup of pid files/sockets/temporary runtime files, and post-run residual checks as required by `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

## Functional Requirements

- Every `ActionDefinition` declares `task_requirement`.
- Allowed values are exactly `free` and `active_task_required`.
- Invalid values fail definition validation.
- `operation_semantics()` and `env_tools_description()[tool]["action_semantics"][action]` expose `task_requirement`.
- Actions classified `free` dispatch normally with no active task.
- Actions classified `active_task_required` dispatch normally when `TaskViewModel.current_anchor` exists.
- Actions classified `active_task_required` reject when `TaskViewModel.current_anchor` is empty.
- Gate rejection uses canonical `tool_results.rejection(...)`.
- Gate rejection has `error.code="E_ACTIVE_TASK_REQUIRED"`, `permission_boundary="task.active_anchor"`, `state_changed=false`, `durability="none"`, and `retryable=true`.
- Gate rejection guidance names existing task tools: `task.current`, `task.capture`, and `task.select`.
- Rejected gated actions do not call the selected handler and do not mutate runtime state.
- Existing ordering is preserved: unsupported tool/action, role authorization failure, and malformed non-object `args` reject before the active-task gate.

## Expected Classification

### Free

- `artifact.list`, `artifact.get`, `artifact.list_attachments`, `artifact.get_attachment`
- `comment.list`
- `context.summarize`, `context.get`, `context.list_sources`
- `message.contacts`, `message.send`, `message.get`, `message.mark`, `message.list`, `message.conversation`
- `request.list`, `request.get`
- `search.status`
- `task.current`, `task.capture`, `task.select`, `task.switch_request`, `task.switch_confirm`, `task.progress`, `task.checkout`, `task.review`
- `track.list`, `track.open`

### Active Task Required

- `artifact.create_revision`, `artifact.update_metadata`, `artifact.attach_file`
- `comment.add`, `comment.resolve`
- `evidence.issue_browser`, `evidence.approve_downgrade`
- `request.create`, `request.accept`, `request.block`, `request.complete`, `request.cancel`
- `search.request`, `search.open_browser`
- `track.create`, `track.update_now`, `track.add_material`, `track.add_update`, `track.add_proof`, `track.archive`

## Test Files

Primary new file:

- `tests/test_env_tool_active_task_gate.py`

Existing contract file to extend:

- `tests/test_env_tool_semantic_contract.py`

## Test Cases

### Contract Coverage

In `tests/test_env_tool_semantic_contract.py`:

- Assert every registered action has `task_requirement`.
- Assert every value is `free` or `active_task_required`.
- Assert the current action set exactly matches the classification table above.
- Assert `operation_semantics()[tool.action]["task_requirement"]` matches the action definition.
- Assert `env_tools_description()[tool]["action_semantics"][action]["task_requirement"]` matches the action definition.
- Assert invalid `ActionDefinition(task_requirement="invalid")` fails `validate_definition(...)`.

### Gate Rejection

In `tests/test_env_tool_active_task_gate.py`:

- Create an active actor instance with no taskbox current anchor.
- Dispatch a valid `active_task_required` action.
- Patch `env.tool_runtime.registry._invoke_tool` so the test fails if it is called.
- Assert response `ok is False`.
- Assert `response["error"]["code"] == "E_ACTIVE_TASK_REQUIRED"`.
- Assert `response["permission_boundary"] == "task.active_anchor"`.
- Assert `response["state_changed"] is False`.
- Assert `response["durability"] == "none"`.
- Assert `response["retryable"] is True`.
- Assert `why_blocked` names the blocked action and missing `TaskViewModel.current_anchor`.
- Assert `allowed_next_actions` mention `task.current`, `task.capture`, and `task.select`.
- Assert `extra` fields are exposed as top-level fields: `category="task_required"`, `gate_source="env.tool task requirement"`, `gate_stage="pre_dispatch"`, `executed is False`, and `task_requirement="active_task_required"`.

### Free Actions Still Work

With no active task:

- Dispatch `task.current` and assert it is not rejected by `E_ACTIVE_TASK_REQUIRED`.
- Dispatch `context.summarize` and assert it is not rejected by `E_ACTIVE_TASK_REQUIRED`.
- Patch `_invoke_tool` for a representative free action and assert it is called exactly once.

### Active Task Allows Dispatch

Seed taskbox for the active actor with one `active` task and `task.selected` history.

- Dispatch a valid `active_task_required` action.
- Patch `_invoke_tool` to return a canonical success response.
- Assert the handler is called once.
- Assert response is the handler response, not an active-task rejection.

### Dispatch Ordering

With no active task:

- Dispatch a role-forbidden gated action and assert role auth rejection happens before the active-task gate.
- Dispatch a gated action with `args` as a non-object and assert `E_ENV_TOOL_PAYLOAD` happens before the active-task gate.
- Dispatch unsupported tool/action and assert existing `E_ENV_TOOL` rejection happens before the active-task gate.

### State Unchanged Guarantee

With no active task:

- Snapshot taskbox and runtime object directories before dispatching a gated action.
- Dispatch a rejected `active_task_required` action.
- Snapshot again.
- Assert snapshots are identical.
- Assert response says `state_changed=false` and `durability=none`.

## Verification Commands

Focused red/green loop:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_active_task_gate.py -q
```

Relevant contract verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_tool_feedback.py \
  -q
```

Compile touched modules:

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

## Acceptance

The test plan passes only when contract tests prove all action declarations and catalog exposure, dispatch tests prove rejection before handler invocation and allowance with an active anchor, ordering tests prove the gate is in the intended stage, and state snapshots prove rejected gated actions do not mutate runtime state.

## Plan Review

- Requirement coverage: each memo requirement maps to a test section above.
- No compatibility path: the plan adds one action-level contract and one central dispatch gate, not handler-local fallbacks.
- Resource safety: verification uses no service-starting suites.
- Anti-cheat check: tests assert externally visible behavior, handler non-invocation, state snapshots, and catalog semantics rather than implementation-only details.
