# Project Workspace Sparse Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `${BUDDYSWITCH_SHARED_ROOT}/project/workspace` a narrow Git-managed product-source worktree that exposes `projects/app/` without exposing BuddySwitch framework source directories.

**Architecture:** Keep the existing launcher contract: product instances run from `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace`, and runtime `projects/app` points to `${BUDDYSWITCH_SHARED_ROOT}/project/workspace/projects/app`. Replace the current full detached project worktree materialization with a sparse, no-cone project worktree whose checkout surface is `projects/app/` only. Existing clean full project worktrees should be narrowed in place; unsafe non-`projects/app` local changes should stop startup instead of being silently deleted.

**Tech Stack:** Bash launcher scripts, Git worktrees, Git sparse checkout, Python `unittest`/`pytest`, fake Codex launcher tests.

---

## Working Directory

Run all implementation and verification from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit the main checkout at `/Users/chen/Dev/buddyswitch`. This plan intentionally targets the `dev0210` worktree.

## Memo Confirmation

The direction memo at `docs/memo/2026-05-08-project-workspace-full-worktree-boundary-memo.md` identifies the current defect as a filesystem boundary problem. Product mode currently creates:

```text
${BUDDYSWITCH_SHARED_ROOT}/project/workspace
```

with:

```bash
git -C "${repo_root}" worktree add --detach "${project_workspace}" HEAD
```

That command materializes a full BuddySwitch repository checkout under a path named as the shared product workspace. Runtime instances then correctly replace their local `projects/app` with a symlink to:

```text
${BUDDYSWITCH_SHARED_ROOT}/project/workspace/projects/app
```

The accepted target is a Git-managed shared product workspace whose visible source surface is:

```text
${BUDDYSWITCH_SHARED_ROOT}/project/workspace/
└── projects/
    └── app/
```

Buddy-facing sessions must still use relative `projects/app`; `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}` remains launcher/debug context, not required buddy input.

## Current Bottleneck

The bottleneck is launcher workspace materialization. Product source sharing and runtime projection already work, but the project workspace is created as a full worktree, which exposes framework directories (`buddyswitch/`, `tools/`, `scripts/`, `tests/`, `framework/`, `docs/`) in the wrong filesystem boundary.

The shortest validated loop is to narrow only the project worktree creation/validation path, then prove that existing runtime projection, cross-buddy shared writes, and cleanup behavior still work.

## Confirmed Facts

