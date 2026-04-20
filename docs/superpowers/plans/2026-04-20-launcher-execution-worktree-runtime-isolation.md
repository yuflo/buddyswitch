# Launcher Execution Worktree Runtime Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move BuddySwitch product-mode runtime out of the main checkout by launching Codex inside a launcher-managed execution worktree under `${BUDDYSWITCH_SHARED_ROOT}`, while keeping repo-root development lightweight.

**Architecture:** Keep the existing shared runtime environment under `${BUDDYSWITCH_SHARED_ROOT}` for `HOME`, `CODEX_HOME`, browser state, logs, and run markers. Add one launcher-owned execution worktree at `${BUDDYSWITCH_SHARED_ROOT}/workspace`, run it in `detached HEAD`, inject runtime-only `AGENTS.md` and local Git guardrails there, and move BuddySwitch state directories to execution-worktree-local storage instead of main-checkout skeleton paths.

**Tech Stack:** Bash launcher helpers, Git worktree plumbing, repo-local runtime templates, Python `unittest` / `pytest`, existing BuddySwitch persistence scripts.

---

## File Structure

- Modify: `buddyswitch-codex`
  - Keep the user-facing CLI surface stable.
  - Stop launching Codex from repo root; launch from the execution worktree.
- Modify: `tools/launcher/env.sh`
  - Keep ownership of shared runtime environment paths.
  - Add exported path(s) for the execution worktree and related runtime assets.
- Create: `tools/launcher/workspace.sh`
  - Own execution worktree bootstrap, validation, runtime file injection, and Git-local guardrails.
- Create: `tools/launcher/assets/runtime-AGENTS.md`
  - Hold the full product-mode runtime contract that should only apply inside the execution worktree.
- Modify: `AGENTS.md`
  - Reduce root instructions to development-facing architecture guidance.
  - Explain runtime environment vs execution worktree without carrying the full runtime contract.
- Modify: `README.md`
  - Explain the two entry modes: repo-root development vs launcher-managed product mode.
- Modify: `.gitignore`
  - Remove tracked ignore rules for BuddySwitch state directories that will no longer live in the main checkout.
- Modify: `tests/test_buddyswitch_launcher.py`
  - Add failing regression coverage for execution worktree creation, runtime file injection, and launch cwd.
- Modify: `tests/test_browser_cockpit_launcher.py`
  - Keep browser bootstrap assertions aligned with the new workspace path model.
- Modify: `tests/test_repo_consistency.py`
  - Update repo-level architecture assertions to the new split between root `AGENTS.md` and runtime `AGENTS.md`.
- Modify: `tests/test_cleanup_system.py`
  - Remove assumptions about tracked `.gitkeep` files in state directories.

Notes locked in by this plan:

- The execution worktree lives at `${BUDDYSWITCH_SHARED_ROOT}/workspace`.
- The execution worktree is launcher-owned, local-only, and `detached HEAD`.
- Runtime BuddySwitch state stays on canonical repo-relative paths, but only inside the execution worktree.
- Main checkout no longer carries tracked skeleton state directories for BuddySwitch runtime state.

### Task 1: Add Failing Coverage For Execution Worktree Launch

**Files:**
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_browser_cockpit_launcher.py`

- [ ] **Step 1: Add a failing launcher test that proves `start` no longer launches from repo root**

```python
    def test_start_launches_codex_from_execution_worktree_with_runtime_agents(self) -> None:
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
                [str(LAUNCHER), "start", "debug", "prompt-input", "switch pm: draft prd"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)

            payload = json.loads(capture_path.read_text(encoding="utf-8"))
            expected_workspace = source_home_path / ".codex-buddyswitch" / "workspace"
            self.assertEqual(payload["cwd"], str(expected_workspace))
            self.assertTrue((expected_workspace / "AGENTS.md").exists())
            self.assertEqual(
                (expected_workspace / "AGENTS.md").read_text(encoding="utf-8").splitlines()[0],
                "# BuddySwitch Runtime Workspace",
            )
```

- [ ] **Step 2: Run the new launcher test and confirm it fails against the current repo-root launch behavior**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k execution_worktree -v
```

Expected:

```text
FAIL ... expected cwd to equal .../.codex-buddyswitch/workspace
```

