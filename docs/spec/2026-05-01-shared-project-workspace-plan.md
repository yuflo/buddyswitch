# Shared Project Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make BuddySwitch product-mode buddies collaborate on one shared project source workspace while keeping each instance workspace runtime-only.

**Architecture:** Keep `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace` as the per-instance runtime workspace for BuddySwitch control flow, buddy lock, state projections, raw dumps, and `projects/app/.runtime`. Add one shared project worktree per shared root at `${BUDDYSWITCH_SHARED_ROOT}/project/workspace`, expose it to every product-mode session as `BUDDYSWITCH_PROJECT_WORKSPACE_DIR`, and document that durable product edits belong under `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`. This is a forward replacement for instance-local product source work, with no automatic migration from old instance workspaces and no track-level workspace layer.

**Tech Stack:** Bash launcher helpers, Git worktrees, per-instance Codex environment, Python test harnesses, `pytest` integration and consistency tests.

---

## Scope

In scope:

- Add a shared project worktree under `${BUDDYSWITCH_SHARED_ROOT}/project/workspace`.
- Expose the shared project worktree to product-mode Codex sessions with `BUDDYSWITCH_PROJECT_WORKSPACE_DIR`.
- Keep `BUDDYSWITCH_WORKSPACE_DIR` as the instance runtime workspace.
- Keep `runs/raw/` and `projects/app/.runtime/` instance-local.
- Keep canonical BuddySwitch state in `${BUDDYSWITCH_SHARED_ROOT}/state` and projected into runtime workspaces.
- Ensure multiple buddies see the same project workspace path and can read/write the same durable project files.
- Ensure `instance delete` removes only the target instance root and does not delete the shared project workspace.
- Ensure `env reset --yes` removes the shared project worktree registration before deleting the shared root.
- Update runtime guidance so agents use the shared project workspace for durable product code edits.

Out of scope:

- Track-level project worktrees.
- Branch orchestration, merge queues, or workflow engines.
- Automatic migration of product edits from existing instance workspaces.
- Long-lived compatibility for old instance-local product source edits.
- Making `projects/app/.runtime` shared.
- Changing BuddySwitch state authority, task/artifact/run persistence, or cleanup semantics beyond guarding product source from data cleanup.

## Current Facts From Code

- `buddyswitch_env_bind_instance` sets `BUDDYSWITCH_WORKSPACE_DIR` to `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace`.
- `instance start` and `instance open` run Codex from `BUDDYSWITCH_WORKSPACE_DIR`.
- Runtime workspace state projections already follow the shared-area model: `buddyswitch/objects/**` and `buddyswitch/content/runs/**` point into `${BUDDYSWITCH_SHARED_ROOT}/state`.
- `runs/raw/` and `projects/app/.runtime/` are created as local runtime paths inside each instance workspace.
- Runtime workspace hooks block commit, rebase, and push from instance workspaces.
- `env reset --yes` already removes registered worktrees under `${BUDDYSWITCH_SHARED_ROOT}` before deleting the shared root.
- Codex automation config already grants `${BUDDYSWITCH_SHARED_ROOT}` as a writable root, so a project worktree under that root stays inside the existing sandbox boundary.

## Design Decisions

- The shared project workspace path is `${BUDDYSWITCH_SHARED_ROOT}/project/workspace`.
- `BUDDYSWITCH_PROJECT_WORKSPACE_DIR` is always exported for product-mode sessions.
- `BUDDYSWITCH_WORKSPACE_DIR` does not change meaning.
- The launcher creates or repairs the shared project workspace with a detached Git worktree at the current launcher `HEAD`.
- The launcher does not move, copy, or reconcile existing product edits from instance workspaces.
- The runtime workspace remains the Codex cwd for now. This preserves buddy-specific `AGENTS.md`, runtime state projections, and `switch_runtime.py` write protection.
- Durable product edit guidance must name `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app` explicitly.
- Tests must verify user-visible CLI behavior and filesystem effects, not private helper return values.

## File Map

