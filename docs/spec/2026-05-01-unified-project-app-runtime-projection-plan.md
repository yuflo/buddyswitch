# Unified Project App Runtime Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `projects/app` mean the same shared product app path for every product-mode buddy, without relying on SKILL instructions or user-provided paths.

**Architecture:** Keep Codex cwd in the launcher-owned instance runtime workspace so BuddySwitch runtime control flow, state projections, and `scripts/switch_runtime.py resolve/persist` continue to work. Replace the instance runtime workspace's `projects/app` checkout copy with a filesystem projection to `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`, so all relative `projects/app` reads, writes, serves, and smoke checks hit the same shared product app. Remove the old instance-local `projects/app/.runtime` and `--app-runtime` cleanup model instead of preserving dual behavior.

**Tech Stack:** Bash launcher helpers, Git worktrees, symlink filesystem projection, Python cleanup utility, fake Codex launcher integration tests, `pytest`, repo consistency checks.

---

## Scope

In scope:

- Make `projects/app` in every product-mode instance resolve to `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`.
- Keep `BUDDYSWITCH_WORKSPACE_DIR` as the per-instance runtime workspace and Codex cwd.
- Keep shared product source under `${BUDDYSWITCH_SHARED_ROOT}/project/workspace`.
- Ensure `instance start` and `instance open` both repair the `projects/app` projection.
- Remove instance-local `projects/app/.runtime` creation, staging, cleanup, docs, and tests.
- Remove `data cleanup --app-runtime` and its Python cleanup branches.
- Remove old compatibility code that migrates legacy `${BUDDYSWITCH_SHARED_ROOT}/workspace` durable state.
- Remove unused legacy cleanup-exclude stripping logic.
- Update active docs so product-facing instructions say `projects/app`, not `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`.

Out of scope:

- Moving Codex cwd to the shared project workspace.
- Track-level or task-level project worktrees.
- Migrating product edits from old instance workspace copies.
- Preserving `projects/app/.runtime` as a compatibility path.
- Adding new workflow engines, adapters, or routing layers.

## Current Code Facts

- `buddyswitch-codex` runs Codex after `cd "${BUDDYSWITCH_WORKSPACE_DIR}"`.
- `BUDDYSWITCH_WORKSPACE_DIR` is `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace` in product mode.
- `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}` already defaults to `${BUDDYSWITCH_SHARED_ROOT}/project/workspace`.
- The shared project workspace is already created as a Git worktree and preserved across instance deletion.
- The runtime worktree still contains a tracked `projects/app` checkout copy, which makes relative `projects/app` ambiguous.
- `tools/launcher/workspace.sh` still creates and preserves `projects/app/.runtime`.
- `buddyswitch-codex data cleanup --app-runtime` and `scripts/env_cleanup.py` still own cleanup behavior for that old path.
- Runtime docs and buddy AGENTS currently mention `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app` as a path buddies should consciously use.

## Target Behavior

- In a product-mode Codex session, `pwd` remains the instance runtime workspace.
- In that same session, `realpath projects/app` equals `realpath ${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`.
- A file written by `pm` to relative `projects/app/...` is visible to `dev`, `test`, `design`, and `market` through the same relative path.
- The instance runtime workspace does not contain a separate durable copy of `projects/app`.
- No buddy needs to read SKILL-specific path guidance to choose the correct product app directory.
- Runtime scratch stays outside `projects/app`; current retained scratch path is `runs/raw/`.
- Cleanup can delete runtime state and raw outputs, but must never delete shared product source.

## File Map

- Modify: `tools/launcher/workspace.sh`
  - Add product app projection helper.
  - Remove `projects/app/.runtime` from runtime output, local runtime path, skeleton, excludes, and staging/restore logic.
  - Remove legacy state migration helper.

- Modify: `buddyswitch-codex`
  - Call shared project worktree ensure + runtime product app projection from `instance start`.
  - Call the same projection repair from `instance open`.
  - Remove the legacy state migration call.
  - Remove `data cleanup --app-runtime` from help and parsing.

- Modify: `tools/launcher/cleanup.sh`
  - Remove `--app-runtime` target.
  - Remove unused `buddyswitch_cleanup_strip_legacy_runtime_excludes`.
  - Keep `--buddy` and `--all-data`.

- Modify: `scripts/env_cleanup.py`
  - Remove `--app-runtime`.
  - Remove `app-runtime` scope mapping.
  - Remove internal `project` / `project_runtime` cleanup branches.
  - Keep shared-root instance discovery for `runs/raw` cleanup only.

