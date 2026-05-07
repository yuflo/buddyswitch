# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `dev` buddy.
AGENTS.md is context projection only; permission source is env profile + runtime broker.

## Runtime Boundary

- Active buddy is `dev`.
- `projects/app` is live shared source with `project.access=write`.
- Dev can write `projects/app`; keep runtime scratch under `runs/raw/dev/`.
- Raw state is broker-only: do not edit `buddyswitch/objects/**` or `buddyswitch/content/runs/**` directly.
- Use `scripts/turn_runtime.py prepare "<request>"` and `scripts/turn_runtime.py persist --context <context> --result <result>`; product mode routes through runtime broker.
- If state writes are rejected, do not bypass persist.

## Receipt

- Final output must include `Receipt` then `Summary`.
- `Receipt` includes persisted status, buddy, task, optional track, artifacts, run id, optional handoff.

## Summary

- Keep concise and verification-focused.
