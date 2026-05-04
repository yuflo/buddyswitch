# Track-Manager Despecialization Test Plan

**Goal:** Verify that `track-manager` is no longer a special non-artifact runtime path and that PM-owned track lifecycle effects work through normal PM artifact persistence.

**Testing Principle:** Tests must start from product behavior and contracts: PM can explicitly mutate track lifecycle, the operation is auditable, the result is a PM artifact, non-PM buddies cannot mutate tracks, and retired input contracts are rejected. Do not create tests that merely mirror private helper names or preserve old implementation shape.

---

## Functional Requirements Under Test

FR1. `track-manager` is a normal PM buddy skill that materializes under `.agents/skills/track-manager`.

FR2. `track-manager` emits PM buddy-level result JSON directly.

FR3. `track-manager` uses the PM result schema, has an output slot, and produces an artifact.

FR4. PM result JSON may optionally declare `state_effects.track_operation`.

FR5. `persist` validates the selected result against the manifest schema before any artifact, task, track, run, reservation, or instance-binding write.

FR6. `persist` applies a declared track operation without checking `skill_id == "track-manager"`.

FR7. Track create/update/advance/archive still mutate canonical track and task objects correctly.

FR8. A track operation persist writes a PM artifact, task state, track state, run audit, and receipt.

FR9. Receipts expose `artifact_id`, `artifact_ids`, `track_id`, `track_title`, `track_action`, `next_state`, `receipt_paths`, and `related_run_ids` when track state changes.

FR10. Non-PM buddies cannot submit `state_effects.track_operation`; rejection happens before writes.

FR11. Old top-level `track_operation` payloads are rejected; there is no backward-compatible input path.

FR12. Manifest validation no longer permits `produces_artifact=false` skills.

FR13. Active docs, skill instructions, and prompt assets describe direct PM artifact output plus explicit PM state effects.

FR14. Runtime skill materialization and launcher-managed buddy workspaces still install PM skills and assets correctly.

FR15. Existing workspace projection and receipt contracts remain usable after track effects.

## Coverage Matrix

| Requirement | Test Type | Observable Proof |
| --- | --- | --- |
| FR1 | Runtime materialization | PM runtime workspace contains `.agents/skills/track-manager/SKILL.md` and track operation asset |
| FR2 | Skill/template contract | `track-operation-template.md` is valid PM result JSON |
| FR3 | Manifest/schema contract | `track-manager` maps to `pm-result.json`, `produces_artifact=true`, `output_slot=track-operation` |
| FR4 | Schema contract | PM schema accepts `state_effects.track_operation` |
| FR5 | Negative runtime | Invalid schema/effect snapshots are unchanged after rejected persist |
| FR6 | Repo hygiene + behavior | No active skill-id branch; `write-prd` and `track-manager` share artifact path semantics |
| FR7 | Runtime integration | create/update/advance/archive mutate track objects and task linkage |
| FR8 | Runtime integration | artifact object, task object, track object, and run audit paths exist |
| FR9 | Receipt contract | receipt contains artifact and track metadata after track effect |
| FR10 | Negative schema/runtime | non-PM state effect rejected before writes |
| FR11 | Negative runtime | old top-level `track_operation` rejected before writes |
| FR12 | Manifest negative | any `produces_artifact=false` manifest entry fails |
| FR13 | Docs consistency | active docs mention `state_effects.track_operation` and do not require old schema/path |
| FR14 | Launcher/materialization | launcher and runtime skill tests pass with new track-manager asset |
| FR15 | Projection/contract regression | workspace projection still exposes run audit next state and track action |

## Test Data Rules

Use realistic product payloads.

Valid track create payload:

```json
{
  "execution_summary": "Created onboarding delivery track.",
  "working_notes": ["The request explicitly asked for track lifecycle mutation."],
  "deliverables_or_changed_files": [],
  "artifact_content": {
    "summary": "Created onboarding delivery track.",
    "decisions": ["Created a PM-owned delivery track for onboarding."],
    "risks": [],
    "open_questions": [],
    "suggested_next_step": "Hand off to design after PM scope is ready.",
    "specialized_sections": {
      "track_operation": {
        "action": "create",
        "track_id": "track-onboarding-delivery",
        "title": "Onboarding Delivery",
        "status": "active",
        "current_buddy": "pm",
        "next_buddy": "design",
        "summary": "Cross-functional onboarding delivery flow."
      }
    }
  },
  "state_effects": {
    "track_operation": {
      "action": "create",
      "track_id": "track-onboarding-delivery",
      "title": "Onboarding Delivery",
      "status": "active",
      "current_buddy": "pm",
      "next_buddy": "design",
      "summary": "Cross-functional onboarding delivery flow."
    }
  }
}
```

Valid PM PRD payload:

```json
{
  "execution_summary": "Captured onboarding PRD updates.",
  "working_notes": ["Focused on P0 scope and acceptance criteria."],
  "deliverables_or_changed_files": ["runs/raw/prd-notes.md"],
  "artifact_content": {
    "summary": "Captured onboarding PRD updates.",
    "decisions": ["Ship guided onboarding flow before broader redesign."],
    "risks": ["Unknown migration edge cases."],
    "open_questions": ["Need follow-up QA pass?"],
    "suggested_next_step": "Hand off to design for a flow draft.",
    "specialized_sections": {
      "prd": {
        "problem": "Users need clearer onboarding scope.",
        "user_value": "Faster onboarding completion with clearer guidance.",
        "requirements": ["Define launch acceptance criteria", "Capture follow-up questions"],
        "scope": {
          "in_scope": ["Onboarding flow scope and acceptance criteria"],
          "out_of_scope": ["Implementation delivery code"]
        }
      }
    }
  }
}
```

Retired payload that must fail:

```json
{
  "execution_summary": "Created onboarding track.",
  "working_notes": ["Old payload shape."],
  "deliverables_or_changed_files": [],
  "track_operation": {
    "action": "create",
    "track_id": "track-legacy-top-level"
  }
}
```

## Anti-Cheat Rules

- Do not test by calling private track helper functions directly for success cases; use real `prepare` and real `persist`.
- Do not accept tests that only check for a missing function name while the old behavior still works.
- Do not make invalid payload tests pass by checking error text alone; compare runtime state snapshots before and after rejection.
- Do not satisfy the task by adding fake PRD fields to track-manager output.
- Do not keep `track-manager.json` as an unused compatibility schema.
- Do not add a fallback branch that accepts old top-level `track_operation`.
- Do not infer track effects from request text in tests; every mutating success case must include `state_effects.track_operation`.
- Do not broaden the test surface into arbitrary workflow-engine behavior.

## Test Groups

### TG-01: PM Schema Contract

Requirement: PM schema is buddy-level PM output, not PRD-only output, and optionally supports PM track state effects.

Cases:

1. PM schema requires the common result envelope.
   - Input: `framework/schemas/pm/pm-result.json`.
   - Expected: required keys are `execution_summary`, `working_notes`, `deliverables_or_changed_files`, `artifact_content`.
   - Expected: top-level `additionalProperties` is `false`.

2. PM artifact content is general PM output.
   - Input: schema JSON.
   - Expected: `artifact_content.required` is `summary`, `decisions`, `risks`, `open_questions`, `suggested_next_step`, `specialized_sections`.
   - Expected: PRD-specific fields are not top-level required PM artifact fields.

3. PM schema accepts valid PRD details under `specialized_sections.prd`.
   - Input: valid PRD payload from Test Data Rules.
   - Expected: validation succeeds.

4. PM schema accepts `state_effects.track_operation`.
   - Input: valid track create payload from Test Data Rules.
   - Expected: validation succeeds.

5. PM schema rejects retired top-level `track_operation`.
   - Input: retired payload from Test Data Rules.
   - Expected: validation fails with unsupported top-level `track_operation`.

6. Non-PM schemas reject `state_effects`.
   - Input: valid Dev/Test/Market/Design payload plus top-level `state_effects`.
   - Expected: validation fails with unsupported top-level `state_effects`.

### TG-02: Manifest And Skill Contract

Requirement: `track-manager` is an artifact-producing PM skill.

Cases:

1. Live manifest maps `track-manager` to PM result schema.
   - Expected: `produces_artifact=true`.
   - Expected: `output_slot="track-operation"`.
   - Expected: `output_schema="framework/schemas/pm/pm-result.json"`.

2. Live manifest has no active `track-manager` non-artifact schema.
   - Expected: `framework/schemas/pm/track-manager.json` does not exist.
   - Expected: no live manifest entry references it.

3. Manifest parser rejects non-artifact skills.
   - Input: temp manifest with `produces_artifact=false`.
   - Expected: load fails before runtime use.

4. PM skill docs describe direct result emission and state effects.
   - Input: `buddyswitch/skills/pm/track-manager/SKILL.md`.
   - Expected: mentions `artifact_content.specialized_sections.track_operation`.
   - Expected: mentions `state_effects.track_operation`.
   - Expected: does not instruct top-level `track_operation`.

5. Track-manager template is valid JSON and matches PM schema.
   - Input: `buddyswitch/skills/pm/track-manager/assets/track-operation-template.md`.
   - Expected: parses as JSON.
   - Expected: validates with `pm-result.json`.
   - Expected: includes both human-readable specialized section and executable state effect.

### TG-03: Track Create Runtime Success

Requirement: creating a track through `track-manager` persists an artifact and mutates track/task state.

Cases:

1. Create track through real prepare/persist.
   - Flow: PM `prepare`, then `persist --skill-id track-manager` with valid create payload.
   - Expected: response `ok=true`.
   - Expected: receipt has `artifact_id`, `artifact_ids`, `track_id`, `track_title`, `track_action=create`, `run_id`, `next_state`, `receipt_paths`, `related_run_ids`.
   - Expected: receipt `artifact_id` is included in `artifact_ids`.

2. Artifact object exists and is current.
   - Expected: artifact path exists.
   - Expected: artifact `skill_id` is `track-manager`.
   - Expected: artifact `slot` is `track-operation`.
   - Expected: artifact `content.specialized_sections.track_operation.action` is `create`.

3. Track object exists and links task.
   - Expected: track path exists.
   - Expected: track id/title/status/current_buddy/next_buddy/summary match payload.
   - Expected: task id appears in `track.task_ids`.

4. Task object links artifact and track.
   - Expected: task `track_id` is created track id.
   - Expected: task `artifact_ids` includes receipt artifact id.
   - Expected: task artifact slot `track-operation` points at the current artifact.

5. Run audit records both artifact and track metadata.
   - Expected: run path exists.
   - Expected: run `skill_id=track-manager`.
   - Expected: run `artifact_ids` includes receipt artifact id.
   - Expected: run `track_action=create`.
   - Expected: run `next_state.track_id` is created track id.

### TG-04: Track Update, Advance, And Archive Runtime Success

Requirement: existing track lifecycle operations still work through state effects.

Cases:

1. Update track title/summary/status.
   - Setup: create a track through valid create payload.
   - Flow: PM prepare/persist with `state_effects.track_operation.action=update`.
   - Expected: receipt has artifact id and `track_action=update`.
   - Expected: track mutable fields update.
   - Expected: artifact slot records update run.

2. Advance track to next buddy.
   - Setup: create a track.
   - Flow: PM prepare/persist with `action=advance`, `next_buddy=dev`, `status=active`.
   - Expected: track `next_buddy=dev`.
   - Expected: receipt `next_state.mode` is `handoff` when next buddy differs from current buddy.

3. Archive track.
   - Setup: create a track.
   - Flow: PM prepare/persist with `action=archive`.
   - Expected: track `status=archived`.
   - Expected: receipt `track_action=archive`.
   - Expected: receipt `next_state.mode=track_archived`.

4. Each operation creates an artifact revision.
   - Expected: each persist returns an artifact id.
   - Expected: task `artifact_slots.track-operation.revision_count` increases.
   - Expected: latest artifact is current.

### TG-05: Validation Failure And No Partial Writes

Requirement: invalid effects and invalid schemas fail before durable writes.

Snapshot rule:

- Capture task, artifact, track, run, reservation, and instance-binding state after `prepare` and before rejected `persist`.
- Assert the snapshot is unchanged after rejection except for already-created prepare state.

Cases:

1. Retired top-level `track_operation`.
   - Input: retired payload from Test Data Rules.
   - Expected: schema validation fails.
   - Expected: no track, artifact, run, task mutation, reservation clear, or instance update after failure.

2. Non-PM state effect.
   - Input: Dev valid payload plus top-level `state_effects.track_operation`.
   - Expected: schema validation fails before writes.
   - Expected: no partial writes.

3. Missing track for update/advance/archive.
   - Input: PM payload with `action=advance`, `track_id=track-does-not-exist`.
   - Expected: runtime validation fails before artifact write.
   - Expected: no partial writes.

4. Update/advance with no mutable fields.
   - Input: existing track id and `action=advance` without `title`, `status`, `current_buddy`, `next_buddy`, or `summary`.
   - Expected: runtime validation fails before writes.

5. Invalid status.
   - Input: PM payload with `status=paused`.
   - Expected: schema validation fails before writes.

6. Duplicate create track id.
   - Setup: existing track id.
   - Input: create payload with same track id.
   - Expected: validation fails before artifact write.

7. Unknown skill id remains rejected.
   - Flow: PM prepare, persist with valid track payload but `skill_id=unknown`.
   - Expected: membership validation fails before writes.

### TG-06: No Skill-Id-Specific Runtime Branch

Requirement: behavior is based on validated result contract and active buddy, not `track-manager` skill id.

Cases:

1. Static runtime hygiene.
   - Expected: `scripts/turn_runtime.py` contains no `selected_skill_id == "track-manager"`.
   - Expected: no `_persist_track_manager` function exists.

2. Track-manager uses artifact receipt shape.
   - Expected: runtime tests prove `artifact_id` exists for `track-manager`.
   - Expected: no tests assert `track-manager` returns `artifact_ids=[]`.

3. A PM artifact skill without `state_effects` still persists normally.
   - Flow: `write-prd` valid PRD payload.
   - Expected: artifact persist succeeds.
   - Expected: no track mutation occurs.
   - Expected: no `track_action` except `None`.

