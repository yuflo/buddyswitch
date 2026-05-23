# Instance-Local Taskbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace shared task runtime objects with a private instance-local taskbox for the active buddy, including priority, references, lifecycle history, and context integration.

**Architecture:** Keep the existing task tool and repository entry points, but replace their storage boundary from `buddyswitch/objects/tasks` to `BUDDYSWITCH_INSTANCE_ROOT/taskbox/<buddy>`. The launcher creates taskbox directories, repository functions own JSON and `history.md`, task tools expose bounded operations, and context reads from the same taskbox. No compatibility fallback reads old shared task objects.

**Tech Stack:** Python env tools and repositories, Bash launcher setup, TOML/JSON env profiles, Markdown runtime skills, pytest/unittest, static repo scans with `rg`.

---

## Scope

Build the full task upgrade:

- launcher-created taskbox directories
- instance-local task JSON files
- one `history.md` per buddy instance taskbox
- priority support
- structured private references
- status lifecycle and `closed_at`
- list filters and sorting
- task history tool action
- context tool taskbox integration
- cleanup removal for shared task objects
- docs, contracts, profiles, and skill updates
- tests proving no fallback to `buddyswitch/objects/tasks`

Do not build:

- cross-buddy task sharing
- cross-instance task sharing
- buddybox read or write changes
- message upgrade work
- task UI
- old task object migration
- old task object fallback

## File Map

Create or modify these files.

Launcher:

- Modify: `buddyswitch-codex`
  - call taskbox creation during instance startup.
- Modify: `tools/launcher/env.sh`
  - add taskbox creation helper.
- Modify: `tools/launcher/workspace.sh`
  - keep workspace free of taskbox projections.
- Modify: `tools/launcher/codex_config.py`
  - keep taskbox out of native writable source paths unless tests prove no change is needed.

Repository and domain:

- Modify: `scripts/env/repos/runtime_files.py`
  - add instance taskbox path helpers.
  - remove active use of `TASKS_DIR`.
- Modify: `scripts/env/repos/tasks.py`
  - replace shared object implementation with taskbox implementation.
- Modify: `scripts/env/domain/tasks.py`
  - validate new schema, filters, updates, priority, refs, and history arguments.
- Modify: `scripts/env/tool_runtime/context.py`
  - pass instance identity to task repo access.

Tool implementation:

- Modify: `scripts/env/tools/task/tool.py`
  - update schemas and semantics.
- Modify: `scripts/env/tools/task/_impl.py`
  - pass active buddy and instance identity into task repo operations.
  - add history action.
- Modify: `scripts/env/tools/context/_impl.py`
  - read tasks from taskbox and include priority metadata.

Cleanup:

- Modify: `scripts/env_cleanup.py`
  - remove shared task object cleanup category.

Profiles, docs, and skills:

- Modify: `buddyswitch/env-profiles/*.json`
- Modify: `scripts/env_profiles.py`
- Modify: `buddyswitch/skills/shared/task-tool/SKILL.md`
- Modify: `framework/contracts/*.md`
- Modify: `README.md`

Tests:

- Modify: `tests/test_task_env_tool.py`
- Modify: `tests/test_task_management_skill_architecture.py`
- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_host_decision_surface_product_mode.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_cleanup_system.py`
- Modify: `tests/test_runtime_broker.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tests/test_runless_runtime_contract.py`
- Modify: `tests/test_runtime_tool_feedback.py`
- Modify: `tests/test_buddy_env_profiles.py`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/runtime_root_test_helper.py` if current helpers cannot express instance roots cleanly.

## Shared Contract

Use these constants and values consistently.

Task status values:

```python
VALID_TASK_STATUS = ("active", "blocked", "done", "archived")
```

Task priority values:

```python
VALID_TASK_PRIORITY = ("high", "normal", "low")
PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}
```

Allowed reference types:

```python
ID_REF_TYPES = {"track", "artifact", "message", "comment", "request"}
BUDDYBOX_REF_TYPE = "buddybox"
```

Taskbox layout:

