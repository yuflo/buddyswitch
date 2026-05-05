# Runtime Gate Trimming Test Plan

**Goal:** Verify that BuddySwitch keeps only runtime checks that prevent wrong execution or bad state writes, while removing package-format and content-quality gates from product runtime paths.

**Testing Principle:** Tests must start from functional behavior: can the instance install skills, can a product request prepare context, and can a result safely persist state. Do not construct tests around private helper names, historical implementation branches, or artificial error messages.

---

## Functional Requirements Under Test

FR1. Instance startup materializes the active buddy's registered skills into `.agents/skills`.

FR2. Materialization rejects only source/target conditions that would copy from or write to the wrong place.

FR3. Materialization treats each skill package as opaque content; BuddySwitch does not inspect `SKILL.md`, frontmatter, `skill.toml`, or package file layout.

FR4. Materialization preserves package symlinks as symlink objects and does not dereference external content during copy.

FR5. Manifest loading validates BuddySwitch registration identity and buddy references, not skill package contents or source readiness.

FR6. `prepare` creates a correct product turn context and run reservation when product instance identity and task/track bindings are valid.

FR7. `prepare` does not fail because a skill package source is missing, has non-BuddySwitch metadata, lacks `SKILL.md`, has a missing output schema file, or because the active buddy has no registered skills.

FR8. `prepare` rejects failures that would produce wrong context or wrong pre-write state.

FR9. `persist` writes artifact, task, track, run, and receipt state only when the selected skill belongs to the active buddy and the result has the minimum writable shape.

FR10. `persist` does not require full buddy-level schema completeness or output schema file availability when the result can still be safely written.

FR11. `persist` rejects stale context, run reservation mismatches, cross-buddy skill writes, invalid output slot, invalid minimal result shape, and unsafe PM track effects before any state write.

FR12. PM track lifecycle mutation remains explicit through `state_effects.track_operation` and remains unavailable to non-PM buddies.

FR13. Docs and memo describe the final three-gate boundary without reintroducing package-format compatibility language.

## Coverage Matrix

| Requirement | Test Type | Observable Proof |
| --- | --- | --- |
| FR1 | Runtime materialization | `.agents/skills/<skill-id>` exists for active buddy after install |
| FR2 | Negative materialization | bad source/target paths fail and existing runtime skills are unchanged |
| FR3 | Opaque package positive | package with no frontmatter, `skill.toml`, unusual files, or no `SKILL.md` installs |
| FR4 | Opaque copy positive | symlink file remains a symlink in `.agents/skills` |
| FR5 | Manifest contract | manifest with malformed package contents loads; duplicate ids and unknown buddy refs still fail |
| FR6 | Prepare success | real product-mode prepare returns `ok=true`, task context, and reserved run envelope |
| FR7 | Prepare non-gating | prepare succeeds despite invalid package/source/schema readiness |
| FR8 | Prepare negatives | invalid product identity or binding conflict fails without bad state |
| FR9 | Persist success | minimal writable result writes artifact/run/task and receipt |
| FR10 | Persist non-gating | schema-incomplete result and missing output schema file do not block writes |
| FR11 | Persist negatives | stale/cross-buddy/invalid-result cases fail with state snapshots unchanged |
| FR12 | PM track effects | PM effect succeeds; non-PM effect fails before writes |
| FR13 | Docs consistency | docs state materialization/prepare/persist boundaries and no package-content gate |

## Test Data Rules

Use realistic product-shaped data. Avoid values that exist only to hit a specific private branch.

Opaque community package contents:

```text
SKILL.md                  # may have no YAML frontmatter
skill.toml                # legacy metadata that BuddySwitch must preserve
README.md                 # arbitrary package file
assets/example.md         # arbitrary asset
linked-readme.md -> README.md
```

Minimal writable persist result:

```json
{
  "execution_summary": "Saved community implementation summary.",
  "working_notes": [],
  "deliverables_or_changed_files": [],
  "artifact_content": {
    "summary": "Saved community implementation summary.",
    "freeform": {
      "community_output": "Community skill output can be persisted without matching every buddy schema detail."
    }
  }
}
```

Valid PM track effect result:

```json
{
  "execution_summary": "Created onboarding delivery track.",
  "working_notes": ["The request explicitly asked for track lifecycle mutation."],
  "deliverables_or_changed_files": [],
  "artifact_content": {
    "summary": "Created onboarding delivery track.",
    "freeform": {
      "reason": "Track lifecycle operation was requested by the user."
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

Invalid non-PM track effect result:

```json
{
  "execution_summary": "Tried to mutate a track from dev.",
  "working_notes": [],
  "deliverables_or_changed_files": [],
  "artifact_content": {
    "summary": "Invalid non-PM track mutation attempt."
  },
  "state_effects": {
    "track_operation": {
      "action": "advance",
      "track_id": "track-onboarding-delivery",
      "next_buddy": "test"
    }
  }
}
```

Invalid minimal result:

```json
{
  "execution_summary": "",
  "working_notes": "not a list",
  "artifact_content": "not an object"
}
```

## Anti-Cheat Rules

- Do not satisfy success behavior by calling private helper functions directly; use real install, real prepare, and real persist where product behavior is under test.
- Do not make negative tests pass by checking error text only; snapshot relevant state before and after failure.
- Do not keep a package-content validator and bypass it only in tests.
- Do not create a community package fixture that secretly follows BuddySwitch first-party package conventions.
- Do not preserve strict schema validation behind a different helper name.
- Do not let `prepare` pass by skipping product-mode instance identity setup.
- Do not let `persist` pass by writing partial state before failing later.
- Do not infer track effects from request text; mutating success cases must include explicit `state_effects.track_operation`.

## Test Groups

### TG-01: Manifest Loading Is Registration-Only

Requirement: manifest loading must not prove package contents or source readiness.

Cases:

1. Manifest loads with package lacking BuddySwitch frontmatter.
   - Fixture: package has `SKILL.md` containing plain Markdown.
   - Expected: `load_manifest()` returns skill id, path, buddy membership, and persistence metadata.

2. Manifest loads with legacy metadata.
   - Fixture: package contains `skill.toml`.
   - Expected: `load_manifest()` succeeds.

3. Manifest loads when source directory is missing.
   - Fixture: skill path points to a repo-relative missing directory.
   - Expected: `load_manifest()` succeeds because materialization, not manifest loading, owns source existence.

4. Manifest loads when output schema file is missing.
   - Fixture: skill has `output_schema = "framework/schemas/dev/missing-runtime-gate.json"`.
   - Expected: `load_manifest()` succeeds because prepare must not be blocked by schema readiness.

5. Duplicate skill id still fails.
   - Fixture: two `[[skills]]` entries have the same id.
   - Expected: `load_manifest()` fails.

6. Buddy references unknown skill still fails.
   - Fixture: buddy `skills = ["not-declared"]`.
   - Expected: `load_manifest()` fails.

7. Invalid permission still fails.
   - Fixture: permission object is not `track`, `task`, or `artifact`.
   - Expected: `load_manifest()` fails.

### TG-02: Materialization Copies Opaque Packages Safely

Requirement: instance startup installs active buddy packages without inspecting their contents.

Cases:

1. Opaque package with no frontmatter installs.
   - Flow: run `scripts/runtime_skills.py install --buddy dev --workspace <tmp>`.
   - Expected: installed package contains `SKILL.md`.
   - Expected: command exits 0.

2. Opaque package with `skill.toml` installs.
   - Flow: same install path.
   - Expected: installed package preserves `skill.toml`.

3. Opaque package without `SKILL.md` installs.
   - Flow: package contains only `README.md`.
   - Expected: installed runtime package exists with `README.md`.
   - Meaning: Codex CLI can later reject it, but BuddySwitch materialization does not.

4. Package symlink is preserved.
   - Flow: package contains `linked-readme.md -> README.md`.
   - Expected: installed `linked-readme.md` is a symlink and points to `README.md`.
   - Expected: copied file is not a dereferenced duplicate.

5. Invalid skill id fails without mutation.
   - Fixture: skill id contains `/`.
   - Expected: install fails.
   - Expected: previous `.agents/skills` snapshot is unchanged.

6. Absolute source path fails without mutation.
   - Fixture: manifest path is absolute.
   - Expected: install fails before deleting existing runtime skills.

7. Source path escaping repo fails without mutation.
   - Fixture: manifest path contains `..` or resolves outside repo.
   - Expected: install fails before deleting existing runtime skills.

8. Missing source directory fails without mutation.
   - Fixture: manifest source path is repo-relative but absent.
   - Expected: install fails because materialization cannot copy it.

9. Runtime target symlink fails without mutation.
   - Fixture: workspace `.agents` or `.agents/skills` is symlink.
   - Expected: install fails before writes.

10. Source checkout root and filesystem root workspaces fail.
   - Fixture: workspace is repo root or `/`.
   - Expected: install fails and no `.agents` is created in source checkout root.

### TG-03: Prepare Only Validates Turn Context

Requirement: prepare should only reject states that would produce an invalid context or reservation.

Cases:

1. Prepare succeeds with malformed package contents.
   - Fixture: active buddy skill package lacks frontmatter and contains `skill.toml`.
   - Flow: real product-mode prepare.
   - Expected: `ok=true`, `context_revision`, `current_task_id`, and `run_envelope.status="reserved"`.

2. Prepare succeeds when package source directory is missing after instance startup.
   - Fixture: manifest points to missing source path.
   - Flow: real product-mode prepare with known active buddy.
   - Expected: prepare succeeds because source copying is not part of prepare.

3. Prepare succeeds when selected schema file is missing.
   - Fixture: active buddy skill has missing `output_schema` path.
   - Expected: prepare succeeds.

4. Prepare succeeds when active buddy has empty skill list.
   - Fixture: active buddy exists with `skills = []`.
   - Expected: prepare creates task context and run reservation.

5. Empty request fails.
   - Input: blank request text.
   - Expected: `ok=false`.
   - Expected: no task or reservation is created.

6. Missing product-mode env fails.
   - Flow: call prepare without launcher-managed env.
   - Expected: `E_PRODUCT_MODE_REQUIRED`.

7. Partial product-mode env fails.
   - Fixture: only some product-mode env vars are present.
   - Expected: failure before task or reservation creation.

8. Instance id mismatch fails.
   - Fixture: env instance id differs from instance JSON.
   - Expected: failure before task or reservation creation.

9. Existing task owned by another buddy fails.
   - Fixture: product instance points to task whose `buddy` differs from active buddy.
   - Expected: prepare fails without changing that task.

10. Existing task bound to different track fails.
    - Fixture: instance requests explicit track not matching task's existing track.
    - Expected: prepare fails without rebinding the task.

### TG-04: Persist Writes Minimal Valid Results

Requirement: persist should write safe artifact/run state without requiring full content schema completeness.

Cases:

1. Minimal writable result persists.
   - Flow: real prepare, then real persist with minimal writable result.
   - Expected: `ok=true`.
   - Expected: artifact object exists.
   - Expected: artifact `summary` equals `execution_summary`.
   - Expected: artifact `content` equals `artifact_content`.
   - Expected: run audit exists and references artifact id.

2. Schema-incomplete content persists.
   - Fixture: `artifact_content` lacks buddy-level optional quality fields such as `risks`, `decisions`, or `specialized_sections`.
   - Expected: persist succeeds if minimum write shape is valid.

3. Missing output schema file does not block persist.
   - Fixture: selected skill has valid `output_slot` and missing `output_schema`.
   - Expected: artifact id and slot are derived from `output_slot`.
   - Expected: persist succeeds.

4. Extra artifact content persists.
   - Fixture: `artifact_content` includes arbitrary community output fields.
   - Expected: artifact stores them unchanged.

5. Missing `artifact_content` fails before writes.
   - Input: result has `execution_summary` but no `artifact_content`.
   - Expected: no artifact, run, task run id, track write, or reservation clear occurs.

6. Non-object `artifact_content` fails before writes.
   - Input: `artifact_content` is a string.
   - Expected: state snapshot unchanged.

7. Missing or blank `execution_summary` fails before writes.
   - Input: summary missing or empty.
   - Expected: state snapshot unchanged.

8. Non-list `working_notes` fails before writes.
   - Input: `working_notes` is a string.
   - Expected: state snapshot unchanged.

9. Non-list `deliverables_or_changed_files` fails before writes.
   - Input: `deliverables_or_changed_files` is an object.
   - Expected: state snapshot unchanged.

10. Selected skill without output slot fails before writes.
    - Fixture: selected manifest skill lacks `output_slot`.
    - Expected: no artifact is written because artifact identity cannot be derived.

### TG-05: Persist Blocks Unsafe Writes

Requirement: persist remains a hard gate for state safety.

Cases:

1. Context payload not ok fails.
   - Input: context has `ok=false`.
   - Expected: persist fails before any writes.

2. Stale context revision fails.
   - Fixture: task has advanced since prepare.
   - Expected: persist fails and state snapshot is unchanged.

3. Run reservation mismatch fails.
   - Fixture: reservation task id, sequence, or turn identity differs from context.
   - Expected: persist fails and state snapshot is unchanged.

4. Duplicate run id fails.
   - Fixture: run id already exists in task or run content.
   - Expected: persist fails before writes.

5. Skill not available for active buddy fails.
   - Flow: PM context tries to persist with a Dev-only skill id.
   - Expected: persist fails before writes.

6. Top-level `track_operation` fails.
   - Input: result uses retired top-level track operation.
   - Expected: no artifact or track write occurs.

7. Non-PM track effect fails.
   - Flow: Dev context persists result with `state_effects.track_operation`.
   - Expected: no artifact or track write occurs.

8. Invalid track operation action fails.
   - Input: action is not `create`, `update`, `advance`, or `archive`.
   - Expected: no writes.

9. Track operation conflicts with current task binding.
   - Fixture: task is bound to one track, effect targets another.
   - Expected: no writes.

10. PM valid track create succeeds.
    - Flow: PM prepare, then PM persist with valid create effect.
    - Expected: artifact, track, task, run audit, and receipt are written.
    - Expected: receipt includes `track_action="create"` and artifact id.

### TG-06: Launcher And Product Runtime Regression

Requirement: product-mode startup and PM/dev/test/design/market runtime flows still work after trimming gates.

Cases:

1. Launcher PM workspace installs active skills.
   - Flow: launcher-managed workspace setup or existing launcher test helper.
   - Expected: `.agents/skills/write-prd` and `.agents/skills/track-manager` exist.

2. Launcher Dev workspace installs active skills.
   - Expected: `.agents/skills/implement-task` exists and PM skills do not.

3. Product prepare and persist smoke succeeds.
   - Flow: launcher-style product env, prepare a PM request, persist a minimal PM result.
   - Expected: receipt includes artifact and run id.

4. Track-manager product smoke succeeds.
   - Flow: launcher-style PM env, prepare track creation request, persist PM track effect.
   - Expected: track object and artifact object exist.

### TG-07: Documentation And Scope Checks

Requirement: docs and tests do not reintroduce removed gates.

Cases:

1. Memo states the three runtime gates.
   - Expected: memo names materialization, prepare, persist.
   - Expected: memo says package content validation belongs to Codex CLI.

2. Runtime docs do not require `SKILL.md` frontmatter for BuddySwitch materialization.
   - Expected: no active runtime doc says BuddySwitch rejects missing frontmatter.

3. Runtime docs do not require strict full schema at persist.
   - Expected: docs distinguish minimum write safety from authoring guidance.

4. Tests do not cheat by replacing old package gate with equivalent consistency gate.
   - Expected: no test fails product runtime because of `name`, `description`, `skill.toml`, or package symlink content.

5. No new compatibility layer exists.
   - Expected: search for new wrapper/fallback language returns no active implementation.

## Required Verification Commands

Run from `/Users/chen/Dev/buddyswitch/.worktrees/dev0210`.

Focused suites:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_output_schema_boundaries.py tests/test_repo_consistency.py tests/test_parallel_contracts.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
```

Compile:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env_manifest.py scripts/runtime_skills.py scripts/turn_runtime.py scripts/output_schema.py
```

Full suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

Manual product smoke:

```bash
./buddyswitch-codex instance start --buddy pm
```

In the launched PM instance, perform:

```text
创建一个 onboarding delivery track
```

Expected product result:

- prepare succeeds;
- `track-manager` is available from `.agents/skills`;
- persist writes artifact, run, task, and track state;
- receipt includes `artifact_id`, `run_id`, `track_id`, and `track_action`.

## Completion Criteria

The task is test-complete only when:

- package-format variants install or prepare according to the three-gate boundary;
- all negative cases that can write bad state fail before writes;
- minimal writable community-style output persists successfully;
- strict content quality is not enforced as a runtime gate;
- final focused suites, compile check, and full suite pass from `dev0210`;
- docs clearly explain why each remaining gate exists.