- Modify: `framework/console/app.js`
  - Remove `./buddyswitch-codex data cleanup --app-runtime` suggestions.

- Modify active docs:
  - `README.md`
  - `AGENTS.md`
  - `tools/launcher/assets/runtime-AGENTS.md`
  - `tools/launcher/assets/buddies/{pm,dev,design,market,test}/AGENTS.md`
  - `framework/docs/artifacts-runs-git-policy.md`
  - `framework/docs/interface-spec.md`
  - `framework/contracts/dev.md`
  - `framework/contracts/test.md`
  - `buddyswitch/skills/dev/implement-task/SKILL.md`
  - `buddyswitch/skills/test/smoke-test/SKILL.md`

- Modify tests:
  - `tests/test_buddyswitch_launcher.py`
  - `tests/test_cleanup_system.py`
  - `tests/test_repo_consistency.py`

## Non-Cheating Test Rules

- Test public CLI behavior through `./buddyswitch-codex instance start`, `instance open`, `instance delete`, `env reset`, and `data cleanup`.
- Use fake Codex only as the launched process observing cwd, environment, `realpath`, and file effects.
- Do not assert that a private helper was called.
- Do not make tests pass by checking implementation-specific function names.
- Do not construct tests around current implementation internals; start from user-visible behavior: relative `projects/app` must be shared across buddies.
- Use actual filesystem reads/writes to prove path behavior.
- For cleanup, prove product source survives by checking real files, not by checking a hard-coded exclusion list.

## Detailed Test Plan

### Launcher Behavior Tests

- Add `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app`
  - Launch `./buddyswitch-codex instance start --buddy pm` with fake Codex.
  - Fake Codex records:
    - `cwd`
    - `BUDDYSWITCH_PROJECT_WORKSPACE_DIR`
    - `Path("projects/app").exists()`
    - `Path("projects/app").resolve(strict=True)`
    - `Path(os.environ["BUDDYSWITCH_PROJECT_WORKSPACE_DIR"]) / "projects" / "app"`
  - Assert `cwd` is the instance runtime workspace.
  - Assert relative `projects/app` exists.
  - Assert relative `projects/app` resolves to the shared project app.
  - Assert writing `projects/app/relative-path-sentinel.txt` creates the file under the shared project app.
  - Assert the same sentinel does not exist as a separate regular file under the instance workspace outside the projection target.
  - Expected failure before implementation: relative `projects/app` resolves to the instance workspace copy.

- Add `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_cross_buddy_relative_projects_app_is_shared`
  - Launch `pm` with fake Codex writing `projects/app/cross-buddy-sentinel.txt`.
  - Launch `dev` with fake Codex reading `projects/app/cross-buddy-sentinel.txt`.
  - Assert both sessions have different `cwd` values.
  - Assert both sessions resolve `projects/app` to the same shared app path.
  - Assert `dev` reads the exact content written by `pm`.
  - Expected failure before implementation: `dev` reads its own instance copy and cannot see the `pm` relative write.

- Add `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_repairs_existing_runtime_projects_app_copy`
  - Create or launch an instance whose runtime workspace contains a real directory at `projects/app`.
  - Put `projects/app/instance-only-stale.txt` in that runtime directory.
  - Open the instance through `./buddyswitch-codex instance open <instance-id>` with fake Codex.
  - Assert `realpath projects/app` is the shared project app.
  - Assert `projects/app/instance-only-stale.txt` is not visible after open unless it also exists in shared product source.
  - Assert a new relative write lands in shared product source.
  - Expected failure before implementation: stale instance-local app copy remains active.

- Update `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace`
  - Keep proving the shared project worktree exists.
  - Replace old `.runtime` assertions with the new assertion that runtime `projects/app` resolves to shared app.
  - Assert `${project_workspace}/projects/app/.runtime` is not created.

- Update `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_project_workspace_is_shared_across_buddy_instances`
  - Change fake Codex write/read from `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app/...` to relative `projects/app/...`.
  - Keep the cross-buddy shared content assertion.

- Update `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_reset_removes_shared_project_worktree_registration`
  - Keep current reset assertions.
  - Add proof that runtime `projects/app` projection does not leave a broken registered worktree entry after reset.

### Cleanup Tests

- Remove or rewrite tests that expect `projects/app/.runtime` to exist or be cleaned.
- Add `tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_cleanup_rejects_removed_app_runtime_target`
  - Run `./buddyswitch-codex data cleanup --app-runtime`.
  - Assert exit code `2`.
  - Assert stderr says the target was removed and lists only supported targets: `--buddy <buddy>` and `--all-data`.
  - This verifies no old cleanup compatibility remains.