```text
<instance-root>/taskbox/<active-buddy>/tasks/<task-id>.json
<instance-root>/taskbox/<active-buddy>/history.md
```

Task record:

```python
{
    "id": task_id,
    "owner_buddy": active_buddy,
    "title": title,
    "summary": summary,
    "status": status,
    "priority": priority,
    "track_id": track_id,
    "refs": refs,
    "created_at": now,
    "updated_at": now,
    "closed_at": None,
}
```

## Implementation Tasks

### Task 1: Add Launcher Taskbox Tests

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add startup assertion for taskbox creation**

Add a test near the instance startup tests:

```python
def test_instance_start_creates_private_taskbox_for_active_buddy(self) -> None:
    result = self._run_launcher(
        "instance",
        "start",
        "--buddy",
        "dev",
        "--print-env",
        extra_env=self._service_env(),
    )
    self.assertEqual(result.returncode, 0, msg=result.stderr)
    env = self._parse_printed_env(result.stdout)
    instance_root = Path(env["BUDDYSWITCH_INSTANCE_ROOT"])
    workspace_dir = Path(env["BUDDYSWITCH_WORKSPACE_DIR"])
    runtime_root = Path(env["BUDDYSWITCH_RUNTIME_ROOT"])

    taskbox_root = instance_root / "taskbox" / "dev"
    self.assertTrue((taskbox_root / "tasks").is_dir())
    self.assertTrue((taskbox_root / "history.md").is_file())
    self.assertEqual((taskbox_root / "history.md").read_text(encoding="utf-8"), "")

    self.assertFalse((workspace_dir / "taskbox").exists())
    self.assertFalse((runtime_root / "buddyswitch" / "objects" / "tasks").exists())
```

If the local test helper uses a different launcher helper name, keep the exact assertions and wire them into the existing helper used by adjacent `instance start` tests.

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_creates_private_taskbox_for_active_buddy -q
```

Expected before implementation:

```text
FAILED ... AssertionError: False is not true
```

The failing assertion should be the missing `taskbox/dev/tasks` directory or missing `history.md`.

### Task 2: Implement Launcher Taskbox Creation

**Files:**

- Modify: `tools/launcher/env.sh`
- Modify: `buddyswitch-codex`

- [ ] **Step 1: Add a taskbox helper in `tools/launcher/env.sh`**

Add this function after `buddyswitch_env_bind_instance` and before `buddyswitch_instance_activate`:

```bash
buddyswitch_instance_ensure_taskbox() {
  local buddy="${1:-}"
  if [[ -z "${buddy}" ]]; then
    echo "buddyswitch: buddy is required to create taskbox" >&2
    return 2
  fi
  if [[ -z "${BUDDYSWITCH_INSTANCE_ROOT:-}" ]]; then
    echo "buddyswitch: BUDDYSWITCH_INSTANCE_ROOT is not set" >&2
    return 2
  fi

  local taskbox_root="${BUDDYSWITCH_INSTANCE_ROOT}/taskbox/${buddy}"
  mkdir -p "${taskbox_root}/tasks"
  if [[ ! -e "${taskbox_root}/history.md" ]]; then
    : > "${taskbox_root}/history.md"
  fi
}
```

- [ ] **Step 2: Call the helper during instance startup**

In `buddyswitch-codex`, after the launcher binds `BUDDYSWITCH_INSTANCE_ROOT` and before the instance is activated for use, call:

```bash
buddyswitch_instance_ensure_taskbox "${buddy}"
```

Place it in the same startup path used by `./buddyswitch-codex instance start --buddy <buddy>`.

- [ ] **Step 3: Run launcher test**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_creates_private_taskbox_for_active_buddy -q
```

Expected after implementation:

```text
1 passed
```

### Task 3: Add Taskbox Repository Path Helpers

**Files:**

- Modify: `scripts/env/repos/runtime_files.py`
- Modify: `tests/test_task_env_tool.py`

- [ ] **Step 1: Add failing path-helper coverage through task tool tests**

In `tests/test_task_env_tool.py`, add helper setup that creates an instance root and instance payload:

```python
def _make_instance_context(self, instance_id: str = "instance-a", buddy: str = "dev") -> dict[str, object]:
    instance_root = self.runtime_root / "instances" / instance_id
    instance_root.mkdir(parents=True, exist_ok=True)
    instance_payload = {
        "instance_id": instance_id,
        "buddy": buddy,
        "instance_root": str(instance_root),
    }
    instance_json = instance_root / "instance.json"
    instance_json.write_text(json.dumps(instance_payload), encoding="utf-8")
    return {
        "instance_root": instance_root,
        "instance_json": instance_json,
        "instance_payload": instance_payload,
    }
```

Use the same field names already used by env tool runtime context if adjacent tests have a helper. The contract is that task operations receive active buddy, `instance_json`, and `instance_payload`.

- [ ] **Step 2: Add runtime path expectations in the create test**

Assert task files must be created at:

```python
task_file = instance_root / "taskbox" / "dev" / "tasks" / "task-dev-high.json"
self.assertTrue(task_file.is_file())
self.assertFalse((self.runtime_root / "buddyswitch" / "objects" / "tasks" / "task-dev-high.json").exists())
```

- [ ] **Step 3: Implement helpers in `runtime_files.py`**

Add:

```python
def instance_root_from_context(
    *,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> Path:
    payload_root = None
    if instance_payload:
        raw_root = instance_payload.get("instance_root")
        if isinstance(raw_root, str) and raw_root:
            payload_root = Path(raw_root)
    if payload_root is not None:
        return payload_root
    if instance_json is not None:
        return Path(instance_json).resolve().parent
    raise ValueError("instance context is required for taskbox access")


def taskbox_root(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> Path:
    require_id(active_buddy, label="buddy")
    root = instance_root_from_context(
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    return root / "taskbox" / active_buddy


def taskbox_tasks_dir(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> Path:
    return taskbox_root(
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    ) / "tasks"


def taskbox_history_file(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> Path:
    return taskbox_root(
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    ) / "history.md"
```

Import `Mapping` from `typing`.

- [ ] **Step 4: Run task tests and observe expected failures**

Run:

```bash
python3 -m pytest tests/test_task_env_tool.py -q
```

Expected:

- new tests still fail because repository and tool code still use shared task objects.

### Task 4: Replace Task Repository Storage

**Files:**

- Modify: `scripts/env/repos/tasks.py`
- Modify: `scripts/env/repos/runtime_files.py`
- Modify: `tests/test_task_env_tool.py`

- [ ] **Step 1: Replace repository function signatures**

In `scripts/env/repos/tasks.py`, use explicit taskbox context on public repository functions:

```python
def list_tasks(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    include_archived: bool = False,
) -> list[dict[str, object]]:
    ...


def get_task(
    task_id: str,
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> dict[str, object] | None:
    ...


def save_task(
    task: Mapping[str, object],
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> dict[str, object]:
    ...
```

Use `owner_buddy` in saved records. Do not accept or persist the old `buddy` field for new records.

- [ ] **Step 2: Implement path resolution**

Use:

```python
tasks_dir = runtime_files.taskbox_tasks_dir(
    active_buddy=active_buddy,
    instance_json=instance_json,
    instance_payload=instance_payload,
)
tasks_dir.mkdir(parents=True, exist_ok=True)
task_file = tasks_dir / f"{task_id}.json"
```

Validate `task_id` with the existing `runtime_files.require_id` helper before building the path.

- [ ] **Step 3: Implement atomic JSON writes using the existing project pattern**

If `scripts/env/repos/tasks.py` already has an atomic write helper, keep it and change only the destination directory.

The write path must:

```python
tmp_file = task_file.with_suffix(task_file.suffix + ".tmp")
tmp_file.write_text(json.dumps(task, indent=2, sort_keys=True) + "\n", encoding="utf-8")
tmp_file.replace(task_file)
```

- [ ] **Step 4: Implement list ordering**

Use:

```python
PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}


def _sort_key(task: Mapping[str, object]) -> tuple[int, str, str]:
    priority = str(task.get("priority") or "normal")
    updated_at = str(task.get("updated_at") or "")
    task_id = str(task.get("id") or "")
    return (PRIORITY_RANK.get(priority, 1), _reverse_timestamp(updated_at), task_id)
```

