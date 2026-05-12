# Task Management Skill Architecture Handoff Memo

## Purpose

This memo records the converged architecture decision for completing the task-management rebuild in `dev2258`.

The current issue is not only that `task-tool` exists as a skill. The incomplete part is that system runtime paths still create, bind, and update tasks outside the host-driven skill loop. The target is to finish the migration so task management is owned by buddies through the runtime skill architecture.

## Current Finding

The motivating log showed a PM request:

> 创建3个task关于为三款产品（日程管理工具、邮件管理工具、财务管理工具）分别制作简单的landing page

The PM buddy created three explicit tasks through `task-tool`:

- `task-pm-landing-page-50cefcd4`
- `task-pm-landing-page-ab3fd1f8`
- `task-pm-landing-page-7ad912e7`

But the final receipt also showed:

- `task-pm-3-task-landing-page-a200dce2b7`

That fourth task was not created by the PM's explicit `task create` calls. It came from system-level `prepare` behavior. In the current code, `scripts/turn_runtime.py` creates a prepared task when no explicit current task exists, and `persist` then records the run against that task.

## Root Cause

The task-manager-to-task-tool migration removed manager vocabulary and exposed a skill-facing task tool, but task lifecycle authority was not fully moved out of the runtime run path.

Current task authority still leaks through:

- `prepare` creating or repairing tasks.
- `context_revision` depending on a task object.
- run reservation depending on `task_id`.
- `persist` treating every run as current-task work.
- `state_effects.task` mutating task status and summary.
- `state_effects.track` indirectly linking tasks to tracks.
- artifact persistence writing artifacts into task slots.
- post-persist binding update deriving current task from receipt or refreshed context.

These paths mean the system still partially manages tasks even when the host used `task-tool`.

## Converged Target

Complete task management handoff means:

> The system owns run boundaries and validation. Buddies own task lifecycle decisions through skills and broker-routed env tools.

In final form:

- User input does not automatically create a task.
- `prepare` never creates, repairs, binds, updates, or archives a task.
- `persist` never creates, repairs, binds, updates, archives, or links a task.
- Task creation, status change, archival, and current binding happen only through `task-tool` or an explicitly authorized env tool action invoked by the host.
- A run may be taskless. Task association is optional metadata, not the runtime envelope's required container.
- Taskless runs are valid when the buddy decides no task object is needed.

## Final User Input Chain

### System-Owned Steps

1. Launcher locks the active instance and active buddy.
2. `turn_runtime.py prepare` loads manifest, active buddy profile, current instance binding, and readable context.
3. `prepare` creates a run envelope and run reservation.
4. `prepare` returns runtime context, decision surface, env tool hints, and persist command hints.
5. Broker validates identity, instance status, tool envelope shape, permissions, and ownership for any env tool call.
6. `persist` commits only a run audit and receipt.

System output after `prepare` may include `current_task_id` only when a task was already explicitly bound. It must not synthesize one.

### Buddy-Owned Steps

1. Host reads the materialized `.agents/skills/<skill-id>/SKILL.md` packages.
2. Buddy decides whether the request needs task state.
3. If a task is needed, buddy uses `task-tool`:
   - `python3 scripts/env/client.py task create --payload <json-file>`
   - `python3 scripts/env/client.py task set-current --task-id <task-id>`
   - `python3 scripts/env/client.py task update --payload <json-file>`
   - `python3 scripts/env/client.py task archive --task-id <task-id>`
4. If track or artifact state is needed, buddy uses the relevant `track-tool` or `artifact-tool`.
5. Buddy prepares the final result payload.
6. System persists the run audit without adding hidden task effects.

## Desired Architecture Loop

Task state changes should flow through this loop only:

```text
host
  -> .agents/skills/task-tool/SKILL.md
  -> python3 scripts/env/client.py task <operation>
  -> runtime broker method env.tool
  -> scripts/env/tools/router.py
  -> scripts/env/tools/dispatch.py
  -> scripts/env/services/tasks.py
  -> buddyswitch/objects/tasks/*.json
```

The current code already has the positive path:

- CLI task surface: `scripts/env/client.py`
- broker/router entry: `scripts/env/tools/router.py`
- task action dispatch: `scripts/env/tools/dispatch.py`
- task lifecycle service: `scripts/env/services/tasks.py`
- skill package: `buddyswitch/skills/shared/task-tool/SKILL.md`
- runtime materialization: `scripts/runtime_skills.py`
- buddy membership: `buddyswitch/manifest.toml`

The remaining implementation work is to remove runtime bypasses around this path.

## Boundary Rules

### Runtime May

- Read current task binding.
- Read task context for projection.
- Report stale or missing bindings.
- Validate active buddy, instance id, and permissions.
- Save run audit content.
- Return structured feedback pointing the buddy to `task-tool`.

### Runtime Must Not

- Create a task during `prepare`.
- Create a task during `persist`.
- Repair a missing bound task.
- Auto-bind the instance to any task after persist.
- Update task status or summary from `state_effects.task`.
- Attach a task to a track from persist side effects.
- Add run ids to a task as part of the generic run commit.

### Buddy Must

