# BuddySwitch Architecture Overview

BuddySwitch is a runtime control layer used inside a host Codex session.
The host executes native skills; BuddySwitch enforces boundaries and persists collaboration state.

Capability source:

- Env profiles under `buddyswitch/env-profiles/*.json` are the machine-readable authority.
- `framework/contracts/buddy-env-profile.json` defines profile shape and enums.
- Runtime `AGENTS.md` is context projection only, not permission source.

## Responsibilities

BuddySwitch:

- prepares turn context from locked instance metadata and ordinary `request_text`
- loads buddy/skill metadata from `buddyswitch/manifest.toml`
- loads and validates active buddy env profile from `buddyswitch/env-profiles`
- compiles profile-derived filesystem/tool boundaries in launcher config
- reserves one run id per prepared turn
- validates buddy-run commit shape and write permissions
- persists canonical task, artifact, track, and run state

Host Codex session:

- interprets user intent
- runs one or more native skills from runtime `.agents/skills`
- integrates outputs into one buddy-run commit payload
- persists once per turn through the runtime persist boundary

## Canonical Flow

1. `prepare-turn-context` via `python3 scripts/turn_runtime.py prepare "<request>"` (product mode routed through runtime broker)
2. host execution of needed native skills inside the locked buddy session
3. `persist-buddy-run` via `python3 scripts/turn_runtime.py persist --context ... --result ...` (product mode routed through runtime broker)

If another turn is needed, use `receipt.next_state` or `receipt.handoff` to compose a new ordinary `request_text`, then run `prepare` again.

## Runtime Boundaries

- Product mode is locked to one buddy instance.
- User text does not override active buddy binding.
- Runtime broker is the only product-mode state writer.
- Env tool operations route through broker method `env.tool` and `python3 scripts/env/client.py`.
- Runtime writes happen only in canonical BuddySwitch object/run paths.
- Raw state paths are broker-only from host sandbox perspective.
- `persist` is the end-of-turn commit boundary.

## State Model

- Tracks: `buddyswitch/objects/tracks/*.json`
- Tasks: `buddyswitch/objects/tasks/*.json`
- Artifacts: `buddyswitch/objects/artifacts/*.json`
- Runs: `buddyswitch/content/runs/*.json`

Artifacts are task-scoped, keyed by buddy-level `kind`, and revisioned per `(task, kind)`.
Run audit rows include `next_state`, `handoff`, and `receipt_paths` for deterministic follow-up.

## Current Skill Inventory

Market buddy currently exposes:

- `research-scan`
- `pmf-recon`
- `customer-discovery`
- `positioning-copy`
- `channel-discovery`
- `launch-prep`
- shared `task-tool`, `track-tool`, and `artifact-tool`

Other buddies:

- `pm`: `write-prd`, plus shared `task-tool`, `track-tool`, and `artifact-tool`
- `design`: `shape-prototype`, plus shared `task-tool`, `track-tool`, and `artifact-tool`
- `dev`: `implement-task`, plus shared `task-tool`, `track-tool`, and `artifact-tool`
- `test`: `smoke-test`, plus shared `task-tool`, `track-tool`, and `artifact-tool`

Track lifecycle mutations and task-track linkage are explicit env tool actions validated against buddy permissions.
