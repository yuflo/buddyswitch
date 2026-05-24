# Instance Private Writable Surface Review

Date: 2026-05-24

## Scope

This memo records the implementation and review state for the `Instance Private
Writable Surface` work executed in worktree
`/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env`.

Target change:

- replace old shared-state buddybox usage with one instance-local persistent
  writable surface at `workspace/buddybox`
- replace product-mode writable global temp usage with instance-local
  `instances/<id>/tmp`
- keep Codex runtime-required writable roots intact

This memo also records the current full-test blocker discovered after the
feature-specific work was completed.

## Implemented Changes

### Runtime and repo roots

- `scripts/env/repos/runtime_files.py`
  - `buddybox_local_dir()` now resolves to `runtime_workspace_root(...) / "buddybox"`
  - `instance_tmp_dir()` now resolves to `instance_root/tmp`
  - instance context now relies on explicit `instance_root`
- `scripts/env/repos/buddybox_files.py`
  - removed physical buddy-id suffix from the active buddybox root
  - active root is now the instance workspace root `buddybox/`
- `scripts/env/domain/buddybox_workspace.py`
  - buddybox descriptors now expose `workspace_relative_root = "buddybox"`

### Launcher and runtime environment

- `tools/launcher/env.sh`
  - binds `BUDDYSWITCH_INSTANCE_TMP`
  - ensures `workspace/buddybox` and `instance tmp` exist
  - writes `instance_root` into instance records
  - exports `TMPDIR`, `TMP`, and `TEMP` from the instance-local temp root for
    product mode
- `buddyswitch-codex`
  - startup now ensures the private writable surface before instance activation
- `tools/launcher/app_server.sh`
  - propagates the instance temp environment to the app-server helper
- `scripts/runtime_kernel/dispatcher.py`
  - exports `BUDDYSWITCH_INSTANCE_ROOT` and `BUDDYSWITCH_INSTANCE_TMP`

### Product-mode permission profile

- `tools/launcher/codex_config.py`
  - product mode now grants writes only to:
    - `home`
    - `codex-home`
    - `xdg-config`
    - `workspace/buddybox`
    - `instance_root/tmp`
  - product mode now rejects non-instance temp roots
  - product mode no longer grants write access to global `/tmp` or host
    `TMPDIR`

### Buddybox import and cleanup boundaries

- `scripts/env/tools/buddybox/_impl.py`
  - import sources are allowed only from runtime workspace and instance-local
    temp
  - import rejects buddybox self-import, shared state, source checkout, global
    temp, symlink escapes, and directories
- `tools/launcher/workspace.sh`
  - ensures `workspace/buddybox`
  - removes stale legacy buddybox projections without migration
- `scripts/env_cleanup.py`
  - cleanup now targets `instances/*/workspace/buddybox`

### Env profile contract

- `scripts/env_profiles.py`
  - buddybox root contract is now `buddybox`
  - `filesystem_capability.host_writable` now uses `runtime-temp`
- updated profile JSON files:
  - `buddyswitch/env-profiles/dev.json`
  - `buddyswitch/env-profiles/design.json`
  - `buddyswitch/env-profiles/market.json`
  - `buddyswitch/env-profiles/pm.json`
  - `buddyswitch/env-profiles/test.json`

### Test updates completed for this work

- `tests/test_buddybox_env_tool.py`
- `tests/test_artifact_env_tool.py`
- `tests/test_buddy_env_profiles.py`
- `tests/test_buddy_env_sandbox.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_clean_runtime_environment.py`
- `tests/test_cleanup_system.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_env_layer_boundaries.py`
- `tests/test_env_layer_end_to_end.py`
- `tests/test_host_decision_surface_product_mode.py`
- `tests/test_repo_consistency.py`
- `tests/test_runless_runtime_contract.py`
- `tests/test_runtime_broker.py`
- `tests/test_track_env_tool.py`
- `tests/helpers/fake_codex.py`

## Verification Run

Focused suites run and passing:

- `python3 -m pytest tests/test_buddybox_env_tool.py -q`
- `python3 -m pytest tests/test_buddyswitch_launcher.py -q`
- `python3 -m pytest tests/test_env_layer_boundaries.py -q`
- `python3 -m pytest tests/test_clean_runtime_environment.py -q`
- `python3 -m pytest tests/test_cleanup_system.py -q`
- `python3 -m pytest tests/test_buddy_env_profiles.py -q`
- `python3 -m pytest tests/test_context_binding_env_tool.py -q`
- `python3 -m pytest tests/test_artifact_env_tool.py -q`
- `python3 -m pytest tests/test_repo_consistency.py -q`
- `python3 -m pytest tests/test_env_tool_response_contract.py tests/test_env_tool_payload_contract.py tests/test_env_layer_end_to_end.py -q`
- `python3 -m pytest tests/test_buddy_env_sandbox.py tests/test_track_env_tool.py tests/test_runtime_broker.py tests/test_host_decision_surface_product_mode.py tests/test_runless_runtime_contract.py -q`

Observed result after the task-specific repairs:

- all writable-surface related focused tests pass

## Full Suite Status

Full suite command run:

```bash
python3 -m pytest tests -q
```

Current result:

- `622 passed`
- `10 failed`
- `1385 subtests passed`

Remaining failures are limited to:

- `tests/test_black_box_tool_runtime.py`
- `tests/test_env_tool_schema_contract.py`
- `tests/test_env_tool_semantic_contract.py`

## Remaining Blocker: Task Public Contract Drift

The remaining failures are not in buddybox, launcher, cleanup, context,
artifact-attachment, runtime temp, or product-mode permission behavior.

They are all caused by `task` tool public contract drift introduced earlier by
commit:

- `ac1f9e0 migrate tasks to instance-local taskbox`

Key facts:

- current task implementation exposes `task.history`
  - `scripts/env/tools/task/tool.py`
- current task-specific tests expect and validate `task.history`
  - `tests/test_task_env_tool.py`
- task-specific suite passes:
  - `python3 -m pytest tests/test_task_env_tool.py -q`

But shared contract tests still expect the older task public contract:

- only `create/list/get/update/archive`
- older `task.list` schema expectations
- older task semantic wording, including `context link` phrasing

This leaves the repository in a split state:

- task implementation and task-specific tests agree with the newer taskbox
  model
- black-box/schema/semantic contract tests still encode the older contract

## Review Conclusion For This Work

Within the `Instance Private Writable Surface` scope, the implementation is in
good shape:

- old buddybox runtime paths are no longer active runtime write targets
- product mode no longer exposes global `/tmp` or host temp as writable
- Codex runtime-required writable roots remain available
- no writable-surface fallback or dual-path behavior was added
- instance-local `workspace/buddybox` and `instance tmp` behavior is enforced by
  code and tests

However, the repository is **not yet at full green** because of the pre-existing
task public contract split described above.

## Recommendation

Treat the next step as a separate repair task:

1. decide whether `task.history` is intended public surface
2. either:
   - update shared contract tests and semantic/schema expectations to match the
     current task implementation
   - or remove/revert the public `task.history` exposure and restore the older
     contract
3. rerun:

```bash
python3 -m pytest tests -q
```

until the full suite is green

## Commit Scope Note

The commit prepared from this worktree should include:

- the writable-surface implementation and tests for this task
- this memo
- the development plan document for this task if the user wants the task record
  checked in

It should exclude unrelated dirty files already present in the worktree, such
as:

- `docs/memo/2026-05-23-cowork-forward-stages.md`
- `docs/memo/2026-05-24-instance-record-missing-incident.md`
