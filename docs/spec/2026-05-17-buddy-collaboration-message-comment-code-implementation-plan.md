# Buddy Collaboration Message Comment Code Implementation Plan

> **For agentic workers:** Implement this plan in `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem` on branch `dev_buddy_mem`. Use test-first changes for every behavior change. Do not implement handoff, review, whiteboard, broadcast, read receipt, comment resolution, task comments, edit, or delete capabilities.

**Goal:** Add two atomic BuddySwitch collaboration tools, `message` and `comment`, so buddies can exchange direct messages and attach plain comments to readable tracks or artifacts through the existing env.tool layer.

**Architecture:** Follow the current registry -> semantics -> dispatch -> service pattern. Store messages and comments as durable runtime objects under `buddyswitch/objects`, attach comments to track/artifact `comment_ids`, and reuse existing track/artifact read-boundary helpers instead of adding a new permission framework or workflow engine.

**Tech Stack:** Python env store/services/tools, broker-routed `env.tool`, Python CLI, TOML manifest, runtime skill Markdown, shell launcher projection, JSON workspace projection contract, pytest/unittest.

---

## 1. Source Inputs And Current State

- Read first:
  - `AGENTS.md`
  - `docs/memo/2026-05-17-buddy-collaboration-message-comment-design.md`
- Current implementation shape inspected:
  - Tool registry and semantics: `scripts/env/tools/contracts.py`, `scripts/env/tools/semantics.py`
  - Tool routing: `scripts/env/tools/router.py`, `scripts/env/tools/dispatch.py`, `scripts/env/client.py`
  - Store/model: `scripts/env_store.py`
  - Existing service patterns: `scripts/env/services/tasks.py`, `scripts/env/services/tracks.py`, `scripts/env/services/artifacts.py`, `scripts/env/services/artifact_visibility.py`, `scripts/env/services/context.py`
  - Runtime surfaces: `scripts/env_manifest.py`, `buddyswitch/manifest.toml`, `scripts/runtime_store/projections.py`, `framework/contracts/workspace-projection.json`, `tools/launcher/workspace.sh`, `scripts/env_cleanup.py`
  - Test scaffolding: `tests/runtime_root_test_helper.py`, `tests/test_env_tool_router.py`, `tests/test_env_tool_semantic_contract.py`, `tests/test_context_binding_env_tool.py`, `tests/test_env_manifest_v2.py`, `tests/test_runtime_skills.py`, `tests/test_parallel_contracts.py`, `tests/test_buddyswitch_launcher.py`, `tests/test_cleanup_system.py`, `tests/test_env_store_v2.py`, `tests/test_artifact_env_tool.py`, `tests/test_track_env_tool.py`, `tests/test_runless_runtime_contract.py`, `tests/test_repo_consistency.py`

Current bottleneck: BuddySwitch has track/task/artifact collaboration state and per-buddy private files, but no atomic buddy-to-buddy communication surface and no object-level discussion surface. The shortest verified path is adding two concrete tools and their durable object support while keeping workflow composition in skills.

## 2. Target Runtime Contract

### Active Tool Surface

After this work, the active env tool set is:

- `task`
- `track`
- `artifact`
- `buddybox`
- `context`
- `evidence`
- `search`
- `message`
- `comment`

`message` and `comment` are atomic tools. They do not trigger task changes, handoffs, reviews, notifications, read receipts, status transitions, resolution workflows, or broadcast fan-out.

### Message Tool

Actions:

- `message.send`
- `message.list`

`message.send` payload:

```json
{
  "to_buddy": "dev",
  "content": "Plain text",
  "reply_to": "msg-..."
}
```

Rules:

- `to_buddy` is required.
- `to_buddy` must be declared in `buddyswitch/manifest.toml`.
- `to_buddy` must not equal the active buddy.
- `content` is required, plain text, and non-empty after trimming.
- `reply_to` is optional.
- `reply_to`, when present, must reference an existing message in the same two-buddy conversation pair where the active buddy is a participant.
- No `track_id`, `task_id`, `artifact_id`, `broadcast`, `recipients`, `status`, `read_at`, or attachment fields are accepted.

`message.list` payload:

```json
{
  "buddy": "design"
}
```

Rules:

- Returns only messages where `to_buddy == active_buddy`.
- Optional `buddy` filters by `from_buddy`.
- No status filter exists.
- No sent-mail view exists in this pass.
- Listing does not mutate read state and does not create read receipts.

Message object:

```json
{
  "id": "msg-<uuid>",
  "from_buddy": "design",
  "to_buddy": "dev",
  "content": "Plain text",
  "reply_to": null,
  "created_at": "2026-05-17T00:00:00+08:00"
}
```

Storage:

- `buddyswitch/objects/messages/<message-id>.json`

### Comment Tool

Actions:

- `comment.add`
- `comment.list`

`comment.add` payload:

```json
{
  "target_type": "artifact",
  "target_id": "art-dev-example",
  "content": "Plain text",
  "reply_to": "comment-..."
}
```

Rules:

- `target_type` must be exactly `track` or `artifact`.
- `task` target type is rejected.
- `target_id` is required.
- `content` is required, plain text, and non-empty after trimming.
- `reply_to` is optional.
- `reply_to`, when present, must reference an existing comment attached to the same target object.
- No status, resolution, edit, delete, attachment, task comment, or review fields are accepted.
- The active buddy must have read access to the target object.

`comment.list` payload:

```json
{
  "target_type": "track",
  "target_id": "track-example"
}
```

Rules:

- Uses the same target read boundary as `comment.add`.
- Returns comments attached to that target by `comment_ids`.
- Does not mutate state.

Comment object:

```json
{
  "id": "comment-<uuid>",
  "target_type": "artifact",
  "target_id": "art-dev-example",
  "author_buddy": "design",
  "content": "Plain text",
  "reply_to": null,
  "created_at": "2026-05-17T00:00:00+08:00"
}
```

Storage:

- `buddyswitch/objects/comments/<comment-id>.json`

Target object support:

- Track records gain `comment_ids: []`.
- Artifact records gain `comment_ids: []`.
- Existing track/artifact JSON missing `comment_ids` normalizes to `[]` when read through `env_store`.
- New track/artifact writes persist `comment_ids`.
- Task records are not modified and do not gain `comment_ids`.

Target read boundaries:

- Track targets reuse the readable-track rule from `track.get`: target exists and is not archived.
- Artifact targets reuse `artifact_visibility.artifact_read_decision()`.
- Rejections preserve the underlying `permission_boundary`, especially:
  - `track.lifecycle_status`
  - `artifact.currentness`
  - `artifact.track_relation`
  - `artifact.track_association`
  - `artifact.task_association`

## 3. Scope

In scope:

- Durable message and comment object storage.
- `message.send`, `message.list`, `comment.add`, `comment.list`.
- Registry, semantics, dispatch, CLI, context catalog, manifest permissions, runtime skills, launcher state projection, cleanup, workspace projection contract, and tests.
- `comment_ids` on tracks and artifacts only.
- Reply validation for message and comment.
- Structured success and rejection responses following existing env-tool response patterns.

Out of scope:

- Handoff.
- Review or approval workflow.
- Whiteboard.
- Broadcast or group messaging.
- Read receipts, unread counts, online status, or message status.
- Message edit/delete.
- Comment edit/delete.
- Comment resolution, status, assignment, or resolved/unresolved filtering.
- Task comments.
- Rich text or attachments.
- Generic permission framework, event bus, workflow engine, plugin layer, or compatibility wrapper.

## 4. Definition Of Done

- `message` and `comment` appear in registry, semantics, dispatch, CLI help, runtime status, context tool catalog, and compact affordances.
- `message.send` creates durable message objects with no status field.
- `message.list` returns only active-buddy inbox messages and accepts only optional sender filter `buddy`.
- `message.send` rejects self-send, unknown target buddy, unsupported fields, blank content, and invalid `reply_to`.
- `comment.add` creates durable comments and appends ids to track/artifact `comment_ids`.
- `comment.list` returns comments for readable track/artifact targets.
- `comment.add/list` reject archived track targets.
- `comment.add/list` for artifacts reuse `artifact_visibility.artifact_read_decision()`, including foreign superseded artifact rejection through `artifact.currentness`.
- Track and artifact records normalize and persist `comment_ids`; task records do not.
- Runtime projection exposes `comment_ids` on track/artifact views only, with no top-level messages or comments.
- Manifest validator accepts `message.*` and `comment.*`; every buddy has the new shared skills and permissions.
- Launcher projects `buddyswitch/objects/messages` and `buddyswitch/objects/comments` as runtime-managed shared state.
- Cleanup covers message/comment object dirs and recreates their skeleton directories.
- Focused message/comment tests and broader registry/manifest/projection/launcher/cleanup tests pass.

## 5. Full File Change List

