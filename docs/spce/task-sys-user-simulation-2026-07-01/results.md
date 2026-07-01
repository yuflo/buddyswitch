# Task Sys User Simulation Results

**Date:** 2026-07-01

**Branch / commit:** `fea-daemon` at `a8a9fc6 Rebuild Task Sys lifecycle`, already pushed to `origin/fea-daemon` before this simulation.

**Simulation root:** `/tmp/buddyswitch-task-sys-user-sim-20260701`

**Plan:** `docs/spec/task-sys-user-simulation-2026-07-01/plan.md`

## Result

Overall result: **PASS for the Task Sys rebuild lifecycle semantics**, with one runtime cleanup observation.

The simulation started real BuddySwitch product-mode actors from the CLI, sent user inputs through `./buddyswitch-codex instance input`, observed Task Sys status projections, and used actor-facing `task_sys` tool calls through the env tool boundary. It did not call `env.domain.task_sys` mutators directly for scenario actions.

## Scenarios

| Scenario | Role | Actor | Task | Result |
| --- | --- | --- | --- | --- |
| S1 side close | `test` | `act-test-12a3b51dabba` | `task-user-input-dfb1031f4c23` | Started as `side_processing`, closed by actor-facing `task_sys.close`, final active count `0`. |
| S2 side to parent | `pm` | `act-pm-4550af446a72` | `task-user-input-aacaa1a120cc` | Started as `side_processing`, moved to `parent_processing` through `task_sys.need_parent`, closed by parent on the same task id. |
| S3 ownership / live actor behavior | `dev` | `act-dev-0267c50795f0` | `task-user-input-cb4ec5a04200` | Initially observed as `side_processing`; the live actor then requested parent and parent closed the same task. Cross-actor `get` was rejected for `test` and `pm`. |

## Evidence Summary

### Commit Confirmation

- `git log -1 --oneline --decorate` showed `a8a9fc6 (HEAD -> fea-daemon, origin/fea-daemon) Rebuild Task Sys lifecycle`.
- This confirms the simulation ran after the Task Sys optimization commit was already synchronized.

### S1: Side Close

Raw evidence:

- `s1_start_test.json`
- `s1_input_test.json`
- `s1_status_before_close.json`
- `s1_tool_close.json`
- `s1_status_after_close.json`
- `s1_task_record_after_close.json`
- `s1_daemon_tail.log`
- `s1_app_server_tail.log`

Observed:

- `instance input` returned `action: "task_created"`, `instruction_type: "start_side"`, `runtime.action: "start_side"`.
- Before close, `instance status` reported `daemon.task_sys.active_count: 1`, `by_status: {"side_processing": 1}`, `active_processor: "side"`.
- `task_sys.close` returned a closed task.
- Final task events: `created`, `side_frame_started`, `closed`, `side_cleanup_recorded`.
- Final `instance status` reported `daemon.task_sys.active_count: 0`.

### S2: Parent Handoff And Parent Close

Raw evidence:

- `s2_start_pm.json`
- `s2_input_pm.json`
- `s2_status_before_need_parent.json`
- `s2_tool_need_parent.json`
- `s2_status_after_need_parent.json`
- `s2_tool_parent_close.json`
- `s2_status_after_parent_close.json`
- `s2_task_record_after_parent_close.json`
- `s2_daemon_tail.log`
- `s2_app_server_tail.log`

Observed:

- `instance input` created one `user.input` Task Sys task with `instruction_type: "start_side"`.
- `task_sys.need_parent` preserved `task-user-input-aacaa1a120cc`.
- Parent instruction was `submit_parent`; parent runtime returned `action: "submit_parent"`.
- After handoff, status projection reported `by_status: {"parent_processing": 1}`, `active_processor: "parent"`.
- Parent close recorded `close_result.processor: "parent"`.
- Final task events: `created`, `side_frame_started`, `side_parent_requested`, `parent_handoff_started`, `side_cleanup_recorded`, `closed`.
- Final active count was `0`.

### S3: Actor-Owned Isolation And Real Actor Autonomy

Raw evidence:

- `s3_start_dev.json`
- `s3_input_dev.json`
- `s3_status_dev_active.json`
- `s3_dev_list_all.json`
- `s3_dev_get_own.json`
- `s3_test_list_all.json`
- `s3_pm_list_all.json`
- `s3_test_get_dev_rejected.json`
- `s3_pm_get_dev_rejected.json`
- `s3_status_dev_final.json`
- `s3_task_record_dev_active.json`
- `s3_daemon_tail.log`
- `s3_app_server_tail.log`

