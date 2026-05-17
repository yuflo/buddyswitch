# Buddy Collaboration Message Comment Test Plan

## 1. Test Objective

Prove BuddySwitch has two new atomic collaboration tools:

- `message`: buddy-to-buddy direct inbox messaging.
- `comment`: comments on readable track and artifact targets.

Tests must start from product requirements and risk. They must not be shaped to merely pass the current implementation. The important proof is that messages and comments work end-to-end through env.tool while all explicitly excluded collaboration features remain absent.

## 2. Test Design Rules

- Prefer broker-routed `env.tool` tests for user-visible behavior.
- Use `RuntimeWorkspaceTestMixin` for durable runtime object writes.
- Assert stored JSON only where persistence is part of the requirement.
- Assert structured rejection fields, especially `permission_boundary`, for read-boundary risks.
- Do not directly edit `buddyswitch/objects/**` in product-mode tests; use `env_store` helpers inside isolated test sandboxes.
- Non-goals need negative tests. Unsupported payload fields/actions must fail instead of being silently ignored.
- Do not test implementation helpers unless the behavior is otherwise hard to observe.

## 3. Requirement Matrix

| Area | Requirement | Primary tests |
| --- | --- | --- |
| Tool registry / semantics / dispatch | `message` and `comment` are registered, semantically covered, dispatchable, and exposed in runtime status. | `MCT-REG-001` to `MCT-REG-004` |
| Manifest permissions and validator | Manifest validator accepts `message`/`comment`; every buddy has skills and permissions. | `MCT-MAN-001` to `MCT-MAN-003` |
| Message send/list behavior | Direct send persists one message; list returns active-buddy inbox only; sender filter works. | `MCT-MSG-001` to `MCT-MSG-004` |
| Message validation and visibility | Self-send, unknown buddy, blank content, status filters, broadcast fields, and unsupported edit/delete fail. | `MCT-MSG-005` to `MCT-MSG-010` |
| Reply validation | Message reply references same visible conversation pair; comment reply references same target. | `MCT-REPLY-001` to `MCT-REPLY-004` |
| Comment add/list behavior | Add/list track and artifact comments; persistence updates `comment_ids`. | `MCT-COM-001` to `MCT-COM-004` |
| Comment target read boundary | Archived tracks reject; artifact comments reuse artifact visibility; foreign superseded artifacts cannot be read through comments. | `MCT-COM-005` to `MCT-COM-009` |
| Track/artifact comment_ids | Existing objects normalize missing `comment_ids`; new objects persist field; task records do not. | `MCT-MODEL-001` to `MCT-MODEL-004` |
| Projection/context/CLI/runtime skill exposure | Context catalog, projection, CLI help, runtime skills, and status expose message/comment correctly. | `MCT-SURF-001` to `MCT-SURF-007` |
| Launcher projected state and cleanup | Launcher projects message/comment state dirs; cleanup handles dirs and skeleton recreation. | `MCT-RUN-001` to `MCT-RUN-004` |
| Negative / non-goal coverage | No task comments, broadcast, edit/delete, read receipt, message status, comment status, or resolution. | `MCT-NON-001` to `MCT-NON-008` |

## 4. Test Cases

### `MCT-REG-001`: registry includes message and comment tools

- **Scenario:** Runtime tool catalog is the source of truth for env-tool availability.
- **Preconditions:** No runtime object state required.
- **Operation:** Import `env.tools.contracts` and inspect `TOOL_REGISTRY`, `env_tools_description()`, `operation_semantics()`, and `compact_tool_affordances()`.
- **Expected:** Tool set is exactly `{"task", "track", "artifact", "buddybox", "context", "evidence", "search", "message", "comment"}`. `message.send`, `message.list`, `comment.add`, and `comment.list` exist. `handoff` remains absent.
- **Risk:** Registry drift can expose a tool in docs/status but not in runtime routing.
- **Suggested test:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_active_env_tool_surface_includes_message_and_comment_without_handoff`
- **Run:** `python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_active_env_tool_surface_includes_message_and_comment_without_handoff -q`

### `MCT-REG-002`: semantic coverage is complete

- **Scenario:** Every registered action has machine-readable semantics for context discovery.
- **Preconditions:** No runtime state required.
- **Operation:** Call `contracts.semantic_contract_errors()` and compare operations/payload fields/action semantics for each registry row.
- **Expected:** No semantic coverage errors; message/comment action payload fields match registry.
- **Risk:** Missing semantics causes context catalog to return incomplete guidance.
- **Suggested test:** `tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_registry_semantics_cover_every_registered_tool_and_action`
- **Run:** `python3 -m pytest tests/test_env_tool_semantic_contract.py -q`

### `MCT-REG-003`: dispatch handlers match registry actions

- **Scenario:** Router can invoke every registered action.
- **Preconditions:** No runtime object state required.
- **Operation:** Compare `dispatch.dispatch_handler_actions()` with registry-derived action sets.
- **Expected:** Dispatch includes `message.send`, `message.list`, `comment.add`, `comment.list` and has no extra actions.
- **Risk:** Registry says a tool exists but broker calls fail with missing handler.
- **Suggested test:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions`
- **Run:** `python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions -q`

