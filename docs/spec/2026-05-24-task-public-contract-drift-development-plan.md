# Task Public Contract Drift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the shared env tool public contract with the current instance-local taskbox `task` implementation, keeping `task.history` as a first-class public action and removing stale five-action expectations.

**Architecture:** Keep `scripts/env/tools/task/tool.py` as the single source of truth for task public action definitions. Update the task tool definition so schema and semantic fields precisely describe the six-action instance-local taskbox contract, then update shared black-box/schema/semantic tests to assert that same contract. Do not add compatibility branches, action aliases, fallback reads, or old shared task behavior.

**Tech Stack:** Python env tool runtime definitions, Python task domain validation and repository helpers, pytest/unittest contract tests, Markdown specs.

---

## Scope

This plan repairs the public contract split exposed after the writable-surface
work:

- keep public actions: `create`, `list`, `get`, `update`, `archive`, `history`
- make `task.history` visible in all shared shipped-tool and semantic action
  expectations
- add missing bounded-limit schema fields for `task.list` and `task.history`
- refine task semantics so adjacent action boundaries are explicit
- keep existing instance-local taskbox behavior unchanged
- verify focused and full tests

Do not implement:

- old five-action compatibility
- `task.history` aliases
- old shared `buddyswitch/objects/tasks` fallback
- taskbox storage migration
- launcher or writable-surface changes
- broad test rewrites outside task public contract alignment

## Current Code Facts

- `scripts/env/tools/task/tool.py` defines six actions, including
  `ActionDefinition(name="history", title="task.history", ...)`.
- `scripts/env/tools/task/_impl.py` dispatches `"history"` to
  `history_for_active_buddy`.
- `scripts/env/domain/tasks.py` validates positive integer limits with
  `normalize_limit(value, default=100, maximum=200)` and
  `history_limit(args)` using default `50`.
- `scripts/env/repos/tasks.py` reads history from the instance-local active
  buddy taskbox `history.md`.
- `buddyswitch/skills/shared/task-tool/SKILL.md` already documents
  `task history`.
- `tests/test_task_env_tool.py` already validates lifecycle history behavior.
- `tests/test_task_management_skill_architecture.py` already expects
  `history` in the task tool catalog.
- Shared contract tests still encode stale expectations in:
  - `tests/test_black_box_tool_runtime.py`
  - `tests/test_env_tool_schema_contract.py`
  - `tests/test_env_tool_semantic_contract.py`

## Task 1: Confirm Baseline Failures And Passing Taskbox Behavior

**Files:**

- Read: `scripts/env/tools/task/tool.py`
- Read: `scripts/env/tools/task/_impl.py`
- Read: `scripts/env/domain/tasks.py`
- Read: `tests/test_black_box_tool_runtime.py`
- Read: `tests/test_env_tool_schema_contract.py`
- Read: `tests/test_env_tool_semantic_contract.py`
- Read: `tests/test_task_env_tool.py`
- Read: `tests/test_task_management_skill_architecture.py`

- [ ] **Step 1: Confirm worktree and dirty scope**

Run:

```bash
pwd
git status --short --branch
```

Expected:

```text
/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env
## clean-runtime-env...origin/clean-runtime-env
```

Any unrelated dirty files must remain untouched.

- [ ] **Step 2: Reproduce the current shared-contract failures**

Run:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_shipped_tools_expose_single_public_entrypoint tests/test_env_tool_schema_contract.py::EnvToolSchemaContractTests::test_high_risk_schema_shapes_match_domain_contracts tests/test_env_tool_semantic_contract.py -q
```

Expected before repair:

```text
10 failed
```

The failures must be limited to:

- missing `history` in expected task action sets
- missing `task.list.limit.minimum`
- stale task semantic snippets and object-model wording

- [ ] **Step 3: Confirm taskbox-specific tests already support the new direction**

Run:

```bash
python3 -m pytest tests/test_task_env_tool.py tests/test_task_management_skill_architecture.py -q
```

Expected before repair:

```text
passed
```

If these tests fail, stop and investigate before editing shared contracts.

## Task 2: Update Failing Shared Tests First

**Files:**

- Modify: `tests/test_black_box_tool_runtime.py`
- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_env_tool_semantic_contract.py`

- [ ] **Step 1: Update shipped task action expectation**

In `tests/test_black_box_tool_runtime.py`, change:

```python
"task": {"archive", "create", "get", "list", "update"},
```

to:

```python
"task": {"archive", "create", "get", "history", "list", "update"},
```

- [ ] **Step 2: Update semantic task action expectation**

In `tests/test_env_tool_semantic_contract.py`, change:

```python
"task": {"create", "list", "get", "update", "archive"},
```

to:

```python
"task": {"create", "list", "get", "update", "archive", "history"},
```

- [ ] **Step 3: Add schema assertions for task history limit**

In `tests/test_env_tool_schema_contract.py`, after:

```python
task_list = catalog.get_action_definition("task", "list").input_schema
```

add:

```python
task_history = catalog.get_action_definition("task", "history").input_schema
```

Then replace the task limit assertions with:

```python
self.assertEqual(task_create["properties"]["status"].get("enum"), ["active", "blocked", "done", "archived"])
self.assertEqual(task_list["properties"]["limit"].get("type"), "integer")
self.assertEqual(task_list["properties"]["limit"].get("minimum"), 1)
self.assertEqual(task_list["properties"]["limit"].get("default"), 100)
self.assertEqual(task_history["properties"]["limit"].get("type"), "integer")
self.assertEqual(task_history["properties"]["limit"].get("minimum"), 1)
self.assertEqual(task_history["properties"]["limit"].get("default"), 50)
```

- [ ] **Step 4: Add task.history semantic snippet coverage**

In `tests/test_env_tool_semantic_contract.py`, keep the existing task adjacent
action snippet rows and add:

```python
("task", "history", ("history", "lifecycle", "list")),
```

Do not delete the existing task rows for `list`, `get`, `update`, or
`archive`; the implementation will satisfy them.

- [ ] **Step 5: Add task.history machine semantics coverage**

In `tests/test_env_tool_semantic_contract.py`, add this test near the other
operation semantics tests:

```python
def test_task_history_operation_semantics_are_read_only(self) -> None:
    history = catalog.operation_semantics()["task.history"]
    self.assertEqual(history["kind"], "read")
    self.assertEqual(history["mutates"], "none")
    self.assertEqual(history["required_permission"], "task.read")
    self.assertEqual(history["authority"], "task.buddy_scope")
    self.assertEqual(history["visibility"], "active-buddy private")
    self.assertEqual(history["durability"], "none")
    self.assertEqual(history["result_content_level"], "history rows")
    self.assertIn("instance-local taskbox history", history["reads"])
    self.assertEqual(history["writes"], [])
    self.assertIn("task state", " ".join(history["does_not_write"]).lower())
    self.assertIs(history["risk_hints"]["read_only"], True)
    self.assertIs(history["risk_hints"]["destructive"], False)
    self.assertIs(history["risk_hints"]["idempotent"], True)
```

- [ ] **Step 6: Run the updated contract tests and verify they fail for implementation reasons**

Run:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_shipped_tools_expose_single_public_entrypoint tests/test_env_tool_schema_contract.py::EnvToolSchemaContractTests::test_high_risk_schema_shapes_match_domain_contracts tests/test_env_tool_semantic_contract.py -q
```

Expected after test edits and before implementation edits:

```text
failed
```

Acceptable remaining failures:

- `task.list.limit.minimum` missing
- `task.list.limit.default` missing
- `task.history.limit.minimum` missing
- `task.history.limit.default` missing
- task semantic text missing expected snippets
- task object model missing `context link`

If tests pass before implementation edits, inspect whether the code already
contains the contract and only the tests were stale.

## Task 3: Update Task Tool Definition Schema And Semantics

**Files:**

- Modify: `scripts/env/tools/task/tool.py`

- [ ] **Step 1: Add bounded schema fields for task.list.limit**

In the `task.list` `limit` property, replace:

```python
"limit": {
    "type": "integer",
    "description": "Optional maximum number of rows to return.",
},
```

with:

```python
"limit": {
    "type": "integer",
    "minimum": 1,
    "default": 100,
    "description": "Optional maximum number of summary rows to return.",
},
```

Do not change runtime validation in `scripts/env/domain/tasks.py` unless tests
prove schema and runtime still disagree after this edit.

- [ ] **Step 2: Add bounded schema fields for task.history.limit**

In the `task.history` `limit` property, replace:

```python
"limit": {
    "type": "integer",
    "description": "Optional maximum number of history entries to return.",
},
```

with:

```python
"limit": {
    "type": "integer",
    "minimum": 1,
    "default": 50,
    "description": "Optional maximum number of lifecycle history entries to return.",
},
```

- [ ] **Step 3: Clarify task object model with private context links**

Replace the `object_model` string with:

```python
object_model=(
    "Tasks live in the active instance taskbox under taskbox/<buddy>. "
    "They are private work items, not shared runtime objects. "
    "Task refs and track_id are private context links to tracks, artifacts, messages, comments, requests, or buddybox files; they do not publish or share those objects."
),
```

This preserves the new taskbox model while satisfying the high-risk boundary
test that requires explicit `context link` wording.

- [ ] **Step 4: Clarify task.list adjacent action semantics**

Replace `task.list` action semantics:

```python
use_when=("You need queue triage across private taskbox tasks.",),
do_not_use_when=("You need one specific task or you need to mutate task state.",),
```

with:

```python
use_when=("You need to list private taskbox summary rows for queue triage before choosing task.get.",),
do_not_use_when=("You need one specific task row; use task.get. You need to mutate task state; use task.update or task.archive.",),
```

- [ ] **Step 5: Clarify task.get adjacent action semantics**

Replace `task.get` action semantics:

```python
use_when=("You need one specific private task row by id.",),
do_not_use_when=("You need multi-row filtering or mutation.",),
```

with:

```python
use_when=("You need one specific private task row by task id after task.list or another response gave you the id.",),
do_not_use_when=("You need multi-row filtering; use task.list. You need mutation; use task.update or task.archive.",),
```

- [ ] **Step 6: Clarify task.update adjacent action semantics**

Replace `task.update` action semantics:

```python
use_when=("You need to patch task content, priority, refs, or lifecycle state.",),
do_not_use_when=("You need to create a new task or inspect history without mutation.",),
```

with:

```python
use_when=("You need to patch a task title, summary, priority, refs, track_id, or lifecycle status without archiving it.",),
do_not_use_when=("You need to create a new task, archive a task, or inspect history without mutation.",),
```

- [ ] **Step 7: Clarify task.archive adjacent action semantics**

Replace `task.archive` action semantics:

```python
use_when=("You need to remove a task from default taskbox views while preserving history.",),
do_not_use_when=("You only need a non-archival status change; use task.update.",),
```

with:

```python
use_when=("You need to archive a task so it leaves default active taskbox views while preserving lifecycle history.",),
do_not_use_when=("You need to keep the task active or only need a non-archival status change; use task.update.",),
```

- [ ] **Step 8: Clarify task.history adjacent action semantics**

Replace `task.history` action semantics:

```python
use_when=("You need recent lifecycle history for the active instance taskbox.",),
do_not_use_when=("You need current task rows rather than lifecycle history.",),
```

with:

```python
use_when=("You need recent lifecycle history lines for the active instance taskbox after create, update, close, reopen, or archive events.",),
do_not_use_when=("You need current task summary rows; use task.list. You need one task row; use task.get.",),
```

- [ ] **Step 9: Do not edit runtime handlers unless a test proves a real mismatch**

Do not change:

- `scripts/env/tools/task/_impl.py`
- `scripts/env/domain/tasks.py`
- `scripts/env/repos/tasks.py`

The current issue is public contract drift. Runtime behavior already validates
positive limits and reads instance-local history.

## Task 4: Run Focused Contract And Runtime Tests

**Files:**

- Verify only.

- [ ] **Step 1: Run focused shared contract tests**

Run:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_shipped_tools_expose_single_public_entrypoint tests/test_env_tool_schema_contract.py::EnvToolSchemaContractTests::test_high_risk_schema_shapes_match_domain_contracts tests/test_env_tool_semantic_contract.py -q
```

