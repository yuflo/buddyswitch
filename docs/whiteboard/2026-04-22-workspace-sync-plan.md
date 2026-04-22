# Workspace Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the user-facing `buddyswitch-codex workspace ensure` command with a manual `buddyswitch-codex workspace sync` command that always refreshes the runtime workspace to the repo's current `HEAD` while preserving runtime outputs, and keep `start` on its existing non-sync bootstrap path.

**Architecture:** Keep launcher startup behavior unchanged: `start` should continue to prepare a usable runtime workspace shell without forcing a code refresh. Add a separate sync-only path in the workspace helper that always rebuilds the execution worktree from repo `HEAD`, then rehydrates runtime outputs and reinstalls runtime shell files. Rename the user-facing workspace subcommand and docs/tests to match the new explicit semantics.

**Tech Stack:** Bash launcher scripts, git worktrees, Python `unittest` launcher regression tests, Markdown docs.

---

## File Structure

- Modify: `buddyswitch-codex`
  - Replace `workspace ensure` help text and parser handling with `workspace sync`.
  - Keep `start` calling the current prepare/bootstrap path.
- Modify: `tools/launcher/workspace.sh`
  - Split "prepare shell" from "force rebuild to HEAD" so `start` and `workspace sync` have distinct behavior.
  - Preserve existing runtime-output staging/restore behavior for sync.
- Modify: `README.md`
  - Replace `workspace ensure` references with `workspace sync`.
  - Clarify that `workspace sync` is a manual code refresh, while `start` does not auto-sync.
- Modify: `tests/test_buddyswitch_launcher.py`
  - Rename `workspace ensure` expectations to `workspace sync`.
  - Add explicit assertions for the new sync wording and semantics.

## Task 1: Rename The User-Facing Workspace Command

**Files:**
- Modify: `buddyswitch-codex`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Write the failing help-surface test**

```python
self.assertIn("workspace sync", help_result.stdout)
self.assertNotIn("workspace ensure", help_result.stdout)
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py -k "help_and_reset_flow" -q`
Expected: FAIL because launcher help still prints `workspace ensure`.

- [ ] **Step 3: Update launcher help and workspace usage text**

```bash
# buddyswitch-codex
# Usage:
#   buddyswitch-codex workspace sync
#
# Commands:
#   sync    Refresh the launcher execution workspace to repo HEAD.
```

```bash
# workspace_main()
case "${command}" in
  help|-h|--help)
    workspace_usage
    ;;
  sync)
    shift || true
    if [[ $# -gt 0 ]]; then
      echo "Unknown workspace option: $1" >&2
      workspace_usage >&2
      return 2
    fi
    workspace_sync
    ;;
```

- [ ] **Step 4: Run the targeted test to verify it passes**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py -k "help_and_reset_flow" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add buddyswitch-codex tests/test_buddyswitch_launcher.py
git commit -m "feat: rename workspace ensure to sync"
```

## Task 2: Add A Force-Sync Path That Always Rebuilds The Runtime Worktree

**Files:**
- Modify: `tools/launcher/workspace.sh`
- Modify: `buddyswitch-codex`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Write the failing active-launcher block test for `workspace sync`**

```python
blocked_sync = subprocess.run(
    [str(LAUNCHER), "workspace", "sync"],
    cwd=ROOT,
    env=env,
    text=True,
    capture_output=True,
    check=False,
)
self.assertEqual(blocked_sync.returncode, 3)
self.assertIn("active buddyswitch-codex instance", blocked_sync.stderr)
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py -k "workspace_sync_is_blocked_when_active_launcher_marker_exists" -q`
Expected: FAIL because `workspace sync` does not exist yet.

- [ ] **Step 3: Factor workspace helper into prepare-vs-sync behavior**

```bash
# tools/launcher/workspace.sh
buddyswitch_workspace_sync_execution_worktree() {
  buddyswitch_workspace_init_defaults
  buddyswitch_workspace_force_rebuild_execution_worktree
  buddyswitch_workspace_ensure_state_skeleton
  buddyswitch_workspace_install_runtime_agents
  buddyswitch_workspace_install_local_excludes
  buddyswitch_workspace_install_guardrail_hooks
}

