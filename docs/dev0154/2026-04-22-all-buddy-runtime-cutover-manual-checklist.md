# All-Buddy Runtime Cutover Manual Checklist

1. In a launcher-owned runtime workspace, run `python3 scripts/switch_runtime.py resolve "switch market: validate an AI workflow"` and confirm the response contains `context_revision`, `run_envelope`, `skills`, and no packet-era fields.
2. Run a market skill through the host and confirm `host_execution` keeps `browser_executor = "chrome-devtools-cockpit"` and `discovery_mode = "browser-native"`.
3. Run `switch pm: create a landing page track`, persist a `track-manager` result, and confirm `task.track_id` and `track.task_ids` update together.
4. Run `switch design: shape the landing-page prototype`, persist a `shape-prototype` result, and confirm the durable artifact is `design-handoff`, sandbox changed-file paths are recorded in run audit, and preview path metadata may still live inside the durable artifact.
5. Persist a second dev or pm turn and confirm the response returns a new reserved `run_id` in `refreshed_context.run_envelope`.
