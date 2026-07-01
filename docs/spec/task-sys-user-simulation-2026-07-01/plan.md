# Task Sys User Simulation Plan

**Goal:** Verify the committed Task Sys rebuild with user-like product-mode flows, starting from actor creation, across multiple actor roles and lifecycle outcomes.

**Precondition:** The optimization is already committed on `fea-daemon` as `a8a9fc6 Rebuild Task Sys lifecycle`, with the worktree clean and synced to `origin/fea-daemon`.

**Record paths:**
- Plan: `docs/spec/task-sys-user-simulation-2026-07-01/plan.md`
- Results: `docs/spce/task-sys-user-simulation-2026-07-01/results.md`
- Raw command/log evidence: `docs/spce/task-sys-user-simulation-2026-07-01/`

## Scope

This is not a unit-test rerun. The main path uses `./buddyswitch-codex` product-mode commands:

1. Create actors with `instance start --role <role> --json`.
2. Send user-visible work with `instance input <actor-id> --text ... --json`.
3. Inspect product status with `instance status <actor-id> --json`.
4. Observe runtime task records and daemon/app-server logs.
5. Simulate the actor's `task_sys` env tool calls only through `scripts.env.tools.task_sys._impl.invoke`, using the actor identity from the real instance and Task Sys runtime cleanup/parent-submit helpers. Do not call `env.domain.task_sys` mutators directly in the scenario steps.

The simulation uses an isolated shared root so it does not mix with a developer's default BuddySwitch state:

```bash
export BUDDYSWITCH_SHARED_ROOT=/tmp/buddyswitch-task-sys-user-sim-20260701
rm -rf "$BUDDYSWITCH_SHARED_ROOT"
```

## Actor Matrix

| Scenario | Role | User action | Expected Task Sys path |
| --- | --- | --- | --- |
| S1 | `test` | Short validation request that side can finish | `user.input` creates one `side_processing` task; actor-facing `task_sys.close` closes the same task |
| S2 | `pm` | Request that needs parent resources | `user.input` creates one `side_processing` task; actor-facing `task_sys.need_parent` preserves the task id and submits parent frame; parent-facing `task_sys.close` closes the same task |
| S3 | `dev` | Separate implementation request left active | `user.input` creates one independent actor-owned `side_processing` task; `test`/`pm` task lists do not show it |

## Evidence To Capture

For every actor:

- `instance start` JSON.
- `instance input` JSON, including `task_id`, `instruction.type`, and runtime result.
- `instance status` JSON before and after the task_sys operation.
- Task record JSON from `$BUDDYSWITCH_SHARED_ROOT/state/buddyswitch/objects/task-sys/tasks/<task_id>.json`.
- Instance daemon log and app-server log excerpts when available.

For actor-facing tool calls:

- `task_sys.list` before mutation.
- `task_sys.get` before and after mutation.
- `task_sys.close` or `task_sys.need_parent` result JSON.
- Ownership negative check: a different actor's `task_sys.get` for the task must be rejected.

## Scenario Steps

### S1: Test Actor Side Close

1. Start actor:

```bash
./buddyswitch-codex instance start --role test --json
```

Expected: JSON includes `actor_id`, `role: "test"`, `workspace_dir`, `project_workspace_dir`, and `instance_record`.

2. Send user input:

```bash
./buddyswitch-codex instance input <test_actor_id> --text "请快速确认 Task Sys side close 主路径是否能闭环，并用 Task Sys 完成当前任务。" --json
```

Expected:
- `action: "task_created"`
- `instruction_type: "start_side"`
- `runtime.action: "start_side"`
- `runtime.status` is absent or not `runtime_failed`

3. Inspect status:

```bash
./buddyswitch-codex instance status <test_actor_id> --json
```

Expected:
- `daemon.task_sys.active_count: 1`
- active task has `status: "side_processing"`
- active task has `active_processor: "side"`

4. Simulate the actor's Task Sys tool read and close:

```bash
python3 docs/spce/task-sys-user-simulation-2026-07-01/task_sys_actor_tool_probe.py close \
  --instance-json <test_instance_record> \
  --task-id <test_task_id> \
  --summary "Side validation completed in the simulated actor frame."
```

Expected:
- `task_sys.list` shows the task before close.
- `task_sys.close` returns `task_status: "closed"`.
- post-close `task_sys.get` returns events including `created`, `side_frame_started`, `closed`, and `side_cleanup_recorded`.
- final actor status has `daemon.task_sys.active_count: 0`.

### S2: PM Actor Parent Handoff And Close

1. Start actor:

```bash
./buddyswitch-codex instance start --role pm --json
```

2. Send user input:

```bash
./buddyswitch-codex instance input <pm_actor_id> --text "请把 Task Sys parent handoff 主路径跑通：side 判断需要 parent，parent 收到 frame 后再关闭同一个 task。" --json
```

Expected initial state is the same as S1: one `side_processing` task owned by the PM actor.

3. Simulate actor-facing parent handoff:

```bash
python3 docs/spce/task-sys-user-simulation-2026-07-01/task_sys_actor_tool_probe.py need-parent \
  --instance-json <pm_instance_record> \
  --task-id <pm_task_id> \
  --parent-frame-context '{"reason":"requires parent-thread task_sys validation","source":"manual user simulation"}' \
  --relation "simulation_parent_handoff" \
  --interrupt false
```

Expected:
- `task_sys.need_parent` returns `task_status: "parent_processing"`.
- `parent_instruction.type: "submit_parent"`.
- `parent_runtime.action: "submit_parent"`.
- post-handoff task record preserves the same task id and includes `side_parent_requested`, `parent_handoff_started`, and `side_cleanup_recorded`.

4. Simulate parent frame close:

```bash
python3 docs/spce/task-sys-user-simulation-2026-07-01/task_sys_actor_tool_probe.py close \
  --instance-json <pm_instance_record> \
  --task-id <pm_task_id> \
  --summary "Parent frame validation completed on the same Task Sys task."
```

Expected:
- `task_sys.close` returns `task_status: "closed"`.
- final record has `close_result.processor: "parent"`.
- final events include `closed`.

### S3: Dev Actor Ownership And Independent Active Task

1. Start actor:

```bash
./buddyswitch-codex instance start --role dev --json
```

2. Send user input:

```bash
./buddyswitch-codex instance input <dev_actor_id> --text "请创建一个独立的 dev Task Sys active task，用于验证 actor-owned list/get 隔离。" --json
```

Expected:
- one `side_processing` task owned by the Dev actor.
- `task_sys.list` for Dev shows the Dev task.
- `task_sys.list` for Test and PM does not show the Dev task.
- `task_sys.get` from Test or PM against the Dev task is rejected with ownership failure.

## Pass Criteria

The simulation passes only if all of these are true:

1. Each `instance input` creates exactly one Task Sys task with source type `user.input`.
2. New task records start as `side_processing` with `active_processor: "side"`.
3. Task records contain lifecycle events instead of checkpoint/no-actor-action records.
4. S1 closes in side and records side cleanup.
5. S2 uses the same task id across side handoff, parent submit, and parent close.
6. S3 proves actor-owned reads: each actor sees its own active tasks, and cross-actor `get` is rejected.
7. `instance status` task_sys projection agrees with task object state.
8. Log review shows no runtime errors that contradict the task state.

## Cleanup

After evidence capture:

```bash
./buddyswitch-codex instance stop <actor-id> --json
./buddyswitch-codex instance delete <actor-id> --yes --json
```

Keep copied logs and JSON evidence under `docs/spce/task-sys-user-simulation-2026-07-01/`.
