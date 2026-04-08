# BuddySwitch v1 Interface Spec

## Purpose

The v1 interface is a read-only context panel for a BuddySwitch workspace.

It helps users see:
- product tracks declared in the workspace registry
- untracked artifact diagnostics
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
- show artifact and summary metadata from a generated snapshot
- generate suggested commands for manual CLI use
- keep only local browser UI selection state, such as the currently selected track

## Location

- Static interface: `framework/console/`
- Snapshot generator: `scripts/build_console_snapshot.py`
- Snapshot output: `framework/console/workspace-data.js`
- Track registry: `artifacts/workspace-registry.json`

The interface is intentionally not placed in `projects/app/`, because `projects/app/` is the target product code area.

## Data Model

The snapshot generator writes:

```js
window.BUDDYSWITCH_WORKSPACE = {
  generated_at: "...",
  registry_path: "artifacts/workspace-registry.json",
  project: {},
  tracks: [],
  untracked_artifacts: [],
  summaries: []
};
```

Tracks are declared in `artifacts/workspace-registry.json`. The registry is the durable project state for product iteration records:

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

Files not referenced by any registry track are listed in `untracked_artifacts`. They are diagnostics only, not a product queue.

Track creation and artifact association must be explicit. Agents may suggest `track_id`, `title`, `role`, `type`, and `state`, but must not create tracks only from their own judgment.

## Refresh Workflow

Run:

```bash
python3 scripts/build_console_snapshot.py
```

Then open or refresh:

```text
framework/console/index.html
```

No local server is required for v1 because the interface loads `workspace-data.js` as a script instead of fetching JSON.

## Cleanup Integration

Cleanup is command-level only. The interface shows copyable commands such as:

```bash
scripts/cleanup_buddyswitch.sh --agent market
scripts/cleanup_buddyswitch.sh --all-agents
scripts/cleanup_buddyswitch.sh --project app
scripts/cleanup_buddyswitch.sh --all-storage
```

Generated cleanup commands must not include `--execute` or `--force` by default.
