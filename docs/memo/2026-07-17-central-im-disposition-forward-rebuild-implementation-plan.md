# Central IM Disposition Forward Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Execute every behavior change with `superpowers:test-driven-development` and select proof only through `$buddyswitch-testing`. Steps use checkbox (`- [ ]`) syntax for resumable execution.

**Goal:** Remove Central IM disposition as a live model so one message may have multiple replies, while Task Sys remains the sole owner of inbound work lifecycle.

**Architecture:** Central IM owns immutable messages, identity-addressed direct conversations, `reply_to` edges, visible events, cursors, target resolution, and delivery results. Task Sys owns `side_processing`, `awaiting_parent`, `parent_processing`, `completed`, and `canceled`; iMessage remains a stateless adapter that maps a Native Reply GUID to one Central IM anchor and invokes the ordinary reply wrapper.

**Tech Stack:** Python 3.13, JSON runtime object storage, Central IM service/repository, BuddySwitch env tools, Task Sys, iMessage `imsg`/Messages `chat.db`, `./buddyswitch-test focused`, BuddySwitch product CLI.

---

## 1. FRAME

### Bottleneck

Central IM currently turns an inbound message into a one-shot work item:

```text
unseen | needs_parent
  -> Reply accepted
  -> original message marked replied
  -> every later Reply rejected
```

That rule prevents the user from replying more than once to the same visible iMessage bubble and duplicates the Task Sys lifecycle already introduced by `3d26d0e`.

### Acceptance sentence

For one actor-origin Central IM message, the user may perform multiple iMessage Native Replies; every user action creates a distinct Central IM message with the same `reply_to`, uses the anchor message's sender as target through the normal target resolver, and is never admitted or rejected based on mutable processing state.

### Product paths

```text
iMessage user Native Reply
  -> schema-6 GUID/message link
  -> Central IM reply wrapper
  -> target resolver
  -> immutable reply message with reply_to
  -> actor-visible event/task
  -> user observes actor handling

IM task needs reply
  -> message.send(reply_to=...)
  -> task_sys.close

IM task needs no reply
  -> task_sys.close

IM task needs parent
  -> task_sys.need_parent

IM task must stop incomplete
  -> task_sys.cancel
```

### Protected current contracts

These must remain unchanged:

- Reply anchor must exist and be addressed to the current sender identity.
- Reply target is the anchor's original sender and passes the normal IM target resolver.
- Actor reachability failures reject before a message/event write.
- Explicit `target_identity_id` sends remain independent of Reply.
- Direct conversation visibility and `reply_to` query behavior remain exact.
- iMessage `NativeReply` and `TopLevel` parser domains remain unchanged.
- iMessage routing never guesses from quoted text or falls back to a selected actor.
- Task Sys status and legal transitions from `3d26d0e` remain unchanged.
- Event ack/cursor behavior remains current; event acknowledgement is not message disposition.

No repository evidence identifies `PATCH /api/im/messages/{id}/disposition` or `message.mark` as a protected external contract. They are forward-deletion targets.

### Explicit non-goals

- Do not add Task Sys ingress deduplication or transport retry behavior.
- Do not add read receipts, unread counts, or replacement message status.
- Do not rename disposition and move it into another layer.
- Do not change `/actors`, `@actor`, Native Reply parsing, connection TTL, or GUID mapping.
- Do not introduce compatibility aliases, fallback reads, migration adapters, or dual state.
- Do not run `./buddyswitch-test full`; this task requires exact and affected focused proof plus real product acceptance.

## 2. TRACE

### Current semantic owners

| Concern | Current owner after rebuild |
|---|---|
| Message, conversation, reply edge, visibility | `scripts/env/services/messages.py` + `scripts/env/repos/messages.py` |
| Actor/external message projection | `scripts/env/tool_runtime/im_client.py`, `tools/launcher/external_im_session.py`, `tools/launcher/im_http_router.py` |
| Message tool public contract | `scripts/env/tools/message/tool.py` |
| Task processing lifecycle | `scripts/env/domain/task_sys.py` |
| Task frame guidance | `tools/launcher/task_sys_runtime.py`, `buddyswitch/skills/shared/task-management/SKILL.md` |
| iMessage grammar/routing/correlation | `tools/launcher/imessage_channel.py` |

