# BuddySwitch v1 Interface Spec

## Purpose

The v1 interface is a read-only context panel for a BuddySwitch workspace.

It helps users see:
- product tracks declared in the workspace registry
- artifact inbox diagnostics for local dump files not registered to a Track
- role-specific artifact timelines
- recent run summaries
- copyable `switch ...` prompts
- copyable cleanup commands

## Boundary

The interface must not:
- invoke `market`, `pm`, `design`, `dev`, or `test`
- call Codex, Claude Code, Gemini CLI, or any LLM
- execute shell commands
- execute cleanup commands
- write repository files from the browser
- store hidden agent state

The interface may:
- show artifact and summary metadata from the live local server
- generate suggested commands for manual CLI use
- keep only local browser UI selection state, such as the currently selected track

## Location

- Static interface: `framework/console/`
- Local server: `scripts/serve_context_panel.py`
- Workspace data module: `scripts/workspace_data.py`
- Track registry: `artifacts/workspace-registry.json`

The interface is intentionally not placed in `projects/app/`, because `projects/app/` is the target product code area.

## Data Model

The local server returns the current workspace read model at `/api/workspace` by scanning local dump files and the Track Registry:

```json
{
  generated_at: "...",
  registry_path: "artifacts/workspace-registry.json",
  project: {},
  tracks: [],
  untracked_artifacts: [],
  summaries: []
};
```

Tracks are declared through the registry adapter and currently stored in `artifacts/workspace-registry.json`. The JSON file is the v1 local dump backend for product iteration records:

```json
{
  "schema_version": 1,
  "project": {"id": "buddyswitch", "name": "BuddySwitch"},
  "tracks": [
    {
      "id": "onboarding-minimal",
      "title": "Onboarding Minimal",
      "state": "active",
      "artifacts": [
        {"role": "pm", "type": "prd", "path": "artifacts/prd/onboarding-minimal.md"}
      ]
    }
  ]
}
```

Artifact scanning still covers:
- `artifacts/research/*.md`
- `artifacts/prd/*.md`
- `artifacts/design/*.md`
- `artifacts/build/*.md`
- `artifacts/test/*.md`

Files not referenced by any registry track are listed in the Artifact Inbox via `untracked_artifacts`. They are diagnostics only, not a product queue.

Track creation and artifact association must be explicit. Agents may suggest `track_id`, `title`, `role`, `type`, and `state`, but must not create tracks only from their own judgment. Registry writes should go through `scripts/registry.py`, not direct JSON editing.

## Refresh Workflow

Run the local server:

```bash
python3 scripts/serve_context_panel.py
```

Then open:

```text
http://127.0.0.1:8765/
```

Use the page's `Refresh workspace` button to reload current workspace data from the local server.

## Cleanup Integration

Cleanup is command-level only. The interface shows copyable commands such as:

```bash
scripts/cleanup_buddyswitch.sh --agent market
scripts/cleanup_buddyswitch.sh --all-agents
scripts/cleanup_buddyswitch.sh --project app
scripts/cleanup_buddyswitch.sh --all-storage
```

Generated cleanup commands must not include `--execute` or `--force` by default.

Cleanup keeps registry state aligned through `scripts/registry.py` for agent-level and all-agent cleanup. `--all-storage` removes the local registry dump.