- Modify: `tools/launcher/workspace.sh`
  - Define `BUDDYSWITCH_PROJECT_WORKSPACE_DIR`.
  - Validate the project workspace is under `${BUDDYSWITCH_SHARED_ROOT}` and outside reserved launcher runtime roots.
  - Ensure the shared project worktree exists before launching product-mode Codex.

- Modify: `buddyswitch-codex`
  - Ensure `instance start` and `instance open` bootstrap the shared project worktree.
  - Print the project workspace path when starting a buddy instance.
  - Keep Codex cwd as the instance runtime workspace.

- Modify: `tests/test_buddyswitch_launcher.py`
  - Extend the fake Codex capture to record `BUDDYSWITCH_PROJECT_WORKSPACE_DIR`.
  - Add CLI integration tests proving shared project workspace creation, cross-buddy sharing, instance delete preservation, and reset cleanup.

- Modify: `tests/test_cleanup_system.py`
  - Add a guard test proving data cleanup does not delete shared project source.

- Modify: `tools/launcher/assets/runtime-AGENTS.md`
  - Add the product source placement rule.

- Modify: `tools/launcher/assets/buddies/pm/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/dev/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/design/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/market/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/test/AGENTS.md`
  - Add the same durable product edit rule while preserving buddy lock language.

- Modify: `README.md`
  - Document runtime workspace versus shared project workspace.
  - Replace any wording that implies durable product source edits belong inside instance workspaces.

- Modify: `AGENTS.md`
  - Document the new shared product work surface as repository-level execution guidance.

- Modify: `tests/test_repo_consistency.py`
  - Lock the documented path contract and prevent future docs from teaching instance-local product source edits.

## Testing Principles

Tests must start from product behavior:

- A buddy session launched through `./buddyswitch-codex instance start --buddy <buddy>` gets a shared project workspace.
- A second buddy session sees the same shared project workspace and can read a file written by the first session.
- The runtime workspace stays per-instance and keeps instance-local scratch.
- Instance deletion does not delete shared project source.
- Environment reset removes all launcher-managed roots, including the shared project worktree registration.
- Data cleanup never removes durable product source.

Tests must not cheat:

- Do not test a private helper as the primary proof.
- Do not assert that a specific helper function was called.
- Do not construct assertions around implementation-only names except the public environment contract `BUDDYSWITCH_PROJECT_WORKSPACE_DIR`.
- Use fake Codex only as the launched process that observes environment, cwd, and filesystem behavior after the public CLI starts it.
- Verify actual files and Git worktree state on disk.

## Detailed Test Plan

Primary regression tests:

- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace`
  - Launch `./buddyswitch-codex instance start --buddy pm` with fake Codex.
  - Assert fake Codex cwd is still the instance runtime workspace.
  - Assert fake Codex sees `BUDDYSWITCH_PROJECT_WORKSPACE_DIR`.
  - Assert the path equals `${shared_root}/project/workspace`.
  - Assert the shared project workspace is a valid Git worktree with the same common Git dir as the source repo.
  - Assert `${project_workspace}/projects/app/index.html`, `main.js`, and `styles.css` exist.
  - Assert runtime `projects/app/.runtime` exists inside the instance workspace and is not a symlink.
  - Assert `${project_workspace}/projects/app/.runtime` does not exist after startup.
  - Expected red result before implementation: missing `BUDDYSWITCH_PROJECT_WORKSPACE_DIR` in fake Codex capture or missing `${shared_root}/project/workspace`.

- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_project_workspace_is_shared_across_buddy_instances`
  - Launch `pm` with fake Codex configured to write a sentinel file to `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app/shared-product-sentinel.txt`.
  - Remove active browser markers and launcher state required by the test harness.
  - Launch `dev` with fake Codex configured to read the same sentinel file.
  - Assert both sessions report the same `BUDDYSWITCH_PROJECT_WORKSPACE_DIR`.
  - Assert the dev capture contains the sentinel content written by pm.
  - Assert neither runtime workspace contains the sentinel under `instances/<id>/workspace/projects/app/shared-product-sentinel.txt`.
  - Expected red result before implementation: fake Codex has no project workspace env var or writes into no shared path.

- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_keeps_shared_project_workspace`
  - Launch a `pm` instance and create `${project_workspace}/projects/app/delete-survival-sentinel.txt`.
  - Stop active test browser markers.
  - Run `./buddyswitch-codex instance delete <instance-id> --yes`.
  - Assert the target instance root is gone.
  - Assert `${project_workspace}/projects/app/delete-survival-sentinel.txt` still exists.
  - Assert `git worktree list --porcelain` still includes the project workspace.
  - Expected red result before implementation: no project workspace exists to survive deletion.

- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_reset_removes_shared_project_worktree_registration`
  - Launch a `pm` instance.
  - Capture `BUDDYSWITCH_PROJECT_WORKSPACE_DIR`.
  - Stop active test browser markers.
  - Run `./buddyswitch-codex env reset --yes`.
  - Assert `${shared_root}` no longer exists.
  - Assert `git worktree list --porcelain` does not include the old project workspace path.
  - Expected red result before implementation: no project workspace path is captured.

- `tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_data_cleanup_keeps_shared_project_workspace`
  - Create a realistic shared project workspace path under the test shared root: `project/workspace/projects/app`.
  - Write `project/workspace/projects/app/product-source-sentinel.txt`.
  - Run `./buddyswitch-codex data cleanup --all-data --yes --json`.
  - Assert cleanup succeeds.
  - Assert the product source sentinel still exists.
  - Assert `deleted_paths` does not contain `project/workspace/projects/app/product-source-sentinel.txt`.
  - This is a guard test. It may pass before implementation because current cleanup does not know that path, but it protects the product-source boundary once the launcher starts creating the path.

- `tests/test_repo_consistency.py::RepoConsistencyTests::test_product_mode_docs_define_shared_project_workspace`
  - Assert README, root AGENTS, runtime AGENTS, and buddy AGENTS mention `BUDDYSWITCH_PROJECT_WORKSPACE_DIR`.
  - Assert they mention `${BUDDYSWITCH_SHARED_ROOT}/project/workspace`.
  - Assert docs distinguish instance runtime workspace from shared project workspace.
  - Assert docs do not say durable product source edits belong in `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace/projects/app`.
  - Expected red result before documentation updates: missing `BUDDYSWITCH_PROJECT_WORKSPACE_DIR`.

Verification commands:

```bash
bash -n buddyswitch-codex tools/launcher/env.sh tools/launcher/workspace.sh tools/launcher/browser_cockpit.sh tools/launcher/cleanup.sh
```

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_project_workspace_is_shared_across_buddy_instances \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_keeps_shared_project_workspace \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_reset_removes_shared_project_worktree_registration \
  -q
```

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_data_cleanup_keeps_shared_project_workspace \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_product_mode_docs_define_shared_project_workspace \
  -q
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

Stop condition:

- All commands above pass.
- New tests prove cross-buddy sharing through public launcher commands and filesystem state.
- Main checkout remains untouched; all changes stay in `.worktrees/dev2230`.

## Task 1: Add Shared Project Workspace Capture To Test Harness

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Extend fake Codex capture**

Modify `_write_fake_codex()` so every captured payload includes the project workspace env var and optional product sentinel read/write behavior:

```python
entry = {
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "home": os.environ.get("HOME"),
    "codex_home": os.environ.get("CODEX_HOME"),
    "xdg_config_home": os.environ.get("XDG_CONFIG_HOME"),
    "active_buddy": os.environ.get("BUDDYSWITCH_ACTIVE_BUDDY"),
    "instance_id": os.environ.get("BUDDYSWITCH_INSTANCE_ID"),
    "instance_json": os.environ.get("BUDDYSWITCH_INSTANCE_JSON"),
    "project_workspace_dir": os.environ.get("BUDDYSWITCH_PROJECT_WORKSPACE_DIR"),
}