- `tools/launcher/workspace.sh` defines `BUDDYSWITCH_PROJECT_WORKSPACE_DIR` as `${BUDDYSWITCH_SHARED_ROOT}/project/workspace`.
- `tools/launcher/workspace.sh::buddyswitch_workspace_force_rebuild_project_worktree` currently runs `git -C "${repo_root}" worktree add --detach "${project_workspace}" HEAD`.
- `tools/launcher/workspace.sh::buddyswitch_workspace_repair_runtime_projects_app_projection` expects `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app` to exist and symlinks runtime `projects/app` to it.
- `buddyswitch-codex` calls `buddyswitch_workspace_ensure_project_worktree` and then `buddyswitch_workspace_repair_runtime_projects_app_projection` during both instance start and instance open.
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace` already captures the runtime cwd, `BUDDYSWITCH_PROJECT_WORKSPACE_DIR`, `projects_app_probe`, and the shared project workspace path.
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app` proves relative writes through runtime `projects/app` land in the shared project app target.
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_cross_buddy_relative_projects_app_is_shared` proves separate buddy launches resolve `projects/app` to the same shared target.
- `tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_data_cleanup_keeps_shared_project_workspace` proves cleanup preserves shared product source paths.
- Local verification showed `git worktree add --detach --no-checkout <path> HEAD` is supported by the installed Git.
- Local verification showed a fresh `--no-checkout` worktree reports non-checked-out files as deleted before `checkout HEAD`; dirty-change detection must run only for existing worktrees, not for freshly created no-checkout worktrees.
- Local verification showed `git sparse-checkout init --cone && git sparse-checkout set projects/app` keeps root files such as `AGENTS.md`, `README.md`, and `buddyswitch-codex`; use `--no-cone` to expose only `projects/app/`.

## Open Assumptions And Invalidators

- Assumption: `projects/app/README.md` is sufficient product-source content for the current repository state. Invalidator: a real product project requires root files for its build tooling; if proven, add those files explicitly to the sparse checkout and update this plan before implementation.
- Assumption: existing full project worktrees are clean outside `projects/app/` because they were launcher-created framework checkouts. Invalidator: `git status --porcelain --untracked-files=all -- . ':(exclude)projects/app/**'` in the project worktree returns entries; startup must stop with a clear message rather than deleting those changes.
- Assumption: no launcher flow needs to execute `buddyswitch-codex`, `tools/`, or `scripts/` from inside `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}`. Invalidator: a focused launcher test fails because a command is run from the project workspace root; fix the caller to use the runtime workspace or repo root rather than expanding project workspace visibility.
- Assumption: the sparse boundary should be enforced at the project worktree layer, not with additional prompt guidance. Invalidator: none expected; the memo explicitly rejects solving this with guidance alone.

## Tools, Permissions, And Boundary Checks

- Use `apply_patch` for file edits.
- Use `rg` for searches.
- Use `git status --short --branch` before and after edits.
- Do not edit launcher-managed runtime data under `${BUDDYSWITCH_SHARED_ROOT}` directly.
- Do not remove or rewrite existing user product files under `${BUDDYSWITCH_SHARED_ROOT}/project/workspace/projects/app`.
- Do not weaken the `projects/app` path contract or buddy access policy.
- Do not add a compatibility layer that lets both full and sparse project worktrees remain valid indefinitely; existing full worktrees should be narrowed or rejected.

## Verification Stop Condition

Stop only when all of these are proven:

- A fresh `./buddyswitch-codex instance start --buddy pm ...` creates a project workspace with `projects/app/README.md`.
- The fresh project workspace does not contain framework directories or root framework files by default: `buddyswitch/`, `tools/`, `scripts/`, `tests/`, `framework/`, `docs/`, `AGENTS.md`, `README.md`, or `buddyswitch-codex`.
- Runtime cwd remains `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace`.
- Runtime `projects/app` resolves to `${BUDDYSWITCH_SHARED_ROOT}/project/workspace/projects/app`.
- Cross-buddy writes through runtime `projects/app` still land in the same shared project source.
- Cleanup still preserves shared project source and still targets runtime state separately.
- Existing clean full project worktrees are narrowed to sparse shape on next start/open.
- Non-`projects/app` dirty changes in an existing project worktree are rejected with a clear diagnostic.
- Focused tests pass and `git diff --check` reports no whitespace errors.

## File Map

Modify:

- `tools/launcher/workspace.sh`: add sparse project worktree helpers, create project worktrees with `--no-checkout`, configure no-cone sparse checkout for `projects/app/`, narrow existing clean full project worktrees in place, and reject unsafe non-product local changes.
- `tests/test_buddyswitch_launcher.py`: strengthen project workspace tests so they assert the sparse boundary, preserve projection behavior, preserve cross-buddy sharing, and cover migration/rejection cases.
- `tests/test_cleanup_system.py`: add a cleanup assertion that shared sparse product source is preserved while runtime state cleanup remains separate.

Do not modify:

- `buddyswitch/env-profiles/*.json`: project access policy is unchanged.
- `tools/launcher/assets/buddies/*/AGENTS.md`: buddy-facing path guidance is already about relative `projects/app`.
- `projects/app/README.md`: this task changes project workspace materialization, not the placeholder content.

## Task 1: Add Project Sparse Boundary Tests For Fresh Startup

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`
- Test: `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace`

- [ ] **Step 1: Run the current focused test to confirm baseline behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace -q
```

Expected before implementation: the test passes today because it does not yet assert that framework directories are absent.

- [ ] **Step 2: Add sparse boundary assertions to the existing test**

In `test_start_with_buddy_creates_shared_project_workspace`, after the placeholder assertions for `project_app_dir`, add:

```python
            forbidden_project_workspace_entries = (
                "buddyswitch",
                "tools",
                "scripts",
                "tests",
                "framework",
                "docs",
                "AGENTS.md",
                "README.md",
                "buddyswitch-codex",
            )
            for entry_name in forbidden_project_workspace_entries:
                self.assertFalse(
                    (project_workspace_dir / entry_name).exists(),
                    msg=f"project workspace must not expose framework entry: {entry_name}",
                )

            sparse_list = subprocess.check_output(
                ["git", "-C", str(project_workspace_dir), "sparse-checkout", "list"],
                text=True,
            ).splitlines()
            self.assertEqual(sparse_list, ["projects/app/"])
