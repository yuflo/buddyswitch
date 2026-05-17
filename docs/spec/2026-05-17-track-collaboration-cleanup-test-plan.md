# Track Collaboration Cleanup Test Plan

## 1. Test Objective

Prove BuddySwitch no longer exposes the low-value staged collaboration model. The observable runtime should contain track/task/artifact collaboration, private buddybox files, context discovery, evidence, and search. It should not expose handoff objects, next-buddy routing, `track.advance`, mutable current-stage ownership, or archived-track read leakage.

Tests must be written from product behavior and runtime contracts. They must not preserve old implementation details just because current helper functions make them easy to assert.

## 2. Requirement And Behavior Matrix

| ID | Requirement / behavior | Primary tests |
| --- | --- | --- |
| `CCR-001` | `handoff` env tool is absent from registry, router, dispatch, CLI, runtime status, context catalog, compact affordances, manifest skills, permissions, projections, cleanup, launcher paths, and runtime skills. | `CCR-HANDOFF-001` to `CCR-HANDOFF-008` |
| `CCR-002` | `source_refs.type="handoff"` is rejected for artifact/source ref normalization and no handoff provenance type remains. | `CCR-SRCREF-001`, `CCR-SRCREF-002` |
| `CCR-003` | `next_buddy` is absent from stored tracks, payload fields, responses, projections, context, docs, skills, schemas, and relation labels. | `CCR-NEXT-001` to `CCR-NEXT-006` |
| `CCR-004` | `track.advance` is no longer supported anywhere. | `CCR-ADV-001` to `CCR-ADV-004` |
| `CCR-005` | Tracks contain `owner_buddy`; `owner_buddy` is created once and cannot be updated. | `CCR-OWNER-001` to `CCR-OWNER-004` |
| `CCR-006` | Archived tracks are hard explicit-read boundaries for `track.get`, `artifact.list`, and related `artifact.get`, with no owner bypass. | `CCR-ARCH-001` to `CCR-ARCH-004` |
| `CCR-007` | Context and list discovery do not expose archived tracks as active collaboration context. | `CCR-ARCH-005`, `CCR-ARCH-006` |
| `CCR-008` | `artifact.list`, `track.get`, and `context` expose current artifact summaries through one consistent selection path. | `CCR-ARTSUM-001` to `CCR-ARTSUM-003` |
| `CCR-009` | Superseded revisions are not exposed as collaboration-layer objects and non-owner superseded body reads reject. | `CCR-ARTSUM-004`, `CCR-ARTREAD-004` |
| `CCR-010` | Artifact editing remains owner-only. | `CCR-ARTWRITE-001`, `CCR-ARTWRITE-002` |
| `CCR-011` | Non-owner artifact reads are allowed only through an active, non-archived track collaboration surface and do not depend on `current_buddy`, `next_buddy`, participant labels, or handoff recipient state. | `CCR-ARTREAD-001` to `CCR-ARTREAD-003` |
| `CCR-012` | Active docs, skills, role contracts, schemas, and runtime AGENTS do not teach handoff or next-buddy workflows. | `CCR-DOC-001` to `CCR-DOC-005` |

## 3. Test Design Rules

- Test public broker-routed `env.tool` behavior when possible.
- Use `RuntimeWorkspaceTestMixin` for runtime object writes.
- Prefer exact field-presence/absence and structured error assertions over prose snapshots.
- Do not call deleted helpers through compatibility shims.
- Do not keep `tests/test_handoff_env_tool.py` as a behavior suite. Delete it or replace it with absence checks in other suites.
- Residue scans should cover active surfaces and exclude historical records under `docs/memo/**` and dated `docs/spec/**`.
- Artifact kind names such as `design-handoff` may remain where they identify a deliverable kind; tests must not confuse that with the retired `handoff` runtime object.

## 4. Scenario Coverage Index

