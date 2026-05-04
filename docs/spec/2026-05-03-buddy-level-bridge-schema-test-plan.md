# Buddy-Level Schema-Only Bridge Test Plan

**Goal:** Verify that BuddySwitch persists artifact results through five buddy-level schemas without requiring or retaining a runtime bridge/conversion module.

**Testing Principle:** Tests start from product requirements: native skill identity, direct buddy-level result emission, canonical validation, durable writes, and receipt usability. Do not create tests that merely preserve the current implementation shape or pass by checking token presence.

---

## Functional Requirements Under Test

FR1. Codex-native skill execution remains the entry point: runtime skills are materialized under `.agents/skills/<skill-id>`.

FR2. Artifact-producing skills emit buddy-level result JSON directly.

FR3. Manifest maps every artifact-producing native skill id to exactly one buddy-level schema for its buddy.

FR4. `persist --skill-id <native-skill-id>` preserves that native id in receipt, artifact object, and run audit.

FR5. `persist` validates the selected skill result against the manifest `output_schema` before writing canonical state.

FR6. PM, Dev, Test, Market, and Design each have product-structured `artifact_content`, not a single markdown dump.

FR7. Runtime receipt behavior remains usable: task id/title, artifact id(s), run id, optional track context, next state, paths, related run ids, and native skill id.

FR8. A registered community-style compatible skill can persist when it emits valid buddy-level result JSON directly.

FR9. Wrong buddy membership, unknown skill ids, wrong schemas, runtime metadata, and missing required fields are rejected without partial writes.

FR10. Active runtime docs and prompt assets describe direct buddy-level emission and do not require a runtime bridge module.

FR11. Deleted artifact-producing skill-specific schemas are not active dependencies.

FR12. `track-manager` remains the Task 1 exception and is not converted to artifact behavior.

## Coverage Matrix

| Requirement | Test Type | Observable Proof |
| --- | --- | --- |
| FR1 | Runtime materialization | `.agents/skills/<skill-id>/SKILL.md` exists in a runtime workspace and matches source bytes |
| FR2 | Runtime integration | Skill result fixture is already buddy-level JSON and persists without conversion |
| FR3 | Manifest contract | Artifact-producing skills point to `*-result.json`; `track-manager` keeps its own non-artifact schema |
| FR4 | Runtime integration | Receipt, artifact, and run audit contain the native skill id |
| FR5 | Negative runtime | Invalid result fails before task/artifact/run writes |
| FR6 | Schema contract | Each schema requires the agreed buddy-specific content fields |
| FR7 | Receipt contract | Persist response paths point to written state files |
| FR8 | End-to-end compatibility | Registered `dev-summary` skill persists a direct `dev-result` payload |
| FR9 | Negative runtime | State snapshots are identical before and after rejected persist |
| FR10 | Docs consistency | Active docs and prompts contain direct-emission flow and reject bridge residue |
| FR11 | Repo consistency | Active code/tests/docs do not depend on retired artifact schema files |
| FR12 | Regression | Existing `track-manager` tests still pass with `artifact_ids=[]` |

## Test Data Rules

Use realistic product payloads. A passing test must prove usable persisted content, not only the minimum required keys.

Representative payload themes:

- PM: problem, user value, requirements, scope, decisions, risks, open questions, next step.
- Dev: task summary, changed files, implementation notes, verification checks, risks, follow-ups.
- Test: test scope, checks run, passed/failed/blocked items, reproduction notes, readiness.
- Market: research question, evidence, insights, assumptions, risks, conclusion, next step, specialized sections.
- Design: design goal, flow/screen summary, interaction notes, asset refs, handoff notes, open questions.

Community-style compatible payload:

```json
{
  "execution_summary": "Summarized checkout banner implementation.",
  "working_notes": ["Kept changes scoped to projects/app."],
  "deliverables_or_changed_files": ["projects/app/main.js"],
  "artifact_content": {
    "task_summary": "Summarized checkout banner implementation.",
    "changed_files": ["projects/app/main.js"],
    "implementation_notes": ["Confirmed implementation details from changed files."],
    "verification": {
      "checks_run": ["npm test"],
      "passed": ["Unit tests passed"],
      "failed": [],
      "blocked": ["Manual browser smoke not run"]
    },
    "risks": ["Manual browser smoke not run"],
    "follow_ups": ["Run browser smoke test before release."]
  }
}
```

The community fixture must not mention retired schema filenames or rely on a bridge conversion step.

## Anti-Cheat Rules

- Do not test arbitrary native-output conversion for Task 1; that would reintroduce the removed runtime adapter as a requirement.
- Do not satisfy persistence tests by calling storage helpers directly; use real `prepare` and real `persist`.
- Do not validate docs by checking a single token only; verify the actual flow semantics.
- Do not satisfy negative tests with error messages only; compare state snapshots before and after rejected operations.
- Do not use retired schema filenames as fixtures for unrelated path-validation tests.
- Do not hide community skills behind a generic bridge skill id; use the registered native skill id.

