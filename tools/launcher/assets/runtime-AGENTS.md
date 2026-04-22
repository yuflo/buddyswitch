# BuddySwitch Runtime Workspace

This workspace is launcher-owned and runtime-only.

Use it only for active BuddySwitch runs and runtime state inspection.
Do not treat this worktree as a development checkout and do not commit from it.

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
- `switch pm(task-pm-ai-companion): Continue scope refinement`
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
   - `pm` controls track lifecycle (`create/update/advance/archive`)
   - other buddies can read tracks and create/update artifacts through their resolved task
   - every persisted run must belong to a task
6. Resolve through `scripts/switch_runtime.py resolve` to get `resolve_context`, including `skills`, `inputs`, `task_context`, `track_context`, and the reserved run envelope.
7. Let the host Codex session choose one `skill_id` from `resolve_context.skills`.
8. Read the selected skill's `instruction_path`, use `resolve_context.inputs` as the current selected artifact bundle only when that skill surface is already resolved, and for multi-skill buddies choose from `resolve_context.skills` using the skill metadata plus `task_context` / `track_context`. For market runs, apply `resolve_context.skills[*].host_execution` plus `resolve_context.skills[*].tool_scope` before starting browser work.
9. Execute the selected skill in-session and produce a structured result matching the selected skill's output schema.
10. Persist through `scripts/switch_runtime.py persist` as the current CLI wrapper for the `persist-skill-result` step whenever you need BuddySwitch state and canonical run audit persistence.
11. Continue from `refreshed_context` when another buddy turn is needed after a successful persist.
12. BuddySwitch does not execute host tools; it remains the control layer and only supplies resolve_context plus canonical persistence.
13. Render terminal final output in three sections, in this exact order: `Receipt`, `Commands`, `Summary`.
14. `Receipt` section rules:
    - `Persisted: ok|failed`
    - `Task: <task_title> [<task_id>]` (required)
    - `Track: <track_title> [<track_id>]` (show only when track exists)
    - `Artifact: <artifact_id|none>`
    - `Run: <run_id>` (required)
    - `Related Runs: <run_id_1>, <run_id_2>` (optional, only when present)
15. `Commands` section rules:
    - Show one `Template:` command from `reference_switches`:
      - use `continue_current_task_in_track` when present, otherwise `continue_current_task`
    - Show one `Recommended:` command:
      - prefer `handoff_to_next_buddy`, else `continue_current_task_in_track`, else `continue_current_task`
16. `Summary` section rules:
    - Keep execution summary to 1-2 lines.
    - Open questions max 4 items.
    - Do not lead with long object path lists; object paths are debug-only details.

Default runtime behavior:

- Task object path: `buddyswitch/objects/tasks/<task-id>.json`
- Artifact object path: `buddyswitch/objects/artifacts/<artifact-id>.json`
- Run audit path: `buddyswitch/content/runs/<run-id>.json`
- Users do not need to provide output file paths.
- `resolve_context` is the canonical runtime handoff between BuddySwitch and the host session.
- `persist-skill-result` is the canonical persistence step; `scripts/switch_runtime.py persist` is its current CLI wrapper.
- `refreshed_context` is the canonical follow-up handoff after a successful persist.
- Default terminal summaries must follow the `Receipt -> Commands -> Summary` contract and keep full object paths as debug-only details.
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
