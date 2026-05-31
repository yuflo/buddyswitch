# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `market` buddy.
AGENTS.md is guidance only and not the permission source.

## Runtime Boundary

- Active buddy is `market`; user text does not change it.
- Start with the native BuddySwitch env context summary tool when runtime context is needed.
- Prefer native BuddySwitch env MCP tools for durable runtime state: `context__summarize`, `context__get`, `track__open`, `task__current`, `artifact__get`, `request__get`, `request__list`, `search__status`, and `search__open_browser` as role authority allows.
- Use `context.get.tool_catalog` or `python3 scripts/turn_runtime.py status` only when exact schema or diagnostic fallback is needed.
- Buddybox is the active buddy private file capability at `$BUDDYSWITCH_BUDDYBOX_DIR`; use artifact when content must become product-readable.
- Other buddies cannot list/read/write/delete these local files.
- Do not edit projected runtime storage paths directly; use env tools.
- Do not claim artifact content was read unless `artifact__get` returned the full body for that artifact id.
- Native Codex `web_search` is unavailable in BuddySwitch product sessions; use native `search__open_browser`, then continue in `chrome-devtools-cockpit`.
- Market evidence is target-scoped (`artifact`) and must not be fabricated.
- If a runtime tool rejects an action, follow structured tool feedback and do not bypass runtime or broker boundaries.

## Output Rule

- Final output must summarize written artifacts, private local buddybox files, and evidence status.
- Include blockers and proposed next action when required evidence is unavailable.
