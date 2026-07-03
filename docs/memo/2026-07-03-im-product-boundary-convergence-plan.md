# IM Product Boundary Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Converge Central IM message semantics into the IM product core while keeping current message flows and behavior rules unchanged.

**Architecture:** Central daemon remains the basic actor runtime provider for actor registration, presence, reachability, wake, and mailbox delivery. Central IM owns message-facing semantics: contacts projection, participant identity, connection, conversation, message, event, disposition, reply target interpretation, and actor-directed send target interpretation. Tool, HTTP, Web, iMessage, and Task Sys surfaces project the IM product instead of stitching daemon actor rows and IM participants themselves.

**Tech Stack:** Python runtime code under `scripts/env/`, launcher projections under `tools/launcher/`, JSON-backed IM repository under `scripts/env/repos/messages.py`, existing `unittest` suites, and scoped `rg` residue scans.

---

## 0. Task Target Restatement

This task is not to open the `actor -> external target_identity_id` capability.

This task is not to fix iMessage outbound routing.

This task is not to introduce `peer`, a global identity registry, a new resolver framework, or a compatibility layer.

The current target is architecture convergence:

```text
central daemon
  owns actor runtime facts:
  register / heartbeat / online presence / reachability / wake / mailbox delivery

Central IM product
  owns message semantics:
  participant / connection / conversation / message / event / disposition /
  contacts projection / current send target interpretation / reply target interpretation

consumer projections
  actor tool / external HTTP session / Web / iMessage / Task Sys
  call IM product operations and do not reinterpret daemon actor rows as message semantics
```

After this task, the current user-visible message rules must still be:

1. `external -> actor` works through an external connection and an online actor target.
2. `actor -> external` with `message.send(target_identity_id="ext-...")` is still rejected.
3. `actor -> external` works only through `message.send(reply_to=external_origin_message_id, ...)` when the original direct conversation contains the active actor and the external identity.

The value of this task is not new capability. The value is that these rules are interpreted in one product owner, Central IM, instead of being scattered through tool runtime, external session, and daemon contacts naming.

## 1. `docs/bitter` Principles Applied

The plan applies these repository principles:

- Tool and prompt layering: fix the owning runtime contract, not AGENTS text or skill prose.
- Built-in product interface: IM product owns the model, rules, storage, and contracts; tools and HTTP routes are projections.
- Wrong-boundary narrowness: do not add a narrow `ext-*` special case to daemon or a new projection helper. Move semantics to the IM owner.
- Residue cleanup: a semantic replacement is incomplete while live surfaces still teach old semantics.
- Parallel boundary: reduce repeated edits in projection layers by making IM product the owning change surface.
- End-to-end contract slice: prove the real consumer loops still work, not only helper-level tests.
- Test resource lifecycle: this task should not start long-lived services; if a later smoke test starts services, it must include cleanup and residual checks.

## 2. Current Code Audit

### 2.1 IM Core Already Owns Durable Message Identity

Evidence:

- `scripts/env/services/messages.py`
  - `create_external_connection()` creates `ext-*`, persists participant and connection.
  - `send_im_message()` accepts actor or external participants, writes direct conversation, message, state, and events.
  - `_resolve_reply_conversation()` owns current `reply_to` derivation and direct conversation scope checks.
- `scripts/env/repos/messages.py`
  - persists external participants under `state/im/participants`.
  - persists connections under `state/im/connections`.
  - normalizes conversations to `identity_ids`.
  - normalizes message/event/state visibility by identity id.

Conclusion:

```text
IM storage and service can already express actor and external identities.
The current problem is not missing IM identity storage.
```

### 2.2 Actor Tool Projection Owns Too Much IM Semantics

Evidence:

- `scripts/env/tool_runtime/im_client.py`
  - `contacts()` calls `self._context.daemon.list_contacts(...)` and maps actor rows into message contact rows.
  - `send()` calls `_target_participant(..., require_reachable_actor=True)`.
  - `_target_participant()` allows external lookup only when `require_reachable_actor=False`.
  - `_actor_participant_for_identity()` directly scans daemon contact rows.

