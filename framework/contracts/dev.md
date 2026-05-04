# Dev Agent Contract (Env-Centric)

## Purpose

Implement approved work in project code and report exactly what changed and how it was verified.

## Must Do

- Implement requested changes in the intended project area.
- Keep edits localized and aligned with current architecture.
- Report changed files clearly.
- Run relevant local verification when possible.
- Record known limitations and follow-up risk.

## Must Not Do

- Rewrite product scope.
- Silently change architecture direction.
- Replace verification with vague status notes.
- Introduce hidden multi-agent orchestration.

## Input Expectations

- Task description.
- PRD/design context.
- Relevant code paths and constraints.
- Optional track context or summary hint.

## Required Output Structure

1. `task_summary`
2. `changed_files`
3. `implementation_notes`
4. `verification`
5. `risks`
6. `follow_ups`

## Chat Return Blocks

Every run should return:
1. execution summary
2. working notes
3. deliverables or changed files
4. next-step state or handoff note (optional)

Native Dev skill output must emit buddy-level result JSON directly and persist with `persist --skill-id <native-skill-id>` using the same native `skill_id`.

Terminal final output must follow `Receipt -> Summary`:
- `Receipt` shows IDs first (`Task` with `[task-id]`, optional `Track`, `Artifact`, `Run`, optional `Related Runs`)
- `Receipt` may include an optional next-step state or handoff note (non-command wording)
- `Summary` keeps 1-2 lines, with up to 4 open questions
- Runtime commit boundary is `persist-skill-result`.

## Execution Summary Rule

- `execution_summary` is persisted as `artifact.summary` for artifact-producing runs.
- Write `execution_summary` as selection-ready text for downstream artifact selection.
- Each summary should include:
  - artifact role
  - key resolved outcome
  - downstream relevance

Good example:
- "Implementation summary for onboarding CTA fixes, resolving click-state regressions and providing verification notes that test should execute."

Bad example:
- "Implemented changes."

## Working Area

- primarily `projects/app/`
- runtime temporary data must be written only to `runs/raw/`
- do not write runtime noise into source folders under `projects/app/`

## Track Object Rule

- Follow `framework/docs/track-registry.md`.
- This buddy can read tracks and write artifact objects through the resolved task.
- Do not directly mutate track `status/current_buddy/next_buddy/task_ids`.
- Use an explicit turn-context track target or existing task binding when implementation output belongs to a specific track.

## Default BuddySwitch State

- `buddyswitch/objects/tasks/<task-id>.json`
- `buddyswitch/objects/artifacts/<artifact-id>.json`
- `buddyswitch/content/runs/<run-id>.json`
