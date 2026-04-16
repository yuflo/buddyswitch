# Market Research Cockpit

## Purpose

Define the shared execution contract for market research skills without changing BuddySwitch object authority or skill boundaries.

`prepare-execution` materializes a `selected_skill_packet` whose injected instructions and execution constraints make browser-first behavior explicit to the host.
BuddySwitch does not open browser tools itself; it remains the control layer while the host stays the only executor.

## Per-Run Contract

- The host chooses exactly one `market` `skill_id` for the run.
- The host calls `prepare-execution` to materialize `selected_skill_packet` for that selected skill.
- The host injects `selected_skill_packet.skill_instructions` and follows `selected_skill_packet.execution_steps` in order.
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

- `execution_mode = "market-browser-native"`
- `browser_mode = "headed-only"`
- `browser_profile = "shared-market"`
- `login_policy = "mandatory-takeover"`
- `fallback_policy = "no-silent-degrade"`
- `session_continuity = "shared-cockpit"`
- `evidence_capture_level = "medium"`

## Runtime Rules

1. Shared headed cockpit
- All six skills run in one shared headed cockpit profile (`shared-market`) with session continuity (`shared-cockpit`).
- The cockpit is execution-time infrastructure for browsing and evidence capture only.

2. Mandatory login takeover for critical sources
- Critical evidence sources that require login must use mandatory takeover.
- The host/user performs the takeover in the same headed session; the skill does not bypass or fake access.

3. No silent downgrade
- `no-silent-degrade` means no silent downgrade to low-density public alternatives when critical sources are blocked.
- If access is blocked, the run must explicitly record the evidence gap, impact, and next action (takeover request or unresolved risk).

4. Ordered host execution
- `selected_skill_packet.execution_steps` is the ordered runtime contract for the selected skill.
- The host may not replace that packet with manual reconstruction or ad hoc market-specific shortcuts.

## Source Of Truth Boundary

The cockpit is not a second source of truth. Canonical BuddySwitch outputs remain:

- task objects in `buddyswitch/objects/tasks/*.json`
- artifact objects in `buddyswitch/objects/artifacts/*.json`
- run audits in `buddyswitch/content/runs/*.json`

Runtime browser state, cookies, tabs, or temporary captures are execution-time only and must not be treated as canonical state.
