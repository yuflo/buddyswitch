# Track Collaboration Cleanup Code Implementation Plan

> **For agentic workers:** Implement this plan in `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem` on branch `dev_buddy_mem`. Use test-first changes for every behavior change, keep each phase runnable, and do not implement any handoff/next-buddy replacement.

**Goal:** Shrink BuddySwitch collaboration runtime to track/task/artifact core by removing `handoff`, `next_buddy`, and `track.advance`, renaming immutable track creator metadata to `owner_buddy`, centralizing artifact visibility, and making archived tracks a hard explicit-read boundary.

**Architecture:** Replace the staged-handoff model directly instead of routing around it. Runtime contracts remain owned by Python services, JSON contracts, manifest/profile validation, role contracts, skills, and tests. Artifact read visibility becomes one small shared helper used by `artifact.get`, `artifact.list`, `track.get`, and `context`; there is no new workflow router, lifecycle engine, ACL framework, handoff substitute, or next-executor model.

**Tech Stack:** Python env store/services/tools, broker-routed `env.tool`, TOML manifest, JSON env profiles/contracts/schemas, launcher shell projection, Markdown runtime skills/contracts, pytest/unittest.

---

## 1. Source Inputs

- `AGENTS.md`
- `docs/memo/2026-05-17-track-collaboration-cleanup-memo.md`
- Current implementation inspected:
  - Store/model: `scripts/env_store.py`, `scripts/env/services/source_refs.py`
  - Env services: `scripts/env/services/tracks.py`, `scripts/env/services/artifacts.py`, `scripts/env/services/track_relations.py`, `scripts/env/services/handoffs.py`, `scripts/env/services/context.py`
  - Tool layer: `scripts/env/tools/contracts.py`, `scripts/env/tools/semantics.py`, `scripts/env/tools/router.py`, `scripts/env/tools/dispatch.py`, `scripts/env/tools/responses.py`
  - CLI/runtime: `scripts/env/client.py`, `scripts/turn_runtime.py`
  - Manifest/profile: `buddyswitch/manifest.toml`, `scripts/env_manifest.py`, `buddyswitch/env-profiles/*.json`, `scripts/env_profiles.py`, `framework/contracts/buddy-env-profile.json`
  - Projection/context panel: `scripts/runtime_store/projections.py`, `scripts/workspace_data.py`, `scripts/serve_context_panel.py`, `framework/contracts/workspace-projection.json`, `framework/console/app.js`
  - Cleanup/launcher: `scripts/env_cleanup.py`, `tools/launcher/workspace.sh`, `tools/launcher/cleanup.sh`
  - Skills/docs/contracts/schemas: `buddyswitch/skills/**`, `tools/launcher/assets/buddies/*/AGENTS.md`, `framework/contracts/{pm,design,dev,market,test}.md`, `framework/schemas/{pm,design,dev,market,test}/*-result.json`, `README.md`
  - Tests: `tests/test_track_env_tool.py`, `tests/test_artifact_env_tool.py`, `tests/test_handoff_env_tool.py`, `tests/test_context_binding_env_tool.py`, `tests/test_env_tool_router.py`, `tests/test_env_tool_semantic_contract.py`, `tests/test_runtime_skills.py`, `tests/test_env_manifest_v2.py`, `tests/test_env_store_v2.py`, `tests/test_cleanup_system.py`, `tests/test_parallel_contracts.py`, `tests/test_console_app_contract.py`, `tests/test_runtime_tool_feedback.py`, `tests/test_turn_integration.py`, `tests/test_buddyswitch_launcher.py`, `tests/test_task_management_skill_architecture.py`, `tests/test_output_schema_boundaries.py`, `tests/test_memory_removal_contract.py`, `tests/test_runless_runtime_contract.py`

## 2. Target Runtime Contract

### Active Tool Surface

After cleanup, active env tools are:

- `track`
- `task`
- `artifact`
- `buddybox`
- `context`
- `evidence`
- `search`

`handoff` is absent from registry, router, dispatch, CLI, runtime status, context catalog, manifest permissions, skills, projections, cleanup indexing, launcher projected paths, and tests.

### Track Contract

Supported `track` actions are:

- `list`
- `get`
- `join`
- `create`
- `update`
- `archive`
- `attach_task`
- `detach_task`

