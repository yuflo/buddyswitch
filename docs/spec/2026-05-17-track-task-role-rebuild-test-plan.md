# Track Task Role Rebuild Test Plan

## 1. Test Objective

Prove BuddySwitch collaboration no longer depends on task relations. The observable product behavior must be:

- A non-archived track is the shared progress page.
- Current shared materials and close proof are readable directly from the track page and by `artifact.get`.
- Tasks are private buddy work aids and do not grant cross-buddy access.
- Archived tracks are hard visibility and mutation boundaries.
- Removed relation operations are absent from active runtime surfaces.

Tests must start from product behavior and risk, not from current implementation helpers. New behavior tests should fail before implementation and pass only after direct track publication replaces the task bridge.

## 2. Requirement Coverage Matrix

| ID | Requirement, risk, or boundary | Primary tests |
| --- | --- | --- |
| `RTR-001` | PM creates a track with human-readable `outcome`, `appetite`, `now`, fixed `state`, fixed `health`, PM owner, timestamps, empty materials, empty updates, empty proof, and no task relation fields. | `RTR-STORE-001`, `RTR-TRACK-001`, `RTR-SURF-003` |
| `RTR-002` | Only PM can create and archive tracks. | `RTR-TRACK-002`, `RTR-ARCH-002` |
| `RTR-003` | All buddies can list and open non-archived tracks. | `RTR-TRACK-003`, `RTR-CTX-001` |
| `RTR-004` | Archived tracks are omitted from normal lists and reject open, now updates, material updates, timeline updates, proof updates, comments, and reads of published artifacts. | `RTR-ARCH-001` to `RTR-ARCH-006` |
| `RTR-005` | `track.open` returns a page shape, not task context, and never includes full artifact bodies. | `RTR-TRACK-004` |
| `RTR-006` | `track.add_material` publishes an artifact directly to `track.shared_materials` and `artifact.published_to_track`. | `RTR-MAT-001`, `RTR-MAT-002`, `RTR-STORE-002` |
| `RTR-007` | Current material view shows current refs by default and supersedes older refs for the same `(kind, label, from_buddy)`. | `RTR-MAT-003`, `RTR-ART-003` |
| `RTR-008` | `artifact.get` allows all buddies to read current published materials on non-archived tracks without `track.join` or a task. | `RTR-ART-001`, `RTR-E2E-001` |
| `RTR-009` | Non-owner draft artifacts and non-current historical materials are not readable through collaboration. | `RTR-ART-002`, `RTR-ART-003` |
| `RTR-010` | `track.add_update` creates concise progress/decision/blocker/proof timeline rows and rejects invalid kind or invalid refs without mutation. | `RTR-UPD-001`, `RTR-FAIL-003`, `RTR-FAIL-004` |
| `RTR-011` | `track.add_proof` publishes exact proof refs, adds a proof update, and allows PM to mark the track done through `track.update_now`. | `RTR-PROOF-001`, `RTR-E2E-001` |
| `RTR-012` | Tasks are active-buddy private; `task.track_id` is only a hint and does not mutate tracks or grant access. | `RTR-TASK-001` to `RTR-TASK-004` |
| `RTR-013` | Removed operations and fields are rejected or absent: `track.get`, `track.update`, `track.join`, `track.attach_task`, `track.detach_task`, `artifact.list`, `track.task_ids`, `artifact.task_id`, `task.artifact_ids`, `task.artifact_slots`. | `RTR-SURF-001` to `RTR-SURF-006`, `RTR-STORE-004` |
| `RTR-014` | Context, workspace projection, console, artifact selection, cleanup, role contracts, skills, manifest, CLI, and runtime status use the track-page model. | `RTR-CTX-001`, `RTR-PROJ-001`, `RTR-SEL-001`, `RTR-CLEAN-001`, `RTR-DOC-001` to `RTR-DOC-004` |
| `RTR-015` | Message/comment tools remain atomic and comment artifact read boundaries use direct published-material visibility. | `RTR-COM-001`, `RTR-COM-002` |

## 3. Failing-First Tests

These tests must be added or rewritten before implementation and verified red:

- `RTR-STORE-001` through `RTR-STORE-004`
- `RTR-TRACK-001` through `RTR-TRACK-005`
- `RTR-MAT-001` through `RTR-MAT-003`
- `RTR-ART-001` through `RTR-ART-004`
- `RTR-TASK-001` through `RTR-TASK-004`
- `RTR-SURF-001` through `RTR-SURF-006`
- `RTR-E2E-001`

Expected initial failures are missing action registration, old validators expecting `task_ids`/`task_id`, old artifact read denial for buddies without task relations, and old CLI/skill surfaces exposing relation operations.

## 4. Unit And Store Tests

### `RTR-STORE-001`: track validator accepts page shape and rejects old relation fields

- **Purpose:** Lock the new durable track contract.
- **Initial state:** Runtime test workspace has no track files.
- **Steps:** Call `env_store.validate_track()` with the target track JSON. Then call it with payloads containing `task_ids`, `status`, `summary`, `current_buddy`, `next_buddy`, and `artifact_ids`.
- **Expected result:** Target shape normalizes successfully. Each old-field payload raises `ValueError`; no file is written.
- **Covers:** `RTR-001`, `RTR-013`.
- **Suggested file:** `tests/test_env_store_v2.py::TrackStoreContractTests::test_validate_track_accepts_page_shape_and_rejects_relation_fields`.

### `RTR-STORE-002`: material publication writes track ref and artifact publication metadata

- **Purpose:** Prove durable publication is direct to track.
- **Initial state:** PM track exists in target shape.
- **Steps:** Call the store helper used by `track.add_material` with PRD payload.
- **Expected result:** Track `shared_materials` contains one current ref with artifact id and `from_buddy="pm"`; artifact has `published_to_track` set to the track id, `publication_role="material"`, and no `task_id`.
- **Covers:** `RTR-006`.
- **Suggested file:** `tests/test_env_store_v2.py::ArtifactPublicationStoreTests::test_publish_material_writes_track_ref_and_artifact_metadata`.

### `RTR-STORE-003`: proof publication writes exact close proof ref

- **Purpose:** Protect close proof traceability.
- **Initial state:** Non-archived track exists.
- **Steps:** Publish a smoke-test proof artifact through the store helper used by `track.add_proof`.
- **Expected result:** `close_proof` contains the exact proof artifact id and `publication_role="proof"`; `shared_materials` is unchanged.
- **Covers:** `RTR-011`.
- **Suggested file:** `tests/test_env_store_v2.py::ArtifactPublicationStoreTests::test_publish_proof_writes_exact_close_proof_ref`.

### `RTR-STORE-004`: task validator rejects artifact linkage fields

- **Purpose:** Keep task private and non-collaboration-defining.
- **Initial state:** No task files.
- **Steps:** Validate a private task shape, then validate payloads containing `artifact_ids` and `artifact_slots`.
- **Expected result:** Private task shape passes; old artifact linkage fields raise `ValueError`.
- **Covers:** `RTR-012`, `RTR-013`.
- **Suggested file:** `tests/test_env_store_v2.py::ResolveTimeTaskMaterializationTests::test_task_shape_has_no_artifact_linkage_fields`.

## 5. Track Tool Tests

### `RTR-TRACK-001`: PM creates a human-readable track

- **Purpose:** Verify track creation target shape through broker-routed `env.tool`.
- **Initial state:** PM instance JSON exists.
- **Steps:** Dispatch `track.create` with `track_id`, `title`, `outcome`, `appetite`, and `now`.
- **Expected result:** `ok=true`; response track has `owner_buddy="pm"`, `state="active"`, `health="ok"`, empty arrays, timestamps, and no `task_ids`, `status`, or `summary`; stored JSON matches.
- **Covers:** `RTR-001`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_pm_creates_human_readable_track_page`.

### `RTR-TRACK-002`: non-PM cannot create track

- **Purpose:** Enforce PM-only lifecycle creation.
- **Initial state:** Design instance JSON exists.
- **Steps:** Dispatch `track.create` as Design.
- **Expected result:** `ok=false`, error code `E_TRACK_AUTHORITY`, `permission_boundary="track.lifecycle_authority"`, `state_changed=false`, no track file.
- **Covers:** `RTR-002`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_non_pm_cannot_create_track`.

### `RTR-TRACK-003`: all buddies can list and open non-archived tracks

