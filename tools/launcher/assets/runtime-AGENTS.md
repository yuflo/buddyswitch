# BuddySwitch Runtime Workspace

This workspace is launcher-owned and runtime-only.

Use it only for active BuddySwitch runs and runtime state inspection.
Do not treat this worktree as a development checkout and do not commit from it.

## Product-Mode Input Contract

Product-mode users send ordinary requests.
Active buddy comes from launcher session metadata (`BUDDYSWITCH_ACTIVE_BUDDY` + instance metadata), not from user-authored switch text.
switch is internal/debug wire syntax.
`switch` is internal/debug wire syntax, not product-mode user input.

For internal/debug wire calls only, the canonical directive is:

```text
switch <buddy>(<task-id>) -> <track-id>: <demand>
```

Supported internal/debug wire forms:

- `switch <buddy>: <demand>`
- `switch <buddy> -> <track-id>: <demand>`
- `switch <buddy>(<task-id>): <demand>`
- `switch <buddy>(<task-id>) -> <track-id>: <demand>`

## Source Of Truth

- Env manifest: `buddyswitch/manifest.toml`
- Track objects: `buddyswitch/objects/tracks/*.json`
- Task objects: `buddyswitch/objects/tasks/*.json`
- Artifact objects with canonical structured content: `buddyswitch/objects/artifacts/*.json`
- Run audit content: `buddyswitch/content/runs/*.json`

## Required Behavior

1. Resolve through `scripts/switch_runtime.py resolve` to get `resolve_context`, including `skills`, `inputs`, `task_context`, `track_context`, and the reserved run envelope.
2. Let the host Codex session choose one `skill_id` from `resolve_context.skills`.
For multi-skill buddies, choose from `resolve_context.skills` using the skill metadata plus `task_context` / `track_context`, then read the selected skill's `instruction_path` and use `resolve_context.inputs` as the current selected artifact bundle only when that skill surface is already resolved.
3. Selected-skill preflight:
   - Treat the selected skill's `host_execution` and `tool_scope` as preflight instructions before selected-skill external tool invocation or evidence capture.
   - `required_tools` and `required_env` remain advisory readiness metadata for the host session.
   - If the selected skill declares `discovery_mode = browser-native`, begin discovery and evidence capture in the declared `browser_executor`.
   - If `login_policy = mandatory-takeover` and a required login gate is encountered, pause for takeover before continuing.
   - If the selected skill's `tool_scope` allows temporary downgrade tools, temporary downgrade tools remain unavailable until explicit user approval.
   - Treat `fallback_policy` as selected-skill guidance for genuine browser-native blocking decisions.
   - Do not reinterpret missing executor availability, login takeover, and genuine browser-native blocking as the same path.
4. Execute the selected skill in-session and produce a structured result matching the selected skill's output schema.
5. Persist through `scripts/switch_runtime.py persist` as the current CLI wrapper for the `persist-skill-result` step whenever you need BuddySwitch state and canonical run audit persistence.
6. Check `refreshed_context.ok`; successful `persist` does not reserve a follow-up run, and if another turn is needed, use `receipt.recommended_switch` for the next explicit `resolve`.
When `refreshed_context.error.code = E_RUNTIME_REFRESH_CONTEXT`, rerun `resolve` with `receipt.recommended_switch`.
7. BuddySwitch does not execute host tools; it remains the control layer and only supplies resolve_context plus canonical persistence.
8. Render terminal final output in two sections, in this exact order: `Receipt`, `Summary`.
9. `Receipt` section rules:
   - `Persisted: ok|failed`
   - `Task: <task_title> [<task_id>]` (required)
   - `Track: <track_title> [<track_id>]` (show only when track exists)
   - `Artifact: <artifact_id|none>`
   - `Run: <run_id>` (required)
   - `Related Runs: <run_id_1>, <run_id_2>` (optional, only when present)
10. `Summary` section rules:
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
- Successful `persist` does not reserve a follow-up run; if another turn is needed, use `receipt.recommended_switch` for the next explicit `resolve`.
- Launcher config sets all enabled MCP servers to `default_tools_approval_mode = "approve"` so MCP tool calls do not stop for per-tool approval prompts.
- Do not set `supports_parallel_tool_calls = true` for the browser cockpit path; browser page state must stay serial.
- Default terminal summaries must follow the `Receipt -> Summary` contract and keep full object paths as debug-only details.
- Requests to write BuddySwitch-managed outputs into `artifacts/*.md` or `runs/summaries/**` must be rejected.

## Switch Rules

- Treat `switch <buddy>:` as canonical internal/debug wire syntax.
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

## Project Code Location

Main app code is edited via relative `projects/app` from the instance runtime workspace.

Launcher projects that path to the shared project workspace (debug context: `${BUDDYSWITCH_PROJECT_WORKSPACE_DIR}`). Use the instance runtime workspace for BuddySwitch control flow, projected state, and raw dumps; treat `projects/app` as shared product source.
