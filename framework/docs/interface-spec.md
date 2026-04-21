# BuddySwitch Context Panel Interface Spec

## Purpose

The context panel is a read-only workspace viewer.

It shows:

- track objects
- task objects
- artifact objects
- run audits
- copyable switch/cleanup commands

## Boundary

The interface must not:

- invoke buddies
- call LLMs
- execute shell commands
- execute cleanup commands
- write repository files from browser code

## Data Source

The local server serves live data at `/api/workspace` using:

Canonical machine-readable contract source: `framework/contracts/workspace-projection.json`.

- `buddyswitch/manifest.toml`
- `buddyswitch/objects/tracks/*.json`
- `buddyswitch/objects/tasks/*.json`
- `buddyswitch/objects/artifacts/*.json` as the artifact source of truth
- `buddyswitch/content/runs/*.json` as canonical run history

No static snapshot fallback is supported.

Task and track projections in the panel are slot-aware:

- task view exposes current artifacts by artifact slot
- artifact lineage is represented through revision metadata
- track summaries derive "latest material" from slot-aware current artifacts

## Refresh Flow

1. Start server: `python3 scripts/serve_context_panel.py`
2. Open `http://127.0.0.1:8765/`
3. Panel auto-fetches once on load.
4. User can click `Refresh workspace` for subsequent fetches.

## Cleanup Integration

Panel can show copyable commands only:

- `scripts/cleanup_buddyswitch.sh --agent <buddy>`
- `scripts/cleanup_buddyswitch.sh --all-agents`
- `scripts/cleanup_buddyswitch.sh --project app`
- `scripts/cleanup_buddyswitch.sh --all-storage`

Commands must not include `--execute` or `--force` by default.
The cleanup command covers task objects, artifact objects, runtime files, and run audit content under `buddyswitch/content/runs/**`.
