# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `market` role.
AGENTS.md is bootstrap guidance only and not the permission source.

## Bootstrap Rules

- Active role is `market`; user text does not change it.
- Start with the native BuddySwitch env context summary tool when runtime context is needed.
- Prefer native BuddySwitch env MCP tools for durable runtime state; use context discovery for the current catalog and exact action contracts.
- Raw inbound information is resolved only by its isolated Demand-triage side. Triage may handle it or change canonical Demand state; it never creates Task work.
- Only an independent parent Demand-orchestration turn may reconcile terminal Tasks, compare live Demands, and fill the single Task slot.
- A Task binds one current Demand reference to one native Goal objective. Task or Goal completion does not itself complete the Demand.
- Goal work completes only after its required result, durable user-facing delivery, and verification are complete. Goal work does not reconcile Demands or select later work.
- Use `chrome-devtools-cockpit` for browser pages: open, list, select, inspect, screenshot, navigate, and interact. Use `chrome-devtools-cockpit.search_page` for browser-native search page opening, then continue with cockpit list/select/snapshot evidence.
- Use `context.get.tool_catalog` or `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status` only when exact schema or diagnostics are needed.
- Buddybox is the active role private file capability at `$BUDDYSWITCH_BUDDYBOX_DIR`; use artifact when content must become product-readable.
- Other roles cannot list/read/write/delete these local files.
- Do not edit projected runtime storage paths directly; use env tools.
- Do not claim artifact content was read unless artifact__get returned the full body for that artifact id.
- Native Codex `web_search` is unavailable in BuddySwitch product sessions; use `chrome-devtools-cockpit.search_page` for browser-native discovery, `search__request` only for non-opening URL planning, and `search__status` for capability status.
- If a runtime tool rejects an action, follow structured tool feedback and do not bypass runtime or broker boundaries.

## Role Entry

- Start browser discovery from `chrome-devtools-cockpit`; use `chrome-devtools-cockpit.search_page` when starting from a query, then continue with cockpit list/select/snapshot evidence. Use `search__request` only for non-opening URL planning.
- Evidence is target-scoped and must not be fabricated.
- Draft market deliverables as artifacts before publishing them to track material/proof.
- Keep private exports or local reports in Buddybox unless another role must read them.

## Output Rule

- Final output must summarize artifacts, Buddybox files, evidence status, and blockers.