```

- [ ] **Step 3: Run the focused test and verify it fails for the current full worktree**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace -q
```

Expected before implementation: failure showing at least one forbidden project workspace entry exists.

## Task 2: Create Project Worktrees As No-Cone Sparse Checkouts

**Files:**

- Modify: `tools/launcher/workspace.sh`
- Test: `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace`

- [ ] **Step 1: Add sparse helper functions after `buddyswitch_workspace_is_valid_project_worktree`**

Add this Bash code:

```bash
buddyswitch_workspace_project_sparse_paths() {
  cat <<'EOF'
projects/app/
EOF
}

buddyswitch_workspace_project_worktree_has_sparse_boundary() {
  local project_workspace="$1"
  local sparse_paths forbidden_entry expected

  git -C "${project_workspace}" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 1
  sparse_paths="$(git -C "${project_workspace}" sparse-checkout list 2>/dev/null || true)"
  expected="$(buddyswitch_workspace_project_sparse_paths)"
  [[ "${sparse_paths}" == "${expected}" ]] || return 1

  for forbidden_entry in \
    buddyswitch \
    tools \
    scripts \
    tests \
    framework \
    docs \
    AGENTS.md \
    README.md \
    buddyswitch-codex; do
    if [[ -e "${project_workspace}/${forbidden_entry}" || -L "${project_workspace}/${forbidden_entry}" ]]; then
      return 1
    fi
  done

  [[ -d "${project_workspace}/projects/app" ]]
}

buddyswitch_workspace_project_worktree_has_dirty_non_project_changes() {
  local project_workspace="$1"
  local status_output

  status_output="$(
    git -C "${project_workspace}" status --porcelain --untracked-files=all -- . ':(exclude)projects/app/**'
  )"
  [[ -n "${status_output}" ]]
}

buddyswitch_workspace_report_dirty_non_project_changes() {
  local project_workspace="$1"

  echo "project workspace has local changes outside projects/app; refusing to narrow sparse checkout" >&2
  echo "project workspace: ${project_workspace}" >&2
  git -C "${project_workspace}" status --short --untracked-files=all -- . ':(exclude)projects/app/**' >&2 || true
}

buddyswitch_workspace_configure_project_sparse_checkout() {
  local project_workspace="$1"
  local mode="${2:-existing}"

  if [[ "${mode}" != "fresh" && "${mode}" != "existing" ]]; then
    echo "unsupported project sparse checkout mode: ${mode}" >&2
    return 2
  fi

  if [[ "${mode}" != "fresh" ]] && buddyswitch_workspace_project_worktree_has_dirty_non_project_changes "${project_workspace}"; then
    buddyswitch_workspace_report_dirty_non_project_changes "${project_workspace}"
    return 3
  fi

  git -C "${project_workspace}" sparse-checkout init --no-cone >/dev/null
  git -C "${project_workspace}" sparse-checkout set --no-cone projects/app/ >/dev/null
  git -C "${project_workspace}" checkout HEAD >/dev/null

  if ! buddyswitch_workspace_project_worktree_has_sparse_boundary "${project_workspace}"; then
    echo "project workspace sparse checkout did not reach expected projects/app boundary" >&2
    echo "project workspace: ${project_workspace}" >&2
    return 1
  fi
}
```

- [ ] **Step 2: Replace full checkout creation in `buddyswitch_workspace_force_rebuild_project_worktree`**

Replace:

```bash
  git -C "${repo_root}" worktree prune >/dev/null 2>&1 || true
  git -C "${repo_root}" worktree add --detach "${project_workspace}" HEAD >/dev/null
```

with:

```bash
  git -C "${repo_root}" worktree prune >/dev/null 2>&1 || true
  git -C "${repo_root}" worktree add --detach --no-checkout "${project_workspace}" HEAD >/dev/null
  buddyswitch_workspace_configure_project_sparse_checkout "${project_workspace}" fresh
```

- [ ] **Step 3: Narrow existing valid full project worktrees in `buddyswitch_workspace_ensure_project_worktree`**