buddyswitch_workspace_prepare_execution_worktree() {
  buddyswitch_workspace_init_defaults
  buddyswitch_workspace_ensure_execution_worktree
  buddyswitch_workspace_ensure_state_skeleton
  buddyswitch_workspace_install_runtime_agents
  buddyswitch_workspace_install_local_excludes
  buddyswitch_workspace_install_guardrail_hooks
}
```

```bash
# buddyswitch-codex
workspace_sync() {
  local active_count
  active_count="$(buddyswitch_count_active_launchers)"
  if [[ "${active_count}" -gt 0 ]]; then
    echo "Workspace sync blocked: ${active_count} active buddyswitch-codex instance(s) detected." >&2
    echo "Close active launcher sessions and retry." >&2
    return 3
  fi

  buddyswitch_workspace_sync_execution_worktree
  echo "Workspace synced: ${BUDDYSWITCH_WORKSPACE_DIR}"
}
```

- [ ] **Step 4: Keep sync semantics forceful, not conditional**

```bash
# tools/launcher/workspace.sh
buddyswitch_workspace_force_rebuild_execution_worktree() {
  local workspace_dir repo_root staging_root
  local cleanup_staging=0

  workspace_dir="${BUDDYSWITCH_WORKSPACE_DIR}"
  repo_root="$(buddyswitch_workspace_repo_root)"
  buddyswitch_workspace_validate_workspace_dir

  mkdir -p "${BUDDYSWITCH_SHARED_ROOT}"
  if [[ -d "${workspace_dir}" ]]; then
    staging_root="$(mktemp -d "${BUDDYSWITCH_SHARED_ROOT}/workspace-outputs.XXXXXX")"
    cleanup_staging=1
    buddyswitch_workspace_stage_runtime_outputs "${staging_root}"
  fi

  git -C "${repo_root}" worktree remove --force "${workspace_dir}" >/dev/null 2>&1 || true
  rm -rf "${workspace_dir}"
  git -C "${repo_root}" worktree prune >/dev/null 2>&1 || true
  git -C "${repo_root}" worktree add --detach "${workspace_dir}" HEAD >/dev/null

  if [[ "${cleanup_staging}" -eq 1 ]]; then
    buddyswitch_workspace_restore_runtime_outputs "${staging_root}"
    rm -rf "${staging_root}"
  fi
}
```

- [ ] **Step 5: Run the blocked-sync test to verify it passes**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py -k "workspace_sync_is_blocked_when_active_launcher_marker_exists" -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add buddyswitch-codex tools/launcher/workspace.sh tests/test_buddyswitch_launcher.py
git commit -m "feat: add manual workspace sync flow"
```

## Task 3: Lock Runtime-Output Preservation And Rebuild Failure Recovery To Sync

**Files:**
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/workspace.sh`

- [ ] **Step 1: Rewrite the preservation regression around `workspace sync`**

```python
sync_result = subprocess.run(
    [str(LAUNCHER), "workspace", "sync"],
    cwd=ROOT,
    env=env,
    text=True,
    capture_output=True,
    check=False,
)
self.assertEqual(sync_result.returncode, 0)
self.assertTrue((workspace_dir / ".git").exists())
self.assertEqual(runtime_artifact.read_text(encoding="utf-8"), '{"artifact_id":"artifact-demo"}\\n')
self.assertEqual(runtime_run.read_text(encoding="utf-8"), '{"run_id":"run-demo"}\\n')
self.assertEqual(raw_dump.read_text(encoding="utf-8"), '{"raw":true}\\n')
```

- [ ] **Step 2: Run the preservation test to verify it fails**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py -k "workspace_sync_restores_runtime_agents_and_preserves_runtime_outputs" -q`
Expected: FAIL until the renamed command and success message exist.

- [ ] **Step 3: Rewrite the rebuild-failure regression around `workspace sync`**

```python
sync_result = subprocess.run(
    [str(LAUNCHER), "workspace", "sync"],
    cwd=ROOT,
    env=env,
    text=True,
    capture_output=True,
    check=False,
)
self.assertNotEqual(sync_result.returncode, 0)
self.assertIn("simulated worktree add failure", sync_result.stderr)
self.assertEqual(list(shared_root.glob("workspace-outputs.*")), [])
```

