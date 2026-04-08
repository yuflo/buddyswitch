# Case 08: Interface Context Panel Boundary

## Intent

Validate that the BuddySwitch interface is a read-only context panel, not an agent orchestrator.

## Commands

```bash
python3 scripts/serve_context_panel.py
```

## Preconditions

- `framework/console/index.html` exists.
- `scripts/serve_context_panel.py` exists.
- `scripts/build_console_snapshot.py` exists.

## Manual Steps

1. Run the local server command.
2. Open `http://127.0.0.1:8765/`.
3. Inspect the Tracks list, artifact timeline, Untracked Artifacts diagnostics, run summaries, suggested switch commands, and cleanup commands.
4. Click `Refresh` and confirm the page reloads current workspace data from the server.
5. Review generated cleanup commands.
6. Review `framework/docs/interface-spec.md`.

## Pass Criteria

- Local server serves `/workspace-data.js` from current workspace state.
- Static snapshot generation still creates `framework/console/workspace-data.js` for debugging.
- Snapshot data includes `tracks`, `untracked_artifacts`, and `summaries`.
- Snapshot data does not include `research_inbox`.
- Tracks come from `artifacts/workspace-registry.json`, not filename-based product inference.
- Registry-declared tracks appear under Tracks when registry data exists.
- Files under `artifacts/` that are not registry-referenced appear under Untracked Artifacts.
- If registry and artifacts are absent after full cleanup, Tracks and Untracked Artifacts are empty.
- The console shows:
  - Tracks list
  - artifact timeline
  - Untracked Artifacts diagnostics
  - run summaries
  - suggested `switch ...` commands
  - cleanup commands
- Cleanup commands do not include `--execute` or `--force` by default.
- The interface does not execute shell commands.
- The interface does not invoke any agent or LLM.
- The interface does not write repo files from the browser.
- `framework/docs/interface-spec.md` documents the read-only boundary.

## Fail Signals

- The UI directly runs cleanup or agent commands.
- The UI stores hidden agent state.
- The UI displays an Inbox or Research Inbox.
- The UI cannot refresh current workspace data through the local server.
- Cleanup commands default to destructive execution.
