# Track Task Role Rebuild Implementation Plan

> **For agentic workers:** Implement this plan in `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem` on branch `dev_buddy_mem`. Use test-first changes for every behavior change. Do not preserve the old `track -> task -> artifact` collaboration chain through aliases, compatibility shims, wrapper helpers, or dual read paths.

**Goal:** Rebuild BuddySwitch so `track` is the shared collaboration surface, `task` is a buddy-private work aid, and artifacts become cross-buddy material only when published directly to a non-archived track.

**Architecture:** Replace the old task-relation bridge with direct track publication. Runtime contracts stay in Python services, env-tool registry/semantics, JSON projection contracts, manifest/profile data, active skills, role contracts, and tests. The main path is `track.open -> shared_materials -> artifact.get`, with `track.add_material`, `track.add_update`, and `track.add_proof` mutating the shared page.

**Tech Stack:** Python env store/services/tools, broker-routed `env.tool`, Python CLI, TOML manifest, JSON contracts/projections, Markdown runtime skills/contracts, launcher shell projection, pytest/unittest.

---

## 1. Source Inputs

- `AGENTS.md`
- `docs/memo/2026-05-17-track-task-role-rebuild-memo.md`
- Store/model inspected: `scripts/env_store.py`
- Env services inspected: `scripts/env/services/tracks.py`, `scripts/env/services/tasks.py`, `scripts/env/services/artifacts.py`, `scripts/env/services/artifact_visibility.py`, `scripts/env/services/context.py`, `scripts/env/services/comments.py`
- Tool layer inspected: `scripts/env/tools/contracts.py`, `scripts/env/tools/semantics.py`, `scripts/env/tools/dispatch.py`, `scripts/env/tools/router.py`, `scripts/env/client.py`
- Runtime/projection inspected: `scripts/turn_runtime.py`, `scripts/runtime_store/projections.py`, `scripts/artifact_selection.py`, `framework/contracts/workspace-projection.json`, `framework/console/app.js`
- Manifest/docs/skills inspected: `buddyswitch/manifest.toml`, `buddyswitch/env-profiles/pm.json`, `buddyswitch/skills/shared/{track-tool,artifact-tool,task-tool}/SKILL.md`, `tools/launcher/assets/buddies/pm/AGENTS.md`, `framework/contracts/{pm,design,dev,test,market}.md`
- Tests inspected: `tests/test_track_env_tool.py`, `tests/test_artifact_env_tool.py`, `tests/test_task_env_tool.py`, `tests/test_env_store_v2.py`, `tests/test_comment_env_tool.py`, `tests/test_env_layer_end_to_end.py`, `tests/test_env_tool_router.py`, `tests/test_env_tool_response_contract.py`, `tests/test_env_tool_semantic_contract.py`, `tests/test_repo_consistency.py`, `tests/test_runtime_skills.py`, `tests/test_runtime_tool_feedback.py`, `tests/test_runtime_broker.py`, `tests/test_turn_integration.py`, `tests/test_artifact_selection.py`, `tests/test_cleanup_system.py`

## 2. Current Core Problem

Current implementation still makes shared collaboration depend on task relations:

- `scripts/env_store.py` validates tracks with `status`, `summary`, and `task_ids`.
- `scripts/env/services/tracks.py` returns track context containing related `tasks` and artifact summaries derived from those tasks.
- `track.join`, `track.attach_task`, and `track.detach_task` are registered in service, dispatch, CLI, semantics, runtime skills, and tests.
- `scripts/env/services/artifact_visibility.py` grants non-owner artifact body reads only when the active buddy has an active task relation on the artifact's track.
- `artifact.create_revision` requires an active-buddy-owned `task_id`, and artifacts store `task_id`.
- `context`, workspace projection, cleanup, artifact selection, role contracts, and shared skills still teach task-backed shared collaboration.

The bottleneck is conceptual and runtime coupling: a buddy must create or attach a private task before reading shared material. The memo's target removes that bridge.

## 3. Final Target

The rebuilt runtime has one obvious collaboration path:

1. PM creates a track with `outcome`, `appetite`, and `now`.
2. PM publishes a PRD through `track.add_material`.
3. Design opens the track through `track.open`, sees current `shared_materials`, and reads the PRD through `artifact.get`.
4. Design publishes a design draft through `track.add_material`.
5. Dev opens the same track and reads PM plus Design materials without joining or attaching a task.
6. Test publishes smoke proof through `track.add_proof`.
7. PM sets `state="done"` with `track.update_now`, or archives the track through `track.archive` when it should disappear from collaboration.

## 4. Functional Scope From Memo

