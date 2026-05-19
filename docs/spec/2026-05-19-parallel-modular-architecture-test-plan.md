# Parallel Modular Architecture Test Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` when implementing this plan. Tests must be written from the functional requirements below before code changes for each boundary.

**Goal:** Prove BuddySwitch has a thin, enforceable runtime architecture that supports parallel module development without schema drift, hidden cross-object writes, private-file leakage, or multiple publication paths.

**Architecture:** Tests combine static boundary scans, runtime-visible contract checks, focused env.tool integration tests, persisted JSON/file assertions, no-mutation rejection checks, and one end-to-end runtime path. Test design starts from product/runtime requirements and collaboration risks, not from existing helper internals.

**Tech Stack:** `pytest`, Python `unittest`, broker-routed `env.tool`, `RuntimeWorkspaceTestMixin`, temporary runtime roots, static `rg`/AST checks, persisted runtime state under temporary `buddyswitch/objects/**` and `buddyswitch/local/buddybox/**`.

---

## Test Scope

In scope:

- Runtime-visible tool contract alignment.
- Service/domain/repo/storage layer boundaries.
- Per-object ownership boundaries for `message`, `comment`, `buddybox`, `artifact`, `track`, and `task`.
- `track/artifact` publication as the only intentional cross-object mutation.
- Skill and role contract behavior at the level of workflow guidance, without copying runtime schemas.
- End-to-end env.tool behavior through the broker.
- Runtime projection, cleanup, and context catalog behavior after repo split.

Out of scope:

- Tests that scan or require changes under `docs/**`.
- Tests that pass by checking only `ok=true`, action name presence, or loose string inclusion.
- Tests that encode private implementation helper names instead of runtime-visible behavior or architectural boundaries.

## Requirements Model

R1. The active runtime path follows:

```text
SKILL -> Tool Contract -> Service -> Domain Ops -> Object Repo -> JSON / Files
```

R2. Tool registry, operation semantics, dispatch handlers, CLI operation maps, context catalog, and host-visible env tool descriptions expose the same active action set.

R3. Skills and role contracts describe when and why to use tools, but do not copy payload schemas, dispatch tables, or object storage shapes.

R4. Services adapt env.tool requests and responses. Services do not write JSON/files directly and do not own cross-object business rules.

R5. Domain ops own business rules. Cross-object mutation is allowed only in explicitly named domain modules.

R6. Object repos own one object type's schema, path, load/save/list, and validation. Object repos do not import or mutate sibling object repos.

R7. `message` sends direct buddy-to-buddy messages and lists the active-buddy inbox. It never mutates track, task, artifact, comment, or buddybox state.

R8. `comment` adds/lists comments on readable track/artifact targets. It may check target readability through domain logic but does not mutate target objects.

R9. `buddybox` reads/writes/deletes only active-buddy private files by `logical_name`. It never creates product-readable runtime object state.

R10. `artifact.create_revision` creates active-buddy draft/revision artifacts only. It cannot directly publish to a track.

R11. `track.add_material` and `track.add_proof` are the only active shared publication entries. Successful publication updates track refs and artifact publication state together.

R12. `track.open -> artifact.get` is sufficient for buddies to discover shared artifact refs and read full artifact bodies.

R13. `task` is active-buddy private work state. `task.track_id` is optional context only; task actions do not publish artifacts or mutate shared track state.

R14. Rejections for invalid payloads, permissions, stale state, or boundary violations are actionable and leave state unchanged.

R15. Focused tests for `message`, `comment`, and `buddybox` run independently without track/artifact/task test setup except where comment readability explicitly needs a target fixture.

R16. Runtime projections, cleanup, and context discovery use the new repo/domain boundaries and do not depend on a monolithic active object-store API.

## Risk Model

Primary risks:

- Contract drift: registry, semantics, dispatch, CLI, context, and host descriptions disagree.
- Schema drift: skills copy payload schema and become stale.
- Service leakage: services write JSON/files directly or own cross-object state changes.
- Repo coupling: object repos import sibling repos and recreate the old monolith in smaller files.
- Hidden cross-object mutation: message/comment/task/buddybox changes mutate unrelated product objects.
- Comment target mutation: adding a comment changes track/artifact JSON instead of creating a comment object.
- Buddybox leakage: private files become product-readable state or appear under `buddyswitch/objects/**`.
- Artifact direct publish: artifact creation writes `published_to_track`, shared refs, or current track state.
- Multiple publication paths: publication logic exists outside the publication domain.
- Partial publication mutation: artifact says published but track refs do not include it, or track refs include an artifact whose state was not updated.
- Task scope creep: task actions take publication fields or mutate track shared state.
- Dead-end feedback: success responses point to impossible next actions or rejection responses omit correction guidance.
- Old API residue: `env_store.py` remains an active object API and continues attracting cross-module edits.
- Integration residue: projection, cleanup, launcher, or context code keeps importing monolithic object helpers.

Testing rules:

- Positive tests assert response shape, persisted state, and affected object boundaries.
- Negative tests snapshot relevant runtime files before the action and compare after rejection.
- Static tests verify boundaries by scanning code paths, imports, and runtime guidance files, excluding `docs/**`.
- Runtime tests use broker-routed `env.tool` where user-visible behavior matters.
- Tests should fail for a real boundary violation even if a helper function returns a superficially valid object.

## Test Matrix

| ID | Level | Requirement | File | Main assertion |
| --- | --- | --- | --- | --- |
| C1 | Contract | R2 | `tests/test_env_tool_semantic_contract.py` | Registry, semantics, dispatch, CLI, context catalog, and host env tools expose the same action set |
| C2 | Contract | R2/R14 | `tests/test_env_tool_response_contract.py` | Write success and rejection responses include state effects, durability, and recovery options |
| C3 | Contract | R3 | `tests/test_runtime_skills.py` | Skills use workflow guidance and runtime discovery, not copied payload schemas |
| B1 | Static boundary | R4 | `tests/test_env_layer_boundaries.py` | Services do not directly write JSON/files or runtime object paths |
| B2 | Static boundary | R5/R6 | `tests/test_env_layer_boundaries.py` | Object repos do not import sibling repos; cross-object imports appear only in allowed domains |
| B3 | Static boundary | R16 | `tests/test_repo_consistency.py` | No active object API imports remain from `env_store.py` |
| M1 | Integration | R7/R14 | `tests/test_message_env_tool.py` | Message send/list mutates only message files; invalid sends mutate nothing |
| M2 | Integration | R7 | `tests/test_message_env_tool.py` | Message replies stay within visible two-buddy conversation pairs |
| CM1 | Integration | R8/R14 | `tests/test_comment_env_tool.py` | Comment add/list uses target readability and leaves target JSON unchanged |
| CM2 | Integration | R8 | `tests/test_comment_env_tool.py` | Unsupported comment target/status/action paths reject before mutation |
| BB1 | Integration | R9 | `tests/test_buddybox_env_tool.py` | Buddybox file lifecycle stays under active-buddy private local root |
| BB2 | Boundary | R9/R14 | `tests/test_buddybox_env_tool.py` | Traversal, buddy-prefix, absolute path, and symlink escapes reject without product object mutation |
| A1 | Integration | R10/R14 | `tests/test_artifact_env_tool.py` | Direct artifact publication inputs reject and create no artifact/track mutation |
| A2 | Integration | R10/R12 | `tests/test_artifact_env_tool.py` | Owner can read drafts; other buddies cannot read drafts before publication |
| T1 | Integration | R11 | `tests/test_track_env_tool.py` | Material publication updates artifact JSON and track JSON together |
| T2 | Integration | R11 | `tests/test_track_env_tool.py` | Proof publication updates artifact JSON, track proof refs, and response state changes together |
| T3 | Integration | R11/R14 | `tests/test_track_env_tool.py` | Duplicate, cross-track, wrong-owner, and archived-track publication reject with no mutation |
| TK1 | Integration | R13 | `tests/test_task_env_tool.py` | Task create/update with `track_id` verifies existence but does not mutate track/artifact state |
| TK2 | Boundary | R13/R14 | `tests/test_task_env_tool.py` | Publication-style task payload fields reject with no mutation |
| P1 | Projection | R16 | `tests/test_parallel_contracts.py` | Workspace projection reads object state through repos and exposes only contracted fields |
| CL1 | Cleanup | R16 | `tests/test_cleanup_system.py` | Cleanup deletes each object/private file through its owner boundary |
| E1 | End-to-end | R1/R12/R15 | `tests/test_env_layer_end_to_end.py` | Broker path creates track, artifact, publication, message, comment, buddybox file, and task while preserving boundaries |
| E2 | Turn runtime | R2/R3/R16 | `tests/test_turn_integration.py` | Runtime context gives host enough catalog/semantics to choose tools without schema copied in skills |

