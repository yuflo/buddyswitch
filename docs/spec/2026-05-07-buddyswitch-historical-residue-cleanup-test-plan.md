# BuddySwitch Historical Residue Cleanup Test Plan

**Goal:** Verify that active BuddySwitch product surfaces converge on the current env/tool-layer runtime model without preserving old authoring, routing, or store mental models.

**Testing Principle:** Tests must start from functional requirements and observable product contracts. Do not write tests around private helper names, branch names, or implementation-specific deletion details just to make cleanup look complete. Scans are allowed only as active-surface contract checks, and their exclusions must be justified by product status: historical memos and archived plans may describe old behavior; active code, contracts, schemas, skills, templates, and tests may not teach it.

---

## Functional Requirements Under Test

FR1. A locked buddy instance remains the source of active buddy identity. User request text, including text shaped like old `switch <buddy>:` syntax, is ordinary request text.

FR2. Active authoring surfaces teach one compact buddy-run commit payload: required `execution_summary`; optional `working_notes`, `artifacts`, `state_effects`, `handoff`, `contributors`, and `tool_evidence`.

FR3. Artifact-producing runs author artifacts through `artifacts[]` entries with `kind`, `title`, `content`, and optional `summary`.

FR4. Active authoring surfaces no longer require or recommend old result keys: `deliverables_or_changed_files`, `artifact_content`, or `specialized_sections`.

FR5. PM track lifecycle authoring uses `state_effects.track`. No active schema, contract, skill, or template accepts or recommends `track_operation`.

FR6. Non-PM buddies cannot author track lifecycle effects, but may author current-task effects where env profiles allow `status` or `summary`.

FR7. Runtime persist still enforces durable signal requirements, manifest artifact kinds, handoff targets, PM-only track lifecycle authority, and no partial writes on invalid commits.

FR8. Market artifact-producing runs still require broker-issued browser evidence or an approved broker-issued downgrade token. The cleanup must not create hand-written token or silent fallback guidance.

FR9. Active skills and templates provide enough commit-shape guidance for buddies to author a result without reading source code or schemas.

FR10. The active object store has one clear implementation path. It must not call current store behavior `legacy`, and it must not keep a repository pass-through layer whose only job is delegating back to `_legacy_*` functions.

FR11. Read-only workspace projections, context panel behavior, debug APIs, and object lifecycle behavior remain stable after store flattening.

FR12. Active docs no longer blur the model with selected-skill or compatibility-era wording. Archived memos and old plans may retain historical language.

## Anti-Cheating Constraints

- Do not assert that a private helper was called, skipped, deleted, or renamed as the primary proof of user-visible behavior.
- Do not build tests around a single hard-coded residue example if the requirement is broader. For example, use multiple switch-prefixed texts and multiple buddies when proving locked buddy authority.
- Do not water down scans by excluding active paths that still influence runtime behavior. Allowed broad exclusions are `docs/memo/**` and intentionally archived old plans such as `docs/spec/2026-05-05-*`.
- Do not replace behavior tests with scans. Scans prove active surfaces do not teach the wrong model; behavior tests prove runtime still works.
- Do not make schema tests pass by allowing both old and new authoring contracts. The requirement is convergence, not compatibility.

## Coverage Matrix

| Requirement | Test Groups | Observable Proof |
| --- | --- | --- |
| FR1 | TG-01 | `prepare` succeeds and preserves switch-shaped text while active buddy comes from session metadata |
| FR2 | TG-02, TG-06 | schemas and active docs expose compact buddy-run keys |
| FR3 | TG-02, TG-03 | schemas accept `artifacts[]`; runtime persists artifact commits |
| FR4 | TG-06 | active contracts, schemas, skills, and templates contain no old artifact envelope keys |
| FR5 | TG-02, TG-03, TG-06 | PM schema accepts `state_effects.track`; runtime persists PM track effects; scans find no `track_operation` |
| FR6 | TG-02, TG-03 | non-PM schemas reject track effects; runtime rejects unauthorized track lifecycle commits |
| FR7 | TG-03 | buddy-run persist tests cover valid and invalid commit behavior |
| FR8 | TG-04 | market browser evidence tests still require broker-issued evidence |
| FR9 | TG-05, TG-06 | active skills/templates contain compact examples and no old payload keys |
| FR10 | TG-07 | store behavior tests pass and active store files contain no `_legacy_` path |
| FR11 | TG-07, TG-08 | projections, debug APIs, and context panel tests pass |
| FR12 | TG-06, TG-09 | wording scans find no active selected-skill or compatibility leftovers |

## Test Data Rules

Use product-meaningful examples:

- Switch-shaped ordinary request: `switch market: do competitor scan`
- Mismatched locked-buddy authority cases: PM session with `switch market: ...`, Market session with `switch dev: ...`, Dev session with `switch pm: ...`
- PM artifact kind: `prd`
- Market artifact kind: `market-scan`
- Design artifact kind: `design-handoff`
- Dev artifact kind: `implementation-report`
- Test artifact kind: `smoke-test`
- PM track effect: `state_effects.track.action = "advance"`
- Non-PM task effect: `state_effects.task.status = "active"`

Do not use fake strings whose only purpose is to hit a private branch. Invalid test data should represent product-invalid states: empty input, missing product session, unknown artifact kind, duplicate artifact kind, unauthorized track lifecycle mutation, invalid handoff target, missing market evidence token, or no durable collaboration signal.

## Test Groups

### TG-01: Locked Buddy Authority And Switch-Shaped Text

**Purpose:** Prove Batch 1 remains complete and old switch-shaped runtime rejection does not return.

**Functional scenario:**

1. Prepare a PM product session with request text `switch market: do competitor scan`.
2. Assert prepare returns `ok=true`.
3. Assert `active_buddy` equals `pm`.
4. Assert `request_text` and `run_envelope.turn_identity.request_text` preserve the exact input.
5. Assert a normal run reservation is created.
6. Repeat with locked Market and Dev sessions where the text prefix names a different buddy.
7. Assert retired public launcher commands still fail closed.

**Primary command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_accepts_switch_prefixed_text_as_ordinary_request \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_uses_locked_buddy_for_switch_prefixed_text \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_legacy_public_commands_fail_closed_with_hints \
  -q
```

**Expected proof:**

- Switch-shaped text is accepted as ordinary request text.
- The locked session buddy controls active identity.
- Retired public CLI commands remain separate launcher failures.

### TG-02: Compact Schema Contract

**Purpose:** Prove active result schemas describe the compact buddy-run commit instead of old artifact envelopes.

**Functional scenario:**

1. Load all five buddy result schemas through `scripts/output_schema.py`.
2. Assert each schema requires only `execution_summary`.
3. Assert each schema allows compact optional commit keys.
4. Validate one artifact-producing compact payload for each buddy.
5. Validate PM `state_effects.track`.
6. Validate non-PM `state_effects.task`.
7. Assert non-PM schemas reject `state_effects.track`.
8. Assert PM schema rejects `state_effects.track_operation`.
9. Assert runtime receipt metadata such as `task_id`, `artifact_ids`, and `run_id` remains unsupported in authored result payloads.

**Primary command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_output_schema_boundaries.py \
  -q
```

**Expected proof:**

- All schema examples use `artifacts[]`.
- Old top-level keys are not accepted.
- PM track effects use `state_effects.track`.
- Non-PM schemas do not imply track lifecycle authority.

### TG-03: Runtime Persist Behavior Remains Correct

**Purpose:** Prove schema/doc cleanup did not change or weaken runtime commit behavior.

**Functional scenarios:**

1. Artifact-producing commits create artifact objects and run audits.
2. Multiple valid artifacts in one run persist when kinds are unique and allowed by manifest.
3. Unknown artifact kinds fail before writes.
4. Duplicate artifact kinds fail before writes.
5. PM can create, update, advance, and archive tracks through `state_effects.track`.
6. Non-PM buddies cannot perform track lifecycle mutations.
7. Current-task effects update only allowed task fields.
8. Handoff-only commits are valid durable collaboration signals.
9. Invalid handoff target or empty handoff reason fails before writes.
10. Summary-only commits fail because they have no durable signal.

**Primary command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py \
  tests/test_parallel_contracts.py \
  -q
```

**Expected proof:**

- Runtime accepts the compact payload shape already used by product-mode persist.
- Invalid commits do not create artifacts, mutate tasks, mutate tracks, or consume reservations.
- The cleanup did not add compatibility support for old result authoring keys.

### TG-04: Market Browser Evidence Gate

**Purpose:** Prove Market cleanup preserves browser-native evidence authority.

**Functional scenarios:**

1. Market artifact-producing persist without `tool_evidence` fails.
2. Hand-written token strings fail.
3. Broker-issued browser evidence for the current run succeeds.
4. Broker-issued approved downgrade token succeeds only when it matches the current run context.
5. Evidence token mismatch by run, buddy, instance, mode, or context revision fails.
6. Non-market buddies are not forced through the market evidence gate.

**Primary command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_market_browser_evidence.py \
  tests/test_turn_runtime.py -k "market or tool_evidence or browser" \
  -q
```

**Expected proof:**

- Market remains browser-native and broker-gated.
- Templates may mention the token field, but tests prove only broker-issued evidence works.
- No silent web fallback is introduced.

### TG-05: Active Skills And Templates Are Sufficient For Authoring