`track.advance` is absent everywhere. `track.update` remains the only PM-owned metadata/status patch action until a later track lifecycle redesign.

Track records use:

```json
{
  "id": "track-example",
  "title": "Example",
  "status": "active",
  "owner_buddy": "pm",
  "task_ids": [],
  "summary": "",
  "updated_at": "..."
}
```

Rules:

- `owner_buddy` is set on creation.
- Env-tool `track.create` records `owner_buddy` from `active_buddy`; callers do not choose a next actor.
- `owner_buddy` is not patchable through `track.update`.
- `owner_buddy` does not grant artifact read access and does not imply stage ownership.
- `current_buddy` and `next_buddy` are removed from validation, storage, payload fields, response rows, projections, context, schemas, docs, and skills.

### Artifact Visibility Contract

Rules:

- Artifact editing remains owner-only.
- `artifact.create_revision` can only write to an active-buddy-owned task.
- `artifact.update_metadata` can only update an active-buddy-owned artifact.
- Owner reads are allowed only when the artifact is not related to an archived track.
- Non-owner artifact body reads are allowed only when the artifact is current and attached to a task on an active, non-archived track where the active buddy has an active task relation.
- Non-owner reads do not depend on `current_buddy`, `next_buddy`, participant labels, handoff records, or handoff recipient state.
- Collaboration-facing summaries expose only current artifacts.
- Superseded revisions remain artifact-layer history and are not exposed as collaboration-layer rows.

### Archived Track Contract

When `track.status == "archived"`:

- `track.get(track_id)` rejects explicit reads.
- `artifact.list(track_id)` rejects explicit reads.
- `artifact.get(artifact_id)` rejects when the artifact belongs to a task under the archived track, including owner reads.
- `context.get` and `context.summarize` omit archived tracks from active collaboration context.
- `track.list` omits archived tracks from default discovery. If implementation keeps `status=archived` discovery for admin inspection, it must label it as archived summary-only and it must not make `track.get` or artifact reads succeed.

## 3. Non-Goals

- Do not redesign track lifecycle.
- Do not add a new lifecycle state machine.
- Do not add assignment, claim, lock, routing, or automatic stage-transition semantics.
- Do not add a replacement object for `handoff`.
- Do not add a replacement field for `next_buddy`.
- Do not design "who should execute next".
- Do not solve historical task buddy-scope semantics beyond the artifact visibility rules above.
- Do not add an ACL framework, permission engine, workflow engine, event bus, router abstraction, plugin layer, or compatibility alias layer.
- Do not keep hidden `next_buddy` semantics under a new name.
- Do not rewrite dated memo/spec history as active runtime docs. Only update active surfaces scanned by tests: `README.md`, root/runtime `AGENTS.md`, `framework/contracts/**`, `framework/schemas/**`, active skills, and runtime code/contracts.

## 4. Definition Of Done

- `handoff` env tool and active runtime surface are gone.
- `source_refs.type="handoff"` is rejected.
- `next_buddy` is gone from active payloads, responses, contracts, projections, context, docs, skills, schemas, and tests.
- `track.advance` is gone from registry, router, dispatch, CLI, semantics, manifest/profile permissions, skills, tests, and docs.
- Track state uses immutable `owner_buddy`; `current_buddy` is gone from active runtime state.
- Artifact visibility decisions are made through one shared helper.
- Archived explicit reads reject with structured env-tool errors.
- `artifact.list`, `track.get`, and `context` use the same current-artifact summary path.
- Old handoff behavior tests are deleted or rewritten into absence tests.
- Focused and broader verification commands pass.

## 5. File-Level Change Map

### Store And Data Model

- Modify: `scripts/env_store.py`
  - Remove `HANDOFF_OBJECTS_DIR`, `VALID_HANDOFF_STATUS`, `handoff_file()`, `validate_handoff_record()`, `list_handoffs()`, `get_handoff()`, `save_handoff()`, and `create_handoff()`.
  - Remove `_validate_retired_handoff_private_path()`.
  - Remove `"handoff"` from `_normalize_source_refs()` supported object ref types.
  - Replace `validate_track()` fields `current_buddy` and `next_buddy` with required `owner_buddy`.
  - Replace `create_track(... current_buddy, next_buddy ...)` with `create_track(... owner_buddy="pm" ...)`.
  - Replace `update_track()` allowed fields with `{"title", "status", "summary", "task_ids"}`.
  - Keep `task_ids`, task registration, artifact revision slot behavior, and owner-only artifact write constraints.