## Detailed Tests

### C1: Runtime Tool Surfaces Stay Aligned

**Level:** Contract

**File:** `tests/test_env_tool_semantic_contract.py`

**Functional requirement:** Runtime-visible tool discovery surfaces expose one active action graph.

**Initial state:**

- Import `scripts/env/tools/contracts.py`, `semantics.py`, `dispatch.py`, `scripts/env/client.py`, `scripts/env/services/context.py`, and `turn_runtime._build_env_tools_desc()`.

**Operation steps:**

1. Build `{tool.action}` sets from:
   - `TOOL_REGISTRY`
   - `operation_semantics`
   - dispatch handler maps
   - CLI operation parser/action map
   - `context.get` tool catalog
   - host env tool description
2. Compare sets.
3. For each action, compare payload field names from registry and context catalog.

**Assertions:**

- All action sets are equal.
- Every action has non-empty `plain_description`, `use_when`, `do_not_use_when`, `inputs_explained`, `side_effects`, `success_means`, and `common_failures`.
- Inactive actions such as unsupported `comment.resolve`/`comment.reopen` are absent from all active surfaces and rejected by router tests.

**Regression value:** Prevents catalog/semantics/dispatch drift that would force agents to rely on prompt memory.

### C2: Tool Responses Expose Real State Effects

**Level:** Contract

**File:** `tests/test_env_tool_response_contract.py`

**Functional requirement:** Tool responses describe state effects and recovery paths accurately.

**Initial state:**

- Use a runtime workspace with one track, one draft artifact, and one active buddy instance.

**Operation steps:**

1. Run one successful write per object family:
   - `message.send`
   - `comment.add`
   - `buddybox.write`
   - `artifact.create_revision`
   - `track.add_material`
   - `task.create`
2. Run one rejected write per family using an invalid payload or boundary violation.

**Assertions:**

- Successful writes include `ok=true`, `state_changed=true`, `durability`, `effect_summary`, `state_changes`, and at least one structured `allowed_next_action_options` row when a useful next action exists.
- Rejections include `ok=false`, `permission_boundary`, `why_blocked`, `impact`, `state_changed=false`, `retryable`, `retry_guidance`, `correctable_fields`, and `allowed_next_actions`.
- Rejection state snapshots match pre-action snapshots.

**Regression value:** Catches dead-end feedback and false success responses.

### C3: Skills Do Not Copy Runtime Schemas

**Level:** Contract/static

**File:** `tests/test_runtime_skills.py`

**Functional requirement:** Skills guide workflow and defer contract details to runtime discovery.

**Initial state:**

- Scan `buddyswitch/skills`, `framework/contracts`, and `tools/launcher/assets/buddies`.
- Exclude `docs/**` from all scans.

**Operation steps:**

1. Search for copied schema patterns:
   - `payload_fields`
   - JSON blocks containing active action names and field lists
   - tables that duplicate registry fields for active tools