- 正向场景：`CCR-OWNER-001`, `CCR-ARTSUM-001`, `CCR-ARTSUM-002`, `CCR-ARTSUM-003`, `CCR-ARTREAD-001`, `CCR-ARTREAD-004`, `CCR-ARTWRITE-001` existing-owner paths after rewrite.
- 负向场景：`CCR-HANDOFF-002`, `CCR-SRCREF-001`, `CCR-SRCREF-002`, `CCR-NEXT-002`, `CCR-ADV-002`, `CCR-ADV-003`, `CCR-OWNER-002`, `CCR-OWNER-003`, `CCR-ARTREAD-002`, `CCR-ARTWRITE-002`.
- 边界场景：`CCR-ARCH-001` through `CCR-ARCH-006`, `CCR-ARTSUM-004`, and owner reads for standalone/non-archived artifacts in `CCR-ARTREAD-004`.
- 回归场景：`CCR-HANDOFF-001` through `CCR-HANDOFF-008`, `CCR-NEXT-006`, `CCR-ADV-001`, `CCR-ADV-004`, `CCR-DOC-001` through `CCR-DOC-005`, plus the old-test rewrite list in section 6.

## 5. Focused Test Cases

### `CCR-HANDOFF-001`: runtime registry excludes handoff

- **Purpose:** Prove the active env tool set no longer includes `handoff`.
- **Preconditions:** No runtime state required.
- **Input / operation:** Load `env.tools.contracts.TOOL_REGISTRY`, `contracts.env_tools_description()`, `contracts.compact_tool_affordances()`, and `turn_runtime._build_env_tools_desc()`.
- **Expected output or state:** Tool set is exactly `{"task", "track", "artifact", "buddybox", "context", "evidence", "search"}`. `handoff` is absent from full catalog, compact affordances, and operation semantics.
- **Suggested test:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_active_env_tool_surface_excludes_handoff` and `tests/test_repo_consistency.py::RepoConsistencyTests::test_env_tool_surface_excludes_handoff`.

### `CCR-HANDOFF-002`: router rejects handoff tool

- **Purpose:** Prove callers cannot invoke a retired handoff tool.
- **Preconditions:** Runtime workspace instance for any buddy.
- **Input / operation:** Broker dispatch `{"tool": "handoff", "action": "list", "args": {}}`.
- **Expected output or state:** `ok=false`, error code `E_ENV_TOOL`, `permission_boundary="env.tool"`, `state_changed=false`, and no handoff service code runs.
- **Suggested test:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_handoff_tool_is_unsupported`.

### `CCR-HANDOFF-003`: dispatch has no handoff handler

- **Purpose:** Prevent a hidden service path after registry removal.
- **Preconditions:** Import `env.tools.dispatch`.
- **Input / operation:** Inspect `dispatch.dispatch_handler_actions()`.
- **Expected output or state:** No `"handoff"` key. `scripts/env/services/handoffs.py` does not exist.
- **Suggested test:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_excludes_handoff`.

### `CCR-HANDOFF-004`: CLI has no handoff resource

- **Purpose:** Prove skill-facing CLI cannot suggest or route retired handoff operations.
- **Preconditions:** No broker needed.
- **Input / operation:** Run `python3 scripts/env/client.py handoff list`.
- **Expected output or state:** Process exits non-zero with argparse unsupported resource text; `python3 scripts/env/client.py --help` does not list `handoff`.
- **Suggested test:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_cli_excludes_handoff_resource`.

### `CCR-HANDOFF-005`: manifest and runtime skills exclude handoff-tool

- **Purpose:** Prove runtime skill materialization no longer installs handoff guidance.
- **Preconditions:** Load `buddyswitch/manifest.toml`.
- **Input / operation:** Inspect manifest skills and every buddy skill list; materialize runtime skills for one buddy in test workspace.
- **Expected output or state:** No `handoff-tool` skill row, no buddy references it, and `.agents/skills/handoff-tool` is absent.
- **Suggested test:** `tests/test_runtime_skills.py::RuntimeSkillsTests::test_handoff_tool_skill_is_removed` and `tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_manifest_has_no_handoff_tool_skill`.

### `CCR-HANDOFF-006`: projection and workspace contract exclude handoffs