- Update `tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_data_cleanup_keeps_shared_project_workspace`
  - Create `project/workspace/projects/app/product-source-sentinel.txt` under the shared root.
  - Run `./buddyswitch-codex data cleanup --all-data --yes --json`.
  - Assert cleanup succeeds.
  - Assert the sentinel still exists.
  - Assert `deleted_paths` does not include anything under `project/workspace/projects/app`.
  - This test must not rely on a hard-coded implementation exclude; it verifies the observable product source survives cleanup.

- Update symlink safety tests in `tests/test_cleanup_system.py`
  - Remove symlink cases specific to `projects/app/.runtime`.
  - Keep symlink safety coverage for retained cleanup roots such as `runs/raw` and projected state paths.

### No Old Compatibility Tests

- Add `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_start_does_not_migrate_legacy_shared_workspace_state`
  - Create a legacy file under `${shared_root}/workspace/buddyswitch/objects/tasks/task-legacy.json`.
  - Start a product-mode buddy instance.
  - Assert `${shared_root}/state/buddyswitch/objects/tasks/task-legacy.json` was not created by startup.
  - Assert the launched session still starts normally with empty projected state.
  - This locks the no-migration decision.

- Add or update repo consistency tests to assert removed compatibility surfaces stay removed:
  - `buddyswitch_workspace_migrate_legacy_state_if_needed` is absent.
  - `buddyswitch_cleanup_strip_legacy_runtime_excludes` is absent.
  - Active docs do not advertise `data cleanup --app-runtime`.
  - Active docs do not teach `projects/app/.runtime`.

### Documentation Consistency Tests

- Update `tests/test_repo_consistency.py::RepoConsistencyTests::test_product_mode_docs_define_shared_project_workspace`
  - Assert active docs say product app work uses `projects/app`.
  - Assert active docs do not require users or buddies to type `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`.
  - Assert active docs distinguish runtime workspace from shared product source.

- Add `tests/test_repo_consistency.py::RepoConsistencyTests::test_active_docs_remove_project_app_runtime_cleanup_surface`
  - Assert active docs and console do not contain `data cleanup --app-runtime`.
  - Assert active docs and skill docs do not contain `projects/app/.runtime`.
  - Allow historical docs under `docs/memo/` and older committed specs to remain as history if tests explicitly target only active docs.

## Implementation Tasks

### Task 1: Add Behavior-First Failing Tests

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_cleanup_system.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] Add fake Codex capture fields for `projects/app` existence, resolved path, relative write, and relative read.
- [ ] Add the launcher tests listed in the Detailed Test Plan.
- [ ] Add cleanup rejection and product-source survival tests.
- [ ] Add repo consistency tests for active docs and removed old surfaces.
- [ ] Run the new tests and confirm the main path tests fail for the expected reason: relative `projects/app` still resolves to the instance workspace copy.

Verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_cross_buddy_relative_projects_app_is_shared \
  -q
```

Expected before implementation:

```text
FAILED
```

The failure must show a path mismatch or missing cross-buddy relative file, not a fake-Codex harness error.

### Task 2: Project Shared App Into Runtime Workspace

**Files:**

- Modify: `tools/launcher/workspace.sh`
- Modify: `buddyswitch-codex`

- [ ] Add a launcher helper that removes any instance-local `projects/app` path and creates `projects/app` as a symlink to `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`.
- [ ] Ensure the helper validates both paths stay under `${BUDDYSWITCH_SHARED_ROOT}` before deletion or linking.
- [ ] Call the helper after the execution worktree and shared project worktree are both prepared.
- [ ] Call the same helper from `instance open` so old instance workspaces are repaired.
- [ ] Do not copy or migrate files from the old instance-local app copy.

Verification:

```bash
bash -n buddyswitch-codex tools/launcher/workspace.sh tools/launcher/cleanup.sh
```

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_cross_buddy_relative_projects_app_is_shared \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_repairs_existing_runtime_projects_app_copy \
  -q
```

Expected after Task 2:

```text
3 passed
```

### Task 3: Remove `projects/app/.runtime` Model

**Files:**