2. Search for runtime discovery guidance:
   - `context.get`
   - `context.summarize`
   - tool catalog or operation semantics references

**Assertions:**

- No copied runtime schema blocks exist in active skills or role contracts.
- Skills may include short examples but not complete payload schemas.
- Shared skills mention runtime discovery before using unfamiliar tool actions.

**Regression value:** Keeps SKILL independent from Python runtime contracts.

### B1: Services Do Not Write Runtime State Directly

**Level:** Static boundary

**File:** `tests/test_env_layer_boundaries.py`

**Functional requirement:** Services adapt requests and responses; repos write state.

**Initial state:**

- Scan `scripts/env/services/**/*.py`.
- Exclude `docs/**`.

**Operation steps:**

1. Search service files for direct state-write markers:
   - `_write_json`
   - `.write_text(`
   - `.unlink(`
   - `buddyswitch/objects`
   - `buddyswitch/local/buddybox`
2. Allow no matches once Buddybox Agent migrates file writes into `repos/buddybox_files.py`.

**Assertions:**

- Service files contain no direct JSON/file writes.
- Services import `scripts.env.domain.*` or `scripts.env.repos.<same_object>` only.

**Regression value:** Prevents state mutation from creeping back into request adapters.

### B2: Object Repos Do Not Import Sibling Repos

**Level:** Static boundary

**File:** `tests/test_env_layer_boundaries.py`

**Functional requirement:** Repos own one object type and cannot coordinate sibling state.

**Initial state:**

- Parse imports from `scripts/env/repos/*.py` and `scripts/env/domain/*.py`.

**Operation steps:**

1. For each object repo file, collect imports from `scripts.env.repos`.
2. For domain files, collect cross-object imports.
3. Compare to allowed map:
   - object repos may import `runtime_files`
   - `domain.publication` may import `repos.tracks` and `repos.artifacts`
   - `domain.comment_targets` may read target repos or visibility helpers
   - `domain.artifact_visibility` may read track/artifact repos
   - no other cross-object repo import is allowed

**Assertions:**

- Object repos do not import sibling object repos.
- Cross-object repo imports exist only in explicitly allowed domain modules.

**Regression value:** Stops the old monolith from reappearing as repo-to-repo coupling.

### B3: Old Object Store API Is Gone From Active Runtime

**Level:** Static boundary

**File:** `tests/test_repo_consistency.py`

**Functional requirement:** `env_store.py` is not an active object API after migration.

**Initial state:**

- Scan `scripts`, `tests`, `tools`, `framework`, and `buddyswitch`.
- Exclude `docs/**`.

**Operation steps:**

1. Run an import scan for `import env_store` and `from env_store import`.
2. If `env_store.py` still exists, inspect exported names.

**Assertions:**

- No runtime service/domain/repo/projection/cleanup code imports object APIs from `env_store.py`.
- If `env_store.py` remains, it exports only runtime-root compatibility helpers and no object read/write/create/update/delete helpers.
- Tests use concrete repos or test factories, not the old active object API.

**Regression value:** Removes the shared file bottleneck that blocks parallel development.

### M1: Message Mutates Only Message State

**Level:** Integration

**File:** `tests/test_message_env_tool.py`

**Functional requirement:** `message.send` and `message.list` are isolated from all product objects.

**Initial state:**

- Runtime workspace contains one track, one task, one artifact, one comment, and no messages.
- Snapshot all files under:
  - `buddyswitch/objects/tracks`
  - `buddyswitch/objects/tasks`
  - `buddyswitch/objects/artifacts`
  - `buddyswitch/objects/comments`
  - `buddyswitch/local/buddybox`

**Operation steps:**

1. Dispatch `message.send` from `design` to `dev`.
2. Dispatch `message.list` as `dev`.
3. Dispatch invalid `message.send` with `to_buddy=dev` as `dev`.

**Assertions:**