- Modify: `scripts/env/services/source_refs.py`
  - Remove `"handoff"` from `_ALLOWED_TYPES`.
  - Remove `"handoff"` from object-id normalization branch.
  - Keep `artifact`, `track`, `task`, `buddybox`, `external`, and `note`.
- Modify: `tests/runtime_root_test_helper.py`
  - Remove patching of `env_store.HANDOFF_OBJECTS_DIR`.

### Artifact Visibility Helper

- Add: `scripts/env/services/artifact_visibility.py`
  - Move and replace the useful parts of `scripts/env/services/track_relations.py`.
  - Export:
    - `artifacts_for_task(task_id: str) -> list[dict[str, Any]]`
    - `artifact_track_association(artifact: dict[str, Any]) -> dict[str, Any] | None`
    - `artifact_read_decision(artifact: dict[str, Any], active_buddy: str) -> dict[str, Any]`
    - `artifact_summary_row(artifact: dict[str, Any], active_buddy: str, *, track: dict[str, Any] | None = None, task: dict[str, Any] | None = None) -> dict[str, Any]`
    - `current_artifact_rows_for_track(track_id: str, active_buddy: str) -> list[dict[str, Any]]`
    - `assert_track_readable(track_id: str, *, active_buddy: str, action: str) -> dict[str, Any] | None` if services need a shared archived-track rejection payload builder; otherwise keep rejection builders in services and only return a decision dict.
  - Decision order:
    - Missing task association rejects.
    - Missing track for non-owner rejects.
    - Archived track rejects before owner allow.
    - Owner allow.
    - Non-current foreign artifact rejects.
    - Active-buddy-owned active task on the same non-archived track allows.
    - Everything else rejects.
  - Summary rows return neutral relation labels only: `owner`, `track_task`, or `none`.
  - Summary rows replace `readable_by_current_buddy` with `readable_by_active_buddy`.
- Delete: `scripts/env/services/track_relations.py`
  - Delete after all imports move to `artifact_visibility.py`.
  - Do not keep a compatibility re-export module.

### Track Service

- Modify: `scripts/env/services/tracks.py`
  - Import `artifact_visibility` instead of `track_relations`.
  - Remove `_ADVANCE_FIELDS` and `advance_track_for_pm()`.
  - Change `_CREATE_FIELDS` to `{"track_id", "title", "status", "summary"}`.
  - Change `_UPDATE_FIELDS` to `{"track_id", "title", "status", "summary"}`.
  - Remove payload error hints for `current_buddy` and `next_buddy`.
  - Change `_normalize_track_summary()` to return `owner_buddy` and never `current_buddy` or `next_buddy`.
  - Change `list_tracks_for_active_buddy()` buddy filtering to match `owner_buddy` or active task relation; remove `next_buddy`.
  - Filter archived tracks from default `track.list` discovery.
  - Change `get_track_for_active_buddy()` to reject archived tracks with a structured `E_TRACK_ARCHIVED` or `E_TRACK_READ_SCOPE` error.
  - Change `_track_context()` artifact rows to call `artifact_visibility.artifact_summary_row()`.
  - Change `_pm_write()`:
    - `track.create` records `owner_buddy=active_buddy`.
    - `track.update` accepts only title/status/summary patches.
    - `track.archive` continues to set `status="archived"`.
    - Lifecycle change values are `created`, `updated`, `archived`; `advanced` is removed.
  - Remove allowed next actions that mention handoff or next actor.

### Artifact Service

- Modify: `scripts/env/services/artifacts.py`
  - Import `artifact_visibility` instead of `track_relations`.
  - Change `list_artifacts_for_track()` to reject archived explicit track reads before summary selection.
  - Change `get_artifact_for_active_buddy()` to use `artifact_visibility.artifact_read_decision()`.
  - Change `_artifact_response_row()` to expose `readable_by_active_buddy`, not `readable_by_current_buddy`.
  - Remove `allowed_next_actions` that point to `handoff.create`.
  - Keep owner-only `create_revision` and `update_metadata` checks.