| Area | File | Required change |
| --- | --- | --- |
| Object store | `scripts/env_store.py` | Add `MESSAGES_DIR`, `COMMENTS_DIR`, path helpers, validators, list/get/save/create helpers for messages/comments; add `comment_ids` normalization/persistence to track/artifact; add helpers to append comment ids to track/artifact. |
| Tool registry | `scripts/env/tools/contracts.py` | Add `message` and `comment` registry rows with actions, payload fields, permissions, mutation type, authority, preconditions, returns. |
| Tool semantics | `scripts/env/tools/semantics.py` | Add capability rows and action semantics for message/comment; ensure action semantics include no status/read receipt/resolution behavior. |
| Tool dispatch | `scripts/env/tools/dispatch.py` | Import new services and add `message` and `comment` handler maps. |
| CLI | `scripts/env/client.py` | Add `message send/list` and `comment add/list` subcommands routed through `env.tool`. |
| Message service | `scripts/env/services/messages.py` | New service with `send_message()` and `list_messages()`. |
| Comment service | `scripts/env/services/comments.py` | New service with `add_comment()` and `list_comments()`, reusing track/artifact read boundaries. |
| Context service | `scripts/env/services/context.py` | Context tool catalog updates automatically through registry; add message/comment source descriptors in `context.list_sources`; expose `comment_ids` only through track/artifact views, never task views. |
| Manifest validator | `scripts/env_manifest.py` | Add `message` and `comment` to supported permission objects. |
| Manifest | `buddyswitch/manifest.toml` | Add shared skill rows for `message-tool` and `comment-tool`; add both skill ids to every buddy; add `message.send`, `message.list`, `comment.add`, `comment.list` to every buddy permissions list. |
| Shared skill | `buddyswitch/skills/shared/message-tool/SKILL.md` | New concise tool usage manual for message env tool. |
| Shared skill | `buddyswitch/skills/shared/comment-tool/SKILL.md` | New concise tool usage manual for comment env tool. |
| Projection implementation | `scripts/runtime_store/projections.py` | Add `comment_ids` to track and artifact views; do not expose top-level message/comment records. |
| Projection contract | `framework/contracts/workspace-projection.json` | Add `comment_ids` to track and artifact view shapes; keep top-level keys unchanged and do not expose top-level comments/messages. |
| Launcher state | `tools/launcher/workspace.sh` | Add `buddyswitch/objects/messages` and `buddyswitch/objects/comments` to runtime-managed/projected state paths. |
| Cleanup | `scripts/env_cleanup.py` | Add message/comment categories, discovery, buddy/all-data cleanup coverage, safe detach of deleted comment ids, skeleton recreation. |
| Test sandbox | `tests/runtime_root_test_helper.py` | Patch `env_store.MESSAGES_DIR` and `env_store.COMMENTS_DIR` into the temp runtime root. |
| New tests | `tests/test_message_env_tool.py` | New focused message service/dispatch/visibility/reply/non-goal tests. |
| New tests | `tests/test_comment_env_tool.py` | New focused comment service/read-boundary/reply/persistence/non-goal tests. |
| Existing tests | `tests/test_env_tool_router.py` | Expected tools include message/comment; dispatch coverage matches registry; CLI help exposes message/comment; unsupported non-goal actions reject. |
| Existing tests | `tests/test_env_tool_semantic_contract.py` | Expected tools include message/comment and semantic coverage remains complete. |
| Existing tests | `tests/test_context_binding_env_tool.py` | Expected tools include message/comment; context sources/tool affordances include new tools; no task comment exposure. |
| Existing tests | `tests/test_env_manifest_v2.py` | Validator accepts message/comment and all buddies include required skills/permissions; rejects non-goal objects where applicable. |
| Existing tests | `tests/test_runtime_skills.py` | Required shared runtime tools include message-tool/comment-tool; shared tool skills do not teach non-goals. |
| Existing tests | `tests/test_parallel_contracts.py` | Workspace projection includes `comment_ids` on track/artifact and no top-level messages/comments. |
| Existing tests | `tests/test_repo_consistency.py` | Expected tool set includes message/comment; residue scan keeps handoff/non-goals absent from active surfaces. |
| Existing tests | `tests/test_buddyswitch_launcher.py` | Runtime projected state pairs include messages/comments; runtime skill materialization includes new shared skills per manifest. |
| Existing tests | `tests/test_cleanup_system.py` | Cleanup plans include message/comment dirs and recreate skeletons. |
| Existing tests | `tests/test_runless_runtime_contract.py` | Runtime status/env client help assertions include message/comment and keep old retired tools absent. |
| Existing tests | `tests/test_artifact_env_tool.py` | Reuse existing artifact visibility fixtures for comment artifact-boundary tests or keep those in new `test_comment_env_tool.py`. |
| Existing tests | `tests/test_track_env_tool.py` | Reuse archived track expectations for comment boundary tests or keep those in new `test_comment_env_tool.py`. |

## 6. Data Model And Store Design

### Store constants and paths

Add to `scripts/env_store.py` near existing object dir constants:

```python
MESSAGES_DIR = OBJECTS_ROOT / "messages"
COMMENTS_DIR = OBJECTS_ROOT / "comments"
```

Update `ensure_runtime_dirs()` to create:

- `TRACKS_DIR`
- `TASKS_DIR`
- `ARTIFACT_OBJECTS_DIR`
- `MESSAGES_DIR`
- `COMMENTS_DIR`

Add path helpers:

```python
def message_file(message_id: str) -> Path:
    return MESSAGES_DIR / f"{require_id(message_id, 'message id')}.json"


def comment_file(comment_id: str) -> Path:
    return COMMENTS_DIR / f"{require_id(comment_id, 'comment id')}.json"
```

### Message validation

Add `validate_message(message: dict[str, Any]) -> dict[str, Any]`.