- Successful send creates exactly one file under `buddyswitch/objects/messages`.
- Message object contains `from_buddy`, `to_buddy`, `content`, `reply_to`, and `created_at`.
- Message object does not contain `status`, `read_at`, `track_id`, `task_id`, or `artifact_id`.
- All non-message snapshots are byte-for-byte unchanged.
- Rejected self-send creates no message and changes no existing files.

**Regression value:** Proves message is independent and safe for parallel development.

### M2: Message Reply Scope Is Conversation-Local

**Level:** Integration

**File:** `tests/test_message_env_tool.py`

**Functional requirement:** Replies must reference visible messages in the same two-buddy conversation pair.

**Initial state:**

- PM sends a message to Dev.
- Design sends a message to Dev.
- Market sends a message to PM.

**Operation steps:**

1. Dev replies to PM using PM's message id.
2. Dev tries to reply to PM using Design's message id.
3. Dev tries to reply to PM using Market-to-PM message id.

**Assertions:**

- The first reply succeeds and stores `reply_to` as PM's message id.
- The second and third replies reject with `permission_boundary="message.reply_to_scope"`.
- Rejected replies create no message files.

**Regression value:** Prevents message reply logic from becoming a broad graph or broadcast system.

### CM1: Comment Add/List Leaves Target JSON Unchanged

**Level:** Integration

**File:** `tests/test_comment_env_tool.py`

**Functional requirement:** Comments attach to readable targets through comment objects, not target object mutation.

**Initial state:**

- Create a non-archived track and a published artifact.
- Snapshot the track JSON and artifact JSON.

**Operation steps:**

1. Dispatch `comment.add` on the track as `design`.
2. Dispatch `comment.add` on the artifact as `dev`.
3. Dispatch `comment.list` for each target.

**Assertions:**

- Comment objects are created under `buddyswitch/objects/comments`.
- Comment rows contain target type/id, author buddy, content, thread metadata if active, reply id, and created timestamp.
- Track JSON and artifact JSON snapshots remain unchanged after add/list.
- `comment.list` returns only comments for the requested readable target.

**Regression value:** Catches accidental target mutation and keeps comment independent.

### CM2: Comment Boundary Rejections Are No-Mutation

**Level:** Integration

**File:** `tests/test_comment_env_tool.py`

**Functional requirement:** Comment target checks reject unsupported or unreadable targets before state changes.

**Initial state:**

- Runtime workspace contains:
  - an archived track
  - a private draft artifact owned by PM
  - no comments
- Snapshot all object directories.

**Operation steps:**

1. Dev calls `comment.add` on archived track.
2. Dev calls `comment.add` on PM private draft artifact.
3. Dev calls `comment.add` with target type `task`.
4. Dev calls inactive `comment.resolve` if it is not in active contract.

**Assertions:**

- Each operation rejects.
- Rejections preserve underlying boundaries such as `track.lifecycle_status` or artifact read boundary.
- No comment files are created.
- Track, task, artifact, message, and buddybox snapshots remain unchanged.

**Regression value:** Verifies target readability stays in domain checks and unsupported workflow actions do not sneak in.

### BB1: Buddybox File Lifecycle Is Private

**Level:** Integration

**File:** `tests/test_buddybox_env_tool.py`

**Functional requirement:** Buddybox state is active-buddy private and local to the instance.

**Initial state:**

- PM active instance with empty buddybox root.
- Dev active instance with separate buddybox root.

**Operation steps:**

1. PM calls `buddybox.write` for `notes/brief.md`.
2. PM calls `buddybox.list` and `buddybox.read`.
3. Dev calls `buddybox.list` and `buddybox.read` for the same logical name.
4. PM calls `buddybox.delete`.

**Assertions:**

- PM write creates a file only under `buddyswitch/local/buddybox/pm/notes/brief.md`.
- No file is created under `buddyswitch/objects/**`.
- PM can list/read/delete the file.
- Dev cannot list/read PM's file through prefix or logical name.
- Responses report `visibility="active_buddy_private"`, `product_readable=false`, and no product state mutation.

**Regression value:** Prevents buddybox private work from becoming shared runtime product state.

