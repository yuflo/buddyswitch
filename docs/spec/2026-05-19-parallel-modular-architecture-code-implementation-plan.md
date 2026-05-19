# Parallel Modular Architecture Code Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to execute this plan with one sub-agent per work package. Steps use checkbox (`- [ ]`) syntax for tracking. Keep each sub-agent inside its declared write set.

**Goal:** Complete the BuddySwitch thin-layer runtime architecture so tool contracts, skills, services, domain operations, object repositories, and JSON/file storage can evolve in parallel without hidden cross-object coupling.

**Architecture:** Runtime code follows `SKILL -> Tool Contract -> Service -> Domain Ops -> Object Repo -> JSON / Files`. Tool contracts own discoverable payload/action semantics, services own request/response adaptation, domain ops own business rules and cross-object coordination, and object repos own only one object type's storage. The implementation uses concrete per-object modules and targeted boundary tests, not a workflow engine, plugin system, event bus, generic object framework, or long-lived compatibility path.

**Tech Stack:** Python env.tool runtime, broker-routed `env.tool`, concrete service/domain/repo modules under `scripts/env/**`, runtime JSON/files under `buddyswitch/objects/**` and `buddyswitch/local/buddybox/**`, `pytest`/`unittest`, runtime skills under `buddyswitch/skills/**`, role contracts under `framework/contracts/**`.

---

## Source Inputs

Read these before executing any work package:

- `AGENTS.md`
- `docs/memo/buddyswitch-parallel-modular-architecture.md`
- Existing plans in `docs/spec/*implementation-plan.md` and `docs/spec/*test-plan.md`
- Tool contract/runtime files:
  - `scripts/env/tools/contracts.py`
  - `scripts/env/tools/semantics.py`
  - `scripts/env/tools/dispatch.py`
  - `scripts/env/tools/router.py`
  - `scripts/env/tools/responses.py`
  - `scripts/env/client.py`
  - `scripts/env/services/context.py`
  - `scripts/turn_runtime.py`
- Current object services and storage:
  - `scripts/env_store.py`
  - `scripts/env/services/messages.py`
  - `scripts/env/services/comments.py`
  - `scripts/env/services/buddybox.py`
  - `scripts/env/services/artifacts.py`
  - `scripts/env/services/tracks.py`
  - `scripts/env/services/tasks.py`
  - `scripts/env/services/artifact_visibility.py`
  - `scripts/env/services/source_refs.py`
- Runtime projection and launcher surfaces:
  - `scripts/workspace_data.py`
  - `scripts/runtime_store/projections.py`
  - `scripts/runtime_kernel/dispatcher.py`
  - `scripts/env_cleanup.py`
  - `tools/launcher/workspace.sh`
  - `buddyswitch/manifest.toml`
  - `buddyswitch/env-profiles/*.json`
- Runtime guidance surfaces:
  - `buddyswitch/skills/**/*.md`
  - `framework/contracts/*.md`
  - `tools/launcher/assets/buddies/*/AGENTS.md`
- Existing focused tests:
  - `tests/test_env_tool_semantic_contract.py`
  - `tests/test_env_tool_router.py`
  - `tests/test_env_tool_response_contract.py`
  - `tests/test_runtime_tool_feedback.py`
  - `tests/test_repo_consistency.py`
  - `tests/test_env_layer_boundaries.py`
  - `tests/test_parallel_contracts.py`
  - `tests/test_message_env_tool.py`
  - `tests/test_comment_env_tool.py`
  - `tests/test_buddybox_env_tool.py`
  - `tests/test_artifact_env_tool.py`
  - `tests/test_track_env_tool.py`
  - `tests/test_task_env_tool.py`
  - `tests/test_env_layer_end_to_end.py`
  - `tests/test_turn_integration.py`

## Current Bottleneck

BuddySwitch already has useful runtime objects and env tools, but the implementation is still too coupled for fast parallel work:

