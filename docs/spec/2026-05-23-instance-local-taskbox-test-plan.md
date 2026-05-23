# Instance-Local Taskbox Test Plan

Date: 2026-05-23

## Test Goal

Prove task management is a private, instance-local taskbox capability for one active buddy instance, with priority, references, lifecycle history, and no fallback to shared `buddyswitch/objects/tasks`.

Tests must be requirement-driven. They should validate user-visible behavior and runtime boundaries, not shape themselves around a convenient implementation detail.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | Instance startup creates a private taskbox directory for the active buddy. |
| FR2 | Taskbox state is stored under the instance root, not under workspace projections or shared runtime objects. |
| FR3 | Task tool writes and reads only the active instance taskbox. |
| FR4 | Same buddy in two different instances has isolated task namespaces. |
| FR5 | Different buddies cannot read, list, update, or archive each other's taskbox tasks. |
| FR6 | Pre-existing shared `buddyswitch/objects/tasks/*.json` files are ignored by task tool and context tool. |
| FR7 | Task create supports required fields plus `priority`, `track_id`, and `refs`. |
| FR8 | Task update supports title, summary, status, priority, track_id, and refs changes. |
| FR9 | Status transitions maintain `closed_at` correctly. |
| FR10 | Archive is idempotent and does not duplicate history on repeated archive calls. |
| FR11 | Every real create, update, done, blocked, reopened, and archive lifecycle change appends to `history.md`. |
| FR12 | History can be read through the task tool with a bounded limit. |
| FR13 | Task list filters by status, priority, and track_id, excludes archived tasks by default, and can include archived tasks by request. |
| FR14 | Task list ordering is priority rank first, updated time second, and id as a stable tie-breaker. |
| FR15 | Invalid task ids, priorities, statuses, refs, and unsupported publication-style fields are rejected. |
| FR16 | Context summary and context get use instance-local taskbox tasks and expose useful task metadata. |
| FR17 | Tool definition and operation semantics describe private instance taskbox effects, not shared runtime object mutation. |
| FR18 | Env cleanup no longer discovers or deletes task objects as shared runtime state. |
| FR19 | Runtime task skill tells buddies to manage private instance tasks with priority and history. |
| FR20 | README, framework contracts, and env profile expectations no longer claim task state lives in `buddyswitch/objects/tasks`. |

## Coverage Matrix

| Requirement | Primary Verification |
| --- | --- |
| FR1 | `tests/test_buddyswitch_launcher.py` startup assertions. |
| FR2 | Launcher tests and repo consistency scans for old task object path. |
| FR3 | `tests/test_task_env_tool.py` create/list/get/update/archive assertions plus filesystem checks. |
| FR4 | `tests/test_task_env_tool.py` two-instance isolation test. |
| FR5 | `tests/test_task_env_tool.py` active-buddy isolation test. |
| FR6 | `tests/test_task_env_tool.py` and `tests/test_context_binding_env_tool.py` legacy object ignore tests. |
| FR7 | Task tool create tests. |
| FR8 | Task tool update tests. |
| FR9 | Status transition tests. |
| FR10 | Archive idempotency test. |
| FR11 | History append tests. |
| FR12 | Task history action test. |
| FR13 | List filter tests. |
| FR14 | List ordering test with deterministic timestamps. |
| FR15 | Validation tests in task tool tests. |
| FR16 | Context binding and host decision surface tests. |
| FR17 | Runtime tool definition and response contract tests. |
| FR18 | Cleanup system tests. |
| FR19 | Runtime skill architecture and runtime skill materialization tests. |
| FR20 | Repo consistency scans and profile tests. |

## Test Data Model

Use instance-shaped temporary roots in tests:

```text
<tmp-runtime-root>/
  instances/
    instance-a/
      instance.json
      taskbox/
        dev/
          tasks/
          history.md
    instance-b/
      instance.json
      taskbox/
        dev/
          tasks/
          history.md
  buddyswitch/
    objects/
      tasks/
        task-legacy.json
```

The legacy `buddyswitch/objects/tasks/task-legacy.json` file should be present in targeted tests and should not affect task tool output.