- **Purpose:** Prove handoff records are no longer active projected product state.
- **Preconditions:** Seed tracks/tasks/artifacts only.
- **Input / operation:** Call `runtime_store.projections.build_workspace_projection()` and read `framework/contracts/workspace-projection.json`.
- **Expected output or state:** Projection has no top-level `handoffs`; contract top-level order and data sources omit `buddyswitch/objects/handoffs/*.json`; no handoff view shape.
- **Suggested test:** `tests/test_parallel_contracts.py::ParallelContractsTests::test_workspace_projection_contract_excludes_handoffs`.

### `CCR-HANDOFF-007`: cleanup does not index handoff objects

- **Purpose:** Prove cleanup no longer treats handoff as active product data.
- **Preconditions:** Runtime root includes tracks/tasks/artifacts and a stale `buddyswitch/objects/handoffs/handoff-old.json`.
- **Input / operation:** Build cleanup plan with `--buddy dev` and `--all-data`.
- **Expected output or state:** Buddy cleanup has no `handoff_object_ids`, `handoff_records`, or `handoff_objects` category. `--all-data` either deletes stale handoff directory as retired residue without indexing or ignores it; whichever implementation chooses must be explicit and tested.
- **Suggested test:** `tests/test_cleanup_system.py::CleanupSystemTests::test_cleanup_plan_excludes_handoff_indexing`.

### `CCR-HANDOFF-008`: launcher no longer projects handoff directories

- **Purpose:** Prove new product instances do not create a handoff runtime surface.
- **Preconditions:** Launcher integration test uses temp shared root.
- **Input / operation:** Start a buddy instance through existing launcher fixture.
- **Expected output or state:** Workspace has projected symlinks for `tracks`, `tasks`, `artifacts`; no `buddyswitch/objects/handoffs` projected path; runtime copied services exclude `scripts/env/services/handoffs.py`.
- **Suggested test:** `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_runtime_surface_excludes_handoffs`.

### `CCR-SRCREF-001`: artifact source_refs rejects handoff type

- **Purpose:** Remove handoff provenance type from active durable objects.
- **Preconditions:** Active-buddy-owned task exists.
- **Input / operation:** Broker dispatch `artifact.validate_payload` with `source_refs=[{"type": "handoff", "id": "handoff-old"}]`.
- **Expected output or state:** `ok=false`, error code `E_SOURCE_REFS`, `state_changed=false`.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_artifact_source_refs_reject_handoff_type`.

### `CCR-SRCREF-002`: store source_refs rejects handoff type

- **Purpose:** Prevent bypass through direct store helper tests.
- **Preconditions:** Runtime store sandbox.
- **Input / operation:** Call `env_store.create_artifact(... source_refs=[{"type": "handoff", "id": "handoff-old"}])`.
- **Expected output or state:** Raises `ValueError("unsupported source_ref type: handoff")`; no artifact file written.
- **Suggested test:** `tests/test_env_store_v2.py::ArtifactSourceRefsTests::test_store_rejects_handoff_source_ref_type`.

### `CCR-NEXT-001`: track create response omits next_buddy and current_buddy

- **Purpose:** Prove track creation no longer persists next actor or mutable current stage.
- **Preconditions:** PM instance.
- **Input / operation:** Broker dispatch `track.create` with `{"track_id": "track-owner", "title": "Owner Track"}`.
- **Expected output or state:** Response `track.owner_buddy == "pm"`; response has no `current_buddy` and no `next_buddy`; stored JSON has `owner_buddy` only.
- **Suggested test:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_track_create_records_owner_buddy_without_next_buddy`.

### `CCR-NEXT-002`: track payload rejects next_buddy/current_buddy