- `scripts/env_store.py` is a shared mutation hotspot for tracks, tasks, artifacts, messages, comments, and buddybox path helpers.
- Services call storage helpers directly, so object-specific business rules and cross-object rules are not consistently separated.
- Tool registry, semantics, dispatch, CLI, context catalog, skills, and tests can drift because they are not guarded by a single contract-alignment check.
- `comment` contains product discussion behavior but must not mutate target objects.
- `buddybox` is active-buddy private file state and must never become product-readable object state by accident.
- `track/artifact` publication is intentionally coupled but must have one domain entry point.
- `task` may reference a track as private work context but must not own artifact publication or shared track state.

The shortest complete repair is to add enforcement tests first, then replace the shared object-store hotspot with concrete per-object repos and the few domain modules that coordinate across repos.

## Target Runtime Boundaries

### Layer Ownership

| Layer | Owns | Must not own |
| --- | --- | --- |
| `SKILL` | When to use tools, workflow judgement, role-specific process | Payload schema copies, dispatch tables, object storage shape |
| `Tool Contract` | Tool/action names, payload fields, permission labels, catalog, operation semantics | JSON object internals, cross-object mutation decisions |
| `Service` | Env.tool argument validation, active-buddy context adaptation, structured responses | Direct JSON/file writes, sibling object mutation rules |
| `Domain Ops` | Business rules, permission/readability decisions, cross-object coordination | Generic workflow engine, plugin/event framework |
| `Object Repo` | One object type's schema, path, normalize, load/save/list | Importing sibling repos, mutating sibling objects |
| `JSON / Files` | Durable state format | Runtime behavior decisions |

### Object Ownership

| Object | Owns | Allowed coupling | Must not do |
| --- | --- | --- | --- |
| `message` | Direct send, active-buddy inbox listing, reply scope | Manifest buddy ids | Mutate track/task/artifact/comment |
| `comment` | Comment shape, thread rows, comment status if active, target-scoped listing | Domain read check for readable track/artifact target | Mutate target object state |
| `buddybox` | Active-buddy private local files by `logical_name` | `source_refs` may cite `logical_name` provenance | Become product-readable state |
| `artifact` | Draft/revision/body/readability metadata | Published refs are read by track views | Directly edit track shared refs |
| `track` | Shared collaboration page, current material refs, proof refs, updates | Publication domain coordinates artifact state | Own artifact body/schema |
| `task` | Active-buddy private work item state and optional `track_id` context | Verify referenced track exists | Publish artifacts or mutate shared track state |

### Final File Structure

Create concrete repo/domain modules. Do not create a generic object framework.

- Create: `scripts/env/repos/__init__.py`
- Create: `scripts/env/repos/runtime_files.py`
  - Shared runtime root resolution, JSON read/write, ID validation, timestamps, and directory creation.
  - Does not know object relationships.
- Create: `scripts/env/repos/tracks.py`
  - Track schema, normalize, load/save/list/create/update/archive.
  - Does not import artifact/task/comment/message/buddybox repos.
- Create: `scripts/env/repos/artifacts.py`
  - Artifact schema, normalize, load/save/list/create draft/update/delete.
  - Does not import track/task/comment/message/buddybox repos.
- Create: `scripts/env/repos/tasks.py`
  - Task schema, normalize, load/save/list/create/update/archive.
  - Does not import artifact/track/comment/message/buddybox repos.
- Create: `scripts/env/repos/messages.py`
  - Message schema, normalize, load/save/list/create.
  - Does not import other object repos.
- Create: `scripts/env/repos/comments.py`
  - Comment schema, normalize, load/save/list/create/thread-status update.
  - Does not import target object repos.
- Create: `scripts/env/repos/buddybox_files.py`
  - Active-buddy private file root, logical-name normalization, list/read/write/delete.
  - Does not import product object repos.
- Create: `scripts/env/domain/__init__.py`
- Create: `scripts/env/domain/publication.py`
  - The only module allowed to mutate both track and artifact state in one operation.
- Create: `scripts/env/domain/artifact_visibility.py`
  - Artifact readability/currentness decisions using read-only track/artifact repo calls.
- Create: `scripts/env/domain/comment_targets.py`
  - Comment target readability checks for track/artifact targets.
