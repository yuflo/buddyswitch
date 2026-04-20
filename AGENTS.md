# BuddySwitch Development Workspace

This repo root is for developing BuddySwitch itself.

- Use `codex` here when you are editing BuddySwitch source, tests, docs, or launcher code.
- `./buddyswitch-codex start` does not run Codex from this checkout; it launches from a launcher-managed execution worktree under `${BUDDYSWITCH_SHARED_ROOT}/workspace`.
- The execution worktree carries the full runtime BuddySwitch contract in `tools/launcher/assets/runtime-AGENTS.md`.
- Runtime BuddySwitch state is not maintained as tracked skeleton directories in the main checkout.

## Canonical Sources

- Env manifest: `buddyswitch/manifest.toml`
- Runtime state paths inside the execution worktree:
  - `buddyswitch/objects/tracks/*.json`
  - `buddyswitch/objects/tasks/*.json`
  - `buddyswitch/objects/artifacts/*.json`
  - `buddyswitch/content/runs/*.json`
  - `runs/raw/`
  - `projects/app/.runtime/`
- Read-only context panel server: `python3 scripts/serve_context_panel.py`
- Main app code: `projects/app/`

## Development Notes

- Keep repo-root work focused on BuddySwitch source, tests, docs, launcher behavior, and framework contracts.
- Use `codex` in this checkout for development mode.
- Use `./buddyswitch-codex start` when you need a launcher-managed product-mode runtime session.
