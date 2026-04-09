# BuddySwitch Workspace (Env-Centric)

BuddySwitch now uses `buddyswitch/` env as the single source of truth.

## Quick Start

1. Read `AGENTS.md`.
2. Validate parser and router:
   - `python3 scripts/parse_switch.py "switch pm: create track"`
   - `python3 scripts/codex_router.py "switch pm: create track"`
3. Resolve/execute a switch directive (runtime default flow):
   - `python3 scripts/switch_runtime.py resolve "switch market: quick market research for AI scheduler landing page"`
   - `python3 scripts/switch_runtime.py execute "switch market: quick market research for AI scheduler landing page"`
4. Start Context Panel:
   - `python3 scripts/serve_context_panel.py`
5. Open:
   - `http://127.0.0.1:8765/`

## Canonical UI

`switch <buddy>: <task>`

Buddy list, scope, skills, and permissions are loaded from `buddyswitch/manifest.toml`.
Users are not required to provide output paths in task text; runtime defaults are applied automatically.

## Core Storage

- Env manifest: `buddyswitch/manifest.toml`
- Track objects: `buddyswitch/objects/tracks/*.json`
- Artifact objects: `buddyswitch/objects/artifacts/*.json`
- Artifact markdown files: `artifacts/*.md` (flat root)
- Run summaries: `runs/summaries/`
- Raw dumps: `runs/raw/`

## Env APIs

- Switch runtime (primary): `scripts/switch_runtime.py` (`resolve|execute`)
- Manifest inspection: `scripts/env_manifest.py`
- Track CRUD/advance (manual/debug): `scripts/env_tracks.py`
- Artifact CRUD/auto-register (manual/debug): `scripts/env_artifacts.py`
- Codex routing: `scripts/codex_router.py`

Example commands:

- `python3 scripts/switch_runtime.py execute "switch market: quick(2轮) market research for AI scheduler landing page"`
- `python3 scripts/switch_runtime.py execute "switch pm: create ai-scheduler-lp track"`
- `python3 scripts/switch_runtime.py execute "switch pm: attach art-ai-scheduler-lp-market to track-ai-scheduler-lp track"`

## Context Panel

The panel is read-only and serves live data from `/api/workspace`:

- tracks from `buddyswitch/objects/tracks/*.json`
- artifacts from `buddyswitch/objects/artifacts/*.json`
- artifact inbox from untracked `artifacts/*.md`
- run summaries from `runs/summaries/`

No static snapshot or fallback file is required.

## Cleanup

Manual cleanup script:

- `scripts/cleanup_buddyswitch.sh`

Defaults to dry-run. Add `--execute` to apply deletion.

Examples:

- `scripts/cleanup_buddyswitch.sh --agent market`
- `scripts/cleanup_buddyswitch.sh --all-agents`
- `scripts/cleanup_buddyswitch.sh --project app`
- `scripts/cleanup_buddyswitch.sh --all-storage`