### BB2: Buddybox Escape Attempts Reject Before Mutation

**Level:** Boundary/integration

**File:** `tests/test_buddybox_env_tool.py`

**Functional requirement:** Buddybox logical names cannot escape the active buddy private root.

**Initial state:**

- PM active instance.
- Runtime workspace contains one track and one artifact snapshot.

**Operation steps:**

1. Attempt `buddybox.write` with absolute path.
2. Attempt `buddybox.write` with `../` traversal.
3. Attempt `buddybox.write` with another buddy prefix.
4. Attempt read/delete through a symlink escape if platform supports symlinks.

**Assertions:**

- Every escape attempt rejects with the private file boundary.
- No files are written outside PM buddybox root.
- Product object snapshots remain unchanged.

**Regression value:** Proves private file isolation is enforced at runtime, not only by prompt instruction.

### A1: Artifact Creation Cannot Directly Publish

**Level:** Integration

**File:** `tests/test_artifact_env_tool.py`

**Functional requirement:** `artifact.create_revision` creates drafts only.

**Initial state:**

- Runtime workspace contains one non-archived track.
- Snapshot track JSON and artifact directory.

**Operation steps:**

1. PM calls `artifact.create_revision` with `published_to_track`.
2. PM calls `artifact.create_revision` with `status="published"`.
3. PM opens the track.

**Assertions:**

- Both create attempts reject with publication-path boundary.
- No artifact file is created.
- Track JSON is unchanged and has no new shared material/proof refs.
- `track.open` returns no refs created by failed artifact calls.

**Regression value:** Prevents orphan published artifacts and multiple publication entries.

### A2: Draft Readability Is Owner-Only Before Publication

**Level:** Integration

**File:** `tests/test_artifact_env_tool.py`

**Functional requirement:** Private drafts are readable by owner only until published by track actions.

**Initial state:**

- PM active instance.
- Dev active instance.

**Operation steps:**

1. PM creates `artifact.create_revision` draft.
2. PM calls `artifact.get`.
3. Dev calls `artifact.get` for the same artifact.

**Assertions:**

- PM read succeeds and returns full body.
- Dev read rejects with artifact private/readability boundary.
- No track JSON exists or changes because draft creation is not publication.

**Regression value:** Preserves artifact draft privacy and avoids accidental shared state.

### T1: Material Publication Is Atomic

**Level:** Integration

**File:** `tests/test_track_env_tool.py`

**Functional requirement:** `track.add_material` updates artifact publication state and track shared refs together.

**Initial state:**

- PM creates a track.
- PM creates a draft artifact.
- Snapshot artifact JSON and track JSON.

**Operation steps:**

1. PM calls `track.add_material` with track id, artifact id, label, and summary.
2. PM calls `track.open`.
3. Dev calls `artifact.get` using the returned artifact id.

**Assertions:**

- Response includes `state_changes` for artifact publication and track material ref.
- Artifact JSON has `status="published"` and `published_to_track=<track-id>`.
- Track JSON has a current `shared_materials` row with the artifact id.
- `track.open` exposes the current ref.
- Dev can read full body through `artifact.get`.

**Regression value:** Catches partial material publication.

### T2: Proof Publication Is Atomic

**Level:** Integration

**File:** `tests/test_track_env_tool.py`

**Functional requirement:** `track.add_proof` updates artifact publication state and track proof refs together.

**Initial state:**

- PM creates a track and proof draft artifact.
- Snapshot artifact JSON and track JSON.

**Operation steps:**

1. PM calls `track.add_proof`.
2. PM calls `track.open`.
3. Test buddy calls `artifact.get` using proof artifact id.

**Assertions:**

- Response includes artifact and proof-ref state changes.
- Artifact JSON is published to the track.
- Track JSON has a current `close_proof` row with the artifact id.
- Full body is readable through `artifact.get`.

**Regression value:** Catches proof-specific partial mutation.

### T3: Publication Rejections Preserve State

