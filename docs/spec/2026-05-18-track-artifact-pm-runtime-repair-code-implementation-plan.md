# Track/Artifact PM Runtime Repair Code Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the track/artifact merge regression by making runtime state transitions, tool catalog semantics, response feedback, PM/shared skills, contracts, and tests describe one publication contract.

**Architecture:** `artifact.create_revision` creates active-buddy-owned draft/revision markdown artifacts. `track.add_material` and `track.add_proof` are the only active shared publication entry points and update both artifact state and track state in one service/store path. Runtime-visible semantics and responses describe atomic tool effects; PM workflow guidance stays in skills and contracts, not in AGENTS prompt bulk.

**Tech Stack:** Python env.tool services, JSON runtime object store under `buddyswitch/objects/**`, broker-routed tests with `pytest`, Markdown contracts and skills.

---

## Source Inputs

Required source reads for this plan:

- `AGENTS.md`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/memo/2026-05-18-track-artifact-pm-runtime-repair-memo.md`
- `git log -2 --oneline`
- `git show --stat`
- Relevant merge diff from `40d9ce4 feat: merge track page and artifact markdown collaboration model`
- Current services, store, tool catalog, semantics, client, PM contract, PM skill, shared tool skills, and related tests named in the request

Recent commit scope establishes the regression source:

- `f9c42c4 Merge branch 'integration/merge-track-artifact-2342'`
- `40d9ce4 feat: merge track page and artifact markdown collaboration model`
- The merge changed `scripts/env/services/tracks.py`, `scripts/env_store.py`, `scripts/env/tools/contracts.py`, role contracts, skills, projections, and tests.

## Current Bottleneck

The core runtime bottleneck is a split publication contract:

- `artifact.create_revision` accepts `status="published"` and `published_to_track=<track-id>` and can persist an artifact that says it is published.
- That call does not write the corresponding `track.shared_materials` or `track.close_proof` row.
- `track.open` does not expose the artifact.
- A later `track.add_material` can reject the same artifact as already bound to the track but not current material.

This is a runtime contract, state transition, response feedback, skill/contract, and test alignment bug. It must not be repaired by large PM prompt guidance, AGENTS workflow manuals, or phrase routing.

## Target Publication Contract

The only active path is:

```text
artifact.create_revision = create an active-buddy-owned draft/revision content page
track.add_material       = publish that artifact as current shared track material
track.add_proof          = publish that artifact as close proof
track.open               = read current shared material/proof references
artifact.get             = read the full body of a readable artifact id
```

`published_to_track` is a persisted artifact field set by successful track publication. It is not an active input to `artifact.create_revision`. If a caller sends `artifact.create_revision(published_to_track=...)` or `status="published"`, the call rejects before any object is written.

## Active Payload Language

Active artifact content uses Artifact V1 terms:

- `template`: one of `brief`, `proposal`, `design`, `decision`, `proof`, `note`
- `body`: non-empty markdown string
- `title`, `summary`, `source_refs`, `read_claim`, `supersedes_artifact_id`

Active track publication payloads use artifact ids:

- `track.add_material`: `track_id`, `artifact_id`, `label`, `summary`
- `track.add_proof`: `track_id`, `artifact_id`, `label`, `summary`

Legacy terms are not active env.tool payload language:

- `kind=prd`
- `content.prd`
- `content`
- inline `title/kind/content` creation through `track.add_material` or `track.add_proof`
- direct shared publication through `artifact.create_revision(published_to_track=...)`

Legacy normalization remains only inside store fixture compatibility and explicit legacy/negative tests. It is not exposed in `contracts.py`, `semantics.py`, client help text, PM contracts, PM skills, or shared tool skills as an active route.

## File Responsibility Map

- `scripts/env/services/artifacts.py`: validate artifact env.tool payloads, create private draft/revision artifacts, read readable artifact bodies, return artifact response feedback.
- `scripts/env/services/tracks.py`: validate track env.tool payloads, publish existing draft artifacts to material/proof, update track page refs, reject archived/duplicate/cross-track publication without mutation.
- `scripts/env_store.py`: canonical JSON validation and atomic object mutations for tracks and artifacts.
- `scripts/env/services/artifact_visibility.py`: decide artifact readability and currentness from artifact state plus track refs.
- `scripts/env/tools/responses.py`: canonical success/rejection response fields.
- `scripts/env/tools/contracts.py`: runtime-visible tool registry, payload fields, preconditions, returns, permissions.
- `scripts/env/tools/semantics.py`: runtime-visible atomic capability/action semantics.
- `scripts/env/client.py`: CLI operation names and help text.
- `framework/contracts/pm.md`: PM role contract.
- `buddyswitch/skills/pm/write-prd/SKILL.md`: PM product definition workflow guidance.
- `buddyswitch/skills/shared/artifact-tool/SKILL.md`: artifact tool skill.
- `buddyswitch/skills/shared/track-tool/SKILL.md`: track tool skill.
- Tests listed in the companion test plan verify behavior, responses, persisted JSON, semantics, skills, residue, and manual runtime behavior.

## Repair Coverage Map

Each memo repair item is covered by the implementation tasks below:

1. One active publication path: Tasks 2, 3, 4, 5, 6.
2. Remove orphan direct-publish path: Tasks 1, 2, 4.
3. Revision/currentness semantics: Tasks 2, 3, 4.
4. Normalize active payload language: Tasks 2, 3, 5, 6, 7.
5. Tool registry and CLI contract: Task 5.
6. Runtime semantics: Task 5.
7. Success and rejection feedback: Task 4.
8. PM role contract: Task 6.
9. PM skill behavior without AGENTS bloat: Task 6.
10. Shared tool skills: Task 6.
11. Keep AGENTS short: Task 6 and Task 7 validation.
12. Regression tests inspecting persisted JSON and env.tool responses: Task 1 and companion test plan.
13. End-to-end coverage: Task 8 and companion test plan.
14. Stale active vocabulary cleanup: Task 7.
15. Manual PM runtime verification: Task 8.

## Implementation Tasks

### Task 1: Add Contract-First Regression Tests

**Files:**

- Modify: `tests/test_artifact_env_tool.py`
- Modify: `tests/test_track_env_tool.py`
- Modify: `tests/test_env_layer_end_to_end.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tests/test_runtime_tool_feedback.py`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_buddy_env_profiles.py`
- Modify: `tests/test_turn_integration.py`