- [ ] **Step 3: Add a failing browser test that proves browser bootstrap does not need repo-root state skeletons**

```python
    def test_browser_ensure_does_not_require_main_checkout_state_skeleton(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root, tempfile.TemporaryDirectory() as source_home:
            temp_root_path = Path(temp_root)
            source_home_path = Path(source_home)
            fake_bin = temp_root_path / "bin"
            fake_bin.mkdir(parents=True, exist_ok=True)

            ready_file = temp_root_path / "browser-ready.flag"
            self._write_fake_curl(fake_bin / "curl")
            self._write_fake_chrome(fake_bin / "fake-chrome")
            self._write_fake_codex(fake_bin / "codex")

            capture_path = temp_root_path / "calls.jsonl"

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
            env["BUDDYSWITCH_TEST_BROWSER_READY_FILE"] = str(ready_file)
            env["BUDDYSWITCH_BROWSER_CHROME_BIN"] = str(fake_bin / "fake-chrome")
            env["BUDDYSWITCH_TEST_CAPTURE"] = str(capture_path)

            completed = subprocess.run(
                [str(LAUNCHER), "browser", "ensure"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)
            shared_root = source_home_path / ".codex-buddyswitch"
            self.assertTrue((shared_root / "workspace").exists())
            self.assertFalse((ROOT / "buddyswitch" / "objects" / "tracks" / ".gitkeep").samefile(
                shared_root / "workspace" / "buddyswitch" / "objects" / "tracks" / ".gitkeep"
            ))
```

- [ ] **Step 4: Run the browser launcher test slice and confirm current behavior is still missing the execution-worktree contract**

Run:

```bash
python3 -m pytest tests/test_browser_cockpit_launcher.py -k state_skeleton -v
```

Expected:

```text
FAIL ... shared_root / "workspace" does not exist
```

- [ ] **Step 5: Commit the red tests**

```bash
git add tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py
git commit -m "test: cover launcher execution worktree bootstrap"
```

### Task 2: Introduce Launcher-Owned Execution Worktree Bootstrap

**Files:**
- Create: `tools/launcher/workspace.sh`
- Create: `tools/launcher/assets/runtime-AGENTS.md`
- Modify: `tools/launcher/env.sh`
- Modify: `buddyswitch-codex`
- Test: `tests/test_buddyswitch_launcher.py`
- Test: `tests/test_browser_cockpit_launcher.py`

- [ ] **Step 1: Create a focused workspace helper with exported execution-worktree paths**

```bash
#!/usr/bin/env bash
set -euo pipefail

buddyswitch_workspace_init_defaults() {
  export BUDDYSWITCH_WORKSPACE_DIR="${BUDDYSWITCH_WORKSPACE_DIR:-${BUDDYSWITCH_SHARED_ROOT}/workspace}"
  export BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE="${BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE:-${REPO_ROOT}/tools/launcher/assets/runtime-AGENTS.md}"
}

buddyswitch_workspace_git_dir() {
  git -C "${BUDDYSWITCH_WORKSPACE_DIR}" rev-parse --git-dir
}

buddyswitch_workspace_exclude_path() {
  git -C "${BUDDYSWITCH_WORKSPACE_DIR}" rev-parse --git-path info/exclude
}
```

- [ ] **Step 2: Implement execution worktree creation in `detached HEAD` under shared root**

```bash
buddyswitch_workspace_ensure_checkout() {
  if [[ -d "${BUDDYSWITCH_WORKSPACE_DIR}" ]] && git -C "${BUDDYSWITCH_WORKSPACE_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    return 0
  fi

  rm -rf "${BUDDYSWITCH_WORKSPACE_DIR}"
  mkdir -p "$(dirname "${BUDDYSWITCH_WORKSPACE_DIR}")"
  git -C "${REPO_ROOT}" worktree add --detach "${BUDDYSWITCH_WORKSPACE_DIR}" HEAD
}
```

- [ ] **Step 3: Inject runtime-only files and local Git guardrails into the execution worktree**

