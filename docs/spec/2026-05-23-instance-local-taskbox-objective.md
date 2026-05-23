# Instance-Local Taskbox Objective

Date: 2026-05-23

## Goal

Upgrade BuddySwitch task management from shared runtime task objects into a private, physical taskbox owned by one active buddy instance.

The task system should help a buddy manage its own work as a person would: create tasks, see active work, set priority, track blocked work, close completed work, and review instance-local task history.

## Current Bottleneck

The next co-work improvement depends on clearer task handling inside each buddy's own runtime. Buddy-to-buddy continuity will depend on messages, tracks, artifacts, comments, and requests, not on a shared task queue.

The current task implementation stores tasks under shared runtime objects:

```text
buddyswitch/objects/tasks/*.json
```

That shape makes task look like product-level durable state. It is the wrong boundary for this requirement because the intended task scope is private to one running buddy instance.

## Confirmed Product Decisions

1. A task is private to a single buddy instance.
2. A task lives only as long as that buddy instance lives.
3. Task state is not shared across buddies.
4. Task state is not shared across instances of the same buddy.
5. Co-work continuity is not implemented through task sharing.
6. The launcher creates the private taskbox when the instance starts.
7. Task tools and task skills manage task files; Codex native file editing should not be the task API.
8. Each instance taskbox owns one `history.md` file for task lifecycle memory.
9. Priority and structured references are first-class task fields.
10. Buddybox changes are out of scope for this task.
11. No transitional compatibility path is allowed.

## No Transitional Path

This is a forward replacement.

The implementation must not:

- keep writing new task state into `buddyswitch/objects/tasks`
- read legacy shared task objects as a fallback
- mirror taskbox tasks into shared runtime objects
- add a migration layer for old shared task files
- keep both old and new task repositories active
- expose taskbox as a normal workspace editing surface

Tests should prove legacy shared task files are ignored by the new task tool path.

## Current Code Facts

### Current Task Storage

Current task storage is owned by:

- `scripts/env/repos/runtime_files.py`
  - defines `OBJECTS_ROOT = STATE_ROOT / "buddyswitch" / "objects"`
  - defines `TASKS_DIR = OBJECTS_ROOT / "tasks"`
- `scripts/env/repos/tasks.py`
  - reads and writes task JSON files through `runtime_files.TASKS_DIR`
  - exposes `list_tasks`, `get_task`, `save_task`, and archive helpers
- `scripts/env/domain/tasks.py`
  - validates the existing narrow schema
  - currently allows `title`, `summary`, `status`, and `track_id` updates
- `scripts/env/tools/task/tool.py`
  - declares the task tool actions
  - currently describes active-buddy private tasks while still mutating shared runtime objects
- `scripts/env/tools/task/_impl.py`
  - filters tasks by `task["buddy"] == active_buddy`
  - uses `context.repos.task`

### Current Task Fields

The existing schema effectively supports:

```json
{
  "id": "task-dev-example",
  "buddy": "dev",
  "title": "Example",
  "status": "active",
  "track_id": "track-alpha",
  "summary": "Current summary",
  "created_at": "2026-05-23T12:00:00+08:00",
  "updated_at": "2026-05-23T12:00:00+08:00"
}
```

Missing fields for the upgraded requirement:

- `priority`
- `refs`
- `closed_at`
- history events

### Current Launcher Boundary

The launcher already has instance identity and instance root setup:

- `buddyswitch-codex`
  - binds an instance before startup
  - prepares workspace and project workspace
  - activates the instance
- `tools/launcher/env.sh`
  - defines `BUDDYSWITCH_INSTANCE_ROOT`
  - writes `instance.json`
- `tools/launcher/workspace.sh`
  - avoids projecting old runtime state into instance workspaces
- `tools/launcher/codex_config.py`
  - keeps the state root and repo root out of normal native write access

This is enough to create a private taskbox under the instance root without exposing it as normal project source.

### Current Context Surface

Task context currently comes from shared task objects:

- `scripts/env/tools/context/_impl.py`
  - `candidate_tasks` rows include `task_id`, `title`, `summary`, `status`, `track_id`, and `updated_at`
  - task visibility is filtered by active buddy and visible track

This must read the instance taskbox instead.

### Current Cleanup Surface

Task cleanup currently treats tasks as shared runtime objects:

- `scripts/env_cleanup.py`
  - discovers `buddyswitch/objects/tasks`
  - reports task objects in cleanup plans

This must be removed because instance taskboxes are deleted with their instance root.

### Current Docs And Contracts

Live references to `buddyswitch/objects/tasks` exist in:

- `README.md`
- `framework/contracts/*.md`
- tests that seed or assert shared task objects
- runtime skill docs, especially `buddyswitch/skills/shared/task-tool/SKILL.md`
- env profile tests around `state_capability.task_effects`

These references must be replaced with the instance-local taskbox contract.

## Target Runtime Shape

For a running instance:

```text
instances/<instance-id>/
  taskbox/
    <buddy>/
      tasks/
        task-<id>.json
      history.md
```

The exact `instances/<instance-id>` root is the existing launcher instance root exposed through `BUDDYSWITCH_INSTANCE_ROOT` and `instance.json`.