- Create: `scripts/env/domain/messages.py`
  - Message send/list validation that needs manifest buddy ids and reply-scope rules.
- Create: `scripts/env/domain/tasks.py`
  - Task business rules, including `track_id` existence as private work context only.
- Modify: `scripts/env/services/*.py`
  - Services call domain modules or single-object repos and return structured env.tool responses.
- Modify: `scripts/env/tools/contracts.py`
- Modify: `scripts/env/tools/semantics.py`
- Modify: `scripts/env/tools/dispatch.py`
- Modify: `scripts/env/client.py`
- Modify: `scripts/env/services/context.py`
- Modify: `scripts/turn_runtime.py`
- Modify: `scripts/workspace_data.py`
- Modify: `scripts/runtime_store/projections.py`
- Modify: `scripts/runtime_kernel/dispatcher.py`
- Modify: `scripts/env_cleanup.py`
- Modify: focused tests under `tests/**`.

`scripts/env_store.py` is removed as an active object API by the final task. Acceptable final residue is a small runtime-root compatibility module only if launch/test infrastructure still needs it for `ROOT`, runtime root override, and directory setup. It must not export object read/write/list/create/update/delete functions.

## Non-Goals

- Do not add workflow engines, plugin systems, event buses, rule engines, generic object frameworks, or new service boundaries.
- Do not keep old and new object storage APIs as active dual paths.
- Do not fix runtime behavior by expanding `AGENTS.md` or by copying payload schemas into skills.
- Do not modify `docs/**` during implementation or verification after this plan/test-plan generation work.
- Do not add release/rollback compatibility unless a concrete external contract requires it.

## Parallel Execution Rules

1. Contract/Boundary Agent exclusively owns shared registry and discovery files:
   - `scripts/env/tools/contracts.py`
   - `scripts/env/tools/semantics.py`
   - `scripts/env/tools/dispatch.py`
   - `scripts/env/client.py`
   - `scripts/env/services/context.py`
   - `scripts/turn_runtime.py`
   Other agents must not edit these files. They hand off exact action/service names and payload fields to the Contract/Boundary Agent.
2. Foundation Agent exclusively owns common repo/domain scaffolding:
   - `scripts/env/repos/runtime_files.py`
   - `scripts/env/repos/__init__.py`
   - `scripts/env/domain/__init__.py`
   - root override helpers currently used from `env_store.py`
3. Object agents own only their object files, focused tests, and object-specific repo/domain/service code.
4. TrackArtifact Publication Agent owns cross-object track/artifact mutation. Artifact and track repos must not import each other.
5. Skill Surface Agent owns runtime skills and role contracts. It must not edit Python runtime.
6. Runtime Integration Agent owns projection, cleanup, launcher/runtime integration, and end-to-end tests after object agents land.
7. Final Review Agent owns static boundary tests and residue removal. It must not rewrite object behavior except to remove verified dead paths.

## Agent Work Packages

### Agent 1: Contract/Boundary Agent

**Goal:** Make the runtime-visible tool surface a single source of truth and add boundary tests before object agents refactor internals.

**May modify:**

- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/client.py`
- `scripts/env/services/context.py`
- `scripts/turn_runtime.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_tool_router.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_runtime_tool_feedback.py`
- `tests/test_repo_consistency.py`
- `tests/test_env_layer_boundaries.py`

**Must not modify:**

- Object services, repos, domains, and object-specific tests owned by other agents.
- `docs/**`.

**Depends on:** Source reads only. This agent starts first.

**Steps:**

- [ ] Add a contract-alignment test that builds sets from `TOOL_REGISTRY`, `semantics.operation_semantics`, `dispatch.dispatch_handler_actions()`, CLI operation maps, and `context.get` catalog. Assert every active tool action appears in all runtime-visible surfaces with the same action name.
- [ ] Add a boundary static test that scans `scripts/env/services/**` for direct `_write_json`, `.write_text`, `objects/`, and repo path writes. Allow only `scripts/env/repos/**` and `scripts/env/services/buddybox.py` until the Buddybox Agent migrates file writes.
- [ ] Add a repo static test that scans `scripts/env/repos/*.py` imports. Assert object repo files do not import sibling object repos.
- [ ] Add a domain static test that permits cross-object imports only from `scripts/env/domain/publication.py`, `scripts/env/domain/comment_targets.py`, and `scripts/env/domain/artifact_visibility.py`.
- [ ] Add a skills static test that scans `buddyswitch/skills`, `framework/contracts`, and `tools/launcher/assets/buddies` for copied JSON payload schema blocks. Allow tool names and short operation examples; reject copied `payload_fields` lists and inline contract tables that duplicate `contracts.py`.
- [ ] Keep `contracts.py` and `semantics.py` aligned with the current active actions:
  - `task.create/list/get/update/archive`
  - `track.create/list/open/update_now/add_material/add_update/add_proof/archive`
  - `artifact.get/create_revision/update_metadata`
  - `buddybox.desc/list/read/write/delete`
  - `context.get/summarize/list_sources`
  - `evidence.issue_browser/approve_downgrade`
  - `search.status/request/open_browser`
  - `message.send/list`
  - `comment.add/list`
- [ ] If `comment.resolve` or `comment.reopen` remains inactive, assert the router rejects those actions and remove them from runtime-visible semantics. If product scope activates them later, they must be added by a separate contract-first task owned by this agent.
- [ ] Update response contract tests so each write action must expose `state_changed`, `durability`, `state_changes`, `allowed_next_action_options`, and actionable rejection fields.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py tests/test_env_tool_router.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py tests/test_repo_consistency.py tests/test_env_layer_boundaries.py -q
```

**Handoff condition:** New boundary tests fail only where object agents have not migrated code yet. Contract/dispatch/semantics/client/context mismatches are fixed before other agents integrate.

### Agent 2: Foundation Repo Agent

**Goal:** Extract the minimal shared runtime file substrate needed by per-object repos without introducing a generic object framework.

**May modify:**

- `scripts/env/repos/__init__.py`
- `scripts/env/repos/runtime_files.py`
- `tests/runtime_root_test_helper.py`
- `tests/test_env_store_v2.py`
- `tests/test_env_layer_boundaries.py`

**Must not modify:**

- Tool registry, semantics, dispatch, services, object repos beyond scaffolding, and `docs/**`.

**Depends on:** Contract/Boundary Agent boundary test names.

**Steps:**

- [ ] Move runtime root selection, directory creation, timestamp, ID validation, JSON read/write, and object directory constants into `scripts/env/repos/runtime_files.py`.
- [ ] Keep object-specific validation out of `runtime_files.py`.
- [ ] Update `tests/runtime_root_test_helper.py` to set/reset runtime root through `runtime_files`.
- [ ] Add tests proving runtime root override applies to all repo directories and never writes to the source checkout during runtime workspace tests.
- [ ] Leave `env_store.py` temporarily importing root helpers from `runtime_files.py` so existing object agents can migrate one object at a time.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_store_v2.py tests/test_env_layer_boundaries.py -q
```

**Handoff condition:** Runtime root override tests pass and object agents can import `scripts.env.repos.runtime_files` without touching each other's files.

### Agent 3: Message Agent

**Goal:** Move message behavior behind a concrete message domain/repo boundary and prove it cannot affect other objects.

**May modify:**

- `scripts/env/repos/messages.py`
- `scripts/env/domain/messages.py`
- `scripts/env/services/messages.py`
- `tests/test_message_env_tool.py`
- message-related rows in `tests/test_env_layer_boundaries.py` only if coordinated with Agent 1.

**Must not modify:**

- `scripts/env/tools/**`
- Track/task/artifact/comment/buddybox services or repos
- `docs/**`

**Depends on:** Foundation Repo Agent for `runtime_files.py`.

**Steps:**

- [ ] Move message schema validation, `list_messages`, `get_message`, `save_message`, and `create_message` from `env_store.py` into `scripts/env/repos/messages.py`.
- [ ] Implement `scripts/env/domain/messages.py` for manifest buddy validation, self-send rejection, reply-to existence, visible conversation-pair checks, inbox filtering, and sender filter rules.
- [ ] Update `scripts/env/services/messages.py` so it only validates env.tool payload shape, calls `domain.messages`, and formats tool responses.
- [ ] Remove message object helpers from `env_store.py` after all imports move to the new repo.
- [ ] Strengthen `tests/test_message_env_tool.py` to snapshot `buddyswitch/objects/{tracks,tasks,artifacts,comments}` before rejected and successful message calls and assert no changes.
- [ ] Assert message list is read-only and never creates status/read-receipt fields.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_message_env_tool.py tests/test_env_layer_boundaries.py -q
```

**Handoff condition:** Message service no longer imports `env_store`, message repo imports no sibling repos, and message tests pass independently.

### Agent 4: Comment Agent

**Goal:** Move comment behavior behind comment repo/domain modules and prove comments attach to readable targets without mutating target objects.

**May modify:**

- `scripts/env/repos/comments.py`
- `scripts/env/domain/comment_targets.py`
- `scripts/env/services/comments.py`
- `tests/test_comment_env_tool.py`
- comment-related rows in `tests/test_env_layer_boundaries.py` only if coordinated with Agent 1.

**Must not modify:**

- `scripts/env/tools/**`
- Track/artifact repo mutation functions
- Message/task/buddybox files
- `docs/**`

**Depends on:** Foundation Repo Agent. TrackArtifact Publication Agent may later update read helpers, but this agent must use a narrow read-decision interface rather than target mutation.

**Steps:**

- [ ] Move comment schema validation, `list_comments`, `get_comment`, `save_comment`, `create_comment`, `comments_for_target`, and thread status mutation from `env_store.py` into `scripts/env/repos/comments.py`.
- [ ] Implement `scripts/env/domain/comment_targets.py` to check:
  - track target exists and is non-archived
  - artifact target is readable through `domain.artifact_visibility`
  - unsupported target types reject before any comment write
- [ ] Update `scripts/env/services/comments.py` so `comment.add` and `comment.list` use the domain module and comment repo.
- [ ] Keep target object JSON unchanged when adding/listing comments. Comments are discovered by `comments_for_target`, not by appending IDs to track/artifact objects unless an already documented projection contract requires derived IDs.
- [ ] If current code supports `artifact_section`, `mentions`, or status filtering, either keep them fully inside the comment domain/repo contract with tests or remove them from active service payloads. The tool registry and service must agree.
- [ ] Remove inactive `comment.resolve` and `comment.reopen` service paths unless Agent 1 explicitly activates them in the contract.
- [ ] Strengthen tests to snapshot target track/artifact JSON before `comment.add` and assert unchanged after success and rejection.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_comment_env_tool.py tests/test_artifact_env_tool.py tests/test_track_env_tool.py tests/test_env_layer_boundaries.py -q
```

**Handoff condition:** Comment service no longer imports `env_store`, comment repo imports no target repos, and target JSON no-mutation tests pass.

### Agent 5: Buddybox Agent

**Goal:** Make buddybox a private file capability with no product object state leakage.

**May modify:**

- `scripts/env/repos/buddybox_files.py`
- `scripts/env/services/buddybox.py`
- `scripts/env/services/source_refs.py`
- `tests/test_buddybox_env_tool.py`
- `tests/test_buddy_env_profiles.py`
- `tests/test_env_layer_boundaries.py` buddybox allowlist rows only if coordinated with Agent 1.

**Must not modify:**

- Product object repos
- Track/artifact publication code
- Tool registry/shared semantics except through Agent 1
- `docs/**`

**Depends on:** Foundation Repo Agent.

**Steps:**

- [ ] Move buddybox logical-name normalization, active-buddy root resolution, path containment checks, list/read/write/delete, and file summaries into `scripts/env/repos/buddybox_files.py`.
- [ ] Keep `source_refs` support limited to provenance references to `logical_name`; it must not make buddybox files product-readable.
- [ ] Update `scripts/env/services/buddybox.py` so it calls `repos.buddybox_files` and formats response options.
- [ ] Add tests that another buddy cannot read/list/delete/write the active buddy's buddybox files by prefix, traversal, symlink, or absolute path.
- [ ] Add tests that buddybox write/delete does not create or alter `buddyswitch/objects/**`.
- [ ] Add tests that `buddybox.desc` reports `product_readable=false`, `cross_buddy_readable=false`, and `mutates_product_state=false`.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddybox_env_tool.py tests/test_buddy_env_profiles.py tests/test_env_layer_boundaries.py -q
```

**Handoff condition:** Buddybox service no longer imports `env_store`, buddybox repo imports no product object repos, and private file boundary tests pass.

### Agent 6: TrackArtifact Publication Agent

**Goal:** Make track/artifact publication the only intentional cross-object runtime mutation and isolate it in one domain module.

**May modify:**

- `scripts/env/repos/tracks.py`
- `scripts/env/repos/artifacts.py`
- `scripts/env/domain/publication.py`
- `scripts/env/domain/artifact_visibility.py`
- `scripts/env/services/tracks.py`
- `scripts/env/services/artifacts.py`
- `scripts/env/services/source_refs.py`
- `scripts/artifact_selection.py`
- `tests/test_track_env_tool.py`
- `tests/test_artifact_env_tool.py`
- `tests/test_env_layer_end_to_end.py`
- publication-related rows in `tests/test_env_layer_boundaries.py` only if coordinated with Agent 1.

**Must not modify:**

- Message/comment/task/buddybox files
- `scripts/env/tools/**` except through Agent 1
- `docs/**`

**Depends on:** Foundation Repo Agent. Coordinate with Comment Agent on `domain.artifact_visibility`.

**Steps:**

- [ ] Move track schema validation, track load/save/list/create/update/archive, and update append helpers from `env_store.py` into `scripts/env/repos/tracks.py`.
- [ ] Move artifact schema validation, artifact load/save/list/create draft/update/delete, revision-chain reads, and source-ref normalization hooks from `env_store.py` into `scripts/env/repos/artifacts.py`.
- [ ] Implement `scripts/env/domain/publication.py` as the only module that imports both `repos.tracks` and `repos.artifacts`.
- [ ] Move `publish_track_material` and `publish_track_proof` into `domain.publication`.
- [ ] Enforce the only active publication path:
  - `artifact.create_revision` creates active-buddy draft/revision content
  - `track.add_material` publishes an existing draft artifact as current material
  - `track.add_proof` publishes an existing draft artifact as close proof
  - `track.open` returns current refs
  - `artifact.get` returns full readable body
- [ ] Reject `artifact.create_revision` inputs that try to directly set `status` or `published_to_track` before mutation.
- [ ] Ensure `artifact.create_revision` never changes track JSON and never demotes current published material/proof.
- [ ] Ensure `track.add_material` and `track.add_proof` atomically update both artifact JSON and track JSON, or reject with no mutation.
- [ ] Update `scripts/env/domain/artifact_visibility.py` so it uses read-only repo calls and exposes owner draft readability, current material, proof, historical publication, and archived-track rejection.
- [ ] Remove direct track mutation from artifact repo and direct artifact mutation from track repo.
- [ ] Update track/artifact services to call repo or publication domain only.
- [ ] Remove track/artifact object helpers from `env_store.py` after imports move.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py tests/test_track_env_tool.py tests/test_env_layer_end_to_end.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py tests/test_env_layer_boundaries.py -q
```

**Handoff condition:** Track repo and artifact repo do not import each other, only `domain.publication` writes both objects, and publication tests pass.

### Agent 7: Task Boundary Agent

**Goal:** Keep task as active-buddy private work state with optional track context, not a publication or shared collaboration authority.

**May modify:**

- `scripts/env/repos/tasks.py`
- `scripts/env/domain/tasks.py`
- `scripts/env/services/tasks.py`
- `tests/test_task_env_tool.py`
- `tests/test_task_management_skill_architecture.py`
- `tests/test_repo_consistency.py` task boundary assertions only if coordinated with Agent 1.

**Must not modify:**

- Track/artifact publication code
- Message/comment/buddybox files
- `scripts/env/tools/**` except through Agent 1
- `docs/**`

**Depends on:** Foundation Repo Agent. Track repo read function must be available for `track_id` existence checks.

**Steps:**

- [ ] Move task schema validation, `list_tasks`, `get_task`, `save_task`, `create_task`, `update_task`, and archive behavior into `scripts/env/repos/tasks.py`.
- [ ] Implement `scripts/env/domain/tasks.py` for active-buddy ownership, status validation, and optional `track_id` existence check.
- [ ] Update `scripts/env/services/tasks.py` to call `domain.tasks`.
- [ ] Reject `artifact_id`, `artifact_ids`, `published_to_track`, `shared_materials`, `close_proof`, and publication-style fields in task payloads.
- [ ] Add tests that task create/update with `track_id` does not mutate track JSON.
- [ ] Add static scan tests that task repo/service/domain do not import artifact repo or publication domain.
- [ ] Remove task object helpers from `env_store.py` after imports move.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_task_env_tool.py tests/test_task_management_skill_architecture.py tests/test_env_layer_boundaries.py tests/test_repo_consistency.py -q
```

**Handoff condition:** Task service no longer imports `env_store`, task repo imports no sibling repos, and task boundary tests pass.

### Agent 8: Skill Surface Agent

**Goal:** Keep skills and role contracts useful while preventing them from becoming runtime schema mirrors.

**May modify:**

- `buddyswitch/skills/**/*.md`
- `framework/contracts/*.md`
- `tools/launcher/assets/buddies/*/AGENTS.md`
- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py` skill-scan assertions only if coordinated with Agent 1.

