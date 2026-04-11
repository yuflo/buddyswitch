# BuddySwitch Env Framework

This repository uses an env-centric BuddySwitch model.

## Canonical UI

Use the canonical directive:

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
- Canonical structured content: `buddyswitch/content/**`
- Artifact markdown files: `artifacts/*.md` (flat root)

## Required Behavior

When user sends `switch <buddy>: <task>`:

1. Parse the `switch` intent first. Treat `switch <buddy>: <task>` as the canonical form and tolerate minor CLI spacing variation when buddy and task remain clear.
2. Validate buddy from `buddyswitch/manifest.toml`.
3. Resolve skill runtime metadata and guidance from `buddyswitch/skills/**/SKILL.md`.
4. Use manifest scope, skills, and object authority as routing context. Treat `buddy -> skills` as the main runtime routing authority. Treat `permissions` as object-authority metadata for manual/debug mutation APIs. Keep runtime validation focused on successful resolution and safe persistence.
5. Respect object authority:
   - `pm` controls track lifecycle (`create/read/list/update/advance/attach/detach/archive`)
   - other buddies can read tracks and create/update artifacts
6. Resolve through `scripts/switch_runtime.py resolve` to get `eligible_skills`, skill cards, context, defaults, and output schema paths.
7. Let the host Codex session choose one `skill_id` from `eligible_skills`, then use `buddyswitch/skills/<buddy>/<skill>/SKILL.md`.
8. Persist through `scripts/switch_runtime.py persist` when you need BuddySwitch state plus default artifact/summary persistence.
9. Keep outputs explicit:
   - execution summary
   - working notes
   - deliverables or changed files
   - suggested next switch (optional)

Default runtime behavior:

- Artifact path: `artifacts/<artifact-id>--<slug>.md`
- Summary path: `runs/summaries/<buddy>/<artifact-id>.md` when skill `auto_summary=true`
- Users do not need to provide output file paths unless they want explicit overrides.
- Current markdown artifacts and summaries remain the panel-facing compatibility layer.

## Switch Rules

- Treat `switch <buddy>:` as the canonical framework directive.
- Normalize minor spacing variation before rejecting when buddy and task are still unambiguous.
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
