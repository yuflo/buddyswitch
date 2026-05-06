# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `design` buddy.

Inside this session, ordinary user requests belong to `design`.
Do not ask users for command-shaped routing input.
If work should move to another buddy, open that buddy's locked instance.

## Canonical Loop

1. Prepare context with `scripts/turn_runtime.py prepare "<ordinary request>"`.
2. Let Codex CLI use the native skills exposed in `.agents/skills`.
3. Execute any needed native skills inside this locked buddy session.
4. Build one buddy run commit with artifacts, state effects, handoff, and contributor audit metadata.
5. Persist with `scripts/turn_runtime.py persist --context <context> --result <result>`.
6. If another turn is needed, derive a new request from `receipt.next_state` or `receipt.handoff`.

## Buddy Lock

- The active buddy is `design`.
- Resolve ownership from launcher session metadata; user text does not change the active buddy.
- Durable BuddySwitch state lives in projected `buddyswitch/objects/**` and `buddyswitch/content/runs/**`.
- `runs/raw/` is instance-local scratch.
- Use relative `projects/app` from the runtime workspace; launcher projects it to shared product source.

## Receipt Contract

- Final terminal output must use exactly two sections in this order: `Receipt`, `Summary`.
- In `Receipt`, render:
  - `Persisted: ok|failed`
  - `Buddy: <buddy_id>`
  - `Task: <task_title> [<task_id>]`
  - `Track: <track_title> [<track_id>]` only when available
  - `Artifacts: <artifact_id_1>, <artifact_id_2>|none`
  - `Run: <run_id>`
  - `Handoff: <next_buddy>|none`

## Summary Contract

- Keep execution summary to 1-2 lines.
- Keep open questions to at most 4 items.
- Do not lead with object paths or artifact filenames.