- `track` is a human-readable shared progress page with fields `id`, `title`, `outcome`, `owner_buddy`, `state`, `health`, `appetite`, `now`, `shared_materials`, `updates`, `close_proof`, `created_at`, `updated_at`, and `archived_at`.
- `owner_buddy` is always `pm`, is set at creation, and is not patchable.
- `state` is one of `active`, `blocked`, `review`, `done`.
- `health` is one of `ok`, `risk`, `blocked`, `stale`.
- `now` stores exactly `next` and `blocker`.
- `shared_materials` stores current published artifact refs, not full artifact bodies.
- `updates` stores concise progress, decision, blocker, and proof notes.
- `close_proof` stores exact proof refs that close the track.
- `archive` is implemented as `archived_at != null`; archived tracks are omitted from normal lists and rejected by reads or mutations.
- `task` remains active-buddy private. `task.track_id` is an optional private organization hint and never mutates track state.
- `track` never stores `task_ids`.
- Artifact publication is direct: `artifact.published_to_track` and `track.shared_materials` / `track.close_proof`.
- Non-archived tracks and their current shared materials are readable by all buddies.
- All buddies can add updates, materials, proof, and now-state changes to non-archived tracks in V1.
- Only PM can create and archive tracks.

## 5. Non-Goals

- Do not implement track participation, buddy join/leave, task-track attach/detach, handoff objects, next-buddy routing, custom workflows, dependency engines, ACL frameworks, project portfolios, task hierarchies, general chat, artifact access through task relations, or task-derived track visibility.
- Do not preserve `track.get`, `track.join`, `track.attach_task`, `track.detach_task`, `track.task_ids`, `artifact.task_id`, `task.artifact_ids`, or `task.artifact_slots` as compatibility paths.
- Do not rewrite dated memo/spec history. Residue scans should target active runtime surfaces and tests, excluding dated archives.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly outside isolated tests and cleanup utilities.

## 6. Target Env Tool Surface

### Track

- `track.create`
- `track.list`
- `track.open`
- `track.update_now`
- `track.add_material`
- `track.add_update`
- `track.add_proof`
- `track.archive`

Removed from active runtime:

- `track.get`
- `track.update`
- `track.join`
- `track.attach_task`
- `track.detach_task`

### Artifact

- `artifact.get`
- `artifact.create_revision`
- `artifact.update_metadata`

`artifact.list` is removed. Current track materials are discovered through `track.open`.

### Task

- `task.create`
- `task.list`
- `task.get`
- `task.update`
- `task.archive`

Task operations stay active-buddy private and never create shared collaboration access.

## 7. Target Data Contracts

### Track Object

```json
{
  "id": "track-landing-proof",
  "title": "Landing page first proof",
  "outcome": "Validate whether the landing page explains the core value.",
  "owner_buddy": "pm",
  "state": "active",
  "health": "blocked",
  "appetite": "2 days",
  "now": {
    "next": "Design produces first-screen structure.",
    "blocker": "One-line positioning is unsettled."
  },
  "shared_materials": [],
  "updates": [],
  "close_proof": [],
  "created_at": "2026-05-17T12:00:00+08:00",
  "updated_at": "2026-05-17T12:00:00+08:00",
  "archived_at": null
}
```

### Shared Material Ref

```json
{
  "type": "artifact",
  "artifact_id": "art-pm-prd-r1",
  "label": "PRD",
  "kind": "prd",
  "from_buddy": "pm",
  "summary": "Landing page scope, constraints, and success checks.",
  "current": true,
  "published_at": "2026-05-17T12:00:00+08:00"
}
```

`track.add_material` marks older material refs with the same `(kind, label, from_buddy)` on the same track as `current=false`.

### Update Ref

```json
{
  "id": "upd-landing-001",
  "by_buddy": "design",
  "summary": "First-screen structure is blocked by unresolved one-line positioning.",
  "kind": "blocker",
  "refs": [{"type": "artifact", "id": "art-design-draft-r1"}],
  "created_at": "2026-05-17T12:30:00+08:00"
}
```

Allowed `kind` values are `progress`, `decision`, `blocker`, and `proof`.

### Artifact Object

```json
{
  "id": "art-pm-prd-r1",
  "title": "Landing page PRD",
  "kind": "prd",
  "created_by": "pm",
  "published_to_track": "track-landing-proof",
  "publication_role": "material",
  "summary": "Landing page scope, constraints, and success checks.",
  "content": {},
  "source_refs": [],
  "revision": 1,
  "supersedes_artifact_id": null,
  "is_current": true,
  "created_at": "2026-05-17T12:00:00+08:00",
  "updated_at": "2026-05-17T12:00:00+08:00"
}
```

`published_to_track` is `null` for a private draft artifact. Non-owner reads require a non-archived `published_to_track` and a current material or proof ref on that track.

### Task Object

```json
{
  "id": "task-design-sketch-first-screen",
  "buddy": "design",
  "title": "Sketch first screen",
  "status": "active",
  "track_id": "track-landing-proof",
  "summary": "Private checklist item for Design.",
  "created_at": "2026-05-17T12:05:00+08:00",
  "updated_at": "2026-05-17T12:05:00+08:00"
}
```