Current boundary smell:

```text
Actor tool projection is deciding what a message target identity means.
```

Target boundary:

```text
Actor tool projection should adapt context and invoke IM product operations.
IM product should decide how current message contacts and current actor-directed targets are interpreted.
```

### 2.3 External HTTP Session Also Owns Too Much IM Semantics

Evidence:

- `tools/launcher/external_im_session.py`
  - owns `BLOCKED_ACTOR_STATUSES`.
  - owns `list_actors()` projection from actor rows to IM actor identity rows.
  - owns `_actor_participant_for_identity()` for external-origin sends and direct conversation reads.
- `tools/launcher/im_http_router.py`
  - correctly acts as HTTP projection, but routes into `ExternalImSession`, where the actor target semantics currently live.

Current boundary smell:

```text
External session projection and actor tool projection duplicate actor row interpretation.
```

Target boundary:

```text
External session should pass runtime actor rows into IM product operations and return the IM product response.
```

### 2.4 Central Daemon Has A Misleading `contacts` Runtime Surface

Evidence:

- `tools/launcher/central_daemon_core.py`
  - method `contacts.list` reads only `registry["actors"]`.
  - it returns only online actor rows.
  - it does not read IM participants or external connections.
- `scripts/env/tool_runtime/daemon_client.py`
  - exposes this runtime method as `list_contacts()`.
- `scripts/env/tool_runtime/context.py`
  - exposes `DaemonAccess.list_contacts()`.
- `scripts/env/tools/message/tool.py`
  - `message.contacts` is a valid IM product action, but its contract text currently says it reads `central daemon online contacts`.

Correct interpretation:

```text
message.contacts is IM.
daemon contacts.list is not IM contacts; it is actor runtime online directory.
```

Target boundary:

```text
Keep `message.contacts`.
Replace daemon `contacts.list` / `list_contacts()` live surfaces with actor runtime directory naming.
Do not keep both names alive.
```

### 2.5 Task Sys Side Boundary Is Out Of Scope And Must Stay Restrictive

Evidence:

- `tools/launcher/task_sys_runtime.py` tells side frames not to start new IM conversations and to close current-source IM work with exact `reply_to` or `message.mark(absorbed)`.

This plan must not weaken that rule. Side-frame restrictions are workflow authority constraints, not the same problem as IM product boundary ownership.

## 3. Target Architecture

Target call graph for actor tool:

```text
message.contacts
  -> ActorImClient obtains actor runtime rows from daemon actor directory
  -> message_service projects current IM actor contacts
  -> tool response

message.send(target_identity_id=act-...)
  -> ActorImClient passes active actor, target id, and actor runtime rows to message_service
  -> message_service interprets current actor-directed target rule
  -> message_service.send_im_message(...)
  -> daemon wake only if target participant is actor

message.send(reply_to=...)
  -> ActorImClient passes no explicit target
  -> message_service._resolve_reply_conversation(...)
  -> existing reply behavior unchanged
```

Target call graph for external HTTP/Web/iMessage inbound:

```text
external connection
  -> ExternalImSession authenticates external connection
  -> external send uses IM product actor target interpretation
  -> message_service.send_external_connection_message(...)
  -> daemon wake only if target participant is actor
```

Target central daemon boundary:

```text
actor runtime consumer
  -> actor_directory.list_online
  -> actor.check_reachability
  -> event.deliver / signal.deliver / wake_im_actor
```

`message.contacts` remains the only live surface named contacts in the IM sense.

## 4. Non-Goals

Do not implement these in this task:

- `actor -> external` through `target_identity_id`.
- iMessage route-by-external-contact for actor-initiated outbound messages.
- external identities in daemon registry.
- a global identity resolver.
- a `peer` abstraction.
- a dual path where old daemon `contacts.list` and new actor directory methods both work.
- compatibility wrappers for old internal daemon contact method names.
- broad reformatting, unrelated refactors, or prompt-only fixes.

