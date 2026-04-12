# BuddySwitch Switch Spec

## Canonical Syntax

```text
switch <buddy>(<task-id>) -> <track-id>: <demand>
```

Supported forms:

1. `switch <buddy>: <demand>`
2. `switch <buddy> -> <track-id>: <demand>`
3. `switch <buddy>(<task-id>): <demand>`
4. `switch <buddy>(<task-id>) -> <track-id>: <demand>`

Rules:

1. Message must start with `switch`.
2. `<buddy>` must be one token.
3. Optional `<task-id>` is written in parentheses immediately after buddy.
4. Optional `<track-id>` is written after `->`.
5. `:` is required.
6. `<demand>` must be non-empty.
7. Text after `:` is demand text, not a task object. When no task id is supplied, persistence creates a new task.
8. Parser and router may normalize minor CLI whitespace variation around `:`, `->`, and task parentheses when intent remains unambiguous.

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
  - unknown buddy / empty demand / non-switch input => `reject`
- `resolve`
  - advisory runtime metadata such as `required_tools` / `required_env` => `warn`
  - multi-skill selection belongs to the host decision loop => `ask`
  - missing explicit task/track references or unsafe task-track conflicts => `reject`
- `persist`
  - invalid `skill_id`, schema mismatch, or unsafe state/reference writes => `reject`
- manual/debug APIs
  - actor permission failure or invalid object references => `reject`

## Runtime Resolution

- Runtime entry: `scripts/switch_runtime.py`
- Resolution order:
  1. parse switch
  2. load the selected buddy's skill catalog from `buddyswitch/skills/**/SKILL.md`
  3. validate explicit task id, explicit track id, and task ownership when supplied
  4. derive task resolution (`create` or `reuse`) and effective track id
  5. build task context and optional track context from canonical objects
  6. build `track_artifact_index` from canonical `track -> task -> artifact` links when a track is present
  7. reject explicit requests for retired markdown outputs under `artifacts/*.md` or `runs/summaries/**`
  8. run deterministic artifact selection from `track_artifact_index` (when present) and return `artifact_selection`
  9. return `eligible_skills`, compact `skill_cards`, task context, track context, `track_artifact_index`, output schema paths, invocation details, and explicit next actions

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
- every persisted run belongs to a task object
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

Recommended fixed host flow for track-bound work:
1. resolve switch
2. read `track_artifact_index` and `artifact_selection`
3. read selected artifacts by id (from `artifact_selection.selected_artifact_ids` or `run_instructions.artifact_read_commands`)
4. execute selected skill
5. persist result

## Persist Behavior

`persist` is a lightweight technical gate, not a business-quality review.

It validates:

- selected `skill_id` belongs to the resolved buddy
- selected `skill_id` is still in `eligible_skills`
- result payload matches the selected schema
- basic state/reference safety

Schema validation in this stage is structural only. It checks shape and allowed values, not whether the work itself is good enough.

It writes:

- task objects under `buddyswitch/objects/tasks/*.json`
- artifact objects with canonical structured content under `buddyswitch/objects/artifacts/*.json`
- run audit payloads under `buddyswitch/content/runs/**`
- track objects under `buddyswitch/objects/tracks/*.json` when task binding or PM track-manager mutations are requested

Successful persist receipts and run audits also include:

- `task_title`
- `track_title` (nullable)
- `reference_switches` with copy-ready command templates:
  - `continue_current_task`
  - `continue_current_task_in_track` (when track exists)
  - `handoff_to_next_buddy` (when track has `next_buddy`)
- `related_run_ids` (up to 2 run ids linked to the same task, excluding the current run)
- `recommended_switch` (host-ready command chosen with precedence:
  `handoff_to_next_buddy` > `continue_current_task_in_track` > `continue_current_task`)

Host terminal rendering contract:

- Render exactly three sections in order: `Receipt`, `Commands`, `Summary`.
- `Receipt` order:
  - `Persisted`
  - `Task` (`task_title` + `task_id`)
  - `Track` (`track_title` + `track_id`) only when a track exists
  - `Artifact` (`artifact_id` or `none`)
  - `Run`
  - `Related Runs` only when `related_run_ids` is non-empty
- `Commands` order:
  - one `Template` command from `reference_switches` (`continue_current_task_in_track` preferred over `continue_current_task`)
  - one `Recommended` command from `recommended_switch`
- `Summary` constraints:
  - execution summary in 1-2 lines
  - open questions up to 4 items
- Keep full object paths as optional debug output, not the primary summary surface.

`resolve` writes nothing. Its only job is to return enough context for the host Codex session to decide what to do next.

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

For syntax and unknown-buddy errors include:

- expected syntax: `switch <buddy>(<task-id>) -> <track-id>: <demand>`
- one valid example
- current valid buddies from manifest

## Reference Commands

- Parser: `python3 scripts/parse_switch.py "switch pm -> track-demo: continue scope definition"`
- Router: `python3 scripts/codex_router.py "switch pm -> track-demo: continue scope definition"`
- Runtime resolve: `python3 scripts/switch_runtime.py resolve "switch dev: continue implementation"`
- Runtime persist: `python3 scripts/switch_runtime.py persist --resolved resolved.json --skill-id write-prd --result result.json`
