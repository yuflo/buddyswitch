# Skill Runtime Shared Rules

These rules apply to artifact-producing BuddySwitch skills in launcher-managed runtime sessions.

## Three Runtime Gates

- Materialization validates copy boundaries only.
- `prepare` validates turn context and reservation safety only.
- `persist` validates write safety only.

Codex CLI owns package acceptance after `.agents/skills/<skill-id>` is materialized.

## Direct Emission Rule

- Native artifact-producing skills emit buddy-level result JSON directly.
- Call `persist --skill-id <native-skill-id>` with that direct result payload.
- Keep the same native `skill_id` in the persist call; runtime preserves it in receipt, artifact, and run audit metadata.

## Runtime Write-Safety Minimums

`persist` requires only the minimum payload shape needed for safe writes:

- non-empty string `execution_summary`;
- object `artifact_content`;
- `working_notes` and `deliverables_or_changed_files` as lists when present.

Write `execution_summary` into `artifact.summary` and keep that summary selection-ready for downstream buddies.

Buddy-level schemas remain authoring and development guidance. Runtime does not require full schema completeness unless a field is needed for safe writes.

## Task And Artifact Boundaries

- Follow `framework/docs/track-registry.md` for track context.
- PM lifecycle mutations must use `state_effects.track_operation` in PM result payloads.
- Retired top-level `track_operation` payloads are rejected.

## Durable Output Paths

- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- `buddyswitch/content/runs/<run-id>.json`

Do not request or rely on `artifacts/*.md` or `runs/summaries/**`.