## 5. Required Behavior After This Task

The behavior contract is intentionally unchanged:

```text
external action
  -> external connection sends to online actor
  -> IM stores durable direct conversation, message, event, state
  -> actor wake is attempted
  -> actor reply_to original message
  -> external connection reads one consumable reply event
```

Negative behavior that must remain:

```text
actor action
  -> message.send(target_identity_id="ext-...", content="...")
  -> rejected
  -> no conversation/message/event/state mutation
```

Actor-to-actor behavior that must remain:

```text
actor action
  -> message.contacts returns online actor identity rows
  -> message.send(target_identity_id="act-...", content="...")
  -> durable message is created
  -> target actor wake is attempted
```

## 6. Implementation Plan

### Task 1: Pin Current Behavior In IM Product Tests

**Files:**

- Modify: `tests/test_im_product_core.py`
- Modify: `tests/test_message_tool_im_client.py`
- Modify: `tests/test_external_im_session.py`

- [ ] Add an IM product-core test proving external participants are persisted but are not current actor-directed send targets.

  Test intent:

  ```text
  create external connection
  authenticate it to obtain ext-...
  call the new IM product target interpretation operation with target_identity_id=ext-...
  expect E_IM_PAYLOAD and no new message files
  ```

- [ ] Add an IM product-core test proving actor runtime rows are projected to current IM actor contacts without leaking `actor_address`.

  Expected contact row shape:

  ```python
  {
      "identity": {"id": "act-...", "type": "actor"},
      "identity_id": "act-...",
      "role_id": "...",
      "reachability_status": "online",
  }
  ```

- [ ] Add an actor tool test proving `message.send(reply_to=external_origin_message_id)` still succeeds and marks the original source `replied`.

  Existing coverage is present in `tests/test_message_tool_im_client.py`; keep it green while moving ownership.

- [ ] Add or adjust external session tests proving missing/offline actor targets are rejected with current payload behavior.

  Existing coverage is present in `tests/test_external_im_session.py`; keep the user-visible error class stable unless the IM product response is made clearer in the same test.

- [ ] Run focused tests and verify any new tests fail before implementation.

  Command:

  ```bash
  python3 -m pytest tests/test_im_product_core.py tests/test_message_tool_im_client.py tests/test_external_im_session.py -q
  ```

### Task 2: Move Current Contact Projection And Actor Target Interpretation Into IM Product

**Files:**

- Modify: `scripts/env/services/messages.py`
- Modify: `scripts/env/tool_runtime/im_client.py`
- Modify: `tools/launcher/external_im_session.py`

- [ ] Add concrete IM product operations in `scripts/env/services/messages.py`.

  Target operations:

  ```text
  list_im_actor_contacts(actor_rows, role_id=None)
  actor_participant_for_current_send_target(
      actor_rows,
      target_identity_id,
      field="target_identity_id",
      active_actor_id=None,
  )
  ```

  Constraints:

  - These functions may parse `ActorAddress` because actor identity projection is part of the current IM contact contract.
  - These functions must not read daemon directly.
  - These functions must not read external participants for `target_identity_id` in this phase.
  - The send target function must preserve the actor tool self-send rejection when `active_actor_id` is provided.
  - These functions must not add flags such as `allow_external`; that would create dual semantics before the capability is approved.

- [ ] Replace `ActorImClient.contacts()` row mapping with a call to `message_service.list_im_actor_contacts(...)`.

- [ ] Replace `ActorImClient._actor_participant_for_identity()` with a call to the IM product target operation.

- [ ] Remove the `require_reachable_actor` branch as a semantic owner in `ActorImClient`.

  Current conversation lookup can keep external participant lookup only where conversation reading already supports external direct conversations, but send target interpretation should no longer be owned by the projection.

- [ ] Replace `ExternalImSession.list_actors()` row mapping with a call to the IM product contact operation.

- [ ] Replace `ExternalImSession._actor_participant_for_identity()` with the same IM product target operation.