4. PM authorization is explicit.
   - Input: if a test manifest includes another PM artifact skill using `pm-result.json`, a valid `state_effects.track_operation` from that PM skill may be accepted because authorization is PM schema/active buddy based.
   - Expected: behavior proves runtime is not tied to `track-manager` skill id.
   - Note: this is optional if it requires too much fixture setup; the required proof is no skill-id branch plus successful `track-manager` artifact path.

### TG-07: Docs And Prompt Contract

Requirement: active instructions describe forward-only direct output and explicit PM state effects.

Cases:

1. PM docs define state effects.
   - Expected: `framework/contracts/pm.md`, `framework/docs/turn-runtime-spec.md`, and `framework/docs/skill-runtime-shared-rules.md` mention `state_effects.track_operation`.

2. Active docs reject retired payload.
   - Expected: docs say retired top-level `track_operation` is not accepted.

3. Active docs do not require non-artifact track-manager.
   - Expected: no active docs require `produces_artifact=false`.
   - Expected: no active docs reference `framework/schemas/pm/track-manager.json`.

4. Skill docs preserve explicit track mutation boundary.
   - Expected: `write-prd` says track lifecycle requests belong to `track-manager`.
   - Expected: `track-manager` says mutation must be explicit and declared in result JSON.

### TG-08: Runtime Skill Materialization And Launcher Regression

Requirement: schema changes do not break product-mode skill installation.

Cases:

1. PM runtime materializes track-manager.
   - Expected: `.agents/skills/track-manager/SKILL.md` exists in PM runtime workspace.
   - Expected: `.agents/skills/track-manager/assets/track-operation-template.md` exists.

2. Switching away from PM removes track-manager.
   - Expected: Design/Dev/Test/Market runtime workspaces do not retain stale track-manager directories after materialization switch.

3. Launcher copies buddy prompt assets unchanged.
   - Expected: existing launcher copy tests still pass.

4. Launcher tests do not leave tracked source residue.
   - Expected: after test run and known sentinel cleanup, `git status --short projects/app` has no output.

### TG-09: Workspace Projection And Contract Regression

Requirement: UI/debug consumers still receive useful track metadata after track effects.

Cases:

1. Workspace projection includes run audit track metadata.
   - Expected: projected run audit has `track_id`, `track_title`, `track_action`, `artifact_ids`, `next_state`, `receipt_paths`.

2. Receipt contract still contains required keys.
   - Expected: `persist-skill-result.json` required keys remain `ok`, `skill_id`, `task_id`, `task_title`, `artifact_ids`, `run_id`, `next_state`, `receipt_paths`, `related_run_ids`.
   - Expected: `artifact_id`, `track_id`, `track_title`, `track_action`, `warnings` remain optional.

3. Context panel can link task/artifact/track paths.
   - Expected: receipt paths point to existing task, artifact, track, and run files.

## Recommended Verification Commands

Run from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Schema and manifest:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_output_schema_boundaries.py tests/test_env_manifest_v2.py -q
```

Runtime persistence:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py -q
```

Parallel contract regression:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_parallel_contracts.py -q
```

Skill materialization:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py -q
```

Docs, prompt assets, launcher copy:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py -q
```

Compile check:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/buddyswitch-pycache-track-manager \
PYTHONDONTWRITEBYTECODE=1 \
python3 -m py_compile scripts/turn_runtime.py scripts/env_manifest.py scripts/output_schema.py scripts/runtime_skills.py
```

Full focused suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_output_schema_boundaries.py \
  tests/test_turn_runtime.py \
  tests/test_env_manifest_v2.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  tests/test_parallel_contracts.py \
  tests/test_buddyswitch_launcher.py \
  -q
```

Residue scans:

```bash
rg -n "selected_skill_id == \"track-manager\"|def _persist_track_manager|produces_artifact = false|framework/schemas/pm/track-manager.json" scripts tests framework buddyswitch README.md tools
```

Expected release state:

- No active dependency match remains except explicit absence assertions in tests or historical memo/spec documents outside the active scan.

```bash
rg -n "\"track_operation\"|state_effects.track_operation|track_action" scripts tests framework buddyswitch README.md tools
```

Expected release state:

- `track_operation` appears only as `state_effects.track_operation`, artifact `specialized_sections.track_operation`, track effect tests, docs, and output metadata `track_action`.

## Release Confidence Criteria

The test plan is satisfied when:

- `track-manager` creates a PM artifact and mutates track/task state through real `prepare` and `persist`.
- Update, advance, and archive track effects still work.
- Invalid schemas and invalid effects fail before writes.
- Non-PM buddies cannot persist track state effects.
- Old top-level `track_operation` is rejected.
- Manifest no longer supports non-artifact skills.
- Active docs and skill instructions describe the forward-only result contract.
- Full focused suite and residue scans pass.
