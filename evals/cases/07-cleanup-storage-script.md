# Case 07: Cleanup Script Safety and Scope

## Intent

Validate that BuddySwitch cleanup is manual, safe by default, and scoped to framework-external storage data only.

## Commands

```bash
scripts/cleanup_buddyswitch.sh --agent market
scripts/cleanup_buddyswitch.sh --project app
scripts/cleanup_buddyswitch.sh --all-storage
scripts/cleanup_buddyswitch.sh --agent potato
scripts/cleanup_buddyswitch.sh --agent market --all-agents
scripts/cleanup_buddyswitch.sh --all-storage --force
```

## Preconditions

- `scripts/cleanup_buddyswitch.sh` exists and is executable.
- `artifacts/workspace-registry.json` exists when the Track Registry is enabled.
- `projects/app/.runtime/.gitkeep` exists.
- `README.md` includes manual cleanup usage.

## Manual Steps

1. Run each command above.
2. Confirm default mode is dry-run (no file deletion).
3. Confirm error commands return explicit and actionable error messages.
4. Optionally run a safe execute path:
   - `scripts/cleanup_buddyswitch.sh --project app --execute --force`
5. Confirm cleanup scope does not include framework or source-code paths.

## Pass Criteria

- Script supports required targets:
  - `--agent <market|pm|design|dev|test>`
  - `--all-agents`
  - `--project app`
  - `--all-storage`
- Default behavior is preview-only.
- `--force` without `--execute` is rejected.
- Invalid agent and conflicting targets are rejected with clear messages.
- Cleanup plan and deletion candidates are limited to:
  - `artifacts/**`
  - `runs/raw/**`
  - `runs/summaries/**`
  - `projects/app/.runtime/**`
- `artifacts/workspace-registry.json` is not targeted for deletion.
- `framework/`, `.codex/`, `.agents/`, `evals/`, and `projects/app` source files are not targeted.

## Fail Signals

- Any deletion occurs without `--execute`.
- Cleanup deletes or targets `artifacts/workspace-registry.json`.
- Cleanup target set includes framework or source-code files.
- Missing required target modes.
- Errors are ambiguous or silently ignored.
