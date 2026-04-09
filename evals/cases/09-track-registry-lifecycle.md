# Case 09: Track Object Lifecycle

## Intent

Validate explicit track control by PM and artifact auto-register behavior.

## Preconditions

- `scripts/env_tracks.py` exists.
- `scripts/env_artifacts.py` exists.
- `framework/docs/track-registry.md` exists.
- `buddyswitch/objects/tracks/` and `buddyswitch/objects/artifacts/` are writable.

## Manual Steps

1. PM creates track:
   - `python3 scripts/env_tracks.py create demo-track --title "Demo Track" --actor pm`
2. Non-PM artifact create with context track:
   - `python3 scripts/env_artifacts.py create --artifact-id art-demo-market --title "Demo Market" --kind research --path artifacts/art-demo-market--demo-market.md --producer-buddy market --source-skill research-scan --context-track-id demo-track --actor market`
3. Verify track shows attached artifact id:
   - `python3 scripts/env_tracks.py show demo-track --actor pm`
4. Verify non-PM cannot advance track:
   - `python3 scripts/env_tracks.py advance demo-track --status done --actor market`
5. Verify PM can advance track:
   - `python3 scripts/env_tracks.py advance demo-track --status done --actor pm`

## Pass Criteria

- PM can create and advance tracks.
- Non-PM artifact with `context_track_id` auto-registers into `artifact_ids`.
- Non-PM direct track advance is rejected.
- Object files are persisted under `buddyswitch/objects/`.

## Fail Signals

- Non-PM can mutate track lifecycle fields.
- Artifact `context_track_id` does not attach to track.
- Track state depends on legacy registry script.