- Modify: `tools/launcher/workspace.sh`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_cleanup_system.py`
- Modify: active docs and skill docs listed in File Map

- [ ] Remove `projects/app/.runtime` from runtime output paths.
- [ ] Remove `projects/app/.runtime` from local runtime paths.
- [ ] Remove `projects/app/.runtime` skeleton creation.
- [ ] Remove `projects/app/.runtime/**` local exclude insertion.
- [ ] Remove tests that assert runtime `.runtime` exists.
- [ ] Replace active docs that mention runtime scratch under `projects/app/.runtime` with `runs/raw/`.

Verification:

```bash
rg -n "projects/app/.runtime" \
  README.md AGENTS.md tools/launcher/assets framework/contracts buddyswitch/skills tests/test_buddyswitch_launcher.py tests/test_cleanup_system.py
```

Expected:

```text
no matches
```

Historical docs under `docs/memo/` and older specs can still contain old terms unless the implementation intentionally edits history.

### Task 4: Remove `--app-runtime` Cleanup Surface

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/cleanup.sh`
- Modify: `scripts/env_cleanup.py`
- Modify: `framework/console/app.js`
- Modify: `README.md`
- Modify: `framework/docs/interface-spec.md`
- Modify: `tests/test_cleanup_system.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] Remove `--app-runtime` from CLI help.
- [ ] Remove `--app-runtime` from cleanup parser support.
- [ ] Make `--app-runtime` return a removed-option error.
- [ ] Remove Python cleanup scope branches for `app-runtime`, `project`, and `project_runtime`.
- [ ] Remove console cleanup suggestions for `--app-runtime`.
- [ ] Update tests to expect rejection, not cleanup.

Verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_cleanup_rejects_removed_app_runtime_target \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_data_cleanup_keeps_shared_project_workspace \
  -q
```

Expected:

```text
2 passed
```

### Task 5: Remove Old Compatibility Code

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/workspace.sh`
- Modify: `tools/launcher/cleanup.sh`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] Remove the startup call to `buddyswitch_workspace_migrate_legacy_state_if_needed`.
- [ ] Delete `buddyswitch_workspace_migrate_legacy_state_if_needed`.
- [ ] Delete unused `buddyswitch_cleanup_strip_legacy_runtime_excludes`.
- [ ] Add or update tests proving startup does not migrate old `${BUDDYSWITCH_SHARED_ROOT}/workspace` durable state.
- [ ] Add consistency checks so deleted compatibility helper names do not return.

Verification:

```bash
rg -n "migrate_legacy_state|legacy_runtime_excludes|strip_legacy_runtime_excludes" \
  buddyswitch-codex tools scripts tests README.md AGENTS.md framework
```

Expected:

```text
no matches
```

### Task 6: Update Product Path Documentation

**Files:**

- Modify active docs listed in File Map.
- Modify: `tests/test_repo_consistency.py`

- [ ] State the product-mode user-facing app path as `projects/app`.
- [ ] Keep `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}` only as launcher/debug context, not as the path a buddy must type.
- [ ] Remove statements that tell buddies to edit `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`.
- [ ] Keep the distinction that Codex cwd is a runtime workspace while `projects/app` is projected shared product source.

Verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_product_mode_docs_define_shared_project_workspace \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_docs_remove_project_app_runtime_cleanup_surface \
  -q
```

Expected:

```text
2 passed
```

### Task 7: Full Verification

**Files:**

- No new files.
- Verify all modified surfaces together.

- [ ] Run shell syntax checks.
- [ ] Run targeted launcher tests.
- [ ] Run cleanup tests.
- [ ] Run repo consistency tests.
- [ ] Confirm main checkout is clean.
- [ ] Confirm `.worktrees/dev2230` contains only this task's intended changes.

Commands:

```bash
bash -n buddyswitch-codex tools/launcher/env.sh tools/launcher/workspace.sh tools/launcher/browser_cockpit.sh tools/launcher/cleanup.sh
```

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
```

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py -q
```

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

```bash
git -C /Users/chen/Dev/buddyswitch status --short
git status --short
```

Expected:

- Shell syntax check exits `0`.
- Launcher, cleanup, and repo consistency tests pass.
- Main checkout status is empty.
- dev2230 status shows only the implementation changes for this plan.

## Stop Conditions

- Stop if any new test passes before implementation for the wrong reason, such as fake Codex directly writing `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}` instead of relative `projects/app`.
- Stop if implementing the projection requires changing Codex cwd away from the runtime workspace.
- Stop if cleanup would need to follow `projects/app` into shared product source.
- Stop if any implementation keeps both an instance-local `projects/app` copy and a shared product app path active.

## Definition Of Done

- Every product-mode buddy sees relative `projects/app` as the same shared product app.
- Dev and test buddy workflows can use natural `projects/app` commands without path instructions in SKILL.
- There is no instance-local durable product app copy.
- `projects/app/.runtime` and `data cleanup --app-runtime` are removed from active code, active docs, and active tests.
- Legacy state migration and unused legacy cleanup exclude stripping are removed.
- Full verification commands pass.
- Main checkout remains untouched.
