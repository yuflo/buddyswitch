# Case 08: Interface Context Panel Boundary

## Intent

Validate that context panel is read-only and reads from env object store.

## Commands

```bash
python3 scripts/serve_context_panel.py
```

## Preconditions

- `framework/console/index.html` exists.
- `scripts/serve_context_panel.py` exists.
- `scripts/workspace_data.py` exists.
- `buddyswitch/manifest.toml` exists.

## Manual Steps

1. Run local server.
2. Open `http://127.0.0.1:8765/`.
3. Confirm tracks, artifact timeline, artifact inbox, summaries, and command suggestions are visible.
4. Click `Refresh workspace` and verify data is re-fetched from `/api/workspace`.
5. Review `framework/docs/interface-spec.md`.

## Pass Criteria

- `/api/workspace` returns live data.
- Payload includes `tracks`, `artifacts`, `untracked_artifacts`, and `summaries`.
- Tracks come from `buddyswitch/objects/tracks/*.json`.
- Artifact metadata comes from `buddyswitch/objects/artifacts/*.json`.
- Artifact inbox comes from untracked `artifacts/*.md`.
- UI does not execute cleanup or switch commands.
- UI does not call any agent or LLM.
- UI does not write files.

## Fail Signals

- UI relies on static snapshot fallback.
- UI mutates workspace state.
- UI cannot refresh live data.
