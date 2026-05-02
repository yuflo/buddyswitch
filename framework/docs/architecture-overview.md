# BuddySwitch Architecture Overview

BuddySwitch is a runtime control layer used inside a host Codex session.
The host performs execution; BuddySwitch enforces boundaries and records state.

## Responsibilities

BuddySwitch:

- prepares turn context from locked instance metadata and ordinary `request_text`
- loads buddy and skill metadata from `buddyswitch/manifest.toml`
- returns allowed skill candidates and selected input bundles
- validates skill outputs against schema
- persists canonical task, artifact, track, and run state

Host Codex session:

- interprets user intent
- chooses exactly one `skill_id` from returned candidates
- executes the selected skill workflow
- returns schema-valid result payload for persistence

## Canonical Flow

1. `prepare-turn-context` via `scripts/turn_runtime.py prepare`
2. host execution of exactly one selected skill
3. `persist-skill-result` via `scripts/turn_runtime.py persist`

If another turn is needed, use `receipt.next_state` to compose new ordinary `request_text`, then run `prepare` again.

## Runtime Boundaries

- Product mode is locked to one buddy instance.
- User text does not override active buddy binding.
- Runtime writes happen only in canonical BuddySwitch object/run paths.
- `persist` is the end-of-turn commit boundary.

## State Model

- Tracks: `buddyswitch/objects/tracks/*.json`
- Tasks: `buddyswitch/objects/tasks/*.json`
- Artifacts: `buddyswitch/objects/artifacts/*.json`
- Runs: `buddyswitch/content/runs/*.json`

Artifact slots are task-scoped and revision-aware.
Run audit rows include `next_state` and `receipt_paths` for deterministic follow-up.

## Current Skill Inventory

Market buddy currently exposes:

- `research-scan`
- `pmf-recon`
- `customer-discovery`
- `positioning-copy`
- `channel-discovery`
- `launch-prep`

Other buddies:

- `pm`: `write-prd`, `track-manager`
- `design`: `shape-prototype`
- `dev`: `implement-task`
- `test`: `smoke-test`