**Intent:** Define the desired user-visible runtime contract before service changes. The tests must assert env.tool responses and persisted JSON, not only `ok=true` or field presence.

**Behavior to lock:**

- `artifact.create_revision` rejects `published_to_track` and `status="published"` with `state_changed=false` and no artifact file.
- Draft revisions do not replace current shared material/proof until track publication succeeds.
- `track.add_material` and `track.add_proof` publish existing draft artifacts and update both artifact JSON and track JSON.
- Duplicate, already-bound, cross-track, archived-track, and wrong-owner publication attempts reject with actionable feedback and no state mutation.
- Design/Dev/Test can follow `track.open -> artifact.get` to read shared artifact bodies.
- Critical tool semantics are not placeholders.
- PM contract, PM skill, `track-tool`, and `artifact-tool` describe the same publication path.
- Forbidden active vocabulary is absent outside explicit legacy/negative test contexts.

**Old path replaced:** Existing tests that call `track.add_material` or `track.add_proof` with inline `kind/content` payloads must be rewritten to first call `artifact.create_revision` with `template/body`, then publish by `artifact_id`.

**Corresponding tests:** The companion test plan names each concrete test case, initial state, action, response assertions, persisted JSON assertions, and regression value.

**Verification command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py tests/test_track_env_tool.py tests/test_env_layer_end_to_end.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_buddy_env_profiles.py tests/test_turn_integration.py -q
```

**Expected result before implementation:** New or updated tests that cover the repaired contract fail on current main at the direct-publish, inline `kind/content`, semantics placeholder, response feedback, skill wording, or residue assertions.

**Expected result after Tasks 2-8:** All selected tests pass.

### Task 2: Make `artifact.create_revision` Draft-Only

**Files:**

- Modify: `scripts/env/services/artifacts.py`
- Modify: `scripts/env_store.py`
- Modify: `scripts/env/services/artifact_visibility.py`
- Test: `tests/test_artifact_env_tool.py`
- Test: `tests/test_env_layer_end_to_end.py`
- Test: `tests/test_env_tool_response_contract.py`
- Test: `tests/test_runtime_tool_feedback.py`

**Intent:** Remove artifact-side direct shared publication. Artifact creation creates draft/revision content only.

**Service changes in `scripts/env/services/artifacts.py`:**

- Active `_CREATE_FIELDS` becomes `artifact_id`, `title`, `summary`, `template`, `body`, `supersedes_artifact_id`, `source_refs`, `read_claim`.
- `status` and `published_to_track` are retired env.tool inputs for `artifact.create_revision`.
- Before generic unknown-field rejection, detect `published_to_track` and return a specific rejection:
  - `code`: `E_ARTIFACT_PUBLICATION_PATH`
  - `permission_boundary`: `artifact.publication_path`
  - `why_blocked`: `artifact.create_revision creates private drafts; track.add_material or track.add_proof publishes existing artifacts`
  - `impact`: `No artifact or track state changed.`
  - `state_changed`: `false`
  - `durability`: `none` after Task 4 updates rejection helper
  - `correctable_fields`: `["published_to_track"]`
  - `allowed_next_actions`: include creating the draft without `published_to_track`, then publishing with `track.add_material` or `track.add_proof`.
- Detect `status` and reject every supplied `status` field. Callers omit `status`; the service writes `status="draft"` itself. Return:
  - `code`: `E_ARTIFACT_PUBLICATION_PATH`
  - `correctable_fields`: `["status"]`
  - `why_blocked`: `artifact.create_revision always creates status=draft artifacts`
- Successful `artifact.create_revision` always passes `status="draft"` and `published_to_track=None` to the store.
- Successful response `effect_summary` must state that the artifact is a durable private draft and is not shared track material.
- Successful response `allowed_next_actions` must be conditional and accurate:
  - `Use track.add_material with this artifact_id when this draft should become current shared material.`
  - `Use track.add_proof with this artifact_id when this draft is close proof.`
  - `Use artifact.get with this artifact_id to read the full body.`

**Store changes in `scripts/env_store.py`:**

- Change `create_artifact_revision` so `published_to_track` is no longer an accepted parameter. Callers cannot set it.
- Change `create_artifact_revision` so `status` is no longer an accepted parameter. It writes `status: "draft"` for every created artifact.
- Keep `supersedes_artifact_id` as an accepted draft-revision link.
- Validate all inputs before mutating any prior artifact. The current behavior can mark the superseded artifact non-current before later validation fails; the repaired function must not mutate any existing artifact during draft creation if the create call rejects.
- Revision rules:
  - No `supersedes_artifact_id`: write `revision=1`, `supersedes_artifact_id=None`, `is_current=False` for drafts.
  - Supersedes a private draft owned by the active buddy: write the new draft with `revision=previous.revision+1`, `supersedes_artifact_id=previous.id`, `is_current=True`, and mark the previous private draft `is_current=False`.
  - Supersedes a published artifact: write the new artifact as `status="draft"`, `published_to_track=None`, `revision=previous.revision+1`, `supersedes_artifact_id=previous.id`, `is_current=False`, and leave the published artifact and all track refs unchanged.
  - Reject supersedes targets that are not current private drafts or current published track material/proof on a non-archived track.
- Delete the exported legacy helper `create_artifact`. It is only called by the current inline track publish path. Keep `_template_from_legacy_kind` and `validate_artifact` legacy fixture normalization because explicit legacy tests still need persisted old objects to load.

**Visibility changes in `scripts/env/services/artifact_visibility.py`:**

- Return `currentness="draft"` for draft artifacts in `artifact_summary_row`.
- Allow the owner to read drafts.
- Do not let foreign buddies read drafts.
- Continue to let all buddies read published artifacts listed in current or historical track material/proof refs on non-archived tracks.
- Return `currentness="current"` for current shared material, `currentness="proof"` for current close proof, and `currentness="superseded"` for historical material/proof refs that are no longer current.

**Old path deleted/replaced:**

- Direct artifact publication with `status="published"` and `published_to_track`.
- Store-level direct published artifact creation through `create_artifact_revision`.
- Exported `env_store.create_artifact` inline legacy creation helper.

**Corresponding tests:**

- `tests/test_artifact_env_tool.py::test_create_revision_rejects_direct_publication_without_orphan`
- `tests/test_artifact_env_tool.py::test_create_revision_rejects_status_published_without_mutation`
- `tests/test_artifact_env_tool.py::test_draft_revision_does_not_replace_current_shared_material`
- `tests/test_artifact_env_tool.py::test_superseded_published_artifact_remains_readable_and_traceable`
- `tests/test_env_layer_end_to_end.py::test_response_planes_distinguish_product_private_token_and_browser_session`
- `tests/test_env_tool_response_contract.py::test_track_and_artifact_success_contract`
- `tests/test_runtime_tool_feedback.py::test_artifact_direct_publish_rejection_has_structured_feedback`

**Verification command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py tests/test_env_layer_end_to_end.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py -q
```