Each instance currently runs one active buddy, so there is one effective taskbox and one `history.md` per buddy instance.

## Target Task Record

The target JSON record is:

```json
{
  "id": "task-dev-design-review",
  "owner_buddy": "dev",
  "title": "Review design handoff",
  "summary": "Check artifact references and implementation risks.",
  "status": "active",
  "priority": "high",
  "track_id": "track-alpha",
  "refs": [
    {"type": "track", "id": "track-alpha", "label": "Main track"},
    {"type": "buddybox", "logical_name": "prototype/index.html", "label": "Prototype entry"}
  ],
  "created_at": "2026-05-23T12:00:00+08:00",
  "updated_at": "2026-05-23T12:05:00+08:00",
  "closed_at": null
}
```

Field rules:

- `id` must pass the existing runtime object id validation style.
- `owner_buddy` is the active buddy that owns this instance taskbox.
- `title` is required and non-empty.
- `summary` defaults to an empty string.
- `status` is one of `active`, `blocked`, `done`, or `archived`.
- `priority` is one of `high`, `normal`, or `low`.
- `track_id` is optional.
- `refs` is optional and defaults to an empty list.
- `closed_at` is null until status becomes `done` or `archived`.

Allowed `refs` types:

- `track`, with `id`
- `artifact`, with `id`
- `message`, with `id`
- `comment`, with `id`
- `request`, with `id`
- `buddybox`, with `logical_name`

`refs` only store references. This task does not change buddybox read or write behavior.

## Target Tool Behavior

The `task` env tool should support:

- `create`
- `list`
- `get`
- `update`
- `archive`
- `history`

Required create fields:

- `task_id`
- `title`

Optional create fields:

- `summary`
- `status`
- `priority`
- `track_id`
- `refs`

Optional list filters:

- `status`
- `priority`
- `track_id`
- `include_archived`
- `limit`

Default list behavior:

1. Exclude archived tasks.
2. Sort by priority rank: `high`, `normal`, `low`.
3. Sort equal priority groups by `updated_at` descending.
4. Use `id` as a stable final tie-breaker.

Update behavior:

- allows title, summary, status, priority, track_id, and refs changes
- sets `updated_at` on real changes
- sets `closed_at` when status becomes `done` or `archived`
- clears `closed_at` when a task is reopened to `active` or `blocked`
- appends exactly one history event per real lifecycle change

Archive behavior:

- sets status to `archived`
- sets `closed_at` if absent
- does not append a duplicate history line when the task is already archived

History behavior:

- reads the tail of `history.md`
- defaults to a small bounded limit
- returns newest relevant entries without exposing raw filesystem paths as editable surfaces

## Target History Format

`history.md` is an instance-local task lifecycle log.

Recommended line format:

```markdown
- 2026-05-23T12:00:00+08:00 task.create task-dev-design-review status=active priority=high title="Review design handoff"
- 2026-05-23T12:05:00+08:00 task.update task-dev-design-review priority=normal previous_priority=high
- 2026-05-23T12:10:00+08:00 task.archive task-dev-design-review status=archived previous_status=done
```

The log is not a source of truth. Task JSON files are the source of truth.

## Implementation Boundary

The preferred implementation is to replace the internals of the existing task repository module rather than add a second task repository beside it.

Keep the public concept:

```text
context.repos.task
```

Replace what it points to:

- from shared `buddyswitch/objects/tasks`
- to active-instance private taskbox

The task tool should pass active buddy and instance identity into repository operations. The repository should not infer ownership from a shared `buddy` field.

## Non-goals

This task does not build:

- shared cross-buddy tasks
- cross-instance task memory
- message persistence changes
- buddybox file API changes
- task publication
- a workflow engine
- a rule engine
- a generic permission framework
- a compatibility bridge for old task object files
- a UI for task management

## Key Questions Resolved

### Is `history.md` one file per instance?

Yes. It is one file per buddy instance taskbox. Since an instance is bound to one active buddy, this is effectively one `history.md` per instance.

### Can a task reference buddybox content?

Yes. A task may contain a private reference such as:

```json
{"type": "buddybox", "logical_name": "prototype/index.html", "label": "Prototype entry"}
```

The task only records the reference. It does not read buddybox content and does not change buddybox access rules.

### Does this require changing buddybox read or write tools?

No. Buddybox is out of scope for this task.

### Should tasks be recoverable after instance deletion?

No. Taskbox state is instance-local and should disappear with the instance root.

### Should old shared task objects still appear in task list?

No. Old shared task objects must not appear through the new task tool.

## Success Criteria

- Launcher creates `taskbox/<buddy>/tasks` and `taskbox/<buddy>/history.md` for each started instance.
- Task tool creates, lists, reads, updates, archives, and reads history from the active instance taskbox.
- Task JSON records include `priority`, `refs`, and `closed_at`.
- List filtering and sorting match the target behavior.
- Context tool reads active task candidates from the instance taskbox.
- Cleanup no longer treats task files as shared runtime objects.
- No live code path writes tasks to `buddyswitch/objects/tasks`.
- Tests prove old shared task object files are ignored.
- Runtime skill guidance describes instance-local private task management.
- Docs and contracts no longer claim task state lives under `buddyswitch/objects/tasks`.
