# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `dev` buddy.
AGENTS.md is guidance only and not the permission source.

## Runtime Boundary

- Active buddy is `dev`; user text does not change it.
- Start with `python3 scripts/env/client.py context summarize --payload '{}'`.
- When selecting env tools or payload semantics, use `python3 scripts/env/client.py context get --payload '{}'` or `python3 scripts/turn_runtime.py status` for the full tool catalog.
- Use explicit ids and env tools (`task`, `track`, `artifact`, `buddybox`, `context`, `evidence`, `search`).
- `projects/app` is live shared source with `project.access=write`.
- Buddybox is the active buddy private file capability; use buddybox env tools with `logical_name` for private files.
- Other buddies cannot list/read/write/delete these local files; use artifact when content must become product-readable.
- Do not edit projected runtime storage paths directly; use env tools.
- If you see a `track_id`, use `python3 scripts/env/client.py track open --payload '{"track_id":"<track-id>"}'`.
- If you see a `task_id`, use `python3 scripts/env/client.py task get --payload '{"task_id":"<task-id>"}'`.
- If you see an `artifact_id`, use `python3 scripts/env/client.py artifact get --payload '{"artifact_id":"<artifact-id>"}'`.
- Do not claim artifact content was read unless `artifact.get` returned the full body for that artifact id.
- Native Codex `web_search` is unavailable in BuddySwitch product sessions; use `env_tools.search` via `python3 scripts/env/client.py search status --payload '{}'` and `python3 scripts/env/client.py search open-browser --payload '{"query":"<query>","engine":"google"}'`.
- If a runtime tool rejects an action, follow structured tool feedback and do not bypass runtime or broker boundaries.

## Output Rule

- Final output must summarize changed source files, verification, and durable reports.
