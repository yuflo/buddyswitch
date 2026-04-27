# BuddySwitch Cleanup Launcher Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `./buddyswitch-codex cleanup ...` the canonical cleanup entrypoint while keeping the existing cleanup behavior, safety guards, and dry-run defaults intact.

**Architecture:** Move shell cleanup orchestration from `scripts/cleanup_buddyswitch.sh` into `tools/launcher/cleanup.sh`, source it from `buddyswitch-codex`, and leave `scripts/env_cleanup.py` as the Python cleanup backend. Replace `scripts/cleanup_buddyswitch.sh` with a thin compatibility shim so existing manual paths still work during this cut without maintaining duplicate cleanup logic.

**Tech Stack:** Bash launcher scripts, Python cleanup backend, `unittest`/`pytest`, Markdown docs, plain JavaScript Context Panel command rendering.

---

## Current Bottleneck

Cleanup is product-mode runtime maintenance, but its public command still lives under `scripts/cleanup_buddyswitch.sh`. That makes the surface inconsistent with the new lifecycle CLI (`buddy`, `instance`, `workspace`, `browser`, `reset`) and keeps host-oriented `scripts/` responsible for launcher-owned orchestration.

The shortest validated improvement is not a broader cleanup redesign. It is one concrete boundary correction:

- Canonical user command: `./buddyswitch-codex cleanup ...`
- Launcher-owned Bash orchestration: `tools/launcher/cleanup.sh`
- Backend storage planner/executor: `scripts/env_cleanup.py`
- Backward-compatible shim: `scripts/cleanup_buddyswitch.sh`

## Confirmed Facts

- `scripts/cleanup_buddyswitch.sh` currently sources `tools/launcher/env.sh` and `tools/launcher/browser_cockpit.sh`, then acquires the runtime lock through `buddyswitch_with_runtime_lock`.
- `scripts/cleanup_buddyswitch.sh` owns cleanup safety checks for active launcher markers, browser liveness, state-root targeting, instance-local scratch cleanup, all-storage instance removal, and direct `__locked-cleanup` rejection.
- `scripts/env_cleanup.py` is the storage-aware backend that builds and executes cleanup plans. It should not move in this cut because tests and historical handoff docs depend on its standalone importability.
- `buddyswitch-codex` already owns launcher command dispatch for `start`, `buddy`, `instance`, `browser`, `workspace`, and `reset`.
- `README.md`, `framework/docs/interface-spec.md`, and `framework/console/app.js` still present `scripts/cleanup_buddyswitch.sh ...` as the user-facing cleanup command.
- `tests/test_cleanup_system.py` currently copies `scripts/cleanup_buddyswitch.sh` into a temp repo and executes it directly.

## Non-Goals

- Do not add per-instance cleanup, prune, retention, or rename flows.
- Do not merge scoped cleanup with `reset --yes`.
- Do not add retention policies, pruning policies, JSON lifecycle output, or a new cleanup abstraction layer.
- Do not let the Context Panel execute cleanup; it remains copy-only and dry-run-only.
- Do not move `scripts/env_cleanup.py`.
- Do not move object, task, artifact, track, or run cleanup semantics into Bash.
- Do not delete the compatibility shim in this cut; removal can be a later cleanup only after active docs and console references have stabilized on `./buddyswitch-codex cleanup`.
- Do not rewrite historical review docs except where active consistency tests require it.

## File Map

- Modify `buddyswitch-codex`: add `cleanup` to help text and command dispatch; source the new launcher cleanup helper.
- Create `tools/launcher/cleanup.sh`: hold all Bash cleanup orchestration currently in `scripts/cleanup_buddyswitch.sh`, adjusted to call `${BUDDYSWITCH_CLEANUP_REPO_ROOT}/scripts/env_cleanup.py`.
- Modify `scripts/cleanup_buddyswitch.sh`: replace implementation with an exec-only compatibility shim to `../buddyswitch-codex cleanup`.
- Modify `tests/test_cleanup_system.py`: make primary shell integration tests execute `./buddyswitch-codex cleanup`; keep one shim compatibility test.
- Modify `tests/test_buddyswitch_launcher.py`: cover `cleanup` in top-level help and basic cleanup routing.
- Modify `tests/test_repo_consistency.py`: enforce active docs and Context Panel use the canonical `./buddyswitch-codex cleanup` command.
- Modify `README.md`: document canonical cleanup commands.
- Modify `framework/docs/interface-spec.md`: update copyable command examples while preserving dry-run-only constraint.
- Modify `framework/console/app.js`: render canonical cleanup suggestions.

## Task 1: Add Failing CLI and Shim Tests