- [ ] Run focused tests.

  Command:

  ```bash
  python3 -m pytest tests/test_im_product_core.py tests/test_message_tool_im_client.py tests/test_external_im_session.py tests/test_im_http_router.py -q
  ```

### Task 3: Rename Daemon Actor Directory Surface And Delete Old Contact Names

**Files:**

- Modify: `tools/launcher/central_daemon_core.py`
- Modify: `scripts/env/tool_runtime/daemon_client.py`
- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env/tool_runtime/im_client.py`
- Modify: `scripts/env/tools/track/_impl.py`
- Modify: `tools/launcher/im_http_router.py`
- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_central_daemon_service.py`
- Modify: `tests/test_runtime_actor_profile.py`
- Modify: `tests/test_track_comment_env_tool.py`
- Modify: `tests/test_external_im_session.py`
- Modify: `tests/test_im_http_router.py`
- Modify: `tests/test_im_external_reply_loop.py`
- Modify: `tests/test_external_im_projection_contract.py`

- [ ] Replace central daemon method `contacts.list` with an actor runtime name.

  Target name:

  ```text
  actor_directory.list_online
  ```

- [ ] Replace `daemon_client.list_contacts()` with:

  ```text
  daemon_client.list_online_actors()
  ```

- [ ] Replace `DaemonAccess.list_contacts()` with:

  ```text
  DaemonAccess.list_online_actors()
  ```

- [ ] Update IM, Track, HTTP, and tests to use the new actor runtime name.

- [ ] Do not leave an alias for `contacts.list`, `list_contacts`, or `DaemonAccess.list_contacts`.

- [ ] Update central daemon tests so they describe actor directory behavior, not message contacts.

  Required test wording:

  ```text
  actor_directory.list_online returns only online actor addresses
  actor_directory.list_online filters by role without resolving message targets
  ```

- [ ] Run focused daemon and dependent projection tests.

  Command:

  ```bash
  python3 -m pytest tests/test_central_daemon_service.py tests/test_runtime_actor_profile.py tests/test_track_comment_env_tool.py tests/test_message_tool_im_client.py tests/test_external_im_session.py tests/test_im_http_router.py -q
  ```

### Task 4: Update Live Tool Contracts To Teach The New Boundary

**Files:**