Replace:

```bash
  if buddyswitch_workspace_is_valid_project_worktree; then
    return 0
  fi

  buddyswitch_workspace_force_rebuild_project_worktree
```

with:

```bash
  if buddyswitch_workspace_is_valid_project_worktree; then
    if buddyswitch_workspace_project_worktree_has_dirty_non_project_changes "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"; then
      buddyswitch_workspace_report_dirty_non_project_changes "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"
      return 3
    fi
    if buddyswitch_workspace_project_worktree_has_sparse_boundary "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"; then
      return 0
    fi
    buddyswitch_workspace_configure_project_sparse_checkout "${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"
    return $?
  fi

  buddyswitch_workspace_force_rebuild_project_worktree
```

- [ ] **Step 4: Run the fresh startup test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace -q
```

Expected after implementation: one passing test.

## Task 3: Prove Existing Full Project Worktrees Are Narrowed Safely

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`
- Test: `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_narrows_existing_full_project_worktree`

- [ ] **Step 1: Add a regression test for clean full worktree migration**

Add this test method near the other project workspace tests:

```python
    def test_start_narrows_existing_full_project_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            source_codex_home = source_home_path / ".codex"
            source_codex_home.mkdir(parents=True, exist_ok=True)
            (source_codex_home / "auth.json").write_text(
                json.dumps(
                    {
                        "auth_mode": "apikey",
                        "openai_api_key": "test-key",
                        "tokens": None,
                        "last_refresh": None,
                        "agent_identity": None,
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            shared_root = source_home_path / ".codex-buddyswitch"
            project_workspace_dir = shared_root / "project" / "workspace"
            project_workspace_dir.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(project_workspace_dir), "HEAD"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            self.addCleanup(
                subprocess.run,
                ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(project_workspace_dir)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertTrue((project_workspace_dir / "tools").exists())
            product_sentinel = project_workspace_dir / "projects" / "app" / "migration-sentinel.txt"
            product_sentinel.write_text("preserve\n", encoding="utf-8")

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            capture_path = temp_root_path / "capture.json"
            ready_file = temp_root_path / "browser-ready.flag"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "debug", "prompt-input", "Draft the onboarding PRD"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)

            self.assertFalse((project_workspace_dir / "tools").exists())
            self.assertFalse((project_workspace_dir / "buddyswitch").exists())
            self.assertTrue((project_workspace_dir / "projects" / "app").is_dir())
            self.assertEqual(product_sentinel.read_text(encoding="utf-8"), "preserve\n")
            sparse_list = subprocess.check_output(
                ["git", "-C", str(project_workspace_dir), "sparse-checkout", "list"],
                text=True,
            ).splitlines()
            self.assertEqual(sparse_list, ["projects/app/"])
```

- [ ] **Step 2: Run the migration test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_narrows_existing_full_project_worktree -q
```

Expected after implementation: one passing test. If the sentinel is removed, stop and fix sparse migration before continuing.

## Task 4: Reject Dirty Non-Project Changes Before Narrowing

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`
- Test: `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_rejects_dirty_non_project_project_worktree_before_sparse_narrowing`

- [ ] **Step 1: Add a regression test for dirty non-project changes**

Add this test method near the migration test:

```python
    def test_start_rejects_dirty_non_project_project_worktree_before_sparse_narrowing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            source_codex_home = source_home_path / ".codex"
            source_codex_home.mkdir(parents=True, exist_ok=True)
            (source_codex_home / "auth.json").write_text(
                json.dumps(
                    {
                        "auth_mode": "apikey",
                        "openai_api_key": "test-key",
                        "tokens": None,
                        "last_refresh": None,
                        "agent_identity": None,
                    },
                    ensure_ascii=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            shared_root = source_home_path / ".codex-buddyswitch"
            project_workspace_dir = shared_root / "project" / "workspace"
            project_workspace_dir.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(project_workspace_dir), "HEAD"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            self.addCleanup(
                subprocess.run,
                ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(project_workspace_dir)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            dirty_file = project_workspace_dir / "tools" / "launcher" / "dirty-non-project-change.txt"
            dirty_file.write_text("do not delete silently\n", encoding="utf-8")

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            ready_file = temp_root_path / "browser-ready.flag"
            capture_path = temp_root_path / "capture.json"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_BROWSER_PORT"] = "1"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "debug", "prompt-input", "Draft the onboarding PRD"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("local changes outside projects/app", completed.stderr)
            self.assertTrue(dirty_file.exists())
            self.assertTrue((project_workspace_dir / "tools").exists())
            self.assertFalse(capture_path.exists())
```

