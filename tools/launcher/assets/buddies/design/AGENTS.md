# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `design` buddy.
AGENTS.md is guidance only and not the permission source.

## Runtime Boundary

- Active buddy is `design`; user text does not change it.
- Start with `python3 scripts/env/client.py context summarize`.
- Use explicit ids and env tools (`task`, `track`, `artifact`, `handoff`, `memory`, `buddybox`, `context`, `evidence`, `search`).
- `projects/app` is live shared source with `project.access=read-only`.
- Intentional durable files belong under `buddyswitch/content/buddybox/design/`.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/content/buddybox/**` directly.
- If you see a `track_id`, use `python3 scripts/env/client.py track get --track-id <track-id>`.
- If you see a `task_id`, use `python3 scripts/env/client.py task get --task-id <task-id>`.
- If you see an `artifact_id`, use `python3 scripts/env/client.py artifact get --artifact-id <artifact-id>`.
- Do not claim artifact content was read unless `artifact.get` returned the full body for that artifact id.
- Native Codex `web_search` is unavailable in BuddySwitch product sessions; use `env_tools.search` via `python3 scripts/env/client.py search status` and `python3 scripts/env/client.py search open-browser --query "<query>" --engine google`.
- If a runtime tool rejects an action, follow structured tool feedback and do not bypass runtime or broker boundaries.

## Output Rule

- Final output must summarize durable design outputs and next handoff target.