- **Purpose:** Prove old payload fields are not silently accepted.
- **Preconditions:** PM instance.
- **Input / operation:** Broker dispatch `track.create` or `track.update` with `next_buddy` or `current_buddy`.
- **Expected output or state:** `ok=false`, `E_TRACK_PAYLOAD`, `state_changed=false`, `correctable_fields` includes the retired field.
- **Suggested test:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_track_payload_rejects_current_and_next_buddy`.

### `CCR-NEXT-003`: context candidate tracks omit next_buddy/current_buddy

- **Purpose:** Remove next actor from discovery surface.
- **Preconditions:** Active track with tasks from two buddies.
- **Input / operation:** `context.summarize` and `context.get`.
- **Expected output or state:** Candidate track rows include `owner_buddy` and active relation, but no `current_buddy`, `next_buddy`, or recommendation fields.
- **Suggested test:** `tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_candidate_tracks_use_owner_buddy_only`.

### `CCR-NEXT-004`: projection omits next_buddy/current_buddy

- **Purpose:** Remove old fields from context panel API.
- **Preconditions:** Track exists.
- **Input / operation:** Build workspace projection.
- **Expected output or state:** Track view has `owner_buddy`; no `current_buddy`, `next_buddy`.
- **Suggested test:** `tests/test_parallel_contracts.py::ParallelContractsTests::test_projected_track_shape_uses_owner_buddy`.

### `CCR-NEXT-005`: artifact relation labels do not mention current/next/participant/handoff

- **Purpose:** Prevent old authorization categories from leaking through summaries.
- **Preconditions:** Track has PM artifact and active dev task relation.
- **Input / operation:** Dev calls `artifact.list` and `track.get`.
- **Expected output or state:** Artifact row relation is `track_task` or another neutral approved value; never `current_buddy`, `next_buddy`, `participant`, or `handoff_recipient`; row has `readable_by_active_buddy`.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_artifact_summary_relation_labels_are_neutral`.

### `CCR-NEXT-006`: active docs and skills omit next_buddy

- **Purpose:** Prevent runtime guidance from teaching old next actor payloads.
- **Preconditions:** Repository checkout.
- **Input / operation:** `rg -n "next_buddy" README.md AGENTS.md scripts buddyswitch tools framework tests -g '!docs/memo/**' -g '!docs/spec/**'`.
- **Expected output or state:** No hits except tests that construct the scan itself.
- **Suggested test:** `tests/test_repo_consistency.py::RepoConsistencyTests::test_active_surfaces_exclude_next_buddy`.

### `CCR-ADV-001`: track.advance absent from registry and status

- **Purpose:** Prove lifecycle advancement action is removed.
- **Preconditions:** No runtime state.
- **Input / operation:** Inspect registry, operation semantics, compact affordances, runtime status.
- **Expected output or state:** No `track.advance` action or support row.
- **Suggested test:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_track_advance_is_not_registered`.

### `CCR-ADV-002`: router rejects track.advance

- **Purpose:** Prove old action cannot be invoked.
- **Preconditions:** PM instance and active track.
- **Input / operation:** Broker dispatch `{"tool": "track", "action": "advance", "args": {"track_id": "track-owner"}}`.
- **Expected output or state:** `ok=false`, `E_ENV_TOOL`, `state_changed=false`; stored track unchanged.
- **Suggested test:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_track_advance_action_is_unsupported`.

### `CCR-ADV-003`: CLI excludes track advance

- **Purpose:** Remove skill-facing command path.
- **Preconditions:** No broker required.
- **Input / operation:** `python3 scripts/env/client.py track advance --payload /tmp/nope.json`.
- **Expected output or state:** argparse rejects unsupported operation; `track --help` does not list `advance`.
- **Suggested test:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_cli_track_help_excludes_advance`.

### `CCR-ADV-004`: PM schema/profile/manifest excludes track.advance

- **Purpose:** Remove PM authority to old action.
- **Preconditions:** Load manifest, profile, and PM output schema.
- **Input / operation:** Validate manifest/profile and inspect schema enum.
- **Expected output or state:** No `track.advance` permission; PM `state_capability.track_effects == ["create", "update", "archive"]`; PM schema action enum excludes `advance`.
- **Suggested test:** `tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_pm_manifest_and_profile_exclude_track_advance` and `tests/test_output_schema_boundaries.py::OutputSchemaBoundaryTests::test_pm_schema_rejects_track_advance_effect`.

### `CCR-OWNER-001`: owner_buddy is created from active buddy

- **Purpose:** Prove track owner metadata exists.
- **Preconditions:** PM instance.
- **Input / operation:** `track.create`.
- **Expected output or state:** Response and stored JSON include `owner_buddy="pm"`.
- **Suggested test:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_track_create_sets_owner_buddy`.

### `CCR-OWNER-002`: owner_buddy cannot be updated

