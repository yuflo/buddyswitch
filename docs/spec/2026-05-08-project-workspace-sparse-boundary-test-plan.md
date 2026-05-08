# Project Workspace Sparse Boundary Test Plan

**Goal:** Verify from functional requirements that product-mode BuddySwitch exposes shared product source through `projects/app` while keeping `${BUDDYSWITCH_SHARED_ROOT}/project/workspace` from looking like a second BuddySwitch framework checkout.

**Testing Principle:** Tests must start from observable product-mode behavior: launcher-created filesystem shape, runtime cwd, `projects/app` projection, cross-buddy shared source behavior, cleanup preservation, and user-data safety. Do not write tests that merely exercise a private helper or check for a specific implementation branch while allowing a full framework checkout to remain visible.

---

## Functional Requirements Under Test

FR1. Product-mode instances run from `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace`, not from `${BUDDYSWITCH_SHARED_ROOT}/project/workspace`.

FR2. Buddy-facing product source remains relative `projects/app` inside the runtime workspace.

FR3. Runtime `projects/app` resolves to `${BUDDYSWITCH_SHARED_ROOT}/project/workspace/projects/app`.

FR4. `${BUDDYSWITCH_SHARED_ROOT}/project/workspace` remains Git-managed so product source edits are not unmanaged copies.

FR5. A fresh product workspace exposes `projects/app/` and does not expose framework implementation directories by default.

FR6. A fresh product workspace does not expose framework root files by default unless a future product-source requirement explicitly adds them.

FR7. Git sparse checkout configuration for the product workspace includes `projects/app/` as the visible product-source path.

FR8. Cross-buddy writes and reads through runtime `projects/app` land in the same shared product source.

FR9. Existing clean full project worktrees are narrowed to the new product-only surface on the next start/open.

FR10. Existing product source files under `project/workspace/projects/app` survive narrowing.

FR11. Existing local changes outside `projects/app/` in the project workspace are not silently deleted during narrowing.

FR12. Cleanup commands preserve shared product source under `project/workspace/projects/app` and continue targeting runtime state separately.

FR13. The implementation does not change buddy access policy: Dev remains the write-capable product-source buddy, and non-Dev buddies remain read-only by profile/guidance.

FR14. Tests must detect the concrete boundary failure that motivated the task: a product workspace containing `buddyswitch/`, `tools/`, `scripts/`, `tests/`, `framework/`, or `docs/` must fail.

## Coverage Matrix

| Requirement | Test Group | Observable Proof |
| --- | --- | --- |
| FR1, FR2, FR3 | TG-01, TG-03 | Fake Codex capture shows runtime cwd and `projects_app_probe.resolved` |
| FR4, FR7 | TG-02 | Project workspace is a Git worktree and sparse checkout list is `projects/app/` |
| FR5, FR6, FR14 | TG-02 | Filesystem assertions reject framework dirs and root framework files |
| FR8 | TG-04 | Two buddy launches share one resolved product source and sentinel content |
| FR9, FR10 | TG-05 | Pre-existing full worktree is narrowed and product sentinel remains |
| FR11 | TG-06 | Dirty non-project file blocks startup and remains on disk |
| FR12 | TG-07 | Cleanup leaves product source sentinel and does not delete project app paths |
| FR13 | TG-08 | Existing env/profile/runtime tests still pass |

## Test Data Rules

- Use temporary `HOME` directories for launcher integration tests so no user runtime state is touched.
- Use fake `codex`, fake `curl`, and fake Chrome helpers already present in `tests/test_buddyswitch_launcher.py`.
- Use neutral sentinel names such as `shared-product-sentinel.txt`, `relative-path-sentinel.txt`, `cross-buddy-sentinel.txt`, and `migration-sentinel.txt`.
- Do not create tracked app fixtures under repo `projects/app` to make the tests pass.
- Do not satisfy boundary tests by hiding framework directories with prompt guidance; the filesystem shape itself must prove the boundary.
- Do not allow tests to pass if `project/workspace` still contains a full checkout but the helper reports success.

## TG-01 Runtime Workspace Contract

**Purpose:** Prove product-mode Codex still starts in the instance runtime workspace and sees `projects/app` as the product-source path.

