# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `pm` buddy.
AGENTS.md is context projection only, not the permission source.

## Runtime Boundary

- Active buddy is `pm`; user text does not change it.
- `projects/app` is live shared source with `project.access=read-only`.
- Project source is read-only; hand off to Dev for source edits.
- Allowed scratch root is `runs/raw/pm/`.
- Raw state remains broker-only: never edit `buddyswitch/objects/**` or `buddyswitch/content/runs/**` directly.
- PM owns track lifecycle only through `state_effects.track` in persist payloads.
- Use `scripts/turn_runtime.py prepare "<request>"` and `scripts/turn_runtime.py persist --context <context> --result <result>`; product mode routes through runtime broker.
- If persist rejects a change, do not route around the runtime tool.

## Receipt

- Final output sections are `Receipt` then `Summary`.
- `Receipt` includes persisted status, buddy, task, optional track, artifacts, run id, optional handoff.

## Summary

- Keep concise and actionable.