- [ ] **Step 2: Run the rejection test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_rejects_dirty_non_project_project_worktree_before_sparse_narrowing -q
```

Expected after implementation: one passing test.

- [ ] **Step 3: Add and run a regression test for already-sparse non-project stray files**

Add `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_rejects_dirty_non_project_file_in_existing_sparse_project_worktree` to prove an already-sparse project worktree with a root-level stray file such as `root-stray.txt` is rejected before buddy execution.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_rejects_dirty_non_project_file_in_existing_sparse_project_worktree -q
```

Expected after implementation: one passing test.

## Task 5: Prove Runtime Projection And Cross-Buddy Sharing Still Work

**Files:**

- Modify: no new files if Task 2 is correct
- Test: existing launcher tests

- [ ] **Step 1: Run focused projection tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_cross_buddy_relative_projects_app_is_shared \
  -q
```

Expected after implementation: two passing tests.

- [ ] **Step 2: If either test fails, inspect only projection logic**

Run:

```bash
rg -n "buddyswitch_workspace_ensure_project_worktree|buddyswitch_workspace_repair_runtime_projects_app_projection|projects_app_probe|relative_probe" buddyswitch-codex tools/launcher/workspace.sh tests/test_buddyswitch_launcher.py
```

Expected investigation boundary: fix sparse setup or projection ordering only. Do not change buddy access policy or replace the runtime `projects/app` symlink contract.

## Task 6: Strengthen Cleanup Preservation Around Sparse Product Source

**Files:**

- Modify: `tests/test_cleanup_system.py`
- Test: `tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_data_cleanup_keeps_shared_project_workspace`

- [ ] **Step 1: Add a framework-directory sentinel to the existing cleanup test**

In `test_shell_all_data_cleanup_keeps_shared_project_workspace`, after creating `sentinel_path`, add:

```python
        framework_residue_path = self.shared_root / "project" / "workspace" / "tools" / "launcher" / "should-not-exist.txt"
        self.assertFalse(framework_residue_path.exists())
```

Keep the existing product sentinel assertions unchanged.

- [ ] **Step 2: Run the cleanup test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_data_cleanup_keeps_shared_project_workspace -q
```

Expected after implementation: one passing test.

## Task 7: Run The Focused Regression Suite

**Files:**

- Verify: `tools/launcher/workspace.sh`
- Verify: `tests/test_buddyswitch_launcher.py`
- Verify: `tests/test_cleanup_system.py`

- [ ] **Step 1: Run the sparse boundary launcher suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_narrows_existing_full_project_worktree \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_rejects_dirty_non_project_project_worktree_before_sparse_narrowing \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_rejects_dirty_non_project_file_in_existing_sparse_project_worktree \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_mode_projects_app_resolves_to_shared_project_app \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_cross_buddy_relative_projects_app_is_shared \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_data_cleanup_keeps_shared_project_workspace \
  -q
```

Expected result: all selected tests pass.

- [ ] **Step 2: Run existing repo/project-source consistency checks**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_projects_app_is_framework_placeholder_only \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_browser_ui_does_not_import_runtime_internals \
  -q
```

Expected result: both selected tests pass.

- [ ] **Step 3: Run shell formatting and diff checks**

Run:

```bash
git diff --check
git status --short
```

Expected result: `git diff --check` prints no errors. `git status --short` shows only intentional changes for this task plus any pre-existing unrelated untracked memo files.

## Self-Review Rubric

Before declaring implementation complete, answer these directly:

- Root cause: does `project/workspace` stop being created as a visible full framework checkout?
- Boundary: does runtime `projects/app` still resolve to shared product source?
- Migration: does a clean existing full project worktree narrow in place without losing `projects/app` files?
- Safety: does a dirty non-project project worktree, including an already-sparse worktree with arbitrary root stray files, stop before deleting local changes?
- Scope: did changes stay limited to project workspace materialization/tests?
- Verification: do focused launcher, cleanup, and repo consistency tests prove the claimed behavior?
