# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `dev` buddy.
AGENTS.md is context projection only and not the permission source.

## Runtime Boundary

- Active buddy is `dev`; user text does not change it.
- Use `python3 scripts/turn_runtime.py prepare "<request>"` first.
- Read `prepare.runtime_context` for allowed actions, persist shape, tool requirements, and handoff limits.
- `projects/app` is live shared source with `project.access=write`.
- Dev can write `projects/app`; keep temporary files in `runs/raw/dev/`.
- Raw state is broker-only: do not edit `buddyswitch/objects/**` or `buddyswitch/content/runs/**` directly.
- Env manager actions use `python3 scripts/env/client.py ...` through broker method `env.tool`.
- Use `python3 scripts/turn_runtime.py persist --context <context> --result <result>` after execution.
- If a runtime tool rejects an action, follow structured tool feedback and do not bypass runtime or broker boundaries.

## Receipt

- Final output must include `Receipt` then `Summary`.
- `Receipt` includes persisted status, buddy, task, optional track, artifact ids, run id, and optional handoff.

## Summary

- Keep concise and verification-focused.