product_probe = None
project_workspace_dir = entry["project_workspace_dir"]
product_write = os.environ.get("BUDDYSWITCH_TEST_PRODUCT_WRITE")
product_read = os.environ.get("BUDDYSWITCH_TEST_PRODUCT_READ")
if project_workspace_dir and product_write:
    product_path = Path(project_workspace_dir) / "projects" / "app" / "shared-product-sentinel.txt"
    product_path.parent.mkdir(parents=True, exist_ok=True)
    product_path.write_text(product_write + "\n", encoding="utf-8")
    product_probe = {"path": str(product_path), "content": product_path.read_text(encoding="utf-8").strip()}
elif project_workspace_dir and product_read:
    product_path = Path(project_workspace_dir) / "projects" / "app" / "shared-product-sentinel.txt"
    product_probe = {
        "path": str(product_path),
        "exists": product_path.exists(),
        "content": product_path.read_text(encoding="utf-8").strip() if product_path.exists() else None,
    }
```

Then include `product_probe` in the final `payload`:

```python
payload = {
    **entry,
    "launch_count": launch_count,
    "config_toml": (codex_home / "config.toml").read_text(encoding="utf-8"),
    "auth_json": json.loads((codex_home / "auth.json").read_text(encoding="utf-8")),
    "instance_json_payload": instance_payload,
    "product_probe": product_probe,
}
```

- [ ] **Step 2: Run a narrow existing launcher test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_wires_instance_env_and_lifecycle -q
```

Expected:

```text
1 passed
```

This harness-only step must not change launcher behavior.

## Task 2: Add Public CLI Tests For Shared Project Workspace Creation

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add a failing test for project workspace creation**

Add this test near `test_start_with_buddy_wires_instance_env_and_lifecycle`:

```python
    def test_start_with_buddy_creates_shared_project_workspace(self) -> None:
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
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "debug", "prompt-input", "edit app"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            instance_root = shared_root / "instances" / payload["instance_id"]
            runtime_workspace = instance_root / "workspace"
            project_workspace = shared_root / "project" / "workspace"

            self.assertEqual(payload["cwd"], str(runtime_workspace.resolve()))
            self.assertEqual(payload["project_workspace_dir"], str(project_workspace))
            self.assertTrue(project_workspace.is_dir())
            self.assertTrue((project_workspace / "projects" / "app" / "index.html").is_file())
            self.assertTrue((project_workspace / "projects" / "app" / "main.js").is_file())
            self.assertTrue((project_workspace / "projects" / "app" / "styles.css").is_file())
            self.assertTrue((runtime_workspace / "projects" / "app" / ".runtime").is_dir())
            self.assertFalse((runtime_workspace / "projects" / "app" / ".runtime").is_symlink())
            self.assertFalse((project_workspace / "projects" / "app" / ".runtime").exists())

            project_common_raw = subprocess.check_output(
                ["git", "-C", str(project_workspace), "rev-parse", "--git-common-dir"],
                text=True,
            ).strip()
            project_common = Path(project_common_raw)
            if not project_common.is_absolute():
                project_common = project_workspace / project_common
            repo_common = self._repo_git_common_dir()
            self.assertEqual(project_common.resolve(strict=False), repo_common)
```