### Handoff Removal

- Delete: `scripts/env/services/handoffs.py`
- Modify: `scripts/env/tools/dispatch.py`
  - Remove `handoff_service` import.
  - Remove the `"handoff"` handler map.
- Modify: `scripts/env/tools/contracts.py`
  - Remove the `handoff` registry entry.
  - Remove any `required_permission` values `handoff.read` and `handoff.create`.
- Modify: `scripts/env/tools/semantics.py`
  - Remove `handoff` from `_CAPABILITIES`.
  - Remove all `handoff` action rows from `_action_rows()`.
  - Remove `handoff` from `compact_tool_affordances()`.
  - Remove handoff paths from `buddybox` `does_not_write` wording.
  - Update `task`/`artifact`/`context` text that currently says tasks/artifacts are used by handoffs.
- Modify: `scripts/env/tools/router.py`
  - No direct handler edit is required if it remains registry-derived, but update rejection text only if it lists expected tools in tests.
- Modify: `scripts/env/client.py`
  - Remove the `handoff` subparser.
  - Remove `_dispatch_handoff()`.
  - Remove the `elif args.resource == "handoff"` branch.
- Modify: `scripts/turn_runtime.py`
  - No structural change if status stays registry-derived. Verify `env_tools` no longer includes `handoff`.

### Context Service

- Modify: `scripts/env/services/context.py`
  - Import `artifact_visibility`.
  - Remove `handoffs = env_store.list_handoffs()`.
  - Remove `handoff_summaries`, `has_handoffs`, and `handoffs` counts.
  - Remove `"handoffs"` from `context_sources_desc()`.
  - Remove `handoff` from `allowed_next_actions` text.
  - Filter archived tracks from `visible_tracks` and `candidate_tracks`.
  - If `track_id` filter names an archived track, return active context without that track rather than exposing it as active collaboration context. Explicit hard rejection remains owned by `track.get`, `artifact.list`, and `artifact.get`.
  - Candidate track rows expose `owner_buddy` and `active_buddy_role` values `owner`, `track_task`, or `observer`; remove `current_buddy`, `next_buddy`, and `participant`.

### Projection, Context Panel, And Workspace Contract

- Modify: `scripts/runtime_store/projections.py`
  - Remove `_workspace_uses_projected_state()` handoff path.
  - Remove `handoff_object_path()` and `build_handoff_view()`.
  - Remove `handoffs` from `build_workspace_projection()`.
  - Change track projection rows from `current_buddy`/`next_buddy` to `owner_buddy`.
  - Keep task `current_artifacts` as the current-artifact projection source.
- Modify: `scripts/workspace_data.py`
  - Remove `build_handoff_view()` facade.
- Modify: `framework/contracts/workspace-projection.json`
  - Remove top-level key `handoffs`.
  - Remove `buddyswitch/objects/handoffs/*.json` from `data_sources`.
  - Change track view shape fields from `current_buddy` and `next_buddy` to `owner_buddy`.
  - Remove `view_shapes.handoff`.
- Modify: `framework/console/app.js`
  - Remove `handoffs` from `emptyWorkspace` and normalization.
  - Delete `deriveNextStepStateForTrack()`, `deriveNextStepStateForTask()`, and `_modeForBuddies()` if they exist only for next-buddy handoff state.
  - If the console still needs an orientation helper, replace it with a neutral `deriveTrackOwnerState(trackPayload)` that returns `trackId`, `ownerBuddy`, `status`, and `summary` without recommendations.
- Modify: `tests/test_console_app_contract.py`
  - Replace next-step/handoff expectations with owner/status display expectations.

### Cleanup And Launcher Runtime Projection

- Modify: `scripts/env_cleanup.py`
  - Remove `handoff_objects` from `CATEGORY_ORDER`, `new_plan()`, `counts_by_category`, ids, records, and text output.
  - Remove `discover_handoff_objects()` and `add_indexed_handoff()`.
  - Remove buddy-scoped handoff attribution.
  - Remove `buddyswitch/objects/handoffs` from required skeleton recreation.
  - For `--all-data`, either ignore stale handoff directories or delete the entire stale directory as retired residue without exposing `handoff_object_ids`. Use one behavior consistently in tests; prefer deleting the stale directory only under `--all-data`.