**Files:**
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_cleanup_system.py`

- [ ] **Step 1: Add launcher help coverage for cleanup**

Add assertions to the existing launcher help test in `tests/test_buddyswitch_launcher.py`:

```python
self.assertIn("buddyswitch-codex cleanup", help_result.stdout)
self.assertIn("cleanup", help_result.stdout)
```

- [ ] **Step 2: Add a cleanup routing test**

Add a focused launcher test that runs `./buddyswitch-codex cleanup --all-agents --json` in a temporary HOME with `BUDDYSWITCH_SHARED_ROOT` pointing at an empty temp root.

Expected behavior:

```text
return code is 1
stderr does not contain "Unknown"
stderr contains "Cleanup blocked"
```

Use the existing subprocess helper patterns in `tests/test_buddyswitch_launcher.py`; do not start Codex.

- [ ] **Step 3: Split cleanup test runner into canonical and shim paths**

In `CleanupShellIntegrationTests`, keep `run_cleanup()` but make it execute the canonical launcher command:

```python
["bash", "./buddyswitch-codex", "cleanup", *args]
```

Add a second helper only for compatibility:

```python
def run_cleanup_shim(self, *args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["BUDDYSWITCH_SHARED_ROOT"] = str(self.shared_root)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", "scripts/cleanup_buddyswitch.sh", *args],
        cwd=self.repo_root,
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )
```

- [ ] **Step 4: Add one shim compatibility test**

Add one test that proves the legacy script forwards to the canonical cleanup path:

```python
def test_shell_cleanup_legacy_script_forwards_to_launcher_cleanup(self) -> None:
    completed = self.run_cleanup_shim("--agent", "market", "--json")
    self.assertEqual(completed.returncode, 0, msg=completed.stderr)
    payload = json.loads(completed.stdout)
    self.assertIn("buddyswitch/content/runs/run-market.json", payload["delete_paths"])
    self.assertEqual(payload["repo_root"], str(self.workspace_dir))
```

- [ ] **Step 5: Run targeted failing tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_launcher_help_and_reset_flow \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_agent_dry_run_reports_run_content \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_cleanup_legacy_script_forwards_to_launcher_cleanup \
  -q
```

Expected before implementation: at least one failure because `buddyswitch-codex cleanup` is not routed and/or the shim is not yet forwarding.

## Task 2: Move Cleanup Orchestration Under Launcher Tools

**Files:**
- Create: `tools/launcher/cleanup.sh`
- Modify: `buddyswitch-codex`
- Modify: `scripts/cleanup_buddyswitch.sh`

- [ ] **Step 1: Create `tools/launcher/cleanup.sh` from the existing orchestration**

Move the Bash functions from `scripts/cleanup_buddyswitch.sh` into `tools/launcher/cleanup.sh`, preserving function names and behavior unless a path must change.

At the top of the new file use launcher-relative paths:

```bash
#!/usr/bin/env bash

BUDDYSWITCH_CLEANUP_HELPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUDDYSWITCH_CLEANUP_REPO_ROOT="$(cd "${BUDDYSWITCH_CLEANUP_HELPER_DIR}/../.." && pwd)"
BUDDYSWITCH_CLEANUP_ENV_CLEANUP="${BUDDYSWITCH_CLEANUP_REPO_ROOT}/scripts/env_cleanup.py"
```

Do not call `main "$@"` from this helper. It must expose functions for `buddyswitch-codex` to call.

- [ ] **Step 2: Keep the Python backend path explicit**

In the moved `buddyswitch_cleanup_run_env_cleanup()` function, call:

```bash
python3 "${BUDDYSWITCH_CLEANUP_ENV_CLEANUP}" \
  --repo-root "${repo_root}" \
  "${target_args[@]}" \
  "${BUDDYSWITCH_CLEANUP_COMMON_ARGS[@]}"
```

In the all-storage source checkout cleanup path, call:

```bash
python3 "${BUDDYSWITCH_CLEANUP_ENV_CLEANUP}" --repo-root "${BUDDYSWITCH_CLEANUP_REPO_ROOT}" --all-storage --execute --force >/dev/null
```

- [ ] **Step 3: Add the canonical cleanup command to `buddyswitch-codex`**

Update helper sourcing:

```bash
CLEANUP_HELPER="${REPO_ROOT}/tools/launcher/cleanup.sh"
```

Update the missing-helper check to include `${CLEANUP_HELPER}`, then source it:

```bash
source "${CLEANUP_HELPER}"
```

Add help text:

```text
  buddyswitch-codex cleanup [--agent <buddy>|--all-agents|--project app|--all-storage] [--execute --force] [--json]
```