- **Purpose:** Prove owner metadata is immutable after create.
- **Preconditions:** Track exists with `owner_buddy="pm"`.
- **Input / operation:** PM calls `track.update` with `owner_buddy="design"`.
- **Expected output or state:** `ok=false`, `E_TRACK_PAYLOAD`; stored owner remains `pm`.
- **Suggested test:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_track_update_rejects_owner_buddy_patch`.

### `CCR-OWNER-003`: owner_buddy does not grant artifact body reads

- **Purpose:** Prove owner metadata is not read authorization for foreign artifacts.
- **Preconditions:** Track owner is `pm`; design task on track owns current artifact; PM has no active PM task relation to that track.
- **Input / operation:** PM calls `artifact.get` for design artifact.
- **Expected output or state:** `ok=false`, `E_ARTIFACT_READ_SCOPE`; relation does not say owner. If PM joins with a PM task relation on active track, read succeeds through track-task relation.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_owner_buddy_metadata_does_not_grant_foreign_artifact_read`.

### `CCR-OWNER-004`: store rejects legacy track fields

- **Purpose:** Prevent direct fixture drift.
- **Preconditions:** Runtime store sandbox.
- **Input / operation:** Call `env_store.validate_track()` with `current_buddy` or `next_buddy`.
- **Expected output or state:** Raises `ValueError` naming unsupported or missing `owner_buddy`.
- **Suggested test:** `tests/test_env_store_v2.py::TrackStoreContractTests::test_validate_track_rejects_current_and_next_buddy`.

### `CCR-ARCH-001`: archived track.get rejects

- **Purpose:** Enforce explicit track read boundary.
- **Preconditions:** Track exists with `status="archived"`.
- **Input / operation:** Broker dispatch `track.get {"track_id": "track-archived"}`.
- **Expected output or state:** `ok=false`, code `E_TRACK_ARCHIVED` or `E_TRACK_READ_SCOPE`, `permission_boundary="track.lifecycle_status"`, no `track_context_summary`.
- **Suggested test:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_track_get_rejects_archived_track`.

### `CCR-ARCH-002`: archived artifact.list rejects

- **Purpose:** Enforce explicit artifact summary read boundary.
- **Preconditions:** Archived track has task and current artifact.
- **Input / operation:** Broker dispatch `artifact.list {"track_id": "track-archived"}`.
- **Expected output or state:** `ok=false`, code `E_ARTIFACT_READ_SCOPE` or `E_TRACK_ARCHIVED`, no artifact rows.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_artifact_list_rejects_archived_track`.

### `CCR-ARCH-003`: archived artifact.get rejects even for owner

- **Purpose:** Prove no owner exception bypasses archived read boundary.
- **Preconditions:** PM-owned artifact belongs to task under archived track.
- **Input / operation:** PM calls `artifact.get`.
- **Expected output or state:** `ok=false`, permission boundary `track.lifecycle_status`; content body string absent from serialized response.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_artifact_get_rejects_archived_track_even_for_owner`.

### `CCR-ARCH-004`: archived artifact.get rejects for non-owner relation

- **Purpose:** Prove active task relation cannot bypass archived boundary.
- **Preconditions:** Archived track has PM artifact and dev task relation.
- **Input / operation:** Dev calls `artifact.get` for PM artifact.
- **Expected output or state:** `ok=false`, archived boundary error, no content.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_artifact_get_rejects_archived_track_for_track_relation`.

### `CCR-ARCH-005`: context omits archived tracks

- **Purpose:** Prevent archived tracks from appearing as active collaboration context.
- **Preconditions:** One active track and one archived track.
- **Input / operation:** `context.summarize` and `context.get`.
- **Expected output or state:** Candidate tracks and visible track sections include active track only.
- **Suggested test:** `tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_omits_archived_tracks_from_active_context`.

### `CCR-ARCH-006`: track.list default omits archived discovery