If the codebase does not have `_reverse_timestamp`, sort with:

```python
tasks.sort(key=lambda task: (PRIORITY_RANK.get(str(task.get("priority") or "normal"), 1), str(task.get("id") or "")))
tasks.sort(key=lambda task: str(task.get("updated_at") or ""), reverse=True)
tasks.sort(key=lambda task: PRIORITY_RANK.get(str(task.get("priority") or "normal"), 1))
```

This preserves priority as the primary ordering key and updated time descending inside each priority group.

- [ ] **Step 5: Run focused repository behavior through tool tests**

Run:

```bash
python3 -m pytest tests/test_task_env_tool.py -q
```

Expected:

- storage-path tests move forward
- schema and tool action tests still fail until domain and tool implementation are updated

### Task 5: Expand Task Domain Validation

**Files:**

- Modify: `scripts/env/domain/tasks.py`
- Modify: `tests/test_task_env_tool.py`

- [ ] **Step 1: Add validation constants**

Add:

```python
VALID_TASK_PRIORITY = ("high", "normal", "low")
ALLOWED_TASK_REF_ID_TYPES = {"track", "artifact", "message", "comment", "request"}
ALLOWED_TASK_REF_TYPES = ALLOWED_TASK_REF_ID_TYPES | {"buddybox"}
```

- [ ] **Step 2: Validate priority**

Add a helper:

```python
def normalize_priority(value: object | None) -> str:
    if value is None:
        return "normal"
    if not isinstance(value, str) or value not in VALID_TASK_PRIORITY:
        raise ValueError("priority must be one of: high, normal, low")
    return value
```

- [ ] **Step 3: Validate refs**

Add:

```python
def normalize_refs(value: object | None) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("refs must be a list")
    refs: list[dict[str, object]] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError("each ref must be an object")
        ref_type = raw.get("type")
        if ref_type not in ALLOWED_TASK_REF_TYPES:
            raise ValueError("ref type is not supported")
        normalized: dict[str, object] = {"type": ref_type}
        label = raw.get("label")
        if label is not None:
            if not isinstance(label, str):
                raise ValueError("ref label must be a string")
            normalized["label"] = label
        if ref_type == "buddybox":
            logical_name = raw.get("logical_name")
            if not isinstance(logical_name, str) or not logical_name.strip():
                raise ValueError("buddybox refs require logical_name")
            normalized["logical_name"] = logical_name
        else:
            ref_id = raw.get("id")
            if not isinstance(ref_id, str) or not ref_id.strip():
                raise ValueError("refs require id")
            normalized["id"] = ref_id
        refs.append(normalized)
    return refs
```

- [ ] **Step 4: Expand create and update schemas**

Create should accept:

```python
CREATE_ALLOWED_FIELDS = {
    "task_id",
    "title",
    "summary",
    "status",
    "priority",
    "track_id",
    "refs",
}
```

Update should accept:

```python
UPDATE_ALLOWED_FIELDS = {
    "title",
    "summary",
    "status",
    "priority",
    "track_id",
    "refs",
}
```

Reject:

```python
PUBLICATION_FIELDS = {
    "source_refs",
    "visibility",
    "publish",
    "target_buddy",
}
```

- [ ] **Step 5: Run validation tests**

Run:

```bash
python3 -m pytest tests/test_task_env_tool.py -q
```

Expected:

- invalid priority, status, refs, publication fields, and path traversal task ids fail with tool errors
- valid priority and refs still wait on tool implementation if not connected

### Task 6: Implement Task Lifecycle And History

**Files:**

- Modify: `scripts/env/repos/tasks.py`
- Modify: `scripts/env/tools/task/_impl.py`
- Modify: `tests/test_task_env_tool.py`

- [ ] **Step 1: Add history append helper**

In `scripts/env/repos/tasks.py`, add:

```python
def append_history(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    event: str,
    task_id: str,
    fields: Mapping[str, object],
) -> None:
    history_file = runtime_files.taskbox_history_file(
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    history_file.parent.mkdir(parents=True, exist_ok=True)
    parts = [f"{key}={json.dumps(value, ensure_ascii=True)}" for key, value in sorted(fields.items())]
    line = f"- {now_iso()} {event} {task_id}"
    if parts:
        line = f"{line} {' '.join(parts)}"
    with history_file.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
```

Use the repository's existing timestamp helper instead of `now_iso()` if one already exists.

- [ ] **Step 2: Add history reader**

Add:

```python
def read_history(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    limit: int = 50,
) -> list[dict[str, object]]:
    history_file = runtime_files.taskbox_history_file(
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    if not history_file.exists():
        return []
    lines = history_file.read_text(encoding="utf-8").splitlines()
    tail = lines[-limit:]
    return [{"line": line} for line in tail]
```

Clamp `limit` in domain validation so callers cannot request unbounded history.

- [ ] **Step 3: Implement `closed_at` lifecycle**

When creating a task:

```python
closed_at = now if status in {"done", "archived"} else None
```

When updating status:

```python
if new_status in {"done", "archived"} and old_status not in {"done", "archived"}:
    task["closed_at"] = now
elif new_status in {"active", "blocked"}:
    task["closed_at"] = None
```

When archiving:

```python
if task["status"] == "archived":
    return task, False
task["status"] = "archived"
task["closed_at"] = task.get("closed_at") or now
```

- [ ] **Step 4: Emit one history event per real change**

Use event names:

```text
task.create
task.update
task.block
task.close
task.reopen
task.archive
```

Map status changes:

- status becomes `blocked`: `task.block`
- status becomes `done`: `task.close`
- status becomes `active` from `done` or `archived`: `task.reopen`
- archive action: `task.archive`
- other field-only update: `task.update`

- [ ] **Step 5: Run lifecycle and history tests**

Run:

```bash
python3 -m pytest tests/test_task_env_tool.py -q
```

Expected:

- create/update/archive/history tests pass or fail only on tool schema wiring that Task 7 handles

### Task 7: Update Task Tool Definition And Implementation

**Files:**

- Modify: `scripts/env/tools/task/tool.py`
- Modify: `scripts/env/tools/task/_impl.py`
- Modify: `tests/test_runtime_tool_feedback.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tests/test_runless_runtime_contract.py`
- Modify: `tests/test_runtime_broker.py`

- [ ] **Step 1: Update action schema**

In `tool.py`, add:

```python
"history": {
    "description": "Read recent private taskbox history for the active buddy instance.",
    "input": {
        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
    },
}
```

Add `priority` and `refs` to create and update schemas. Add list filters:

```python
"status": {"enum": ["active", "blocked", "done", "archived"]},
"priority": {"enum": ["high", "normal", "low"]},
"track_id": {"type": "string"},
"include_archived": {"type": "boolean"},
"limit": {"type": "integer", "minimum": 1, "maximum": 100},
```

- [ ] **Step 2: Update operation semantics**

Change task tool metadata so it describes:

```text
mutates active buddy instance taskbox
does not publish shared product state
does not write shared runtime objects
```

Inspect `scripts/env/tool_runtime/definition.py` before choosing the exact `mutates` value. If the model accepts free strings, use `instance_taskbox`. If it validates an enum, add the smallest enum value needed and update its tests.

- [ ] **Step 3: Pass instance context to repository calls**

In `_impl.py`, gather:

```python
active_buddy = context.active_buddy
instance_json = context.instance_json
instance_payload = context.instance_payload
```

Pass those values into every task repository call.

- [ ] **Step 4: Implement actions**

Create:

```python
task = task_repo.create_task(
    task_id=task_id,
    title=title,
    summary=summary,
    status=status,
    priority=priority,
    track_id=track_id,
    refs=refs,
    active_buddy=active_buddy,
    instance_json=instance_json,
    instance_payload=instance_payload,
)
```

List:

```python
tasks = task_repo.list_tasks(
    active_buddy=active_buddy,
    instance_json=instance_json,
    instance_payload=instance_payload,
    include_archived=include_archived,
)
tasks = domain_tasks.filter_tasks(tasks, status=status, priority=priority, track_id=track_id, limit=limit)
```

