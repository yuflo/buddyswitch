# Track-Native Comment Rebuild Test Plan

Date: 2026-06-10
Source memo: `docs/memo/2026-06-09-track-comment-rebuild-task.md`
Resource warning: `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

## Goal

Prove that Comment is no longer an independent target-scoped discussion system. Comments must be Track-scoped collaboration rows, stored and read through exact Track instance isolation, exposed through Track-native actions, and absent from the standalone actor-facing `comment` tool catalog.

## Current Bottleneck

The current implementation still has a generic `comment` tool, flat `buddyswitch/objects/comments/*.json` storage, `target_type + target_id` comment rows, Artifact/Artifact section comment logic, Artifact relation backlinks, and context text that describes comments as target-scoped Track/Artifact discussion.

The test suite must therefore replace old target-anything assertions with tests that prove:

- Track comments require `track_id`;
- all thread/reply/resolve behavior is Track-local;
- Artifact and Artifact section comments are removed, not hidden behind compatibility branches;
- Track actions own add/list/resolve;
- `track.open` and context only expose compact Track comment cues;
- actor-facing catalog/auth/skills no longer advertise `comment.*`;
- storage path makes Track isolation visible: `buddyswitch/objects/track-comments/<track_id>/<comment_id>.json`.

## Test Scope

### 1. Track Comment Env Tool Behavior

File: `tests/test_track_comment_env_tool.py`

Replace old `tests/test_comment_env_tool.py` coverage with Track-native scenarios.

Cases:

1. `track.add_comment` creates one root comment on a non-archived Track.
   - Input: `track_id`, `content`.
   - Assert success action is `track.add_comment`.
   - Assert returned comment has `track_id`, `thread_id == id`, `reply_to is None`, `status == "open"`, `by_actor`, `mentioned_actors`.
   - Assert no `target_type`, `target_id`, `anchor`, or `artifact_revision_id`.
   - Assert the JSON file exists under `buddyswitch/objects/track-comments/<track_id>/<comment_id>.json`.
   - Assert no file is written under `buddyswitch/objects/comments`.

2. `track.list_comments` returns full comment rows for exactly one Track.
   - Seed comments on Track A and Track B.
   - Assert listing Track A returns only Track A rows.
   - Assert `threads` groups rows by `thread_id`.
   - Assert `status_counts` supports `open`, `resolved`, and `all`.

3. Replies inherit the parent thread only inside the same Track.
   - Root A on Track A, root B on Track B.
   - Reply to root A with `track_id=Track A` succeeds and inherits root A `thread_id`.
   - Reply to root B with `track_id=Track A` fails with `permission_boundary == "track_comment.reply_to_scope"`.
   - Assert failed reply does not write any row.

4. PM resolves one Track-local thread.
   - Root plus reply on one Track.
   - Non-PM resolve is rejected by role-action auth using required permission `track.resolve_comment_thread`.
   - PM `track.resolve_comment_thread` with `track_id`, `comment_id`, and `resolution_summary` resolves every row in the thread.
   - Assert resolver is `resolved_by_actor`, status is `resolved`, and repeat resolve fails with `permission_boundary == "track_comment.state"`.

5. Resolve cannot cross Tracks.
   - Create root comment on Track B.
   - PM calls resolve with `track_id=Track A`, `comment_id=<Track B comment>`.
   - Assert rejection boundary is `track_comment.thread_scope`.
   - Assert Track B comment remains open.

6. Archived Track rejects Track comment writes/resolution.
   - Archive Track.
   - Assert `track.add_comment` and `track.resolve_comment_thread` reject with `track.lifecycle_status`.
   - Assert list can either reject archived Track consistently with `track.open` or return no active Track rows only if product semantics explicitly choose that. For this rebuild, follow the existing Track read boundary and reject archived routine opens.

7. Mention validation remains concrete ActorAddress validation.
   - Valid roles in manifest succeed and deduplicate repeated actor ids.
   - Unknown role fails with `E_TRACK_COMMENT_PAYLOAD`.

8. Artifact and Artifact section payload fields are not accepted.
   - `track.add_comment` with `target_type`, `target_id`, `anchor`, or `artifact_revision_id` fails as unsupported payload.
   - Dispatch to removed `comment.add/list/resolve` fails with `E_ENV_TOOL`.

### 2. Repo Storage and Validation

File: `tests/test_track_comments_repo.py`

Cases:

1. Repo writes Track comments under `track-comments/<track_id>/<comment_id>.json`.
2. `validate_track_comment` rejects rows missing `track_id`.
3. `validate_track_comment` rejects forbidden legacy fields: `target_type`, `target_id`, `anchor`, `artifact_revision_id`, `resolved`, `task_id`, `edit_history`, `attachment`.
4. `reply_to_track_comment` rejects missing parent and parent from another Track.
5. `comments_for_track_thread(track_id, thread_id)` cannot return rows from another Track even if thread ids collide.
6. `resolve_track_comment_thread(track_id, comment_id, ...)` updates only same-Track rows and leaves same `thread_id` rows in another Track untouched.

### 3. Catalog, Schema, Auth, and Semantic Contracts

Files:

- `tests/test_env_tool_schema_contract.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_role_action_auth.py`
- `tests/test_env_manifest_v2.py`
- `tests/test_runtime_skills.py`

Cases:

1. `catalog.supported_tools()` does not include `comment`.
2. `track` action schema includes:
   - `add_comment(track_id, content, reply_to?, mentioned_actors?)`
   - `list_comments(track_id, status?)`
   - `resolve_comment_thread(track_id, comment_id, resolution_summary)`
3. Track comment schemas do not include `target_type`, `target_id`, `anchor`, or `artifact_revision_id`.
4. Role auth permits common roles to add/list Track comments.
5. Role auth restricts `track.resolve_comment_thread` to PM.
6. Context runtime policy previews show `track.resolve_comment_thread`, not `comment.resolve`.
7. Manifest roles no longer require or advertise `comment-tool`; Track skill/docs become the actor-facing path.
8. Runtime shared skill tests no longer require an independent comment skill with `artifact_section`.

### 4. Track Open and Context Cues

Files:

- `tests/test_track_comment_env_tool.py`
- `tests/test_host_decision_surface_product_mode.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_env_tool_response_contract.py`

Cases:

1. `track.open` includes compact `comment_cues`:
   - `open_thread_count`
   - `recent_comments`
   - `mentioned_comment_ids` or equivalent compact mention cue when active actor is mentioned
   - source of truth guidance pointing to `track.list_comments`
2. `track.open` does not replace full listing; full rows are returned by `track.list_comments`.
3. `context.get/summarize` `open_comment_threads` rows only use Track comment state and include `track_id`.
4. Context source descriptors describe Track collaboration comments, not target-scoped Track/Artifact comments.
5. Artifact summaries no longer include comment counts or comment backlinks from generic Artifact comments.

### 5. Cleanup and Env Store Compatibility Boundaries

Files:

- `tests/test_cleanup_system.py`
- `tests/test_env_store_v2.py`
- `scripts/env_store.py`
- `scripts/env_legacy_store.py`

Cases:

1. Cleanup discovers `buddyswitch/objects/track-comments/<track_id>/*.json`.
2. Role cleanup deletes authored Track comments and leaves the Track object unchanged.
3. All-data cleanup recreates `buddyswitch/objects/track-comments`, not the old `comments` directory.
4. Env store facade exposes Track comment helpers only for tests and runtime internals:
   - `track_comment_file`
   - `list_track_comments`
   - `get_track_comment`
   - `create_track_comment`
   - `comments_for_track`
   - `resolve_track_comment_thread`
5. Legacy generic comment helper tests are removed or rewritten; no test should depend on `comments_for_target`.

### 6. Static Removal Guards

Add or update tests to grep/source-inspect:

1. No `scripts/env/tools/comment` package is discoverable.
2. No active production code imports `env.domain.comment_targets`.
3. No active production code imports `env.repos.comments` except deleted compatibility shims during the edit; final code uses `env.repos.track_comments`.
4. No active production code calls `comments_for_target`.
5. No actor-facing docs/role AGENTS/shared skills say `comment.add`, `comment.list`, `comment.resolve`, `artifact_section` comment support, or target-scoped comments.

## Verification Commands

Use focused commands first. These tests use isolated temporary runtime roots and do not start launcher services.

```bash
python -m pytest tests/test_track_comments_repo.py -q
python -m pytest tests/test_track_comment_env_tool.py -q
python -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py -q
python -m pytest tests/test_role_action_auth.py tests/test_env_manifest_v2.py tests/test_runtime_skills.py -q
python -m pytest tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py tests/test_cleanup_system.py tests/test_env_store_v2.py -q
```

Run broad verification only after focused groups are green:

```bash
python -m pytest tests/test_track_comments_repo.py tests/test_track_comment_env_tool.py tests/test_env_tool_schema_contract.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_role_action_auth.py tests/test_env_manifest_v2.py tests/test_runtime_skills.py tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py tests/test_cleanup_system.py tests/test_env_store_v2.py -q
```

Do not run launcher or browser service suites as part of this task unless a changed test explicitly requires them and lifecycle cleanup has been inspected first.

## Phase 1 Review

- Functional coverage maps to every acceptance criterion in the memo.
- Tests are behavior-first: they assert Track isolation, Track-native APIs, and removal of unsupported Artifact/comment surfaces, not implementation-specific shortcuts.
- Resource lifecycle risk is controlled by avoiding service-starting launcher paths and using isolated runtime-root unit/integration tests.
- No transitional compatibility behavior is accepted as passing evidence.