### Retired live surfaces to remove

Production:

- `scripts/env/repos/messages.py`
  - `_VALID_DISPOSITIONS`
  - `_MESSAGE_STATE_FIELDS`
  - `save_im_message_state`
  - `get_im_message_state`
  - `im/message_states` writes and reads
- `scripts/env/services/messages.py`
  - `_reply_source_state`
  - `_mark_reply_source_replied`
  - initial `unseen` state creation
  - Reply disposition response fields
  - `update_im_disposition`
- `scripts/env/tool_runtime/im_client.py`
  - `ActorImClient.mark`
  - `message.mark` failure/result projection
- `scripts/env/tools/message/tool.py`
  - `message.mark`
  - processable/disposition contract language
- `scripts/env/tool_runtime/role_auth.py`
  - `message.mark` permission
- `tools/launcher/external_im_session.py`
  - `update_disposition`
- `tools/launcher/im_http_router.py`
  - authenticated `PATCH .../disposition` route
- `tools/launcher/task_sys_runtime.py`
  - `message.mark` and processable/disposition guidance
- `buddyswitch/skills/shared/task-management/SKILL.md`
  - message disposition workflow
- `scripts/env_legacy_store.py`
  - `VALID_MESSAGE_DISPOSITIONS`
- `docs/arch/web-interface-call-architecture.md`
  - current disposition ownership statement

Historical `docs/memo/**` files remain historical evidence. This new plan supersedes their one-shot Reply statements but does not rewrite history.

## 3. PROVE / BUILD / REPLACE

### Task 1: RED — prove one anchor accepts multiple replies

**Files:**

- Modify: `tests/integration/im/test_product_core.py`

- [x] **Step 1: Replace the one-shot guard test with exact multi-reply behavior**

Replace `test_send_im_reply_rejects_non_processable_source_message_without_write` with a test equivalent to:

```python
def test_send_im_reply_allows_multiple_replies_to_same_inbound_message(self) -> None:
    _created, _external_session, external = self._external_session()
    actor = self._actor_identity(role="dev", label="act-dev-multi-reply")
    root = message_service.send_im_message(
        sender_identity=actor["identity"],
        target_identity=external,
        content="reply more than once",
    )

    first = message_service.send_im_reply(
        sender_identity=external,
        reply_to=root["message"]["id"],
        content="first",
        actor_reachability_checker=lambda *, target_identity_id: {
            "reachability_status": "online",
            "target_identity_id": target_identity_id,
            "record": {"identity_id": target_identity_id},
        },
    )
    second = message_service.send_im_reply(
        sender_identity=external,
        reply_to=root["message"]["id"],
        content="second",
        actor_reachability_checker=lambda *, target_identity_id: {
            "reachability_status": "online",
            "target_identity_id": target_identity_id,
            "record": {"identity_id": target_identity_id},
        },
    )

    self.assertTrue(first.get("ok"), msg=first)
    self.assertTrue(second.get("ok"), msg=second)
    self.assertNotEqual(first["message"]["id"], second["message"]["id"])
    self.assertEqual(first["message"]["reply_to"], root["message"]["id"])
    self.assertEqual(second["message"]["reply_to"], root["message"]["id"])

    replies = message_service.list_im_replies(
        identity=external,
        message_id=root["message"]["id"],
    )
    self.assertEqual(replies["count"], 2)
    self.assertEqual([row["content"] for row in replies["replies"]], ["first", "second"])
```

- [x] **Step 2: Run the exact RED**

```bash
./buddyswitch-test focused \
  tests/integration/im/test_product_core.py::ImProductCoreTests::test_send_im_reply_allows_multiple_replies_to_same_inbound_message
```

Expected RED: the second reply returns `E_IM_REPLY_TARGET` because the original disposition is `replied`.

- [x] **Step 3: Record RED evidence**

