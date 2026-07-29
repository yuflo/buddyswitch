# S3 Formal Source Snapshot

> Historical pre-mutation snapshot. Current partial-candidate identity:
> `S3-R1-SOURCE-SNAPSHOT.md`.

## Identity

```text
HEAD: 8db3a07c4cca6423a1e2c789281a813800bfa2a9
tree: e3e788150f52ac8a39969737a1829f0829583f31
branch: fea-tool
origin/fea-tool: 8db3a07c4cca6423a1e2c789281a813800bfa2a9
ahead/behind: 0/0
tracked patch SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
index patch SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
non-ignored untracked path SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
S3 affected path count: 79
S3 affected path-set SHA-256: 98d1ca9a6fb9f9baa77774645deb0a0589400ae00b7b748525c684896fd3933c
S3 affected path/content SHA-256: 2f1735d148c6c021264128d1182e56930bea89e02c3972be6aad3bbf59db7742
```

The worktree was clean before S3 preparation. Preparation changes only this
plan directory plus the master migration documents named by the Goal Packet.
No S3 executable change exists at READY.

## Runtime identity

```text
activated_at: 2026-07-29T11:44:27.023663Z
package version: 0.1.0
source digest: 664dc704b9c76293761dd4c36e12f3c38403b73d183a1fceec365e22dcb9963a
distribution digest: 9c9483635358ce4dd66cd3f9107969c2d11efd637bb575efe31c15d3ba88540b
Python: .buddyswitch-runtime/venv/bin/python
package root: .buddyswitch-runtime/venv/lib/python3.13/site-packages/buddyswitch
```

`./buddyswitch-codex env status` returned zero instances and inactive
Browser before and after the preservation runs.

## Current affected behavior

The source-bound Task/Goal/Demand/Tool/Daemon/CLI/Web/system group ran as:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_task_sys_boundaries.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_repo_contracts.py \
  tests/unit/daemon/test_instance_entrypoint.py \
  tests/unit/env_tool/test_active_task_gate.py \
  tests/integration/task_sys \
  tests/integration/goal_mode/test_task_goal_reconciliation.py \
  tests/integration/goal_mode/test_demand_orchestration.py \
  tests/integration/env_tool/test_response_task.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/integration/web/test_management_product_api.py::WebManagementProductApiTests::test_actor_console_api_composes_runtime_task_sys_track_and_im_projection \
  tests/process/launcher/test_public_cli.py::TestLauncherPublicCli::test_public_cli_task_and_track_commands_read_external_projections \
  tests/process/launcher/test_public_cli.py::TestLauncherPublicCli::test_public_cli_task_and_track_malformed_arguments_emit_canonical_errors \
  tests/process/cli/test_black_box_tool_runtime.py::ToolRuntimeProcessTests::test_probe_tool_add_and_delete_use_only_tool_py_registration \
  tests/system/goal_mode/test_product_flow.py::NativeGoalProductFlowSystemTests::test_web_actor_delivers_then_goal_and_demand_complete
```

Result:

```text
run: 4f91dbd4a7d540f2b4b0853d7e69d4b7
result: 101 passed, 18 subtests passed
duration: 205.66s
cleanup: /private/tmp/bs-test-4f91dbd4-504_7mz4 absent
```

The remaining direct-import, fixture, architecture and neighboring consumer
set then ran as one supplemental focused group:

```text
run: ee6bf076007c400588c7aaccab9c5a12
result: 228 passed, 287 subtests passed
duration: 9.39s
cleanup: /private/tmp/bs-test-ee6bf076-u3y6wauy absent
```

Together the two non-overlapping groups prove all 79 current affected paths:

```text
329 passed, 305 subtests passed
```

The clear/resume daemon-lifecycle preservation proof ran separately:

```text
command:
  ./buddyswitch-test focused \
    tests/system/instance_lifecycle/test_interaction.py::TestInstanceInteraction::test_resume_after_clear_daemon_failure_uses_new_thread
run: 1361ebd113804bf8826674b519ec352c
result: 1 passed
duration: 7.69s
cleanup: /private/tmp/bs-test-1361ebd1-jqjbm80h absent
```

The first attempt used the wrong class node id. Run
`d5c442f630834ac59a908ec3a82abf1a` collected no tests and exited 4; its root
is absent. It is retained here as complete execution history and is not
behavior evidence.

The first preparation artifact assertion (`S3A-20260729-01`) rejected because
the plan cited the new decisions as the compact range `D-045–D-048` while the
checker required each ID literally. The plan now lists D-045, D-046, D-047
and D-048 explicitly. This was a documentation-check precision defect, not
product or boundary evidence, and is retained rather than hidden.

The second artifact assertion (`S3A-20260729-02`) rejected because the four
Task test move sources were classified by `tests/integration/task_sys/**` but
three importing files were not named literally. The manifest now enumerates
all four. This was another manifest-proof precision defect and did not touch
product source or runtime state.

Artifact assertion `S3A-20260729-03` then passed. It proved the seven-file
plan set and read order, READY master/ledger/charter state, action-time packet
gates, individually named D-045–D-048 decisions, exactly one authorized
FINAL command, absence of a Task checkpoint/Skill addition, the 79-path and
329/305 baseline records, literal classification of every current test import
of the retired Task owners, clean document diff, no executable/current-
architecture/build change, zero instances, inactive Browser and no test root.

## Current facts

- canonical Task data remains
  `buddyswitch/objects/task-sys/tasks/*.json`;
- canonical statuses remain `active`, `completed`, and `canceled`;
- the Actor Tool remains exactly `list/get/create/cancel`;
- native Goal remains the sole Task execution loop;
- App Server remains Goal persistence and scheduling owner;
- Task owns reconciliation meaning and terminal recording;
- Demand completion remains a later, independent decision;
- no Task Skill exists or is required;
- current module-test discovery and package exclusion are already generic.

## Invalidation

Any executable, build, current architecture, affected test, activation or
accepted boundary-design change after this identity invalidates the matching
evidence. An executor must stop instead of silently refreshing this packet.