History:

```python
entries = task_repo.read_history(
    active_buddy=active_buddy,
    instance_json=instance_json,
    instance_payload=instance_payload,
    limit=limit,
)
```

- [ ] **Step 5: Remove old shared-object ownership checks**

Delete logic that trusts `task["buddy"]` from shared objects.

Replace it with physical taskbox scoping:

```python
task = task_repo.get_task(
    task_id,
    active_buddy=active_buddy,
    instance_json=instance_json,
    instance_payload=instance_payload,
)
if task is None:
    return not_found_response(...)
```

- [ ] **Step 6: Run tool contract tests**

Run:

```bash
python3 -m pytest tests/test_task_env_tool.py tests/test_runtime_tool_feedback.py tests/test_env_tool_response_contract.py tests/test_runless_runtime_contract.py tests/test_runtime_broker.py -q
```

Expected:

```text
passed
```

or failures that name stale shared task object expectations to remove in Task 8 and Task 10.

### Task 8: Update Runtime Context To Read Taskbox

**Files:**

- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_host_decision_surface_product_mode.py`

- [ ] **Step 1: Add context tests first**

Seed an instance task:

```python
self._write_taskbox_task(
    instance_root=instance_root,
    buddy="dev",
    task={
        "id": "task-dev-high",
        "owner_buddy": "dev",
        "title": "Inspect taskbox context",
        "summary": "Visible from context.",
        "status": "active",
        "priority": "high",
        "track_id": "track-alpha",
        "refs": [{"type": "track", "id": "track-alpha"}],
        "created_at": "2026-05-23T12:00:00+08:00",
        "updated_at": "2026-05-23T12:00:00+08:00",
        "closed_at": None,
    },
)
```

Seed a legacy task object under `buddyswitch/objects/tasks/task-legacy-shared.json`.

Assert context contains `task-dev-high` and not `task-legacy-shared`.

- [ ] **Step 2: Update candidate task row**

Change `_candidate_task_row` to return:

```python
{
    "task_id": task.get("id"),
    "title": task.get("title"),
    "summary": task.get("summary"),
    "status": task.get("status"),
    "priority": task.get("priority"),
    "track_id": task.get("track_id"),
    "updated_at": task.get("updated_at"),
    "closed_at": task.get("closed_at"),
    "ref_count": len(task.get("refs") or []),
}
```

- [ ] **Step 3: Pass instance context into task listing**

Replace:

```python
context.repos.task.list_tasks()
```

with:

```python
context.repos.task.list_tasks(
    active_buddy=context.active_buddy,
    instance_json=context.instance_json,
    instance_payload=context.instance_payload,
    include_archived=False,
)
```

Use the actual context accessors available in `scripts/env/tools/context/_impl.py`.

- [ ] **Step 4: Run context tests**

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py -q
```

Expected:

```text
passed
```

### Task 9: Remove Shared Task Cleanup

**Files:**

- Modify: `scripts/env_cleanup.py`
- Modify: `tests/test_cleanup_system.py`

- [ ] **Step 1: Add cleanup test**

In `tests/test_cleanup_system.py`, add:

```python
def test_cleanup_plan_does_not_manage_task_objects_as_shared_runtime_state(self) -> None:
    task_object = self.runtime_root / "buddyswitch" / "objects" / "tasks" / "task-legacy-shared.json"
    task_object.parent.mkdir(parents=True, exist_ok=True)
    task_object.write_text("{}", encoding="utf-8")

    taskbox_task = self.runtime_root / "instances" / "instance-a" / "taskbox" / "dev" / "tasks" / "task-dev-high.json"
    taskbox_task.parent.mkdir(parents=True, exist_ok=True)
    taskbox_task.write_text("{}", encoding="utf-8")

    plan = env_cleanup.build_cleanup_plan(
        scope="all-data",
        buddy=None,
        repo_root=self.runtime_root,
        manifest_path=self.manifest_path,
    )

    self.assertNotIn("task_objects", plan)
    self.assertNotIn("task_object_ids", plan)
```