- Modify: `tools/launcher/workspace.sh`
  - Remove `buddyswitch/objects/handoffs` from:
    - `buddyswitch_workspace_runtime_managed_paths`
    - `buddyswitch_workspace_runtime_output_paths`
    - `buddyswitch_workspace_projected_state_paths`
    - local runtime state skeleton
    - runtime-only git excludes
  - Do not create or symlink a handoff state directory for new instances.
- Modify: `tools/launcher/cleanup.sh`
  - No argument change expected; it delegates to `scripts/env_cleanup.py`. Update help text only if tests expose handoff wording.
- Modify: `tests/test_buddyswitch_launcher.py`
  - Remove expectations for projected `buddyswitch/objects/handoffs`.
  - Remove runtime copied service file expectation for `scripts/env/services/handoffs.py`.
  - Remove `handoff` from tool lists in runtime agent asset expectations.

### Manifest, Profiles, Skills, Contracts, Schemas, Docs

- Modify: `buddyswitch/manifest.toml`
  - Delete `[[skills]] id = "handoff-tool"`.
  - Remove `"handoff-tool"` from every buddy `skills` list.
  - Remove `handoff.read`, `handoff.create`, and `track.advance` permissions.
  - Keep `track.create`, `track.update`, and `track.archive` PM-only.
- Modify: `scripts/env_manifest.py`
  - Remove `"handoff"` from `_validate_permission()` supported objects.
  - Update `buddy_authority_profile()` runtime note to `track/task/artifact/buddybox`.
- Modify: `buddyswitch/env-profiles/{market,pm,design,dev,test}.json`
  - Remove `state_capability.handoff_targets`.
  - Remove `advance` from PM `state_capability.track_effects`.
- Modify: `scripts/env_profiles.py`
  - Remove validation for `state_capability.handoff_targets`.
  - Change expected PM `track_effects` to `["create", "update", "archive"]`.
- Modify: `framework/contracts/buddy-env-profile.json`
  - Remove `state_capability.handoff_targets` enum.
- Delete: `buddyswitch/skills/shared/handoff-tool/`
- Modify: `buddyswitch/skills/shared/track-tool/SKILL.md`
  - Operations become `list`, `get`, `join`, `create`, `update`, `archive`, `attach-task`, `detach-task`.
  - Remove `advance`.
- Modify: `buddyswitch/skills/shared/track-tool/assets/track-operation-template.md`
  - Replace `current_buddy`/`next_buddy` examples with create/update/archive examples using no next actor.
- Modify: `buddyswitch/skills/shared/artifact-tool/SKILL.md`
  - Clarify non-owner reads come through active non-archived track collaboration surface.
  - Do not mention handoff.
- Modify: `buddyswitch/skills/shared/task-tool/SKILL.md`
  - Remove "task ids used by handoffs".
- Modify active role skills:
  - `buddyswitch/skills/market/{research-scan,pmf-recon,customer-discovery,positioning-copy,channel-discovery,launch-prep}/SKILL.md`
  - `buddyswitch/skills/pm/write-prd/SKILL.md`
  - `buddyswitch/skills/design/shape-prototype/SKILL.md`
  - `buddyswitch/skills/dev/{implement-task,skill-creator-importer}/SKILL.md`
  - `buddyswitch/skills/test/smoke-test/SKILL.md`
  - Replace "task, artifact, or handoff objects" with "task or artifact objects; buddybox for private files".
  - Remove "Use optional `handoff` when another manifest buddy should continue."
  - Keep artifact kind names such as `design-handoff` only when they mean a deliverable kind, not the removed runtime object.
- Modify: `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`
  - Tool list excludes `handoff`.
  - Output rule removes "next handoff target".
- Modify: `framework/contracts/{pm,design,dev,market,test}.md`
  - Remove `buddyswitch/objects/handoffs/<handoff-id>.json`.
  - Remove `track.advance` and next actor wording.
  - Keep role-specific artifact and buddybox guidance.
- Modify: `framework/schemas/{pm,design,dev,market,test}/*-result.json`
  - Remove top-level `handoff` property from all schemas.
  - In PM schema, remove `"advance"` from track action enum.
  - In PM schema, replace `current_buddy`/`next_buddy` properties with no owner mutation fields. Track effects may include `track_id`, `title`, `status`, and `summary`.
