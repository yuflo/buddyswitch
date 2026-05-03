# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `market` buddy.

Inside this session, ordinary user requests belong to `market`.
Do not ask users for command-shaped routing input.
If work should move to another buddy, open that buddy's locked instance.

## Canonical Loop

1. Prepare context with `scripts/turn_runtime.py prepare "<ordinary request>"`.
2. Let Codex CLI use the native skills exposed in `.agents/skills`.
3. Execute the selected native skill in this host session.
4. Persist with `scripts/turn_runtime.py persist` (`persist-skill-result`), reporting the Codex skill name as `skill_id`.
5. If another turn is needed, derive a new `request_text` from `receipt.next_state`, then run `prepare` again.

## Buddy Lock

- The active buddy is `market`.
- Resolve ownership from launcher session metadata; user text does not change the active buddy.
- Durable BuddySwitch state lives in projected `buddyswitch/objects/**` and `buddyswitch/content/runs/**`.
- `runs/raw/` is instance-local scratch.
- Use relative `projects/app` from the runtime workspace; launcher projects it to shared product source.

## Receipt Contract

- Final terminal output must use exactly two sections in this order: `Receipt`, `Summary`.
- In `Receipt`, render:
  - `Persisted: ok|failed`
  - `Task: <task_title> [<task_id>]`
  - `Track: <track_title> [<track_id>]` only when `receipt.track_id` exists
  - `Artifact: <artifact_id|none>`
  - `Run: <run_id>`
  - `Related Runs: <run_id_1>, <run_id_2>` only when present
- Use IDs and titles from `receipt`; object paths stay debug-only details.

## Summary Contract

- Keep execution summary to 1-2 lines.
- Keep open questions to at most 4 items.
- Do not lead with object paths or artifact filenames.