Record runner id, HEAD, dirty patch identity, failure reason, duration, and clean runner-root/process cleanup in this plan.

### Task 2: GREEN — make Reply a pure target-resolution wrapper

**Files:**

- Modify: `scripts/env/services/messages.py`
- Modify: `tests/integration/im/test_product_core.py`

- [x] **Step 1: Remove processing-state admission**

Delete `_reply_source_state(...)` and the call from `_resolve_reply_target_identity_id(...)`. Keep these checks only:

```python
original_message = message_repo.get_im_message(reply_to_id)
if original_message is None:
    return _im_reply_target_error("reply_to message not found")

original_sender = _identity_ref(original_message.get("sender_identity"), "reply_to.sender_identity")
original_target = _identity_ref(original_message.get("target_identity"), "reply_to.target_identity")
if original_target["id"] != sender["id"]:
    return _im_reply_target_error("reply_to message is not addressed to the sender identity")
```

- [x] **Step 2: Remove post-send state mutation**

Delete `_mark_reply_source_replied(...)`, its invocation from `send_im_reply(...)`, and `original_final_disposition`. Preserve `original_message_id`:

```python
response = dict(result)
response["original_message_id"] = reply_target["reply_to"]
return response
```

- [x] **Step 3: Update the existing success contract test**

Rename `test_send_im_reply_normalizes_original_sender_to_target_identity_and_marks_replied` so it proves target normalization and persisted `reply_to`, then remove state-file and final-disposition assertions.

- [x] **Step 4: Run the Task 1 exact target GREEN**

Run the same Task 1 command. Expected: PASS with two distinct reply rows and one shared anchor.

- [x] **Step 5: Run direct Reply safety boundaries**

```bash
./buddyswitch-test focused \
  tests/integration/im/test_product_core.py::ImProductCoreTests::test_send_im_reply_rejects_message_not_addressed_to_sender \
  tests/integration/im/test_product_core.py::ImProductCoreTests::test_send_im_reply_to_offline_actor_rejects_before_write \
  tests/integration/im/test_product_core.py::ImProductCoreTests::test_reply_uses_original_direct_conversation
```

Expected: PASS; no scope, reachability, or conversation invariant is weakened.

### Task 3: RED/GREEN — remove message state and disposition API

**Files:**

- Modify: `tests/integration/im/test_product_core.py`
- Modify: `tests/integration/im/test_http_router.py`
- Modify: `tests/integration/im/test_external_session.py`
- Modify: `scripts/env/repos/messages.py`
- Modify: `scripts/env/services/messages.py`
- Modify: `tools/launcher/external_im_session.py`
- Modify: `tools/launcher/im_http_router.py`
- Modify: `scripts/env_legacy_store.py`

- [x] **Step 1: Write repository RED**

Update the direct-send persistence test to assert the current store contains only conversations, messages, and events, and no `message_states` directory is created:

```python
self.assertFalse((self.runtime_state_root / "im" / "message_states").exists())
```

- [x] **Step 2: Write HTTP RED**

Replace disposition success coverage with:

```python
status, payload = router.dispatch(
    "PATCH",
    f"/api/im/messages/{message_id}/disposition",
    headers={"Authorization": f"Bearer {session_key}"},
    body=json.dumps({"disposition": "absorbed"}).encode("utf-8"),
)
self.assertEqual(status, 404)
self.assertEqual(payload["error"]["code"], "NOT_FOUND")
```

- [x] **Step 3: Run repository/API RED**

```bash
./buddyswitch-test focused \
  tests/integration/im/test_product_core.py \
  tests/integration/im/test_http_router.py \
  tests/integration/im/test_external_session.py
```

Expected RED: direct send creates `message_states`; PATCH is authenticated and succeeds; external session still exposes `update_disposition`.

- [x] **Step 4: Delete state persistence**

Delete `_VALID_DISPOSITIONS`, `_MESSAGE_STATE_FIELDS`, `save_im_message_state`, and `get_im_message_state` from the repository. Delete target `unseen` state creation from `send_im_message`. Delete `update_im_disposition` from the service.

