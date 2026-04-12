# Case 07: Cleanup Script Safety and Scope

## Intent

Validate cleanup is manual, dry-run by default, and scoped to storage paths.

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
- `projects/app/.runtime/.gitkeep` exists.
- `README.md` includes manual cleanup usage.

## Manual Steps

1. Run each command above.
2. Confirm default mode is dry-run.
3. Confirm invalid commands fail explicitly.
4. Optionally run execute path:
   - `scripts/cleanup_buddyswitch.sh --project app --execute --force`
5. Confirm cleanup does not target framework/source-code directories.

## Pass Criteria

- Required targets are supported:
  - `--agent <buddy>`
  - `--all-agents`
  - `--project app`
  - `--all-storage`
- Default behavior is preview-only.
- `--force` without `--execute` is rejected.
- Cleanup scope is limited to:
  - `runs/raw/**`
  - `buddyswitch/content/runs/**`
  - `projects/app/.runtime/**`
  - `buddyswitch/objects/**`
- Agent/all-agent cleanup can remove artifact objects/files through `scripts/env_artifacts.py`.

## Fail Signals

- Deletion happens without `--execute`.
- Cleanup targets framework/source-code paths.
- Env object store remains stale after execute cleanup.
