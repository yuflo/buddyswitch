# BuddySwitch Internal Wire Spec

This document defines the internal/debug wire contract for BuddySwitch switch routing.

## Canonical Wire Syntax

```text
switch <buddy>(<task-id>) -> <track-id>: <demand>
```

Canonical machine-readable grammar: `framework/contracts/switch-grammar.json`.

Supported canonical forms:

- `switch <buddy>: <demand>`
- `switch <buddy> -> <track-id>: <demand>`
- `switch <buddy>(<task-id>): <demand>`
- `switch <buddy>(<task-id>) -> <track-id>: <demand>`

## Product-Mode Plain Input

The canonical wire grammar remains `switch <buddy>(<task-id>) -> <track-id>: <demand>`.
`parse_switch.py` stays strict and only parses canonical `switch ...` text.
Product-mode users do not type `switch` commands.

In a launcher-managed product-mode session, `./buddyswitch-codex instance start --buddy <buddy>` binds the process to one active buddy.
Plain user text inside that session is adapted by `scripts/switch_runtime.py resolve` before parse when all product-mode env vars are valid and active buddy from launcher session metadata is present:

- `BUDDYSWITCH_ACTIVE_BUDDY`
- `BUDDYSWITCH_INSTANCE_ID`
- `BUDDYSWITCH_INSTANCE_JSON`

Any structural `switch <buddy>...:` input in a product-mode buddy instance must reject before parse or resolve mutation.
Missing product-mode env keeps strict canonical wire behavior.
Partial product-mode env rejects before mutation.

## Buddy Validation

- Buddy names are loaded from `buddyswitch/manifest.toml`.
- Do not use a hardcoded allowlist in parser or router.

## Runtime Model

BuddySwitch uses four primitives:

1. `parse`
2. `resolve_context`
3. `run`
4. `persist-skill-result`

`parse`, `resolve_context`, and `persist-skill-result` belong to BuddySwitch. `run` belongs to the host Codex session.

The current CLI entrypoints are:

- `python3 scripts/switch_runtime.py resolve`
- `python3 scripts/switch_runtime.py persist`

`persist` is the current CLI wrapper for the `persist-skill-result` step.

Canonical runtime contract files:

- `framework/contracts/resolve-context.json`
- `framework/contracts/persist-skill-result.json`

## Failure Action Vocabulary

Control-layer checks should map to exactly one of these actions:

- `normalize`: keep going after canonicalizing input without changing user intent
- `warn`: keep going and surface advisory information to the host session
- `ask`: stop before mutation and ask the host/user for missing intent or an explicit choice
- `reject`: stop because continuing would misroute work or write unsafe state

Current control-layer expectations:

- `parse`
  - minor CLI spacing variation around `:` => `normalize`
  - unknown buddy / empty demand / non-switch input => `reject`
- `resolve_context`
  - advisory runtime metadata such as `required_tools` / `required_env` => `warn`
  - multi-skill selection belongs to the host decision loop => `ask`
  - missing explicit task/track references or unsafe task-track conflicts => `reject`
- `persist-skill-result`
  - invalid `skill_id`, schema mismatch, stale context revision, or unsafe state/reference writes => `reject`
- manual/debug APIs
  - actor permission failure or invalid object references => `reject`

## Resolve Context

Runtime entry: `scripts/switch_runtime.py`.

`resolve_context` returns the current execution handoff for the host session. The response shape is frozen in `framework/contracts/resolve-context.json`.

Core fields:

- `context_revision`
- `switch`
- `buddy`
- `authority`
- `task_resolution`
- `run_envelope`
- `task_context`
- `track_context`
- `inputs`
- `skills`
- `warnings`

Resolution order:

1. parse the switch
2. load the selected buddy's skill catalog from skill packages under `buddyswitch/skills/**/` (`skill.toml` + `SKILL.md`)
3. validate explicit task id, explicit track id, and task ownership when supplied
4. derive task resolution (`create` or `reuse`) and effective track id
5. materialize create-mode task context when needed and reserve the next run envelope
6. build task context and optional track context from canonical objects
7. reject explicit requests for retired markdown outputs under `artifacts/*.md` or `runs/summaries/**`
8. select current artifact inputs only when one skill surface is already unambiguous
9. return compact skill cards plus any resolved `host_execution` / `tool_scope` metadata needed by the host

Create-mode contract:

- When no explicit task id is supplied, `resolve_context` may materialize the task immediately with zero runs.
- Zero-run tasks use `run_ids: []` and `latest_run_id: null`.
- `run_envelope.status = "reserved"` and `run_envelope.run_id` is the reserved run id for the next persist.
- Because create-mode resolve may materialize a zero-run task, run `resolve` and `persist` from a launcher-owned runtime workspace rather than the repo-root source checkout.

Current runtime defaults:

- single-skill buddies expose one skill in `skills`
- multi-skill buddies never auto-execute in runtime
- `buddy -> skills` is the main routing authority in runtime
- buddy `permissions` remain object-authority metadata for manual/debug mutation APIs
- `required_tools` and `required_env` are advisory host metadata
- BuddySwitch skills are loaded from skill packages under `buddyswitch/skills/**/`
- artifact slot and revision semantics are canonical (`task.artifact_slots[slot]` plus artifact `revision` / `is_current`)
- output contracts are enforced through `framework/schemas/**`
- output schema validation is structure-only; it is not a business-quality review and it does not score workflow completeness
- every persisted run belongs to a task object
- run audit payloads are written to `buddyswitch/content/runs/**`
- derived markdown artifacts and run summaries are retired

Multi-skill resolution notes:

- multi-skill buddies never auto-select in runtime; the host must choose one `skill_id` from `resolve_context.skills`
- `resolve_context.inputs` is the current selected input bundle only when one skill surface is already resolved
- for multi-skill resolves, top-level `inputs` may be empty until the host chooses the skill turn
- the host should choose by combining the resolved skill metadata with `task_context`, `track_context`, and the buddy contract docs

Market runtime note:

- market browser rules live in `resolve_context.skills[*].host_execution`
- market tool boundaries live in `resolve_context.skills[*].tool_scope`
- for `market-browser-native`, `host_execution.browser_executor` stays `chrome-devtools-cockpit`
- host execution for market runs must stay browser-native: search in the browser and continue into real pages (details, comments, related pages when relevant)
- no silent search API/snippet/crawler fallback is allowed; only explicit `user-approved` one-off downgrade is permitted when browser-native access is genuinely blocked

## Host Codex Responsibilities

Recommended fixed host flow:

1. call `scripts/switch_runtime.py resolve`
2. choose exactly one `skill_id` from `resolve_context.skills`
3. read the selected skill package instruction markdown from `instruction_path`
4. treat `resolve_context.inputs` as the current selected input bundle for the run when the selected skill surface is already resolved
5. for market runs, apply `resolve_context.skills[*].host_execution` and `resolve_context.skills[*].tool_scope` before browser work
6. execute the selected skill in-session
7. produce a structured result payload matching the selected skill schema
8. call `scripts/switch_runtime.py persist` to perform the `persist-skill-result` step
9. check `refreshed_context.ok`; the default successful persist path returns `E_RUNTIME_REFRESH_CONTEXT`, and if another turn is needed, run explicit `resolve` with `receipt.recommended_switch`

Boundary for execution:

- BuddySwitch supplies routing context, resolve_context, and persistence.
- The host remains the only executor of browser, shell, and MCP tool actions.
- BuddySwitch does not execute host tools itself.

## Persist Skill Result

`persist-skill-result` is the canonical write boundary. The response shape is frozen in `framework/contracts/persist-skill-result.json`.

The current CLI command is:

```bash
python3 scripts/switch_runtime.py persist --resolved context.json --skill-id <skill_id> --result result.json
```

It performs one boundary validation pass:

- confirms the context revision is current
- confirms the selected skill is valid for the authoritative buddy/task context
- validates the result payload against the selected schema
- rejects unsafe run reuse and unsafe state/reference writes

It then commits canonical state:

- updates the resolved task mode (`create` or `reuse`)
- preserves the resolved task-track binding for track-targeted runs and applies any remaining registration needed before write completion
- routes into the selected skill's canonical write path (`track-manager` mutation or artifact persistence)
- writes the final run audit after canonical object writes succeed

It writes:

- task objects under `buddyswitch/objects/tasks/*.json`
- artifact objects with canonical structured content under `buddyswitch/objects/artifacts/*.json`
- run audit payloads under `buddyswitch/content/runs/*.json`
- track objects under `buddyswitch/objects/tracks/*.json` when task binding or PM track-manager mutations are requested

Successful persist responses include `receipt` plus `refreshed_context`.
Host-facing follow-up fields live inside `receipt`, including:

- `task_title`
- optional `track_title`
- `reference_switches`
- `related_run_ids`
- `recommended_switch`

`persist` is the end-of-turn commit boundary. Successful `persist` does not reserve a follow-up run.

Check `refreshed_context.ok` before using it for the next turn. The default successful persist path returns `{ok: false, error.code: E_RUNTIME_REFRESH_CONTEXT}`; if another turn is needed, run explicit `resolve` with `receipt.recommended_switch`.

Host terminal rendering contract:

- Render exactly two sections in order: `Receipt`, `Summary`.
- Terminal final output should follow `Receipt -> Summary`.
- `Receipt` order:
  - `Persisted`
  - `Task` (`task_title` + `task_id`)
  - `Track` (`track_title` + `track_id`) only when a track exists
  - `Artifact` (`artifact_id` or `none`)
  - `Run`
  - `Related Runs` only when `related_run_ids` is non-empty
  - Optional next-step state/handoff note (non-command wording)
- `Summary` constraints:
  - execution summary in 1-2 lines
  - open questions up to 4 items
- `reference_switches` and `recommended_switch` may remain in receipt as internal/debug follow-up fields.
- Keep full object paths as optional debug output, not the primary summary surface.

## Error Handling

Parsing should return explicit errors:

- `E_EMPTY_INPUT`
- `E_INVALID_SYNTAX`
- `E_UNKNOWN_AGENT`
- `E_EMPTY_DEMAND`
- `E_ENV_MANIFEST`

Runtime should return explicit errors:

- `E_RUNTIME_RESOLVE`
- `E_RUNTIME_PERSIST`
- `E_RUNTIME_REFRESH_CONTEXT`

For syntax and unknown-buddy errors include:

- expected syntax: `switch <buddy>(<task-id>) -> <track-id>: <demand>`
- one valid example
- current valid buddies from manifest

## Reference Commands

- Parser: `python3 scripts/parse_switch.py "switch pm -> track-demo: continue scope definition"`
- Router: `python3 scripts/codex_router.py "switch pm -> track-demo: continue scope definition"`
- Runtime resolve (launcher-owned runtime workspace): `python3 scripts/switch_runtime.py resolve "switch dev: continue implementation"`
- Runtime persist (launcher-owned runtime workspace): `python3 scripts/switch_runtime.py persist --resolved resolved.json --skill-id write-prd --result result.json`
