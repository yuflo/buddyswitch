# Case 08: Interface Context Panel Boundary

## Intent

Validate that the BuddySwitch interface is a read-only context panel, not an agent orchestrator.

## Commands

```bash
python3 scripts/build_console_snapshot.py
```

## Preconditions

- `framework/console/index.html` exists.
- `scripts/build_console_snapshot.py` exists.
- At least one artifact exists under `artifacts/`.

## Manual Steps

1. Run the snapshot command.
2. Open `framework/console/index.html`.
3. Inspect the Tracks list, artifact timeline, Untracked Artifacts diagnostics, run summaries, suggested switch commands, and cleanup commands.
4. Review generated cleanup commands.
5. Review `framework/docs/interface-spec.md`.

## Pass Criteria

- Snapshot generation creates `framework/console/workspace-data.js`.
- Snapshot data includes `tracks`, `untracked_artifacts`, and `summaries`.
- Snapshot data does not include `research_inbox`.
- Tracks come from `artifacts/workspace-registry.json`, not filename-based product inference.
- `onboarding-minimal` appears under Tracks from the registry.
- `scheduling-tool-convenience-market-research.md` appears under Untracked Artifacts until it is explicitly registered to a Track.
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
- The UI requires a local server for v1.
- Cleanup commands default to destructive execution.