- **Purpose:** Prove V1 has no participation model.
- **Initial state:** PM creates one active track.
- **Steps:** Dispatch `track.list` and `track.open` as PM, Design, Dev, Market, and Test.
- **Expected result:** Every buddy receives `ok=true`; track id appears in list; open returns the same track page shape.
- **Covers:** `RTR-003`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_all_buddies_can_list_and_open_non_archived_tracks`.

### `RTR-TRACK-004`: track.open is page-shaped and body-safe

- **Purpose:** Prevent old task context and artifact body leakage.
- **Initial state:** Track has one published PRD material with unique body text.
- **Steps:** Dispatch `track.open` as Dev.
- **Expected result:** Response contains `shared_materials`, `updates`, and `close_proof`; response does not contain `tasks`, `task_ids`, `source_task_id`, `artifact_slots`, `content`, or the unique body text.
- **Covers:** `RTR-005`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_track_open_returns_page_without_tasks_or_artifact_bodies`.

### `RTR-TRACK-005`: all buddies can update now-state on non-archived track

- **Purpose:** Verify simple V1 shared current-state mutation.
- **Initial state:** Active track exists.
- **Steps:** Dispatch `track.update_now` as Design with new `now.next`, `now.blocker`, `state="blocked"`, and `health="blocked"`.
- **Expected result:** `ok=true`, track now-state changes, one progress update is appended, and no task is created.
- **Covers:** `RTR-010`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_all_buddies_can_update_now_state_on_non_archived_track`.

## 6. Material And Artifact Tests

### `RTR-MAT-001`: track.add_material creates and publishes PRD

- **Purpose:** Prove main publication path.
- **Initial state:** PM-created active track exists.
- **Steps:** Dispatch `track.add_material` as PM with `kind="prd"`, `label="PRD"`, `summary`, and JSON `content`.
- **Expected result:** `ok=true`; returns `artifact_id`; `track.open.shared_materials` contains current PRD ref; `artifact.get` as PM returns body; stored artifact has `published_to_track` and no `task_id`.
- **Covers:** `RTR-006`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_add_material_creates_artifact_and_track_ref`.

### `RTR-MAT-002`: design publishes draft to same track without task

- **Purpose:** Prove cross-buddy publishing does not require joining.
- **Initial state:** Track has PM PRD material; Design has no task.
- **Steps:** Dispatch `track.add_material` as Design with `kind="design-handoff"` and draft content.
- **Expected result:** `ok=true`; `track.open` as Dev shows both PM PRD and Design draft; no Design task file exists.
- **Covers:** `RTR-006`, `RTR-012`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_design_publishes_material_without_task_relation`.

### `RTR-MAT-003`: newer material supersedes older current ref

- **Purpose:** Keep default track page current-only.
- **Initial state:** Track has PM PRD r1 current.
- **Steps:** PM dispatches `track.add_material` with same `kind`, `label`, and `from_buddy` for r2.
- **Expected result:** `track.open.shared_materials` includes r2 as current and omits r1 from default current rows; stored track may retain r1 with `current=false`; non-owner `artifact.get` for r1 rejects with `artifact.currentness`.
- **Covers:** `RTR-007`, `RTR-009`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_new_material_supersedes_default_current_ref`.

### `RTR-ART-001`: non-owner reads current material without task relation

- **Purpose:** Prove direct cross-buddy read path.
- **Initial state:** PM publishes PRD to active track; Dev has no task.
- **Steps:** Dev dispatches `artifact.get` for PRD artifact id.
- **Expected result:** `ok=true`; response relation is `track_material`; response includes full `content`; serialized response does not contain `track_task`, `join`, or `source_task_id`.
- **Covers:** `RTR-008`.
- **Suggested file:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_non_owner_reads_current_material_without_task_relation`.

### `RTR-ART-002`: non-owner cannot read private draft artifact

- **Purpose:** Preserve draft/private boundary.
- **Initial state:** PM creates a private artifact through `artifact.create_revision` with `published_to_track=null`.
- **Steps:** Dev dispatches `artifact.get` for the private artifact id.
- **Expected result:** `ok=false`, error code `E_ARTIFACT_READ_SCOPE`, `permission_boundary="artifact.publication"`, no content leak.
- **Covers:** `RTR-009`.
- **Suggested file:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_non_owner_cannot_read_private_draft_artifact`.

### `RTR-ART-003`: non-owner cannot read superseded material