Validation rules:

- `id` required, `require_id`.
- `from_buddy` required non-empty string.
- `to_buddy` required non-empty string.
- `content` required non-empty string after trim.
- `reply_to` must be `None` or a valid id.
- `created_at` required non-empty string.
- Return exactly: `id`, `from_buddy`, `to_buddy`, `content`, `reply_to`, `created_at`.
- Do not accept or return `status`, `read_at`, `track_id`, `task_id`, `artifact_id`, `recipients`, or `broadcast`.

### Comment validation

Add `validate_comment(comment: dict[str, Any]) -> dict[str, Any]`.

Validation rules:

- `id` required, `require_id`.
- `target_type` must be `track` or `artifact`.
- `target_id` required valid id.
- `author_buddy` required non-empty string.
- `content` required non-empty string after trim.
- `reply_to` must be `None` or a valid id.
- `created_at` required non-empty string.
- Return exactly: `id`, `target_type`, `target_id`, `author_buddy`, `content`, `reply_to`, `created_at`.
- Do not accept or return `status`, `resolved`, `resolved_at`, `task_id`, `edit_history`, or attachment fields.

### Track/artifact `comment_ids`

Modify `validate_track()`:

- Read `comment_ids = track.get("comment_ids", [])`.
- Missing field normalizes to `[]`.
- Field must be a list of non-empty valid ids.
- Returned normalized track includes `comment_ids` after `task_ids`.

Modify `create_track()`:

- New track object includes `"comment_ids": []`.

Modify `update_track()`:

- Do not expose `comment_ids` as a generic `track.update` env-tool payload field.
- Keep `comment_ids` out of public `track.update` payload fields. Only the private store helper `add_comment_id_to_track()` may update this field.

Modify `validate_artifact()`:

- Read `comment_ids = artifact.get("comment_ids", [])`.
- Missing field normalizes to `[]`.
- Field must be a list of non-empty valid ids.
- Returned normalized artifact includes `comment_ids` immediately after `source_refs`; keep key order stable and update projection contract to match.

Modify `create_artifact()`:

- New artifact object includes `"comment_ids": []`.

Add private append helpers:

```python
def add_comment_id_to_track(track_id: str, comment_id: str) -> dict[str, Any]:
    track = get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    require_id(comment_id, "comment id")
    if comment_id not in track["comment_ids"]:
        track["comment_ids"].append(comment_id)
        track["updated_at"] = now_iso()
    return save_track(track)


def add_comment_id_to_artifact(artifact_id: str, comment_id: str) -> dict[str, Any]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    require_id(comment_id, "comment id")
    if comment_id not in artifact["comment_ids"]:
        artifact["comment_ids"].append(comment_id)
        artifact["updated_at"] = now_iso()
    return save_artifact(artifact)
```

Add removal helper for cleanup:

```python
def remove_comment_id_from_target(target_type: str, target_id: str, comment_id: str) -> dict[str, Any] | None:
    ...
```

Use it only from cleanup or comment-delete cleanup paths; there is no env-tool `comment.delete`.

### Message/comment helpers

Add:

- `list_messages()`
- `get_message(message_id)`
- `save_message(message)`
- `create_message(*, from_buddy, to_buddy, content, reply_to=None)`
- `list_comments()`
- `get_comment(comment_id)`
- `save_comment(comment)`
- `create_comment(*, target_type, target_id, author_buddy, content, reply_to=None)`

Sorting:

- `list_messages()` sorts by `(created_at, id)` ascending for stable inbox reading.
- `list_comments()` sorts by `(created_at, id)` ascending for stable target discussion reading.

## 7. Service Behavior Design

### Shared response style

Use `env.tools.responses.success()` and `env.tools.responses.rejection()` exactly like existing services.

Rejection requirements:

- `state_changed=False` for validation/read-boundary failures.
- `permission_boundary` is precise.
- `correctable_fields` identifies payload fields when useful.
- `allowed_next_actions` points to existing tools such as `message.list`, `comment.list`, `track.get`, `artifact.get`, or `context.summarize`.
- Do not suggest handoff, review, broadcast, read receipts, comment resolution, task comments, edit, or delete.

### `scripts/env/services/messages.py`

Add `MessageServiceContext` typed dict consistent with other services.

Allowed field sets:

```python
_SEND_FIELDS = {"to_buddy", "content", "reply_to"}
_LIST_FIELDS = {"buddy"}
```

Helper behavior:

- `_buddy_ids(context)` reads manifest buddies.
- `_reject_payload(...)` returns `E_MESSAGE_PAYLOAD`, `permission_boundary="request-payload"`.
- `_reject_scope(...)` returns `E_MESSAGE_SCOPE`, with boundaries:
  - `message.self_send`
  - `message.reply_to_scope`
  - `message.buddy_scope`