- [x] **Step 5: Delete external projections**

Delete `ExternalImSession.update_disposition`, the router dispatch branch, and `_is_authenticated_im_route` support for `PATCH .../disposition`.

- [x] **Step 6: Delete the legacy constant**

Delete `VALID_MESSAGE_DISPOSITIONS` from `scripts/env_legacy_store.py`; do not add a replacement constant or adapter.

- [x] **Step 7: Rewrite affected tests around current products**

Preserve external session authentication, send, event ack, conversation, message, and Reply tests. Remove state file fixtures and disposition assertions rather than replacing them with another message status.

- [x] **Step 8: Run the Task 3 target GREEN**

Run the Task 3 command. Expected: PASS, no `message_states` write, disposition route is absent, all event/cursor/Reply behavior remains green.

### Task 4: RED/GREEN — remove `message.mark` and processable-message contract

**Files:**

- Modify: `tests/unit/env_tool/test_schema_contract.py`
- Modify: `tests/unit/env_tool/test_semantic_contract.py`
- Modify: `tests/integration/env_tool/test_message.py`
- Modify: `tests/process/cli/test_black_box_tool_runtime.py`
- Modify: `tests/unit/actor/test_role_action_auth.py`
- Modify: `scripts/env/tools/message/tool.py`
- Modify: `scripts/env/tool_runtime/im_client.py`
- Modify: `scripts/env/tool_runtime/role_auth.py`

- [x] **Step 1: Write the public-contract RED**

Update schema/registry assertions so the current message action set is exactly:

```python
{"contacts", "conversation", "get", "list", "send"}
```

Assert `message.get` is an exact visible-message read with no processable/disposition precondition or return field. Assert `message.send` returns `original_message_id` for Reply but no `original_final_disposition`.

- [x] **Step 2: Run contract RED**

```bash
./buddyswitch-test focused \
  tests/unit/env_tool/test_schema_contract.py \
  tests/unit/env_tool/test_semantic_contract.py \
  tests/process/cli/test_black_box_tool_runtime.py \
  tests/unit/actor/test_role_action_auth.py
```

Expected RED: `message.mark` remains registered/authorized and live descriptions teach processable/disposition semantics.

- [x] **Step 3: Delete the mark action**

Delete the `ActionDefinition(name="mark", ...)` block, `ActorImClient.mark`, its rejection/result helper usage, and the `message.mark` permission.

- [x] **Step 4: Rewrite the current message contract**

Teach exactly:

```text
message.get(message_id) reads one exact message visible to the current identity.
message.send(reply_to=message_id, content=...) resolves the original sender through the normal target resolver.
Reply success creates a new immutable message and returns original_message_id.
```

Do not use `processable`, `disposition`, `absorbed`, or `replied` as message state terminology.

- [x] **Step 5: Remove mark behavior tests**

Delete env-tool tests that preserve `message.mark`; keep send/get/list/conversation and rejection behavior tests.

- [x] **Step 6: Run the Task 4 target GREEN**

Run the Task 4 command. Expected: PASS with one current message tool action set and no mark permission.

### Task 5: RED/GREEN — make Task Sys the only lifecycle instruction

**Files:**

- Modify: `tests/unit/task_sys/test_runtime_executor.py`
- Modify: `tests/unit/architecture/test_task_management_skill.py`
- Modify: `tests/integration/env_tool/test_response_task.py`
- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `buddyswitch/skills/shared/task-management/SKILL.md`

- [x] **Step 1: Write Task Sys guidance RED**

Assert IM side/parent frames contain:

```text
message.get(message_id=...)
message.send(reply_to=source_message_id, content=...)
task_sys.close(task_id=..., summary=...)
task_sys.need_parent(...)
task_sys.cancel(task_id=..., reason=...)
```

Assert they do not contain `message.mark`, `processable`, or disposition terminology.

- [x] **Step 2: Run Task Sys RED**

```bash
./buddyswitch-test focused \
  tests/unit/task_sys/test_runtime_executor.py \
  tests/unit/architecture/test_task_management_skill.py \
  tests/integration/env_tool/test_response_task.py
```

