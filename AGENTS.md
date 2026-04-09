# BuddySwitch Env Framework

This repository uses an env-centric BuddySwitch model.

## Canonical UI

Use the strict directive:

`switch <buddy>: <task>`

Examples:
- `switch market: Research demand for AI companion live spaces and write to artifacts/`
- `switch pm: Create a new track and define MVP scope`
- `switch design: Continue track context and produce IA spec artifact`
- `switch dev: Implement the approved P0 scope in projects/app`
- `switch test: Run smoke checks and write a report artifact`

## Source Of Truth

- Env manifest: `buddyswitch/manifest.toml`
- Track objects: `buddyswitch/objects/tracks/*.json`
- Artifact objects: `buddyswitch/objects/artifacts/*.json`
- Artifact content files: `artifacts/*.md` (flat root)

## Required Behavior

When user sends `switch <buddy>: <task>`:

1. Parse with strict syntax only.
2. Validate buddy from `buddyswitch/manifest.toml`.
3. Enforce that buddy's scope, skills, and object permissions from manifest.
4. Respect object authority:
   - `pm` controls track lifecycle (`create/update/advance/attach/detach`)
   - other buddies can read tracks and create/update artifacts
5. Use skill docs from `buddyswitch/skills/<buddy>/<skill>/SKILL.md`.
6. Keep outputs explicit:
   - execution summary
   - working notes
   - deliverables or changed files
   - suggested next switch (optional)

## Switch Rules

- Treat `switch <buddy>:` as a framework directive.
- Do not silently guess unknown buddy names.
- Do not silently reroute to a different buddy.
- Do not use multiple buddies unless the user explicitly asks.

## Context Panel Rules

- `framework/console/` is read-only and uses live `/api/workspace` data.
- Interface must not invoke buddies, LLMs, cleanup, or hidden state writes.
- Tracks come from `buddyswitch/objects/tracks/*.json`.
- Artifact inbox is diagnostics for `artifacts/*.md` files that are not represented by artifact objects.
- Refresh by running `python3 scripts/serve_context_panel.py` and clicking `Refresh workspace`.

## File Placement

- Artifact markdown files: `artifacts/*.md` (flat)
- Run summaries: `runs/summaries/`
- Raw dumps: `runs/raw/`
- Track objects: `buddyswitch/objects/tracks/*.json`
- Artifact objects: `buddyswitch/objects/artifacts/*.json`
- Project runtime-only temporary data: `projects/app/.runtime/`

## Project Code Location

Main app code lives in `projects/app/`.