```bash
buddyswitch_workspace_install_runtime_files() {
  mkdir -p "${BUDDYSWITCH_WORKSPACE_DIR}/.codex"
  cp "${BUDDYSWITCH_RUNTIME_AGENTS_TEMPLATE}" "${BUDDYSWITCH_WORKSPACE_DIR}/AGENTS.md"
}

buddyswitch_workspace_install_local_excludes() {
  local exclude_path
  exclude_path="$(buddyswitch_workspace_exclude_path)"
  mkdir -p "$(dirname "${exclude_path}")"
  cat > "${exclude_path}" <<'EOF'
buddyswitch/objects/tracks/**
buddyswitch/objects/tasks/**
buddyswitch/objects/artifacts/**
buddyswitch/content/runs/**
runs/raw/**
projects/app/.runtime/**
EOF
}

buddyswitch_workspace_install_guardrails() {
  local hooks_dir="${BUDDYSWITCH_SHARED_ROOT}/hooks"
  mkdir -p "${hooks_dir}"
  cat > "${hooks_dir}/pre-commit" <<'EOF'
#!/usr/bin/env bash
echo "BuddySwitch execution worktree is runtime-only; commit is blocked." >&2
exit 1
EOF
  cat > "${hooks_dir}/pre-rebase" <<'EOF'
#!/usr/bin/env bash
echo "BuddySwitch execution worktree is runtime-only; rebase is blocked." >&2
exit 1
EOF
  cat > "${hooks_dir}/pre-push" <<'EOF'
#!/usr/bin/env bash
echo "BuddySwitch execution worktree is runtime-only; push is blocked." >&2
exit 1
EOF
  chmod +x "${hooks_dir}/pre-commit" "${hooks_dir}/pre-rebase" "${hooks_dir}/pre-push"
  git -C "${BUDDYSWITCH_WORKSPACE_DIR}" config --worktree core.hooksPath "${hooks_dir}"
}

buddyswitch_workspace_prepare() {
  buddyswitch_workspace_init_defaults
  buddyswitch_workspace_ensure_checkout
  buddyswitch_workspace_install_runtime_files
  buddyswitch_workspace_install_local_excludes
  buddyswitch_workspace_install_guardrails
}
```

- [ ] **Step 4: Wire launcher start-up to prepare the worktree and launch Codex from there**

```bash
source "${REPO_ROOT}/tools/launcher/workspace.sh"

start_codex() {
  buddyswitch_browser_bootstrap
  buddyswitch_workspace_prepare

  local marker_path
  marker_path="$(buddyswitch_write_launcher_marker)"
  trap "buddyswitch_cleanup_pid_marker '${marker_path}'" EXIT INT TERM HUP

  cd "${BUDDYSWITCH_WORKSPACE_DIR}"
  buddyswitch_run_codex "$@"
}
```

- [ ] **Step 5: Add the runtime-only AGENTS template with the full product-mode contract**

