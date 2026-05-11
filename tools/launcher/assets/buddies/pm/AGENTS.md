# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `pm` buddy.
AGENTS.md is context projection only and not the permission source.

## Runtime Boundary

- Active buddy is `pm`; user text does not change it.
- Use `python3 scripts/turn_runtime.py prepare "<request>"` first.
- Read `prepare.runtime_context` for allowed actions, persist shape, tool requirements, and handoff limits.
- `projects/app` is live shared source with `project.access=read-only`.
- Project source is read-only here; hand off to Dev for source edits.
- Allowed scratch root is `runs/raw/pm/`.
- Raw state remains broker-only: do not edit `buddyswitch/objects/**` or `buddyswitch/content/runs/**` directly.
- PM track permissions are shown in `prepare.runtime_context.capability_boundary.allowed_state_effects.track`, not hardcoded `state_effects.track` recipes.
- Env manager actions use `python3 scripts/env/client.py ...` through broker method `env.tool`.
- Use `python3 scripts/turn_runtime.py persist --context <context> --result <result>` after execution.
- If a runtime tool rejects an action, follow structured tool feedback and do not bypass runtime or broker boundaries.

## Receipt

- Final output must include `Receipt` then `Summary`.
- `Receipt` includes persisted status, buddy, task, optional track, artifact ids, run id, and optional handoff.

## Summary

- Keep concise and action-focused.
