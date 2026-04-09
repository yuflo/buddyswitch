# Case 09: Track Object Lifecycle

## Intent

Validate PM track-manager core operations and artifact auto-register behavior.

## Preconditions

- `scripts/switch_runtime.py` exists.
- `scripts/env_tracks.py` exists (manual inspection only).
- `scripts/env_artifacts.py` exists (manual inspection only).
- `framework/docs/track-registry.md` exists.
- `buddyswitch/objects/tracks/` and `buddyswitch/objects/artifacts/` are writable.

## Manual Steps

1. PM creates track:
   - `python3 scripts/switch_runtime.py execute "switch pm: create demo track"`
2. Non-PM artifact create with context track:
   - `python3 scripts/switch_runtime.py execute "switch market: continue track-demo track and produce market evidence"`
3. Verify track shows attached artifact id:
   - `python3 scripts/env_tracks.py show track-demo`
4. Verify PM can advance track:
   - `python3 scripts/switch_runtime.py execute "switch pm: advance track-demo track status done next_buddy test"`
5. Verify PM can list/read/archive:
   - `python3 scripts/switch_runtime.py execute "switch pm: list tracks"`
   - `python3 scripts/switch_runtime.py execute "switch pm: read track-demo track"`
   - `python3 scripts/switch_runtime.py execute "switch pm: archive track-demo track"`

## Pass Criteria

- PM can run core operations through `track-manager` runtime flow.
- Non-PM artifact with `context_track_id` auto-registers into `artifact_ids`.
- Object files are persisted under `buddyswitch/objects/`.

## Fail Signals

- Non-PM can mutate track lifecycle fields.
- Artifact `context_track_id` does not attach to track.
- Track state depends on legacy registry script.
