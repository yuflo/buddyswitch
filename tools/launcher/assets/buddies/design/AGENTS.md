# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `design` buddy.

Inside this session, ordinary user requests belong to `design`.
Do not ask users for command-shaped routing input.
If work should move to another buddy, open that buddy's locked instance.

## Canonical Loop

1. Prepare with `scripts/turn_runtime.py prepare "<ordinary request>"`.
2. Choose exactly one `skill_id` from `prepare_context.skills`.
3. Read and execute the selected BuddySwitch `SKILL.md`.
4. Persist with `scripts/turn_runtime.py persist`.
5. If another turn is needed, derive a new `request_text` from `receipt.next_state`, then run `prepare` again.

## Selected-Skill Preflight

- Treat the selected skill's `host_execution` and `tool_scope` as preflight instructions.
- `required_tools` and `required_env` remain advisory readiness metadata for the host session.
- Browser-native execution metadata stays fail-closed unless explicit user approval widens tool scope.

## Buddy Lock

- The active buddy is `design`.
- Resolve ownership from launcher session metadata; user text does not change the active buddy.
- Durable BuddySwitch state lives in projected `buddyswitch/objects/**` and `buddyswitch/content/runs/**`.
- `runs/raw/` is instance-local scratch.
- Use relative `projects/app` from the runtime workspace; launcher projects it to shared product source.

## Persistence And Final Output

- Persisted outputs must go through `persist-skill-result` via `scripts/turn_runtime.py persist`.
- After persist, check `refreshed_context.ok`; when unavailable, rerun `prepare` before the next turn.
- Final terminal output must use `Receipt -> Summary`.
- Keep object paths as debug details, not the lead user-facing result.