`track_id` is a private hint. It does not make the task visible to other buddies and does not grant artifact read access.

## 8. Current Code Change Map

- Store boundary: `scripts/env_store.py` owns durable JSON validation and writes. It must replace track `status/summary/task_ids`, artifact `task_id`, and task `artifact_ids/artifact_slots` with the target shapes before service changes can be made safely.
- Track service boundary: `scripts/env/services/tracks.py` currently exposes relation and lifecycle actions. It must become the only shared page mutation service for `create`, `list`, `open`, `update_now`, `add_material`, `add_update`, `add_proof`, and `archive`.
- Artifact service boundary: `scripts/env/services/artifacts.py` currently validates `task_id` ownership for writes and delegates read grants to task relations. It must keep body reads and private draft writes while moving shared publication into track operations.
- Visibility helper boundary: `scripts/env/services/artifact_visibility.py` currently derives read scope from `artifact -> task -> track -> active buddy task`. It must derive read scope from `artifact.published_to_track` and current track material/proof refs.
- Task service boundary: `scripts/env/services/tasks.py` remains private active-buddy task CRUD and must stop teaching or mutating track relations.
- Context/projection boundary: `scripts/env/services/context.py`, `scripts/runtime_store/projections.py`, `framework/contracts/workspace-projection.json`, `framework/console/app.js`, and `scripts/artifact_selection.py` must consume track page materials instead of task bundles.
- Tool interface boundary: `scripts/env/tools/contracts.py`, `scripts/env/tools/semantics.py`, `scripts/env/tools/dispatch.py`, `scripts/env/tools/router.py`, `scripts/env/client.py`, and `scripts/runtime_kernel/coordinator.py` must expose target action names and lock modes.
- Runtime guidance boundary: `buddyswitch/manifest.toml`, `buddyswitch/env-profiles/*.json`, `buddyswitch/skills/shared/*.md`, role skills, `framework/contracts/*.md`, and `tools/launcher/assets/buddies/*/AGENTS.md` must teach the direct track material path.
- Cleanup/launcher boundary: `scripts/env_cleanup.py`, `tools/launcher/workspace.sh`, and launcher tests must keep projected object directories while removing task-track detach behavior.
- Test entrypoints: focused tests live in `tests/test_env_store_v2.py`, `tests/test_track_env_tool.py`, `tests/test_artifact_env_tool.py`, `tests/test_task_env_tool.py`, `tests/test_context_binding_env_tool.py`, `tests/test_env_tool_router.py`, `tests/test_env_tool_semantic_contract.py`, `tests/test_runtime_skills.py`, `tests/test_repo_consistency.py`, `tests/test_env_layer_end_to_end.py`, and `tests/test_turn_integration.py`.

Data flow replacement:

```text
Current: track.get -> track.task_ids -> task.artifact_slots -> artifact rows -> task relation read check
Target:  track.open -> track.shared_materials/current close_proof refs -> artifact.get direct read check
```

Command entrypoint replacement:

```text
Current: python3 scripts/env/client.py track get|join|attach-task|detach-task
Target:  python3 scripts/env/client.py track open|update-now|add-material|add-update|add-proof
```

## 9. Phased Implementation Plan

### Phase 0: Add Failing Contract Tests

| Step | Files or modules | Purpose | Expected behavior | Preconditions | Completion standard | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| 0.1 | Modify `tests/test_env_store_v2.py` | Lock the new track, artifact, and task object shapes before code changes. | `validate_track` accepts the target track shape and rejects `task_ids`, `status`, and `summary`; `validate_artifact` accepts `published_to_track` and rejects `task_id`; `validate_task` accepts private task shape without artifact slots. | Test sandbox from `RuntimeWorkspaceTestMixin` works. | New tests fail against current validators with clear field errors. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_store_v2.py -q` |
| 0.2 | Modify `tests/test_track_env_tool.py` | Define the product track surface. | PM can `track.create`; all buddies can `track.open`, `track.update_now`, `track.add_update`, `track.add_material`, and `track.add_proof`; archived tracks reject every read and mutation. | Existing broker dispatch helper can call arbitrary actions. | New tests fail because current registry lacks `open`, `update_now`, `add_material`, `add_update`, and `add_proof`. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py -q` |
| 0.3 | Modify `tests/test_artifact_env_tool.py` | Define direct track material visibility. | Design reads PM PRD via `artifact.get` after PM publishes to a non-archived track, without `track.join` or a Design task. Superseded material is absent from `track.open` and non-owner direct read rejects. | Track tests create published material through target actions. | New tests fail because current artifact read requires an active task relation. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py -q` |
| 0.4 | Modify `tests/test_task_env_tool.py` | Protect task-private positioning. | Task create/update with `track_id` stores a hint only; `track.open` does not return tasks; task reads remain active-buddy only. | Task service remains registered. | New tests fail because current track context embeds tasks. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_track_env_tool.py -q` |
| 0.5 | Modify `tests/test_env_tool_router.py`, `tests/test_env_tool_semantic_contract.py`, `tests/test_runtime_skills.py`, `tests/test_repo_consistency.py` | Lock active runtime surface and residue rules. | Registry, dispatch, CLI, runtime status, compact affordances, and track-tool skill expose the target operations and omit removed task-relation operations. | No product code changes yet. | Tests fail on old operations and missing new operations. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q` |
| 0.6 | Modify `tests/test_env_layer_end_to_end.py` and `tests/test_turn_integration.py` | Define the full memo main path. | PM -> Design -> Dev -> Test flow succeeds without `track.join`, task attachment, or task-derived artifact visibility. | Store/service tests already express target payloads. | New e2e tests fail before implementation. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_turn_integration.py -q` |

