# Identity Communication Full-Pass Optimization Plan

Date: 2026-07-04

Status: completed full-pass optimization after live Codex probing, implementation, residue cleanup, and final acceptance verification.

Target memo: `docs/memo/2026-07-03-identity-first-communication-task-brief.html`

Previous implementation plan: `docs/memo/2026-07-04-communication-identity-cutover-optimization-plan.md`

## 1. Task Restatement

The current task is to move the Communication / IM identity cutover from "core live path passes" to "full pass".

The full-pass target is:

```text
All live communication surfaces address actors and external users through identity.

No live code accepts, emits, stores, projects, or quietly cleans the retired ActorAddress / IM participant schema.

No long-lived dual-track compatibility remains.
```

The forward path is not to keep old and new shapes side by side. The forward path is to:

1. delete old message/participant entry points where they are no longer product-owned;
2. reject retired shapes at repository/service boundaries when bad input appears;
3. make Web, Context, iMessage, Task Sys, Track, Artifact, and Comment surfaces project one identity model;
4. prove the result with focused tests, scoped static residue scans, and a live Codex user simulation.

## 2. Core Requirements

- Product communication semantics are owned by `scripts/env/services/messages.py` and `scripts/env/repos/messages.py`.
- CLI, HTTP, Web, iMessage, Task Sys, daemon, and tool layers only project the product contract.
- IM storage uses `sender_identity`, `target_identity`, `identity_ids`, `owner_identity_id`, and `visible_to_identity_id`.
- Daemon reachability uses `identity_id` and `role_id`, not `ActorAddress`.
- Actor-to-actor new sends use `target_identity_id`.
- Actor-to-external active sends remain rejected unless they are replies through `reply_to` conversation context.
- External-to-actor sends must carry actor identity plus route role in one canonical API shape.
- Track / Artifact / Comment surfaces must use identity-owned fields and delivery routes, not old actor-address payloads.
- Static scans must distinguish live surfaces from historical docs. Historical memo/spec text may retain old terms as evidence, but live code, tool docs, role docs, shipped Web assets, and active tests must not teach old runtime semantics.

## 3. `docs/bitter` Principles Applied

- Residue cleanup: the cutover is not complete while live surfaces still teach, accept, or clean old schemas.
- Built-in product interface: product core owns identity communication contracts; interface layers must not invent private identity shapes.
- End-to-end contract slice: passing unit tests is insufficient unless the user-visible loop is verified from input to observable message/state/log output.
- Tool/skill layering: fix schema, tool metadata, and service responses instead of compensating with prompt bulk.
- Wrong-boundary narrowness: a change only in `message.send` is too narrow if cleanup, Web, Context, iMessage, and Task Sys still carry retired shapes.
- Test lifecycle: live Codex probes must own instance start/stop or explicitly preserve instances with recorded reason and residual process checks.
- Parallel change boundary: split by product slice and avoid central catch-all adapters.

## 4. Current Verified State

Live Codex evidence already proves the core communication path:

- PM live actor `act-pm-67c51fcb67e4` and Dev live actor `act-dev-4ed035de9f32` started through real `./buddyswitch-codex` in `/Users/chen/.codex-buddyswitch`.
- CLI user input to PM caused PM to send Dev a Central IM.
- Dev received and replied with `reply_to`.
- External identity `ext-a606b75f7cd0` sent to PM; PM replied to external through `reply_to`.
- PM active direct send to `ext-*` without `reply_to` was rejected with `E_IM_PAYLOAD`.
- Runtime state and logs produced by that live probe had no old `actor_address` / IM participant shape hits.

Focused suites already passed in the previous probe:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_communication_identity_cutover.py tests/test_message_tool_im_client.py tests/test_im_product_core.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py tests/test_daemon_mailbox.py tests/test_im_wake_handler.py tests/test_track_comment_added_handler.py tests/test_daemon_service_contract.py tests/test_central_daemon_service.py tests/test_daemon_core.py tests/test_daemon_core_decoupling.py tests/test_daemon_trigger_router.py -q
# 170 passed, 25 subtests passed
```

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_track_comment_env_tool.py tests/test_context_binding_env_tool.py tests/test_web_management.py tests/test_artifact_selection.py -q
# 149 passed, 110 subtests passed
```