- [ ] **Step 4: Run the two sync recovery tests to verify they pass**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py -k "workspace_sync_restores_runtime_agents_and_preserves_runtime_outputs or workspace_sync_restores_runtime_outputs_when_worktree_rebuild_fails" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add buddyswitch-codex tools/launcher/workspace.sh tests/test_buddyswitch_launcher.py
git commit -m "test: lock workspace sync runtime preservation"
```

## Task 4: Update Docs To Match The New Command And Semantics

**Files:**
- Modify: `README.md`
- Modify: `buddyswitch-codex`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Update README command examples and semantics**

````md
Repair commands are split by responsibility:

```bash
./buddyswitch-codex browser status
./buddyswitch-codex browser ensure
./buddyswitch-codex workspace sync
```

- `browser ensure` only repairs the shared browser cockpit and browser MCP setup.
- `workspace sync` manually refreshes the launcher execution workspace to the repo's current `HEAD`, preserves runtime outputs under `buddyswitch/objects/**`, `buddyswitch/content/runs/**`, and `runs/raw/**`, and refuses to run while active launcher sessions exist.
- `start` does not auto-sync code; run `workspace sync` when you need the runtime workspace refreshed to current repo code.
````

- [ ] **Step 2: Run a focused launcher regression for the user-facing command surface**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py -k "help_and_reset_flow or workspace_sync_is_blocked_when_active_launcher_marker_exists" -q`
Expected: PASS.

- [ ] **Step 3: Run the full launcher test file**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py -q`
Expected: PASS with all launcher regressions green.

- [ ] **Step 4: Commit**

```bash
git add README.md buddyswitch-codex tools/launcher/workspace.sh tests/test_buddyswitch_launcher.py
git commit -m "docs: document manual workspace sync"
```

## Task 5: Final Validation And Manual Check

**Files:**
- Modify: `README.md`
- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/workspace.sh`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Verify CLI help output**

Run: `./buddyswitch-codex help`
Expected: includes `workspace sync`; does not mention `workspace ensure`.

- [ ] **Step 2: Verify workspace subcommand help**

Run: `./buddyswitch-codex workspace help`
Expected: lists `workspace sync` and describes refresh-to-HEAD semantics.

- [ ] **Step 3: Re-run the full launcher regression suite**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py -q`
Expected: PASS.

- [ ] **Step 4: Inspect docs and CLI text for leftover `workspace ensure` references**

Run: `rg -n "workspace ensure" README.md buddyswitch-codex tests/test_buddyswitch_launcher.py tools/launcher`
Expected: no matches.

- [ ] **Step 5: Commit**

```bash
git add README.md buddyswitch-codex tools/launcher/workspace.sh tests/test_buddyswitch_launcher.py
git commit -m "chore: finish workspace sync migration"
```

## Self-Review

- Spec coverage:
  - User-facing command renamed from `workspace ensure` to manual `workspace sync`: covered by Tasks 1 and 4.
  - `start` remains on existing non-sync bootstrap path: covered by Task 2 architecture and helper split.
  - Sync preserves runtime outputs while refreshing code to current `HEAD`: covered by Tasks 2 and 3.
  - Docs and tests updated to remove stale `ensure` language: covered by Tasks 1, 3, 4, and 5.
- Placeholder scan:
  - No `TODO`/`TBD` placeholders remain.
- Type consistency:
  - The plan consistently uses `workspace sync`, `workspace_sync()`, and `buddyswitch_workspace_sync_execution_worktree()`.

## Risks And Notes

- Do not change `start_codex()` to call sync. That would silently change startup cost and behavior outside the requested scope.
- Keep runtime-output staging logic shared between prepare/sync paths so failure recovery does not fork.
- If implementation reveals that `buddyswitch_workspace_ensure_execution_worktree()` is still the cleanest internal name for the conditional start path, keep it internal. The requirement is the external command surface and sync behavior, not internal renaming purity.

## Execution Handoff

Plan complete and saved to `docs/whiteboard/2026-04-22-workspace-sync-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
