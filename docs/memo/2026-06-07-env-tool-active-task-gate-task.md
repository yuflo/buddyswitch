# Env Tool Active Task Gate Task

Date: 2026-06-07
Status: focused implementation memo

## Highlight Summary

> **Highlight: Core capability.** Env tool runtime must reject task-owned work when the active actor has no `TaskViewModel.current_anchor`.

> **Highlight: Stable boundary.** The gate belongs to `scripts/env/tool_runtime/registry.py` before handler dispatch, not inside individual tool implementations.

> **Highlight: Source of truth.** Each env action declares one runtime contract value: `task_requirement = free | active_task_required`.

> **Highlight: Feedback contract.** Rejection must use canonical `tool_results.rejection(...)`, with `error.code = E_ACTIVE_TASK_REQUIRED`, `state_changed = false`, and `durability = none`.

> **Highlight: Current task operations.** Feedback must guide actor through existing task tools: `task.current`, `task.capture`, and `task.select`. There is currently no `task.start`.

> **Highlight: Done means tested.** Every registered action must have task requirement coverage, and gated actions must be proven to reject before their handler runs.

## Task

Add an active-task precondition to env tool dispatch.

When an env action is classified as `active_task_required`, runtime checks the active actor's task view before invoking the selected tool handler. If `TaskViewModel.current_anchor` is empty, runtime returns a canonical rejection and does not call the handler.

This makes task ownership a runtime-visible contract:

```text
env.tool payload
  -> resolve tool/action
  -> role authorization
  -> args shape validation
  -> active task gate
  -> tool handler
```

## Product Reason

The immediate value of a task is not long-term bookkeeping. It is the active work owner for substantial work: context anchor, evidence owner, recovery point, and checkout target.

The runtime should not infer what the incoming input means. It should enforce only one concrete boundary:

```text
task-owned action needs active task owner before execution
```

## Runtime Contract

Add a required field to `ActionDefinition`:

```python
task_requirement: str
```

Allowed values:

```text
free
active_task_required
```

Validation requirements:

- every `ActionDefinition` must declare this field;
- values outside the two allowed strings fail definition validation;
- `operation_semantics` and tool catalog output should expose this value so actor-visible tool semantics match runtime behavior.

This is an action contract declaration only. Tool handlers do not implement this check.

## Dispatch Behavior

### Free Action

```text
task_requirement = free
-> dispatch normally
```

### Active Task Required With Current Anchor

```text
task_requirement = active_task_required
TaskViewModel.current_anchor exists
-> dispatch normally
```

### Active Task Required Without Current Anchor

```text
task_requirement = active_task_required
TaskViewModel.current_anchor is empty
-> return E_ACTIVE_TASK_REQUIRED
-> do not invoke handler
-> leave runtime state unchanged
```

The gate should read active task state through the existing task management projection:

```text
env.domain.task_management.current_view(...).current_anchor
```

`current_view` already treats missing or non-active current tasks as no active anchor.

## Feedback

Use canonical env tool rejection shape. Do not invent a separate response format.

Expected rejection content:

```python
tool_results.rejection(
    tool=tool,
    action=f"{tool}.{action}",
    active_actor=active_actor,
    active_role=active_role,
    code="E_ACTIVE_TASK_REQUIRED",
    message="active task is required for this env tool action",
    permission_boundary="task.active_anchor",
    human_summary="Active task is required for this action.",
    why_blocked=(
        f"Action {tool}.{action} performs task-owned work, "
        "but TaskViewModel.current_anchor is empty."
    ),
    impact="No env action ran and runtime state was unchanged.",
    state_changed=False,
    durability="none",
    retryable=True,
    retry_guidance=(
        "Use task.current to inspect task state. If this is new work, use "
        "task.capture and then task.select. If a captured or blocked task already "
        "matches the work, use task.select. Retry the blocked action after an "
        "active task exists."
    ),
    allowed_next_actions=[
        "Use task.current to inspect TaskViewModel.current_anchor.",
        "Use task.capture to capture this work if it has no existing task.",
        "Use task.select to make a captured or blocked task active, then retry the blocked action.",
    ],
    alternative_capabilities=[
        tool_results.alternative_capability(
            tool="task",
            action="current",
            condition="Inspect current task state before choosing a task action.",
            mutates_product_state=False,
        ),
        tool_results.alternative_capability(
            tool="task",
            action="capture",
            condition="Capture this work when no existing task represents it.",
            mutates_product_state=False,
        ),
        tool_results.alternative_capability(
            tool="task",
            action="select",
            condition="Make a captured or blocked task active before retrying task-owned work.",
            mutates_product_state=False,
        ),
    ],
    extra={
        "category": "task_required",
        "gate_source": "env.tool task requirement",
        "gate_stage": "pre_dispatch",
        "executed": False,
        "task_requirement": "active_task_required",
    },
)
```

Required feedback properties:

- `ok` is `false`;
- `error.code` is `E_ACTIVE_TASK_REQUIRED`;
- `permission_boundary` is `task.active_anchor`;
- `why_blocked` names the blocked action and the missing `TaskViewModel.current_anchor`;
- `impact` says no env action ran and runtime state was unchanged;
- `state_changed` is `false`;
- `durability` is `none`;
- `retryable` is `true`;
- `allowed_next_actions` is non-empty and uses current task tool names.