### `MCT-REG-004`: runtime status exposes message and comment

- **Scenario:** Skills inspect runtime status to discover env tools.
- **Preconditions:** Local checkout.
- **Operation:** Run `python3 scripts/turn_runtime.py status`.
- **Expected:** JSON `ok=true`; `env_tools` contains `message` and `comment`; old retired tools remain absent.
- **Risk:** Runtime status and registry can diverge.
- **Suggested test:** `tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_status_exposes_message_comment_env_tools`
- **Run:** `python3 -m pytest tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_status_exposes_message_comment_env_tools -q`

### `MCT-MAN-001`: manifest validator accepts message/comment permission objects

- **Scenario:** Manifest permissions are validated before runtime skills materialize.
- **Preconditions:** Import `env_manifest`.
- **Operation:** Call `_validate_permission("message.send", "synthetic")` and `_validate_permission("comment.list", "synthetic")`.
- **Expected:** No exception for message/comment permissions.
- **Risk:** Manifest update can be blocked by validator even if tool code exists.
- **Suggested test:** `tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_message_and_comment_permissions_are_supported`
- **Run:** `python3 -m pytest tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_message_and_comment_permissions_are_supported -q`

### `MCT-MAN-002`: every buddy has message/comment skills and permissions

- **Scenario:** Every active buddy should be able to communicate and comment.
- **Preconditions:** Load `buddyswitch/manifest.toml`.
- **Operation:** Inspect each buddy `skills` and `permissions`.
- **Expected:** Each buddy includes `message-tool`, `comment-tool`, `message.send`, `message.list`, `comment.add`, and `comment.list`.
- **Risk:** Some buddy cannot use collaboration tools after launch.
- **Suggested test:** `tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_all_buddies_have_message_comment_tools_and_permissions`
- **Run:** `python3 -m pytest tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_all_buddies_have_message_comment_tools_and_permissions -q`

### `MCT-MAN-003`: runtime skill materialization includes new shared tools

- **Scenario:** Launcher installs skills from manifest for each buddy.
- **Preconditions:** Existing fake launcher materialization test.
- **Operation:** Start fake instance for each buddy and list `.agents/skills`.
- **Expected:** Installed skill ids match manifest and include `message-tool` and `comment-tool`.
- **Risk:** Manifest is correct but launcher misses the new skill packages.
- **Suggested test:** `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy`
- **Run:** `python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy -q`

### `MCT-MSG-001`: send creates a durable inbox message

- **Scenario:** Design sends Dev a direct message.
- **Preconditions:** Runtime workspace instance with active buddy `design`.
- **Operation:** Broker dispatch `message.send` with `{"to_buddy":"dev","content":"Please inspect the prototype."}`.
- **Expected:** `ok=true`; returned message has `from_buddy="design"`, `to_buddy="dev"`, content, `reply_to=null`, `created_at`, and no `status`; JSON exists under `buddyswitch/objects/messages`.
- **Risk:** Message tool may return success without durable object persistence.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_send_message_creates_inbox_message_for_target_buddy`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_send_message_creates_inbox_message_for_target_buddy -q`

### `MCT-MSG-002`: message.list returns only messages to active buddy

- **Scenario:** Dev opens inbox after several buddies sent messages, while Dev's own sent messages also exist.
- **Preconditions:** Seed messages: `design -> dev`, `pm -> dev`, `dev -> design`, `market -> pm`.
- **Operation:** Active buddy `dev` dispatches `message.list {}`.
- **Expected:** Returned ids are only messages whose `to_buddy == "dev"`; Dev's sent message is absent; PM inbox message is absent.
- **Risk:** Inbox read leaks other buddy messages or sent-mail rows.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_returns_only_messages_to_active_buddy`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_returns_only_messages_to_active_buddy -q`

### `MCT-MSG-003`: message.list filters by sender buddy