- Use `task-tool` for task create/list/get/get-current/set-current/update/archive.
- Use task ids explicitly when a run or artifact should be associated with a task.
- Update task status explicitly when the product workflow semantics require it.
- Treat unbound context as a normal state, not as an error requiring system task creation.

## Implementation Direction

The implementation should be a rebuild-forward cleanup, not a compatibility patch.

### Phase 1 - Contract Rewrite

- Update `framework/contracts/persist-buddy-run.json`.
- Change the request boundary from "current task/track context" to "active buddy + reserved run envelope + optional binding snapshot".
- Remove `task_id` and `task_title` from required receipt fields.
- Mark task association as optional metadata.

### Phase 2 - Prepare Decoupling

- Remove automatic `_derive_task_id` / `create_task` behavior from `scripts/turn_runtime.py`.
- If no current task is bound, return `current_task_id: null`, `task_context: null`, and `binding_state: unbound`.
- If a bound task id is missing, return stale context or structured feedback. Do not repair it by creating a task.
- Make context revision derive from the run envelope instead of a task object.

### Phase 3 - Reservation Decoupling

- Allow run reservations with `task_id: null`.
- Keep run-id and instance identity checks.
- Preserve task-level concurrency checks only when an explicit task is bound.

### Phase 4 - Persist Becomes Audit-Only

- Remove task mutation from run commit.
- Remove `state_effects.task` from persist validation and hints.
- Remove `state_effects.track` paths that register tasks to tracks from persist.
- Remove artifact content creation from persist if artifact writing is already handled by `artifact-tool`.
- Persist should record what happened, not perform task lifecycle work.

### Phase 5 - Binding Cleanup

- Remove post-persist instance binding updates derived from receipt or refreshed context.
- Keep explicit binding actions:
  - `task.set-current`
  - `binding.set-task`
  - `binding.clear`
- Update runtime feedback to direct the buddy to those commands.

### Phase 6 - Skill And Host Guidance Cleanup

- Update `task-tool` to state that it is the only task lifecycle path.
- Update buddy AGENTS receipt language so `task` is optional, not required.
- Remove guidance that says task updates must use `state_effects.task`.
- Update framework docs that currently say every run belongs to a task.

### Phase 7 - Guard Tests

Add regression tests that prove:

- Unbound `prepare` creates no task files.
- A request to create three tasks produces exactly three tasks.
- `persist` does not mutate task objects.
- `persist` does not update instance `current_task_id`.
- `state_effects.task` is rejected with guidance to use `task.update`.
- Static scans prevent `prepare` and `persist` from calling task mutation APIs.

## Important Design Decisions

### Decision 1 - Do Not Hide The Fourth Task

Hiding `task_id` in the receipt would only mask the symptom. The task would still exist and would still pollute context, run history, and future binding decisions. The fix must remove hidden system task creation.

### Decision 2 - Runs Can Be Taskless

The old model treated task as the container for every run. The new model treats run as the system audit envelope. A task is a product workflow object that exists only when a buddy chooses to create or bind it.

### Decision 3 - Persist Is Not A Task Mutation Surface

`persist` should close the runtime audit loop. It should not be a second task-update API. Task updates belong to `task-tool`, where permissions, ownership, and host intent are explicit.

### Decision 4 - Track And Artifact Side Effects Need The Same Treatment

Task handoff is incomplete if `track` or `artifact` persist behavior can still mutate task linkage or task slots implicitly. Those writes must be routed through their explicit env tools, or clearly identified as non-task lifecycle writes.

### Decision 5 - Skill Architecture Means Host Execution, Not Prompt Advice

The intended control loop is host-driven skill execution:

```text
tools layer -> SKILL package -> host action -> broker-routed service
```

Prompt text alone is not enough. Runtime code and tests must make bypasses impossible or visible.

## What Counts As Done

The rebuild is complete only when:

- No user input creates a task unless the buddy invokes a task env tool.
- No runtime prepare or persist path can mutate task state.
- Task binding changes only through explicit task or binding tools.
- Task status changes only through explicit task tools.
- Runtime docs, AGENTS, skills, contracts, and tests describe task as buddy-owned.
- Automated tests prove taskless runs and explicit task workflows both work.
- Static tests guard against reintroducing task mutation in prepare/persist/run paths.

## Open Implementation Questions

- Whether `track.attach-task` and `track.detach-task` remain in `track-tool` or move under `task-tool`.
  - If "task lifecycle" includes task-track relation, move them or make the authority rule explicit.
  - If track ownership includes track membership, keep them in `track-tool` but treat them as explicit skill/env-tool task linkage, not system side effects.
- Whether `artifact-tool` should require an explicit task binding for artifact creation or allow run-scoped artifacts.
  - Existing code models artifacts as task-owned.
  - If artifacts remain task-owned, artifact creation should require buddy-selected task context.
  - If run-scoped artifacts are needed, that is a separate schema decision and should not be smuggled through this task handoff.

## Recommended Next Step

Write an implementation plan that starts from tests, not runtime edits. The first failing tests should prove:

1. unbound prepare creates no task;
2. creating three tasks creates exactly three tasks;
3. persist does not mutate task or binding state;
4. `state_effects.task` is no longer accepted.

Those tests define the architecture boundary before deleting the old system-owned task behavior.