- **Purpose:** Enforce current-only default collaboration reads.
- **Initial state:** PM publishes PRD r1 and r2 on same track; r1 is superseded.
- **Steps:** Dev dispatches `artifact.get` for r1.
- **Expected result:** `ok=false`, `permission_boundary="artifact.currentness"`, serialized response does not contain r1 body.
- **Covers:** `RTR-007`, `RTR-009`.
- **Suggested file:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_non_owner_cannot_read_superseded_material`.

### `RTR-ART-004`: artifact.create_revision no longer requires task_id

- **Purpose:** Remove task as artifact write prerequisite.
- **Initial state:** Design instance exists and no Design task exists.
- **Steps:** Design dispatches `artifact.create_revision` with `artifact_id`, `kind`, `title`, `summary`, and `content`.
- **Expected result:** `ok=true`; artifact is private with `created_by="design"` and `published_to_track=null`; passing `task_id` in payload rejects with `E_ARTIFACT_PAYLOAD`.
- **Covers:** `RTR-012`, `RTR-013`.
- **Suggested file:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_create_revision_creates_private_artifact_without_task_id`.

## 7. Update And Proof Tests

### `RTR-UPD-001`: track.add_update creates concise timeline row

- **Purpose:** Verify shared updates are not comments or task status.
- **Initial state:** Active track exists and has one material.
- **Steps:** Design dispatches `track.add_update` with `kind="blocker"`, summary, and artifact ref.
- **Expected result:** `ok=true`; update id starts with `upd-`; row has `by_buddy="design"`, kind, refs, and timestamp; task objects unchanged.
- **Covers:** `RTR-010`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_add_update_creates_shared_timeline_row`.

### `RTR-PROOF-001`: track.add_proof publishes exact proof artifact

- **Purpose:** Verify close proof behavior.
- **Initial state:** Active track has PM and Design materials.
- **Steps:** Test buddy dispatches `track.add_proof` with `kind="smoke-test"` and result content.
- **Expected result:** `ok=true`; `close_proof` contains exact artifact id; a proof update is appended; `artifact.get` as PM returns proof content.
- **Covers:** `RTR-011`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_add_proof_publishes_exact_proof_ref`.

## 8. Task Privacy Tests

### `RTR-TASK-001`: task create with track_id does not mutate track

- **Purpose:** Keep `track_id` as private organization hint.
- **Initial state:** Active track exists; take track JSON snapshot.
- **Steps:** Dev dispatches `task.create` with `track_id`.
- **Expected result:** `ok=true`; task stores `track_id`; track JSON equals pre-create snapshot.
- **Covers:** `RTR-012`.
- **Suggested file:** `tests/test_task_env_tool.py::TaskEnvToolTests::test_task_track_id_hint_does_not_mutate_track`.

### `RTR-TASK-002`: task remains active-buddy private

- **Purpose:** Preserve buddy-private task scope.
- **Initial state:** Dev task exists with `track_id` hint.
- **Steps:** PM dispatches `task.get` for Dev task.
- **Expected result:** `ok=false`, `permission_boundary="task.buddy_scope"`, no task details leak.
- **Covers:** `RTR-012`.
- **Suggested file:** `tests/test_task_env_tool.py::TaskEnvToolTests::test_task_get_rejects_foreign_private_task`.

### `RTR-TASK-003`: task relation does not grant artifact access

- **Purpose:** Prevent old task-derived visibility from returning.
- **Initial state:** PM private draft artifact exists; Dev task exists with same `track_id` hint.
- **Steps:** Dev dispatches `artifact.get` for PM private draft.
- **Expected result:** Read rejects with `artifact.publication`; Dev task hint does not matter.
- **Covers:** `RTR-009`, `RTR-012`.
- **Suggested file:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_task_hint_does_not_grant_artifact_access`.

### `RTR-TASK-004`: task responses omit artifact linkage

- **Purpose:** Remove task as artifact summary surface.
- **Initial state:** Dev task exists.
- **Steps:** Dev dispatches `task.get` and `task.list`.
- **Expected result:** Task rows contain no `artifact_ids`, `artifact_slots`, `current_artifacts`, or `shared_materials`.
- **Covers:** `RTR-012`, `RTR-013`.
- **Suggested file:** `tests/test_task_env_tool.py::TaskEnvToolTests::test_task_rows_omit_artifact_linkage_fields`.

## 9. Archive And Failure Path Tests

### `RTR-ARCH-001`: track.list omits archived tracks

- **Purpose:** Enforce normal collaboration visibility.
- **Initial state:** One active track and one archived track exist.
- **Steps:** Dispatch `track.list` as Dev.
- **Expected result:** Active id appears; archived id does not appear.
- **Covers:** `RTR-004`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_track_list_omits_archived_tracks`.