Adapt `self.manifest_path` to the helper name already present in the file.

- [ ] **Step 2: Remove task object discovery**

In `scripts/env_cleanup.py`, delete or stop using:

```python
TASK_OBJECTS_RELATIVE_DIR
discover_task_objects
```

Remove task object fields from cleanup plan construction and cleanup execution output.

- [ ] **Step 3: Run cleanup tests**

Run:

```bash
python3 -m pytest tests/test_cleanup_system.py -q
```

Expected:

```text
passed
```

### Task 10: Update Profiles, Skills, Docs, And Contracts

**Files:**

- Modify: `buddyswitch/env-profiles/*.json`
- Modify: `scripts/env_profiles.py`
- Modify: `buddyswitch/skills/shared/task-tool/SKILL.md`
- Modify: `framework/contracts/pm.md`
- Modify: `framework/contracts/market.md`
- Modify: `framework/contracts/design.md`
- Modify: `framework/contracts/dev.md`
- Modify: `framework/contracts/test.md`
- Modify: `README.md`
- Modify: `tests/test_buddy_env_profiles.py`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_task_management_skill_architecture.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Update profile contract**

Replace old narrow task effects:

```json
"task_effects": ["status", "summary"]
```

with:

```json
"task_effects": ["create", "update", "priority", "status", "archive", "history"]
```

Update `scripts/env_profiles.py` validation to expect that exact list.

- [ ] **Step 2: Update task skill**

In `buddyswitch/skills/shared/task-tool/SKILL.md`, describe:

```markdown
# Task Tool

Use the `task` env tool to manage your private taskbox for the current buddy instance.

Tasks are private instance-local work items. They are not shared across buddies, not shared across instances, and not durable product state.

Use tasks to:

- create concrete work items
- inspect active and blocked work
- set `priority` to `high`, `normal`, or `low`
- attach private refs to tracks, artifacts, messages, comments, requests, or buddybox logical names
- mark work `done`
- archive closed work
- read recent task history

Do not edit taskbox files directly. Use the task tool so JSON records and `history.md` stay consistent.
```

- [ ] **Step 3: Update framework contracts**

Replace references to:

```text
buddyswitch/objects/tasks/<task-id>.json
```

with:

```text
current instance taskbox task records, managed only through the task env tool
```

Keep the contracts clear that tasks are private buddy-instance work management, not cross-buddy exchange.

- [ ] **Step 4: Update README**

Replace the task runtime storage bullet with:

```markdown
- Active buddy instance taskboxes live under the launcher instance root and are managed through the `task` env tool.
```

Do not document a direct file-edit workflow for taskbox files.

- [ ] **Step 5: Add repo consistency stale-path gate**

In `tests/test_repo_consistency.py`, add:

```python
def test_task_runtime_contract_does_not_point_to_shared_task_objects(self) -> None:
    allowed = {
        "docs/spec/2026-05-23-instance-local-taskbox-objective.md",
        "docs/spec/2026-05-23-instance-local-taskbox-test-plan.md",
        "docs/spec/2026-05-23-instance-local-taskbox-development-plan.md",
    }
    completed = subprocess.run(
        ["rg", "-n", "buddyswitch/objects/tasks", "README.md", "framework", "scripts", "tools", "buddyswitch", "tests"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
    violations = []
    for line in completed.stdout.splitlines():
        path = line.split(":", 1)[0]
        if path not in allowed and "legacy" not in line.lower() and "ignored" not in line.lower():
            violations.append(line)
    self.assertEqual(violations, [], msg="\n".join(violations))
```

- [ ] **Step 6: Run docs and profile tests**

Run:

```bash
python3 -m pytest tests/test_buddy_env_profiles.py tests/test_runtime_skills.py tests/test_task_management_skill_architecture.py tests/test_repo_consistency.py -q
```

Expected:

```text
passed
```

### Task 11: Remove Legacy Shared Task Repository Access

**Files:**