Add command description:

```text
  cleanup Remove BuddySwitch runtime state through the launcher safety gates.
```

Add dispatch:

```bash
cleanup)
  shift || true
  buddyswitch_cleanup_main "$@"
  ;;
__locked-cleanup)
  shift || true
  buddyswitch_cleanup_run_locked "$@"
  ;;
```

- [ ] **Step 4: Keep direct locked entrypoint guarded**

In `tools/launcher/cleanup.sh`, define:

```bash
buddyswitch_cleanup_main() {
  buddyswitch_with_runtime_lock "${BUDDYSWITCH_CLEANUP_REPO_ROOT}/buddyswitch-codex" "__locked-cleanup" "$@"
}
```

Rename the old `run_cleanup_locked()` body to:

```bash
buddyswitch_cleanup_run_locked() {
  buddyswitch_require_runtime_lock
  ...
}
```

Do not expose a second executable main path from `tools/launcher/cleanup.sh`.

- [ ] **Step 5: Replace the legacy script with an exec shim**

Replace `scripts/cleanup_buddyswitch.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

exec "${REPO_ROOT}/buddyswitch-codex" cleanup "$@"
```

- [ ] **Step 6: Run targeted implementation tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_launcher_help_and_reset_flow \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_agent_dry_run_reports_run_content \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_cleanup_legacy_script_forwards_to_launcher_cleanup \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_locked_cleanup_entrypoint_rejects_direct_invocation_without_lock \
  -q
```

Expected after implementation: all listed tests pass.

## Task 3: Update Cleanup Integration Tests Without Broad Rewrites

**Files:**
- Modify: `tests/test_cleanup_system.py`

- [ ] **Step 1: Copy launcher files into shell integration fixture**

The temp repo fixture must include `buddyswitch-codex`, launcher helpers, and `scripts/env_cleanup.py`.

Use this fixture shape:

```python
shutil.copy2(ROOT / "buddyswitch-codex", self.repo_root / "buddyswitch-codex")
scripts_dir = self.repo_root / "scripts"
scripts_dir.mkdir(parents=True, exist_ok=True)
for name in ("cleanup_buddyswitch.sh", "env_cleanup.py"):
    shutil.copy2(ROOT / "scripts" / name, scripts_dir / name)
launcher_dir = self.repo_root / "tools" / "launcher"
launcher_dir.mkdir(parents=True, exist_ok=True)
for name in ("env.sh", "workspace.sh", "runtime_lock.py", "browser_cockpit.sh", "cleanup.sh"):
    shutil.copy2(ROOT / "tools" / "launcher" / name, launcher_dir / name)
```

If `buddyswitch-codex` now requires `tools/launcher/instance.sh`, include it in this fixture too:

```python
for name in ("env.sh", "workspace.sh", "runtime_lock.py", "browser_cockpit.sh", "instance.sh", "cleanup.sh"):
    shutil.copy2(ROOT / "tools" / "launcher" / name, launcher_dir / name)
```

- [ ] **Step 2: Keep all existing cleanup behavior tests**

All existing tests for these behaviors must stay meaningful and pass through `./buddyswitch-codex cleanup`:

- Agent dry-run reports only the selected buddy run content.
- Project cleanup only touches `projects/app/.runtime`.
- All-agents cleanup clears buddy state.
- Agent cleanup targets launcher runtime state, not source checkout state.
- All-storage cleanup migrates legacy source checkout state and strips legacy runtime excludes only when executing.
- Dry-run does not mutate source checkout or `.git/info/exclude`.
- Runtime lock blocks cleanup.
- Active launcher marker blocks cleanup.
- Active browser marker blocks cleanup.
- Stale browser pid without active endpoint does not block cleanup.
- All-storage cleanup handles shared state and instance roots without a legacy workspace.
- Direct `__locked-cleanup` invocation without the runtime lock is rejected.

- [ ] **Step 3: Run full cleanup tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py -q
```

Expected: all cleanup tests pass.

## Task 4: Update Active Docs and Context Panel Copy Commands

**Files:**
- Modify: `README.md`
- Modify: `framework/docs/interface-spec.md`
- Modify: `framework/console/app.js`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Update README cleanup commands**

Replace the active cleanup command block with:

```bash
./buddyswitch-codex cleanup --agent market
./buddyswitch-codex cleanup --all-agents
./buddyswitch-codex cleanup --project app
./buddyswitch-codex cleanup --all-storage
```

Keep the existing dry-run wording and the statement that cleanup targets shared state and instance-local scratch, not repo-root development checkout.

- [ ] **Step 2: Update interface spec copy commands**

Replace the Context Panel cleanup command examples with:

```markdown
- `./buddyswitch-codex cleanup --agent <buddy>`
- `./buddyswitch-codex cleanup --all-agents`
- `./buddyswitch-codex cleanup --project app`
- `./buddyswitch-codex cleanup --all-storage`
```

Keep:

```markdown
Commands must not include `--execute` or `--force` by default.
```

- [ ] **Step 3: Update Context Panel command rendering**

In `framework/console/app.js`, change generated commands to:

```javascript
commands.push(`./buddyswitch-codex cleanup --agent ${task.buddy}`);
commands.push("./buddyswitch-codex cleanup --all-agents");
commands.push("./buddyswitch-codex cleanup --project app");
commands.push("./buddyswitch-codex cleanup --all-storage");
```

Update both `cleanupSuggestions(track)` and the standalone task cleanup command list.

- [ ] **Step 4: Add active reference consistency test**

Add a repo consistency test that checks active user-facing docs and console code prefer canonical cleanup commands:

```python
def test_active_cleanup_surfaces_use_launcher_cleanup_command(self) -> None:
    targets = (
        ROOT / "README.md",
        ROOT / "framework" / "docs" / "interface-spec.md",
        ROOT / "framework" / "console" / "app.js",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in targets)

    self.assertIn("./buddyswitch-codex cleanup --agent", combined)
    self.assertIn("./buddyswitch-codex cleanup --all-agents", combined)
    self.assertIn("./buddyswitch-codex cleanup --project app", combined)
    self.assertIn("./buddyswitch-codex cleanup --all-storage", combined)
    self.assertNotIn("scripts/cleanup_buddyswitch.sh --agent", combined)
    self.assertNotIn("scripts/cleanup_buddyswitch.sh --all-agents", combined)
    self.assertNotIn("scripts/cleanup_buddyswitch.sh --project app", combined)
    self.assertNotIn("scripts/cleanup_buddyswitch.sh --all-storage", combined)
```

- [ ] **Step 5: Run docs and consistency tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_cleanup_surfaces_use_launcher_cleanup_command \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_cleanup_docs_reference_run_content_without_legacy_artifact_content \
  -q
```

Expected: both tests pass.

## Task 5: Final Verification and Scope Check

**Files:**
- No new files beyond `tools/launcher/cleanup.sh`.
- Existing lifecycle changes remain in the same isolated worktree.

- [ ] **Step 1: Run cleanup verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py -q
```

Expected: all cleanup tests pass.

- [ ] **Step 2: Run launcher and repo consistency verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_readme_documents_instance_lifecycle_cli \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_cleanup_surfaces_use_launcher_cleanup_command \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_cleanup_docs_reference_run_content_without_legacy_artifact_content \
  -q
```

Expected: listed launcher and consistency tests pass.

- [ ] **Step 3: Run lifecycle regression subset**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_cleanup_ignores_stale_instance_browser_pid_without_endpoint \
  tests/test_cleanup_system.py::CleanupShellIntegrationTests::test_shell_all_storage_cleanup_handles_state_and_instances_without_legacy_workspace \
  tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests::test_cmd_resolve_product_mode_plain_text_with_task_and_track_binding_adapts_to_task_track_switch \
  tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests::test_reopened_product_mode_env_uses_existing_instance_binding \
  -q
```

Expected: lifecycle and cleanup regression subset passes.

- [ ] **Step 4: Run whitespace verification**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 5: Inspect final diff scope**

Run:

```bash
git diff --stat
git status --short --branch
```

Expected:

- Worktree branch remains `instance-lifecycle-plan`.
- Main checkout is not touched.
- Diff is limited to cleanup launcher integration, active docs, active console copy commands, and tests.
- `scripts/env_cleanup.py` is unchanged unless a test exposes a real backend regression.

## Risks and Stop Conditions

- Stop if moving the shell file changes cleanup target selection between shared state, legacy workspace, and instance-local scratch.
- Stop if the shim grows logic beyond resolving repo root and execing `buddyswitch-codex cleanup`.
- Stop if `buddyswitch-codex cleanup` requires a full product-mode instance before dry-run cleanup can work against an existing shared root.
- Stop if Context Panel changes move from copyable commands into command execution.
- Stop if implementation starts introducing per-instance cleanup, retention policy, or new cleanup abstractions.

## Implementation Decision

Proceed with a narrow launcher integration. This replaces the public cleanup surface without changing cleanup semantics. The cleanup backend remains Python in `scripts/`; the cleanup orchestration becomes launcher-owned in `tools/launcher/`; active user-facing docs and panel suggestions use `./buddyswitch-codex cleanup`.