**Must not modify:**

- Python runtime files
- `docs/**`

**Depends on:** Agent 1's skill-schema-copy test names and active action list.

**Steps:**

- [ ] Replace copied payload tables or JSON schema blocks in skills/contracts with guidance that points agents to runtime-discoverable catalog/semantics through `context.get`, `context.summarize`, and env tool help.
- [ ] Keep workflow judgement in skills:
  - message is direct buddy-to-buddy communication
  - comment is object-level discussion on readable tracks/artifacts
  - buddybox is private file work
  - artifact drafts become shared only through track publication
  - tasks are private work items, not publication state
- [ ] Keep buddy-specific AGENTS files short and role-focused. Do not add runtime contract prose mirrors.
- [ ] Ensure examples use active action paths and do not teach retired publication routes.
- [ ] Add skill tests that assert active skills mention discovery through runtime catalog/semantics and do not copy `payload_fields` tables.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

**Handoff condition:** Skills describe when to use tools, runtime contract is discovered from code, and no Python files changed by this agent.

### Agent 9: Runtime Integration Agent

**Goal:** Update runtime projections, cleanup, launcher context, and end-to-end tests to use the new repo/domain modules.

**May modify:**

- `scripts/workspace_data.py`
- `scripts/runtime_store/projections.py`
- `scripts/runtime_kernel/dispatcher.py`
- `scripts/env_cleanup.py`
- `tools/launcher/workspace.sh`
- `tests/test_parallel_contracts.py`
- `tests/test_cleanup_system.py`
- `tests/test_runless_runtime_contract.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_env_layer_end_to_end.py`
- `tests/test_turn_integration.py`