- `_normalize_content(value, action, active_buddy)` trims and rejects blank/non-string content.
- `_message_visible_to_active(message, active_buddy)` is true when active buddy is either `from_buddy` or `to_buddy`; this is used only for reply validation.
- `_same_pair(message, active_buddy, to_buddy)` is true when `{from_buddy, to_buddy}` equals `{active_buddy, to_buddy}`.

`send_message(args, context)`:

1. Reject unsupported fields.
2. Validate `to_buddy` is a declared buddy.
3. Reject `to_buddy == active_buddy`.
4. Validate content.
5. If `reply_to` is present:
   - Must be a non-empty valid id.
   - Referenced message must exist.
   - Active buddy must be a participant in the referenced message.
   - Referenced message must be in the same two-buddy pair as active buddy and `to_buddy`.
6. Call `env_store.create_message(...)`.
7. Return success with:
   - `message_id`
   - `message`
   - `created_ids=[message_id]`
   - `state_changes=[{"object_type": "message", "change": "sent", "message_id": message_id}]`
   - `durability="durable"`
   - `state_changed=True`

`list_messages(args, context)`:

1. Reject unsupported fields. A payload such as `{"status": "unread"}` rejects with `E_MESSAGE_PAYLOAD`.
2. Select only `env_store.list_messages()` rows where `to_buddy == active_buddy`.
3. If `buddy` filter is present, require declared buddy id and select `from_buddy == buddy`.
4. Return success with:
   - `messages`
   - `discovery_summary={"count": len(messages)}`
   - `state_changed=False`
   - `durability="none"`
   - `read_scope="active-buddy inbox messages"`

### `scripts/env/services/comments.py`

Add `CommentServiceContext` typed dict consistent with other services.

Allowed field sets:

```python
_ADD_FIELDS = {"target_type", "target_id", "content", "reply_to"}
_LIST_FIELDS = {"target_type", "target_id"}
_TARGET_TYPES = {"track", "artifact"}
```

Helper behavior:

- `_reject_payload(...)` returns `E_COMMENT_PAYLOAD`, `permission_boundary="request-payload"`.
- `_reject_target_scope(...)` returns `E_COMMENT_TARGET_SCOPE`, preserving the underlying `permission_boundary`.
- `_normalize_target(args, active_buddy, action)` validates target type/id.
- `_readable_target(target_type, target_id, active_buddy, action)` returns target object or structured rejection:
  - Track: call `artifact_visibility.assert_track_readable(target_id, active_buddy=active_buddy, action=action)`, convert its `ok=False` result into a comment rejection with the same `code`, `message`, and `permission_boundary`.
  - Artifact: load artifact; if missing reject payload; call `artifact_visibility.artifact_read_decision(artifact, active_buddy)` and reject when `allowed` is false using the decision boundary and `why`.
- `_validate_reply_to(reply_to, target_type, target_id, active_buddy, action)`:
  - Missing/`None` is allowed.
  - Must be a valid id.
  - Referenced comment must exist.
  - Referenced comment must have the same `target_type` and `target_id`.

`add_comment(args, context)`:

1. Reject unsupported fields.
2. Validate target type and id.
3. Enforce read boundary.
4. Validate content.
5. Validate `reply_to` if present.
6. Call `env_store.create_comment(...)`.
7. Append the new comment id to the target:
   - `env_store.add_comment_id_to_track(...)` for tracks.
   - `env_store.add_comment_id_to_artifact(...)` for artifacts.
8. Return success with:
   - `comment_id`
   - `comment`
   - `target_type`
   - `target_id`
   - `created_ids=[comment_id]`
   - `updated_ids=[target_id]`
   - `state_changes` for comment creation and target comment linkage
   - `state_changed=True`
   - `durability="durable"`

`list_comments(args, context)`:

1. Reject unsupported fields.
2. Validate target type and id.
3. Enforce read boundary.
4. Read target `comment_ids`.
5. Load referenced comments, keeping only comments whose stored `target_type` and `target_id` match the target.
6. Return success with:
   - `comments`
   - `target_type`
   - `target_id`
   - `discovery_summary={"count": len(comments)}`
   - `state_changed=False`
   - `durability="none"`
   - `read_scope="target comments for readable track"` or `"target comments for readable artifact"`

## 8. Phased Implementation Plan

### Phase 1: Store Model And Test Sandbox

**Files:**

- Modify: `scripts/env_store.py`
- Modify: `tests/runtime_root_test_helper.py`
- Modify/Add tests in: `tests/test_env_store_v2.py`

**Failing tests to write first:**

- `tests/test_env_store_v2.py::MessageStoreTests::test_create_message_persists_flat_message_without_status`
- `tests/test_env_store_v2.py::CommentStoreTests::test_create_comment_persists_flat_comment_without_status`
- `tests/test_env_store_v2.py::CommentStoreTests::test_track_and_artifact_comment_ids_default_and_persist`
- `tests/test_env_store_v2.py::CommentStoreTests::test_task_records_do_not_gain_comment_ids`

