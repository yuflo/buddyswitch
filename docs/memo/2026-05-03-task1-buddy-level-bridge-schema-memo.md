# Task 1: Buddy-Level Bridge Schema Memo

Date: 2026-05-03
Worktree: `dev0210`

## Purpose

Record the agreed scope for Task 1 so future implementation can start from the correct target.

Task 1 is about making community Codex-native skills usable in BuddySwitch without requiring each community skill to directly produce a BuddySwitch skill-specific output schema.

## User Goal

The product goal is to let a community Codex `SKILL.md` execute natively in a BuddySwitch instance and still produce a valid BuddySwitch product result:

1. Codex CLI discovers and executes the native skill.
2. BuddySwitch bridges the native result into a structured buddy-level result.
3. BuddySwitch persists an artifact, run audit, and receipt.

The community skill should not need to know or emit BuddySwitch-specific schemas such as `write-prd.json`, `implement-task.json`, or `research-scan.json`.

## Confirmed Current Problem

Current `dev0210` has native Codex skill execution, but `persist` still expects the selected skill result to match a manifest-specific output schema.

The current model is skill-specific:

```text
write-prd       -> framework/schemas/pm/write-prd.json
implement-task -> framework/schemas/dev/implement-task.json
smoke-test     -> framework/schemas/test/smoke-test.json
shape-prototype -> framework/schemas/design/shape-prototype.json
research-scan / pmf-recon / customer-discovery / positioning-copy / channel-discovery / launch-prep
                -> separate market schemas
```

This means a community skill may run natively but still fail to become a BuddySwitch artifact because it did not produce the exact JSON payload that the selected BuddySwitch skill schema requires.

## Confirmed Code Facts

Artifact-producing schemas already share the same top-level envelope:

```json
{
  "execution_summary": "string",
  "working_notes": ["string"],
  "deliverables_or_changed_files": ["string"],
  "artifact_content": {}
}
```

The current schema differences are concentrated under `artifact_content`.

The storage layer does not require skill-specific artifact content. It requires artifact `content` to be an object. The strict product fields are enforced before storage by the current output schema validation path.

## Target Change

Replace skill-specific artifact result schemas with five buddy-level bridge schemas:

```text
PM skills     -> pm-result schema
Dev skills    -> dev-result schema
Test skills   -> test-result schema
Market skills -> market-result schema
Design skills -> design-result schema
```

The bridge layer should convert native skill output into the relevant buddy-level result schema before calling `persist`.

## Scope Included

Task 1 includes:

- Define five buddy-level artifact result schemas for `pm`, `dev`, `test`, `market`, and `design`.
- Keep the common top-level envelope: `execution_summary`, `working_notes`, `deliverables_or_changed_files`, `artifact_content`.
- Refactor current artifact-producing BuddySwitch skills to persist through the corresponding buddy-level schema.
- Introduce or define a bridge/adaptation module that receives native skill output and produces the selected buddy-level result JSON.
- Ensure existing artifact-producing skills can still produce valid artifacts and receipts through the new buddy-level schema.
- Preserve Codex-native skill execution from `.agents/skills`.

## Scope Excluded

Task 1 does not include:

- Removing BuddySwitch package-format gatekeeping for `SKILL.md`; that is recorded separately in `2026-05-03-community-skill-package-validation-memo.md`.
- Despecializing `track-manager`; that is Task 2.
- Fully automatic launcher-level capture of Codex CLI final response, transcript, tool calls, and file changes.

## Skill Identity Boundary

Task 1 does not remove the current active-buddy skill identity check.

Default decision for implementation planning:

- `persist --skill-id` should receive the native Codex skill id that was materialized under `.agents/skills/<skill-id>`.
- The manifest skill entry should map that native skill id to the relevant buddy-level schema.
- Artifact/run metadata should keep the native skill id as the producing skill identity.
- The bridge should not hide every community skill behind one generic `community-skill` or `buddy-bridge` skill id by default.

If a later design chooses to persist through a generic bridge skill id, then the original native skill identity must be stored separately in the result/artifact/run metadata. That is not the default Task 1 path.

## Bridge Input Assumption

For Task 1, the host session may still explicitly hand native output to the bridge.

This means Task 1 can use a flow like:

```text
Codex CLI executes native skill
-> host writes or passes native result/notes/files to bridge
-> bridge creates buddy-level result JSON
-> host calls turn_runtime.py persist
```

Task 1 should not require deeper launcher/Codex wrapper work that automatically captures the final assistant response or transcript.

## Buddy-Level Content Direction

The five schemas should stay product-structured, not become unstructured markdown dumps.

Suggested artifact content shape:

- `pm`: problem, user value, requirements, scope, decisions, risks, open questions, suggested next step.
- `dev`: task summary, changed files, implementation notes, verification/checks, risks, follow-ups.
- `test`: test scope, checks run, passed items, failed items, blocked items, reproduction notes, readiness.
- `market`: research question, evidence, insights, assumptions, risks, conclusion, recommended next step, optional specialized sections.
- `design`: design goal, flow or screen summary, interaction notes, assets or preview refs, handoff notes, open questions.

The market schema must be broad enough to cover the current six market skills. It should not be modeled only after `research-scan`.

## Acceptance Criteria

Task 1 is complete when:

- Artifact-producing skills for PM, Dev, Test, Market, and Design use buddy-level schemas instead of skill-specific schemas.
- A representative current skill in each buddy can persist successfully through the new schema.
- A community-style native skill can be bridged into one buddy-level schema and persist into a valid artifact and receipt without the skill itself emitting a BuddySwitch-specific schema.
- `persist --skill-id` behavior is explicit: default path uses the native skill id with a buddy-level schema mapping.
- `persist` still validates the bridge output before writing canonical task/artifact/run state.
- Existing product receipt behavior remains usable: artifact id, run id, task id, optional track context, execution summary.

## Working Conclusion

Task 1 is the main community-skill product compatibility step.

It changes BuddySwitch from:

```text
every skill must know a BuddySwitch-specific schema
```

to:

```text
BuddySwitch accepts native skill output through a buddy-level bridge
```

This should deliver an MVP product loop for community Codex skills: native execution plus valid BuddySwitch artifact and receipt.