**Expected result:** All selected tests pass. The direct publish regression test proves there is no artifact file whose `published_to_track` points at a track while `track.shared_materials` and `track.close_proof` lack that artifact id.

### Task 3: Make Track Publication Update Artifact and Track State Together

**Files:**

- Modify: `scripts/env/services/tracks.py`
- Modify: `scripts/env_store.py`
- Modify: `scripts/env/services/artifact_visibility.py`
- Test: `tests/test_track_env_tool.py`
- Test: `tests/test_artifact_env_tool.py`
- Test: `tests/test_env_layer_end_to_end.py`

**Intent:** Make `track.add_material` and `track.add_proof` the single shared publication entry points. Both actions publish existing draft artifacts by id and write consistent artifact and track state.

**Service changes in `scripts/env/services/tracks.py`:**

- Active `_ADD_MATERIAL_FIELDS` becomes `track_id`, `artifact_id`, `label`, `summary`.
- Active `_ADD_PROOF_FIELDS` becomes `track_id`, `artifact_id`, `label`, `summary`.
- Remove inline artifact creation from `_create_material_artifact`.
- Replace `_create_material_artifact` with two explicit helpers:
  - `_load_publishable_artifact_for_material`
  - `_load_publishable_artifact_for_proof`
- Rejections before mutation:
  - Missing `artifact_id`: `E_TRACK_PAYLOAD`, `correctable_fields=["artifact_id"]`, guidance to create a draft through `artifact.create_revision`.
  - Artifact not found: `E_TRACK_PAYLOAD`, no state change.
  - Artifact owner mismatch: `E_TRACK_ARTIFACT_SCOPE`, no state change.
  - Artifact not draft and not already current in the exact same publication slot: reject as duplicate/already-bound with no state change.
  - Artifact published to another track: reject cross-track with no state change.
  - Artifact published to same track as material when calling `track.add_proof`, or as proof when calling `track.add_material`: reject already-bound wrong publication kind with no state change.
  - Archived track: reject before artifact validation mutates anything.
