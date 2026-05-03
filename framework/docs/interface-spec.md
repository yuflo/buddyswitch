# BuddySwitch Context Panel Interface Spec

## Purpose

The context panel is a read-only workspace viewer for:

- track objects
- task objects
- artifact objects
- run audits
- next-step state summaries

## Boundary

The interface must not:

- invoke buddies
- call LLMs
- execute shell commands
- execute cleanup commands
- write repository files from browser code

## Data Source

Live data endpoint: `/api/workspace`.
Canonical contract: `framework/contracts/workspace-projection.json`.

No static snapshot fallback is supported.

Task and track projections are slot-aware:

- task view exposes current artifacts by slot
- artifact lineage uses revision metadata
- track summaries derive latest material from current slot artifacts

## UI Surface Boundary

UI surfaces:

- `framework/console/app.js`
- `projects/app/main.js`

These browser entrypoints must not reference runtime internals.
Runtime internals that must not be referenced from UI surfaces include:

- `env_store`
- `runtime_store.repositories`
- `runtime_store.projections`
- `turn_runtime`
- `workspace_data`

Console UI reads runtime state only from `/api/workspace`.
No direct runtime module imports, runtime object reads, or runtime write paths are allowed in browser code.

## Refresh Flow

1. Start server: `python3 scripts/serve_context_panel.py`
2. Open `http://127.0.0.1:8765/`
3. Panel auto-fetches on load
4. User can click `Refresh workspace`

## Cleanup Integration

Panel may show cleanup commands only:

- `./buddyswitch-codex data cleanup --buddy <buddy>`
- `./buddyswitch-codex data cleanup --all-data`

Commands must not include `--yes` by default.