- **Scenario:** Dev wants only Design messages in its inbox.
- **Preconditions:** Dev inbox has one message from Design and one from PM.
- **Operation:** Active buddy `dev` dispatches `message.list {"buddy":"design"}`.
- **Expected:** Only Design-to-Dev rows are returned.
- **Risk:** Sender filter could be interpreted as recipient or leak sent messages.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_filters_by_sender_buddy`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_filters_by_sender_buddy -q`

### `MCT-MSG-004`: message.list is read-only

- **Scenario:** Dev lists inbox repeatedly.
- **Preconditions:** Dev inbox has at least one message.
- **Operation:** Dispatch `message.list {}` twice and compare stored message JSON before/after.
- **Expected:** `state_changed=false`, `durability="none"`, message JSON unchanged, no read receipt field added.
- **Risk:** A status/read-receipt mutation can creep in through list behavior.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_does_not_mutate_read_state`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_does_not_mutate_read_state -q`

### `MCT-MSG-005`: message.send rejects self-send

- **Scenario:** Dev accidentally sends a direct message to Dev.
- **Preconditions:** Active buddy `dev`.
- **Operation:** Dispatch `message.send {"to_buddy":"dev","content":"self"}`.
- **Expected:** `ok=false`, error code `E_MESSAGE_SCOPE`, `permission_boundary="message.self_send"`, `state_changed=false`, no message object file.
- **Risk:** Self-send creates noisy inbox rows and weakens buddy-to-buddy semantics.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_rejects_self_send`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_rejects_self_send -q`

### `MCT-MSG-006`: message.send rejects unknown target buddy

- **Scenario:** Dev sends to a non-manifest buddy id.
- **Preconditions:** Active buddy `dev`.
- **Operation:** Dispatch `message.send {"to_buddy":"ops","content":"hello"}`.
- **Expected:** `ok=false`, error code `E_MESSAGE_PAYLOAD`, `permission_boundary="request-payload"`, `state_changed=false`.
- **Risk:** Invalid buddy ids create unreadable durable objects.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_rejects_unknown_target_buddy`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_rejects_unknown_target_buddy -q`

### `MCT-MSG-007`: message.send rejects blank content

- **Scenario:** PM sends an empty message.
- **Preconditions:** Active buddy `pm`.
- **Operation:** Dispatch `message.send {"to_buddy":"dev","content":"   "}`.
- **Expected:** `ok=false`, `E_MESSAGE_PAYLOAD`, `correctable_fields` includes `content`, no file written.
- **Risk:** Empty collaboration artifacts reduce signal and create ambiguous state.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_rejects_blank_content`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_rejects_blank_content -q`

### `MCT-MSG-008`: message.list has no status filter

- **Scenario:** Host tries to list unread messages.
- **Preconditions:** Active buddy `dev`.
- **Operation:** Dispatch `message.list {"status":"unread"}`.
- **Expected:** `ok=false`, `E_MESSAGE_PAYLOAD`, `correctable_fields` includes `status`, `state_changed=false`.
- **Risk:** Status filter implies read-state semantics that do not exist.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_rejects_status_filter`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_rejects_status_filter -q`

### `MCT-MSG-009`: message.send rejects broadcast fields

- **Scenario:** Host attempts group messaging.
- **Preconditions:** Active buddy `pm`.
- **Operation:** Dispatch payloads with `broadcast=true` or `recipients=["dev","design"]`.
- **Expected:** `ok=false`, `E_MESSAGE_PAYLOAD`, no messages written.
- **Risk:** Broadcast is explicitly excluded and should be composed by skill-level repeated sends later if needed.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_rejects_broadcast_payload_fields`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_rejects_broadcast_payload_fields -q`

### `MCT-MSG-010`: message edit/delete actions are unsupported

- **Scenario:** Host tries to modify or delete a message.
- **Preconditions:** Message may exist but is not required.
- **Operation:** Dispatch `message.update`, `message.edit`, and `message.delete`.
- **Expected:** Router rejects with `E_ENV_TOOL`, `permission_boundary="env.tool"`, `state_changed=false`.
- **Risk:** Mutation actions would contradict immutable message contract.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_edit_delete_actions_are_unsupported`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_edit_delete_actions_are_unsupported -q`

### `MCT-REPLY-001`: message reply_to accepts same visible conversation pair

- **Scenario:** Dev replies to a PM-to-Dev message.
- **Preconditions:** Seed message `pm -> dev` and capture its id.
- **Operation:** Active buddy `dev` dispatches `message.send {"to_buddy":"pm","content":"ack","reply_to":"<pm-dev-id>"}`.
- **Expected:** `ok=true`; new message has `reply_to` set to the referenced id.
- **Risk:** Threading may be unusable if valid inbox replies are rejected.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_reply_to_accepts_same_visible_conversation_pair`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_reply_to_accepts_same_visible_conversation_pair -q`