**Functional risk covered:** Narrowing the project workspace could accidentally change Codex cwd, make buddies operate from the project workspace root, or break the relative `projects/app` contract.

**Primary test location:**

```text
tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace
```

**Flow:**

1. Start a PM product-mode instance with a temporary `HOME`.
2. Use the existing fake Codex capture payload.
3. Resolve `shared_root`, `instance_root`, `runtime_workspace_dir`, and `project_workspace_dir`.

**Assertions:**

- `payload["cwd"]` equals the runtime workspace path.
- `payload["cwd"]` does not equal the project workspace path.
- `payload["project_workspace_dir"]` equals `${temporary_home}/.codex-buddyswitch/project/workspace`.
- `payload["projects_app_probe"]["exists"]` is true.
- `payload["projects_app_probe"]["resolved"]` equals `${project_workspace_dir}/projects/app` resolved.
- `${project_workspace_dir}/projects/app/.runtime` does not exist.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace -q
```

**Expected result:** one passing test.

**Anti-cheat check:** The test must inspect the fake Codex runtime payload, not only the repository checkout or a launcher helper return code.

## TG-02 Fresh Project Workspace Boundary

**Purpose:** Prove a newly created shared project workspace exposes only product source and not BuddySwitch framework source.

**Functional risk covered:** The original bug is a full framework checkout under `project/workspace`; this test must fail if that shape returns.

**Primary test location:**

```text
tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace
```

**Assertions:**

- `${project_workspace_dir}` exists.
- `${project_workspace_dir}/projects/app` is a directory.
- `${project_workspace_dir}/projects/app/README.md` exists and contains `BuddySwitch runtime mount point`.
- `${project_workspace_dir}` is a Git worktree sharing the repository common git dir.
- `git -C "${project_workspace_dir}" sparse-checkout list` returns exactly:

```text
projects/app/
```

- These paths do not exist under `${project_workspace_dir}`:

```text
buddyswitch
tools
scripts
tests
framework
docs
AGENTS.md
README.md
buddyswitch-codex
```

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace -q
```

**Expected result:** one passing test.

**Anti-cheat check:** Do not replace this with a test that only checks `projects/app` exists. The failure mode is extra framework visibility, so absence of framework entries is required evidence.

## TG-03 Relative `projects/app` Projection

**Purpose:** Prove runtime `projects/app` is still a live projection to shared product source after narrowing.

**Functional risk covered:** Sparse worktree setup could leave `${project_workspace_dir}/projects/app` missing, causing runtime projection repair to fail or point to a local runtime directory.

**Primary test location:**

```text
tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app
```

**Flow:**

1. Start a PM instance with `BUDDYSWITCH_TEST_RELATIVE_WRITE_PATH=relative-path-sentinel.txt`.
2. Fake Codex writes through relative `projects/app/relative-path-sentinel.txt`.
3. Test reads the capture payload and shared project app target.

**Assertions:**

- Runtime cwd equals the instance workspace.
- `payload["project_workspace_dir"]` equals the shared project workspace.
- `projects_app_probe.resolved` equals `${shared_project_workspace}/projects/app`.
- The relative write succeeds.
- The resolved write path is `${shared_project_workspace}/projects/app/relative-path-sentinel.txt`.
- The sentinel file exists at the shared product source target.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app -q
```

**Expected result:** one passing test.

**Anti-cheat check:** The write must go through runtime relative `projects/app`, not directly to `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}`.

## TG-04 Cross-Buddy Shared Product Source

**Purpose:** Prove two buddy instances continue to share the same product source through `projects/app`.

**Functional risk covered:** Narrowing the project worktree must not make each instance receive a separate product source copy.

**Primary test location:**

```text
tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_cross_buddy_relative_projects_app_is_shared
```

**Flow:**

1. Start a PM instance that writes `projects/app/cross-buddy-sentinel.txt`.
2. Start a Dev instance in the same temporary launcher home that reads `projects/app/cross-buddy-sentinel.txt`.
3. Compare both fake Codex captures.

**Assertions:**

- PM and Dev `projects_app_probe.resolved` values both equal the same `${shared_root}/project/workspace/projects/app`.
- PM write path resolves under the shared project app target.
- Dev read path resolves under the same shared project app target.
- Dev reads the exact content written by PM.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_cross_buddy_relative_projects_app_is_shared -q
```

