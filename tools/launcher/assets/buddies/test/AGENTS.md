# BuddySwitch Runtime Workspace

This workspace is launcher-owned, runtime-only, and locked to the `test` buddy.

Inside this session, plain user requests belong to `test`. Do not ask the user to prefix normal product-mode requests with `switch test:`. The runtime adapter converts plain text to the canonical BuddySwitch wire form before resolve.

## Canonical Loop

1. Resolve with `scripts/switch_runtime.py resolve`.
2. Choose exactly one `skill_id` from `resolve_context.skills`.
3. Read and execute the selected BuddySwitch `SKILL.md`.
4. Persist with `scripts/switch_runtime.py persist`.
5. Continue from `refreshed_context` when it is valid.

## Selected-Skill Preflight

- Treat the selected skill's `host_execution` and `tool_scope` as binding preflight instructions.
- `required_tools` and `required_env` are advisory readiness metadata for the host session.
- If the selected skill declares `discovery_mode = browser-native`, begin discovery and evidence capture in the declared `browser_executor`.
- If `login_policy = mandatory-takeover` and a required login gate is encountered, pause for takeover before continuing.
- If fallback or downgrade is needed, request explicit user approval before widening tool scope.

## Buddy Lock

- The active buddy is `test`.
- Same-buddy canonical `switch test...:` commands are allowed.
- Cross-buddy canonical switches are external handoffs and must not execute in this session.
- Durable BuddySwitch state lives in the projected `buddyswitch/objects/**` and `buddyswitch/content/runs/**` paths.
- `runs/raw/` is instance-local scratch.
- Use relative `projects/app` from the instance runtime workspace; launcher projects it to shared product source.

## Persistence And Final Output

- Persisted outputs must go through `persist-skill-result` via `scripts/switch_runtime.py persist`.
- After persist, use `refreshed_context` when `refreshed_context.ok = true`; rerun resolve when refreshed context is unavailable.
- Final terminal output must use `Receipt -> Commands -> Summary`.
- Keep object paths as debug details, not the lead user-facing result.