- `kind`, `content`, `title`, and `source_refs` are unsupported for active track publish payloads. The rejection must name the unsupported fields and keep `state_changed=false`.

**Store changes in `scripts/env_store.py`:**

- `publish_track_material` owns the material transaction:
  - Load non-archived track and artifact.
  - Require artifact `status=="draft"` for new publication.
  - Require artifact `created_by==from_buddy`.
  - Derive track ref `kind` from artifact `template`.
  - Derive slot from `kind`, `label`, and `from_buddy`.
  - If the slot has a current material, mark that track ref `current=false` and mark the old artifact `is_current=false`.
  - If the draft has `supersedes_artifact_id`, verify it matches the current artifact for the slot or is readable track history on the same track. Reject mismatch before mutation.
  - Write the new artifact with `status="published"`, `published_to_track=track_id`, `revision` preserved or raised to previous revision + 1, `is_current=true`, and `supersedes_artifact_id` set to the replaced artifact id when replacing.
  - Append a track `shared_materials` row with `type="artifact"`, `artifact_id`, `label`, `kind`, `from_buddy`, `summary`, `current=true`, and `published_at`.
  - Persist artifact and track after all validation succeeds.
- `publish_track_proof` owns the proof transaction:
  - Load non-archived track and artifact.
  - Require artifact `status=="draft"` for new proof publication.
  - Require artifact `created_by==from_buddy`.
  - Derive proof ref `kind` from artifact `template`.
  - Derive proof slot from `kind`, `label`, and `from_buddy`.
  - Add `current` to `track.close_proof` refs. Current active writes always set the field.
  - If the same proof slot has a current proof, mark that proof row `current=false` and mark the old proof artifact `is_current=false`.
  - Write the new artifact with `status="published"`, `published_to_track=track_id`, `is_current=true`, and `supersedes_artifact_id` set when replacing.
  - Append the new `close_proof` row with `current=true`.
  - Append a `track.updates[]` row with `kind="proof"` and `refs=[{"type":"artifact","id":artifact_id}]` through the service layer after proof publication succeeds.
- Update `_normalize_proof_ref` so persisted legacy proof refs without `current` normalize to `current=true`; all active writes include the field.
- Update `validate_track` and `_track_page` behavior:
  - Persisted `shared_materials` keeps current and historical rows.
  - Persisted `close_proof` keeps current and historical rows.
  - `track.open.shared_materials` returns only current material refs.
  - `track.open.close_proof` returns only current proof refs.
- Do not create or update artifacts from track publication until every precondition is validated.

**Old path deleted/replaced:**

- Inline `track.add_material` / `track.add_proof` artifact creation via `title`, `kind`, `content`.
- Idempotent success for duplicate same-artifact publication. Duplicate publication now rejects with no mutation and actionable feedback because the host should not infer success from a no-op in a collaboration-critical path.
- Already-bound same-track artifact without a current ref is rejected as corrupted state and not repaired through a second active path.

**Corresponding tests:**

- `tests/test_track_env_tool.py::test_add_material_publishes_existing_draft_and_track_ref`
- `tests/test_track_env_tool.py::test_add_material_replaces_current_only_after_successful_publish`
- `tests/test_track_env_tool.py::test_add_material_rejects_duplicate_already_bound_and_cross_track_without_state_pollution`
- `tests/test_track_env_tool.py::test_add_proof_publishes_existing_draft_updates_close_proof_and_update`
- `tests/test_track_env_tool.py::test_add_proof_replaces_current_proof_only_after_successful_publish`
- `tests/test_track_env_tool.py::test_archive_boundaries`
- `tests/test_artifact_env_tool.py::test_publish_exposes_current_artifact_to_all_buddies`
- `tests/test_env_layer_end_to_end.py::test_pm_design_dev_test_track_artifact_publication_flow`