### Phase 1: Replace Store Model

| Step | Files or modules | Purpose | Expected behavior | Preconditions | Completion standard | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| 1.1 | Modify `scripts/env_store.py` constants | Replace track vocabulary. | Add `VALID_TRACK_STATE = ("active", "blocked", "review", "done")`, `VALID_TRACK_HEALTH = ("ok", "risk", "blocked", "stale")`, and `VALID_UPDATE_KIND = ("progress", "decision", "blocker", "proof")`; keep `VALID_TASK_STATUS`. | Phase 0 tests exist. | Constants are imported by services; no old `VALID_TRACK_STATUS` use remains. | `rg -n "VALID_TRACK_STATUS|track\\.status" scripts tests` returns only tests that assert absence or no hits. |
| 1.2 | Modify `scripts/env_store.py::validate_track` | Enforce target track object. | Required fields are `id`, `title`, `outcome`, `owner_buddy`, `state`, `health`, `appetite`, `now`, `shared_materials`, `updates`, `close_proof`, `created_at`, `updated_at`, `archived_at`. Old `task_ids`, `status`, `summary`, `artifact_ids`, `current_buddy`, and `next_buddy` raise `ValueError`. | Step 1.1 complete. | `validate_track` returns normalized target fields and strips no active target fields. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_store_v2.py::TrackStoreContractTests -q` |
| 1.3 | Modify `scripts/env_store.py::create_track` and `update_track` | Make PM-created tracks human-readable and non-task-backed. | `create_track` accepts `outcome`, `appetite`, `now`, `state`, `health`, and `owner_buddy`; creates empty arrays for `shared_materials`, `updates`, `close_proof`; sets `archived_at=None`. `update_track` only accepts `state`, `health`, `now`, `shared_materials`, `updates`, `close_proof`, `archived_at`. | Step 1.2 complete. | Creating a track writes no `task_ids`, `status`, or `summary`. Updating unsupported fields raises `ValueError`. | Focused env-store tests from Step 0.1 pass. |
| 1.4 | Delete `scripts/env_store.py::_register_task_id`, `_unregister_task_id`, and `register_task_to_track` | Remove track-task relationship mutation. | No store helper can append a task id into a track. | Step 1.3 complete. | `rg -n "register_task_to_track|_register_task_id|_unregister_task_id" scripts tests` returns no active code uses. | Run `rg -n "register_task_to_track|_register_task_id|_unregister_task_id" scripts tests`. |
| 1.5 | Modify `scripts/env_store.py::validate_task`, `create_task`, and `update_task` | Make tasks private and optional for collaboration. | Task shape is `id`, `buddy`, `title`, `status`, `track_id`, `summary`, `created_at`, `updated_at`; `artifact_ids` and `artifact_slots` are rejected. `track_id` is validated when present but does not mutate a track. | Step 1.4 complete. | Task create/update never writes to a track file. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_env_store_v2.py -q` |
| 1.6 | Modify `scripts/env_store.py::validate_artifact`, `create_artifact`, `update_artifact`, `delete_artifact` | Remove artifact dependency on task ownership. | Artifact shape uses `created_by`, `published_to_track`, `publication_role`, `summary`, `content`, `source_refs`, `revision`, `supersedes_artifact_id`, `is_current`, timestamps. `task_id` is rejected. `published_to_track` is `null` or an existing track id. | Step 1.5 complete. | Artifact creation can create a private draft without a task; published artifact validates against a track; owner is `created_by`. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py::ArtifactEnvToolTests -q` |
| 1.7 | Replace `scripts/env_store.py::build_track_artifact_index` | Feed artifact selection from track materials instead of tasks. | Returned index contains `track_id`, `track_title`, `outcome`, `shared_materials`, `close_proof`, and `updated_at`; no `tasks` array. | Step 1.6 complete. | `scripts/artifact_selection.py` can consume the new index in Phase 5. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_selection.py -q` fails until Phase 5, then passes. |

### Phase 2: Implement Direct Artifact Visibility

