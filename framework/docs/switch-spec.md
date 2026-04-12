# BuddySwitch Switch Spec

## Canonical Syntax

```text
switch <buddy>: <task>
```

Rules:

1. Message must start with `switch`.
2. `<buddy>` must be one token.
3. `:` is required.
4. `<task>` must be non-empty.
5. This is the canonical form. Parser and router may normalize minor CLI whitespace variation around `:` when buddy and task remain unambiguous.

## Buddy Validation

- Buddy names are loaded from `buddyswitch/manifest.toml`.
- Do not use a hardcoded allowlist in parser or router.

## Runtime Model

BuddySwitch uses four primitives:

1. `parse`
2. `resolve`
3. `run`
4. `persist`

`parse`, `resolve`, and `persist` belong to BuddySwitch.
`run` belongs to the host Codex session.

## Failure Action Vocabulary

Control-layer checks should map to exactly one of these actions:

- `normalize`: keep going after canonicalizing input without changing user intent
- `warn`: keep going and surface advisory information to the host session
- `ask`: stop before mutation and ask the host/user for missing intent or an explicit choice
- `reject`: stop because continuing would misroute work or write unsafe state

Current control-layer expectations:

- `parse`
  - minor CLI spacing variation around `:` => `normalize`
  - unknown buddy / empty task / non-switch input => `reject`
- `resolve`
  - advisory runtime metadata such as `required_tools` / `required_env` => `warn`
  - multi-skill selection belongs to the host decision loop => `ask`
  - missing required track context or unsafe explicit references => `reject`
- `persist`
  - invalid `skill_id`, schema mismatch, or unsafe state/reference writes => `reject`
- manual/debug APIs
  - actor permission failure or invalid object references => `reject`

## Runtime Resolution

- Runtime entry: `scripts/switch_runtime.py`
- Resolution order:
  1. parse switch
  2. load the selected buddy's skill catalog from `buddyswitch/skills/**/SKILL.md`
  3. apply the minimal deterministic gates needed for safe resolution (`track_mode` and track context)
  4. resolve track context from `track_mode`
  5. reject explicit requests for retired markdown outputs under `artifacts/*.md` or `runs/summaries/**`
  6. return `eligible_skills`, compact `skill_cards`, per-skill context, output schema paths, invocation details, and explicit next actions

Current runtime defaults:

- single-skill buddies may expose `implicit_skill_id`
- multi-skill buddies never auto-select in runtime
- `buddy -> skills` is the main routing authority in runtime
- buddy `permissions` stay as object-authority metadata for manual/debug mutation APIs
- `required_tools` and `required_env` are advisory skill metadata for the host session
- BuddySwitch skills are loaded from `buddyswitch/skills/**/SKILL.md`
- BuddySwitch does not rely on Codex native `.agents/skills` discovery for these skills
- output contracts are enforced through `framework/schemas/**`
- output schema validation is structure-only; it does not score business quality, research quality, or workflow completeness
- artifact objects include canonical structured artifact content
- run audit payloads are written to `buddyswitch/content/runs/**`
- derived markdown artifacts and run summaries are retired

## Host Codex Responsibilities

After `resolve`:

1. choose exactly one `skill_id` from `eligible_skills`
2. read the selected `buddyswitch/skills/<buddy>/<skill>/SKILL.md`
3. execute the workflow in-session
4. produce a structured result payload matching `required_output_schema_by_skill[skill_id]`
5. call `scripts/switch_runtime.py persist`

## Persist Behavior

`persist` is a lightweight technical gate, not a business-quality review.

It validates:

- selected `skill_id` belongs to the resolved buddy
- selected `skill_id` is still in `eligible_skills`
- result payload matches the selected schema
- basic state/reference safety

Schema validation in this stage is structural only. It checks shape and allowed values, not whether the work itself is good enough.

It writes:

- artifact objects with canonical structured content under `buddyswitch/objects/artifacts/*.json`
- run audit payloads under `buddyswitch/content/runs/**`
- track objects under `buddyswitch/objects/tracks/*.json` when PM track-manager mutations are requested

`resolve` writes nothing. Its only job is to return enough context for the host Codex session to decide what to do next.

## Error Handling

Parsing should return explicit errors:

- `E_EMPTY_INPUT`
- `E_INVALID_SYNTAX`
- `E_UNKNOWN_AGENT`
- `E_EMPTY_TASK`
- `E_ENV_MANIFEST`

Runtime should return explicit errors:

- `E_RUNTIME_RESOLVE`
- `E_RUNTIME_PERSIST`

For syntax and unknown-buddy errors include:

- expected syntax: `switch <buddy>: <task>`
- one valid example
- current valid buddies from manifest

## Reference Commands

- Parser: `python3 scripts/parse_switch.py "switch pm: continue track"`
- Router: `python3 scripts/codex_router.py "switch pm: continue track"`
- Runtime resolve: `python3 scripts/switch_runtime.py resolve "switch pm: continue track"`
- Runtime persist: `python3 scripts/switch_runtime.py persist --resolved resolved.json --skill-id write-prd --result result.json`