### `RTR-ARCH-002`: only PM can archive track

- **Purpose:** Enforce lifecycle authority.
- **Initial state:** Active track exists.
- **Steps:** Design dispatches `track.archive`.
- **Expected result:** `ok=false`, `permission_boundary="track.lifecycle_authority"`, track `archived_at` remains `null`.
- **Covers:** `RTR-002`, `RTR-004`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_only_pm_can_archive_track`.

### `RTR-ARCH-003`: archived track rejects open and mutations

- **Purpose:** Ensure archive is a hard collaboration boundary.
- **Initial state:** PM archives a track.
- **Steps:** Dispatch `track.open`, `track.update_now`, `track.add_update`, `track.add_material`, and `track.add_proof` as Dev.
- **Expected result:** Every response is `ok=false`, code `E_TRACK_ARCHIVED`, `permission_boundary="track.lifecycle_status"`, and `state_changed=false`.
- **Covers:** `RTR-004`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_archived_track_rejects_open_and_mutations`.

### `RTR-ARCH-004`: archived published artifact rejects owner and non-owner reads

- **Purpose:** Prevent archived track material leakage.
- **Initial state:** PM publishes PRD, then archives track.
- **Steps:** PM and Dev dispatch `artifact.get` for PRD artifact id.
- **Expected result:** Both reject with `permission_boundary="track.lifecycle_status"` and no body text.
- **Covers:** `RTR-004`.
- **Suggested file:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_archived_published_artifact_rejects_owner_and_non_owner_reads`.

### `RTR-ARCH-005`: comments reject archived track and archived material

- **Purpose:** Keep comment target boundary aligned with collaboration read boundary.
- **Initial state:** Archived track contains published material.
- **Steps:** Dispatch `comment.add` and `comment.list` for the track and material.
- **Expected result:** All reject with `track.lifecycle_status`.
- **Covers:** `RTR-004`, `RTR-015`.
- **Suggested file:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comments_reject_archived_track_and_material`.

### `RTR-ARCH-006`: context omits archived track and materials

- **Purpose:** Prevent archived work from context discovery.
- **Initial state:** One active track with material and one archived track with material exist.
- **Steps:** Dispatch `context.get` and `context.summarize` as Dev.
- **Expected result:** Active track/material appears; archived track/material does not appear.
- **Covers:** `RTR-004`, `RTR-014`.
- **Suggested file:** `tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_omits_archived_track_pages_and_materials`.

### `RTR-FAIL-001`: invalid track state and health reject before mutation

- **Purpose:** Lock fixed short vocabularies.
- **Initial state:** Active track exists and snapshot is captured.
- **Steps:** Dispatch `track.update_now` with `state="waiting"` and with `health="yellow"`.
- **Expected result:** Each rejects with `E_TRACK_PAYLOAD`; stored track equals snapshot.
- **Covers:** `RTR-001`, `RTR-010`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_update_now_rejects_invalid_state_and_health_without_mutation`.

### `RTR-FAIL-002`: unsupported owner_buddy patch rejects

- **Purpose:** Keep owner immutable.
- **Initial state:** PM-owned track exists.
- **Steps:** Dispatch any track mutation with `owner_buddy="design"`.
- **Expected result:** `ok=false`, `E_TRACK_PAYLOAD`, `state_changed=false`, stored owner remains `pm`.
- **Covers:** `RTR-001`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_track_payload_rejects_owner_buddy_patch`.

### `RTR-FAIL-003`: invalid update kind rejects