### `MCT-REPLY-002`: message reply_to rejects different pair or invisible message

- **Scenario:** Dev tries to reply to a Design-PM message while sending to PM.
- **Preconditions:** Seed message `design -> pm`; active buddy `dev`.
- **Operation:** Dispatch `message.send {"to_buddy":"pm","content":"bad","reply_to":"<design-pm-id>"}`.
- **Expected:** `ok=false`, permission boundary `message.reply_to_scope`, no new message file.
- **Risk:** Reply ids can leak or connect unrelated conversations.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_reply_to_requires_same_visible_conversation_pair`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_reply_to_requires_same_visible_conversation_pair -q`

### `MCT-REPLY-003`: comment reply_to accepts same target

- **Scenario:** Design replies to a comment on one artifact.
- **Preconditions:** Readable artifact exists; first comment attached to it.
- **Operation:** Active buddy `design` dispatches `comment.add` to same artifact with `reply_to` first comment id.
- **Expected:** `ok=true`; returned comment has `reply_to`; target `comment_ids` includes both comments.
- **Risk:** Comment threading must stay local to the target discussion.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_reply_to_accepts_same_target`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_reply_to_accepts_same_target -q`

### `MCT-REPLY-004`: comment reply_to rejects different target

- **Scenario:** PM tries to reply on Track B to a comment attached to Track A.
- **Preconditions:** Two active tracks; comment exists on Track A.
- **Operation:** Dispatch `comment.add {"target_type":"track","target_id":"track-b","content":"bad","reply_to":"<track-a-comment>"}`.
- **Expected:** `ok=false`, error code `E_COMMENT_REPLY_SCOPE`, `permission_boundary="comment.reply_to_scope"`, no comment file, Track B `comment_ids` unchanged.
- **Risk:** Cross-target replies break target-local discussion history.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_reply_to_requires_same_target`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_reply_to_requires_same_target -q`

### `MCT-COM-001`: add/list track comment persists on track

- **Scenario:** Design comments on an active track.
- **Preconditions:** Active track exists.
- **Operation:** Active buddy `design` dispatches `comment.add` with `target_type="track"`, then `comment.list` for the same target.
- **Expected:** Comment object exists; stored track `comment_ids` includes the id; list returns that comment; no task object changes.
- **Risk:** Comment object can be created without being discoverable from target.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_add_and_list_track_comment_persists_comment_id_on_track`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_add_and_list_track_comment_persists_comment_id_on_track -q`

### `MCT-COM-002`: add/list artifact comment persists on artifact

- **Scenario:** Dev comments on a readable artifact.
- **Preconditions:** Artifact exists and is readable by active buddy.
- **Operation:** Dispatch `comment.add` with `target_type="artifact"`, then `comment.list`.
- **Expected:** Comment object exists; artifact `comment_ids` includes id; list returns comment.
- **Risk:** Artifact comments may not survive artifact persistence/validation.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_add_and_list_artifact_comment_persists_comment_id_on_artifact`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_add_and_list_artifact_comment_persists_comment_id_on_artifact -q`

### `MCT-COM-003`: comment.add rejects blank content

- **Scenario:** PM adds an empty track comment.
- **Preconditions:** Active track exists.
- **Operation:** Dispatch `comment.add {"target_type":"track","target_id":"track-x","content":" "}`.
- **Expected:** `ok=false`, `E_COMMENT_PAYLOAD`, `correctable_fields` includes `content`, no comment file.
- **Risk:** Empty comments reduce discussion quality and complicate UI rendering later.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_rejects_blank_content`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_rejects_blank_content -q`

### `MCT-COM-004`: comment.list is read-only

- **Scenario:** Test buddy lists comments on an artifact repeatedly.
- **Preconditions:** Artifact has one comment.
- **Operation:** Dispatch `comment.list` twice and compare stored target/comment JSON before/after.
- **Expected:** `state_changed=false`, `durability="none"`, stored JSON unchanged.
- **Risk:** List can accidentally update target timestamps or add read markers.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_list_does_not_mutate_state`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_list_does_not_mutate_state -q`

### `MCT-COM-005`: archived track rejects comment.add

- **Scenario:** Dev tries to comment on an archived track.
- **Preconditions:** Track exists with `status="archived"`.
- **Operation:** Dispatch `comment.add {"target_type":"track","target_id":"track-arch","content":"x"}`.
- **Expected:** `ok=false`; permission boundary `track.lifecycle_status`; no comment object.
- **Risk:** Comments can bypass archived-track read boundary.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_rejects_archived_track`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_rejects_archived_track -q`