## Test Groups

### TG-01: Buddy-Level Schema Contract

Requirement: five schemas define the artifact result surface for PM, Dev, Test, Market, and Design.

Cases:

1. Schema files exist under `framework/schemas/<buddy>/<buddy>-result.json`.
   - Expected: each file loads through `scripts/output_schema.py`.
   - Expected: each schema top-level type is `object`.

2. Each schema requires the common envelope.
   - Input: schema JSON.
   - Expected: required keys are `execution_summary`, `working_notes`, `deliverables_or_changed_files`, and `artifact_content`.
   - Expected: top-level `additionalProperties` is `false`.

3. Each schema rejects runtime metadata.
   - Input: valid buddy-level payload plus top-level `run_id`.
   - Expected: validation fails before persistence.

4. Each schema requires buddy-specific product fields.
   - Input: schema JSON.
   - Expected: required fields match the agreed PM, Dev, Test, Market, and Design content surfaces.

5. Market schema covers all current market skill result types.
   - Input: realistic market examples for research scan, PMF recon, customer discovery, positioning copy, channel discovery, and launch prep.
   - Expected: each validates using shared market fields plus `specialized_sections`.

### TG-02: Manifest Mapping And Native Skill Identity

Requirement: manifest maps native skills to buddy-level schemas without changing product-visible slots.

Cases:

1. Artifact-producing skills use buddy-level schemas.
   - Expected: all market artifact skills use `framework/schemas/market/market-result.json`.
   - Expected: `write-prd`, `implement-task`, `smoke-test`, and `shape-prototype` use their buddy result schemas.

2. Output slots remain product-specific.
   - Expected: `write-prd` keeps `prd`.
   - Expected: `implement-task` keeps `implementation-report`.
   - Expected: market skills keep their existing slot names.

3. `track-manager` remains non-artifact.
   - Expected: `produces_artifact=false`.
   - Expected: output schema is `framework/schemas/pm/track-manager.json`.

4. Native skill id survives persistence.
   - Flow: prepare Dev context, persist a valid `dev-result` with `skill_id="implement-task"`.
   - Expected: receipt, artifact object, and run audit all contain `implement-task`.

### TG-03: Real Persist Success For Current Artifact Skills

Requirement: current product skills can still create artifacts and receipts.

Cases:

1. PM representative: `write-prd`.
   - Flow: real `prepare`, then real `persist` with valid `pm-result`.
   - Expected: artifact content contains PM fields and receipt paths exist.

2. Dev representative: `implement-task`.
   - Flow: real `prepare`, then real `persist` with valid `dev-result`.
   - Expected: changed files and verification content persist.

3. Test representative: `smoke-test`.
   - Flow: real `prepare`, then real `persist` with valid `test-result`.
   - Expected: passed, failed, blocked, reproduction, and readiness fields persist.

4. Market representative: `research-scan`.
   - Flow: real `prepare`, then real `persist` with valid `market-result`.
   - Expected: evidence, insights, conclusion, and specialized sections persist.

5. Design representative: `shape-prototype`.
   - Flow: real `prepare`, then real `persist` with valid `design-result`.
   - Expected: design goal, flow summary, asset refs, and handoff notes persist.

### TG-04: Community-Compatible Skill Direct Persist

Requirement: a registered community-style skill can persist when it emits buddy-level JSON directly.

Cases:

1. Fixture package materializes.
   - Input: manifest registering `tests/fixtures/community-skills/dev-summary`.
   - Expected: runtime workspace contains `.agents/skills/dev-summary/SKILL.md`.

2. Direct community-compatible payload persists.
   - Flow: prepare Dev context, persist the direct `dev-result` payload with `skill_id="dev-summary"`.
   - Expected: receipt `skill_id` is `dev-summary`.
   - Expected: artifact object `skill_id` is `dev-summary`.
   - Expected: artifact content equals the submitted `artifact_content`.
   - Expected: run audit `skill_id` is `dev-summary`.

3. Wrong buddy membership rejects.
   - Flow: PM context tries `persist --skill-id dev-summary`.
   - Expected: failure before writes.

4. Fixture avoids retired contracts.
   - Input: `tests/fixtures/community-skills/dev-summary/SKILL.md`.
   - Expected: no retired schema filenames and no bridge-module instruction.

### TG-05: Validation Failure And No Partial Writes

Requirement: `persist` remains the canonical validation/write boundary.

Cases:

1. Missing required buddy-level field.
   - Input: `dev-result` missing `artifact_content.verification`.
   - Expected: `persist` fails before task/artifact/run writes.

2. Runtime metadata included in result.
   - Input: valid `pm-result` plus top-level `run_id`.
   - Expected: schema validation fails before writes.

3. Wrong buddy result submitted for selected skill.
   - Input: `market-result` payload submitted to `write-prd`.
   - Expected: schema validation fails before writes.

