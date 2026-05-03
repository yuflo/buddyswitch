# Browser Cockpit

## Purpose

Define the execution contract for market research skills inside a buddy-locked instance without changing BuddySwitch object authority or skill boundaries.

`prepare_context` exposes the selected skill metadata that makes `browser-native` behavior explicit to the host.
BuddySwitch does not open browser tools itself; it remains the control layer while the host stays the only executor.

## Per-Run Contract

- The host chooses exactly one `market` `skill_id` for the run.
- The host reads market execution metadata from `prepare_context.skills[*].host_execution` for that selected skill.
- The host applies `prepare_context.skills[*].tool_scope` before any market research begins.
- The host executes the selected skill locally while treating the resolved browser rules as binding browser constraints for that chosen run.
- This cockpit contract applies to one selected skill at a time; it does not turn BuddySwitch into a multi-skill workflow engine.

## Applies To

- `research-scan`
- `pmf-recon`
- `customer-discovery`
- `positioning-copy`
- `channel-discovery`
- `launch-prep`

These six skills stay separate and keep their own output schemas, slots, and scope boundaries.

## Shared Host Execution Metadata

All six market skills must carry identical host execution metadata in `skill.toml`:

- `execution_mode = "browser-cockpit-native"`
- `browser_mode = "headed-only"`
- `browser_profile = "instance-browser"`
- `browser_executor = "chrome-devtools-cockpit"`
- `discovery_mode = "browser-native"`
- `login_policy = "mandatory-takeover"`
- `fallback_policy = "no-silent-degrade"`
- `session_continuity = "instance-cockpit"`
- `evidence_capture_level = "medium"`

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
- `prepare_context.skills[*].host_execution` carries the host-facing Chrome MCP contract (`chrome-devtools-cockpit`, `browser-native`, mandatory takeover, and no-silent-degrade).
- `prepare_context.skills[*].tool_scope` carries the allowed tool-server scope for the run.
- For `market-browser-native`, discovery starts with `chrome-devtools-cockpit`; browser-external search is outside the default scope unless an explicit `user-approved` one-off downgrade is granted.
- The selected skill metadata is the host-facing browser contract for the chosen run; it does not imply that top-level `prepare_context.inputs` is already populated before skill choice in a multi-skill prepare.
- The host may not replace that resolved contract with manual reconstruction or ad hoc market-specific shortcuts.

## Cockpit Bootstrap

- Preferred product-mode path: run `./buddyswitch-codex instance start --buddy <buddy>`.
- Buddy-locked `instance start` bootstraps the active instance home, ensures the instance-bound headed cockpit endpoint, ensures `chrome-devtools-cockpit`, and then launches Codex.
- The launcher patches all enabled MCP servers with `default_tools_approval_mode = "approve"` to keep product-mode runs moving without per-tool MCP approval prompts.
- Do not set `supports_parallel_tool_calls = true` for the browser cockpit path; browser pages, active tabs, login state, and DOM reads are shared state and must stay serial.
- `./buddyswitch-codex env browser status` and `./buddyswitch-codex env browser ensure --instance <instance-id>` are debug or compatibility commands outside the normal buddy-locked product-mode path.

## Source Of Truth Boundary

The cockpit is not a second source of truth. Canonical BuddySwitch outputs remain:

- task objects in `buddyswitch/objects/tasks/*.json`
- artifact objects in `buddyswitch/objects/artifacts/*.json`
- run audits in `buddyswitch/content/runs/*.json`

Runtime browser state, cookies, tabs, or temporary captures are execution-time only and must not be treated as canonical state.