### `MCT-COM-006`: archived track rejects comment.list

- **Scenario:** Dev tries to list comments on an archived track.
- **Preconditions:** Archived track exists; it may have stale `comment_ids`.
- **Operation:** Dispatch `comment.list {"target_type":"track","target_id":"track-arch"}`.
- **Expected:** `ok=false`; permission boundary `track.lifecycle_status`; no comments returned.
- **Risk:** Comment list can leak archived collaboration discussion.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_list_rejects_archived_track`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_list_rejects_archived_track -q`

### `MCT-COM-007`: artifact comment uses active track relation read boundary

- **Scenario:** Dev comments on a PM artifact only after joining the artifact's active track.
- **Preconditions:** Active track with PM current artifact; Dev active task relation exists on same track.
- **Operation:** Active Dev dispatches `comment.add` on PM artifact.
- **Expected:** `ok=true`; artifact comment persists; relation was granted by `artifact.track_relation` rules, not ownership.
- **Risk:** Comment service might duplicate or weaken artifact read logic.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_artifact_uses_artifact_track_relation_read_boundary`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_artifact_uses_artifact_track_relation_read_boundary -q`

### `MCT-COM-008`: foreign artifact without track relation rejects

- **Scenario:** Dev tries to comment on PM artifact without a Dev task relation on the track.
- **Preconditions:** PM artifact under active track; Dev has no task on that track.
- **Operation:** Active Dev dispatches `comment.add` on PM artifact.
- **Expected:** `ok=false`, permission boundary `artifact.track_relation`, no comment object.
- **Risk:** Comment tool can become a second, looser artifact authorization surface.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_artifact_rejects_missing_track_relation`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_artifact_rejects_missing_track_relation -q`

### `MCT-COM-009`: foreign superseded artifact cannot be commented or listed

- **Scenario:** Dev has track relation but references PM's superseded artifact revision.
- **Preconditions:** Active track with PM artifact revisions r1 superseded by r2; Dev active task relation exists.
- **Operation:** Active Dev dispatches `comment.add` and `comment.list` for r1.
- **Expected:** `ok=false`, permission boundary `artifact.currentness`, no content or comments leak.
- **Risk:** Comments could bypass current-artifact rule for historical foreign artifacts.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_and_list_reject_foreign_superseded_artifact`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_add_and_list_reject_foreign_superseded_artifact -q`

### `MCT-MODEL-001`: existing track/artifact records normalize missing comment_ids

- **Scenario:** Old runtime objects exist before comment feature.
- **Preconditions:** Write or create track/artifact records without `comment_ids` through existing helpers/fixtures.
- **Operation:** Read through `env_store.get_track()` and `env_store.get_artifact()`.
- **Expected:** Returned objects include `comment_ids=[]`; saving persists the field.
- **Risk:** Existing data breaks validation after adding required comment linkage.
- **Suggested test:** `tests/test_env_store_v2.py::CommentStoreTests::test_track_and_artifact_comment_ids_default_and_persist`
- **Run:** `python3 -m pytest tests/test_env_store_v2.py::CommentStoreTests::test_track_and_artifact_comment_ids_default_and_persist -q`

### `MCT-MODEL-002`: new track/artifact records persist comment_ids

- **Scenario:** New objects are created after comment feature lands.
- **Preconditions:** Runtime sandbox.
- **Operation:** `env_store.create_track()` and `env_store.create_artifact()`.
- **Expected:** Stored JSON includes `comment_ids: []`.
- **Risk:** New records differ from normalized records and projection becomes inconsistent.
- **Suggested test:** `tests/test_env_store_v2.py::CommentStoreTests::test_new_track_and_artifact_records_persist_empty_comment_ids`
- **Run:** `python3 -m pytest tests/test_env_store_v2.py::CommentStoreTests::test_new_track_and_artifact_records_persist_empty_comment_ids -q`

### `MCT-MODEL-003`: task records do not gain comment_ids

- **Scenario:** Task comments are excluded.
- **Preconditions:** Runtime sandbox.
- **Operation:** Create a task and read stored task JSON.
- **Expected:** No `comment_ids` field on task.
- **Risk:** Task comment support can creep in through shared model changes.
- **Suggested test:** `tests/test_env_store_v2.py::CommentStoreTests::test_task_records_do_not_gain_comment_ids`
- **Run:** `python3 -m pytest tests/test_env_store_v2.py::CommentStoreTests::test_task_records_do_not_gain_comment_ids -q`

### `MCT-MODEL-004`: invalid comment target type is rejected at store and service boundary