| Step | Files or modules | Purpose | Expected behavior | Preconditions | Completion standard | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| 2.1 | Modify `scripts/env/services/artifact_visibility.py` | Replace task-relation visibility with direct track publication. | `artifact_read_decision` allows owner draft reads when `published_to_track is None`; rejects archived published artifacts; allows all buddies to read current material/proof artifacts on non-archived tracks; rejects non-owner draft reads; rejects non-current foreign material unless it is in `close_proof`. | Phase 1 artifact and track shapes exist. | Decision payloads use relation labels `owner`, `track_material`, `track_proof`, or `none`; no `track_task`. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py -q` |
| 2.2 | Modify `scripts/env/services/artifact_visibility.py` summary helpers | Return material/proof rows from track refs. | `current_material_rows_for_track(track_id, active_buddy)` reads `track.shared_materials` current refs; `proof_rows_for_track` reads `track.close_proof`; rows include `artifact_id`, `kind`, `label`, `from_buddy`, `summary`, `currentness`, `published_at`, and `readable_by_active_buddy`. | Step 2.1 complete. | No helper scans `track.task_ids`, `task.artifact_ids`, or `artifact_slots`. | `rg -n "task_ids|artifact_slots|artifact_ids" scripts/env/services/artifact_visibility.py` returns no hits. |
| 2.3 | Modify `scripts/env/services/artifacts.py` | Align artifact tool with new model. | Remove `artifact.list`; make `artifact.get` use direct visibility; make `artifact.create_revision` create active-buddy-owned draft artifacts without `task_id`; make `artifact.update_metadata` owner-only through `created_by`. | Steps 2.1 and 2.2 complete. | Artifact payload validation rejects `task_id`; direct read after `track.add_material` succeeds without a task. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py -q` |
| 2.4 | Modify `scripts/env/services/comments.py` | Keep comments readable through target boundaries. | Track comments call readable-track logic based on `archived_at`; artifact comments use direct artifact visibility; comments on a published current PM artifact are allowed for Design without a Design task. | Step 2.3 complete. | Existing comment non-goals remain rejected; artifact comment tests are rewritten from task relation to track material. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_comment_env_tool.py -q` |

### Phase 3: Replace Track Service

| Step | Files or modules | Purpose | Expected behavior | Preconditions | Completion standard | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| 3.1 | Modify `scripts/env/services/tracks.py` action field sets | Register target action payloads. | Field sets exist for `track.create`, `track.list`, `track.open`, `track.update_now`, `track.add_material`, `track.add_update`, `track.add_proof`, and `track.archive`; no field set exists for removed actions. | Phase 2 visibility helpers exist. | Unsupported old fields and actions reject through router/registry. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py -q` |
| 3.2 | Replace track summary/context builders in `scripts/env/services/tracks.py` | Make track page human-readable. | `track.list` returns `id`, `title`, `outcome`, `owner_buddy`, `state`, `health`, `appetite`, `now`, `updated_at`; `track.open` returns full track page with current `shared_materials`, `updates`, and `close_proof`; no `tasks` key. | Step 3.1 complete. | Serialized `track.open` response does not contain `task_ids`, `track_task`, `source_task_id`, `artifact_slots`, or full artifact `content`. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py -q` |
| 3.3 | Implement `track.create` in `scripts/env/services/tracks.py` | PM-only track creation. | Only active buddy `pm` can create. Payload requires `track_id`, `title`, `outcome`, `appetite`, and `now.next`; defaults `state="active"`, `health="ok"`, and `now.blocker=null`. `owner_buddy` in payload rejects. | Step 3.2 complete. | PM create writes target track object; non-PM create rejects with `permission_boundary="track.lifecycle_authority"`. | Focused create tests in `tests/test_track_env_tool.py` pass. |
| 3.4 | Implement `track.update_now` in `scripts/env/services/tracks.py` | Support current work state changes without generic workflow machinery. | Any buddy can patch `now.next`, `now.blocker`, `state`, and `health` on a non-archived track. `state` and `health` reject values outside fixed vocabularies. | Step 3.3 complete. | The operation appends an update row of kind `progress` when `state`, `health`, or `now` changes. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py::TrackEnvToolTests::test_all_buddies_can_update_now_on_non_archived_track -q` |
| 3.5 | Implement `track.add_update` in `scripts/env/services/tracks.py` | Add concise shared timeline notes. | Any buddy can add an update with non-empty `summary`, allowed `kind`, and validated artifact refs. Invalid refs reject before mutation. | Step 3.4 complete. | Stored update has generated `upd-` id, `by_buddy`, `summary`, `kind`, normalized refs, and `created_at`. | Focused add-update tests pass. |
| 3.6 | Implement `track.add_material` in `scripts/env/services/tracks.py` | Publish shared material directly to track. | Payload either supplies owned draft `artifact_id` or supplies `title`, `kind`, `label`, `summary`, `content`, and optional `source_refs` to create and publish an artifact. The track gets a material ref; artifact gets `published_to_track` and `publication_role="material"`. Older refs with the same `(kind, label, from_buddy)` become `current=false`. | Step 3.5 complete. | PM PRD publication and Design draft publication both return artifact ids and appear in `track.open.shared_materials`. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py -q` |
| 3.7 | Implement `track.add_proof` in `scripts/env/services/tracks.py` | Publish close proof directly to track. | Payload creates or publishes an artifact with `publication_role="proof"` and appends an exact proof ref to `close_proof`. It also appends a `proof` update. | Step 3.6 complete. | Test buddy can publish smoke proof; `track.open.close_proof` points to the exact proof artifact id. | Focused add-proof and e2e tests pass. |
| 3.8 | Implement `track.archive` in `scripts/env/services/tracks.py` | Enforce archive as hard visibility boundary. | Only PM can set `archived_at`. Repeated archive returns success with `state_changed=false`. `track.list` omits archived tracks. `track.open`, `track.update_now`, `track.add_update`, `track.add_material`, `track.add_proof`, `artifact.get`, and comment target reads reject archived published material. | Step 3.7 complete. | Archive never deletes files and never changes `state` to `archived`. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_comment_env_tool.py -q` |
| 3.9 | Delete old relation functions from `scripts/env/services/tracks.py` | Remove old collaboration machinery. | `join_track_for_active_buddy`, `attach_task_to_track`, `detach_task_from_track`, `_task_buddies`, and `_reject_task_scope` are gone. | Steps 3.1-3.8 complete. | `rg -n "join_track|attach_task|detach_task|track_task|task relation" scripts/env/services/tracks.py` returns no hits. | Run the `rg` command and router tests. |