**Must not modify:**

- Object services/repos/domains except for import-name fixes coordinated with owning agents
- Tool registry/semantics/dispatch except through Agent 1
- `docs/**`

**Depends on:** Object agents have migrated their services and repos.

**Steps:**

- [ ] Update workspace projection to read tracks, tasks, artifacts, and derived comment summaries through repos or domain read helpers.
- [ ] Keep comments out of top-level workspace projection unless an existing runtime contract explicitly exposes derived comment ids.
- [ ] Update cleanup code to delete objects through each object repo and private files through buddybox repo.
- [ ] Update runtime dispatcher/context paths away from `env_store`.
- [ ] Add an end-to-end test that creates track, artifact draft, material publication, message, comment, buddybox private file, and task context, then verifies each object boundary remains intact.
- [ ] Add context tests proving tool catalog and operation semantics are complete enough for host choice without reading skills.
- [ ] Add cleanup tests proving cleanup removes object/private state through the correct repo without crossing object boundaries.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_parallel_contracts.py tests/test_cleanup_system.py tests/test_runless_runtime_contract.py tests/test_context_binding_env_tool.py tests/test_env_layer_end_to_end.py tests/test_turn_integration.py -q
```

**Handoff condition:** Runtime integration files no longer import object APIs from `env_store.py`, projections match contracts, and end-to-end tests pass.

### Agent 10: Final Review Agent

**Goal:** Remove active legacy object-store paths, enforce boundaries, and run the complete verification loop.

**May modify:**

- `scripts/env_store.py`
- Boundary/residue tests owned by Agent 1 after coordination
- Import fixes required to remove `env_store` object APIs

**Must not modify:**

- Object behavior unless a failing boundary test identifies a direct violation
- `docs/**`

**Depends on:** Agents 1-9 complete.

**Steps:**

- [ ] Run `rg -n "import env_store|from env_store import" scripts tests tools framework buddyswitch` and migrate remaining imports to concrete repos/domain modules.
- [ ] Reduce `scripts/env_store.py` to allowed runtime-root compatibility exports or delete it if no imports remain.
- [ ] Run static boundary tests and fix every disallowed import/write path.
- [ ] Run residue scans for retired routes:
  - schema copies in skills
  - service direct JSON writes
  - object repo sibling imports
  - direct artifact publication fields as active inputs
  - task publication fields
  - buddybox product-readable claims
- [ ] Run focused object tests independently to prove message/comment/buddybox do not need track/artifact/task test setup.
- [ ] Run broader relevant test suite.

**Focused verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_layer_boundaries.py tests/test_repo_consistency.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_router.py -q
```

**Broad verification:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py tests/test_task_env_tool.py tests/test_artifact_env_tool.py tests/test_track_env_tool.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_router.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_env_layer_boundaries.py tests/test_parallel_contracts.py tests/test_cleanup_system.py tests/test_runless_runtime_contract.py tests/test_context_binding_env_tool.py tests/test_env_layer_end_to_end.py tests/test_turn_integration.py -q
```

**Handoff condition:** No active object API remains in `env_store.py`, all boundary tests pass, focused object suites pass independently, and broader verification passes.

## Conflict Avoidance Summary

| Agent | Exclusive write set | Shared-file rule |
| --- | --- | --- |
| Contract/Boundary | `scripts/env/tools/**`, context catalog, semantic/router tests | Other agents submit action metadata, do not edit shared registry |
| Foundation Repo | `scripts/env/repos/runtime_files.py`, repo package init, root override tests | Object agents import only after this lands |
| Message | message repo/domain/service/tests | No shared registry edits |
| Comment | comment repo/domain/service/tests | Uses read helpers, never target mutation |
| Buddybox | buddybox file repo/service/tests | No product object repo edits |
| TrackArtifact | track/artifact repos, publication/visibility domains, related services/tests | Only owner of cross-object publication |
| Task | task repo/domain/service/tests | No publication code edits |
| Skill Surface | skills/contracts/buddy AGENTS and skill tests | No Python runtime edits |
| Runtime Integration | projection/cleanup/launcher/end-to-end tests | Import fixes only after object owners land |
| Final Review | residue removal and boundary enforcement | Behavior fixes only when required by boundary failure |

## Definition of Done

- Tool registry, semantics, dispatch, CLI, context catalog, and runtime feedback describe the same active action set.
- Skills and role contracts teach workflow judgement without copying runtime payload schemas.
- Services no longer write JSON/files directly and no longer import the old object-store monolith for object operations.
- Object repos do not import sibling object repos.
- Cross-object rules exist only in named domain modules.
- `message`, `comment`, and `buddybox` focused tests run independently from track/artifact/task tests.
- `track/artifact` publication has one domain entry point.
- `task` has no artifact publication or shared track mutation role.
- Buddybox state remains active-buddy private and instance-local.
- Runtime projection, cleanup, launcher context, and env.tool broker paths use the new boundaries.
- Existing runtime contract tests continue to pass.
- No implementation or test step requires modifying `docs/**`.
