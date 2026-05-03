# BuddySwitch Skill Architecture Best Practices

## Runtime Model

BuddySwitch is not a standalone agent runtime.
It is a deterministic control layer around host execution.

- Host Codex chooses and executes one skill.
- BuddySwitch prepares context and persists validated state.
- Skill packages live under `buddyswitch/skills/**/`.

## Package Contract

Each skill package includes:

- `skill.toml` metadata
- `SKILL.md` workflow instructions

Required metadata:

- `id`
- `buddy`
- `description` (activation-style text beginning with `Use when`)
- `objects`
- `produces_artifact`
- `input_slots`
- `output_schema`

Conditional metadata:

- `output_slot` when `produces_artifact = true`

Recommended metadata:

- `side_effect_level`
- `required_tools`
- `required_env`
- `produces`
- `consumes`
- `allowed_task_kinds`

## Selection Rules

- `prepare-turn-context` returns candidate skills.
- Host selects exactly one `skill_id`.
- Multi-skill buddies are never auto-selected by runtime.

## Persistence Rules

`persist-skill-result` validates only technical boundaries:

- selected skill identity
- schema conformance
- task/track/run identity integrity

Business-quality review stays in host workflow, not persistence gate logic.

## Output Discipline

- Emit schema-valid structured payloads.
- Persist canonical object/run state only.
- Do not emit legacy markdown output paths.

## Shared Runtime Guidance

Use the shared runtime docs for cross-skill rules:

- `framework/docs/turn-runtime-spec.md`
- `framework/docs/skill-runtime-shared-rules.md`