Use stable task ids:

- `task-dev-high`
- `task-dev-normal`
- `task-dev-low`
- `task-dev-archived`
- `task-legacy-shared`

Use stable buddy ids:

- `dev`
- `design`

Use stable track ids:

- `track-alpha`
- `track-beta`

## Test Changes

### 1. Launcher Taskbox Creation

Modify:

- `tests/test_buddyswitch_launcher.py`

Add a test that starts an instance and asserts:

```python
taskbox_root = instance_root / "taskbox" / "dev"
self.assertTrue((taskbox_root / "tasks").is_dir())
self.assertTrue((taskbox_root / "history.md").is_file())
self.assertFalse((workspace_dir / "taskbox").exists())
self.assertFalse((runtime_root / "buddyswitch" / "objects" / "tasks").exists())
```

Expected before implementation:

- fails because launcher does not create the new taskbox.

Expected after implementation:

- passes and proves taskbox creation is instance-local.

### 2. Task Tool Creates Instance-Local Task Files

Modify:

- `tests/test_task_env_tool.py`

Add a create test that calls the task tool with:

```json
{
  "action": "create",
  "task_id": "task-dev-high",
  "title": "Inspect design handoff",
  "summary": "Review artifact references and risks.",
  "priority": "high",
  "track_id": "track-alpha",
  "refs": [
    {"type": "track", "id": "track-alpha", "label": "Primary track"},
    {"type": "buddybox", "logical_name": "prototype/index.html", "label": "Prototype"}
  ]
}
```

Assert the response contains:

```python
self.assertEqual(payload["task"]["id"], "task-dev-high")
self.assertEqual(payload["task"]["owner_buddy"], "dev")
self.assertEqual(payload["task"]["priority"], "high")
self.assertEqual(payload["task"]["refs"][1]["logical_name"], "prototype/index.html")
self.assertIsNone(payload["task"]["closed_at"])
```

Assert the file exists only at:

```python
instance_root / "taskbox" / "dev" / "tasks" / "task-dev-high.json"
```

Assert this path does not exist:

```python
runtime_root / "buddyswitch" / "objects" / "tasks" / "task-dev-high.json"
```

Expected before implementation:

- fails because the repository still writes shared task objects and lacks `priority`, `refs`, and `closed_at`.

### 3. Task Tool Ignores Shared Legacy Task Objects

Modify:

- `tests/test_task_env_tool.py`

Seed:

```python
legacy_path = runtime_root / "buddyswitch" / "objects" / "tasks" / "task-legacy-shared.json"
legacy_path.parent.mkdir(parents=True, exist_ok=True)
legacy_path.write_text(json.dumps({
    "id": "task-legacy-shared",
    "buddy": "dev",
    "title": "Legacy shared task",
    "status": "active",
    "track_id": None,
    "summary": "This must not appear.",
    "created_at": "2026-05-23T00:00:00+08:00",
    "updated_at": "2026-05-23T00:00:00+08:00"
}), encoding="utf-8")
```

Call:

```json
{"action": "list", "include_archived": true}
```

Assert:

```python
self.assertNotIn("task-legacy-shared", {task["id"] for task in payload["tasks"]})
```

Call:

```json
{"action": "get", "task_id": "task-legacy-shared"}
```

Assert it returns the same not-found shape used for missing taskbox tasks.

### 4. Instance Isolation

Modify:

- `tests/test_task_env_tool.py`

Create `task-dev-high` in instance A and create another `task-dev-high` in instance B with a different title.

Assert:

```python
self.assertEqual(instance_a_payload["task"]["title"], "Instance A title")
self.assertEqual(instance_b_payload["task"]["title"], "Instance B title")
self.assertEqual(len(instance_a_list["tasks"]), 1)
self.assertEqual(len(instance_b_list["tasks"]), 1)
```

Assert the physical files are different:

```python
self.assertTrue((instance_a_root / "taskbox" / "dev" / "tasks" / "task-dev-high.json").is_file())
self.assertTrue((instance_b_root / "taskbox" / "dev" / "tasks" / "task-dev-high.json").is_file())
```

