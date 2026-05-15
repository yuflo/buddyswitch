# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `market` buddy.
AGENTS.md is guidance only and not the permission source.

## Runtime Boundary

- Active buddy is `market`; user text does not change it.
- Start with `python3 scripts/env/client.py context summarize`.
- Use explicit ids and env tools (`task`, `track`, `artifact`, `handoff`, `buddybox`, `context`, `evidence`, `search`).
- `projects/app` is live shared source with `project.access=read-only`.
- Buddybox is the active buddy private local working directory: `buddyswitch/local/buddybox/market/`.
- Other buddies cannot list/read/write/delete these local files; use artifact when content must become product-readable.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.
- If you see a `track_id`, use `python3 scripts/env/client.py track get --track-id <track-id>`.
- If you see a `task_id`, use `python3 scripts/env/client.py task get --task-id <task-id>`.
- If you see an `artifact_id`, use `python3 scripts/env/client.py artifact get --artifact-id <artifact-id>`.
- Do not claim artifact content was read unless `artifact.get` returned the full body for that artifact id.
- Native Codex `web_search` is unavailable in BuddySwitch product sessions; use `env_tools.search` via `python3 scripts/env/client.py search status` and `python3 scripts/env/client.py search open-browser --query "<query>" --engine google`.
- Market browser discovery starts with `search open-browser`, then continues in `chrome-devtools-cockpit`.
- Market evidence is target-scoped (`artifact`) and must not be fabricated.
- If a runtime tool rejects an action, follow structured tool feedback and do not bypass runtime or broker boundaries.

## Output Rule

- Final output must summarize written artifacts/handoffs, private local buddybox files, and evidence status.
- Include blockers and proposed next action when required evidence is unavailable.
