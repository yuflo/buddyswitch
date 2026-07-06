# Communication Identity Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After Task A, make all communication paths consume identity directly and delete `ActorAddress` plus IM participant private identity schema.

**Architecture:** Communication becomes an identity consumer. Daemon registry, runtime send tools, IM repos/services, external session bridges, and product-facing projections use `IdentityRef` / identity id as their addressing contract. IM stores message participants as sender/target identities, not `{"kind": ..., "actor_address": ...}` or `{"kind": ..., "external_id": ...}` payloads.

**Tech Stack:** Python runtime code under `scripts/env/`, launcher daemon code under `tools/launcher/`, IM HTTP/session bridges under `tools/launcher/`, JSON-backed repos, existing `unittest`/`pytest` suites, and scoped `rg` residue scans over communication surfaces.

---

## 0. Task Target Restatement

Task B is the communication / IM identity cutover task.

It depends on Task A being complete:

```text
Task A owns identity schema.
Task B consumes identity schema.
```

Task B does not define actor/external static identity fields. It removes communication-owned identity substitutes.

The target invariant is:

```text
message delivery, reachability, read state, external session routing, and product communication projections
address people and actors by identity

not by ActorAddress
not by IM participant kind payloads
not by actor/external duplicate static schema
```

Task B completes when these are true:

1. daemon register/heartbeat/reachability/signal APIs use actor identity id, not `ActorAddress`.
2. runtime actor message send resolves reachable actor targets through identity, not through `actor_address`.
3. IM repos/services store sender/target/viewer identity references, not private participant schemas.
4. external connections reference an external identity profile from Task A, not an IM-owned `external_id` participant identity.
5. existing allowed flows still work:
   - external -> actor
   - actor -> actor
   - actor -> external by `reply_to`
6. actor -> external active send by `target_identity_id="ext-..."` still rejects clearly.
7. live code has no `ActorAddress`, `actor_address`, or IM participant identity schema residue.

## 1. `docs/bitter` Principles Applied

- Residue cleanup: this task is incomplete while any live communication surface still accepts or emits old identity schema.
- Wrong-boundary narrowness: changing only `ActorImClient.send` would miss daemon reachability, IM storage, bridges, and product projections.
- Built-in product interface: product communication contracts must expose identity, not daemon internals.
- End-to-end contract slice: verification must cover at least one full external -> actor -> reply path and one actor -> actor path.
- Parallel boundary: split by product slice. Task B owns communication consumers; Task A owns identity schema.
- Tool and prompt layering: fix runtime contracts and tool outputs instead of relying on role instructions.
- Test lifecycle: daemon/session tests must clean created registry and runtime state.

## 2. Current Code Audit

Evidence from current live code:

- `tools/launcher/central_daemon_core.py`
  - imports `ActorAddress`.
  - registry rows store `actor_address`.
  - register, unregister, heartbeat, reachability, list-online, and signal paths address actors by actor address.
- `scripts/env/tool_runtime/context.py`
  - `DaemonAccess` constructs `_actor_address`.
  - context exposes `actor_address`.
- `scripts/env/repos/messages.py`
  - imports `identity_from_im_participant` and `ActorAddress`.
  - defines `im_participant_key`, `im_identity_id_for_participant`, and `im_participant_ref`.
  - actor participant payload is `{"kind": "actor", "actor_address": ...}`.
  - external participant payload is `{"kind": "external", "external_id": ...}`.
- `scripts/env/services/messages.py`
  - derives actor addresses from runtime registry rows.
  - `list_im_actor_contacts` and send target selection are actor-address based.
  - external connections create external participants separately from the identity module.
- `tools/launcher/external_im_session.py`
  - builds external participant payloads from connection rows.
- Product surfaces and tests still search for, serialize, or assert old communication identity fields.

Conclusion:

```text
communication currently has two addressing models:
  daemon actor_address for actor reachability
  IM participant payload for message storage and external sessions

Task B replaces both with identity references.
```

## 3. Target Communication Model

### 3.1 Daemon Reachability Contract

Daemon reachability should be keyed by actor identity:

```python
register_actor(identity_id="act-pm-...", role_id="pm", ...)
heartbeat_actor(identity_id="act-pm-...")
is_actor_reachable(identity_id="act-pm-...")
wake_actor(identity_id="act-pm-...")
signal_actor(identity_id="act-pm-...", ...)
```

Rules:

- daemon may keep runtime facts: process id, endpoint, workspace path, last heartbeat, online status, role runtime metadata.
- daemon must not define actor static identity schema.
- daemon must not require `ActorAddress`.
- list contacts returns reachable actor identities plus runtime reachability facts, not actor address objects.

### 3.2 Runtime Send Contract

Actor runtime send should resolve `target_identity_id` as identity:

