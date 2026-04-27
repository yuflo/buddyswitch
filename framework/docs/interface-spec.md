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

The local server serves live data at `/api/workspace`.

Canonical machine-readable contract source: `framework/contracts/workspace-projection.json`.

The exact payload shape, per-entity projection row shapes, and source mapping are frozen in that contract file.

No static snapshot fallback is supported.

Task and track projections in the panel are slot-aware:

- task view exposes current artifacts by artifact slot
- artifact lineage is represented through revision metadata
- track summaries derive "latest material" from slot-aware current artifacts

## UI Surface Boundary

The UI surfaces are:

- `framework/console/app.js`
- `projects/app/main.js`

These files are browser-layer entrypoints and must not reference runtime internals.

Runtime internals that must not be referenced from UI surfaces include:

- `env_store`
- `runtime_store.repositories`
- `runtime_store.projections`
- `switch_runtime`
- `workspace_data`

The console UI reads runtime state only from `/api/workspace`.
No direct runtime module imports, runtime object reads, or runtime write paths are allowed in browser code.

## Refresh Flow

1. Start server: `python3 scripts/serve_context_panel.py`
2. Open `http://127.0.0.1:8765/`
3. Panel auto-fetches once on load.
4. User can click `Refresh workspace` for subsequent fetches.

## Cleanup Integration

Panel can show copyable commands only:

- `./buddyswitch-codex cleanup --agent <buddy>`
- `./buddyswitch-codex cleanup --all-agents`
- `./buddyswitch-codex cleanup --project app`
- `./buddyswitch-codex cleanup --all-storage`

Commands must not include `--execute` or `--force` by default.
The cleanup command covers task objects, artifact objects, runtime files, and run audit content under `buddyswitch/content/runs/**`.