```markdown
# BuddySwitch Runtime Workspace

This file applies only inside the launcher-managed execution worktree.

- This workspace is launcher-owned and runtime-only.
- Do not use this workspace for commit, merge, rebase, push, or PR work.
- BuddySwitch runtime state lives on canonical repo-relative paths in this worktree:
  - `buddyswitch/objects/tracks/*.json`
  - `buddyswitch/objects/tasks/*.json`
  - `buddyswitch/objects/artifacts/*.json`
  - `buddyswitch/content/runs/*.json`
- Follow the full BuddySwitch `switch` runtime contract from this runtime workspace only.
```

- [ ] **Step 6: Run the targeted launcher/browser tests and confirm the new execution-worktree path passes**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k execution_worktree -v
python3 -m pytest tests/test_browser_cockpit_launcher.py -k state_skeleton -v
```

Expected:

```text
PASS
```

- [ ] **Step 7: Commit the execution-worktree bootstrap**

```bash
git add buddyswitch-codex tools/launcher/env.sh tools/launcher/workspace.sh tools/launcher/assets/runtime-AGENTS.md tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py
git commit -m "feat: launch codex from execution worktree"
```

### Task 3: Remove Main-Checkout Runtime State Skeletons

**Files:**
- Modify: `.gitignore`
- Delete: `buddyswitch/objects/tracks/.gitkeep`
- Delete: `buddyswitch/objects/tasks/.gitkeep`
- Delete: `buddyswitch/objects/artifacts/.gitkeep`
- Delete: `buddyswitch/content/runs/.gitkeep`
- Delete: `runs/raw/.gitkeep`
- Modify: `tests/test_cleanup_system.py`
- Test: `tests/test_cleanup_system.py`

- [ ] **Step 1: Remove tracked ignore rules that only existed to protect main-checkout runtime state**

```gitignore
# Project runtime noise (keep only skeleton marker)
projects/app/.runtime/**
!projects/app/.runtime/.gitkeep

# Temporary and local noise
.worktrees/
*.log
*.tmp
*.trace
*.out
*.dump
*.pyc
__pycache__/
tmp/
.DS_Store
```

Delete these blocks entirely:

```gitignore
runs/raw/**
!runs/raw/.gitkeep

buddyswitch/objects/artifacts/**
!buddyswitch/objects/artifacts/.gitkeep

buddyswitch/objects/tasks/**
!buddyswitch/objects/tasks/.gitkeep

buddyswitch/objects/tracks/**
!buddyswitch/objects/tracks/.gitkeep

buddyswitch/content/runs/**
!buddyswitch/content/runs/.gitkeep
```

- [ ] **Step 2: Delete the tracked skeleton markers from the main checkout**

```bash
rm buddyswitch/objects/tracks/.gitkeep
rm buddyswitch/objects/tasks/.gitkeep
rm buddyswitch/objects/artifacts/.gitkeep
rm buddyswitch/content/runs/.gitkeep
rm runs/raw/.gitkeep
```

- [ ] **Step 3: Update cleanup tests to stop asserting tracked skeleton files remain in the main checkout**

```python
        self.assertFalse(self.fixture.exists("buddyswitch/content/runs/run-market.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/content/runs/run-pm.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/content/runs/bad-run.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/objects/tracks/track-demo.json"))
        self.assertFalse(self.fixture.exists("buddyswitch/content/runs/.gitkeep"))
```

And replace expectations like:

```python
            "runs/raw/.gitkeep",
            "buddyswitch/objects/tracks/.gitkeep",
            "buddyswitch/objects/tasks/.gitkeep",
            "buddyswitch/objects/artifacts/.gitkeep",
            "buddyswitch/content/runs/.gitkeep",
```

with:

```python
            "projects/app/.runtime/.gitkeep",
```

- [ ] **Step 4: Run cleanup and persistence tests to verify directory creation still works without tracked skeletons**

Run:

```bash
python3 -m pytest tests/test_cleanup_system.py tests/test_switch_runtime.py -v
```

Expected:

```text
PASS
```

- [ ] **Step 5: Commit the state-surface move out of the main checkout**

```bash
git add .gitignore tests/test_cleanup_system.py tests/test_switch_runtime.py
git rm buddyswitch/objects/tracks/.gitkeep buddyswitch/objects/tasks/.gitkeep buddyswitch/objects/artifacts/.gitkeep buddyswitch/content/runs/.gitkeep runs/raw/.gitkeep
git commit -m "refactor: move runtime state out of main checkout"
```

### Task 4: Split Root Development Guidance From Runtime Guidance

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `tests/test_repo_consistency.py`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Replace the root `AGENTS.md` runtime contract with development-facing architecture guidance**

```markdown
# BuddySwitch Development Workspace

This repo root is for developing BuddySwitch itself.

- Use `codex` here when you are editing BuddySwitch source, tests, docs, or launcher code.
- `./buddyswitch-codex start` does not run Codex from this checkout; it launches from a launcher-managed execution worktree under `${BUDDYSWITCH_SHARED_ROOT}/workspace`.
- The execution worktree carries the full runtime BuddySwitch contract.
- Runtime BuddySwitch state is not maintained as tracked skeleton directories in the main checkout.

Canonical source definitions remain:
- Env manifest: `buddyswitch/manifest.toml`
- Runtime state paths inside the execution worktree:
  - `buddyswitch/objects/tracks/*.json`
  - `buddyswitch/objects/tasks/*.json`
  - `buddyswitch/objects/artifacts/*.json`
  - `buddyswitch/content/runs/*.json`
```

- [ ] **Step 2: Update the README quick start so development mode and launcher mode are explicit**

```markdown
## 30-Second Quick Start

Two modes exist:

1. **Develop BuddySwitch:** run `codex` from the repo root.
2. **Run BuddySwitch product mode:** run `./buddyswitch-codex start`.

The launcher-managed product mode uses:
- `${BUDDYSWITCH_SHARED_ROOT}` for runtime environment isolation
- `${BUDDYSWITCH_SHARED_ROOT}/workspace` for the execution worktree
```

- [ ] **Step 3: Rewrite repo consistency assertions to check the new split**

```python
    def test_root_agents_describes_execution_worktree_without_full_runtime_contract(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8").lower()
        self.assertIn("execution worktree", text)
        self.assertIn("repo root is for developing buddyswitch itself", text)
        self.assertNotIn("inject `selected_skill_packet.skill_instructions` verbatim", text)

    def test_runtime_agents_template_holds_full_runtime_contract(self) -> None:
        text = (ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md").read_text(encoding="utf-8").lower()
        self.assertIn("selected_skill_packet", text)
        self.assertIn("receipt", text)
        self.assertIn("commands", text)
        self.assertIn("summary", text)
```

- [ ] **Step 4: Run the repo consistency suite and confirm docs/contracts are aligned**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py -v
```

Expected:

```text
PASS
```

- [ ] **Step 5: Commit the doc and contract split**

```bash
git add AGENTS.md README.md tests/test_repo_consistency.py
git commit -m "docs: split development and runtime workspace guidance"
```

### Task 5: Verify The Whole Launcher Path End-To-End

**Files:**
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_browser_cockpit_launcher.py`
- Test: `tests/test_buddyswitch_launcher.py`
- Test: `tests/test_browser_cockpit_launcher.py`
- Test: `tests/test_repo_consistency.py`
- Test: `tests/test_cleanup_system.py`
- Test: `tests/test_switch_runtime.py`

- [ ] **Step 1: Add one final launcher test that asserts `reset --yes` removes the execution worktree with the rest of shared root**

```python
    def test_reset_removes_execution_worktree_with_shared_root(self) -> None:
        with tempfile.TemporaryDirectory() as source_home:
            source_home_path = Path(source_home)
            shared_root = source_home_path / ".codex-buddyswitch"
            workspace = shared_root / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)

            env = os.environ.copy()
            env["HOME"] = str(source_home_path)
            env.pop("CODEX_HOME", None)

            completed = subprocess.run(
                [str(LAUNCHER), "reset", "--yes"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0)
            self.assertFalse(shared_root.exists())
```

- [ ] **Step 2: Run the full affected verification loop**

Run:

```bash
python3 -m pytest \
  tests/test_buddyswitch_launcher.py \
  tests/test_browser_cockpit_launcher.py \
  tests/test_repo_consistency.py \
  tests/test_cleanup_system.py \
  tests/test_switch_runtime.py \
  -v
```

Expected:

```text
PASS
```

- [ ] **Step 3: Do one manual launcher smoke check in a disposable home**

Run:

```bash
tmp_home="$(mktemp -d /tmp/buddyswitch-home.XXXXXX)"
HOME="$tmp_home" ./buddyswitch-codex start --help
find "$tmp_home/.codex-buddyswitch" -maxdepth 2 -type d | sort
```

Expected:

```text
.../.codex-buddyswitch
.../.codex-buddyswitch/home
.../.codex-buddyswitch/codex-home
.../.codex-buddyswitch/run
.../.codex-buddyswitch/workspace
```

- [ ] **Step 4: Commit the final verification coverage**

```bash
git add tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py
git commit -m "test: verify launcher execution worktree flow"
```

## Self-Review

- Spec coverage:
  - Dev-mode vs runtime-mode split: covered by Tasks 2 and 4.
  - Execution worktree under shared root: covered by Task 2.
  - Runtime state moved out of main checkout: covered by Task 3.
  - Root `AGENTS.md` kept minimal but still architecture-relevant: covered by Task 4.
  - Avoided speculative systems and sync layers: enforced by the file structure and absence of extra services/tasks.
- Placeholder scan:
  - No `TODO` / `TBD` markers remain.
  - Every task names exact files, commands, and expected outcomes.
- Type consistency:
  - The plan uses one naming scheme throughout: `runtime environment`, `execution worktree`, `${BUDDYSWITCH_SHARED_ROOT}/workspace`, and runtime `AGENTS.md`.

Plan complete and saved to `docs/superpowers/plans/2026-04-20-launcher-execution-worktree-runtime-isolation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