**Implementation steps:**

1. Add message/comment dirs and path helpers.
2. Update `ensure_runtime_dirs()` to include new dirs.
3. Add `validate_message()` and `validate_comment()`.
4. Add list/get/save/create helpers for messages and comments.
5. Add `comment_ids` validation defaults to `validate_track()` and `validate_artifact()`.
6. Add `comment_ids: []` to `create_track()` and `create_artifact()`.
7. Add private target append/remove helpers for comment ids.
8. Patch `RuntimeWorkspaceSandbox.start()` to patch `env_store.MESSAGES_DIR` and `env_store.COMMENTS_DIR`.

**Focused verification:**

```bash
python3 -m pytest tests/test_env_store_v2.py -q
```

Expected result: new store tests pass, existing env store tests remain green.

### Phase 2: Message Tool Service, Registry, Dispatch, CLI

**Files:**

- Create: `scripts/env/services/messages.py`
- Modify: `scripts/env/tools/contracts.py`
- Modify: `scripts/env/tools/semantics.py`
- Modify: `scripts/env/tools/dispatch.py`
- Modify: `scripts/env/client.py`
- Add: `tests/test_message_env_tool.py`
- Modify: `tests/test_env_tool_router.py`
- Modify: `tests/test_env_tool_semantic_contract.py`

**Failing tests to write first:**

- `tests/test_message_env_tool.py::MessageEnvToolTests::test_send_message_creates_inbox_message_for_target_buddy`
- `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_returns_only_messages_to_active_buddy`
- `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_filters_by_sender_buddy`
- `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_rejects_status_filter`
- `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_rejects_self_send`
- `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_reply_to_requires_same_visible_conversation_pair`
- `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_tool_rejects_broadcast_and_edit_delete_actions`
- `tests/test_env_tool_router.py::EnvToolRouterTests::test_active_env_tool_surface_includes_message_and_comment_without_handoff`
- `tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_registry_semantics_cover_every_registered_tool_and_action`

**Implementation steps:**

1. Implement `scripts/env/services/messages.py` with helpers and two handlers.
2. Add `message` registry row:
   - `send`: payload fields `["to_buddy", "content", "reply_to"]`, mutates `runtime_objects`, required permission `message.send`, authority `message.direct_buddy_channel`, returns `["message_id", "message"]`.
   - `list`: payload fields `["buddy"]`, mutates `none`, required permission `message.list`, authority `message.active_buddy_inbox`, returns `["messages"]`.
3. Add semantics:
   - Capability title `Buddy Messages`.
   - `message.send` writes one durable message object only.
   - `message.list` is read-only active-buddy inbox only.
   - `do_not_use_when` explicitly points away from broadcast, read receipts, task comments, reviews, and object comments.
4. Import `messages as message_service` in dispatch and add handler map.
5. Add CLI:
   - `python3 scripts/env/client.py message send --payload /tmp/message.json`
   - `python3 scripts/env/client.py message list [--buddy design]`
6. Update expected tool sets in registry/router/semantic tests to include `message` after the message registry row and dispatch handler are implemented. Phase 3 updates the same expected sets again to include `comment`. Do not leave a registry row without matching dispatch coverage.

**Focused verification:**

```bash
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py -q
python3 scripts/env/client.py message --help
```

Expected result: message tests pass; registry/dispatch/semantic action sets match; CLI help lists `send` and `list`.

### Phase 3: Comment Tool Service And Read-Boundary Reuse

**Files:**

- Create: `scripts/env/services/comments.py`
- Modify: `scripts/env/tools/contracts.py`
- Modify: `scripts/env/tools/semantics.py`
- Modify: `scripts/env/tools/dispatch.py`
- Modify: `scripts/env/client.py`
- Add: `tests/test_comment_env_tool.py`
- Possibly modify: `scripts/env/services/artifact_visibility.py` only if a small reusable track-readable decision helper is needed.

**Failing tests to write first:**

- `tests/test_comment_env_tool.py::CommentEnvToolTests::test_add_and_list_track_comment_persists_comment_id_on_track`
- `tests/test_comment_env_tool.py::CommentEnvToolTests::test_add_and_list_artifact_comment_persists_comment_id_on_artifact`
- `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_and_list_reject_archived_track`
- `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_artifact_uses_artifact_track_relation_read_boundary`
- `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_rejects_foreign_superseded_artifact_with_currentness_boundary`
- `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_reply_to_requires_same_target`
- `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_tool_rejects_task_target_and_status_resolution_edit_delete`

**Implementation steps:**

