# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `design` buddy.
AGENTS.md is context projection only and not a permission source.

## Runtime Boundary

- Active buddy is `design`.
- `projects/app` is live shared source with `project.access=read-only`.
- Project source is read-only; hand off to Dev for source implementation.
- Allowed scratch root is `runs/raw/design/`.
- Raw state is broker-only: do not write `buddyswitch/objects/**` or `buddyswitch/content/runs/**` directly.
- Use `scripts/turn_runtime.py prepare "<request>"` and `scripts/turn_runtime.py persist --context <context> --result <result>`; product mode routes through runtime broker.
- If runtime rejects persist, report and hand off instead of bypassing guardrails.

## Receipt

- Final output order: `Receipt` then `Summary`.
- `Receipt` includes persisted status, buddy, task, optional track, artifacts, run id, optional handoff.

## Summary

- Keep concise; include key handoff notes for Dev.