- **Purpose:** Prevent list discovery from presenting archived tracks as active collaboration choices.
- **Preconditions:** One active track and one archived track.
- **Input / operation:** `track.list {}`.
- **Expected output or state:** Active track appears; archived track does not. If `status=archived` is explicitly supported, add a separate assertion that rows are summary-only and cannot be passed to `track.get` successfully.
- **Suggested test:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_track_list_default_omits_archived_tracks`.

### `CCR-ARTSUM-001`: artifact.list and track.get summaries match

- **Purpose:** Prove one current-artifact selection path.
- **Preconditions:** Track has PM and design tasks; each has current artifact.
- **Input / operation:** Same buddy calls `track.get` and `artifact.list` for same track.
- **Expected output or state:** Artifact summary rows match by `artifact_id`, `source_buddy`, `source_task_id`, `kind`, `revision`, `currentness`, `readable_by_active_buddy`, and neutral `relation`.
- **Suggested test:** `tests/test_track_env_tool.py::TrackEnvToolTests::test_track_get_artifact_rows_match_artifact_list_current_rows`.

### `CCR-ARTSUM-002`: artifact.list returns current revisions only

- **Purpose:** Prevent superseded collaboration rows.
- **Preconditions:** Task has two revisions for same kind.
- **Input / operation:** `artifact.list`.
- **Expected output or state:** Only revision 2 current artifact appears; revision 1 absent.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_artifact_list_returns_current_revisions_only`.

### `CCR-ARTSUM-003`: context artifact summaries match current rows

- **Purpose:** Keep context discovery aligned with artifact surfaces.
- **Preconditions:** Active track with current artifact and superseded revision.
- **Input / operation:** `context.get`.
- **Expected output or state:** `artifact_summaries` include current artifact only and use `readable_by_active_buddy`.
- **Suggested test:** `tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_artifact_summaries_are_current_only`.

### `CCR-ARTSUM-004`: non-owner superseded artifact.get rejects

- **Purpose:** Prevent historical revision leakage across buddies.
- **Preconditions:** PM task has revision 1 superseded by revision 2 on active track; dev has active task relation on same track.
- **Input / operation:** Dev calls `artifact.get` on revision 1.
- **Expected output or state:** `ok=false`, permission boundary `artifact.currentness`, no content.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_non_owner_cannot_get_superseded_revision`.

### `CCR-ARTREAD-001`: non-owner can read current artifact through active track task relation

- **Purpose:** Preserve useful cross-buddy artifact intake.
- **Preconditions:** PM artifact current on active track; dev has active task attached to same track.
- **Input / operation:** Dev calls `artifact.get`.
- **Expected output or state:** `ok=true`, full content returned, relation is neutral active track relation, no current/next/participant/handoff labels.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_non_owner_reads_current_artifact_through_active_track_task_relation`.

### `CCR-ARTREAD-002`: non-owner without task relation cannot read

- **Purpose:** Reject unrelated observer reads.
- **Preconditions:** PM artifact current on active track; dev has no task relation.
- **Input / operation:** Dev calls `artifact.get`.
- **Expected output or state:** `ok=false`, `E_ARTIFACT_READ_SCOPE`, no content.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_non_owner_without_track_task_relation_cannot_read_artifact`.

### `CCR-ARTREAD-003`: next_buddy and handoff do not affect read authorization

- **Purpose:** Prove retired next actor/handoff state has no hidden impact.
- **Preconditions:** Any stale fixture attempt includes ignored or rejected `next_buddy`; no handoff records exist; dev task relation exists.
- **Input / operation:** Dev calls `artifact.get`.
- **Expected output or state:** Read succeeds because of task relation only. Serialized response and decision details contain no `next_buddy` or handoff.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_artifact_read_does_not_depend_on_next_buddy_or_handoff`.

### `CCR-ARTREAD-004`: owner can read standalone owned artifact

