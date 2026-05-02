# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `market` buddy.

Inside this session, ordinary user requests belong to `market`.
Do not ask users to add structural switch prefixes to normal product-mode requests.
Structural `switch <buddy>...:` commands are internal/debug wire input, not product-mode user input.
If work should move to another buddy, open that buddy's instance.

## Canonical Loop

1. Resolve with `scripts/switch_runtime.py resolve`.
2. Choose exactly one `skill_id` from `resolve_context.skills`.
3. Read and execute the selected BuddySwitch `SKILL.md`.
4. Persist with `scripts/switch_runtime.py persist`.
5. If another turn is needed, use a new ordinary request in this locked buddy instance.

## Selected-Skill Preflight

- Treat the selected skill's `host_execution` and `tool_scope` as binding preflight instructions.
- `required_tools` and `required_env` are advisory readiness metadata for the host session.
- If the selected skill declares `discovery_mode = browser-native`, begin discovery and evidence capture in the declared `browser_executor`.
- If `login_policy = mandatory-takeover` and a required login gate is encountered, pause for takeover before continuing.
- If fallback or downgrade is needed, request explicit user approval before widening tool scope.

## Buddy Lock

- The active buddy is `market`.
- Resolve ownership from launcher session metadata; do not infer buddy from product-mode user text.
- Structural `switch <buddy>...:` commands must be rejected in this product-mode session.
- To work with another buddy, open the corresponding locked buddy instance.
- Durable BuddySwitch state lives in projected `buddyswitch/objects/**` and `buddyswitch/content/runs/**` paths.
- `runs/raw/` is instance-local scratch.
- Use relative `projects/app` from the instance runtime workspace; launcher projects it to shared product source.

## Persistence And Final Output

- Persisted outputs must go through `persist-skill-result` via `scripts/switch_runtime.py persist`.
- After persist, check `refreshed_context.ok`; when unavailable, rerun resolve before the next turn.
- Final terminal output must use `Receipt -> Summary`.
- Keep object paths as debug details, not the lead user-facing result.