- Modify: `tests/test_output_schema_boundaries.py`
  - Remove `handoff` from `COMMON_OPTIONAL_COMMIT_KEYS`.
  - Replace PM `advance` sample with `update` or `archive`.
- Modify: `README.md`
  - Remove `handoff_id`, `handoff.*`, and `buddyswitch/objects/handoffs/*.json`.
  - Runtime sources list active tools only.

## 6. Implementation Phases

### Phase 1: Add Contract-Failing Tests

**Files:**

- Modify: `tests/test_env_tool_router.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_env_manifest_v2.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_track_env_tool.py`
- Modify: `tests/test_artifact_env_tool.py`
- Modify: `tests/test_env_store_v2.py`
- Modify: `tests/test_cleanup_system.py`
- Modify: `tests/test_parallel_contracts.py`
- Modify: `tests/test_console_app_contract.py`
- Modify: `tests/test_output_schema_boundaries.py`
- Delete or replace: `tests/test_handoff_env_tool.py`
- Modify: `tests/test_turn_integration.py`
- Modify: `tests/test_runtime_tool_feedback.py`
- Modify: `tests/test_task_management_skill_architecture.py`
- Modify: `tests/test_memory_removal_contract.py`
- Modify: `tests/test_runless_runtime_contract.py`
- Modify: `tests/test_buddyswitch_launcher.py`

**Steps:**

- [ ] Add failing absence tests for `handoff` in registry, dispatch, router, CLI, runtime status, context catalog, manifest, skills, projection, cleanup, and launcher paths.
- [ ] Add failing tests that `source_refs.type="handoff"` is rejected in artifact validation and store normalization.
- [ ] Add failing tests that `next_buddy`, `current_buddy`, and `track.advance` are absent from payload fields, operation semantics, compact affordances, responses, projection, schemas, and skills.
- [ ] Add failing owner tests: create returns `owner_buddy`, update rejects `owner_buddy`, and raw stored track keeps original owner.
- [ ] Add failing archive tests: explicit `track.get`, `artifact.list`, and `artifact.get` reject archived track reads, and context/summarize omit archived active context.
- [ ] Add failing artifact visibility tests: non-owner full read succeeds through active non-archived track task relation, does not depend on current/next/handoff relation, and superseded revision reads reject for non-owners.

**Expected result:**

- Focused tests fail against the current implementation for the targeted old contracts.

**Verification command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_router.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_manifest_v2.py \
  tests/test_runtime_skills.py \
  -q
```

### Phase 2: Remove Handoff From Runtime Tool Surface

**Files:**

- Delete: `scripts/env/services/handoffs.py`
- Modify: `scripts/env/tools/dispatch.py`
- Modify: `scripts/env/tools/contracts.py`
- Modify: `scripts/env/tools/semantics.py`
- Modify: `scripts/env/client.py`
- Modify: `scripts/turn_runtime.py` only if static assumptions remain
- Modify: `scripts/env/services/source_refs.py`
- Modify: `scripts/env_store.py`

**Steps:**

- [ ] Remove handoff service import and handler map.
- [ ] Remove handoff registry entry and semantics rows.
- [ ] Remove handoff CLI parser and dispatcher.
- [ ] Remove handoff store functions and constants.
- [ ] Remove `handoff` source ref type from both source ref normalizers.
- [ ] Update runtime feedback text that suggests `handoff.create`.

**Expected result:**

- Unsupported `tool="handoff"` rejects at router as an unregistered tool.
- `track.advance` is still present until Phase 3; do not mix concerns in this phase.

**Verification command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_router.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_artifact_env_tool.py \
  tests/test_env_store_v2.py \
  -q
```

### Phase 3: Replace Track Current/Next With Immutable Owner And Remove Advance

**Files:**

- Modify: `scripts/env_store.py`
- Modify: `scripts/env/services/tracks.py`
- Modify: `scripts/env/tools/contracts.py`
- Modify: `scripts/env/tools/semantics.py`
- Modify: `scripts/env/client.py`
- Modify: `buddyswitch/manifest.toml`
- Modify: `scripts/env_manifest.py`
- Modify: `buddyswitch/env-profiles/{market,pm,design,dev,test}.json`
- Modify: `scripts/env_profiles.py`
- Modify: `framework/contracts/buddy-env-profile.json`

