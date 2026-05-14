# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `market` buddy.
AGENTS.md is context projection only and not the permission source.

## Runtime Boundary

- Active buddy is `market`; user text does not change it.
- Use `python3 scripts/turn_runtime.py prepare "<request>"` first.
- Read `prepare.runtime_context` for allowed actions, persist shape, tool requirements, and handoff limits.
- `projects/app` is live shared source with `project.access=read-only`.
- Project source is read-only here; hand off to Dev for source edits.
- Allowed scratch root is `runs/raw/market/`.
- Raw state is broker-only: do not edit `buddyswitch/objects/**` or `buddyswitch/content/runs/**` directly.
- Env tool operations use `python3 scripts/env/client.py ...` through broker method `env.tool`.
- If you see a `track_id`, use `python3 scripts/env/client.py track get --track-id <track-id>`.
- If you see a `task_id`, use `python3 scripts/env/client.py task get --task-id <task-id>`.
- If you see an `artifact_id`, use `python3 scripts/env/client.py artifact get --artifact-id <artifact-id>`.
- Do not claim artifact content was read unless `artifact.get` returned the full body for that artifact id.
- Native Codex `web_search` is unavailable in BuddySwitch product sessions; use `env_tools.search` via `python3 scripts/env/client.py search status` and `python3 scripts/env/client.py search open-browser --query "<query>" --engine google`.
- Market browser-native discovery starts with `python3 scripts/env/client.py search open-browser --query "<query>" --engine google`, then continues with page traversal in `chrome-devtools-cockpit`.
- Use `python3 scripts/turn_runtime.py persist --context <context> --result <result>` after execution.
- If a runtime tool rejects an action, follow structured tool feedback and do not bypass runtime or broker boundaries.
- Market browser and evidence policy is defined in `prepare.runtime_context.tool_requirements`.

## Receipt

- Final output must include `Receipt` then `Summary`.
- `Receipt` includes persisted status, buddy, task, optional track, artifact ids, run id, and optional handoff.

## Summary

- Keep to 1-2 lines and include blocker or handoff notes when needed.