The remaining gap is static and surface completeness, not the central live PM / Dev / external loop.

## 5. Problem Classification

### P0: Live Code Still Contains Retired Message Shapes

`scripts/env_legacy_store.py` still owns old message APIs:

- `_actor_address_for_role`
- `_message_actor_payload`
- `validate_message`
- `list_messages`
- `get_message`
- `save_message`
- `create_message`
- `processed_by_actor_address`

This is not acceptable as a live importable path. It can create and validate retired `from_actor_address` / `to_actor_address` message objects.

`scripts/env_cleanup.py` still discovers message objects by reading `from_actor_address.role_id`. Cleanup is a runtime-facing tool, so it must understand the current identity object model or reject retired objects explicitly.

### P0: IM Repository Silently Cleans Old Inputs

`scripts/env/repos/messages.py` currently saves new identity rows, but it also silently drops old row fields:

- `from`
- `to`
- `from_identity_id`
- `to_identity_id`

Silent `pop()` cleanup is a dual-track compatibility path. The repository boundary should reject retired input fields with a clear error, not accept old shapes and rewrite them.

The same rule applies to:

- `participants` on conversations;
- `participant` on message states;
- `visible_to_identity` aliases when `visible_to_identity_id` is the canonical event field.

### P0: External Send Helper Has Ambiguous Target Shape

The live probe found a sharp edge:

```python
to={"id": actor_id, "type": "actor", "role_id": "pm"}
```

is rejected because `role_id` is inside the identity payload. The current accepted shape is:

```python
to={"identity": {"id": actor_id, "type": "actor"}, "role_id": "pm"}
```

That is too easy to misuse. Do not accept both shapes. Replace the helper signature with one canonical form:

```python
send_external_connection_message(
    connection=connection,
    target_identity={"id": actor_id, "type": "actor"},
    target_role_id="pm",
    content=content,
    reply_to=reply_to,
)
```

Then update callers and tests to use this exact contract.

### P1: Web / iMessage / Context Surfaces Still Teach Older Event Projections

`tools/launcher/imessage_channel.py` reads actor reply identity from `from_identity_id` or `sender_identity_id`.

`tools/launcher/assets/web-management/app.js` reads message direction from `message.from_identity_id` and `message.to_identity_id`.

Several Web and iMessage tests still fake events with flattened `from_identity_id` / `to_identity_id` instead of `sender_identity` / `target_identity`.

For IM events, the current product projection should be identity refs:

```json
{
  "sender_identity": {"id": "act-market-demo", "type": "actor"},
  "target_identity": {"id": "ext-web", "type": "external"},
  "visible_to_identity_id": "ext-web"
}
```

Do not preserve both event projections.

### P1: Tests Still Carry Old Runtime Fixtures

Static residue is not just harmless text when tests construct old live-like fixtures:

- `tests/test_runtime_broker.py` seeds `participants`, `participant`, `from`, `to`, `from_identity_id`, and `to_identity_id` in IM state.
- `tests/test_external_im_projection_contract.py` fakes `{"kind": "external", "external_id": ...}` and returns `participant`.
- `tests/test_web_management.py` helper variables named `actor_address` still teach the old model, even when values are now identity routes.
- `tests/test_imessage_channel.py` fakes `from_identity_id` event payloads.
- `tests/test_env_store_v2.py` still names a comment helper as normalizing to actor address.

Tests should either prove rejection of retired shapes in one dedicated residue test or model the current identity contract. They should not keep broad old fixtures that look like supported behavior.

### P1: Task Sys Parent Frame Is Too IM-Source-Centric

Live PM -> Dev user simulation worked, but it exposed a contract clarity issue:

- side frame correctly refused new outbound IM and used `task_sys.need_parent`;
- parent frame then performed `message.send`;
- `render_parent_frame` currently always includes IM source reply/absorb sequencing and lists only `task_sys.close` as the allowed parent frame operation.

For non-IM user-input parent frames, parent instructions should explicitly say:

```text
Perform the requested parent work, including new outbound message.send(target_identity_id=...) when parent_handoff_params requires it, then close the Task Sys task.
```

For IM source frames, keep the reply/mark ordering.

### P2: Static Residue Gate Is Not Yet Encoded

The broad manual scan remains non-empty. Some hits are valid negative assertions, but the repository needs a machine-owned gate that defines:

- which paths are live communication surfaces;
- which old schemas are forbidden there;
- which tests may mention old terms only as explicit rejection cases;
- which docs are historical evidence and excluded from live residue enforcement.

## 6. Target Invariants After Optimization

The implementation is accepted only when these invariants hold:

1. No live code path can create `from_actor_address` / `to_actor_address` message objects.
2. IM repository save functions reject old message, conversation, event, and state fields instead of silently cleaning them.
3. External send uses one canonical target signature: `target_identity` plus `target_role_id`.
4. Web Management and iMessage channel consume `sender_identity` / `target_identity`, not flattened old event fields.
5. Context inbox projections either return identity refs or have explicitly documented current identity-id summary fields; they do not expose old participant or actor-address schema.
6. Task Sys parent frames distinguish IM source closure from user-input parent work and name legal outbound message behavior.
7. Track / Artifact / Comment surfaces use identity routes and have tests proving no old actor-address projections.
8. Scoped live-surface residue scan is clean.
9. Live Codex simulation covers PM -> Dev, Dev reply, external -> actor -> external, active external rejection, Web/Context visibility, and Track/Comment/Artifact identity projections.

## 7. Implementation Plan

### Step 1: Add A Communication Residue Gate

Modify `tests/test_repo_consistency.py`.

Add a focused test:

```python
test_communication_identity_live_surfaces_have_no_retired_shapes
```

Live surface targets:

- `scripts/env/repos/messages.py`
- `scripts/env/services/messages.py`
- `scripts/env/tools/message`
- `scripts/env/tool_runtime/im_client.py`
- `scripts/env/tools/context/_impl.py`
- `scripts/env_cleanup.py`
- `tools/launcher/external_im_session.py`
- `tools/launcher/im_http_router.py`
- `tools/launcher/web_management.py`
- `tools/launcher/assets/web-management/app.js`
- `tools/launcher/imessage_channel.py`
- `tools/launcher/web_im_identity.py`
- `tools/launcher/task_sys_runtime.py`
- `tools/launcher/assets/roles`
- shared message/track Task Sys skills if they describe communication behavior.

Forbidden retired communication shapes:

- `ActorAddress`
- `actor_address`
- `from_actor_address`
- `to_actor_address`
- `processed_by_actor_address`
- `source_actor_address`
- `target_actor_address`
- `identity_from_im_participant`
- `participant.actor_address`
- `participant.external_id`
- JSON participant kind payloads for `actor` / `external`
- IM row fields `from`, `to`, `participants`, `participant`
- IM message/event compatibility inputs `from_identity_id` and `to_identity_id`

Allow old terms only in:

- the new residue-gate test itself;
- explicit rejection tests that construct retired payloads in a local variable whose name includes `retired` or `legacy_rejection`;
- historical `docs/memo`, `docs/spec`, and `docs/bitter`.

Verification:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_communication_identity_live_surfaces_have_no_retired_shapes -q
```

### Step 2: Retire Old `env_legacy_store` Message APIs

Modify `scripts/env_legacy_store.py`.

Direct replacement:

- remove old message creation and validation behavior;
- make message APIs raise a clear retirement error, or delete them if no active test requires symbol presence;
- replace helper naming that returns actor-address payloads with identity-route naming for track/comment helper compatibility;
- update track comment helper tests so they assert `by_identity_id`, not actor-address normalization.

Modify `scripts/env_store.py` only if needed so retired object API errors point to the current repo/service, not to `env_legacy_store` as a recommended live import.

Modify tests:

- `tests/test_env_store_v2.py`
- `tests/test_memory_removal_contract.py`
- `tests/runtime_root_test_helper.py`
- any test importing `env_legacy_store` only for message APIs.

Verification:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_env_store_v2.py tests/test_memory_removal_contract.py tests/test_env_layer_boundaries.py -q
```

### Step 3: Move Cleanup To Current Identity Objects

Modify `scripts/env_cleanup.py`.

Replace message discovery rules:

- read current `state/im/messages/*.json`;
- require `sender_identity.id`, `target_identity.id`, and `conversation_id`;
- report retired `from_actor_address` / `to_actor_address` as invalid stale state;
- do not infer roles from old actor-address payloads.

Modify tests:

- `tests/test_cleanup_system.py`