1. Implement `scripts/env/services/comments.py` with target validation, reply validation, add/list handlers, and structured rejection helpers.
2. Use `artifact_visibility.assert_track_readable()` for track targets. If the helper returns a plain decision dict, convert it to a comment rejection preserving `code`, `message`, and `permission_boundary`.
3. Use `artifact_visibility.artifact_read_decision()` for artifact targets. Do not duplicate owner/currentness/track-relation logic.
4. Add `comment` registry row:
   - `add`: payload fields `["target_type", "target_id", "content", "reply_to"]`, mutates `runtime_objects`, required permission `comment.add`, authority `target.read_boundary`, returns `["comment_id", "comment"]`.
   - `list`: payload fields `["target_type", "target_id"]`, mutates `none`, required permission `comment.list`, authority `target.read_boundary`, returns `["comments"]`.
5. Add semantics:
   - Capability title `Object Comments`.
   - `comment.add` writes one comment object and one target `comment_ids` link.
   - `comment.list` reads target comments only after target read-boundary pass.
   - `do_not_use_when` explicitly excludes task comments, resolution, review, edit/delete, message, and broadcast.
6. Import `comments as comment_service` in dispatch and add handler map.
7. Add CLI:
   - `python3 scripts/env/client.py comment add --payload /tmp/comment.json`
   - `python3 scripts/env/client.py comment list --target-type track --target-id track-alpha`

**Focused verification:**

```bash
python3 -m pytest tests/test_comment_env_tool.py -q
python3 -m pytest tests/test_artifact_env_tool.py tests/test_track_env_tool.py -q
python3 scripts/env/client.py comment --help
```

Expected result: comment read-boundary tests pass and existing track/artifact visibility behavior remains unchanged.

### Phase 4: Manifest, Runtime Skills, Context, Projection

**Files:**

- Modify: `scripts/env_manifest.py`
- Modify: `buddyswitch/manifest.toml`
- Add: `buddyswitch/skills/shared/message-tool/SKILL.md`
- Add: `buddyswitch/skills/shared/comment-tool/SKILL.md`
- Modify: `scripts/env/services/context.py`
- Modify: `scripts/runtime_store/projections.py`
- Modify: `framework/contracts/workspace-projection.json`
- Modify tests: `tests/test_env_manifest_v2.py`, `tests/test_runtime_skills.py`, `tests/test_context_binding_env_tool.py`, `tests/test_parallel_contracts.py`, `tests/test_repo_consistency.py`, `tests/test_runless_runtime_contract.py`

**Failing tests to write first:**

- `tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_message_and_comment_permissions_are_supported`
- `tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_all_buddies_have_message_comment_tools_and_permissions`
- `tests/test_runtime_skills.py::RuntimeSkillsTests::test_each_buddy_keeps_shared_runtime_tools_without_handoff`
- `tests/test_runtime_skills.py::RuntimeSkillsTests::test_message_comment_shared_tool_skills_stay_atomic`
- `tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_exposes_message_and_comment_tool_affordances`
- `tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_list_sources_includes_message_and_comment_descriptors_without_message_rows`
- `tests/test_parallel_contracts.py::ParallelContractsTests::test_workspace_projection_exposes_comment_ids_on_tracks_and_artifacts_only`
- `tests/test_repo_consistency.py::RepoConsistencyTests::test_env_tool_surface_includes_message_comment_and_excludes_non_goals`

**Implementation steps:**

1. Add `"message"` and `"comment"` to `env_manifest._validate_permission()` supported objects.
2. Add manifest skill rows:
   - `message-tool` -> `buddyswitch/skills/shared/message-tool`
   - `comment-tool` -> `buddyswitch/skills/shared/comment-tool`
3. Add `message-tool` and `comment-tool` to each buddy `skills`.
4. Add permissions to each buddy:
   - `message.send`
   - `message.list`
   - `comment.add`
   - `comment.list`
5. Create shared skill docs matching existing concise shared tool format:
   - Purpose.
   - Runtime route.
   - Operations.
   - Key boundary rules.
   - Verification.
   - Explicit "do not" bullets for non-goals.
6. Context:
   - The tool catalog and operation semantics will include message/comment via `tool_contracts`.
   - Add source descriptors in `context_sources_desc()`:
     - `messages`: direct buddy inbox messages, read through `message.list`, not emitted in context sections.
     - `comments`: target comments, read through `comment.list`, not emitted as top-level context rows.
   - Ensure `tasks` rows do not include `comment_ids`.
7. Projection:
   - `build_artifact_view()` includes `comment_ids`.
   - `build_track_views()` includes `comment_ids`.
   - No top-level `messages` or `comments`.
8. Workspace projection contract:
   - Add `comment_ids` to track key order and field types.
   - Add `comment_ids` to artifact key order and field types.
   - Keep `top_level_key_order` unchanged.
   - Keep `data_sources` unchanged unless code exposes comment objects directly; this plan does not.

**Focused verification:**

```bash
python3 -m pytest tests/test_env_manifest_v2.py tests/test_runtime_skills.py -q
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_parallel_contracts.py -q
python3 -m pytest tests/test_repo_consistency.py tests/test_runless_runtime_contract.py -q
```

Expected result: manifest/skills/context/projection reflect message/comment and keep all non-goals absent.

### Phase 5: Launcher Projected State And Cleanup

