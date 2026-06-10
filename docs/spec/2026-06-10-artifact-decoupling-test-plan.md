# Artifact Decoupling Rebuild Test Plan

Date: 2026-06-10
Source memo: `docs/memo/2026-06-09-artifact-decoupling-rebuild-task.md`
Resource guard: `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

## Goal

Prove that Artifact is an independent content carrier and Track owns only relation facts to
Artifacts. Artifact readability may be granted by Track-side relations, but Artifact rows must not
store Track lifecycle, Track publication, material slot, or proof slot truth.

## Current Bottleneck

The current runtime still treats Track publication as Artifact lifecycle:

- `scripts/env/repos/artifacts.py` stores and validates `status` plus `published_to_track`.
- `scripts/env/domain/publication.py` mutates both Track and Artifact during material/proof writes.
- `scripts/env/repos/tracks.py` stores old `shared_materials` and `close_proof` slot fields.
- `scripts/env/domain/artifact_visibility.py` reads `published_to_track` to decide readability.
- Tests and tool descriptions still assert publication language and Artifact mutation effects.

The test suite must move the product contract to one clear path:

```text
Artifact row = content, authoring, source refs, attachments, revision lineage.
Track artifact relation = Track-owned reference from collaboration context to one Artifact id.
track.add_material / track.add_proof = Track-side relation writes, not Artifact publication.
```

## Non-Negotiable Test Principles

- Start new behavior with failing tests.
- Replace old publication assertions instead of adding parallel old/new compatibility tests.
- Do not test implementation shortcuts. Tests must express user-visible and repository contracts.
- Use runless `unittest` tests first. Do not start launcher instances or daemons for this rebuild.
- Before broad verification, confirm no service-starting tests are being added.
- If a verification command starts long-lived services, run one focused case first and inspect
  residual processes before scaling up.

## Test Coverage Matrix

### 1. Artifact Repository Contract

Files:

- `tests/test_env_store_v2.py`
- `scripts/env/repos/artifacts.py`

Required tests:

1. `ArtifactStoreContractTests.test_create_artifact_uses_independent_content_carrier_shape`
   - Create an Artifact revision.
   - Assert the persisted row keys are exactly:
     `id`, `title`, `summary`, `body`, `template`, `revision`, `is_current`,
     `supersedes_artifact_id`, `created_by_actor`, `author_actors`, `source_refs`,
     `attachments`, `created_at`, `updated_at`.
   - Assert `status`, `published_to_track`, `publication_role`, `kind`, `content`, and
     `task_id` are absent.

2. `ArtifactStoreContractTests.test_artifact_validation_rejects_publication_lifecycle_fields`
   - Build an otherwise valid Artifact row.
   - Add each stale field one at a time: `status`, `published_to_track`, `publication_role`.
   - Assert `validate_artifact` raises `ValueError`.

3. `ArtifactStoreContractTests.test_superseding_artifact_is_artifact_local_currentness`
   - Create `art-r1`, then create `art-r2` with `supersedes_artifact_id="art-r1"`.
   - Assert `art-r1.is_current` becomes `False`.
   - Assert `art-r2.is_current` is `True`.
   - Assert neither row contains Track fields.

### 2. Track Repository Relation Contract

Files:

- `tests/test_track_env_tool.py`
- `tests/test_env_store_v2.py`
- `scripts/env/repos/tracks.py`

Required tests:

1. `TrackStoreContractTests.test_create_track_uses_artifact_relations_not_publication_slots`
   - Create a Track.
   - Assert persisted row contains `artifact_relations`.
   - Assert `shared_materials` and `close_proof` are absent.

2. `TrackEnvToolTests.test_add_material_creates_track_relation_without_artifact_mutation`
   - PM creates Track and Artifact.
   - Run `track.add_material`.
   - Assert Artifact before and after is identical except no expected Artifact change is allowed.
   - Assert Track has one relation row:
     `relation_id`, `type="artifact"`, `artifact_id`, `role="material"`, `label`,
     `template`, `from_actor`, `summary`, `current=True`, `created_at`.
   - Assert no `published_to_track`, `status`, `shared_materials`, or `close_proof`.

3. `TrackEnvToolTests.test_add_proof_creates_relation_and_timeline_update_without_artifact_mutation`
   - Test role creates proof Artifact.
   - Run `track.add_proof`.
   - Assert Artifact row is unchanged.
   - Assert Track relation has `role="proof"` and `current=True`.
   - Assert one Track update row is appended with `kind="proof"` and an Artifact ref.

4. `TrackEnvToolTests.test_same_artifact_can_be_related_to_multiple_tracks_without_republication`
   - Create two Tracks and one owner Artifact.
   - Add the same Artifact as material to both Tracks.
   - Assert both Tracks hold independent relation rows.
   - Assert Artifact still has no Track-bound fields.

5. `TrackEnvToolTests.test_relation_replacement_demotes_only_track_relation_currentness`
   - Add `art-r1` as current material.
   - Create `art-r2` with `supersedes_artifact_id="art-r1"`.
   - Add `art-r2` as the same material slot.
   - Assert old relation `current=False`, new relation `current=True`.
   - Assert Artifact currentness follows Artifact lineage only: `art-r1.is_current=False`,
     `art-r2.is_current=True`.

6. `TrackEnvToolTests.test_relation_write_failure_does_not_mutate_track_or_artifact`
   - Patch Track save to fail on first save.
   - Run `track.add_material`.
   - Assert rejection.
   - Assert Track and Artifact snapshots match the before state.

### 3. Artifact Readability And Listing

Files:

- `tests/test_artifact_env_tool.py`
- `scripts/env/domain/artifact_visibility.py`
- `scripts/env/tools/artifact/_impl.py`

Required tests:

1. `ArtifactEnvToolTests.test_private_artifact_is_owner_only_before_track_relation`
   - Create Artifact as PM.
   - Assert PM can `artifact.get`.
   - Assert Design cannot `artifact.get`.

2. `ArtifactEnvToolTests.test_track_relation_exposes_artifact_to_all_track_collaborators`
   - PM creates Artifact and relates it to a Track.
   - Dev gets Artifact body through `artifact.get`.
   - Dev lists it through `artifact.list`.
   - Returned rows include relation metadata, not `published_to_track`.

3. `ArtifactEnvToolTests.test_artifact_list_track_filter_uses_track_relations`
   - Share one Artifact to Track A and another to Track B.
   - `artifact.list(track_id=Track A)` returns only Track A relation artifacts.
   - The filter works even though Artifact rows have no Track id field.

4. `ArtifactEnvToolTests.test_archived_track_relation_does_not_grant_foreign_read`
   - Share an Artifact to a Track.
   - Archive the Track.
   - A non-owner role cannot read the Artifact through that relation.
   - The owner can still read the Artifact as owner content.

5. `ArtifactEnvToolTests.test_superseded_related_artifact_remains_readable_as_track_history`
   - Relate `art-r1`, then supersede and relate `art-r2`.
   - A collaborator can read both.
   - `art-r1` relation metadata says historical/superseded, while `art-r2` is current.

### 4. Attachments

Files:

- `tests/test_artifact_env_tool.py`
- `tests/test_track_env_tool.py`

Required tests:

1. `ArtifactEnvToolTests.test_related_attachment_is_readable_by_track_collaborator`
   - Owner creates Artifact, attaches a file, relates Artifact to Track.
   - Another role can list attachment summaries and read exact attachment content.
   - No file path appears in response.

2. `TrackEnvToolTests.test_track_open_projects_relation_attachment_summaries`
   - Add one material relation and one proof relation, each with an attachment.
   - `track.open` returns attachment summaries on relation rows.
   - No `content_base64` or filesystem path appears in Track output.

### 5. Tool Semantics, Context, And Guidance

Files:

- `tests/test_env_tool_response_contract.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`
- `scripts/env/tools/artifact/tool.py`
- `scripts/env/tools/track/tool.py`
- `scripts/env/tools/context/_impl.py`

Required tests:

1. `EnvToolResponseContractTests.test_track_relation_success_responses_describe_track_only_mutations`
   - `track.add_material` and `track.add_proof` success responses must describe Track relation
     changes and must not claim Artifact publication/status mutation.

2. `ContextBindingEnvToolTests.test_context_summarize_describes_artifacts_as_content_carriers`
   - Context capability snapshot says Artifact manages content and Track manages relations.
   - It does not mention `published_to_track`, publication slots, `shared_materials`, or
     `close_proof`.

3. `RuntimeSkillsTests.test_pm_and_shared_tool_skills_describe_single_track_relation_path`
   - Role skills may mention `track.add_material` and `track.add_proof`.
   - They must not mention `published_to_track`.
   - They must describe Track-side relation/share behavior, not Artifact publication.

4. `RepoConsistencyTests.test_artifact_decoupling_residue_scan`
   - Scan active runtime code and role assets.
   - Disallow `published_to_track`, `"status": "published"`, `shared_materials`,
     `close_proof`, and actor-facing `publication` wording except in docs/memo, docs/spec,
     docs/bitter, and this residue test's own pattern construction.

5. `EnvLayerBoundaryTests.test_track_artifact_relation_domain_is_only_cross_object_write_domain`
   - Replaces the old publication-domain boundary test.
   - Track/Artifact relation writes may live only in the new relation domain and Track tool.
   - Artifact repo must not import Track repo.
   - Track repo must not import Artifact repo.

### 6. End-To-End Runless Product Flow

Files:

- `tests/test_env_layer_end_to_end.py`
- `tests/test_turn_integration.py`

Required tests:

1. `EnvLayerEndToEndTests.test_pm_design_dev_test_track_artifact_relation_flow`
   - PM creates Track and brief Artifact, then relates material.
   - Design and Dev create and relate their Artifacts.
   - Test creates and relates proof.
   - Track page shows relation rows with material/proof roles and proof timeline evidence.
   - Artifact rows remain independent content carrier rows.

2. `TurnRuntimeIntegrationTests.test_pm_product_material_flow_uses_track_artifact_relations`
   - Replace old publication assertions with Track relation assertions.
   - Assert no project-file write path or Artifact lifecycle publication path is used.

## Verification Commands

Run in this order:

```bash
python -m unittest tests.test_env_store_v2.ArtifactStoreContractTests tests.test_env_store_v2.TrackStoreContractTests
python -m unittest tests.test_track_env_tool.TrackEnvToolTests.test_add_material_creates_track_relation_without_artifact_mutation
python -m unittest tests.test_track_env_tool.TrackEnvToolTests.test_add_proof_creates_relation_and_timeline_update_without_artifact_mutation
python -m unittest tests.test_artifact_env_tool.ArtifactEnvToolTests.test_track_relation_exposes_artifact_to_all_track_collaborators
python -m unittest tests.test_artifact_env_tool tests.test_track_env_tool
python -m unittest tests.test_env_layer_end_to_end tests.test_turn_integration
python -m unittest tests.test_env_tool_response_contract tests.test_context_binding_env_tool tests.test_runtime_skills tests.test_repo_consistency tests.test_env_layer_boundaries
python -m unittest discover tests
```

Resource lifecycle check before and after any broad command:

```bash
ps -axo pid,ppid,pgid,command | rg 'buddyswitch-codex|runtime_broker|app-server|fake Codex|Chrom(e|ium)|Playwright' || true
```

The expected result for focused runless tests is no new persistent process. If this check shows new
launcher, broker, browser, or app-server processes after a test command, stop and fix cleanup before
running broader verification.

## Completion Evidence

The rebuild is test-complete only when:

- All required focused tests have failed before implementation and passed after implementation.
- Broad relevant suites pass.
- `python -m unittest discover tests` passes or any excluded service-starting tests are explicitly
  justified with residual process evidence.
- Residue scan has no active-code hits for old Track/Artifact publication contracts.
- Process residual check is clean before final completion.

## Self-Review

- Coverage: This plan covers repo shape, Track relation writes, readability, attachments, context,
  role guidance, end-to-end product flow, boundary scans, and broad verification.
- Scope: This plan intentionally excludes notification center work and `artifact.shared` runtime
  handler registration, matching the memo's forbidden worktree scope.
- Resource safety: Verification starts with runless focused tests and requires residual process
  checks before broad execution.
- Forward principle: Tests remove old publication assertions and replace them with Track relation
  assertions. There is no dual old/new compatibility path.
