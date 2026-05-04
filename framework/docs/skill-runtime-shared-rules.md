# Skill Runtime Shared Rules

These rules apply to artifact-producing BuddySwitch skills that persist durable runtime output.

## Direct Emission Rule

- Native artifact-producing skills emit buddy-level result JSON directly.
- Call `persist --skill-id <native-skill-id>` with that direct result payload.
- Keep the same native `skill_id` in the persist call; runtime preserves it in receipt, artifact, and run audit metadata.

## Execution Summary Persistence

- Write `execution_summary` into `artifact.summary`.
- Keep the summary selection-ready for downstream buddies:
  - artifact role
  - key resolved outcome
  - downstream relevance

## Task And Artifact Boundaries

- Follow `framework/docs/track-registry.md` for track context, but do not mutate track lifecycle fields directly unless the skill explicitly owns track management.
- Artifact-producing skills may read tracks and create or update artifact objects through the resolved task.
- Do not store direct track references inside artifact output unless the skill contract explicitly requires them.
- PM lifecycle mutations must use `state_effects.track_operation` in PM result payloads.
- Retired top-level `track_operation` payloads are rejected.

## Durable Output Paths

- Default BuddySwitch state lives in:
  - `buddyswitch/objects/tasks/<task-id>.json`
  - `buddyswitch/objects/artifacts/<artifact-id>.json`
  - `buddyswitch/content/runs/<run-id>.json`
- Do not request or rely on `artifacts/*.md` or `runs/summaries/**`.
