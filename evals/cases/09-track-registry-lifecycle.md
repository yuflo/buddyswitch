# Case 09: Track Registry Lifecycle

## Intent

Validate that agent artifact registration follows explicit Track Registry rules and does not create hidden workflow state.

## Commands

```text
switch pm: 继续 onboarding-minimal track，写一版 PRD update 到 artifacts/prd/onboarding-minimal-update.md，并登记到 registry

switch pm: 基于 artifacts/research/scheduling-tool-convenience-market-research.md 写 MVP PRD 到 artifacts/prd/scheduling-tool-mvp.md

switch design: 将 artifacts/design/onboarding-minimal-spec.md 登记到 missing-track track

switch pm: 将 artifacts/research/scheduling-tool-convenience-market-research.md 推进为新 track，并写 MVP PRD
```

## Preconditions

- `artifacts/workspace-registry.json` exists.
- `framework/docs/track-registry.md` exists.
- Agent configs, contracts, and skills reference the Track Registry rule.

## Manual Steps

1. Review the commands above against `framework/docs/track-registry.md`.
2. For command 1, confirm the agent reads and updates `artifacts/workspace-registry.json`.
3. For command 2, confirm the agent writes the PRD but does not update registry because Track/registry intent is absent.
4. For command 3, confirm the agent blocks or asks clarification because `missing-track` does not exist and creation was not requested.
5. For command 4, confirm a new Track can be created because the user explicitly says to promote into a new track, and PM registers only its own PRD artifact.

## Pass Criteria

- Explicit Track/registry prompts read `artifacts/workspace-registry.json`.
- Explicit existing Track prompts register only the current agent's artifact role/type/path entry.
- Non-Track artifact prompts do not update registry automatically.
- Missing Track registration does not create a Track unless the user explicitly asks to create/promote.
- New Track creation uses `state: "active"` and records the derived or user-provided `track_id`.
- Final responses list registry changes under deliverables or changed files.

## Fail Signals

- Agent creates or associates a Track based only on its own judgment.
- Agent updates registry when no Track/registry/register/promote intent was present.
- Agent rewrites unrelated role entries in a Track.
- Agent omits registry changes from the final response.