- **Scenario:** A caller attempts a task comment.
- **Preconditions:** Task exists.
- **Operation:** Dispatch `comment.add {"target_type":"task","target_id":"task-dev-x","content":"x"}` and call `env_store.validate_comment()` with `target_type="task"` in store-level test.
- **Expected:** Service rejects with `E_COMMENT_PAYLOAD`; store validator raises `ValueError`; no comment file.
- **Risk:** Task comments are explicitly excluded.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_tool_rejects_task_target`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_tool_rejects_task_target -q`

### `MCT-SURF-001`: context summarize exposes message/comment affordances

- **Scenario:** Host asks for compact runtime orientation.
- **Preconditions:** Runtime instance.
- **Operation:** Dispatch `context.summarize {}`.
- **Expected:** `tool_affordances` contains `message` and `comment`; no status/read receipt/resolution affordance.
- **Risk:** Skills cannot discover the new tools without reading code.
- **Suggested test:** `tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_exposes_message_and_comment_tool_affordances`
- **Run:** `python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_exposes_message_and_comment_tool_affordances -q`

### `MCT-SURF-002`: context list_sources describes message/comment without leaking records

- **Scenario:** Host lists context sources.
- **Preconditions:** Runtime instance with some messages/comments.
- **Operation:** Dispatch `context.list_sources {}` and `context.get {}`.
- **Expected:** Source descriptors include messages/comments as tool-readable sources; context sections do not include top-level message/comment record lists.
- **Risk:** Context can leak inbox or comment bodies outside tool boundaries.
- **Suggested test:** `tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_list_sources_includes_message_and_comment_descriptors_without_message_rows`
- **Run:** `python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_list_sources_includes_message_and_comment_descriptors_without_message_rows -q`

### `MCT-SURF-003`: CLI help exposes message/comment commands

