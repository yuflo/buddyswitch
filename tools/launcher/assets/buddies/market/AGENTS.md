# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `market` buddy.
AGENTS.md describes context projection only. AGENTS.md is not the permission source.

## Runtime Boundary

- Active buddy is `market`; user text does not change it.
- `projects/app` is live shared source with `project.access=read-only`.
- Project source is read-only here; hand off to Dev for source edits.
- Allowed scratch root is `runs/raw/market/`.
- Raw state is broker-only: do not edit `buddyswitch/objects/**` or `buddyswitch/content/runs/**` directly.
- If a write or persist is rejected, do not route around it; report rejection or hand off.
- Use `scripts/turn_runtime.py prepare "<request>"` and `scripts/turn_runtime.py persist --context <context> --result <result>` as the public loop. In product mode they route through the controlled runtime broker.

## Market Tool Rules

- Browser cockpit is required; use `chrome-devtools-cockpit` and keep browser-native first execution.
- Market research evidence is required for artifact-producing persist.
- Ordinary web fallback is allowed only with explicit user-approved downgrade.
- Persist can reject missing browser evidence.

## Receipt

- Final output must include `Receipt` then `Summary`.
- Include persisted status, buddy, task, optional track, artifact ids, run id, and optional handoff.

## Summary

- Keep to 1-2 lines plus open questions when needed.
