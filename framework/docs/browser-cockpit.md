# Browser Cockpit

## Purpose

Define the execution contract for market research skills inside a buddy-locked instance without changing BuddySwitch object authority or skill boundaries.

Runtime instances materialize active buddy skills under `.agents/skills`.
BuddySwitch does not open browser tools itself; Codex executes native skills while BuddySwitch remains the control layer.
`prepare` provides context and run envelope only; Codex handles native skill discovery/execution.

Env profile source of truth:

- Market profile (`buddyswitch/env-profiles/market.json`) sets `browser_cockpit=required`.
- PM/Design/Dev/Test profiles set `browser_cockpit=available` (non-launch-blocking).

## Per-Run Contract

- The host may execute one or more `market` native skills within one prepared buddy run.
- Codex discovers active runtime skill packages from `.agents/skills/<skill-id>/SKILL.md`.
- Codex executes active native skill package work inside the locked buddy run while this browser contract remains the binding runtime constraint.
- This cockpit contract defines execution constraints only; persistence remains one buddy-run commit per turn.

## Applies To

- `research-scan`
- `pmf-recon`
- `customer-discovery`
- `positioning-copy`
- `channel-discovery`
- `launch-prep`

These six skills stay separate and keep their own output schemas, artifact kinds, and scope boundaries.

## Shared Runtime Contract

All six market skills use the same browser runtime contract:

- `execution_mode = "browser-cockpit-native"`
- `browser_mode = "headed-only"`
- `browser_profile = "instance-browser"`
- `browser_executor = "chrome-devtools-cockpit"`
- `discovery_mode = "browser-native"`
- `login_policy = "mandatory-takeover"`
- `fallback_policy = "no-silent-degrade"`
- `session_continuity = "instance-cockpit"`
- `evidence_capture_level = "medium"`

## Evidence Gate

- First executable proof loop is broker-issued `browser-cockpit-preflight` token.
- Market artifact-producing persist requires broker-issued token evidence, or broker-issued `approved-downgrade`.
- Approved downgrade must include explicit reason and is recorded in run audit `tool_evidence`.
- Hand-written token strings are rejected by persist validation.

## Runtime Rules

1. Instance-bound headed cockpit
- All six skills use one instance-bound headed cockpit profile (`instance-browser`) with session continuity (`instance-cockpit`) through `chrome-devtools-cockpit` for the active Buddy instance.
- Discovery is `browser-native`: search happens in the browser and continues into real result pages, details, comments, and related pages when relevant.
- The cockpit is execution-time infrastructure for browsing and evidence capture only.

2. Mandatory login takeover for critical sources
- Critical evidence sources that require login must use mandatory takeover.
- The host/user performs the takeover in the same headed session; the skill does not bypass or fake access.

3. No silent downgrade or hidden fallback
- `no-silent-degrade` means no silent downgrade to low-density public alternatives when critical sources are blocked.
- No silent search API/snippet/crawler fallback is allowed.
- If `browser-native` access is genuinely blocked, only one explicit `user-approved` one-off downgrade is allowed and must be recorded with evidence impact.

4. Ordered host execution
- For `market-browser-native`, discovery starts with `env.tool search.open_browser` (`python3 scripts/env/client.py search open-browser ...`) and then continues in `chrome-devtools-cockpit`.
- Native Codex `web_search` is outside BuddySwitch product-mode runtime surface.
- Browser-external search is outside the default scope unless an explicit `user-approved` one-off downgrade is granted.
- Active native skills used in the run are the host-facing browser contract for that run.
- The host may not replace those contracts with manual reconstruction or ad hoc market-specific shortcuts.

## Cockpit Bootstrap

- Preferred product-mode path: run `./buddyswitch-codex instance start --buddy <buddy>`.
- Buddy-locked `instance start` bootstraps the active instance home, ensures the instance-bound headed cockpit ready page, ensures `chrome-devtools-cockpit`, and then launches Codex.
- Ready page means `/json/version` is reachable and `/json/list` contains at least one usable `type=page` target.
- Usable page targets are `about:blank` (canonical) or normal `http(s)` pages; `chrome://*`, `chrome-untrusted://*`, and `devtools://*` targets (for example `chrome://intro/`) are not ready.
- If the endpoint is reachable but no usable page exists, launcher/runtime performs one `PUT /json/new?about:blank` repair attempt and re-checks `/json/list`.
- Market (`browser_cockpit=required`) treats browser bootstrap failure as launch-blocking when no ready page can be verified.
- PM/Design/Dev/Test (`browser_cockpit=available`) may continue with warning only when browser cockpit cannot be made ready.
- The launcher patches all enabled MCP servers with `default_tools_approval_mode = "approve"` to keep product-mode runs moving without per-tool MCP approval prompts.
- Do not set `supports_parallel_tool_calls = true` for the browser cockpit path; browser pages, active tabs, login state, and DOM reads are shared state and must stay serial.
- `./buddyswitch-codex env browser status` and `./buddyswitch-codex env browser ensure --instance <instance-id>` are debug or compatibility commands outside the normal buddy-locked product-mode path.

## Source Of Truth Boundary

The cockpit is not a second source of truth. Canonical BuddySwitch outputs remain:

- task objects in `buddyswitch/objects/tasks/*.json`
- artifact objects in `buddyswitch/objects/artifacts/*.json`
- run audits in `buddyswitch/content/runs/*.json`

Runtime browser state, cookies, tabs, or temporary captures are execution-time only and must not be treated as canonical state.
`env.tool search` opens discovery pages and reports capability feedback only; it does not write canonical task/artifact/run state.
