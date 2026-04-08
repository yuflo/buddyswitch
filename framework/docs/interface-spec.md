# BuddySwitch v1 Interface Spec

## Purpose

The v1 interface is a read-only context panel for a BuddySwitch workspace.

It helps users see:
- product tracks inferred from cross-agent artifacts
- market-only research inbox items
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
- keep only local browser UI selection state, such as the currently selected track or research item

## Location

- Static interface: `framework/console/`
- Snapshot generator: `scripts/build_console_snapshot.py`
- Snapshot output: `framework/console/workspace-data.js`

The interface is intentionally not placed in `projects/app/`, because `projects/app/` is the target product code area.

## Data Model

The snapshot generator writes:

```js
window.BUDDYSWITCH_WORKSPACE = {
  generated_at: "...",
  tracks: [],
  research_inbox: [],
  summaries: []
};
```

Group detection uses artifact filenames:
- `artifacts/research/*.md`
- `artifacts/prd/*.md`
- `artifacts/design/*.md`
- `artifacts/build/*.md`
- `artifacts/test/*.md`

The directory determines the role. Filename suffixes such as `-market-research`, `-mvp`, `-spec`, `-impl`, and `-smoke` are stripped only to group obvious artifact variants.

Classification rules:
- `tracks`: any inferred group with at least one `prd`, `design`, `build`, or `test` artifact.
- `research_inbox`: inferred groups with only `research` artifacts.
- If a research artifact shares the same inferred slug as a track, it remains attached to that track as the track's research source.

Each group is marked with:
- `classification`: `track` or `research_inbox`
- `inferred`: `true`
- `inference_source`: `artifact_filename`

These groups are filename-based hints, not an explicit topic registry and not hidden agent state.

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