Expected:

```text
passed
```

- [ ] **Step 2: Run task behavior tests**

Run:

```bash
python3 -m pytest tests/test_task_env_tool.py tests/test_task_management_skill_architecture.py -q
```

Expected:

```text
passed
```

- [ ] **Step 3: Run broader env tool contract tests**

Run:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_env_tool_payload_contract.py tests/test_runtime_broker.py tests/test_runless_runtime_contract.py tests/test_runtime_tool_feedback.py -q
```

Expected:

```text
passed
```

If a failure points to a real schema/runtime mismatch, return to Task 3 and fix
the source definition or domain validation. Do not weaken tests to pass.

## Task 5: Final Full-Suite Verification

**Files:**

- Verify only.

- [ ] **Step 1: Run full tests**

Run:

```bash
python3 -m pytest tests -q
```

Expected:

```text
passed
```

Explicit pytest skips are acceptable only if they are environment skips.

- [ ] **Step 2: Inspect git diff scope**

Run:

```bash
git diff -- tests/test_black_box_tool_runtime.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py scripts/env/tools/task/tool.py
git status --short
```

Expected task-related modified files:

```text
scripts/env/tools/task/tool.py
tests/test_black_box_tool_runtime.py
tests/test_env_tool_schema_contract.py
tests/test_env_tool_semantic_contract.py
```

The plan documents may also be modified or untracked if they have not already
been committed. Existing unrelated dirty files must remain untouched.

## Final Review Checklist

Before reporting completion, verify:

- `task.history` is present in `SHIPPED_TOOLS["task"]`.
- `task.history` is present in `_EXPECTED_ACTIONS_BY_TOOL["task"]`.
- `task.history` has semantic contract coverage.
- `task.list.limit` schema has `minimum=1` and `default=100`.
- `task.history.limit` schema has `minimum=1` and `default=50`.
- `task` object model includes private work item and context link wording.
- `task.list/get/update/archive/history` semantics distinguish adjacent actions.
- No old five-action task contract remains in tests.
- No runtime fallback to old shared task objects was added.
- No unrelated dirty file was edited.
- Focused tests pass.
- `python3 -m pytest tests -q` passes.

## Plan Review

This plan is intentionally narrow:

- It treats `task.history` as the intended public surface, matching current
  implementation, task-specific tests, and task skill docs.
- It fixes stale shared contracts instead of reverting the taskbox migration.
- It changes `scripts/env/tools/task/tool.py`, the source of public registry
  projection, rather than adding separate compatibility logic.
- It does not change task storage, cleanup, launcher, buddybox, artifact,
  context, or writable-surface behavior.
- It has a direct failing-test to green-test loop and a full-suite closeout.

If implementation reveals a deeper mismatch, stop and report the exact failing
contract before changing the task semantics or runtime behavior beyond this
plan.