**Verification command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_env_layer_end_to_end.py -q
```

**Expected result:** All selected tests pass. Persisted JSON shows matching artifact publication state and track refs after every successful publication, and no JSON changes after every rejected publication.

### Task 4: Strengthen Success and Rejection Feedback

**Files:**

- Modify: `scripts/env/tools/responses.py`
- Modify: `scripts/env/services/artifacts.py`
- Modify: `scripts/env/services/tracks.py`
- Test: `tests/test_env_tool_response_contract.py`
- Test: `tests/test_runtime_tool_feedback.py`
- Test: `tests/test_track_env_tool.py`
- Test: `tests/test_artifact_env_tool.py`

**Intent:** Make env.tool responses close the loop for the host. The response must say what changed, what did not change, durability, readable scope, and the next valid atomic actions.

**Response helper changes in `scripts/env/tools/responses.py`:**

- Add `durability` to rejection payloads with default value `none`.
- Add `durability` to `_REJECTION_CANONICAL_FIELDS`.
- Keep `state_changed=false` mandatory for all rejections.
- Keep conditional next-action wording validation. Do not add phrase-triggered workflow text.

**Artifact success response changes:**

- `artifact.create_revision` success:
  - `effect_summary`: states draft/private/non-shared status.
  - `state_changed=true`
  - `durability="durable"`
  - `created_ids=[artifact_id]`
  - `state_changes=[{"object_type":"artifact","change":"draft_created","artifact_id":artifact_id}]`
  - `allowed_next_actions`: conditional `track.add_material`, `track.add_proof`, `artifact.get`.
  - `artifact.status="draft"`, `artifact.published_to_track=null`, `artifact.currentness="draft"`.

**Artifact rejection feedback changes:**

- Direct publication rejections:
  - `state_changed=false`
  - `durability="none"`
  - `impact` names both no artifact and no track mutation.
  - `correctable_fields` names `published_to_track` or `status`.
  - `allowed_next_actions` does not lead to a guaranteed rejection.
- Supersedes rejection:
  - `why_blocked` states whether the target is missing, not current, archived, not readable, wrong owner, or wrong track.
  - `correctable_fields=["supersedes_artifact_id"]`.

**Track success response changes:**

- `track.add_material` success:
  - `effect_summary` states both mutations: artifact publication state and track shared material row.
  - `state_changed=true`
  - `durability="durable"`
  - `updated_ids=[track_id, artifact_id]`
  - `state_changes` includes:
    - `{"object_type":"artifact","change":"published_material","artifact_id":artifact_id,"track_id":track_id}`
    - `{"object_type":"track","change":"material_added","track_id":track_id,"artifact_id":artifact_id}`
    - when replacing: `{"object_type":"artifact","change":"superseded","artifact_id":old_artifact_id,"track_id":track_id}`
  - `allowed_next_actions`: `track.open` and `artifact.get`.
- `track.add_proof` success:
  - `effect_summary` states artifact publication, `close_proof` ref, and proof update row.
  - `state_changes` includes artifact publication, track proof row, and update row id.
  - `allowed_next_actions`: `track.open`, `artifact.get`, and `track.update_now` when proof changes track close readiness.

**Track rejection feedback changes:**

- Archived, duplicate, already-bound, wrong-owner, missing artifact, cross-track, unsupported active payload fields:
  - `state_changed=false`
  - `durability="none"`
  - `impact` names no track and no artifact mutation.
  - `correctable_fields` names the exact field to change.
  - `allowed_next_actions` names only valid atomic alternatives.

**Old path deleted/replaced:**

- `artifact.create_revision` success text that makes a published artifact appear shared.
- `artifact.create_revision` next action that sends the host into `track.add_material` rejection.
- No-op duplicate publication success for active collaboration paths.

**Corresponding tests:**

- `tests/test_env_tool_response_contract.py::test_track_and_artifact_success_contract`
- `tests/test_env_tool_response_contract.py::test_publication_success_responses_describe_object_mutations`
- `tests/test_runtime_tool_feedback.py::test_artifact_direct_publish_rejection_has_structured_feedback`
- `tests/test_runtime_tool_feedback.py::test_publish_rejections_have_actionable_feedback_and_no_state_change`
- Publication tests in `tests/test_track_env_tool.py` and `tests/test_artifact_env_tool.py` assert `effect_summary`, `state_changed`, `durability`, `state_changes`, and `allowed_next_actions`.

**Verification command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py -q
```

**Expected result:** Every success response describes real durable state changes. Every rejection response has `state_changed=false`, `durability="none"`, actionable recovery, and persisted JSON equality before/after.

### Task 5: Align Tool Registry, Semantics, and CLI

**Files:**

- Modify: `scripts/env/tools/contracts.py`
- Modify: `scripts/env/tools/semantics.py`
- Modify: `scripts/env/client.py`
- Test: `tests/test_env_tool_semantic_contract.py`
- Test: `tests/test_env_tool_response_contract.py`
- Test: `tests/test_repo_consistency.py`

**Intent:** Make runtime-visible tool catalog and CLI help describe the same atomic publication contract implemented by services.

**Registry changes in `scripts/env/tools/contracts.py`:**

- `track.add_material.payload_fields` becomes `["track_id", "artifact_id", "label", "summary"]`.
- `track.add_material.preconditions` includes:
  - `track_id references an existing non-archived track`
  - `artifact_id references an active-buddy-owned draft artifact`
  - `artifact is not already published to another track`
- `track.add_material.returns` includes `artifact_id`, `track`, `state_changes`.
- `track.add_proof.payload_fields` becomes `["track_id", "artifact_id", "label", "summary"]`.
- `track.add_proof.preconditions` mirrors material and names close proof publication.
- `artifact.create_revision.payload_fields` becomes `["artifact_id", "title", "summary", "template", "body", "supersedes_artifact_id", "source_refs", "read_claim"]`.
- `artifact.create_revision.preconditions` states active buddy owns artifact create permission and `published_to_track/status` are not inputs.
- `artifact.update_metadata.payload_fields` must match service reality. If the action still updates `template` and `body`, include `["artifact_id", "title", "summary", "template", "body", "source_refs", "read_claim"]`.

**Semantics changes in `scripts/env/tools/semantics.py`:**

Fill real action semantics for at least:

- `track.create`
- `track.open`
- `track.add_material`
- `track.add_proof`
- `artifact.create_revision`
- `artifact.get`