### Phase 4: Make Task Service Private

| Step | Files or modules | Purpose | Expected behavior | Preconditions | Completion standard | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| 4.1 | Modify `scripts/env/services/tasks.py` response builders | Remove artifact linkage from task payloads. | Task responses include `id`, `buddy`, `title`, `summary`, `status`, `track_id`, `created_at`, and `updated_at`; no artifact ids or slots. | Phase 1 task shape exists. | Task tests assert absence of artifact fields. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py -q` |
| 4.2 | Modify `scripts/env/services/tasks.py` create/update paths | Keep `track_id` as a private hint. | Creating or updating a task with `track_id` validates the track exists and only writes the task file. It does not mutate the track and does not change artifact visibility. | Step 4.1 complete. | Snapshot tests show track JSON unchanged after task create/update. | Focused task-private tests pass. |
| 4.3 | Modify task rejection copy in `scripts/env/services/tasks.py` | Stop teaching `track.join`. | Allowed next actions mention `task.list`, `task.get`, `task.update`, and `track.open`; no response text suggests joining or attaching a task. | Step 4.2 complete. | `rg -n "track\\.join|attach" scripts/env/services/tasks.py` returns no hits. | Run `tests/test_runtime_tool_feedback.py` after rewriting removed relation test in Phase 8. |

### Phase 5: Update Context, Projection, Artifact Selection, Cleanup, And Console

| Step | Files or modules | Purpose | Expected behavior | Preconditions | Completion standard | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| 5.1 | Modify `scripts/env/services/context.py` | Make runtime discovery track-page based. | Context omits archived tracks; candidate tracks include `track_id`, `title`, `outcome`, `state`, `health`, `owner_buddy`, `now`, and `updated_at`; `artifact_summaries` comes from current `shared_materials`; tasks are active-buddy private hints only. | Phases 2-4 complete. | Context contains no `active_buddy_role="track_task"` and no task-derived material rows. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_context_binding_env_tool.py tests/test_env_tool_response_contract.py -q` |
| 5.2 | Modify `scripts/runtime_store/projections.py` | Project shared track pages. | Track projection contains target track fields, `shared_materials`, `updates`, `close_proof`, `comment_ids`, and `missing_artifact_ids`; it does not embed tasks. Task projection is private task shape; artifact projection uses `published_to_track`. | Step 5.1 complete. | Projection contract tests pass and old `standalone_tasks` derivation no longer depends on `track.task_ids`. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_parallel_contracts.py tests/test_console_app_contract.py -q` |
| 5.3 | Modify `framework/contracts/workspace-projection.json` | Update API contract for context panel. | `view_shapes.track.key_order` matches target fields; old `task_ids`, `tasks`, and `missing_task_ids` are absent; `artifact` shape uses `published_to_track`; task shape omits artifact slots. | Step 5.2 complete. | Contract JSON matches projection output. | Projection contract tests pass. |
| 5.4 | Modify `framework/console/app.js` and `tests/test_console_app_contract.py` | Keep console derivation aligned with track page. | `deriveTrackOwnerState` becomes `deriveTrackPageState` and returns `trackId`, `ownerBuddy`, `state`, `health`, `outcome`, `nowNext`, and `nowBlocker`; no task relation text. | Step 5.3 complete. | Node contract test passes. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_console_app_contract.py -q` |
| 5.5 | Modify `scripts/artifact_selection.py` and `tests/test_artifact_selection.py` | Select inputs from shared materials. | Selection consumes `track_artifact_index.shared_materials`; it selects current refs by requested kind and returns `artifact_id`, `kind`, `from_buddy`, and `selection_reason`; no task id in selected inputs. | Step 1.7 complete. | Tests use new index shape and pass. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_selection.py -q` |
| 5.6 | Modify `scripts/env_cleanup.py` and `tests/test_cleanup_system.py` | Remove task-track detach cleanup. | Buddy cleanup deletes active-buddy private tasks and owned artifacts without editing surviving track `shared_materials`; all-data cleanup recreates active object directories. No helper edits `track.task_ids`. | Step 5.2 complete. | Cleanup no longer contains `detach_task_from_track`; stale old track fields are deleted only through all-data cleanup of files, not migrated. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_cleanup_system.py -q` |