Verification:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_cleanup_system.py -q
```

### Step 4: Reject Retired IM Shapes At Repository Boundary

Modify `scripts/env/repos/messages.py`.

Replace silent cleanup with explicit validation:

- `save_im_conversation` rejects `participants`;
- `save_im_message` rejects `from`, `to`, `from_identity_id`, `to_identity_id`;
- `save_im_message_state` rejects `participant`;
- `save_im_event` rejects `from`, `to`, `from_identity_id`, `to_identity_id`, and `visible_to_identity` alias.

Add regression tests in `tests/test_im_product_core.py` or `tests/test_communication_identity_cutover.py`:

- each rejected old shape returns a clear `ValueError`;
- no file is written after rejection;
- valid identity rows still persist.

Verification:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_communication_identity_cutover.py tests/test_im_product_core.py -q
```

### Step 5: Replace External Send Target API

Modify `scripts/env/services/messages.py`.

Replace:

```python
send_external_connection_message(connection=..., to=..., ...)
```

with:

```python
send_external_connection_message(
    connection=...,
    target_identity=...,
    target_role_id=...,
    content=...,
    reply_to=...,
    wake_actor=...,
)
```

Update `tools/launcher/external_im_session.py` to call the new signature.

Update tests:

- `tests/test_im_product_core.py`
- `tests/test_external_im_session.py`
- `tests/test_im_http_router.py`
- `tests/test_external_im_projection_contract.py`

Acceptance:

- no accepted payload shape carries `role_id` inside identity;
- no compatibility branch accepts both old and new target dicts;
- error messages explain canonical `target_identity` / `target_role_id` fields.

Verification:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_im_product_core.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_external_im_projection_contract.py -q
```

### Step 6: Move Web, iMessage, And Context To Identity Refs

Modify `tools/launcher/assets/web-management/app.js`.

- read sender from `message.sender_identity.id`;
- read target from `message.target_identity.id`;
- remove `from_identity_id` / `to_identity_id` event handling.

Modify `tools/launcher/imessage_channel.py`.

- replace `_actor_id_for_reply` fallback scan with `sender_identity.id`;
- reject events/messages missing `sender_identity.id` instead of guessing old fields.

Modify `scripts/env/tools/context/_impl.py`.

- project inbox rows with `sender_identity` and `target_identity`, or with explicitly current summary fields generated from those refs;
- remove any old participant or actor-address language from context source descriptions.

Update tests:

- `tests/test_web_management.py`
- `tests/test_im_web_management_projection.py`
- `tests/test_imessage_channel.py`
- `tests/test_external_im_projection_contract.py`
- `tests/test_context_binding_env_tool.py`

Verification:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_imessage_channel.py tests/test_external_im_projection_contract.py tests/test_context_binding_env_tool.py -q
```

### Step 7: Prove Track / Artifact / Comment Identity Surfaces

Review and tighten tests for:

- `tests/test_track_env_tool.py`
- `tests/test_artifact_env_tool.py`
- `tests/test_track_comment_env_tool.py`
- `tests/test_artifact_selection.py`
- `tests/test_track_comment_added_handler.py`

Required assertions:

- Track owner and artifact producer are identity ids or identity refs.
- Comment author is `by_identity_id`.
- Comment mentions are `mentioned_identity_ids`.
- Delivery rows use `target_identity_id`.
- No Track / Artifact / Comment response includes actor-address payloads.
- Handler source context uses `source_identity_id` and `target_identity_id`, not source/target actor-address payloads.

Verification:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_track_comment_env_tool.py tests/test_artifact_selection.py tests/test_track_comment_added_handler.py -q
```

### Step 8: Clarify Task Sys Parent Frame Contract

Modify `tools/launcher/task_sys_runtime.py`.

Parent frame rendering should branch by source type:

- For `im.message.created`, keep reply/mark before close.
- For `user.input` or non-IM source, say the parent may perform the requested parent work, including a new `message.send(target_identity_id=...)` when the handoff params require outbound communication, then call `task_sys.close`.
- Do not say the only allowed parent operation is close before naming the parent work.

Update `tests/test_task_sys_runtime_executor.py`:

- IM source parent frame still names reply/absorb ordering.
- user-input parent frame names outbound `message.send(target_identity_id=...)` as legal when requested by handoff params.
- side frame still forbids new outbound communication and uses `task_sys.need_parent`.

Verification:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_task_sys_runtime_executor.py tests/test_env_tool_response_contract.py -q
```