Expected RED: current frames and skill still require `message.mark(absorbed)`.

- [x] **Step 3: Update runtime and skill**

Replace the no-reply path with direct task completion:

```text
If a reply is required, send it before closing the Task.
If no reply is required and the source work is complete, call task_sys.close directly.
Use task_sys.need_parent for parent work and task_sys.cancel only for incomplete work that must stop.
```

Do not modify `scripts/env/domain/task_sys.py`, its statuses, transitions, Progress Check, or turn-completion behavior.

- [x] **Step 4: Delete retired mark/needs_parent response tests**

Remove `message.mark(needs_parent)` compatibility tests. Preserve Task Sys `need_parent`, `close`, and `cancel` product tests.

- [x] **Step 5: Run the Task 5 target GREEN**

Run the Task 5 command. Expected: PASS; Task Sys remains the only processing lifecycle truth.

### Task 6: REPLACE — update iMessage consumer behavior and add residue proof

**Files:**

- Modify: `tests/integration/im/test_imessage_routing.py`
- Modify: `tests/integration/im/_imessage_fakes.py` only if the fake response queue must model two accepted replies
- Modify: `tests/integration/env_tool/test_payload_contract.py`
- Modify: `docs/arch/web-interface-call-architecture.md`

- [x] **Step 1: Replace the one-shot iMessage expectation**

Replace `test_second_reply_rejection_has_no_target_send_fallback` with a test that submits two Native Reply rows using the same `thread_originator_guid` and asserts:

```python
self.assertEqual([call["reply_to"] for call in api.reply_calls], [anchor_message_id, anchor_message_id])
self.assertEqual([call["content"] for call in api.reply_calls], ["FIRST", "SECOND"])
self.assertEqual(api.send_calls, [])
```

The test must continue proving there is no `@actor`/selected-target fallback.

- [x] **Step 2: Add a scoped architecture residue assertion**

In `test_payload_contract.py`, scan current production/contract files only and require absence of the retired IM processing model. Construct retired tokens from fragments so the test does not match itself:

```python
retired = (
    "message_" + "states",
    "update_im_" + "disposition",
    "message." + "mark",
    "original_final_" + "disposition",
    "processable " + "inbound",
)
```

Scope the scan to Central IM, message tool/runtime, Task Sys guidance, external IM adapters, current architecture docs, and current shared skill. Historical memos are excluded.

- [x] **Step 3: Update current architecture documentation**

State that Central IM owns messages, Reply edges, events/cursors, and target resolution; Task Sys status is the sole processing lifecycle. Remove disposition from the Web interface contract.

- [x] **Step 4: Run consumer/residue proof**

```bash
./buddyswitch-test focused \
  tests/integration/im/test_imessage_routing.py \
  tests/integration/env_tool/test_payload_contract.py
```

Expected: PASS; two Reply calls share one anchor, no target fallback occurs, and no live disposition path remains.

## 4. VERIFY

### Task 7: Affected focused verification

- [x] Freeze executable changes and run once:

```bash
./buddyswitch-test focused \
  tests/integration/im/test_product_core.py \
  tests/integration/im/test_http_router.py \
  tests/integration/im/test_external_session.py \
  tests/integration/im/test_imessage_routing.py \
  tests/integration/im/test_imessage_outbound.py \
  tests/integration/im/test_imessage_state.py \
  tests/integration/im/test_imessage_worker.py \
  tests/integration/env_tool/test_message.py \
  tests/integration/env_tool/test_payload_contract.py \
  tests/integration/env_tool/test_response_task.py \
  tests/unit/env_tool/test_schema_contract.py \
  tests/unit/env_tool/test_semantic_contract.py \
  tests/process/cli/test_black_box_tool_runtime.py \
  tests/unit/actor/test_role_action_auth.py \
  tests/unit/task_sys/test_runtime_executor.py \
  tests/unit/architecture/test_task_management_skill.py
```

- [x] Run current-source residue searches and inspect every match:

