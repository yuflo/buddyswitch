# BuddySwitch Workspace (Env-Centric)

BuddySwitch now uses `buddyswitch/` env as the single source of truth.

## Quick Start

1. Read `AGENTS.md`.
2. Validate parser and router:
   - `python3 scripts/parse_switch.py "switch pm: create track"`
   - `python3 scripts/codex_router.py "switch pm: create track"`
3. Start Context Panel:
   - `python3 scripts/serve_context_panel.py`
4. Open:
   - `http://127.0.0.1:8765/`

## Canonical UI

`switch <buddy>: <task>`

Buddy list, scope, skills, and permissions are loaded from `buddyswitch/manifest.toml`.

## Core Storage

- Env manifest: `buddyswitch/manifest.toml`
- Track objects: `buddyswitch/objects/tracks/*.json`
- Artifact objects: `buddyswitch/objects/artifacts/*.json`
- Artifact markdown files: `artifacts/*.md` (flat root)
- Run summaries: `runs/summaries/`
- Raw dumps: `runs/raw/`

## Env APIs

- Manifest inspection: `scripts/env_manifest.py`
- Track CRUD/advance: `scripts/env_tracks.py`
- Artifact CRUD/auto-register: `scripts/env_artifacts.py`
- Codex routing: `scripts/codex_router.py`

Example commands:

- `python3 scripts/env_tracks.py create onboarding-minimal --title "Onboarding Minimal" --actor pm`
- `python3 scripts/env_artifacts.py create --artifact-id art-onboarding-prd --title "Onboarding PRD" --kind prd --producer-buddy pm --source-skill write-prd --context-track-id onboarding-minimal --actor pm`
- `python3 scripts/env_tracks.py advance onboarding-minimal --next-buddy design --actor pm`

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
