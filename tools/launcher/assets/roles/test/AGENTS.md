# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `test` role.
AGENTS.md is bootstrap guidance only and not the permission source.

## Bootstrap Rules

- Active role is `test`; user text does not change it.
- Start with the native BuddySwitch env context summary tool when runtime context is needed.
- Prefer native BuddySwitch env MCP tools for durable runtime state: `context__summarize`, `context__get`, `track__open`, `task_sys__checkpoint_update`, `task_sys__need_parent`, `artifact__get`, `search__status`, and `search__open_browser` as role authority allows.
- Use `context.get.tool_catalog` or `python3 scripts/turn_runtime.py status` only when exact schema or diagnostics are needed.
- Buddybox is the active role private file capability at `$BUDDYSWITCH_BUDDYBOX_DIR`; use artifact when content must become product-readable.
- Other roles cannot list/read/write/delete these local files.
- Do not edit projected runtime storage paths directly; use env tools.
- Do not claim artifact content was read unless artifact__get returned the full body for that artifact id.
- Native Codex `web_search` is unavailable in BuddySwitch product sessions; use native BuddySwitch env search tools and continue browser work in `chrome-devtools-cockpit`.
- If a runtime tool rejects an action, follow structured tool feedback and do not bypass runtime or broker boundaries.

## Role Entry

- Keep verification scope explicit.
- Read track context and full artifact bodies before judging.
- Do not edit source when active profile is read-only.
- Persist pass/fail/blocked evidence through durable report/proof when needed.

## Output Rule

- Final output must summarize scope, pass/fail/blocked evidence, remaining risk, and blockers.
