# BuddySwitch Skill Architecture Best Practices

## Runtime Model

BuddySwitch is a deterministic control layer around host execution.

- Codex discovers and executes native skills from `.agents/skills`.
- BuddySwitch prepares context and persists validated state.
- Native artifact-producing skills emit buddy-level result JSON directly before persist.
- Source skill packages live under `buddyswitch/skills/**`.

## Package Contract

Each source skill package must include:

- `SKILL.md` with YAML frontmatter (`name`, `description`)
- no `skill.toml`

BuddySwitch-specific persistence contract lives in `buddyswitch/manifest.toml` per `[[skills]]` entry:

- `id`
- `path`
- `produces_artifact`
- `output_schema`
- `output_slot` when `produces_artifact = true`

## Runtime Materialization Rules

- Launcher materializes only the active buddy membership into runtime `.agents/skills`.
- Runtime `.agents/skills` is instance-only and must not be tracked at repo root.
- Installer must validate source/target safety before deleting and copying runtime skills.

## Prepare And Persist Rules

- `prepare-turn-context` returns context/state/run envelope only.
- `prepare` does not return skill candidates, instruction paths, or custom skill packets.
- `persist-skill-result` records the Codex `skill_id` and validates membership from active buddy manifest skills.
- `persist-skill-result` keeps native `skill_id` identity in receipt, artifact, and run audit metadata.
- `persist-skill-result` validates payload schema from manifest persistence contract.

## Output Discipline

- Emit schema-valid structured payloads.
- Persist canonical object/run state only.
- Do not emit legacy markdown output paths.

## Shared Runtime Guidance

Use the shared runtime docs for cross-skill rules:

- `framework/docs/turn-runtime-spec.md`
- `framework/docs/skill-runtime-shared-rules.md`