## Initial Action Classification

This table is the expected classification for the currently registered env actions.

### `free`

| Tool | Actions |
| --- | --- |
| `artifact` | `list`, `get`, `list_attachments`, `get_attachment` |
| `comment` | `list` |
| `context` | `summarize`, `get`, `list_sources` |
| `message` | `contacts`, `send`, `get`, `mark`, `list`, `conversation` |
| `request` | `list`, `get` |
| `search` | `status` |
| `task` | `current`, `capture`, `select`, `switch_request`, `switch_confirm`, `progress`, `checkout`, `review` |
| `track` | `list`, `open` |

### `active_task_required`

| Tool | Actions |
| --- | --- |
| `artifact` | `create_revision`, `update_metadata`, `attach_file` |
| `comment` | `add`, `resolve` |
| `evidence` | `issue_browser`, `approve_downgrade` |
| `request` | `create`, `accept`, `block`, `complete`, `cancel` |
| `search` | `request`, `open_browser` |
| `track` | `create`, `update_now`, `add_material`, `add_update`, `add_proof`, `archive` |

> **Highlight: Search is task-owned.** `search.request` and `search.open_browser` may not mutate product objects, but they create research work context and evidence paths. They require active task ownership.

> **Highlight: Message remains free.** Message actions are communication mechanics. They are not the ownership boundary for substantial work.

> **Highlight: Task remains free.** Task actions must stay callable without active task, because they are how the actor creates, selects, switches, and closes the active anchor.

## Implementation Touch Points

### `scripts/env/tool_runtime/definition.py`

Add and validate the action-level contract:

```python
TASK_REQUIREMENT_FREE = "free"
TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED = "active_task_required"
```

`ActionDefinition` gets a required `task_requirement` field. `validate_definition(...)` rejects missing or invalid values.

### `scripts/env/tools/*/tool.py`

Each existing action definition declares `task_requirement`.

This is declaration only. No handler gets task-gate logic.

### `scripts/env/tool_runtime/registry.py`

After tool/action resolution, role auth, and args shape validation:

1. load the selected `ActionDefinition`;
2. if `task_requirement == free`, continue;
3. if `active_task_required`, read `current_view`;
4. if `current_anchor` exists, continue;
5. if missing, return the canonical rejection above;
6. only then invoke the tool handler.

The rejection helper can live next to the existing registry rejection helpers. No new module is needed for this task.

### Tool Catalog / Operation Semantics

Expose `task_requirement` in action semantic rows so actor-visible runtime discovery shows the same boundary that dispatch enforces.

## Test Plan

Add focused tests before implementation.

### Contract Coverage

Test file: `tests/test_env_tool_semantic_contract.py` or a new focused `tests/test_env_tool_active_task_gate.py`.

Assertions:

- every registered action has `task_requirement`;
- every value is `free` or `active_task_required`;
- `operation_semantics` exposes `task_requirement`;
- the action classification table above matches the currently registered actions.

### Gate Rejection

Use an active actor with no active task.

Dispatch one `active_task_required` action with valid args and patch `_invoke_tool` so the test fails if the handler is called.

Assertions:

- response `ok` is `false`;
- `error.code == "E_ACTIVE_TASK_REQUIRED"`;
- `permission_boundary == "task.active_anchor"`;
- `state_changed is False`;
- `durability == "none"`;
- `retryable is True`;
- `allowed_next_actions` includes `task.current`, `task.capture`, and `task.select`;
- patched handler was not called.

### Free Actions Still Work

Use an active actor with no active task.

Dispatch representative free actions:

- `task.current`;
- `context.summarize`;
- one message read action if the fixture can do so deterministically.

Assertions:

- actions are not rejected by `E_ACTIVE_TASK_REQUIRED`;
- task and context reads still return normal canonical responses.

### Active Task Allows Dispatch

Seed an active task in taskbox for the active actor.

Dispatch one `active_task_required` action and patch `_invoke_tool` to return a canonical success.

Assertions:

- handler is called exactly once;
- response is the handler response, not a gate rejection.

### Dispatch Ordering

Assertions:

- role authorization failure still returns `E_TOOL_ROLE_AUTH` before task gate;
- non-object `args` still returns `E_ENV_TOOL_PAYLOAD` before task gate;
- unsupported tool/action still returns existing `E_ENV_TOOL` rejection before task gate.

### State Unchanged Guarantee

Snapshot taskbox and relevant runtime object directories before a rejected gated action.

Assertions:

- snapshot is unchanged after `E_ACTIVE_TASK_REQUIRED`;
- response says `state_changed=false` and `durability=none`.

## Verification Commands

Focused verification:

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

If implementation touches task tool definitions or taskbox seeding helpers, also run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py -q
```

## Definition Of Done

The task is complete only when:

- all registered actions declare `task_requirement`;
- dispatch rejects `active_task_required` actions without active anchor before handler invocation;
- dispatch allows the same actions when an active anchor exists;
- `free` actions remain callable without active anchor;
- feedback follows canonical rejection contract;
- `operation_semantics` exposes the task requirement;
- focused and relevant contract tests pass.