- Modify: `scripts/env/tools/message/tool.py`
- Modify: `scripts/env/tools/context/_impl.py` if its compact affordance text still teaches old contact discovery wording
- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_env_tool_semantic_contract.py` if semantic text checks need current wording

- [ ] Keep `message.contacts` as the IM product contact action.

- [ ] Update wording so `message.contacts` is described as IM actor contact projection backed by actor runtime presence, not as `central daemon contacts`.

- [ ] Keep current send wording actor-directed in this phase.

  This is current behavior, not residue. Do not rewrite `target_identity_id` as external-capable until that capability is approved and implemented.

- [ ] Preserve the current external rule in contract wording:

  ```text
  external identities are valid IM participants in conversations;
  current actor-initiated new sends are actor-directed;
  external replies use reply_to inside an existing direct conversation.
  ```

- [ ] Run tool contract tests.

  Command:

  ```bash
  python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_black_box_tool_runtime.py -q
  ```

### Task 5: Add No-Residual Checks For The Boundary Replacement

**Files:**

- Create or modify a focused repository consistency test if one already exists for boundary scans.
- Candidate: `tests/test_repo_consistency.py`
- If no suitable file exists, add a focused test file such as `tests/test_im_boundary_residue.py`.

- [ ] Add a scoped scan test over live runtime surfaces.

  Include:

  ```text
  scripts/env/
  tools/launcher/
  tests/
  buddyswitch/
  ```

  Exclude:

  ```text
  docs/bitter/
  docs/memo/
  historical specs and archived logs
  ```

- [ ] The scan must fail on these stale live terms:

  ```text
  contacts.list
  list_contacts
  central daemon contacts
  central daemon online contacts
  ```

- [ ] The scan must not flag `message.contacts`, because that remains the IM product action.

- [ ] Run the residue test.

  Command:

  ```bash
  python3 -m pytest tests/test_im_boundary_residue.py -q
  ```

  If the scan lives in an existing consistency file, run that exact test path instead.

### Task 6: Prove End-To-End Contract Slices Still Work

**Files:**

- Existing tests:
  - `tests/test_im_external_reply_loop.py`
  - `tests/test_im_product_core.py`
  - `tests/test_message_tool_im_client.py`
  - `tests/test_external_im_session.py`
  - `tests/test_im_http_router.py`
  - `tests/test_web_management.py` focused IM cases only

- [ ] Run the external reply loop.

  Contract sentence:

  ```text
  external sends to actor -> actor receives durable IM message -> actor reply_to original message -> external reads one reply event.
  ```

  Command:

  ```bash
  python3 -m pytest tests/test_im_external_reply_loop.py -q
  ```

- [ ] Run product and projection focused suites.

  Command:

  ```bash
  python3 -m pytest tests/test_im_product_core.py tests/test_message_tool_im_client.py tests/test_external_im_session.py tests/test_im_http_router.py -q
  ```

- [ ] Run focused Web management IM projection cases if they do not start uncontrolled long-lived services.

  Command:

  ```bash
  python3 -m pytest tests/test_web_management.py -q -k "im or IM"
  ```

  If this selected run starts persistent services without cleanup proof, do not run the broad command. Use the smallest focused unit/integration tests instead and record the lifecycle blocker.

## 7. Old Semantics To Remove

These live semantics should not remain after implementation:

```text
daemon method named contacts.list
daemon_client.list_contacts()
DaemonAccess.list_contacts()
tool/runtime code treating daemon contacts as IM target interpretation
ActorImClient owning actor target participant interpretation
ExternalImSession owning actor target participant interpretation
tool contract wording that says message.contacts reads central daemon contacts
```

These are allowed to remain:

```text
message.contacts
message.contacts permission name
message.contacts tool action name
actor-directed target wording for current message.send behavior
Task Sys side-frame restriction against starting new IM conversations
historical mentions in docs/memo and docs/bitter
```

## 8. Acceptance Checklist

- [ ] Current behavior rules are unchanged:
  - external can send to actor.
  - actor cannot use `target_identity_id="ext-..."`.
  - actor can reply to external only through valid `reply_to`.
- [ ] IM product owns contact projection and current target interpretation.
- [ ] Actor tool projection no longer maps daemon rows into IM contact rows itself.
- [ ] External session projection no longer maps daemon rows into IM actor identity rows itself.
- [ ] Daemon live surface uses actor runtime directory naming.
- [ ] No old daemon contact aliases remain.
- [ ] Tool contract text teaches IM product ownership and actor runtime backing without saying daemon contacts are IM contacts.
- [ ] Behavior tests pass.
- [ ] End-to-end IM contract slice passes.
- [ ] Scoped residue scan passes.

## 9. Verification Commands

Run these before claiming implementation complete:

```bash
python3 -m pytest tests/test_im_product_core.py tests/test_message_tool_im_client.py tests/test_external_im_session.py tests/test_im_http_router.py -q
python3 -m pytest tests/test_central_daemon_service.py tests/test_runtime_actor_profile.py tests/test_track_comment_env_tool.py -q
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_black_box_tool_runtime.py -q
python3 -m pytest tests/test_im_external_reply_loop.py -q
```

Run the residue scan as either an automated test or a manual pre-commit check:

```bash
rg -n "contacts\\.list|list_contacts|central daemon contacts|central daemon online contacts" scripts/env tools/launcher tests buddyswitch
```

Expected result:

```text
No live hits, except deliberate references inside the residue test's forbidden term list.
```

## 10. Next Capability After This Plan

Only after this boundary convergence lands and passes should the next capability be evaluated:

```text
actor -> existing external identity through message.send(target_identity_id="ext-...")
```

That later task must be a separate behavior change with its own tests and channel routing review. It should not be hidden inside this convergence task.