**Expected result:** one passing test.

**Anti-cheat check:** Do not assert only that both instances have a `projects/app` path; the resolved target and sentinel content must be shared.

## TG-05 Existing Full Worktree Migration

**Purpose:** Prove a clean existing full project worktree is narrowed in place on next start/open without deleting product source under `projects/app`.

**Functional risk covered:** Users may already have a full launcher-created project workspace. A correct fix should not require manual deletion and should not lose product files.

**New test location:**

```text
tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_narrows_existing_full_project_worktree
```

**Flow:**

1. Create a temporary shared root.
2. Before launcher start, manually create `${shared_root}/project/workspace` with `git worktree add --detach`.
3. Confirm a framework directory such as `tools/` exists in that full worktree.
4. Write `${project_workspace_dir}/projects/app/migration-sentinel.txt`.
5. Start a PM instance with the same temporary `HOME`.

**Assertions:**

- Startup succeeds.
- Framework directories such as `tools/` and `buddyswitch/` no longer exist under `${project_workspace_dir}`.
- `${project_workspace_dir}/projects/app` remains a directory.
- `migration-sentinel.txt` still exists and still contains `preserve\n`.
- `git -C "${project_workspace_dir}" sparse-checkout list` returns exactly `projects/app/`.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_narrows_existing_full_project_worktree -q
```

**Expected result:** one passing test.

**Anti-cheat check:** Do not satisfy this by deleting and recreating the whole project workspace; the product sentinel under `projects/app` must survive.

## TG-06 Dirty Non-Project Change Safety

**Purpose:** Prove narrowing refuses to delete local changes outside `projects/app`.

**Functional risk covered:** Some user or tool may have edited the wrong root inside the old full project worktree. The boundary cleanup should not silently destroy those edits.

**New test location:**

```text
tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_rejects_dirty_non_project_project_worktree_before_sparse_narrowing
tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_rejects_dirty_non_project_file_in_existing_sparse_project_worktree
```

**Flow for full-worktree narrowing safety:**

1. Create a temporary full project worktree under `${shared_root}/project/workspace`.
2. Write a dirty file outside `projects/app`, such as `tools/launcher/dirty-non-project-change.txt`.
3. Start a PM instance with the same temporary `HOME`.

**Flow for already-sparse boundary safety:**

1. Start a PM instance with a temporary `HOME` to create a valid sparse project worktree.
2. Write a dirty file outside `projects/app`, such as `${project_workspace}/root-stray.txt`.
3. Start a second PM instance with the same temporary `HOME`.

**Assertions:**

- Startup fails.
- `stderr` contains `local changes outside projects/app`.
- The dirty file still exists.
- The full-worktree case still has its framework directory, proving narrowing did not partially delete it.
- The already-sparse case still reports sparse checkout list `projects/app/`, proving the rejection covers sparse early-return paths.
- Fake Codex capture does not exist, proving startup stopped before buddy execution.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_rejects_dirty_non_project_project_worktree_before_sparse_narrowing -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_rejects_dirty_non_project_file_in_existing_sparse_project_worktree -q
```

**Expected result:** one passing test.

**Anti-cheat check:** Do not hide this failure with `rm -rf` or `git clean`; the requirement is to preserve unexpected non-project local changes and ask for cleanup.

## TG-07 Cleanup Preservation

**Purpose:** Prove shared product source remains outside runtime state cleanup.

**Functional risk covered:** The sparse product workspace must remain product source, not runtime state. Cleanup should not erase product files under `project/workspace/projects/app`.

**Primary test location:**

```text
tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_data_cleanup_keeps_shared_project_workspace
```

**Flow:**

1. Create `${shared_root}/project/workspace/projects/app/product-source-sentinel.txt`.
2. Run `./buddyswitch-codex data cleanup --all-data --yes --json` through the existing cleanup test harness.
3. Inspect the JSON deleted path list.

**Assertions:**