- Modify: `scripts/env/repos/runtime_files.py`
- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env_legacy_store.py`
- Modify: `scripts/env_store.py`
- Modify: tests that still call old `env_store.create_task`

- [ ] **Step 1: Find all old task object references**

Run:

```bash
rg -n "TASKS_DIR|objects/tasks|create_task\\(|list_tasks\\(|get_task\\(|task_objects|task_object_ids" scripts tests README.md framework buddyswitch tools
```

Expected before this task:

- hits remain in tests and helper code.

- [ ] **Step 2: Remove or redirect helper usage**

For tests that call `env_store.create_task`, prefer replacing test setup with taskbox JSON fixtures or task tool calls.

If a compatibility helper is still needed for tests, rename it to make the new boundary explicit:

```python
def create_instance_task(
    *,
    instance_root: Path,
    buddy: str,
    task: Mapping[str, object],
) -> Path:
    task_id = str(task["id"])
    task_file = instance_root / "taskbox" / buddy / "tasks" / f"{task_id}.json"
    task_file.parent.mkdir(parents=True, exist_ok=True)
    task_file.write_text(json.dumps(dict(task), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return task_file
```

Do not keep a helper named `create_task` if it writes old shared task objects.

- [ ] **Step 3: Remove active `TASKS_DIR` use**

In `runtime_files.py`, either delete `TASKS_DIR` or leave it only inside a test fixture comment-free legacy ignore test. The preferred result is no `TASKS_DIR` constant in live code.

- [ ] **Step 4: Run stale-reference scan**

Run:

```bash
rg -n "TASKS_DIR|buddyswitch/objects/tasks|task_objects|task_object_ids" scripts tools buddyswitch README.md framework tests
```

Expected:

- no live implementation hit
- tests may contain legacy ignore fixtures with clear names containing `legacy` and `ignored`

### Task 12: Full Verification

**Files:**

- No source edits unless verification exposes a real failure.

- [ ] **Step 1: Run focused task verification**

Run:

```bash
python3 -m pytest tests/test_task_env_tool.py tests/test_task_management_skill_architecture.py -q
```

Expected:

```text
passed
```

- [ ] **Step 2: Run launcher and context verification**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py -q
```

Expected:

```text
passed
```

- [ ] **Step 3: Run runtime contract verification**

Run:

```bash
python3 -m pytest tests/test_runtime_broker.py tests/test_env_tool_response_contract.py tests/test_runless_runtime_contract.py tests/test_runtime_tool_feedback.py -q
```

Expected:

```text
passed
```

- [ ] **Step 4: Run cleanup, profile, skill, and consistency verification**

Run:

```bash
python3 -m pytest tests/test_cleanup_system.py tests/test_buddy_env_profiles.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected:

```text
passed
```

- [ ] **Step 5: Run final stale-path scan**

Run:

```bash
rg -n "buddyswitch/objects/tasks|TASKS_DIR|task_objects|task_object_ids" README.md framework scripts tools buddyswitch tests
```

Expected:

- no live path claims or implementation writes to shared task objects
- remaining hits are only tests proving legacy objects are ignored, with names that include `legacy` or `ignored`

- [ ] **Step 6: Run git status**

Run:

```bash
git status --short
```

Expected:

- implementation files are modified
- no files under the main worktree are modified
- no direct edits under `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**`

## Review Checklist

- Task source of truth is instance taskbox JSON, not shared runtime object JSON.
- No old task object fallback exists.
- No old task object mirror exists.
- Launcher creates taskbox for each instance startup.
- Task tool has create, list, get, update, archive, and history.
- Task records have `priority`, `refs`, and `closed_at`.
- `history.md` records lifecycle events and is not the source of truth.
- Context reads the same taskbox as the task tool.
- Cleanup no longer manages shared task objects.
- Skill guidance matches the private instance-local model.
- Tests cover isolation, legacy ignore behavior, validation, lifecycle, and stale docs.

## Execution Notes

This is a forward replacement. If a test fails because it expects shared task objects, update the test to the instance taskbox contract. Do not add a bridge that keeps both behaviors active.

Keep the work in the `clean-runtime-env` worktree. Do not edit the main worktree.