**Steps:**

- [ ] Change store validation from `current_buddy`/`next_buddy` to `owner_buddy`.
- [ ] Change store create/update helpers so `owner_buddy` is created once and not updateable.
- [ ] Remove `track.advance` service function, contract action, semantic row, compact affordance support, CLI subcommand, PM permission, and PM profile effect.
- [ ] Update track create/update payload validation and response summaries.
- [ ] Update manifest/profile validators to reject `handoff.*` and `track.advance`.

**Expected result:**

- Active track responses contain `owner_buddy`.
- `track.update` rejects `owner_buddy`, `current_buddy`, and `next_buddy`.
- `track.advance` is unsupported through router and absent from catalogs.

**Verification command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_track_env_tool.py \
  tests/test_env_tool_router.py \
  tests/test_env_manifest_v2.py \
  tests/test_buddy_env_profiles.py \
  -q
python3 scripts/env_profiles.py validate-all
python3 scripts/env_manifest.py print >/tmp/buddyswitch-manifest.json
```

### Phase 4: Centralize Artifact Visibility And Enforce Archived Read Boundary

**Files:**

- Add: `scripts/env/services/artifact_visibility.py`
- Delete: `scripts/env/services/track_relations.py`
- Modify: `scripts/env/services/artifacts.py`
- Modify: `scripts/env/services/tracks.py`
- Modify: `scripts/env/services/context.py`

**Steps:**

- [ ] Move current-artifact row selection into `artifact_visibility.current_artifact_rows_for_track()`.
- [ ] Implement `artifact_read_decision()` with archived-track rejection before owner allow.
- [ ] Make `artifact.get` use the decision helper.
- [ ] Make `artifact.list` reject archived explicit track reads and use current rows only.
- [ ] Make `track.get` reject archived explicit reads and use the same current row helper.
- [ ] Make `context.get` and `context.summarize` filter archived tracks and visible artifacts.
- [ ] Rename summary field `readable_by_current_buddy` to `readable_by_active_buddy`.

**Expected result:**

- Artifact read behavior is owner-only for writes and owner-or-active-track-task for reads.
- Archived explicit reads fail consistently.
- `artifact.list` and `track.get` agree on current artifact summaries.

**Verification command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_artifact_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_context_binding_env_tool.py \
  -q
```

### Phase 5: Update Projection, Cleanup, Launcher, And Context Panel

**Files:**

- Modify: `scripts/runtime_store/projections.py`
- Modify: `scripts/workspace_data.py`
- Modify: `framework/contracts/workspace-projection.json`
- Modify: `framework/console/app.js`
- Modify: `scripts/env_cleanup.py`
- Modify: `tools/launcher/workspace.sh`
- Modify: `tools/launcher/cleanup.sh` only if help text contains stale wording
- Modify: `tests/test_parallel_contracts.py`
- Modify: `tests/test_cleanup_system.py`
- Modify: `tests/test_console_app_contract.py`
- Modify: `tests/test_buddyswitch_launcher.py`

**Steps:**

- [ ] Remove handoff top-level projection.
- [ ] Change projected track shape to `owner_buddy`.
- [ ] Remove handoff cleanup indexing and skeleton recreation.
- [ ] Remove handoff runtime projected path creation and excludes.
- [ ] Remove console next-step/handoff derivation.

**Expected result:**

- Workspace projection no longer contains `handoffs`.
- Runtime instance workspaces do not create or symlink `buddyswitch/objects/handoffs`.
- Cleanup reports artifact/task/track categories only.

**Verification command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_parallel_contracts.py \
  tests/test_cleanup_system.py \
  tests/test_console_app_contract.py \
  tests/test_buddyswitch_launcher.py \
  -q
