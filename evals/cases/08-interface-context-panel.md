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
3. Inspect the Tracks list, Research Inbox list, artifact timeline, run summaries, suggested switch commands, and cleanup commands.
4. Review generated cleanup commands.
5. Review `framework/docs/interface-spec.md`.

## Pass Criteria

- Snapshot generation creates `framework/console/workspace-data.js`.
- Snapshot data includes `tracks`, `research_inbox`, and `summaries`.
- Existing artifacts group into tracks and research inbox items using filename-based detection.
- `onboarding-minimal` appears under Tracks when its PRD/design/build/test artifacts exist.
- `scheduling-tool-convenience` appears under Research Inbox when only its market research artifact exists.
- The console shows:
  - Tracks list
  - Research Inbox list
  - artifact timeline
  - run summaries
  - suggested `switch ...` commands
  - cleanup commands
- A Research Inbox item suggests advancing to PM/PRD instead of presenting itself as a complete cross-agent product track.
- Cleanup commands do not include `--execute` or `--force` by default.
- The interface does not execute shell commands.
- The interface does not invoke any agent or LLM.
- The interface does not write repo files from the browser.
- `framework/docs/interface-spec.md` documents the read-only boundary.

## Fail Signals

- The UI directly runs cleanup or agent commands.
- The UI stores hidden agent state.
- The UI requires a local server for v1.
- Cleanup commands default to destructive execution.