### Step 9: Rework Tests That Currently Seed Old IM Fixtures

Replace old fixtures in:

- `tests/test_runtime_broker.py`
- `tests/test_external_im_projection_contract.py`
- `tests/test_imessage_channel.py`
- `tests/test_web_management.py`
- `tests/test_browser_page_expired_handler.py`
- `tests/test_notification_center.py`
- `tests/test_task_checkout_handler.py`
- `tests/test_daemon_mailbox.py`

Rules:

- Use `sender_identity` / `target_identity` for IM messages and events.
- Use `identity_id` / `role_id` for actor routes.
- If a test must prove old shape rejection, keep it in a small explicit negative test and name the variable `legacy_rejection_payload` or `retired_shape`.
- Rename helper variables from `actor_address` to `identity_route`, `actor_route`, or `target_identity_route`.

Verification:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_runtime_broker.py tests/test_browser_page_expired_handler.py tests/test_notification_center.py tests/test_task_checkout_handler.py tests/test_daemon_mailbox.py -q
```

### Step 10: Add A Repeatable Live Codex Probe

Create a concrete probe script under the existing evidence area or `scripts/`:

```text
docs/spec/2026-07-03-identity-first-communication-task-brief/evidence-2026-07-04-live-user-simulation/run/scripts/live_identity_full_pass_probe.py
```

The probe must use real `./buddyswitch-codex` and real app-server turns. It must not edit runtime object files directly.

Required live steps:

1. start PM and Dev actors;
2. send CLI user input to PM requesting `message.send` to Dev;
3. observe Dev receive and reply with `reply_to`;
4. create external connection and send external -> PM;
5. observe PM reply to external through `reply_to`;
6. attempt actor active send to `ext-*` without `reply_to` and verify rejection plus unchanged message/event/state counts;
7. exercise Web Management IM session/events/conversation route against the live root;
8. exercise Context inbox projection from the active actor;
9. create Track / Artifact / Comment state through env tools or live actor turns and verify identity-shaped responses;
10. capture daemon logs, app-server logs, central registry, IM state, and residue scan output;
11. stop/delete instances unless the run is invoked with an explicit preserve flag.

Evidence output:

```text
docs/spec/2026-07-03-identity-first-communication-task-brief/evidence-YYYY-MM-DD-live-full-pass/
```

Verification:

```bash
python3 docs/spec/2026-07-03-identity-first-communication-task-brief/evidence-2026-07-04-live-user-simulation/run/scripts/live_identity_full_pass_probe.py --real-codex
```

### Step 11: Final Verification Gate

Run focused suites:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_communication_identity_cutover.py tests/test_message_tool_im_client.py tests/test_im_product_core.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py tests/test_daemon_mailbox.py tests/test_im_wake_handler.py tests/test_track_comment_added_handler.py tests/test_daemon_service_contract.py tests/test_central_daemon_service.py tests/test_daemon_core.py tests/test_daemon_core_decoupling.py tests/test_daemon_trigger_router.py -q
```

Run surface suites:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_track_comment_env_tool.py tests/test_context_binding_env_tool.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_imessage_channel.py tests/test_artifact_selection.py -q
```

Run repository consistency:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_repo_consistency.py -q
```

Run scoped residue scan over live code and active tests:

```bash
rg -n "ActorAddress|actor_address|target_actor_address|source_actor_address|from_actor_address|to_actor_address|processed_by_actor_address|identity_from_im_participant|participant\\.actor_address|participant\\.external_id|\\\"kind\\\"\\s*:\\s*\\\"actor\\\"|\\\"kind\\\"\\s*:\\s*\\\"external\\\"" scripts/env tools/launcher tests
```

Expected result:

- no live-code hits;
- only explicit rejection-test hits if the new residue gate allows them;
- no runtime fixture that seeds old participant or actor-address schema.

Run live root residue scan after the live probe:

```bash
rg -n "ActorAddress|actor_address|target_actor_address|source_actor_address|from_actor_address|to_actor_address|processed_by_actor_address|identity_from_im_participant|participant\\.actor_address|participant\\.external_id|\\\"kind\\\"\\s*:\\s*\\\"actor\\\"|\\\"kind\\\"\\s*:\\s*\\\"external\\\"" /Users/chen/.codex-buddyswitch/state /Users/chen/.codex-buddyswitch/instances
```