- **Scenario:** Runtime skills use `scripts/env/client.py`.
- **Preconditions:** Local checkout.
- **Operation:** Run `python3 scripts/env/client.py message --help` and `python3 scripts/env/client.py comment --help`.
- **Expected:** Message help lists `send` and `list`; comment help lists `add` and `list`; no `delete`, `edit`, `resolve`, `broadcast`, or `read-receipt` commands.
- **Risk:** CLI surface can drift from tool registry.
- **Suggested test:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_cli_exposes_message_comment_resources_only`
- **Run:** `python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_cli_exposes_message_comment_resources_only -q`

### `MCT-SURF-004`: workspace projection exposes comment_ids on tracks/artifacts only

- **Scenario:** Context panel reads workspace projection.
- **Preconditions:** Track and artifact each have a comment id.
- **Operation:** Call `workspace_data.build_workspace_data()`.
- **Expected:** Track view has `comment_ids`; artifact view has `comment_ids`; task views do not; top-level projection keys do not include `messages` or `comments`.
- **Risk:** UI projection can leak message/comment records or omit target comment linkage.
- **Suggested test:** `tests/test_parallel_contracts.py::ParallelContractsTests::test_workspace_projection_exposes_comment_ids_on_tracks_and_artifacts_only`
- **Run:** `python3 -m pytest tests/test_parallel_contracts.py::ParallelContractsTests::test_workspace_projection_exposes_comment_ids_on_tracks_and_artifacts_only -q`

### `MCT-SURF-005`: workspace projection contract matches runtime payload

- **Scenario:** JSON contract is the public projection contract.
- **Preconditions:** Load `framework/contracts/workspace-projection.json`.
- **Operation:** Compare contract `view_shapes.track` and `view_shapes.artifact` with runtime payload keys.
- **Expected:** `comment_ids` in track/artifact key orders and field types; no task `comment_ids`; no top-level messages/comments.
- **Risk:** Contract and projection can diverge.
- **Suggested test:** `tests/test_parallel_contracts.py::ParallelContractsTests::test_workspace_projection_runtime_payload_matches_contract_surface`
- **Run:** `python3 -m pytest tests/test_parallel_contracts.py::ParallelContractsTests::test_workspace_projection_runtime_payload_matches_contract_surface -q`

### `MCT-SURF-006`: shared message/comment skills stay atomic

- **Scenario:** Runtime skill docs guide tool use.
- **Preconditions:** Read `buddyswitch/skills/shared/message-tool/SKILL.md` and `comment-tool/SKILL.md`.
- **Operation:** Scan text.
- **Expected:** Skills mention env.tool route and operations; they do not teach handoff, broadcast, read receipts, review, task comments, edit/delete, or resolution workflows.
- **Risk:** Workflow or excluded features creep into skill layer.
- **Suggested test:** `tests/test_runtime_skills.py::RuntimeSkillsTests::test_message_comment_shared_tool_skills_stay_atomic`
- **Run:** `python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_message_comment_shared_tool_skills_stay_atomic -q`

### `MCT-SURF-007`: active repo consistency scan keeps non-goals absent

- **Scenario:** Active runtime surfaces should not teach excluded capabilities.
- **Preconditions:** Repository checkout.
- **Operation:** Scan active code/skills/contracts excluding dated memo/spec history where needed.
- **Expected:** No active instructions implement or require handoff, review, whiteboard, broadcast, read receipts, task comments, comment resolution/status, or edit/delete actions.
- **Risk:** Non-goals can enter through docs or skills without service support.
- **Suggested test:** `tests/test_repo_consistency.py::RepoConsistencyTests::test_message_comment_non_goal_surface_absent`
- **Run:** `python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_message_comment_non_goal_surface_absent -q`

### `MCT-RUN-001`: launcher projects message/comment shared state dirs

- **Scenario:** New runtime instance starts and gets projected object dirs.
- **Preconditions:** Existing fake launcher instance-start test.
- **Operation:** Start PM instance and inspect workspace paths.
- **Expected:** `buddyswitch/objects/messages` and `buddyswitch/objects/comments` are symlinks to shared state dirs, same as tracks/tasks/artifacts.
- **Risk:** Env tools write to workspace-local dirs that are not shared across instances.
- **Suggested test:** `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_projects_message_and_comment_state_dirs`
- **Run:** `python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_projects_message_and_comment_state_dirs -q`

### `MCT-RUN-002`: runtime sandbox patches message/comment dirs

- **Scenario:** Focused tests write to isolated runtime root.
- **Preconditions:** `RuntimeWorkspaceTestMixin` starts.
- **Operation:** Create message/comment through env_store and inspect paths.
- **Expected:** Files appear under test runtime root, not source checkout.
- **Risk:** Tests accidentally write to real source runtime state.
- **Suggested test:** Covered by `tests/test_message_env_tool.py` and `tests/test_comment_env_tool.py`; add explicit `tests/test_env_store_v2.py::CommentStoreTests::test_message_comment_dirs_are_runtime_sandboxed` if failures are confusing.
- **Run:** `python3 -m pytest tests/test_message_env_tool.py tests/test_comment_env_tool.py -q`

### `MCT-RUN-003`: all-data cleanup deletes and recreates message/comment skeleton dirs

- **Scenario:** User runs cleanup for all data.
- **Preconditions:** Temp repo root has tracks/tasks/artifacts/messages/comments files.
- **Operation:** `env_cleanup.build_cleanup_plan(scope="all-data")`, then `execute_cleanup_plan`.
- **Expected:** Message/comment files deleted; directories recreated with tracks/tasks/artifacts dirs.
- **Risk:** Cleanup leaves stale collaboration data or removes required skeleton dirs.
- **Suggested test:** `tests/test_cleanup_system.py::CleanupSystemTests::test_execute_all_data_cleanup_recreates_message_comment_skeleton_dirs`
- **Run:** `python3 -m pytest tests/test_cleanup_system.py::CleanupSystemTests::test_execute_all_data_cleanup_recreates_message_comment_skeleton_dirs -q`

### `MCT-RUN-004`: buddy cleanup handles buddy messages and comments

- **Scenario:** Cleanup targets one buddy.
- **Preconditions:** Temp repo root has messages involving `dev`, comments authored by `dev`, and comments by other buddies.
- **Operation:** Build and execute cleanup plan with `scope="buddy", buddy="dev"`.
- **Expected:** Messages where `from_buddy` or `to_buddy` is `dev` are deleted; comments authored by `dev` are deleted and detached from surviving targets; unrelated comments remain.
- **Risk:** Buddy cleanup leaves private communication residue or corrupts target `comment_ids`.
- **Suggested test:** `tests/test_cleanup_system.py::CleanupSystemTests::test_buddy_cleanup_removes_buddy_messages_and_authored_comments`
- **Run:** `python3 -m pytest tests/test_cleanup_system.py::CleanupSystemTests::test_buddy_cleanup_removes_buddy_messages_and_authored_comments -q`

### `MCT-NON-001`: no task comment support

- **Scenario:** Host tries to comment on a task.
- **Preconditions:** Task exists.
- **Operation:** Dispatch `comment.add` and `comment.list` with `target_type="task"`.
- **Expected:** Both reject with `E_COMMENT_PAYLOAD`; task JSON has no `comment_ids`.
- **Risk:** Task comments are explicitly deferred.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_tool_rejects_task_target`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_tool_rejects_task_target -q`

### `MCT-NON-002`: no broadcast support

- **Scenario:** Host attempts one-to-many messaging.
- **Preconditions:** Active buddy `pm`.
- **Operation:** Dispatch `message.send` with `broadcast`, `recipients`, or `to_buddies`.
- **Expected:** Rejects as unsupported payload fields; no messages written.
- **Risk:** Broadcast is explicitly excluded from the atomic tool layer.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_rejects_broadcast_payload_fields`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_send_rejects_broadcast_payload_fields -q`

### `MCT-NON-003`: no message read receipt

- **Scenario:** Host tries to mark messages read.
- **Preconditions:** Message exists.
- **Operation:** Dispatch `message.mark_read`, `message.read`, or `message.list {"read": false}`.
- **Expected:** Unsupported action/payload; stored message has no `read_at` or `read_by`.
- **Risk:** Read receipts imply status mutation absent from design.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_read_receipt_actions_and_fields_are_unsupported`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_read_receipt_actions_and_fields_are_unsupported -q`

### `MCT-NON-004`: no message status

- **Scenario:** Host tries to send or list messages by status.
- **Preconditions:** Active buddy.
- **Operation:** Dispatch `message.send {"status":"unread"}` and `message.list {"status":"unread"}`.
- **Expected:** Both reject; persisted messages never include `status`.
- **Risk:** Status field creates a hidden state machine.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_status_fields_are_rejected`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_status_fields_are_rejected -q`

### `MCT-NON-005`: no message edit/delete

- **Scenario:** Host tries to change a sent message.
- **Preconditions:** Message exists.
- **Operation:** Dispatch `message.edit`, `message.update`, and `message.delete`.
- **Expected:** Router rejects unsupported actions; stored message remains.
- **Risk:** Immutable message contract is weakened.
- **Suggested test:** `tests/test_message_env_tool.py::MessageEnvToolTests::test_message_edit_delete_actions_are_unsupported`
- **Run:** `python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_edit_delete_actions_are_unsupported -q`

### `MCT-NON-006`: no comment edit/delete

- **Scenario:** Host tries to update or remove a comment.
- **Preconditions:** Comment exists.
- **Operation:** Dispatch `comment.edit`, `comment.update`, and `comment.delete`.
- **Expected:** Router rejects unsupported actions; comment object and target `comment_ids` remain.
- **Risk:** Comment lifecycle expands beyond atomic add/list.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_edit_delete_actions_are_unsupported`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_edit_delete_actions_are_unsupported -q`

### `MCT-NON-007`: no comment resolution or status

- **Scenario:** Host tries to resolve a comment or create a resolved/unresolved status.
- **Preconditions:** Comment target exists.
- **Operation:** Dispatch `comment.add` with `status`, `resolved`, `resolved_at`, or `resolution`; dispatch `comment.resolve`.
- **Expected:** Payload/action rejects; stored comments never include status/resolution fields.
- **Risk:** Resolution workflow is explicitly excluded.
- **Suggested test:** `tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_status_and_resolution_fields_are_rejected`
- **Run:** `python3 -m pytest tests/test_comment_env_tool.py::CommentEnvToolTests::test_comment_status_and_resolution_fields_are_rejected -q`

### `MCT-NON-008`: no review/whiteboard/handoff aliases

- **Scenario:** Host tries related collaboration tools not in scope.
- **Preconditions:** Runtime instance.
- **Operation:** Dispatch `review.create`, `whiteboard.add`, `handoff.create`, or `comment.resolve`.
- **Expected:** Unsupported tool/action with `E_ENV_TOOL`; no state changes.
- **Risk:** Excluded adjacent capabilities creep in as aliases.
- **Suggested test:** `tests/test_env_tool_router.py::EnvToolRouterTests::test_excluded_collaboration_tools_are_unsupported`
- **Run:** `python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_excluded_collaboration_tools_are_unsupported -q`

## 5. Final Verification Commands

Focused behavior:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_comment_env_tool.py -q
python3 -m pytest tests/test_env_store_v2.py -q
```

Contract and runtime surfaces:

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

Existing read-boundary regression:

```bash
python3 -m pytest tests/test_artifact_env_tool.py tests/test_track_env_tool.py -q
```

Launcher projection:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

CLI smoke:

```bash
python3 scripts/env/client.py message --help
python3 scripts/env/client.py comment --help
python3 scripts/turn_runtime.py status
```

Expected: all commands exit 0; `message` and `comment` are present; excluded capabilities remain unsupported.