### 5. Active Buddy Isolation

Modify:

- `tests/test_task_env_tool.py`

Seed a design taskbox under the same instance root:

```text
taskbox/design/tasks/task-design-private.json
```

Run the task tool with active buddy `dev`.

Assert:

```python
self.assertNotIn("task-design-private", {task["id"] for task in payload["tasks"]})
```

Call update and archive on `task-design-private`.

Assert the tool returns not found or forbidden using the existing task tool error response style. The test should assert user-visible denial, not internal exception type.

### 6. Priority, Filters, And Sorting

Modify:

- `tests/test_task_env_tool.py`

Create tasks with deterministic `updated_at` values through repository fixtures or a clock override:

| Task | Priority | Status | Track | Updated |
| --- | --- | --- | --- | --- |
| `task-dev-low` | `low` | `active` | `track-alpha` | `2026-05-23T12:03:00+08:00` |
| `task-dev-high` | `high` | `active` | `track-beta` | `2026-05-23T12:01:00+08:00` |
| `task-dev-normal` | `normal` | `blocked` | `track-alpha` | `2026-05-23T12:02:00+08:00` |
| `task-dev-archived` | `high` | `archived` | `track-alpha` | `2026-05-23T12:04:00+08:00` |

Default list should return:

```python
["task-dev-high", "task-dev-normal", "task-dev-low"]
```

List with `{"priority": "high", "include_archived": true}` should return:

```python
["task-dev-archived", "task-dev-high"]
```

List with `{"track_id": "track-alpha"}` should return:

```python
["task-dev-normal", "task-dev-low"]
```

List with `{"status": "blocked"}` should return:

```python
["task-dev-normal"]
```

### 7. Status Transitions And Closed Time

Modify:

- `tests/test_task_env_tool.py`

Create an active task, then update status:

```json
{"action": "update", "task_id": "task-dev-high", "status": "done"}
```

Assert:

```python
self.assertEqual(payload["task"]["status"], "done")
self.assertIsNotNone(payload["task"]["closed_at"])
```

Reopen it:

```json
{"action": "update", "task_id": "task-dev-high", "status": "blocked"}
```

Assert:

```python
self.assertEqual(payload["task"]["status"], "blocked")
self.assertIsNone(payload["task"]["closed_at"])
```

Archive it:

```json
{"action": "archive", "task_id": "task-dev-high"}
```

Assert:

```python
self.assertEqual(payload["task"]["status"], "archived")
self.assertIsNotNone(payload["task"]["closed_at"])
```

Archive it again and assert the response reports no state change if that field exists, or at minimum the history line count does not increase.

### 8. History Events

Modify:

- `tests/test_task_env_tool.py`

After create, priority update, blocked update, done update, and archive, read:

```python
history_text = (instance_root / "taskbox" / "dev" / "history.md").read_text(encoding="utf-8")
```

Assert it contains exactly one line each for:

```text
task.create task-dev-high
task.update task-dev-high
task.block task-dev-high
task.close task-dev-high
task.archive task-dev-high
```

Call:

```json
{"action": "history", "limit": 3}
```

Assert:

```python
self.assertEqual(len(payload["entries"]), 3)
self.assertTrue(payload["entries"][-1]["line"].startswith("- 2026-"))
```

### 9. Validation Coverage

Modify:

- `tests/test_task_env_tool.py`

Add rejection tests for:

- `priority = "urgent"`
- `status = "waiting"`
- `refs = "track-alpha"`
- `refs = [{"type": "track"}]`
- `refs = [{"type": "buddybox", "id": "file"}]`
- `source_refs = []`
- `visibility = "public"`
- `task_id = "../escape"`

Each assertion should check the task tool returns a failure response and does not create a task file.

### 10. Context Uses Taskbox

Modify:

- `tests/test_context_binding_env_tool.py`
- `tests/test_host_decision_surface_product_mode.py`

Seed instance-local taskbox tasks and a legacy shared object task.

Call context summarize.

Assert:

