# Skill Runtime Shared Rules

These rules apply to native BuddySwitch skills in launcher-managed runtime sessions.

## Three Runtime Gates

- Materialization validates copy boundaries only.
- `prepare` validates turn context and reservation safety only.
- Env tool operations route through `env.tool` using `python3 scripts/env/client.py ...`.
- `persist` validates write safety only.

Codex CLI owns package acceptance after `.agents/skills/<skill-id>` is materialized.

Persist commits one active buddy run result. Native skills may contribute to that result, but native skill ids do not own the persist boundary, artifact identity, receipt identity, or write permissions.

## Contribution Rule

- Native skills contribute content to the current buddy run.
- Do not call persist from a skill perspective.
- The locked buddy session persists once per turn with:
  - `python3 scripts/turn_runtime.py persist --context <context> --result <result>`

## Runtime Write-Safety Minimums

`persist` requires only the minimum payload shape needed for safe writes:

- non-empty string `execution_summary`;
- optional `working_notes` list of strings;
- optional association metadata: `task_id`, `track_id`, `artifact_ids`;
- optional `handoff` object (`next_buddy`, `reason`, `context`);
- optional `contributors` object (`skills`/`agents` string lists);
- audit-only commit is valid when no association metadata is needed.

Buddy-level schemas remain authoring and development guidance. Runtime does not require full schema completeness unless a field is needed for safe writes.

## Task, Artifact, And Handoff Boundaries

- Follow `framework/docs/track-registry.md` for track context.
- Track lifecycle mutations must use track-tool/env tool track actions.
- Task updates must use task-tool/env tool task actions.
- Handoff is explicit collaboration state and does not implicitly mutate tracks.

## Durable Output Paths

- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- `buddyswitch/content/runs/<run-id>.json`

Do not request or rely on `artifacts/*.md` or `runs/summaries/**`.