```bash
rg -n -i \
  'message_states|update_im_disposition|message\.mark|original_final_disposition|processable inbound|disposition marking|per-identity dispositions|reply to a newer actor message' \
  scripts tools buddyswitch docs/arch tests \
  --glob '!**/docs/memo/**'
```

Allowed matches: scoped negative residue assertions and unrelated English usage such as review-feedback disposition. No Central IM/message processing match is allowed.

- [x] Run:

```bash
git diff --check
git status --short
```

- [x] Inspect runner roots, processes, sockets, actor instances, and web service ownership. Any task-owned residue is a verification failure.

### Task 8: Review audit before live acceptance

- [x] Audit the final diff against each protected contract and the acceptance sentence.
- [x] Confirm no production file reads or writes `im/message_states`.
- [x] Confirm Reply keeps exact recipient ownership and target reachability checks.
- [x] Confirm the iMessage parser and GUID mapping code are unchanged unless a failing consumer test required a minimal fix.
- [x] Confirm Task Sys domain/status code is unchanged.
- [x] Confirm `message.mark` is absent from registry, auth, schemas, prompt guidance, and skills.
- [x] Confirm the disposition HTTP endpoint returns 404 and no compatibility alias remains.

## 5. ACCEPT — real actor and iMessage product validation

### Task 9: Start product actors and service through BuddySwitch CLI

- [x] Inspect current environment and existing instances:

```bash
./buddyswitch-codex env status
./buddyswitch-codex instance list
```

- [x] Create at least two fresh actor instances through the public product launcher:

```bash
./buddyswitch-codex instance start --role dev
./buddyswitch-codex instance start --role pm
```

Record returned actor ids and use only those ids in this acceptance run.

Acceptance actors: Dev `act-dev-66644ef5ce28`; PM `act-pm-1526207548ac`.

- [x] Start or restart the current worktree Web/Central IM/iMessage service on an available local port using the public CLI:

```bash
./buddyswitch-codex web --host 127.0.0.1 --port 8765
```

Do not reset schema-6 iMessage mappings unless startup proves the persisted state invalid.

### Task 10: Guided real iMessage conversation

Guide the user one action at a time and inspect logs/state after every action.

- [x] **Online discovery:** user sends top-level `/actors`; verify both fresh actors are returned and no actor task is created for the command.
- [x] **Explicit Dev send:** user sends `@<dev-id> LIVE-DEV-ANCHOR`; verify only Dev receives it and Dev returns a uniquely identifiable bubble.
- [x] **Explicit PM send:** user sends `@<pm-id> LIVE-PM-ANCHOR`; verify only PM receives it and PM returns a uniquely identifiable bubble.
- [x] **First Dev Native Reply:** user Native-Replies to the original Dev bubble with `DEV-REPLY-ONE`; verify Central IM stores a new message with the Dev anchor as `reply_to` and Dev handles it.
- [x] **Second Dev Native Reply to the same bubble:** user again Native-Replies to that same original Dev bubble with `DEV-REPLY-TWO`; verify it succeeds, creates a different message id with the same `reply_to`, reaches Dev, and never emits `Reply failed`.
- [x] **Cross-actor anchor:** user Native-Replies to the PM bubble with `PM-ANCHOR-CHECK`; verify PM receives it and Dev does not.
- [x] **Opaque Reply body:** user Native-Replies to a mapped actor bubble with `/actors`; verify the body reaches the anchor actor unchanged and the iMessage interface does not execute the top-level command.
- [x] **Top-level invalid text:** user sends ordinary top-level text; verify usage feedback and no actor wake.
- [x] **Task lifecycle:** inspect Task Sys projections for the real messages; completed no-reply work ends through `task_sys.close`, parent handoff uses Task Sys status, and no message disposition operation appears.

Live evidence:

- `/actors` inbound GUID `9C81D018-A6EE-434E-9328-81A0652A16D3` listed exactly the fresh Dev and PM; neither actor received a Task.
- explicit Dev produced Central actor message `msg-6d9fdce9422f` and iMessage GUID `DD5E4398-A286-48AE-9AF7-FE6540176C67`; explicit PM produced `msg-2b32b5a7bb9a` and GUID `EE478B4E-8E9B-4D89-8C0B-6C33FDBE770C`.
- isolated Dev anchor `msg-b8186175d208` / GUID `BA7E91BF-1976-4ACA-B977-0B5A4336F1E2` accepted first reply `msg-e0135fe2259c` and second reply `msg-fd027658c418`; both have the same `reply_to=msg-b8186175d208`, reached only Dev, produced distinct completed Tasks, and returned `DEV-ACK-PROACTIVE-05` and `DEV-ACK-REPEAT-06` without `Reply failed`.
- PM anchor `msg-406851133085` / GUID `C27F868C-0770-4E16-B9C5-73EB96BD7159` accepted `msg-8c6f5dbf2d28`, reached only PM, and returned `PM-ACK-08`; Dev Task count stayed unchanged.
- Native Reply body `/actors` became PM-bound `msg-b9b9f47ff8b4` with `reply_to=msg-406851133085`; PM handled it in completed Task `task-im-message-created-5e91869893c7`. The actor response retained the `[Message From act-pm-…]` envelope, proving the top-level channel command was not executed.
- top-level `TOPLEVEL-INVALID-10`, GUID `0CCCFC2D-4258-4517-9C8B-36D80D4FFF24`, had no `thread_originator_guid`, returned only the usage prompt, and created no Dev or PM Task.
- two attempted Replies during operator disambiguation anchored the user's own `@act-dev…` GUID `CA883459-B20E-4B3C-8F89-8B41492C4D05`; the channel correctly returned `reply_unavailable`. Historical and subsequent successful records proved this was not a stable iMessage thread-root transformation, so the experimental alias mapping was removed rather than adding a fourth product behavior.

For every live case record:

- iMessage inbound GUID and `thread_originator_guid` form;
- mapped Central IM anchor id;
- created reply message id and `reply_to`;
- target actor id;
- Task Sys task id/final status where applicable;
- user-visible response;
- relevant service/actor errors;
- cleanup state.

If any unexpected result appears, stop acceptance, write the smallest failing automated regression, observe RED, implement the minimal fix, rerun its focused GREEN/IMPACT proof, then resume the exact live case.

### Task 11: Operational cleanup

- [x] Stop the task-owned web/iMessage service.
- [x] Stop and delete only the fresh acceptance actors unless the user explicitly asks to preserve them:

```bash
./buddyswitch-codex instance stop <actor-id>
./buddyswitch-codex instance delete <actor-id> --yes
```

- [x] Confirm no task-owned daemon, app-server, web server, iMessage worker, socket, lock, or temporary test root remains.
- [x] Do not delete user-owned pre-existing actors or reset shared product data.

Cleanup evidence: the `fea-im` service stopped, both acceptance actors were stopped and deleted, `instance list` returned empty, focused run root `/private/tmp/bs-test-5fc43f6d-htmmginq` was absent, and no process referenced either acceptance actor or the `fea-im` Web path. The pre-existing `fea-daemon` service was restored on `127.0.0.1:8765`; listener PID `74801` and its `imsg watch` child resolve to the `fea-daemon` worktree.

## 6. Final acceptance record

Completion requires all of the following evidence in this plan:

- [x] Product: real user performs two Native Replies to one actor bubble and observes both reach the same actor.
- [x] Contract: multi-reply product tests pass; invalid anchor ownership and offline target remain rejected.
- [x] Architecture: Central IM has no processing lifecycle; Task Sys status remains the sole lifecycle truth.
- [x] Replacement: message state, disposition API, `message.mark`, permissions, prompts, tests, and current docs are absent.
- [x] Operations: focused runner and real actor/service resources are clean.
- [x] Scope: no Task Sys ingest dedupe, transport redesign, read receipt, parser rewrite, or unrelated refactor entered the diff.

Final report must include exact focused commands/results, RED/GREEN evidence ids, live actor ids/case results, omitted checks, residual risk, and cleanup status. Do not claim completion while real iMessage acceptance is pending or blocked.

## 7. Execution log