```python
candidate_ids = {task["task_id"] for task in payload["candidate_tasks"]}
self.assertIn("task-dev-high", candidate_ids)
self.assertNotIn("task-legacy-shared", candidate_ids)
```

Assert task rows include:

```python
self.assertIn("priority", candidate_task)
self.assertIn("closed_at", candidate_task)
self.assertIn("ref_count", candidate_task)
```

### 11. Cleanup No Longer Manages Task Objects

Modify:

- `tests/test_cleanup_system.py`

Seed:

```text
buddyswitch/objects/tasks/task-legacy-shared.json
instances/instance-a/taskbox/dev/tasks/task-dev-high.json
```

Build cleanup plan for shared runtime state.

Assert:

```python
self.assertNotIn("task_objects", plan)
self.assertNotIn("task_object_ids", plan)
```

Run cleanup and assert it does not have task-specific shared object deletion reporting.

Instance root deletion tests should continue proving the entire instance root is removable by the launcher or existing cleanup path that owns instances.

### 12. Skills, Contracts, And Profiles

Modify:

- `tests/test_task_management_skill_architecture.py`
- `tests/test_runtime_skills.py`
- `tests/test_buddy_env_profiles.py`
- `tests/test_repo_consistency.py`

Assert `buddyswitch/skills/shared/task-tool/SKILL.md` includes:

- instance-local private taskbox
- priority
- history
- no shared task queue
- no direct taskbox file editing

Assert docs and contracts do not contain live claims that task state lives in:

```text
buddyswitch/objects/tasks
```

Allowed references to the old path should be limited to this spec and tests that explicitly prove legacy files are ignored.

Update profile expectations so `state_capability.task_effects` or its replacement describes the new tool effects:

```json
["create", "update", "priority", "status", "archive", "history"]
```

If the existing profile schema is intentionally narrower, replace the field name in the profile with a taskbox-specific capability and update its validator in `scripts/env_profiles.py`.

### 13. Tool Definition And Response Contracts

Modify:

- `tests/test_runtime_tool_feedback.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_runless_runtime_contract.py`
- `tests/test_runtime_broker.py`

Assert the task tool definition:

- includes `history`
- includes `priority` in create and update schemas
- includes `refs` in create and update schemas
- describes instance-local private taskbox mutation
- does not describe durable product state or shared runtime object mutation

Assert response envelopes for task create, list, update, archive, and history keep the existing env tool success/error contract.

## Verification Commands

Focused task tool tests:

```bash
python3 -m pytest tests/test_task_env_tool.py tests/test_task_management_skill_architecture.py -q
```

Launcher and context tests:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py -q
```

Runtime contract tests:

```bash
python3 -m pytest tests/test_runtime_broker.py tests/test_env_tool_response_contract.py tests/test_runless_runtime_contract.py tests/test_runtime_tool_feedback.py -q
```

Cleanup, profile, and repo consistency tests:

```bash
python3 -m pytest tests/test_cleanup_system.py tests/test_buddy_env_profiles.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Final stale-path scan:

```bash
rg -n "buddyswitch/objects/tasks|TASKS_DIR|task_objects|task_object_ids" README.md framework scripts tools buddyswitch tests
```

Expected final scan behavior:

- no live implementation claims task source of truth is `buddyswitch/objects/tasks`
- no active code writes task files through `TASKS_DIR`
- no cleanup category named `task_objects` remains
- tests may mention the old path only to prove it is ignored

Full relevant suite:

```bash
python3 -m pytest tests/test_task_env_tool.py tests/test_context_binding_env_tool.py tests/test_buddyswitch_launcher.py tests/test_cleanup_system.py tests/test_runtime_broker.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

## Acceptance Criteria

- All FR1 through FR20 requirements have a failing test before implementation or a scan gate that fails on the old behavior.
- All focused verification commands pass after implementation.
- Shared task objects are not read, written, mirrored, or cleaned as task state.
- Instance taskbox behavior is proven through filesystem assertions and tool responses.
- Docs, contracts, skills, and profiles match the new runtime boundary.
