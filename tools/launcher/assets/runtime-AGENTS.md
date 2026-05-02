# BuddySwitch Runtime Workspace

This workspace is launcher-owned and runtime-only.

Use it only for active BuddySwitch runs and runtime state inspection.
Do not treat this worktree as a development checkout and do not commit from it.

## Product-Mode Input Contract

Product-mode users send ordinary requests.
The active buddy comes from launcher session metadata (`BUDDYSWITCH_ACTIVE_BUDDY`, `BUDDYSWITCH_INSTANCE_ID`, and `BUDDYSWITCH_INSTANCE_JSON`).
User-authored command-shaped routing input is rejected before runtime state writes.

## Source Of Truth

- Env manifest: `buddyswitch/manifest.toml`
- Track objects: `buddyswitch/objects/tracks/*.json`
- Task objects: `buddyswitch/objects/tasks/*.json`
- Artifact objects: `buddyswitch/objects/artifacts/*.json`
- Run audit content: `buddyswitch/content/runs/*.json`

## Required Behavior

1. Prepare through `scripts/turn_runtime.py prepare` as `prepare-turn-context` to get `prepare_context`, including `request_text`, `skills`, `inputs_by_skill`, `task_context`, `track_context`, and a reserved run envelope.
2. Choose exactly one `skill_id` from `prepare_context.skills`.
3. Selected-skill preflight:
   - Treat selected skill `host_execution` and `tool_scope` as preflight instructions before tool invocation.
   - `required_tools` and `required_env` remain advisory host readiness metadata.
   - Browser-native execution metadata remains fail-closed unless explicit user approval widens tool scope.
4. Execute the selected skill in-session and produce structured output matching the selected skill output schema.
5. Persist through `scripts/turn_runtime.py persist` as the CLI wrapper for `persist-skill-result` whenever BuddySwitch state should be committed.
6. Check `refreshed_context.ok`; successful persist does not reserve a follow-up run. If another turn is needed, derive the next `request_text` from `receipt.next_state`, then rerun `prepare`.
7. BuddySwitch stays the control layer; host execution happens in the Codex session.
8. Render terminal final output in two sections, in this exact order: `Receipt -> Summary`.

## Receipt Contract

- `Persisted: ok|failed`
- `Task: <task_title> [<task_id>]` (required)
- `Track: <track_title> [<track_id>]` (show only when track exists)
- `Artifact: <artifact_id|none>`
- `Run: <run_id>` (required)
- `Related Runs: <run_id_1>, <run_id_2>` (optional)

## Summary Contract

- Keep execution summary to 1-2 lines.
- Keep open questions to at most 4 items.
- Keep object paths as debug details, not lead user-facing content.

## Context Panel Rules

- `framework/console/` is read-only and uses live `/api/workspace` data.
- Interface must not invoke buddies, LLMs, cleanup, or hidden state writes.
- Refresh by running `python3 scripts/serve_context_panel.py` and clicking `Refresh workspace`.

## File Placement

- Run audit content: `buddyswitch/content/runs/`
- Raw dumps: `runs/raw/`
- Track objects: `buddyswitch/objects/tracks/*.json`
- Task objects: `buddyswitch/objects/tasks/*.json`
- Artifact objects: `buddyswitch/objects/artifacts/*.json`

## Project Code Location

Main app code is edited via relative `projects/app` from the instance runtime workspace.
Launcher projects that path to shared product source (`${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}` debug context).