```

### Phase 6: Update Skills, Role Contracts, Schemas, README, And Active Guidance

**Files:**

- Delete: `buddyswitch/skills/shared/handoff-tool/`
- Modify: `buddyswitch/skills/shared/track-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/track-tool/assets/track-operation-template.md`
- Modify: `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/task-tool/SKILL.md`
- Modify: all active role skills under `buddyswitch/skills/{market,pm,design,dev,test}/`
- Modify: `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`
- Modify: `framework/contracts/{pm,design,dev,market,test}.md`
- Modify: `framework/schemas/{pm,design,dev,market,test}/*-result.json`
- Modify: `tests/test_output_schema_boundaries.py`
- Modify: `README.md`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_runtime_skills.py`

**Steps:**

- [ ] Remove `handoff-tool` from manifest and runtime skills.
- [ ] Rewrite active skill guidance to use task/artifact/buddybox only.
- [ ] Remove `next_buddy`, handoff object, handoff permission, and `track.advance` examples.
- [ ] Keep `design-handoff` as an artifact kind only where it names a deliverable.
- [ ] Update output schemas so buddy result payloads no longer include top-level `handoff`.
- [ ] Add active-surface residue scans excluding historical `docs/memo/**` and dated `docs/spec/**`.

**Expected result:**

- Runtime skills materialized for each buddy exclude `handoff-tool`.
- Active docs and schemas no longer teach next actor or handoff runtime state.

**Verification command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  tests/test_output_schema_boundaries.py \
  tests/test_env_manifest_v2.py \
  -q
```

### Phase 7: Rewrite Or Delete Old Behavior Tests

**Files:**

- Delete: `tests/test_handoff_env_tool.py`
- Modify: `tests/test_memory_removal_contract.py`
- Modify: `tests/test_turn_integration.py`
- Modify: `tests/test_runtime_tool_feedback.py`
- Modify: `tests/test_task_management_skill_architecture.py`
- Modify: `tests/test_runless_runtime_contract.py`
- Modify: any remaining tests found by residue scan.

**Steps:**

- [ ] Delete direct handoff behavior tests instead of preserving them under compatibility names.
- [ ] Replace turn integration handoff flow with track/task/artifact direct-id collaboration: PM creates track/artifact, another buddy joins track, then reads current artifact through `artifact.get`.
- [ ] Replace memory-removal handoff assertions with source_refs rejection and no handoff surface assertions.
- [ ] Replace runtime feedback fixtures that seed `current_buddy`/`next_buddy` with `owner_buddy`.
- [ ] Replace task architecture fixture fields with `owner_buddy`.

**Expected result:**

- No test preserves old handoff or next-buddy behavior.
- Remaining tests prove the contracted smaller surface.

**Verification command:**

```bash
rg -n "handoff|next_buddy|current_buddy|track\\.advance|readable_by_current_buddy" tests scripts buddyswitch framework tools README.md AGENTS.md \
  -g '!docs/memo/**' \
  -g '!docs/spec/**'
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

## 7. Broad Verification

Run after all phases:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_store_v2.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_task_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_router.py \
  tests/test_env_tool_response_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_runtime_skills.py \
  tests/test_env_manifest_v2.py \
  tests/test_buddy_env_profiles.py \
  tests/test_cleanup_system.py \
  tests/test_parallel_contracts.py \
  tests/test_console_app_contract.py \
  tests/test_output_schema_boundaries.py \
  tests/test_turn_integration.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_repo_consistency.py \
  -q

python3 scripts/env_profiles.py validate-all
python3 scripts/env_manifest.py print >/tmp/buddyswitch-manifest.json
python3 scripts/turn_runtime.py status >/tmp/buddyswitch-runtime-status.json

rg -n "handoff|next_buddy|current_buddy|track\\.advance|readable_by_current_buddy" \
  README.md AGENTS.md scripts buddyswitch tools framework tests \
  -g '!docs/memo/**' \
  -g '!docs/spec/**'
```

Expected:

- Pytest exits `0`.
- Manifest/profile commands exit `0`.
- Runtime status JSON contains tools `task`, `track`, `artifact`, `buddybox`, `context`, `evidence`, `search`.
- Residue scan has no active-surface hits except artifact kind prose such as `design-handoff` where tests explicitly allow it.

## 8. Remaining Risk To Watch

- Historical fixture JSON may still contain `current_buddy` or `next_buddy`. Default action is to update fixtures directly. Add read-time normalization only if an active test proves a runtime fixture must be readable during this development-stage cleanup.
- `design-handoff` is both a valid artifact kind and a word containing `handoff`. Residue tests must distinguish artifact-kind names from the retired runtime object.
- Archived track write semantics are not redesigned here. If tests reveal owner writes under archived tracks are confusing, record it as a later lifecycle task instead of expanding this cleanup.