- **Purpose:** Prevent timeline from becoming general chat/status soup.
- **Initial state:** Active track exists.
- **Steps:** Dispatch `track.add_update` with `kind="comment"`.
- **Expected result:** `ok=false`, `E_TRACK_PAYLOAD`, no update row appended.
- **Covers:** `RTR-010`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_add_update_rejects_invalid_kind`.

### `RTR-FAIL-004`: invalid artifact ref rejects update without mutation

- **Purpose:** Prevent broken refs in shared updates.
- **Initial state:** Active track exists.
- **Steps:** Dispatch `track.add_update` with ref `{"type":"artifact","id":"art-missing"}`.
- **Expected result:** `ok=false`, `permission_boundary="track.update_refs"`, no update row appended.
- **Covers:** `RTR-010`.
- **Suggested file:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_add_update_rejects_missing_artifact_ref_without_mutation`.

## 10. Surface, CLI, Projection, And Docs Tests

### `RTR-SURF-001`: registry exposes target track surface only

- **Purpose:** Prevent runtime catalog drift.
- **Initial state:** No runtime objects needed.
- **Steps:** Inspect `env.tools.contracts.TOOL_REGISTRY`, `env_tools_description()`, `operation_semantics()`, `compact_tool_affordances()`, and `turn_runtime._build_env_tools_desc()`.
- **Expected result:** Track operations are exactly target operations; removed operations are absent; artifact operations exclude `list`.
- **Covers:** `RTR-013`, `RTR-014`.
- **Suggested file:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_track_registry_exposes_page_surface_only`.

### `RTR-SURF-002`: dispatch handlers match registry

- **Purpose:** Ensure catalog actions are callable.
- **Initial state:** No runtime objects.
- **Steps:** Compare `dispatch.dispatch_handler_actions()` with registry action sets.
- **Expected result:** Exact match with no removed action handlers.
- **Covers:** `RTR-013`.
- **Suggested file:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions`.

### `RTR-SURF-003`: CLI exposes target commands and rejects removed commands

