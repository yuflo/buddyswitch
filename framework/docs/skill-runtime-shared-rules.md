# Skill Runtime Shared Rules

These rules apply to artifact-producing BuddySwitch skills that persist durable runtime output.

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

## Durable Output Paths

- Default BuddySwitch state lives in:
  - `buddyswitch/objects/tasks/<task-id>.json`
  - `buddyswitch/objects/artifacts/<artifact-id>.json`
  - `buddyswitch/content/runs/<run-id>.json`
- Do not request or rely on `artifacts/*.md` or `runs/summaries/**`.