```python
message.send(target_identity_id="act-designer-...")
```

Allowed in Task B:

```text
actor -> actor by target actor identity
actor -> external by reply_to only
external -> actor through bridge/session target actor identity
```

Rejected in Task B:

```text
actor -> external by target_identity_id="ext-..."
```

Reason for the rejection:

```text
identity can identify an external user,
but active outbound external delivery also needs channel routing authority and connection context.

reply_to has that context through the existing conversation.
target_identity_id alone does not.
```

### 3.3 IM Storage Contract

Messages should store identity references:

```python
{
    "sender_identity": {"id": "act-pm-...", "type": "actor"},
    "target_identity": {"id": "act-designer-...", "type": "actor"},
    "reply_to": None,
}
```

External conversation messages should store:

```python
{
    "sender_identity": {"id": "ext-user-...", "type": "external"},
    "target_identity": {"id": "act-pm-...", "type": "actor"},
    "external_connection_id": "imsg-...",
}
```

Deleted shapes:

```python
{"kind": "actor", "actor_address": ...}
{"kind": "external", "external_id": ...}
```

### 3.4 External Bridge Contract

External session bridges should:

- resolve or create an `ExternalIdentityProfile`;
- attach external connection facts to that identity;
- send inbound messages with `sender_identity=external_identity`;
- send actor replies by reading `reply_to` conversation routing context;
- reject active actor -> external send when no reply conversation context exists.

External connection is not identity. It is a delivery fact about an external identity.

## 4. Non-Goals

Do not implement these in Task B:

- actor -> external active outbound by `target_identity_id="ext-..."`.
- new external channel routing policy.
- generic connection router.
- compatibility wrappers for `ActorAddress`, `actor_address`, or IM participant payloads.
- broad rename-only cleanup outside communication consumers.
- identity schema ownership changes covered by Task A.

## 5. Implementation Tasks

### Task B1: Add Red Tests For Identity-Based Communication Contracts

**Files:**

- Create: `tests/test_communication_identity_cutover.py`
- Modify focused existing tests that assert old communication shapes
- Test: `tests/test_communication_identity_cutover.py`

- [ ] **Step 1: Add daemon reachability identity tests**

Create tests that assert daemon registry and contact listing accept actor identity ids and return identity ids without `actor_address`.

Expected assertions:

```python
assert row["identity_id"].startswith("act-")
assert "actor_address" not in row
```

- [ ] **Step 2: Add IM storage identity tests**

Create tests that save and read IM messages with:

```python
sender_identity={"id": "act-pm-b", "type": "actor"}
target_identity={"id": "act-design-b", "type": "actor"}
```

Expected assertions:

```python
assert message["sender_identity"]["id"] == "act-pm-b"
assert message["target_identity"]["id"] == "act-design-b"
assert "participant" not in message
```

- [ ] **Step 3: Add external reply-only behavior tests**

Test this sequence:

1. external identity sends inbound message to actor identity.
2. actor replies with `reply_to`.
3. actor active send to `target_identity_id="ext-..."` rejects.

Expected assertion for active external send:

```python
assert "external active send requires reply_to" in error_message
```

### Task B2: Replace Daemon Actor Address With Actor Identity

**Files:**

- Modify: `tools/launcher/central_daemon_core.py`
- Modify: daemon client helpers under `scripts/env/` and launcher tools
- Test: daemon reachability tests from Task B1

- [ ] **Step 1: Change registry row key**

Replace:

```text
actor_address
```

with:

```text
identity_id
```

Daemon runtime rows may still store:

```text
role_id
endpoint
pid
workspace_path
last_heartbeat_at
online
```

- [ ] **Step 2: Change daemon API payloads**

Register, unregister, heartbeat, reachability, wake, and signal payloads should accept:

```python
{"identity_id": "act-pm-...", "role_id": "pm"}
```

They should not accept:

```python
{"actor_address": ...}
```

- [ ] **Step 3: Change list contacts**

`daemon.list_contacts()` should return reachable actor identities:

```python
{
    "identity": {"id": "act-designer-...", "type": "actor"},
    "role_id": "designer",
    "reachable": True,
}
```

This is still a reachability view, not a global identity resolver.

### Task B3: Replace Runtime Communication Context Consumers

**Files:**

- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env/tool_runtime/registry.py`
- Modify message tool runtime projection files
- Test: actor tool message-send tests

- [ ] **Step 1: Remove `DaemonAccess._actor_address`**

`DaemonAccess` should hold:

```python
current_identity: IdentityRef
```

and call daemon with `current_identity.id`.

- [ ] **Step 2: Change actor send target resolution**

`ActorImClient.send(target_identity_id=...)` should:

1. parse target as `IdentityRef`.
2. if actor identity, require reachable actor contact from daemon.
3. if external identity and no `reply_to`, reject.
4. if `reply_to`, delegate to IM service conversation routing.

- [ ] **Step 3: Keep rejection explicit**

The rejected path should explain:

```text
target external identity is valid, but active external delivery requires reply_to conversation routing
```

### Task B4: Replace IM Repo Participant Schema With Identity Fields

**Files:**

- Modify: `scripts/env/repos/messages.py`
- Modify: message JSON fixtures if present
- Test: IM repo tests from Task B1

- [ ] **Step 1: Delete participant helpers**

Remove:

```text
im_participant_key
im_identity_id_for_participant
im_participant_ref
identity_from_im_participant
```

- [ ] **Step 2: Store sender and target identities**

Message records use:

```text
sender_identity
target_identity
viewer_identity for read state
```

No `participant`, `from_participant`, `to_participant`, `actor_address`, or `external_id`.

- [ ] **Step 3: Store connection facts separately**

External connection rows may keep:

```text
external_connection_id
provider
channel_address
last_seen_at
```

They must reference:

```text
external_identity_id
```

### Task B5: Replace IM Service And Bridge Callers

**Files:**

- Modify: `scripts/env/services/messages.py`
- Modify: `tools/launcher/external_im_session.py`
- Modify: IM HTTP router / iMessage adapter files found by code search
- Test: external inbound and actor reply tests

- [ ] **Step 1: Change service signatures**

Use signatures shaped like:

```python
send_im_message(
    sender_identity=IdentityRef(...),
    target_identity=IdentityRef(...) | None,
    reply_to=...,
)
```

and:

```python
read_im_events(viewer_identity=IdentityRef(...))
```

- [ ] **Step 2: Change external inbound bridge**

Inbound external messages should:

1. resolve/create `ExternalIdentityProfile`;
2. resolve target actor identity;
3. store message with external sender identity and actor target identity;
4. attach external connection facts separately.

- [ ] **Step 3: Change actor reply bridge**

Actor reply should:

1. load original message by `reply_to`;
2. confirm one side is current actor identity;
3. find the other side external identity;
4. use original conversation connection facts for delivery.

### Task B6: Replace Product Communication Projections

**Files:**

- Modify communication projections in web/runtime/notification/context surfaces found by search
- Test existing product projection tests plus focused communication identity tests

- [ ] **Step 1: Replace old fields in emitted payloads**

Replace:

```text
actor_address
target_actor_address
source_actor_address
participant.actor_address
participant.external_id
```

with:

```text
identity
target_identity
source_identity
sender_identity
viewer_identity
```

- [ ] **Step 2: Update tests to assert new contract**

Tests should assert identity payloads and reject old communication identity keys.

- [ ] **Step 3: Keep UI/API behavior stable**

Human-visible flow should remain:

```text
external sends to actor
actor replies
actor sends to reachable actor
```

Only the internal addressing contract changes.

### Task B7: Run Focused Verification

**Files:**

- Modify: none
- Test: focused communication tests

- [ ] **Step 1: Run focused tests**

Run:

```bash
pytest tests/test_communication_identity_cutover.py -q
```

Expected result:

```text
PASS
```

- [ ] **Step 2: Run affected existing tests**

Run:

```bash
pytest \
  tests/test_im_message_service.py \
  tests/test_external_im_session.py \
  tests/test_tool_runtime_message.py \
  tests/test_web_management.py -q
```

Expected result:

```text
PASS
```

### Task B8: Run Residue And Behavior Acceptance

**Files:**

- Modify: none
- Test: residue scans plus behavior suites

- [ ] **Step 1: Run exact residue scan**

Run:

```bash
rg -n "ActorAddress|actor_address|target_actor_address|source_actor_address|from_actor_address|to_actor_address|identity_from_im_participant|participant\\.actor_address|participant\\.external_id|im_participant_key|im_identity_id_for_participant|im_participant_ref" scripts tools tests buddyswitch
```

Expected result:

```text
rg exits 1 with no live hits except the residue test forbidden-term list
```

- [ ] **Step 2: Run communication behavior verification**

Run the smallest available end-to-end or integration test that proves:

```text
external -> actor works
actor -> external reply_to works
actor -> actor works
actor -> external active target_identity_id rejects
```

Expected result:

```text
PASS
```

## 6. Completion Audit

Task B is complete only when:

- daemon reachability is identity based.
- runtime message send target resolution is identity based.
- IM records no longer store participant identity payloads.
- external connection facts reference external identity.
- product communication projections emit identity fields.
- actor -> external active send remains closed without `reply_to`.
- focused behavior tests pass.
- residue scans have no live old communication identity hits.

Task B is aligned with Task A only if it consumes `env.domain.identity` and does not define any actor/external static identity schema of its own.