**Level:** Integration

**File:** `tests/test_track_env_tool.py`

**Functional requirement:** Invalid publication attempts reject before mutation.

**Initial state:**

- Track A and Track B exist.
- PM owns Artifact A draft.
- Dev owns Artifact D draft.
- Track A may be archived in one subcase.
- Snapshot track and artifact JSON before each subcase.

**Operation steps:**

1. PM publishes Artifact A to Track A.
2. PM tries to publish Artifact A again to Track A.
3. PM tries to publish Artifact A to Track B.
4. PM tries to publish Dev-owned Artifact D.
5. PM tries to publish a draft to archived Track A.

**Assertions:**

- First publication succeeds.
- Later invalid attempts reject with actionable boundaries.
- Every rejected subcase leaves all track/artifact JSON byte-for-byte unchanged from its pre-action snapshot.

**Regression value:** Prevents duplicate, cross-track, wrong-owner, and archived-track corruption.

### TK1: Task Track Context Does Not Mutate Track

**Level:** Integration

**File:** `tests/test_task_env_tool.py`

**Functional requirement:** `task.track_id` is private context, not shared track mutation.

**Initial state:**

- PM creates a track.
- Dev active instance.
- Snapshot track JSON and artifact directory.

**Operation steps:**

1. Dev creates a task with `track_id`.
2. Dev updates the task status and summary.
3. Dev lists tasks filtered by `track_id`.

**Assertions:**

- Task file contains `track_id`.
- Track JSON remains unchanged.
- No artifact files are created or updated.
- Task list returns only active-buddy tasks matching the filter.

**Regression value:** Keeps task from becoming a shared collaboration or publication owner.

### TK2: Task Rejects Publication Fields

**Level:** Boundary/integration

**File:** `tests/test_task_env_tool.py`

**Functional requirement:** Task payloads cannot carry artifact publication or track shared-state fields.

**Initial state:**

- Dev active instance.
- Runtime object directories are snapshotted.

**Operation steps:**

1. Dev calls `task.create` with `artifact_id`.
2. Dev calls `task.update` with `published_to_track`.
3. Dev calls `task.update` with `shared_materials`.

**Assertions:**

- Each operation rejects with payload/request boundary.
- No task is created or modified.
- Track and artifact snapshots remain unchanged.

**Regression value:** Blocks task scope creep.

### P1: Workspace Projection Uses Owner Boundaries

**Level:** Projection

**File:** `tests/test_parallel_contracts.py`

**Functional requirement:** Projection reads object state without creating new coupling.

**Initial state:**

- Runtime workspace contains:
  - one track with material ref
  - one published artifact
  - one task with track context
  - one message
  - one comment
  - one buddybox private file

**Operation steps:**

1. Build workspace projection payload.
2. Inspect projected top-level keys and per-object rows.

**Assertions:**

- Projection matches `framework/contracts/workspace-projection.json`.
- Tasks do not include artifact publication fields.
- Tracks expose shared refs but not artifact bodies.
- Artifacts expose publication metadata but not task ownership.
- Comments are exposed only through contracted derived fields or explicit comment tool output.
- Buddybox private file content is absent.

**Regression value:** Prevents integration code from rejoining object ownership behind the scenes.

### CL1: Cleanup Uses Correct Owner Boundary

**Level:** Integration

**File:** `tests/test_cleanup_system.py`

**Functional requirement:** Cleanup removes runtime state through object owners without cross-boundary mutation.

**Initial state:**

- Runtime workspace contains objects and buddybox files for PM and Dev.

**Operation steps:**

1. Run cleanup for a single buddy.
2. Run cleanup for all runtime state in a separate workspace.

**Assertions:**

- Single-buddy cleanup removes only that buddy's private tasks/artifacts/messages/comments where ownership semantics say it should.
- Buddybox cleanup removes private files only under that buddy's local root.
- Track shared state is not silently rewritten by object cleanup.
- All-object cleanup removes every object through the appropriate repo.

