# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `test` buddy.
AGENTS.md is context projection only and not the permission source.

## Runtime Boundary

- Active buddy is `test`; user text does not change it.
- `projects/app` is live shared source with `project.access=read-only`.
- Project source is read-only; tests, fixtures, snapshots, and generated source under `projects/app` are read-only.
- Hand source fixes to Dev instead of editing source in this buddy.
- Allowed scratch root is `runs/raw/test/`.
- Raw state remains broker-only: do not edit `buddyswitch/objects/**` or `buddyswitch/content/runs/**` directly.
- Use `scripts/turn_runtime.py prepare "<request>"` and `scripts/turn_runtime.py persist --context <context> --result <result>`; product mode routes through runtime broker.

## Receipt

- Final output order is `Receipt` then `Summary`.
- `Receipt` includes persisted status, buddy, task, optional track, artifacts, run id, optional handoff.

## Summary

- Keep concise with pass/fail/blocked signals and Dev handoff when needed.