4. Unknown skill id.
   - Input: valid buddy-level payload with `skill_id="not-in-manifest"`.
   - Expected: membership validation fails before writes.

5. Wrong active buddy membership.
   - Input: Dev skill id in PM context.
   - Expected: membership validation fails before writes.

Snapshot rule:

- Capture task, artifact, run, reservation, and instance-binding state before the rejected persist.
- Assert the snapshot is unchanged after failure except for already-created prepare state.

### TG-06: Native Skill Materialization Regression

Requirement: schema changes do not break Codex-native skill discovery.

Cases:

1. For every manifest buddy, runtime installer materializes only active buddy skills.
   - Expected: installed directories equal the buddy's manifest skill list.

2. Installed package bytes match source package bytes.
   - Expected: no package mutation during materialization.

3. Repo root remains free of tracked runtime `.agents/skills`.
   - Expected: runtime skills stay instance-local.

### TG-07: Receipt Contract Regression

Requirement: product receipts remain useful after schema migration.

Cases:

1. Artifact-producing persist response includes required fields.
   - Expected: `ok`, `skill_id`, `task_id`, `task_title`, `artifact_id`, `artifact_ids`, `run_id`, `next_state`, `receipt_paths`, and `related_run_ids`.

2. Receipt paths point to written state.
   - Expected: task path exists.
   - Expected: run path exists.
   - Expected: artifact path exists and contains the receipt artifact id.

3. Run audit includes result summary fields.
   - Expected: `execution_summary`, `working_notes`, and `deliverables_or_changed_files` are present.

4. Artifact summary uses result summary.
   - Expected: artifact `summary` equals result `execution_summary`.

### TG-08: Track-Manager Non-Regression

Requirement: Task 1 does not alter Task 2 boundaries.

Cases:

1. `track-manager` create operation succeeds.
   - Expected: receipt has `artifact_ids=[]` and no artifact object is created.

2. `track-manager` update or advance operation succeeds.
   - Expected: track mutation semantics match current behavior.

3. Manifest permits only `track-manager` as the non-artifact skill.
   - Expected: another `produces_artifact=false` skill is rejected unless explicitly added in a future task.

### TG-09: Active Docs And Prompt Contract

Requirement: active instructions describe the direct flow.

Cases:

1. Buddy prompt assets define the runtime loop.
   - Expected: `.agents/skills`, `codex cli`, `native skill`, `buddy-level result json`, `persist`, and `skill_id` are present.

2. Buddy prompt assets reject bridge residue.
   - Expected: no `result_bridge`, `scripts/result_bridge.py`, `bridge it with`, or `native output ->`.

3. Runtime docs define direct emission.
   - Expected: active docs say the skill emits buddy-level result JSON directly.
   - Expected: active docs say `persist --skill-id` receives the native skill id.

4. Active docs do not point users to deleted artifact schema files.
   - Expected: no active references to retired artifact-producing schema filenames.

Historical memo/spec documents may mention old decisions as history. Active runtime docs, prompt assets, code, and tests must not require those paths.

### TG-10: Repo Hygiene And Deleted File Boundary

Requirement: the removed adapter does not survive as a hidden dependency.

Cases:

1. Runtime bridge module is absent.
   - Expected: `scripts/result_bridge.py` does not exist.

2. Bridge-only tests are absent.
   - Expected: `tests/test_result_bridge.py` does not exist.

3. No import path depends on the removed module.
   - Expected: `rg -n "result_bridge" scripts tests` returns no active dependency except tests asserting absence.

4. Retired artifact schemas are absent from active dependency graph.
   - Expected: active manifest and tests use buddy-level schemas or `track-manager`.

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
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/turn_runtime.py scripts/env_manifest.py scripts/output_schema.py scripts/runtime_skills.py
```

Bridge residue scan:

```bash
rg -n "result_bridge|scripts/result_bridge.py|bridge it with|native output ->" README.md framework buddyswitch tools tests
```

Retired schema residue scan:

```bash
rg -n "write-prd\\.json|implement-task\\.json|smoke-test\\.json|shape-prototype\\.json|research-scan\\.json|pmf-recon\\.json|customer-discovery\\.json|positioning-copy\\.json|channel-discovery\\.json|launch-prep\\.json" README.md framework buddyswitch tools tests
```

Expected release state:

- Test commands pass.
- Bridge residue scan has no active dependency matches except explicit absence assertions.
- Retired schema scan has no active dependency matches except explicit absence assertions.

## Release Confidence Criteria

The test plan is satisfied when:

- Five buddy-level schemas pass positive and negative validation tests.
- Manifest mapping proves artifact-producing skills use buddy-level schemas.
- Current representative skills persist real artifacts through real runtime flow.
- Community-compatible skill persists direct buddy-level JSON under its own native id.
- Invalid outputs and wrong memberships fail without partial writes.
- Native skill materialization still works.
- `track-manager` behavior is unchanged.
- Active runtime docs and prompt assets no longer describe a runtime bridge module.
