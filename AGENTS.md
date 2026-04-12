# BuddySwitch Env Framework

This repository uses an env-centric BuddySwitch model.

## Canonical UI

Use the canonical directive:

```text
switch <buddy>(<task-id>) -> <track-id>: <demand>
```

Supported forms:

- `switch <buddy>: <demand>`
- `switch <buddy> -> <track-id>: <demand>`
- `switch <buddy>(<task-id>): <demand>`
- `switch <buddy>(<task-id>) -> <track-id>: <demand>`

Examples:
- `switch market: Research demand for AI companion live spaces`
- `switch pm -> track-ai-companion: Define MVP scope`
- `switch design(task-design-ai-companion): Continue IA spec`
- `switch dev(task-dev-ai-companion) -> track-ai-companion: Implement the approved P0 scope in projects/app`
- `switch test: Run smoke checks for the latest implementation`

## Source Of Truth

- Env manifest: `buddyswitch/manifest.toml`
- Track objects: `buddyswitch/objects/tracks/*.json`
- Task objects: `buddyswitch/objects/tasks/*.json`
- Artifact objects with canonical structured content: `buddyswitch/objects/artifacts/*.json`
- Run audit content: `buddyswitch/content/runs/*.json`

## Required Behavior

When user sends `switch <buddy>...: <demand>`:

1. Parse the `switch` intent first. Treat the four supported forms above as canonical and tolerate minor CLI spacing variation when buddy, optional task id, optional track id, and demand remain clear.
2. Validate buddy from `buddyswitch/manifest.toml`.
3. Resolve skill runtime metadata and guidance from `buddyswitch/skills/**/SKILL.md`.
4. Use manifest scope, skills, and object authority as routing context. Treat `buddy -> skills` as the main runtime routing authority. Treat `permissions` as object-authority metadata for manual/debug mutation APIs. Keep runtime validation focused on successful resolution and safe persistence.
5. Respect object authority:
   - `pm` controls track lifecycle (`create/read/list/update/advance/archive`)
   - other buddies can read tracks and create/update artifacts through their resolved task
   - every persisted run must belong to a task
6. Resolve through `scripts/switch_runtime.py resolve` to get `eligible_skills`, skill cards, context, defaults, and output schema paths.
7. Let the host Codex session choose one `skill_id` from `eligible_skills`, then use `buddyswitch/skills/<buddy>/<skill>/SKILL.md`.
8. Persist through `scripts/switch_runtime.py persist` when you need BuddySwitch state and canonical run audit persistence.
9. Render terminal final output with the default concise receipt template first:
   - `Persisted: ok`
   - `Task: <task_title> [<task_id>]`
   - `Track: <track_title> [<track_id>]` (or `none`)
   - `Artifact: <artifact_id|none>`
   - `Run: <run_id>`
   - `Continue task:` followed by `reference_switches.continue_current_task`
   - Optionally include `Continue task in track:` and `Handoff in track:` when those reference switches exist.
10. After the concise receipt block, optional details may include execution summary, working notes, deliverables, and suggested next switch.

Default runtime behavior:

- Task object path: `buddyswitch/objects/tasks/<task-id>.json`
- Artifact object path: `buddyswitch/objects/artifacts/<artifact-id>.json`
- Run audit path: `buddyswitch/content/runs/<run-id>.json`
- Users do not need to provide output file paths.
- Default terminal summaries should show IDs and copy-ready switch references first; full object paths are debug details.
- Requests to write BuddySwitch-managed outputs into `artifacts/*.md` or `runs/summaries/**` must be rejected.

## Switch Rules

- Treat `switch <buddy>:` as the canonical framework directive.
- Normalize minor spacing variation before rejecting when buddy and demand are still unambiguous.
- Do not silently guess unknown buddy names.
- Do not silently reroute to a different buddy.
- Do not use multiple buddies unless the user explicitly asks.

## Context Panel Rules

- `framework/console/` is read-only and uses live `/api/workspace` data.
- Interface must not invoke buddies, LLMs, cleanup, or hidden state writes.
- Tracks come from `buddyswitch/objects/tracks/*.json`.
- Tasks come from `buddyswitch/objects/tasks/*.json`.
- Artifacts come from `buddyswitch/objects/artifacts/*.json`.
- Run history comes from `buddyswitch/content/runs/*.json`.
- Refresh by running `python3 scripts/serve_context_panel.py` and clicking `Refresh workspace`.

## File Placement

- Run audit content: `buddyswitch/content/runs/`
- Raw dumps: `runs/raw/`
- Track objects: `buddyswitch/objects/tracks/*.json`
- Task objects: `buddyswitch/objects/tasks/*.json`
- Artifact objects with canonical structured content: `buddyswitch/objects/artifacts/*.json`
- Project runtime-only temporary data: `projects/app/.runtime/`

## Project Code Location

Main app code lives in `projects/app/`.