**Files:**

- Modify: `tools/launcher/workspace.sh`
- Modify: `scripts/env_cleanup.py`
- Modify tests: `tests/test_buddyswitch_launcher.py`, `tests/test_cleanup_system.py`

**Failing tests to write first:**

- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_projects_message_and_comment_state_dirs`
- `tests/test_cleanup_system.py::CleanupSystemTests::test_execute_all_data_cleanup_recreates_message_comment_skeleton_dirs`
- `tests/test_cleanup_system.py::CleanupSystemTests::test_cleanup_plan_includes_message_and_comment_objects`
- `tests/test_cleanup_system.py::CleanupSystemTests::test_buddy_cleanup_removes_buddy_messages_and_authored_comments`

**Implementation steps:**

1. Add to `buddyswitch_workspace_runtime_managed_paths()`:
   - `buddyswitch/objects/messages`
   - `buddyswitch/objects/comments`
2. Update any launcher tests with `projection_pairs` to include messages/comments.
3. In `scripts/env_cleanup.py`:
   - Extend `CATEGORY_ORDER` with `message_objects` and `comment_objects`.
   - Extend `new_plan()` with `message_object_ids`, `comment_object_ids`, `message_records`, `comment_records`.
   - Add `discover_message_objects()` reading `id`, `from_buddy`, `to_buddy`, `object_path`.
   - Add `discover_comment_objects()` reading `id`, `author_buddy`, `target_type`, `target_id`, `object_path`.
   - For `scope="all-data"`, add dirs:
     - `buddyswitch/objects/messages`
     - `buddyswitch/objects/comments`
   - For `scope="buddy"`, delete messages where `from_buddy == buddy` or `to_buddy == buddy`.
   - For `scope="buddy"`, delete comments where `author_buddy == buddy`.
   - For `scope="buddy"`, when deleting an artifact owned by the buddy, also delete comments attached to that artifact to avoid orphaned artifact comments.
   - Before deleting a comment whose target survives, remove the comment id from the target `comment_ids`.
   - Update `ensure_required_skeleton()` to recreate message/comment dirs.
   - Update JSON/text output to include counts and ids for message/comment categories.

**Focused verification:**

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_projects_message_and_comment_state_dirs -q
python3 -m pytest tests/test_cleanup_system.py -q
```

Expected result: launcher projects new object dirs and cleanup handles them safely.

### Phase 6: Broad Contract Alignment And Residue Checks

**Files:**

- Modify only tests and docs already listed if failures expose expected-surface drift.
- Do not add any new capability beyond memo scope.

**Failing tests to add if missing coverage remains:**

- `tests/test_env_tool_router.py::EnvToolRouterTests::test_message_comment_non_goal_actions_are_unsupported`
- `tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_message_comment_skills_do_not_teach_non_goals`
- `tests/test_repo_consistency.py::RepoConsistencyTests::test_message_comment_non_goal_surface_absent`

**Implementation steps:**

1. Update any `_EXPECTED_TOOLS` constants to:

```python
{"task", "track", "artifact", "buddybox", "context", "evidence", "search", "message", "comment"}
```

2. Update help/status tests to assert:
   - `message` and `comment` present.
   - `handoff`, `run`, `binding`, `memory` still absent.
3. Add residue scans that allow old dated memo/spec docs but reject active code/skills/contracts guidance for:
   - `read receipt`
   - `comment resolution`
   - `task comment`
   - `broadcast`
   - `message.status`
   - `comment.status`
   - `message.delete`
   - `comment.delete`
4. Run all focused and broad verification.

**Focused verification:**

```bash
python3 -m pytest tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py tests/test_context_binding_env_tool.py tests/test_repo_consistency.py -q
```

Expected result: runtime surface is exactly the intended tool set and non-goals stay absent.

## 9. Final Verification Commands

Run focused tests first:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_comment_env_tool.py -q
python3 -m pytest tests/test_env_store_v2.py -q
```

Run registry, manifest, context, projection, runtime skill, and launcher/cleanup contract tests:

```bash
python3 -m pytest \
  tests/test_env_tool_router.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_manifest_v2.py \
  tests/test_runtime_skills.py \
  tests/test_parallel_contracts.py \
  tests/test_repo_consistency.py \
  tests/test_runless_runtime_contract.py \
  tests/test_cleanup_system.py \
  -q
```

Run launcher projection test subset:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Run existing visibility tests to prove comment did not fork artifact/track boundaries:

```bash
python3 -m pytest tests/test_artifact_env_tool.py tests/test_track_env_tool.py -q
```

Run CLI smoke:

```bash
python3 scripts/env/client.py message --help
python3 scripts/env/client.py comment --help
python3 scripts/turn_runtime.py status
```

Expected final state:

- All commands exit 0.
- `turn_runtime.py status` includes `message` and `comment` in `env_tools`.
- No verification relies on direct edits under `buddyswitch/objects/**`.
