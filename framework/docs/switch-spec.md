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

## Runtime Resolution

- Runtime entry: `scripts/switch_runtime.py`
- Resolution order:
  1. parse switch
  2. load the selected buddy's skill catalog from `buddyswitch/skills/**/SKILL.md`
  3. apply deterministic eligibility gates (`track_mode`, required env, required tools)
  4. resolve track context from `track_mode`
  5. derive default artifact/summary paths when needed
  6. return `eligible_skills`, compact `skill_cards`, per-skill context, defaults, and output schema paths

Current runtime defaults:

- single-skill buddies may expose `implicit_skill_id`
- multi-skill buddies never auto-select in runtime
- BuddySwitch skills are loaded from `buddyswitch/skills/**/SKILL.md`
- BuddySwitch does not rely on Codex native `.agents/skills` discovery for these skills
- output contracts are enforced through `framework/schemas/**`
- canonical structured payloads are written to `buddyswitch/content/**`
- human-readable markdown artifacts and summaries remain for panel compatibility

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
- lightweight authority/context consistency

It writes:

- canonical structured payloads under `buddyswitch/content/**`
- artifact objects under `buddyswitch/objects/artifacts/*.json`
- track objects under `buddyswitch/objects/tracks/*.json` when PM track-manager mutations are requested
- compatibility markdown artifacts under `artifacts/*.md`
- compatibility markdown summaries under `runs/summaries/**`

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