Record progress here as implementation proceeds.

```text
Current state: ACCEPTED; IMPLEMENTATION, AUTOMATED PROOF, LIVE IMESSAGE PROOF, AND CLEANUP COMPLETE
HEAD: b7525b07ca41dadecebbf13931d28750dfb354ac
Worktree: clean before plan creation
Plan review: corrected Task 1 to reproduce actor anchor -> external user Reply directly
Baseline evidence: 3fb575806d8a4e41a6a0ca33416f715f; prior one-shot test passed
RED evidence: 9746e9f0b34a4f6bbbebf9facab42443; second Reply rejected with E_IM_REPLY_TARGET after first marked anchor replied
GREEN/IMPACT evidence: recorded below; all selected focused boundaries passed
Task 2 GREEN: d53f4827b8334c0686761ef69e108e41; multi-reply exact target passed
Task 2 safety IMPACT: 8c7d47519c7742e78de713d9f5c6ce3b; ownership/offline/conversation boundaries passed
Task 3 RED: 624bac6666684aa3947b87f8ed9e5360; state directory, HTTP route, and External Session method remained live
Task 3 GREEN: e5099666e16849a0bed1ddf333b57559; 33 tests and 8 subtests passed
Task 4 RED: fd45ca23663147b492beb2f521bc40bb; mark registry and processing-state semantics remained live
Task 4 GREEN: c6acbde8a8444261a8918b55765a8251; 37 contract tests and 493 subtests passed
Task 4 client IMPACT: 5b5adef8e8fc441b803a06415a82248a; 8 tests and 5 subtests passed
Task 5 RED: 98573557fe444776b562a7a902fd0012; runtime and skill still taught message processing state
Task 5 GREEN: 780a8b47587a44a08318cabd1d714c29; 42 tests and 118 subtests passed
Task 6 RED: 85607ec7ff8749d7afaf757144c22d0b; live architecture doc still taught disposition behavior; multi-reply iMessage consumer test already passed
Verification expansion RED: 7b9feae4b8ee413198adeaff30700274; process test still exercised the removed state/action workflow
Task 6 GREEN: 8947ce0935fb4fd3bb688b260180bb7e; 19 tests and 108 subtests passed
Initial affected verification: fcc3e2da6f904f4aa3968a86bb0c681a; 157 tests and 739 subtests passed
Verification expansion GREEN: a8479c7a442744d198a41aad95a89db2; 29 tests and 72 subtests passed
Frozen affected verification: afdb5f633bbd4a14abec4e6ab3885bda; 186 tests and 811 subtests passed
Final post-acceptance focused verification: 5fc43f6d5b8e47dc8fcb7e461fee818d; 185 tests and 772 subtests passed, including the iMessage parser and expanded consumer/process boundaries
Final code review: found stale one-shot failure guidance and missing rejection-path no-fallback proof; no Critical findings
Review RED: 35918ba04b544a3dab0528370857f40c; failure path still emitted `Reply to a newer actor message`
Review GREEN: ac5cc4fa3621407c95cea05888db12f8; failure path now emits state-neutral retry guidance and proves no target-send fallback
Final post-review focused verification: f8cb634a08c746b4933a1a4b0f3b53f5; 186 tests and 772 subtests passed
Follow-up code review: both Important findings resolved; final verdict Ready to merge
Acceptance actors: act-dev-66644ef5ce28, act-pm-1526207548ac
Live service: current fea-im Web/Central IM/iMessage worker on 127.0.0.1:8765 after user-authorized shutdown of the pre-existing worker
Live actor acceptance: passed; /actors, explicit Dev/PM, repeated Dev anchor, cross-actor PM, opaque /actors Reply, invalid top-level, and Task lifecycle all proved
Native Reply investigation: two rows anchored the user's own @Dev message and were correctly unavailable; a proposed thread-root alias was RED/GREEN explored, disproved by historical/current exact actor-anchor evidence, and fully removed before acceptance
Cleanup: complete; task-owned service stopped, acceptance actors deleted, runner root absent, and pre-existing fea-daemon listener restored
```
