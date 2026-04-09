# BuddySwitch Context Panel Interface Spec

## Purpose

The context panel is a read-only workspace viewer.

It shows:

- track objects
- artifact objects
- untracked artifact files
- run summaries
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

- `buddyswitch/manifest.toml`
- `buddyswitch/objects/tracks/*.json`
- `buddyswitch/objects/artifacts/*.json`
- `artifacts/*.md`
- `runs/summaries/**/*.md`

No static snapshot fallback is supported.

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