- **Purpose:** Protect skill-facing command surface.
- **Initial state:** Checkout only.
- **Steps:** Run `python3 scripts/env/client.py track --help`, `artifact --help`, then removed commands `track get`, `track join`, `track attach-task`, `track detach-task`, and `artifact list`.
- **Expected result:** Help contains target track commands and excludes removed commands; removed commands exit non-zero through argparse.
- **Covers:** `RTR-013`, `RTR-014`.
- **Suggested file:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_cli_exposes_track_page_surface_only`.

### `RTR-SURF-004`: runtime status exposes target catalog

- **Purpose:** Verify status matches registry.
- **Initial state:** Checkout only.
- **Steps:** Run `python3 scripts/turn_runtime.py status`.
- **Expected result:** JSON `env_tools.track.operations` equals target operation set; `artifact.operations` excludes `list`.
- **Covers:** `RTR-014`.
- **Suggested file:** `tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_status_exposes_track_page_env_tools`.

### `RTR-SURF-005`: lock policy follows registry mutates values

- **Purpose:** Preserve runtime locking after action rename.
- **Initial state:** No runtime objects.
- **Steps:** Call `runtime_kernel.coordinator.lock_mode_for_request()` for `track.open`, `artifact.get`, `track.add_material`, `track.add_update`, `track.add_proof`, and `track.archive`.
- **Expected result:** Read actions return `READ`; mutating actions return `WRITE`.
- **Covers:** `RTR-014`.
- **Suggested file:** `tests/test_runtime_broker.py::RuntimeBrokerCoordinatorTests::test_lock_mode_for_track_page_actions`.

### `RTR-SURF-006`: residue scan excludes old task-relation model

- **Purpose:** Stop old guidance and code paths from lingering.
- **Initial state:** Checkout only.
- **Steps:** Scan active `README.md`, `AGENTS.md`, `scripts`, `buddyswitch`, `tools/launcher/assets/buddies`, `framework/contracts`, `framework/schemas`, `framework/console/app.js`, and `tests`.
- **Expected result:** No disallowed hits for `track.join`, `attach_task`, `detach_task`, `attach-task`, `detach-task`, `track_task`, `track.task_ids`, `artifact.task_id`, `artifact_slots`, or `readable_by_current_buddy`; dated docs are excluded by the test.
- **Covers:** `RTR-013`, `RTR-014`.
- **Suggested file:** `tests/test_repo_consistency.py::RepoConsistencyTests::test_track_task_role_rebuild_residue_scan`.

### `RTR-CTX-001`: context uses track page model

- **Purpose:** Align runtime discovery with direct collaboration.
- **Initial state:** Active track has PM and Design materials; Dev has a private task hint.
- **Steps:** Dispatch `context.get` and `context.summarize` as Dev.
- **Expected result:** Candidate track rows include `outcome`, `state`, `health`, and `now`; artifact summaries come from shared materials; private task hint appears only in active-buddy tasks; no task grants are implied.
- **Covers:** `RTR-003`, `RTR-014`.
- **Suggested file:** `tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_uses_track_page_materials`.

### `RTR-PROJ-001`: workspace projection uses target track and artifact shapes

- **Purpose:** Keep context panel API aligned.
- **Initial state:** Projection fixture has active track, materials, proof, tasks, artifacts, messages, and comments.
- **Steps:** Call `runtime_store.projections.build_workspace_projection()` and read `framework/contracts/workspace-projection.json`.
- **Expected result:** Track view has target fields and no embedded tasks; artifact view has `published_to_track`; task view has no artifact slots; contract JSON matches.
- **Covers:** `RTR-014`.
- **Suggested file:** `tests/test_parallel_contracts.py::ParallelContractsTests::test_workspace_projection_uses_track_page_shape`.

### `RTR-SEL-001`: artifact selection uses shared materials

- **Purpose:** Remove task-bundle selection from runless input picking.
- **Initial state:** Track artifact index has `shared_materials` for PRD and implementation report.
- **Steps:** Call `artifact_selection.select_artifacts_for_run()` with required kinds.
- **Expected result:** Selected inputs contain material artifact ids and `from_buddy`; no `task_id` is returned.
- **Covers:** `RTR-014`.
- **Suggested file:** `tests/test_artifact_selection.py::ArtifactSelectionTests::test_selection_uses_current_shared_materials`.

### `RTR-CLEAN-001`: cleanup no longer detaches tasks from tracks

- **Purpose:** Remove old cleanup mutation.
- **Initial state:** Cleanup fixture has track, private tasks, artifacts, messages, and comments.
- **Steps:** Build and execute buddy cleanup for Dev.
- **Expected result:** Dev private task/artifact files are deleted; surviving track shared materials are unchanged; cleanup code has no `detach_task_from_track` helper.
- **Covers:** `RTR-012`, `RTR-014`.
- **Suggested file:** `tests/test_cleanup_system.py::CleanupSystemTests::test_buddy_cleanup_does_not_mutate_track_page_relations`.

### `RTR-DOC-001`: shared tool skills teach target operations

- **Purpose:** Keep runtime skill guidance aligned.
- **Initial state:** Checkout only.
- **Steps:** Read `track-tool`, `artifact-tool`, and `task-tool` skill files.
- **Expected result:** Track operations line equals target track operations; artifact skill says publication is through track operations; task skill says tasks are private; no removed operation is taught.
- **Covers:** `RTR-014`.
- **Suggested file:** `tests/test_runtime_skills.py::RuntimeSkillsTests::test_track_task_artifact_skills_teach_role_rebuild_surface`.

### `RTR-DOC-002`: role contracts teach direct track material path

- **Purpose:** Prevent buddy roles from requiring join/attach.
- **Initial state:** Checkout only.
- **Steps:** Inspect `framework/contracts/{pm,design,dev,test,market}.md`.
- **Expected result:** Contracts mention `track.open` and `track.add_material` or `track.add_proof`; they do not mention `track.join`, attach, detach, or task-derived artifact access.
- **Covers:** `RTR-014`.
- **Suggested file:** `tests/test_repo_consistency.py::RepoConsistencyTests::test_role_contracts_teach_direct_track_material_path`.

### `RTR-DOC-003`: manifest permissions match target actions

- **Purpose:** Ensure every buddy can use V1 shared track mutations.
- **Initial state:** Load `buddyswitch/manifest.toml`.
- **Steps:** Inspect each buddy permissions.
- **Expected result:** PM has `track.create` and `track.archive`; every buddy has `track.read`, `track.update_now`, `track.add_material`, `track.add_update`, `track.add_proof`, private task permissions, and artifact read/create/update permissions; no removed track relation permissions.
- **Covers:** `RTR-014`.
- **Suggested file:** `tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_manifest_permissions_match_track_page_surface`.

### `RTR-DOC-004`: buddy AGENTS guidance uses track.open

- **Purpose:** Keep launcher runtime workspaces from teaching removed commands.
- **Initial state:** Checkout only.
- **Steps:** Inspect `tools/launcher/assets/buddies/*/AGENTS.md`.
- **Expected result:** Guidance says `track open --track-id`; no guidance says `track get`, `track join`, attach, or detach.
- **Covers:** `RTR-014`.
- **Suggested file:** `tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_buddy_agents_use_track_open_guidance`.

## 11. Integration And Regression Tests

### `RTR-E2E-001`: PM to Design to Dev to Test direct track material flow

- **Purpose:** Validate the full memo main path.
- **Initial state:** Empty runtime workspace.
- **Steps:** PM creates track; PM adds PRD material; Design opens track and reads PRD; Design adds design draft material; Dev opens track and reads both artifacts; Test adds smoke proof; PM updates state to done.
- **Expected result:** All calls succeed; final track has `state="done"`, two current materials, one proof, and timeline updates. Serialized call log contains no `track.join`, `track.attach_task`, `track.detach_task`, `track_task`, `source_task_id`, `task_ids`, or `artifact.task_id`.
- **Covers:** `RTR-001` through `RTR-015`.
- **Suggested file:** `tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_pm_design_dev_test_direct_track_material_flow_without_tasks`.

### `RTR-E2E-002`: turn integration uses direct material intake

- **Purpose:** Keep explicit-id integration path aligned.
- **Initial state:** Runtime test workspace.
- **Steps:** Use router dispatch to create track, add material, open as Design, and read artifact.
- **Expected result:** Flow succeeds without task creation and without run content directories.
- **Covers:** `RTR-008`, `RTR-013`.
- **Suggested file:** `tests/test_turn_integration.py::TurnRuntimeIntegrationTests::test_cross_buddy_flow_uses_track_open_and_artifact_get`.

### `RTR-COM-001`: comment on current published artifact without task relation

- **Purpose:** Ensure comments reuse direct artifact visibility.
- **Initial state:** PM publishes PRD to active track; Dev has no task.
- **Steps:** Dev dispatches `comment.add` targeting PRD artifact.
- **Expected result:** `ok=true`; comment target is artifact; no task relation exists.
- **Covers:** `RTR-015`.
- **Suggested file:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_artifact_uses_direct_published_material_boundary`.

### `RTR-COM-002`: comment on private draft artifact rejects

- **Purpose:** Preserve draft privacy through comments.
- **Initial state:** PM private draft artifact exists.
- **Steps:** Dev dispatches `comment.add` targeting draft artifact.
- **Expected result:** `ok=false`, `permission_boundary="artifact.publication"`, no comment file.
- **Covers:** `RTR-009`, `RTR-015`.
- **Suggested file:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_rejects_private_draft_artifact`.

## 12. Manual Verification

No behavior in this rebuild requires manual-only verification. The complete main path, failure paths, CLI surface, runtime catalog, projection, cleanup, and residue scans are automatable in isolated runtime workspaces.

## 13. Final Acceptance Commands

Focused red/green commands during implementation:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_store_v2.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_task_env_tool.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_turn_integration.py tests/test_comment_env_tool.py -q
```

Broader acceptance command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_store_v2.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_task_env_tool.py tests/test_comment_env_tool.py tests/test_context_binding_env_tool.py tests/test_env_tool_response_contract.py tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py tests/test_runtime_broker.py tests/test_runtime_tool_feedback.py tests/test_env_layer_end_to_end.py tests/test_turn_integration.py tests/test_artifact_selection.py tests/test_cleanup_system.py tests/test_parallel_contracts.py tests/test_console_app_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_runless_runtime_contract.py tests/test_buddybox_env_tool.py -q
python3 scripts/turn_runtime.py status
python3 scripts/env/client.py track --help
python3 scripts/env/client.py artifact --help
rg -n "track\\.join|attach_task|detach_task|attach-task|detach-task|track_task|readable_by_current_buddy" scripts buddyswitch tools framework tests README.md AGENTS.md
rg -n "track\\.task_ids|artifact\\.task_id|artifact_slots|source_task_id" scripts buddyswitch tools framework tests README.md AGENTS.md
```

Expected residue scan result: no hits outside tests that define the scan and dated `docs/memo/**` or `docs/spec/**` files excluded by the automated scan.