- [ ] **Step 2: Run the new test and verify red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace -q
```

Expected:

```text
FAILED
```

The expected failure is missing `payload["project_workspace_dir"]` or missing `${shared_root}/project/workspace`.

## Task 3: Add Cross-Buddy Product Sharing Test

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add the cross-buddy test**

Add this test near the project workspace creation test:

```python
    def test_project_workspace_is_shared_across_buddy_instances(self) -> None:
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

            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            base_env = os.environ.copy()
            base_env["HOME"] = str(source_home_path)
            base_env.pop("CODEX_HOME", None)
            base_env["PATH"] = f"{fake_bin}{os.pathsep}{base_env.get('PATH', '')}"
            base_env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")

            pm_capture = temp_root_path / "pm-capture.json"
            pm_env = base_env.copy()
            pm_env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "pm-browser-ready.flag")
            pm_env["BUDDYSWITCH_TEST_CAPTURE"] = str(pm_capture)
            pm_env["BUDDYSWITCH_TEST_PRODUCT_WRITE"] = "written by pm"
            pm_result = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "debug", "prompt-input", "edit app"],
                cwd=ROOT,
                env=pm_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(pm_result.returncode, 0, msg=pm_result.stderr)
            pm_payload = json.loads(pm_capture.read_text(encoding="utf-8"))
            pm_instance_root = source_home_path / ".codex-buddyswitch" / "instances" / pm_payload["instance_id"]
            (pm_instance_root / "browser" / "chrome.pid").unlink(missing_ok=True)

            dev_capture = temp_root_path / "dev-capture.json"
            dev_env = base_env.copy()
            dev_env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "dev-browser-ready.flag")
            dev_env["BUDDYSWITCH_TEST_CAPTURE"] = str(dev_capture)
            dev_env["BUDDYSWITCH_TEST_PRODUCT_READ"] = "1"
            dev_result = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "dev", "debug", "prompt-input", "inspect app"],
                cwd=ROOT,
                env=dev_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(dev_result.returncode, 0, msg=dev_result.stderr)
            dev_payload = json.loads(dev_capture.read_text(encoding="utf-8"))

            self.assertEqual(pm_payload["project_workspace_dir"], dev_payload["project_workspace_dir"])
            self.assertEqual(dev_payload["product_probe"]["content"], "written by pm")
            self.assertTrue(Path(dev_payload["product_probe"]["path"]).exists())

            shared_root = source_home_path / ".codex-buddyswitch"
            pm_runtime = shared_root / "instances" / pm_payload["instance_id"] / "workspace"
            dev_runtime = shared_root / "instances" / dev_payload["instance_id"] / "workspace"
            self.assertFalse((pm_runtime / "projects" / "app" / "shared-product-sentinel.txt").exists())
            self.assertFalse((dev_runtime / "projects" / "app" / "shared-product-sentinel.txt").exists())
```

- [ ] **Step 2: Run the new test and verify red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_project_workspace_is_shared_across_buddy_instances -q
```

Expected:

```text
FAILED
```

The expected failure is missing project workspace env var or a failed fake Codex product sentinel write.

## Task 4: Implement The Shared Project Worktree Contract

**Files:**

- Modify: `tools/launcher/workspace.sh`
- Modify: `buddyswitch-codex`

- [ ] **Step 1: Define the project workspace default**

In `buddyswitch_workspace_init_defaults`, add:

```bash
  export BUDDYSWITCH_PROJECT_WORKSPACE_DIR="${BUDDYSWITCH_PROJECT_WORKSPACE_DIR:-${BUDDYSWITCH_SHARED_ROOT}/project/workspace}"
```

- [ ] **Step 2: Add project workspace validation**

Add this helper below `buddyswitch_workspace_validate_workspace_dir`:

```bash
buddyswitch_workspace_validate_project_workspace_dir() {
  local project_workspace shared_root normalized_project normalized_shared_root reserved_root

  project_workspace="${BUDDYSWITCH_PROJECT_WORKSPACE_DIR:-}"
  shared_root="${BUDDYSWITCH_SHARED_ROOT:-}"
  normalized_project="$(buddyswitch_workspace_canonical_path "${project_workspace%/}")"
  normalized_shared_root="$(buddyswitch_workspace_canonical_path "${shared_root%/}")"

  if [[ "${normalized_project}" == "${normalized_shared_root}" ]]; then
    echo "project workspace dir must be under BUDDYSWITCH_SHARED_ROOT" >&2
    echo "project workspace: ${normalized_project}" >&2
    echo "shared root: ${normalized_shared_root}" >&2
    return 1
  fi

  for reserved_root in \
    "${normalized_shared_root}/home" \
    "${normalized_shared_root}/codex-home" \
    "${normalized_shared_root}/run" \
    "${normalized_shared_root}/chrome" \
    "${normalized_shared_root}/instances" \
    "${normalized_shared_root}/state"; do
    case "${normalized_project}" in
      "${reserved_root}" | "${reserved_root}/"*)
        echo "project workspace dir must not be inside reserved BuddySwitch runtime state" >&2
        echo "project workspace: ${normalized_project}" >&2
        echo "reserved root: ${reserved_root}" >&2
        return 1
        ;;
    esac
  done

  case "${normalized_project}" in
    "${normalized_shared_root}/"*)
      return 0
      ;;
  esac

  echo "project workspace dir must be under BUDDYSWITCH_SHARED_ROOT" >&2
  echo "project workspace: ${normalized_project}" >&2
  echo "shared root: ${normalized_shared_root}" >&2
  return 1
}
```