For each row, fill these fields with non-empty, action-specific content:

- `use_when`
- `do_not_use_when`
- `inputs_explained`
- `side_effects`
- `success_means`
- `common_failures`

Required action semantics:

- `track.create`: PM-only creation of one shared track page; writes `buddyswitch/objects/tracks/<track-id>.json`; does not create artifacts or tasks.
- `track.open`: read-only current shared material/proof refs and timeline; returns summaries/refs, not artifact bodies; archived tracks reject.
- `track.add_material`: publishes an existing active-buddy-owned draft artifact as current track material; writes artifact publication fields and track `shared_materials`; rejects archived, duplicate, cross-track, wrong owner, and non-draft inputs without mutation.
- `track.add_proof`: publishes an existing active-buddy-owned draft artifact as close proof; writes artifact publication fields, track `close_proof`, and proof update row; rejects archived, duplicate, cross-track, wrong owner, and non-draft inputs without mutation.
- `artifact.create_revision`: creates an active-buddy-owned private draft markdown artifact; writes artifact only; does not publish; rejects `published_to_track` and `status`.
- `artifact.get`: reads full artifact body by explicit readable artifact id; read-only; owner can read drafts; all buddies can read artifacts published on readable non-archived tracks, including historical refs when id is known.

**CLI changes in `scripts/env/client.py`:**

- Update help text:
  - `track add-material`: `Publish an existing draft artifact as current track material`
  - `track add-proof`: `Publish an existing draft artifact as close proof`
  - `artifact create-revision`: `Create a private draft/revision artifact`
- No phrase routing or business workflow logic in CLI.
- Payload files remain JSON objects. The payload expectations come from the registry/semantics, not hidden client validation.

**Old path deleted/replaced:**

- Registry fields for `kind`, `content`, inline `title`, and direct `published_to_track` active inputs.
- Placeholder action semantics with empty `use_when`, empty `inputs_explained`, empty `common_failures`, and generic `success_means`.

**Corresponding tests:**

- `tests/test_env_tool_semantic_contract.py::test_critical_track_artifact_action_semantics_are_not_placeholders`
- `tests/test_env_tool_semantic_contract.py::test_publication_payload_fields_match_single_publication_path`
- `tests/test_env_tool_response_contract.py::test_context_get_and_summarize_catalog_scope`
- `tests/test_repo_consistency.py::test_env_tool_surface_uses_track_page_actions`