**Regression value:** Prevents cleanup from becoming a hidden cross-object mutator.

### E1: End-to-End Boundary Main Path

**Level:** End-to-end

**File:** `tests/test_env_layer_end_to_end.py`

**Functional requirement:** Main runtime collaboration path works while boundaries hold.

**Initial state:**

- Empty runtime workspace.
- Active PM, Design, Dev, Test instances.

**Operation steps:**

1. PM creates a track.
2. PM creates an artifact draft.
3. PM publishes it as material.
4. Design opens the track and reads the artifact body.
5. Dev creates a private task with the track as context.
6. Design sends Dev a message.
7. Dev adds a comment on the artifact.
8. Dev writes a private buddybox file.
9. Test opens the track and reads material body.

**Assertions:**

- Every call goes through broker-routed `env.tool`.
- Track refs and artifact body are readable through `track.open -> artifact.get`.
- Message appears only in Dev inbox.
- Comment appears only through `comment.list` for the target.
- Task does not change track/artifact state.
- Buddybox file is visible only to Dev and never appears in product objects.

**Regression value:** Verifies the complete architecture through the user-visible main path.

### E2: Runtime Context Is Enough For Host Tool Choice

**Level:** Turn/runtime integration

**File:** `tests/test_turn_integration.py`

**Functional requirement:** Host can discover tool choices from runtime catalog/semantics without copied skill schemas.

**Initial state:**

- Runtime workspace contains candidate track, artifact, task, messages, comments, and buddybox file summaries.

**Operation steps:**

1. Build turn context for PM and Dev.
2. Inspect `context.get` and summarized context payloads.
3. Inspect active buddy instructions.

**Assertions:**

- Context exposes tool catalog and operation semantics for every active action.
- Skills/AGENTS tell buddies to consult runtime catalog/semantics for exact fields.
- Context summary includes enough candidate ids for `track.open`, `artifact.get`, `message.list`, `comment.list`, and `buddybox.list`.
- No active skill or AGENTS file contains copied payload schema blocks.

**Regression value:** Confirms the thin contract layer replaces prompt bulk.

## Verification Commands

Focused boundary/contract verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_tool_semantic_contract.py tests/test_env_tool_router.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_env_layer_boundaries.py -q
```

Focused object verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py tests/test_task_env_tool.py tests/test_artifact_env_tool.py tests/test_track_env_tool.py -q
```

Focused runtime integration verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_parallel_contracts.py tests/test_cleanup_system.py tests/test_runless_runtime_contract.py tests/test_context_binding_env_tool.py tests/test_env_layer_end_to_end.py tests/test_turn_integration.py -q
```

Broader verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py tests/test_task_env_tool.py tests/test_artifact_env_tool.py tests/test_track_env_tool.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_router.py tests/test_env_tool_response_contract.py tests/test_runtime_tool_feedback.py tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_env_layer_boundaries.py tests/test_parallel_contracts.py tests/test_cleanup_system.py tests/test_runless_runtime_contract.py tests/test_context_binding_env_tool.py tests/test_env_layer_end_to_end.py tests/test_turn_integration.py -q
```

Manual runtime smoke check after automated tests pass:

```bash
./buddyswitch-codex instance start --buddy pm
python3 scripts/env/client.py context summarize --limit 5
```

Expected manual outcome:

- PM runtime starts.
- Context summary includes tool catalog/discovery hints.
- No manual state edits under `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` are needed.

## Completion Criteria

- All contract, boundary, object, and integration tests above pass.
- Rejection tests prove no mutation by comparing persisted state snapshots.
- Static scans exclude `docs/**` and enforce active runtime boundaries in code, skills, contracts, and launcher buddy instructions.
- `message`, `comment`, and `buddybox` focused tests can run without the full track/artifact/task suite.
- `track/artifact` publication is tested as the only active cross-object mutation.
- No test relies on internal helper names where runtime-visible behavior or boundary state is the actual requirement.