Expected result:

- no matches in runtime state/logs produced by the probe.

## 8. Acceptance Criteria

The optimization is accepted when all criteria are true:

1. `scripts/env_legacy_store.py` cannot create old message objects.
2. `scripts/env_cleanup.py` discovers current identity-shaped IM state.
3. `scripts/env/repos/messages.py` rejects retired IM input fields instead of silently popping them.
4. external send API has one canonical target signature.
5. Web Management, iMessage, Context, Track, Artifact, and Comment surfaces are tested against identity-shaped projections.
6. Task Sys side and parent frame instructions match the actual source-bound vs parent-work split observed in live Codex.
7. Focused and surface pytest suites pass.
8. `tests/test_repo_consistency.py` owns the scoped residue gate.
9. Live Codex full-pass probe completes and writes evidence.
10. Runtime residue scan is clean.
11. `git status --short --untracked-files=all` only shows intentional implementation/evidence changes.

## 9. Execution Order

Use this order to keep the loop short and verifiable:

1. Add residue gate as a failing test.
2. Retire `env_legacy_store` message APIs and update cleanup.
3. Make IM repo reject old shapes.
4. Replace external send signature.
5. Update Web/iMessage/Context projections.
6. Update Track/Artifact/Comment surface tests.
7. Clarify Task Sys parent frame.
8. Rewrite old tests/fixtures.
9. Run focused suites and residue gate.
10. Run live Codex full-pass probe.

Do not start by building a compatibility migration layer. If stale local runtime data blocks testing, handle it as explicit stale state cleanup in the probe or cleanup tool, not as a permanent product fallback.

## 10. Completed Result

Implementation completed the full-pass cutover through the shortest verified path:

- `scripts/env_legacy_store.py` no longer creates retired message objects; message APIs now fail closed toward identity-first IM.
- `scripts/env_cleanup.py` discovers current identity-shaped IM state and treats retired message object shapes as stale invalid state.
- `scripts/env/repos/messages.py` rejects retired IM message, conversation, state, and event fields instead of silently cleaning them.
- `send_external_connection_message` now uses canonical `target_identity` plus `target_role_id`.
- Web Management, iMessage, Context, Task Sys, Track, Artifact, Comment, and active fixtures now project identity refs/routes.
- `tests/test_repo_consistency.py` owns the scoped residue gate for live communication surfaces.
- The live full-pass probe starts real PM/Dev actors, exercises actor IM, external IM, Web, Context, Track, Artifact, Comment, direct external rejection, runtime residue scan, and cleanup.

Final verification:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_communication_identity_cutover.py tests/test_message_tool_im_client.py tests/test_im_product_core.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py tests/test_daemon_mailbox.py tests/test_im_wake_handler.py tests/test_track_comment_added_handler.py tests/test_daemon_service_contract.py tests/test_central_daemon_service.py tests/test_daemon_core.py tests/test_daemon_core_decoupling.py tests/test_daemon_trigger_router.py -q
# 172 passed, 34 subtests passed

PYTHONPATH=scripts python3 -m pytest tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_track_comment_env_tool.py tests/test_context_binding_env_tool.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_imessage_channel.py tests/test_artifact_selection.py -q
# 184 passed, 243 subtests passed

node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
# 2 test files passed

PYTHONPATH=scripts python3 -m pytest tests/test_repo_consistency.py -q
# 41 passed, 121 subtests passed

PYTHONPATH=scripts python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_communication_identity_live_surfaces_have_no_retired_shapes -q
# 1 passed

PYTHONPATH=scripts python3 -m pytest tests/test_browser_lazy_release_integration.py tests/test_daemon_core.py -q
# 35 passed
```

The scoped broad source scan has no live implementation hits. Remaining matches are residue-gate definitions, test names, and explicit negative assertions that retired fields are absent or rejected.

Live evidence:

```text
docs/spec/2026-07-03-identity-first-communication-task-brief/evidence-2026-07-04-live-full-pass/run/captures/summary.json
```

The evidence summary has `ok: true`, every product check true, `runtime_residue_scan.ok: true`, and cleanup successfully stopped/deleted the two owned live actors.