- Product sentinel still exists.
- Deleted paths do not include `project/workspace/projects/app/product-source-sentinel.txt`.
- Deleted paths do not include any prefix under `project/workspace/projects/app/`.
- The test does not need framework directories under `project/workspace` to exist.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_data_cleanup_keeps_shared_project_workspace -q
```

**Expected result:** one passing test.

**Anti-cheat check:** Do not change cleanup to preserve the whole full checkout as a workaround. Cleanup preservation only needs shared product source, not framework residue.

## TG-08 Access Policy Regression

**Purpose:** Prove sparse workspace cleanup does not redesign buddy capabilities.

**Functional risk covered:** The task is a filesystem boundary cleanup; it must not change Dev/non-Dev access semantics to make tests pass.

**Existing coverage to run:**

```text
tests/test_prepare_runtime_context.py
tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app
```

**Assertions covered by existing tests:**

- Runtime context reports `projects/app` as the product path.
- Dev remains the write-capable project-source buddy.
- PM, Market, Design, and Test retain read-only project access in profiles/guidance.
- Runtime projection still resolves to shared product source.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app \
  -q
```

**Expected result:** all selected tests pass.

**Anti-cheat check:** Do not edit `buddyswitch/env-profiles/*.json` or buddy AGENTS templates to compensate for sparse checkout failures.

## TG-09 Manual Main-Path Filesystem Probe

**Purpose:** Provide one human-readable filesystem proof after automated tests pass.

**Functional risk covered:** A unit test can miss visible filesystem artifacts if it checks only captured payload fields.

**Command:**

```bash
tmp_home="$(mktemp -d "${TMPDIR:-/tmp}/buddyswitch-sparse-boundary-home.XXXXXX")"
HOME="${tmp_home}" ./buddyswitch-codex instance start --buddy pm debug prompt-input "Confirm sparse project workspace boundary"
find "${tmp_home}/.codex-buddyswitch/project/workspace" -maxdepth 2 -mindepth 1 -print | sort
git -C "${tmp_home}/.codex-buddyswitch/project/workspace" sparse-checkout list
```

**Expected filesystem output shape:**

```text
.../.codex-buddyswitch/project/workspace/projects
.../.codex-buddyswitch/project/workspace/projects/app
```

**Expected sparse list output:**

```text
projects/app/
```

**Cleanup command:**

```bash
HOME="${tmp_home}" ./buddyswitch-codex env reset --yes
rm -rf "${tmp_home}"
```

**Anti-cheat check:** If `find` shows `tools`, `buddyswitch`, `framework`, `tests`, `docs`, `AGENTS.md`, `README.md`, or `buddyswitch-codex`, the requirement is not met even if `projects/app` works.

## Combined Verification Suite

Run this focused suite before marking the task complete:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_narrows_existing_full_project_worktree \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_rejects_dirty_non_project_project_worktree_before_sparse_narrowing \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_rejects_dirty_non_project_file_in_existing_sparse_project_worktree \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_cross_buddy_relative_projects_app_is_shared \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_data_cleanup_keeps_shared_project_workspace \
  tests/test_prepare_runtime_context.py \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_projects_app_is_framework_placeholder_only \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_browser_ui_does_not_import_runtime_internals \
  -q
```

Expected result: all selected tests pass.

Then run:

```bash
git diff --check
git status --short
```

Expected result: no whitespace errors. Status should show only intentional changes for the sparse boundary task plus any pre-existing unrelated untracked memo files.

## Failure Triage

- If `projects/app` is missing, inspect project worktree sparse setup before inspecting runtime symlink repair.
- If runtime `projects/app` resolves to the instance workspace, inspect `buddyswitch_workspace_repair_runtime_projects_app_projection`.
- If root files such as `AGENTS.md` or `README.md` appear, confirm the implementation is using `sparse-checkout --no-cone`, not cone mode.
- If product sentinel files under `projects/app` disappear during migration, stop and fix migration before running broader tests.
- If dirty non-project files are deleted, revert that implementation path; deletion is explicitly outside the safety contract.
- If cleanup deletes `project/workspace/projects/app`, fix cleanup target calculation; do not move product source into runtime state.
