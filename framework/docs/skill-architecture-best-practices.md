# BuddySwitch Skill Architecture Best Practices

## Runtime Model

BuddySwitch is a deterministic control layer around host execution.

- Codex discovers and executes native skills from `.agents/skills`.
- BuddySwitch prepares context and persists validated state.
- Native artifact-producing skills emit buddy-level result JSON directly before persist.
- Source skill packages live under `buddyswitch/skills/**`.

## Package Contract

BuddySwitch runtime treats source skill packages as opaque during materialization.
Codex CLI owns package acceptance after install into runtime `.agents/skills/<skill-id>`.
Do not treat package file style as a runtime gate.

Skill registry contract lives in `buddyswitch/manifest.toml` per `[[skills]]` entry:

- `id`
- `path`

Buddy-level persistence contract lives in `[[buddies]]` entries:

- `artifact_kinds`

## Runtime Materialization Rules

- Launcher materializes only the active buddy membership into runtime `.agents/skills`.
- Runtime `.agents/skills` is instance-only and must not be tracked at repo root.
- Installer must validate source/target safety before deleting and copying runtime skills.

## Prepare And Persist Rules

- `prepare-turn-context` returns context/state/run envelope only.
- `prepare` does not return skill candidates, instruction paths, or custom skill packets.
- `prepare` validates context/reservation safety only; it does not gate on package/source/schema readiness.
- `persist-buddy-run` validates active buddy ownership, reserved run usage, and write-safety minimums.
- Native `skill_id` values are contributor audit metadata only (`contributors.skills`), not artifact/receipt/run ownership.
- `persist-buddy-run` validates collaboration-safe shape (`execution_summary`, optional `artifacts`, `state_effects`, `handoff`, `contributors`) and requires at least one durable signal.

## Output Discipline

- Emit schema-valid structured payloads.
- Persist canonical object/run state only.
- Do not emit legacy markdown output paths.

## Shared Runtime Guidance

Use the shared runtime docs for cross-skill rules:

- `framework/docs/turn-runtime-spec.md`
- `framework/docs/skill-runtime-shared-rules.md`
