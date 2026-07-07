# IM Identity Forward Cleanup Implementation Plan

Date: 2026-07-07
Status: revised after guarded-residue boundary review.

## Goal

Finish the remaining `fea-im` identity cleanup without retaining retired runtime shapes.

The target is a single current IM contract:

- repo write helpers persist only current identity-row schemas;
- `reply_to` only works for processable inbound messages;
- live agent/runtime surfaces do not teach retired identity terminology.

## Forward Constraints

- No dual-track compatibility for old IM row shapes.
- No active runtime blacklist that names retired schemas as the main defense.
- External ingress may validate untrusted input; internal repo boundaries define exact current schema.
- Tests must prove current contracts, not only that specific old fields are blocked.

## Task 1: Tighten IM Repo Row Boundaries

Problem:

`save_im_conversation`, `save_im_message`, `save_im_message_state`, and `save_im_event` accepted loose dict rows and preserved unknown fields through `dict(row)`.

Required shape:

- define the exact allowed field set for each row type;
- reject unknown fields before write;
- construct persisted rows explicitly from current schema fields;
- remove retired-field runtime blacklist constants.

Test plan:

- update the repo regression test to pass an arbitrary unknown field to every IM row writer;
- verify each writer raises an unknown-field error;
- verify no JSON file is written on rejection.

Focused command:

```bash
python3 -m pytest tests/test_im_product_core.py::ImProductCoreTests::test_im_repository_rejects_unknown_row_fields_without_writing_files -q
```

## Task 2: Enforce Processable Reply Targets

Problem:

`send_im_reply` accepted `reply_to` messages that were already absorbed or replied, despite the tool contract requiring processable inbound messages.

Required shape:

- resolve `reply_to` through the current identity refs;
- confirm the source message is addressed to the sender;
- confirm the sender's message state is still `unseen` or `needs_parent`;
- reject non-processable sources before creating message or event rows.

Test plan:

- add a regression where absorbed and replied source messages reject reply attempts;
- assert no message/event writes occur on rejection;
- keep the valid external-origin reply path green.

Focused command:

```bash
python3 -m pytest \
  tests/test_im_product_core.py::ImProductCoreTests::test_send_im_reply_rejects_non_processable_source_message_without_write \
  tests/test_im_product_core.py::ImProductCoreTests::test_send_im_reply_normalizes_original_sender_to_target_identity_and_marks_replied \
  tests/test_message_tool_im_client.py::ActorImClientMarkTests::test_actor_can_reply_to_external_origin_message_with_reply_to_only \
  -q
```

## Task 3: Expand Live-Surface Residue Guard

Problem:

Existing residue scans covered core IM files but missed several live surfaces that agents or runtime discovery can consume.

Required shape:

- extend the live-surface scan to role instructions, skills, framework contracts, env tools, tool runtime, and web-management UI;
- keep the scan scoped to high-signal retired identity terms;
- do not scan historical docs or broad common words.

Focused command:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_communication_identity_live_surfaces_have_no_retired_shapes -q
```

Exact no-hit scan:

```bash
rg -n --no-heading "ActorAddress|actor_address|from_actor_address|to_actor_address|processed_by_actor_address|source_actor_address|target_actor_address|identity_from_im_participant|participant\\.actor_address|participant\\.external_id|\\bfrom_identity_id\\b|\\bto_identity_id\\b|\\bvisible_to_identity\\b|\\bactor_profile\\b" buddyswitch/skills framework/contracts scripts/env/tools scripts/env/tool_runtime tools/launcher/assets/roles tools/launcher/assets/web-management/app.js -g "*.py" -g "*.md" -g "*.js"
```

Expected: no output.

## Acceptance

Run the focused commands above, then the broader IM and contract regression groups:

```bash
python3 -m pytest tests/test_im_product_core.py tests/test_message_tool_im_client.py tests/test_external_im_projection_contract.py tests/test_communication_identity_cutover.py -q
python3 -m pytest tests/test_repo_consistency.py tests/test_runtime_skills.py tests/test_env_tool_response_contract.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py -q
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_im_http_router.py tests/test_external_im_session.py tests/test_daemon_mailbox.py tests/test_notification_center.py tests/test_track_comment_added_handler.py tests/test_daemon_communication_boundary.py tests/test_identity_global_convergence.py tests/test_context_binding_env_tool.py tests/test_runtime_broker.py tests/test_web_management.py -q
git diff --check
```

Completion requires all commands to pass and a final diff review confirming no active runtime code names retired IM row shapes as its primary defense.