**Verification command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_repo_consistency.py -q
```

**Expected result:** Runtime catalog, operation semantics, compact affordances, and CLI-visible help align with the repaired service behavior. Critical action semantics are not placeholder rows.

### Task 6: Align PM Contract and Skills Without AGENTS Prompt Bulk

**Files:**

- Modify: `framework/contracts/pm.md`
- Modify: `buddyswitch/skills/pm/write-prd/SKILL.md`
- Modify: `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/track-tool/SKILL.md`
- Do not modify root `AGENTS.md` in this repair.
- Do not turn `tools/launcher/assets/buddies/pm/AGENTS.md` into a PM workflow manual.
- Test: `tests/test_runtime_skills.py`
- Test: `tests/test_repo_consistency.py`
- Test: `tests/test_buddy_env_profiles.py`

**Intent:** Make durable PM and shared-tool guidance match the same publication path while preserving layering principles.

**PM contract changes in `framework/contracts/pm.md`:**

- Remove wording that says formal PM deliverables publish through `artifact.create_revision` with `published_to_track`.
- State:
  - PM owns lifecycle through `track.create`, `track.open`, `track.update_now`, and `track.archive`.
  - PM creates private PM draft/revision artifacts through `artifact.create_revision` with `template` and markdown `body`.
  - PM publishes product direction, briefs, decisions, and close proof through `track.add_material` or `track.add_proof` with an existing `artifact_id`.
  - Durable PM outputs include track objects and artifact objects.
- Keep runtime boundary short: env.tool for durable operations, no direct edits to `buddyswitch/objects/**`, no buddybox raw-state bypass.

**PM skill changes in `buddyswitch/skills/pm/write-prd/SKILL.md`:**

- Broaden the skill from narrow PRD/MVP wording to product brief, product direction, scope, requirements, acceptance criteria, and PM decision output.
- Do not add phrase routing such as `landing page means use this skill`.
- Workflow:
  1. Read relevant `track.open` and `artifact.get` context when ids are available.
  2. Draft product-definition content in artifact `body` using `template="brief"` for product brief or `template="decision"` for decision output.
  3. Call `artifact.create_revision` to create the private draft/revision.
  4. Call `track.add_material` to publish it as current shared material, or `track.add_proof` if the artifact is close proof.
  5. Verify with `track.open` and `artifact.get`.
- Verification text must require `state_changes`, `track.open.shared_materials` or `track.open.close_proof`, and readable `artifact.get` body.

**Shared skill changes:**

- `buddyswitch/skills/shared/artifact-tool/SKILL.md`:
  - `create-revision` creates private drafts/revisions only.
  - It never directly publishes to shared tracks.
  - Shared readability begins after `track.add-material` or `track.add-proof` succeeds.
  - Defer payload details and recovery to `context.get.tool_catalog` and response fields.
- `buddyswitch/skills/shared/track-tool/SKILL.md`:
  - `add-material` and `add-proof` publish existing draft artifact ids.
  - Track publication is the shared-state mutation path.
  - `track.open` returns refs/summaries; use `artifact.get` for bodies.
  - Defer action details and recovery to runtime catalog and response fields.

**AGENTS handling:**

- Keep root and buddy AGENTS short.
- Do not add a PM procedure manual.
- Do not add phrase rules.
- Do not duplicate payload schemas in AGENTS.
- Leave existing AGENTS files unchanged and verify they remain short.

**Old path deleted/replaced:**

- PM contract text: `publish via published_to_track when shared`.
- Skill text implying `artifact.create_revision` makes shared material visible.
- Shared tool skill wording that treats artifact as a direct publish tool.

**Corresponding tests:**

- `tests/test_runtime_skills.py::test_pm_and_shared_tool_skills_describe_single_publication_path`
- `tests/test_runtime_skills.py::test_role_skills_remove_optional_handoff_guidance`
- `tests/test_repo_consistency.py::test_role_contracts_teach_direct_track_material_path`
- `tests/test_repo_consistency.py::test_runtime_buddy_agents_use_track_open_guidance`
- `tests/test_buddy_env_profiles.py::test_profiles_validate_with_matrix_rules`

**Verification command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_buddy_env_profiles.py -q
```

**Expected result:** PM contract and skills describe one path: draft with artifact, publish with track, read refs with track, read body with artifact. AGENTS files remain short and do not become PM workflow manuals.

### Task 7: Remove or Downgrade Stale Active Vocabulary

**Files:**

- Modify: `scripts/env/services/tracks.py`
- Modify: `scripts/env/services/artifacts.py`
- Modify: `scripts/env_store.py`
- Modify: `scripts/env/tools/contracts.py`
- Modify: `scripts/env/tools/semantics.py`
- Modify: `scripts/env/client.py`
- Modify: `framework/contracts/pm.md`
- Modify: `buddyswitch/skills/pm/write-prd/SKILL.md`
- Modify: `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/track-tool/SKILL.md`
- Test: `tests/test_repo_consistency.py`
- Test: `tests/test_runtime_skills.py`
- Test: `tests/test_artifact_env_tool.py`
- Test: `tests/test_track_env_tool.py`

**Intent:** Ensure old merge vocabulary cannot steer the host toward the wrong active path.

**Remove from active runtime guidance and active env.tool payloads:**

- `kind=prd`
- `content.prd`
- `content` as active artifact body payload
- direct shared publication via `artifact.create_revision(published_to_track=...)`
- task-derived artifact visibility
- `track.join`
- `track.attach_task`
- `track.detach_task`
- `task_id` as artifact publication or material visibility control

**Keep only as explicit compatibility or negative coverage:**

- `_template_from_legacy_kind` maps persisted legacy `kind` to active `template`.
- `validate_artifact` can normalize old persisted fixtures that have legacy `kind/content` and no canonical V1 fields.
- Tests may contain legacy vocabulary only when the test name or assertion makes it explicit that the old vocabulary is rejected or legacy-normalized.
- Docs under `docs/memo/**`, `docs/bitter/**`, and `docs/spec/**` may discuss old vocabulary as repair context.

**Direct code cleanup:**

- Remove active imports and calls to deleted `env_store.create_artifact`.
- Remove service branches that build artifacts from `content`.
- Remove active registry payload fields for `kind/content`.
- Remove semantics or help text that names legacy payloads as active input.

**Corresponding tests:**

- `tests/test_repo_consistency.py::test_track_artifact_publication_residue_scan`
- `tests/test_artifact_env_tool.py::test_validate_payload_rejects_retired_fields`
- `tests/test_track_env_tool.py::test_track_publish_rejects_legacy_inline_payload_without_mutation`
- `tests/test_runtime_skills.py::test_pm_and_shared_tool_skills_describe_single_publication_path`

**Verification command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py tests/test_artifact_env_tool.py tests/test_track_env_tool.py tests/test_runtime_skills.py -q
```

**Expected result:** Active runtime catalog, semantics, client help, contracts, and skills no longer present stale vocabulary as a valid route. Legacy vocabulary appears only in explicit legacy/negative tests or repair docs.

### Task 8: Verify Main Runtime Path End-to-End and Manually

**Files:**

- Modify: `tests/test_env_layer_end_to_end.py`
- Modify: `tests/test_turn_integration.py`
- No runtime code changes beyond Tasks 2-7.

**Intent:** Prove the repaired PM-to-Design-to-Dev-to-Test collaboration path works through env.tool and does not depend on task relation machinery, raw state edits, prompt bulk, or `projects/app` implementation behavior by PM.

**Automated end-to-end path:**

1. PM creates a track with `track.create`.
2. PM creates a product brief artifact draft with `artifact.create_revision(template="brief", body=...)`.
3. PM publishes it with `track.add_material(artifact_id=...)`.
4. Design opens the track, reads the PM artifact body with `artifact.get`, creates a design artifact draft, and publishes it with `track.add_material`.
5. Dev opens the track, reads PM and Design bodies with `artifact.get`, creates an implementation report/proposal draft, and publishes it with `track.add_material`.
6. Test opens the track, reads the relevant material bodies, creates a proof artifact draft with `template="proof"`, and publishes it with `track.add_proof`.
7. PM opens the track, sees current shared materials and current close proof, then updates or closes track state through `track.update_now`.

**Assertions:**

- Every write response has accurate `state_changes`.
- Persisted track JSON contains current refs and historical refs where replacements occurred.
- `track.open` exposes current shared material/proof refs only.
- `artifact.get` returns full bodies for readable ids.
- No step uses task relation actions, raw object edits, `prepare/persist`, or direct `published_to_track`.

**Manual PM runtime verification:**

- Start PM runtime:

```bash
./buddyswitch-codex instance start --buddy pm
```

- Ask for a product/landing-page PM output.
- Confirm PM uses context discovery and PM skill behavior to produce a product-definition artifact rather than editing `projects/app`.
- Confirm durable writes go through env.tool:
  - `track.create` or `track.open`
  - `artifact.create_revision`
  - `track.add_material`
  - `track.open`
  - `artifact.get`
- Confirm `track.open.shared_materials` exposes the PM artifact id.
- Confirm Design or Dev can read the full body through `artifact.get`.
- Confirm PM does not treat read-only `projects/app` as an implementation target.

**Corresponding tests:**

- `tests/test_env_layer_end_to_end.py::test_pm_design_dev_test_track_artifact_publication_flow`
- `tests/test_turn_integration.py::test_pm_product_request_uses_track_artifact_publication_not_project_write`
- `tests/test_buddy_env_profiles.py::test_profiles_validate_with_matrix_rules`

**Verification command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_turn_integration.py tests/test_buddy_env_profiles.py -q
```

**Expected result:** Automated E2E path passes. Manual runtime produces durable track/artifact state through env.tool and does not rely on PM prompt bulk or direct project implementation.

## Full Verification

Run focused tests while implementing each task. After all tasks pass, run the full repair verification set:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_env_layer_end_to_end.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_buddy_env_profiles.py tests/test_turn_integration.py -q
```

Expected result: all selected tests pass.

Run syntax verification for touched Python modules:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env/services/artifacts.py scripts/env/services/tracks.py scripts/env/services/artifact_visibility.py scripts/env_store.py scripts/env/tools/contracts.py scripts/env/tools/semantics.py scripts/env/tools/responses.py scripts/env/client.py
```

Expected result: command exits 0 with no syntax errors.

Run residue scan:

```bash
rg -n "kind=prd|content\\.prd|published_to_track|track\\.join|attach_task|detach_task|attach-task|detach-task|task-derived artifact|task_id.*artifact" AGENTS.md scripts buddyswitch framework tools/launcher/assets/buddies tests -g '!**/__pycache__/**' -g '!**/*.pyc'
```

Expected result: hits are limited to explicit legacy/negative tests, persisted schema field names, repair docs, and code that persists or validates `published_to_track` as a store field set by track publication. No active runtime guidance says to call `artifact.create_revision(published_to_track=...)`.

## Acceptance Criteria

The repair is complete when all criteria are true:

- There is one active shared publication path: draft with `artifact.create_revision`, publish with `track.add_material` or `track.add_proof`.
- No env.tool call can create an artifact whose state says it is published to a track while the track page does not expose it as material/proof or history.
- `artifact.create_revision` rejects `published_to_track` and `status` inputs with no mutation.
- Creating a draft revision does not replace current shared material or proof.
- Replacing current material/proof occurs only after successful track publication.
- Superseded artifacts remain traceable and readable by explicit id on non-archived tracks, with correct currentness.
- Archived tracks reject publish/read paths with no state mutation.
- Duplicate, already-bound, and cross-track publication attempts reject with actionable feedback and no state mutation.
- `track.add_material` and `track.add_proof` feedback precisely describe artifact mutation, track ref mutation, and proof update mutation.
- `contracts.py`, `semantics.py`, `client.py`, PM contract, PM skill, `track-tool`, `artifact-tool`, services, and tests all describe the same path.
- Active payload language uses `template/body`; legacy `kind/content/content.prd` appears only in legacy/negative tests or repair context docs.
- AGENTS remains short and does not become a PM workflow manual or phrase router.
- PM -> Design -> Dev -> Test main path works without task relation actions or raw state edits.

## Remaining Risks

- This plan repairs future writes and tests legacy normalization, but does not migrate arbitrary live state. Orphan rows already present require a separate cleanup change if they exist.
- Historical proof refs gain `current`; legacy proof rows without that field normalize as current. If a workspace contains multiple old proof rows in the same slot, the first post-repair replacement will establish currentness going forward.
- Manual PM runtime behavior depends on the host selecting the PM skill from available skill metadata. This plan avoids prompt bulk and verifies the lower runtime contract; if PM still ignores an applicable skill after the runtime contract is correct, that becomes a separate skill-selection problem.