- **Purpose:** Keep owner read behavior where no archived track boundary applies.
- **Preconditions:** Active-buddy-owned task with no track or active track owns artifact.
- **Input / operation:** Owner calls `artifact.get`.
- **Expected output or state:** `ok=true`, content returned.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_owner_reads_owned_artifact_when_not_archived`.

### `CCR-ARTWRITE-001`: create_revision remains active-buddy task only

- **Purpose:** Preserve artifact write boundary.
- **Preconditions:** PM task exists; dev instance active.
- **Input / operation:** Dev calls `artifact.create_revision` with PM `task_id`.
- **Expected output or state:** `ok=false`, `E_ARTIFACT_TASK_SCOPE`, no artifact file.
- **Suggested test:** Existing `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_create_revision_rejects_foreign_task_scope` updated to owner-buddy fixture fields.

### `CCR-ARTWRITE-002`: update_metadata remains owner-only

- **Purpose:** Preserve metadata edit boundary.
- **Preconditions:** PM artifact exists on active track; dev may have track task relation.
- **Input / operation:** Dev calls `artifact.update_metadata` on PM artifact.
- **Expected output or state:** `ok=false`, `E_ARTIFACT_BUDDY_SCOPE`, artifact unchanged.
- **Suggested test:** `tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_update_metadata_rejects_non_owner_even_with_track_relation`.

### `CCR-DOC-001`: active runtime guidance excludes handoff tool

- **Purpose:** Prevent product-mode agents from seeing old tool lists.
- **Preconditions:** Repository checkout.
- **Input / operation:** Scan `tools/launcher/assets/buddies/*/AGENTS.md`, root `AGENTS.md`, `README.md`.
- **Expected output or state:** Tool lists exclude `handoff`; output rules do not mention "next handoff target".
- **Suggested test:** `tests/test_repo_consistency.py::RepoConsistencyTests::test_active_runtime_guidance_excludes_handoff_tool`.

### `CCR-DOC-002`: shared skills exclude handoff-tool and next actor examples

- **Purpose:** Prevent runtime skill instructions from recreating old model.
- **Preconditions:** Repository checkout.
- **Input / operation:** Inspect shared and role skill Markdown.
- **Expected output or state:** `buddyswitch/skills/shared/handoff-tool/SKILL.md` absent; no `Use optional handoff`; no `next_buddy`; no `track.advance`; `design-handoff` artifact kind remains allowed where explicitly listed as kind.
- **Suggested test:** `tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_and_role_skills_exclude_handoff_runtime_guidance`.

### `CCR-DOC-003`: role contracts exclude handoff object paths

- **Purpose:** Keep role contracts aligned with active state.
- **Preconditions:** Repository checkout.
- **Input / operation:** Read `framework/contracts/{pm,design,dev,market,test}.md`.
- **Expected output or state:** No `buddyswitch/objects/handoffs`; no `track.advance`; no next actor guidance.
- **Suggested test:** `tests/test_repo_consistency.py::RepoConsistencyTests::test_role_contracts_exclude_handoff_and_next_actor_state`.

### `CCR-DOC-004`: output schemas remove handoff payload

- **Purpose:** Prevent buddy result payload from carrying next actor semantics.
- **Preconditions:** Load all `framework/schemas/*/*-result.json`.
- **Input / operation:** Validate sample payloads with no top-level `handoff`; validate payloads with `handoff.next_buddy`.
- **Expected output or state:** No schema contains top-level `handoff`; payload with `handoff` is rejected as unsupported property.
- **Suggested test:** `tests/test_output_schema_boundaries.py::OutputSchemaBoundaryTests::test_buddy_result_schemas_reject_handoff_payload`.

### `CCR-DOC-005`: active residue scan

- **Purpose:** Catch missed active-surface strings.
- **Preconditions:** Repository checkout.
- **Input / operation:** Run scans over `README.md AGENTS.md scripts buddyswitch tools framework tests` excluding `docs/memo/**` and `docs/spec/**`.
- **Expected output or state:** No hits for `handoff` as runtime object/tool, `next_buddy`, `current_buddy`, `track.advance`, `readable_by_current_buddy`; allowlist only `design-handoff` artifact kind and test names that scan for retired strings.
- **Suggested test:** `tests/test_repo_consistency.py::RepoConsistencyTests::test_track_collaboration_cleanup_residue_scan`.

## 6. Old Tests To Delete, Rewrite, Or Replace

Delete:

- `tests/test_handoff_env_tool.py`

Rewrite:

- `tests/test_track_env_tool.py`
  - Replace `next_buddy` fixtures with active task relations.
  - Replace PM lifecycle mutation test for `advance` with `update` and explicit unsupported `advance` rejection.
  - Rename `readable_by_current_buddy` assertions to `readable_by_active_buddy`.
- `tests/test_artifact_env_tool.py`
  - Add archived boundary and owner-only metadata tests.
  - Add non-owner active-track-task read tests.
- `tests/test_context_binding_env_tool.py`
  - Remove handoff affordance expectations.
  - Add archived filtering and owner-buddy context rows.
- `tests/test_env_tool_router.py`
  - Remove handoff expected actions.
  - Add unsupported handoff and unsupported `track.advance` tests.
- `tests/test_env_tool_semantic_contract.py`
  - Remove mutation category special case for `advance`.
  - Expected tool/action sets derive from registry and assert `handoff` absent.
- `tests/test_runtime_skills.py`
  - Required shared tools become `{"track-tool", "artifact-tool", "task-tool", "buddybox-tool"}`.
  - Assert `handoff-tool` package absent.
- `tests/test_env_manifest_v2.py`
  - Assert no `handoff.*`, no `track.advance`, and no `handoff-tool`.
- `tests/test_env_store_v2.py`
  - Remove `HandoffRecordCompatibilityTests`.
  - Add `TrackStoreContractTests` and source_refs handoff rejection tests.
- `tests/test_cleanup_system.py`
  - Remove handoff indexed records and expectations.
- `tests/test_parallel_contracts.py`
  - Remove `create_handoff` fixture and `handoffs` projection shape assertions.
- `tests/test_console_app_contract.py`
  - Replace next-step handoff mode tests with owner/status projection tests.
- `tests/test_output_schema_boundaries.py`
  - Remove `handoff` from optional keys; reject top-level `handoff`.
  - Replace PM `advance` sample with `update`.
- `tests/test_turn_integration.py`
  - Replace handoff create/list flow with direct track join plus artifact read.
- `tests/test_runtime_tool_feedback.py`, `tests/test_task_management_skill_architecture.py`, `tests/test_memory_removal_contract.py`, `tests/test_runless_runtime_contract.py`
  - Remove handoff fixtures; replace `current_buddy`/`next_buddy` fixture fields with `owner_buddy`; assert old fields are absent or rejected.
- `tests/test_buddyswitch_launcher.py`
  - Remove handoff projected path, service file, skill, and AGENTS tool-list expectations.

## 7. Focused Test Commands

Contract shrink:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_router.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_manifest_v2.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  -q
```

Track/artifact/context behavior:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_store_v2.py \
  -q
```

Projection, cleanup, launcher:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_parallel_contracts.py \
  tests/test_cleanup_system.py \
  tests/test_console_app_contract.py \
  tests/test_buddyswitch_launcher.py \
  -q
```

Docs, schemas, runtime guidance:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_output_schema_boundaries.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  -q
```

## 8. Broader Verification

Run after focused suites are green:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
python3 scripts/env_profiles.py validate-all
python3 scripts/env_manifest.py print >/tmp/buddyswitch-manifest.json
python3 scripts/turn_runtime.py status >/tmp/buddyswitch-runtime-status.json
rg -n "handoff|next_buddy|current_buddy|track\\.advance|readable_by_current_buddy" \
  README.md AGENTS.md scripts buddyswitch tools framework tests \
  -g '!docs/memo/**' \
  -g '!docs/spec/**'
```

Expected:

- Full test suite exits `0`.
- Manifest/profile/status commands exit `0`.
- Residue scan has no active-surface hits except explicitly allowlisted artifact-kind text such as `design-handoff`.

## 9. Manual Smoke Check

Use only after automated verification passes:

```bash
./buddyswitch-codex instance start --buddy pm --help
python3 scripts/env/client.py track --help
python3 scripts/env/client.py artifact --help
python3 scripts/env/client.py context --help
python3 scripts/turn_runtime.py status
```

Expected:

- Help output has no `handoff` resource and no `track advance`.
- Runtime status tools are `task`, `track`, `artifact`, `buddybox`, `context`, `evidence`, `search`.
- `track` operations are `list`, `get`, `join`, `create`, `update`, `archive`, `attach_task`, `detach_task`.