- [ ] **Step 3: Add project worktree creation**

Add these helpers below `buddyswitch_workspace_is_valid_execution_worktree`:

```bash
buddyswitch_workspace_is_valid_project_worktree() {
  local project_workspace repo_common project_common

  project_workspace="${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"
  repo_common="$(buddyswitch_workspace_repo_common_dir)"

  git -C "${project_workspace}" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 1
  project_common="$(git -C "${project_workspace}" rev-parse --git-common-dir 2>/dev/null || true)"
  [[ "${project_common}" == "${repo_common}" ]]
}

buddyswitch_workspace_force_rebuild_project_worktree() {
  local project_workspace repo_root

  project_workspace="${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"
  repo_root="$(buddyswitch_workspace_repo_root)"
  buddyswitch_workspace_validate_project_workspace_dir

  mkdir -p "$(dirname "${project_workspace}")"
  git -C "${repo_root}" worktree remove --force "${project_workspace}" >/dev/null 2>&1 || true
  rm -rf "${project_workspace}"
  git -C "${repo_root}" worktree prune >/dev/null 2>&1 || true
  git -C "${repo_root}" worktree add --detach "${project_workspace}" HEAD >/dev/null
}

buddyswitch_workspace_ensure_project_worktree() {
  buddyswitch_workspace_init_defaults
  if buddyswitch_workspace_is_valid_project_worktree; then
    return 0
  fi

  buddyswitch_workspace_force_rebuild_project_worktree
}
```

- [ ] **Step 4: Wire project worktree creation into product-mode bootstrap**

In `start_locked_bootstrap`, after `buddyswitch_workspace_prepare_execution_worktree`, add:

```bash
  if [[ -n "${requested_buddy}" ]]; then
    buddyswitch_workspace_ensure_project_worktree
  fi
```

In `instance_open_locked_bootstrap`, after `buddyswitch_workspace_install_guardrail_hooks`, add:

```bash
  buddyswitch_workspace_ensure_project_worktree
```

- [ ] **Step 5: Print project workspace on start**

In `start_codex`, after the existing workspace line, print:

```bash
    echo "Project workspace: ${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}"
```

- [ ] **Step 6: Run shell syntax check**

Run:

```bash
bash -n buddyswitch-codex tools/launcher/env.sh tools/launcher/workspace.sh tools/launcher/browser_cockpit.sh tools/launcher/cleanup.sh
```

Expected:

```text
no output, exit code 0
```

- [ ] **Step 7: Run the first two product workspace tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_project_workspace_is_shared_across_buddy_instances \
  -q
