# Dev Agent Contract (BuddySwitch v1)

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
- Optional explicit output path for implementation summary.

## Required Output Structure

1. `task_summary`
2. `changed_files`
3. `implementation_notes`
4. `verification_runs`
5. `known_limitations`

## Chat Return Blocks

Every run should return:
1. execution summary
2. working notes
3. deliverables or changed files
4. suggested next switch (optional)

## Working Area

- primarily `projects/app/`
- project runtime temporary data must be written only to `projects/app/.runtime/`
- do not write runtime noise into source folders under `projects/app/`

## Default Artifact Path

- `artifacts/build/` (when a durable build summary is needed)