**Purpose:** Prove active buddy skill packages tell the host how to author compact commits without source/schema inspection.

**Functional scenarios:**

1. Every active `SKILL.md` under `buddyswitch/skills/**` contains a buddy-run commit section.
2. Every artifact-producing skill names the manifest artifact kind it contributes.
3. Every template asset uses top-level `execution_summary` and `artifacts[]` or `state_effects`.
4. PM track manager template uses `state_effects.track`.
5. Market templates mention broker-issued `tool_evidence` without instructing users to invent token strings.
6. No active skill or template uses `artifact_content`, `deliverables_or_changed_files`, `specialized_sections`, or `track_operation`.

**Primary command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_authoring_surfaces_use_buddy_run_commit_shape \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_packages_do_not_instruct_skill_level_persist \
  -q
```

**Expected proof:**

- Active skills/templates expose one commit model.
- The old structured authoring contract is gone from active skill guidance.
- Skill docs still avoid skill-level persist instructions.

### TG-06: Active Surface Residue Scan

**Purpose:** Prove cleanup scope matches the memo: active surfaces are clean while historical records remain allowed.

**Functional scenario:**

Scan active authoring surfaces:

```bash
rg -n "deliverables_or_changed_files|artifact_content|specialized_sections|track_operation" \
  framework/contracts framework/schemas buddyswitch/skills
```

Expected:

```text
no matches
```

Scan active runtime docs and helper wording:

```bash
rg -n "selected skill work locally|older turn-runtime imports" \
  framework/docs/browser-cockpit.md scripts/env_manifest.py
```

Expected:

```text
no matches
```

Scan active store files:

```bash
rg -n "_legacy_" \
  scripts/env_store.py scripts/runtime_store tests/test_env_store_v2.py
```

Expected:

```text
no matches
```

**Allowed historical matches:**

- `docs/memo/**`
- archived `docs/spec/2026-05-05-*`
- launcher tests that deliberately prove retired public commands fail closed
- migration tests that deliberately reference old launcher/runtime markers outside the active object-store implementation

### TG-07: Store Behavior After Flattening

**Purpose:** Prove removing the legacy-labeled repository layer does not change object lifecycle behavior.

**Functional scenarios:**

1. `create_track` writes a valid track object.
2. `create_task` can materialize a task without an initial run.
3. Creating a task with a track binds task and track IDs together.
4. Creating a second artifact for the same task and kind creates a revision chain.
5. Moving or deleting artifacts preserves task slot state.
6. Run content writes still land under `buddyswitch/content/runs/<run-id>.json`.
7. Debug APIs still operate through the canonical store path.

**Primary command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_store_v2.py \
  tests/test_debug_apis.py \
  -q
```

**Expected proof:**

- Behavior remains stable without `_legacy_*` names.
- Tests no longer prove delegation to a wrapper; they prove object lifecycle behavior.

### TG-08: Workspace Projection And Context Panel Stability

**Purpose:** Prove store flattening does not break read-only context projection.

**Functional scenarios:**

1. Runtime projections still build task, artifact, track, and run audit views.
2. Context panel browser code still reads through `/api/workspace`.
3. UI surfaces still do not import runtime internals.
4. Interface docs still list runtime internals accurately after removing `runtime_store.repositories`.

**Primary command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_console_app_contract.py \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_browser_ui_does_not_import_runtime_internals \
  -q
```

**Expected proof:**

- Context projection remains read-only and stable.
- Browser UI does not couple to `env_store`, `runtime_store.projections`, `turn_runtime`, or `workspace_data`.

### TG-09: Final Focused Regression Suite

**Purpose:** Prove the cleanup did not regress the core env/tool-layer product path.

**Primary command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_output_schema_boundaries.py \
  tests/test_turn_runtime.py \
  tests/test_parallel_contracts.py \
  tests/test_market_browser_evidence.py \
  tests/test_env_store_v2.py \
  tests/test_debug_apis.py \
  tests/test_console_app_contract.py \
  tests/test_repo_consistency.py \
  -q
```

**Expected proof:**

- All targeted tests pass.
- Active authoring contract is compact buddy-run only.
- Store cleanup is behavior-preserving.
- Browser evidence and locked-buddy runtime authority remain intact.

## Manual Review Checklist

Use this checklist after automated tests:

- A PM buddy can understand from active contract/skill docs how to persist a PRD and a track update without reading schemas.
- A Market buddy can understand from active contract/skill docs that browser evidence is broker-issued and required for artifact-producing commits.
- A Dev/Test/Design buddy can understand artifact output goes under `artifacts[].content`.
- No active template contains the old authoring envelope.
- No code or test asserts that current store behavior is legacy.
- Historical docs are not mistaken for active product instructions.