```

Expected:

```text
2 passed
```

## Task 5: Add Lifecycle Guard Tests

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add instance delete guard test**

Add this test near existing instance delete tests:

```python
    def test_instance_delete_keeps_shared_project_workspace(self) -> None:
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
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            capture_path = temp_root_path / "capture.json"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            start_result = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "debug", "prompt-input", "edit app"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(start_result.returncode, 0, msg=start_result.stderr)
            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            project_workspace = Path(payload["project_workspace_dir"])
            sentinel = project_workspace / "projects" / "app" / "delete-survival-sentinel.txt"
            sentinel.write_text("keep product source\n", encoding="utf-8")
            instance_root = source_home_path / ".codex-buddyswitch" / "instances" / payload["instance_id"]
            (instance_root / "browser" / "chrome.pid").unlink(missing_ok=True)

            delete_result = subprocess.run(
                [str(LAUNCHER), "instance", "delete", payload["instance_id"], "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(delete_result.returncode, 0, msg=delete_result.stderr)
            self.assertFalse(instance_root.exists())
            self.assertTrue(sentinel.exists())
            worktrees = subprocess.check_output(["git", "-C", str(ROOT), "worktree", "list", "--porcelain"], text=True)
            self.assertIn(str(project_workspace), worktrees)
```

- [ ] **Step 2: Add reset worktree cleanup test**

Add this test near `test_reset_removes_execution_worktree_with_shared_root`:

```python
    def test_reset_removes_shared_project_worktree_registration(self) -> None:
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
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)
            self._write_fake_codex(fake_bin / "codex")
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")

            capture_path = temp_root_path / "capture.json"
            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(temp_root_path / "browser-ready.flag")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            start_result = subprocess.run(
                [str(LAUNCHER), "instance", "start", "--buddy", "pm", "debug", "prompt-input", "edit app"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(start_result.returncode, 0, msg=start_result.stderr)
            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            shared_root = source_home_path / ".codex-buddyswitch"
            project_workspace = Path(payload["project_workspace_dir"])
            instance_root = shared_root / "instances" / payload["instance_id"]
            (instance_root / "browser" / "chrome.pid").unlink(missing_ok=True)

            reset_result = subprocess.run(
                [str(LAUNCHER), "env", "reset", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(reset_result.returncode, 0, msg=reset_result.stderr)
            self.assertFalse(shared_root.exists())
            worktrees = subprocess.check_output(["git", "-C", str(ROOT), "worktree", "list", "--porcelain"], text=True)
            self.assertNotIn(str(project_workspace), worktrees)
```

- [ ] **Step 3: Run lifecycle guard tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_keeps_shared_project_workspace \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_reset_removes_shared_project_worktree_registration \
  -q
```

Expected:

```text
2 passed
```

## Task 6: Add Data Cleanup Product Source Guard

**Files:**

- Modify: `tests/test_cleanup_system.py`

- [ ] **Step 1: Add cleanup guard test**

Add this method inside `CleanupShellIntegrationTests`, near the existing all-data cleanup tests:

```python
    def test_shell_all_data_cleanup_keeps_shared_project_workspace(self) -> None:
        project_source = self.shared_root / "project" / "workspace" / "projects" / "app"
        project_source.mkdir(parents=True, exist_ok=True)
        sentinel = project_source / "product-source-sentinel.txt"
        sentinel.write_text("durable product source\n", encoding="utf-8")

        completed = self.run_cleanup("--all-data", "--yes", "--json")

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(sentinel.exists())
        self.assertNotIn(
            "project/workspace/projects/app/product-source-sentinel.txt",
            payload["result"]["deleted_paths"],
        )
```

- [ ] **Step 2: Run cleanup guard test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_data_cleanup_keeps_shared_project_workspace -q
```

Expected:

```text
1 passed
```

This guard protects the product source boundary. It is valid even if it passes before implementation because the functional rule is still observable through public cleanup behavior.

## Task 7: Update Runtime Guidance And Docs

**Files:**

- Modify: `tools/launcher/assets/runtime-AGENTS.md`
- Modify: `tools/launcher/assets/buddies/pm/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/dev/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/design/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/market/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/test/AGENTS.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add product workspace guidance to runtime AGENTS**

In `tools/launcher/assets/runtime-AGENTS.md`, under `## Project Code Location`, replace the current single sentence with:

```markdown
Main app code lives in the shared project workspace at `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`.

Use the instance runtime workspace for BuddySwitch control flow, projected state, raw dumps, and `projects/app/.runtime` only. Durable product source edits must be made under `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`, not under the instance workspace copy of `projects/app`.
```

- [ ] **Step 2: Add product workspace guidance to buddy AGENTS**

In each buddy AGENTS file, add this bullet under `## Buddy Lock`:

```markdown
- Durable product source edits belong under `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`; the instance workspace is for runtime control flow and scratch only.
```

- [ ] **Step 3: Update README**

Update the resolve/persist and repository layout sections so they state:

```markdown
Product mode has two work surfaces:

- Runtime workspace: `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace`
  BuddySwitch control flow, projected state, raw dumps, browser scratch, and `projects/app/.runtime`.
- Shared project workspace: `${BUDDYSWITCH_SHARED_ROOT}/project/workspace`
  Durable product source edits for `projects/app`.
```

Update the `projects/app/` directory entry to state:

```markdown
Main app code. In product mode, durable edits are made through `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`; runtime-only temporary data stays in `projects/app/.runtime` inside the instance runtime workspace.
```

- [ ] **Step 4: Update root AGENTS**

In the BuddySwitch workspace notes, add:

```markdown
- Product-mode durable app source lives in `${BUDDYSWITCH_SHARED_ROOT}/project/workspace/projects/app` and is exposed to sessions as `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}/projects/app`.
- Instance workspaces remain runtime-only; do not treat `${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/workspace/projects/app` as the durable product source.
```

- [ ] **Step 5: Add repo consistency test**

Add this test near the existing product-mode docs tests in `tests/test_repo_consistency.py`:

```python
    def test_product_mode_docs_define_shared_project_workspace(self) -> None:
        docs = (
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "pm" / "AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "dev" / "AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "design" / "AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "market" / "AGENTS.md",
            ROOT / "tools" / "launcher" / "assets" / "buddies" / "test" / "AGENTS.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in docs).lower()

        self.assertIn("buddyswitch_project_workspace_dir", combined)
        self.assertIn("${buddyswitch_shared_root}/project/workspace", combined)
        self.assertIn("shared project workspace", combined)
        self.assertIn("instance runtime workspace", combined)
        self.assertNotIn("durable product source edits belong under `${buddyswitch_shared_root}/instances/<instance-id>/workspace/projects/app`", combined)
```

- [ ] **Step 6: Run docs consistency test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_product_mode_docs_define_shared_project_workspace -q
```

Expected:

```text
1 passed
```

## Task 8: Full Verification

**Files:**

- Test: `tests/test_buddyswitch_launcher.py`
- Test: `tests/test_cleanup_system.py`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Run shell syntax check**

Run:

```bash
bash -n buddyswitch-codex tools/launcher/env.sh tools/launcher/workspace.sh tools/launcher/browser_cockpit.sh tools/launcher/cleanup.sh
```

Expected:

```text
no output, exit code 0
```

- [ ] **Step 2: Run targeted product workspace tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_project_workspace_is_shared_across_buddy_instances \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_delete_keeps_shared_project_workspace \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_reset_removes_shared_project_worktree_registration \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_data_cleanup_keeps_shared_project_workspace \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_product_mode_docs_define_shared_project_workspace \
  -q
```

Expected:

```text
6 passed
```

- [ ] **Step 3: Run launcher integration tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 4: Run cleanup integration tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 5: Run repo consistency tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

Expected:

```text
all tests pass
```

- [ ] **Step 6: Inspect worktree state**

Run:

```bash
git status --short
```

Expected:

```text
modified implementation, test, and doc files only in .worktrees/dev2230
```

## Self-Review

- Spec coverage: The plan implements the remaining memo item by adding a shared product work surface while keeping instance-local runtime workspaces.
- Forward-only scope: No migration, no legacy compatibility layer, no track-level workspace, and no dual product source contract.
- Test integrity: Primary tests use `./buddyswitch-codex instance start`, `instance delete`, `env reset`, and `data cleanup` to verify observable behavior and filesystem state.
- Boundary protection: Tests distinguish runtime workspace, shared project workspace, shared state projection, and instance-local scratch.
- Remaining risk: The first pass uses an explicit environment and guidance contract. It does not attempt transparent filesystem projection of `projects/app` into runtime workspaces because that would collide with the requirement that `projects/app/.runtime` remain instance-local.