Observed:

- Immediately after user input, `instance status` showed the Dev task as `side_processing` with `active_processor: "side"`.
- Dev `task_sys.list` showed only the Dev-owned task.
- Test `task_sys.list` showed only the Test-owned S1 task.
- PM `task_sys.list` showed only the PM-owned S2 task.
- Test and PM `task_sys.get` against the Dev task returned the expected `PermissionError: task does not belong to the active actor`.
- The live Dev actor then made a real `task_sys.need_parent` decision and parent closed the same task. This changed the original S3 expectation of "leave it active" into a useful live-behavior observation: the actor cannot create Task Sys tasks directly, so it handed off and closed the source task through the same lifecycle.

## Pass Criteria Audit

| Criterion | Evidence | Status |
| --- | --- | --- |
| Each `instance input` creates exactly one Task Sys task with source type `user.input`. | `s1_input_test.json`, `s2_input_pm.json`, `s3_input_dev.json` | PASS |
| New task records start as `side_processing` with `active_processor: "side"`. | `s1_status_before_close.json`, `s2_status_before_need_parent.json`, `s3_status_dev_active.json` | PASS |
| Task records contain lifecycle events instead of checkpoint/no-actor-action records. | `s1_task_record_after_close.json`, `s2_task_record_after_parent_close.json`, `s3_task_record_dev_active.json`; residue scan found no checkpoint/no-actor-action task record fields | PASS |
| S1 closes in side and records side cleanup. | `s1_tool_close.json`, `s1_task_record_after_close.json` | PASS |
| S2 preserves the same task id across side handoff, parent submit, and parent close. | `s2_tool_need_parent.json`, `s2_tool_parent_close.json`, `s2_task_record_after_parent_close.json` | PASS |
| S3 proves actor-owned reads and cross-actor rejection. | `s3_dev_list_all.json`, `s3_test_list_all.json`, `s3_pm_list_all.json`, `s3_test_get_dev_rejected.json`, `s3_pm_get_dev_rejected.json` | PASS |
| `instance status` task_sys projection agrees with task object state. | before/after status JSON for S1/S2/S3 | PASS |
| Log review shows no runtime errors contradicting task state. | `rg` over captured `*.log` found no error/failed/Traceback lines; daemon `app_server.turn_completed` notifications were ignored by `task_checkout` as expected | PASS |

## Observations

1. `task_checkout` ignored `app_server.turn_completed` in the daemon log. This supports the rebuild requirement that completed turns do not create Task Sys tasks.
2. Side cleanup recorded `registry_unregistered: true`, but physical side close reported `thread/turns/list failed (-32600): ephemeral threads do not support thread/turns/list` in S1/S2/S3 records. This did not contradict Task Sys state: every affected task still reached the expected lifecycle state and no daemon/app log error was captured. It is a runtime cleanup follow-up candidate, not a Task Sys lifecycle failure.
3. S3 demonstrated real actor autonomy: the Dev actor correctly treated "create an independent task" as outside side authority, requested parent, then parent closed the source task because actor-facing Task Sys intentionally has no create action.

## Cleanup

All three simulation actors were stopped and deleted after evidence capture:

- `cleanup_stop_test.json`, `cleanup_delete_test.json`
- `cleanup_stop_pm.json`, `cleanup_delete_pm.json`
- `cleanup_stop_dev.json`, `cleanup_delete_dev.json`
- `cleanup_instance_list_after_delete.json` shows `{"instances":[]}` for the isolated simulation root.

## Commands Used

Representative commands:

```bash
export BUDDYSWITCH_SHARED_ROOT=/tmp/buddyswitch-task-sys-user-sim-20260701
./buddyswitch-codex instance start --role test --json
./buddyswitch-codex instance input act-test-12a3b51dabba --text "..." --json
./buddyswitch-codex instance status act-test-12a3b51dabba --json
python3 docs/spce/task-sys-user-simulation-2026-07-01/task_sys_actor_tool_probe.py close --instance-json ... --task-id ...
python3 docs/spce/task-sys-user-simulation-2026-07-01/task_sys_actor_tool_probe.py need-parent --instance-json ... --task-id ...
rg -n "Traceback|Exception|failed|physical_close_error|last_error|\"error\"" docs/spce/task-sys-user-simulation-2026-07-01/*.log
```