### Phase 6: Update Registry, CLI, Runtime Lock Semantics, Manifest, And Skills

| Step | Files or modules | Purpose | Expected behavior | Preconditions | Completion standard | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| 6.1 | Modify `scripts/env/tools/contracts.py` | Register target env-tool actions. | Track action list is exactly `create`, `list`, `open`, `update_now`, `add_material`, `add_update`, `add_proof`, `archive`; artifact actions are exactly `get`, `create_revision`, `update_metadata`; task actions unchanged. Payload fields match target contracts. | Service functions from Phases 2-4 exist. | Router action set matches registry. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py -q` |
| 6.2 | Modify `scripts/env/tools/semantics.py` | Update tool descriptions and action semantics. | Track capability describes shared progress pages; task capability describes private work management; artifact capability describes draft/private and published material/proof states. Removed operations have no semantic rows. | Step 6.1 complete. | `contracts.semantic_contract_errors()` returns `[]`. | Semantic contract tests pass. |
| 6.3 | Modify `scripts/env/tools/dispatch.py` | Wire target handlers only. | Dispatch maps target track/artifact/task actions to service functions and has no removed handlers. | Step 6.1 complete. | `dispatch_handler_actions()` equals registry-derived actions. | Router tests pass. |
| 6.4 | Modify `scripts/env/client.py` | Update skill-facing CLI. | CLI supports `track open`, `track update-now`, `track add-material`, `track add-update`, `track add-proof`; removes `track get`, `track join`, `track attach-task`, `track detach-task`, and `artifact list`. | Dispatch supports target actions. | CLI help shows target operations and rejects removed commands. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py::EnvToolRouterTests::test_cli_exposes_track_page_surface_only -q` |
| 6.5 | Modify `tests/test_runtime_broker.py`; inspect `scripts/runtime_kernel/coordinator.py` | Preserve lock behavior from registry `mutates` values. | Read-only actions `track.list`, `track.open`, `artifact.get`, `task.list`, and `task.get` use read locks; mutating target track actions use write locks. | Step 6.1 complete. | Runtime broker lock tests pass with new action names, and `lock_mode_for_request` still reads action specs from the registry. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerCoordinatorTests -q` |
| 6.6 | Modify `buddyswitch/manifest.toml` and `tests/test_env_manifest_v2.py` | Align permissions with target actions. | PM keeps `track.create` and `track.archive`; all buddies have `track.read`, `track.update_now`, `track.add_material`, `track.add_update`, `track.add_proof`, `task.read`, `task.create`, `task.update`, `task.archive`, `artifact.read`, `artifact.create`, and `artifact.update`. Removed track relation permissions are absent. | Tool registry target actions exist. | Manifest validates and env profile tests pass. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py tests/test_buddy_env_profiles.py -q` |
| 6.7 | Modify `buddyswitch/skills/shared/track-tool/SKILL.md`, `artifact-tool/SKILL.md`, `task-tool/SKILL.md` | Teach the new operational path. | Track skill lists target operations and says shared materials are read through `track.open`; artifact skill says `artifact.get` reads full bodies and publication is through track operations; task skill says tasks are private and optional. | CLI target operations exist. | Runtime skill tests assert exact operations and removed wording absence. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py -q` |
| 6.8 | Modify role skills and role contracts | Remove old collaboration instructions. | `buddyswitch/skills/pm/write-prd/SKILL.md` no longer says Design joins via `track.join`; `framework/contracts/{pm,design,dev,test,market}.md` state direct track material publication/read rules. | Shared skills updated. | Repo residue scan excludes removed terms from active docs. | Repo consistency tests pass. |
| 6.9 | Modify `tools/launcher/assets/buddies/*/AGENTS.md` if generated template is static | Update runtime buddy guidance. | Guidance says `track open --track-id`, not `track get`; no guidance says join or attach tasks for shared material access. | CLI updated. | All buddy AGENTS pass residue scan. | Repo consistency tests pass. |

### Phase 7: Update End-To-End Main Path

| Step | Files or modules | Purpose | Expected behavior | Preconditions | Completion standard | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| 7.1 | Modify `tests/test_env_layer_end_to_end.py` | Replace old flow with memo main path. | PM creates track, PM adds PRD material, Design opens and reads PRD, Design adds draft material, Dev opens and reads both, Test adds smoke proof, PM sets state done. No task operation is required. | Phases 1-6 complete. | Test asserts no `task_id`, `track_task`, `join`, `attach`, or `detach` in the serialized success path. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py -q` |
| 7.2 | Modify `tests/test_turn_integration.py` | Keep integration path explicit-id and direct. | Cross-buddy flow uses `track.open`, `track.add_material`, and `artifact.get`; no `track.join`. | Step 7.1 complete. | Test name and assertions reflect direct material intake. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_integration.py -q` |
| 7.3 | Modify `tests/test_buddybox_env_tool.py` | Ensure buddybox promotion uses track material publication. | Private buddybox content becomes shared only through `track.add_material` or `track.add_proof`, not `artifact.create_revision` with task id. | Track publication works. | Tests assert no product object is created by buddybox write and publication creates direct track material. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddybox_env_tool.py -q` |

### Phase 8: Delete Or Rewrite Old Tests

| Step | Files or modules | Purpose | Expected behavior | Preconditions | Completion standard | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| 8.1 | Modify `tests/test_runtime_tool_feedback.py` | Remove task-relation recovery contract. | Replace `track_relation_scope_rejections` with rejection tests for archived track mutations, invalid material refs, and non-PM create/archive. | Target services implemented. | No test expects `track.join`, `attach_task`, or `detach_task`. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_tool_feedback.py -q` |
| 8.2 | Modify `tests/test_track_env_tool.py` | Remove old consistency test that joins before reading. | Rewritten test compares `track.open.shared_materials` with `artifact.get` readability directly. | Phases 2-3 complete. | No test dispatches `track.join`. | `rg -n "track.*join|attach_task|detach_task" tests/test_track_env_tool.py` returns no hits. |
| 8.3 | Modify `tests/test_artifact_env_tool.py` | Remove active-task-relation read tests. | Replace with direct published-material read tests, draft privacy tests, archived published artifact rejection, and superseded material rejection. | Phase 2 complete. | No artifact test creates a foreign task solely to grant read access. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py -q` |
| 8.4 | Modify `tests/test_env_store_v2.py` | Replace task binding invariant. | Old test asserting task creation registers in `track.task_ids` is deleted. New test asserts task `track_id` hint leaves track JSON unchanged. | Phase 1 complete. | Env-store suite passes. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_store_v2.py -q` |
| 8.5 | Modify `tests/test_repo_consistency.py` | Add active-surface residue scan. | Scan active code/docs/tests for `track.join`, `attach_task`, `detach_task`, `track.task_ids`, `artifact.task_id`, `artifact_slots`, `readable_by_current_buddy`, `track_task`; allow dated `docs/memo/**`, `docs/spec/**`, and artifact kind `design-handoff`. | Active docs updated. | Residue scan passes. | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q` |

## 10. Deletion And Replacement Safety Checks

- Delete track relation service code directly: no compatibility modules or alias handlers.
- Reject old object fields at validation boundaries: `track.task_ids`, `track.status`, `track.summary`, `artifact.task_id`, `task.artifact_ids`, and `task.artifact_slots`.
- Keep `design-handoff` as an artifact kind because it names a design deliverable, not a handoff runtime object.
- Use exact residue scans after implementation:

```bash
rg -n "track\\.join|attach_task|detach_task|attach-task|detach-task|track_task|readable_by_current_buddy" scripts buddyswitch tools framework tests README.md AGENTS.md
rg -n "track\\.task_ids|artifact\\.task_id|artifact_slots|task_ids" scripts buddyswitch tools framework tests README.md AGENTS.md
```

Expected result: no hits except scan tests that intentionally contain the pattern and dated docs excluded by test filters.

## 11. Final Verification Commands

Focused suites:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_store_v2.py tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_task_env_tool.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_turn_integration.py tests/test_comment_env_tool.py -q
```

Broader runtime verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_task_env_tool.py tests/test_comment_env_tool.py tests/test_context_binding_env_tool.py tests/test_env_tool_response_contract.py tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py tests/test_runtime_broker.py tests/test_runtime_tool_feedback.py tests/test_env_layer_end_to_end.py tests/test_turn_integration.py tests/test_artifact_selection.py tests/test_cleanup_system.py tests/test_parallel_contracts.py tests/test_console_app_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
python3 scripts/turn_runtime.py status
python3 scripts/env/client.py track --help
python3 scripts/env/client.py artifact --help
```

## 12. Remaining Decisions

No implementation-blocking decision remains. This plan fixes the V1 authority rule as: PM-only create/archive; all buddies may update now-state and add materials, updates, and proof on non-archived tracks.
