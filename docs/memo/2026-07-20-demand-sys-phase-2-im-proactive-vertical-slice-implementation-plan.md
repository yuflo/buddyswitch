# Demand Sys Phase 2 IM Proactive Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the one live `im.message.created -> Task Sys` route with an active-actor `IM -> Demand capture -> Demand Check` vertical slice that is observable through real IM, a real actor, canonical Demand state, and zero Task effects.

**Architecture:** The IM handler validates one exact target-visible message/event pair and maps it to source-normalized intake. A Demand-owned daemon adapter calls the existing Demand domain owner, derives attention from durable pending revisions, and uses one generic daemon `input_actor` capability; the actor alone performs two-pass organization and acknowledgement. Task Sys receives no IM source and has no Demand dependency.

**Tech Stack:** Python 3, existing JSON runtime objects and actor aggregate transactions, existing daemon mailbox/local-trigger contracts, existing Actor Session/app-server input primitive, Central IM HTTP API, BuddySwitch public CLI, installed Codex runtime, `unittest`/`pytest` only through `./buddyswitch-test`.

**Design:** `docs/memo/2026-07-19-demand-sys-phase-2-im-proactive-vertical-slice-design.md`

**Status:** implemented, verified, accepted, and committed on 2026-07-20

**Commit policy:** Per the user instruction, do not commit this plan separately and do not create per-task commits. Keep the plan resumable in the dirty worktree, verify coherent blocks, and create one intentional Phase 2 commit only after implementation, replacement audit, focused proof, real-actor acceptance, and cleanup all succeed.

---

## 1. Frozen acceptance claim

The current bottleneck is that the first real inbound source still creates Task
execution before Demand organization exists. Phase 2 is accepted only when this
path is the single current truth:

```text
external IM POST /api/im/messages
  -> Central IM saves Message + target-visible Event
  -> im.message.created reaches the active target daemon
  -> ImMessageCreatedHandler validates the exact source fact
  -> demand_sys_daemon_adapter.capture_inbound
  -> demand_sys.create + demand_sys.check
  -> DaemonRuntime.input_actor(DEMAND_CHECK_PROMPT)
  -> actor demand_sys.check/get_many/organization/complete_check
  -> public Demand projection explains the result

Task records for the fresh actor: []
IM-to-Task ingress functions: 0
Demand-to-Task imports/calls: 0
Demand writes outside demand_sys domain/repository: 0
```

The real-actor C/U/D scenario is:

```text
C: Support user data CSV export.
U: Fix payment request timeout.
D: CSV export must also include the user timezone.

final C: live, merged timezone content, source refs from C and D
final U: live independent root
final D: terminal absorbed -> C
all three: checked_revision == revision
public Task list: []
```

## 2. Scope and protected boundaries

### In scope

- active target actor only;
- only `im.message.created`;
- exact IM message/event read and validation;
- deterministic source-to-Demand mapping;
- durable pending attention and generic actor start/steer;
- accurate IM handler failure reporting;
- complete retirement of IM-specific Task ingress and Task prompts;
- direct, architecture, integration, and real-actor proof;
- current architecture-document update after executable behavior is green.

### Out of scope

- Track cutover;
- offline actor capture or replay;
- startup pending recovery;
- retry workers, queues, event buses, ChangeSet ledgers, schedulers, or rule engines;
- Demand priority or Task scheduling;
- Demand-to-Task ids, callbacks, subscriptions, imports, transactions, or completion reconciliation;
- direct actor input as inbound Demand;
- new public Demand mutation endpoints;
- a new HTTP response field solely for raw daemon handler status;
- aliases, feature flags, fallbacks, dual reads, dual writes, migration wrappers, or old/new routing switches.

The current external IM response keeps its public `actor_handling_status` field.
`submitted` means the daemon reported `handled`; `handling_failed` means the
mailbox or owned handler did not handle successfully. Exact daemon status remains
visible in the daemon log/state and is not copied into a second HTTP schema.

## 3. Ownership map

| Owner | Current Phase 2 responsibility |
| --- | --- |
| Central IM repository/service | Persist and identity-scope Message/Event truth; add exact event read |
| `ImMessageCreatedHandler` | Validate trigger target and exact IM fact; map to intake; call one Demand adapter |
| `demand_sys_daemon_adapter` | Derive actor target, call Demand owner, evaluate pending attention, request generic actor input |
| Demand domain/repository | Sole lifecycle, revision, organization, acknowledgement, and persistence owner |
| `DaemonRuntime` | Product-neutral `input_actor(text)` host capability only |
| Actor | Semantic matching, relation/lineage action choice, and exact revision acknowledgement |
| Task Sys | Continue serving Track and actor-owned Task actions; explicitly reject retired IM ingress |
| Generic daemon core/mailbox/state/client | Transport, dispatch, logs, and host state without Demand semantics |

Dependency direction:

```text
IM handler -> IM read service
IM handler -> Demand daemon adapter
Demand daemon adapter -> Demand domain
Demand daemon adapter -> generic DaemonRuntime capability
DaemonRuntime -> Actor Session input primitive

Demand domain -X-> IM / daemon / Task
generic daemon -X-> Demand
Task Sys -X-> IM / Demand
```

## 4. File map

### New files

| File | Sole responsibility |
| --- | --- |
| `tools/launcher/demand_sys_daemon_adapter.py` | Demand-owned inbound capture and pending-attention adapter |
| `tests/unit/demand_sys/test_daemon_adapter.py` | Adapter mapping-independent attention, replay, receipt, and no-Task proof |
| `docs/memo/2026-07-20-demand-sys-phase-2-im-proactive-vertical-slice-implementation-plan.md` | Resumable Phase 2 execution state and evidence |

### Modified production files

| File | Exact change |
| --- | --- |
| `scripts/env/repos/messages.py` | Add exact event lookup by event id and visible identity |
| `scripts/env/services/messages.py` | Add identity-scoped `get_im_event` service response |
| `tools/launcher/daemon_runtime.py` | Add only generic `input_actor(text)` delegation |
| `tools/launcher/im_wake_handler.py` | Replace Task creation with exact IM validation and Demand capture |
| `scripts/env/tool_runtime/im_actor_delivery.py` | Map any non-`handled` daemon result to `handling_failed` |
| `tools/launcher/task_sys_ingress.py` | Delete `ingest_im_message`; retain only current Track helper |
| `scripts/env/domain/task_sys.py` | Reject `im.message.created` before persistence |
| `tools/launcher/task_sys_runtime.py` | Delete IM-specific message capability/prompt branches |
| `docs/arch/demand-sys-architecture.md` | Replace Phase 1 isolation statement with implemented Phase 2 boundary |
| `docs/arch/daemon-service-architecture.md` | Record generic actor input as a host runtime capability |
| `docs/memo/2026-07-19-demand-sys-phase-2-im-proactive-vertical-slice-design.md` | Mark implemented status and clarify public-vs-daemon handling observability |

### Modified tests

| File | Proof |
| --- | --- |
| `tests/integration/im/test_product_core.py` | Exact identity-visible event repository/service read |
| `tests/unit/daemon/test_service_contract.py` | Exact `DaemonRuntime` surface and Actor Session delegation |
| `tests/unit/im/test_wake_handler.py` | Exact fact validation, deterministic intake, handler failure, and no Task |
| `tests/unit/im/test_actor_delivery.py` | Failed/ignored daemon handling is externally `handling_failed` |
| `tests/integration/im/test_external_reply_loop.py` | Real mailbox/local-trigger reaches Demand and actor input, never Task |
| `tests/integration/task_sys/test_substrate.py` | Task domain rejects IM without changing Task bytes |
| `tests/unit/task_sys/test_direct_input_retirement.py` | Task ingress retains Track only; direct input and IM remain absent |
| `tests/unit/task_sys/test_runtime_executor.py` | Delete tests and fixtures that teach IM-specific Task frames; retain generic regressions |
| `tests/unit/architecture/test_demand_sys_boundaries.py` | Exact Phase 2 allowed adapter and forbidden dependency laws |

No change is planned for `instance_daemon.py`, `message_inbound.py`,
`notification_center.py`, `actor_session.py`, `app_server.py`, the Demand schema,
the Demand actor tool, the public Demand CLI, Track handler/runtime, or generic
daemon core/mailbox/state/client. Their current contracts are reused.

## 5. Exact implementation contracts

### 5.1 IM exact event read

```python
def get_im_event(
    event_id: str,
    identity: dict[str, Any] | str,
) -> dict[str, Any] | None:
    normalized_event_id = runtime_files.require_id(event_id, "event_id")
    identity_id = im_identity_id_for_row(identity, "identity_id")
    path = _im_dir("events") / f"{normalized_event_id}--{_identity_filename_key(identity_id)}.json"
    if not path.exists():
        return None
    return runtime_files.read_json_object(path)
```

```python
def get_im_event(*, identity: dict[str, Any], event_id: str) -> dict[str, Any]:
    from env.repos import messages as message_repo

    identity_ref = _identity_ref(identity)
    event = message_repo.get_im_event(event_id, identity_ref)
    if event is None:
        return _im_not_found(f"event not found: {event_id}")
    return {"ok": True, "event": event}
```

This is a direct path read, not a list scan. A row stored for the sender under the
same event id does not make it visible to another identity.

### 5.2 Generic actor input

```python
def input_actor(self, text: str) -> dict[str, Any]:
    return dict(
        actor_session.input_actor_turn(
            socket_path=self.context.socket_path,
            instance_json=self.context.instance_json,
            thread_id=self.context.main_thread_id,
            text=text,
            permissions=self.context.permissions,
        )
    )
```

The method contains no Demand token, prompt, pending policy, id, schema, or error.
The public handler-facing method set becomes exactly
`{"parent_activity", "input_actor"}`.

### 5.3 Demand daemon adapter

```python
DEMAND_CHECK_PROMPT = """[DEMAND CHECK]
Actor-owned Demand revisions require attention.
Call demand_sys.check(). Compare pending Demand descriptions with the live index,
load only plausible candidates with demand_sys.get_many, apply only necessary
Demand organization actions, and call demand_sys.complete_check with the exact
revisions observed. Do not create or modify Task Sys during this Demand Check."""

def _actor_input_receipt(result: Any) -> dict[str, str]:
    if not isinstance(result, Mapping):
        raise RuntimeError("actor input returned a non-object result")
    action = result.get("action")
    if action not in {"start", "steer"}:
        raise RuntimeError("actor input action must be start or steer")
    turn_id = runtime_files.require_id(result.get("turn_id"), "actor input turn_id")
    return {"action": action, "turn_id": turn_id}

def capture_inbound(
    context: daemon_contracts.DaemonContext,
    runtime: Any,
    *,
    intake_key: str,
    description: str,
    detail: str,
    source_refs: list[Mapping[str, Any]],
) -> dict[str, Any]:
    actor_target = {
        "actor_id": runtime_files.require_id(context.actor_id, "context.actor_id"),
        "role_id": runtime_files.require_id(context.role, "context.role"),
    }
    created = demand_sys.create(
        actor_target,
        intake_key,
        description,
        detail,
        source_refs,
    )
    pending = demand_sys.check(actor_target)
    actor_input = None
    if pending["pending_count"] > 0:
        actor_input = _actor_input_receipt(runtime.input_actor(DEMAND_CHECK_PROMPT))
    return {
        "demand_id": created["demand_id"],
        "revision": created["revision"],
        "capture_state_changed": created["state_changed"],
        "pending_count": pending["pending_count"],
        "attention_requested": pending["pending_count"] > 0,
        "actor_input": actor_input,
    }
```

`_actor_input_receipt` accepts only a mapping with `action` equal to `start` or
`steer` and a non-empty `turn_id`; it returns only those two fields. It raises on
malformed input. The receipt is not persisted.

### 5.4 IM capture mapping

```python
{
    "intake_key": f"im.message.created:{message_id}",
    "description": message["content"].strip(),
    "detail": message["content"].strip(),
    "source_refs": [
        {
            "type": "im.message.created",
            "ref": {
                "message_id": message_id,
                "conversation_id": conversation_id,
                "event_id": event_id,
            },
        }
    ],
}
```

Before this mapping reaches the adapter, the handler requires:

```text
trigger target identity/role == daemon context identity/role
message.id == payload.message_id
message.conversation_id == payload.conversation_id
message.target_identity == {id: context.actor_id, type: actor}
event.event_id == payload.event_id
event.type == message.created
event.message_id == payload.message_id
event.conversation_id == payload.conversation_id
event.target_identity == message.target_identity
event.visible_to_identity_id == context.actor_id
```

Any service error or mismatch returns `HandlerResult.failed` before Demand or Task
mutation. The handler does not mutate IM disposition.

### 5.5 IM delivery result

```python
handling_status = result.get("handling_status")
if handling_status != "handled":
    return {
        "actor_handling_status": "handling_failed",
        "runtime_target": "daemon_mailbox",
        "error": f"daemon handler did not handle IM trigger: {handling_status or 'missing'}",
        "handling_status": handling_status,
    }
return {
    "actor_handling_status": "submitted",
    "runtime_target": "daemon_mailbox",
    "error": None,
    "handling_status": "handled",
}
```

The durable IM write remains accepted. This change corrects proactive handling
status only; it does not roll back or delete the message.

## Task 1: Preflight, baseline, and source identity

**Files:** no changes

- [x] **Step 1: Partition the worktree**

```bash
git status --short
git rev-parse HEAD
git diff --check
```

Observed before implementation: per the later user instruction, the standalone
design commit `9401679` was intentionally withdrawn. HEAD is
`0f49d1a30d22ce74ee5f140fbaf5ce1ca55ad22d`; the design and plan memos are the
only task-related untracked files. `.superpowers/` is unrelated and remains
unstaged and untouched. Both memos will ship in the single Phase 2 commit.

- [x] **Step 2: Establish behavior-preserving baselines**

```bash
./buddyswitch-test focused \
  tests/unit/daemon/test_service_contract.py \
  tests/unit/task_sys/test_runtime_executor.py \
  tests/integration/track/test_comment_added_handler.py
```

Expected: all current tests pass with clean runner cleanup. This baseline protects
generic daemon runtime, generic Task frames, and the still-current Track route
while IM behavior is replaced.

- [x] **Step 3: Record baseline evidence in this memo**

Append one `Verification Evidence` block using the repository testing format:

```text
Verification Evidence
- state: GREEN
- source: repo root, HEAD, tracked patch identity, and complete untracked identity
- command: exact focused command above
- environment: runner/Python identity from output
- result: exit status, pass summary, duration, cleanup state
- proves: current generic daemon, generic Task runtime, and Track path baseline
- valid-for: current dirty worktree identity
- residual-risk: IM replacement behavior has not yet been built
```

## Task 2: Exact target-visible IM event read

**Files:**

- Modify: `scripts/env/repos/messages.py`
- Modify: `scripts/env/services/messages.py`
- Modify: `tests/integration/im/test_product_core.py`

- [x] **Step 1: Add the exact RED case**

Add `test_exact_im_event_read_is_visible_only_to_named_identity` to
`ImProductCoreTests`. Its core assertions are:

```python
sent = message_service.send_im_message(
    sender_identity=external,
    target_identity=actor["identity"],
    content="Exact event read probe.",
)
event_id = sent["event_id"]

repo_row = message_repo.get_im_event(event_id, actor["identity"])
service_row = message_service.get_im_event(
    identity=actor["identity"],
    event_id=event_id,
)
outsider_row = message_service.get_im_event(
    identity=outsider,
    event_id=event_id,
)

self.assertEqual(repo_row["event_id"], event_id)
self.assertEqual(repo_row["message_id"], sent["message"]["id"])
self.assertEqual(repo_row["visible_to_identity_id"], actor["identity_id"])
self.assertEqual(service_row, {"ok": True, "event": repo_row})
self.assertFalse(outsider_row["ok"])
self.assertEqual(outsider_row["error"]["code"], "E_IM_NOT_FOUND")
```

Create `outsider` with `_external_session(display_name="event outsider")` so it
has a valid identity but no visible event file.

- [x] **Step 2: Run RED**

```bash
./buddyswitch-test focused \
  tests/integration/im/test_product_core.py::ImProductCoreTests::test_exact_im_event_read_is_visible_only_to_named_identity
```

Expected: fail because repository/service `get_im_event` do not exist. A setup or
environment failure is not valid RED.

- [x] **Step 3: Implement the two exact reads**

Implement the signatures and bodies from §5.1. Keep repository identity/path
normalization in the repository and service response/error ownership in the
service. Do not implement the read by filtering `list_im_events_for_identity`.

- [x] **Step 4: Run GREEN at the owner boundary**

```bash
./buddyswitch-test focused \
  tests/integration/im/test_product_core.py::ImProductCoreTests::test_exact_im_event_read_is_visible_only_to_named_identity
```

Expected: pass; runner root removed.

## Task 3: Generic daemon actor-input capability

**Files:**

- Modify: `tools/launcher/daemon_runtime.py`
- Modify: `tests/unit/daemon/test_service_contract.py`

- [x] **Step 1: Add daemon runtime RED**

Add `test_daemon_runtime_input_actor_delegates_exact_context_to_actor_session`:

```python
with tempfile.TemporaryDirectory() as temp_root:
    instance = self._instance(temp_root)
    context = self.core.load_daemon_context(instance["instance_json"])
    calls: list[dict[str, Any]] = []
    original = daemon_runtime.actor_session.input_actor_turn
    self.addCleanup(setattr, daemon_runtime.actor_session, "input_actor_turn", original)
    daemon_runtime.actor_session.input_actor_turn = lambda **kwargs: (
        calls.append(dict(kwargs))
        or {"action": "steer", "turn_id": "turn-demand-check"}
    )

    result = daemon_runtime.DaemonRuntime(context=context).input_actor("Demand check")

    self.assertEqual(result, {"action": "steer", "turn_id": "turn-demand-check"})
    self.assertEqual(
        calls,
        [{
            "socket_path": context.socket_path,
            "instance_json": context.instance_json,
            "thread_id": context.main_thread_id,
            "text": "Demand check",
            "permissions": context.permissions,
        }],
    )
```

Update `test_daemon_runtime_handler_facing_surface_is_exactly_clean_runtime_methods`
to expect `{"parent_activity", "input_actor"}`.

- [x] **Step 2: Run RED**

```bash
./buddyswitch-test focused \
  tests/unit/daemon/test_service_contract.py::DaemonServiceContractTests::test_daemon_runtime_input_actor_delegates_exact_context_to_actor_session \
  tests/unit/daemon/test_service_contract.py::DaemonServiceContractTests::test_daemon_runtime_handler_facing_surface_is_exactly_clean_runtime_methods
```

Expected: fail because `daemon_runtime` has no `actor_session` import or
`input_actor` method.

- [x] **Step 3: Implement the generic delegation**

Import `actor_session` beside `app_server`, then implement §5.2 exactly. Do not add
a prompt constant, Demand import, retry, Task branch, or result persistence.

- [x] **Step 4: Run GREEN**

```bash
./buddyswitch-test focused tests/unit/daemon/test_service_contract.py
```

Expected: all daemon service contract tests pass; public handler-facing surface is
exactly two methods.

## Task 4: Demand capture and attention adapter

**Files:**

- Create: `tools/launcher/demand_sys_daemon_adapter.py`
- Create: `tests/unit/demand_sys/test_daemon_adapter.py`

- [x] **Step 1: Write adapter RED tests**

Create `DemandSysDaemonAdapterTests(RuntimeWorkspaceTestCase)` with these exact
cases:

```text
test_capture_creates_one_pending_demand_and_requests_fixed_actor_input
test_same_intake_replay_after_input_failure_retries_attention_without_duplicate
test_checked_replay_does_not_request_actor_input
test_malformed_actor_input_result_leaves_canonical_demand_pending
```

Use this runtime fake:

```python
class _Runtime:
    def __init__(self, *, result=None, error=None):
        self.result = result or {"action": "start", "turn_id": "turn-demand-1"}
        self.error = error
        self.inputs: list[str] = []

    def input_actor(self, text: str) -> dict[str, Any]:
        self.inputs.append(text)
        if self.error is not None:
            raise self.error
        return dict(self.result)
```

The first case asserts the complete adapter receipt, one Demand record with
`intake_key="im.message.created:msg-adapter-1"`, `revision=1`,
`checked_revision=0`, exact source refs, the fixed prompt as the only runtime
input, and no Task files.

The failure/replay case performs one call with `RuntimeError("input unavailable")`,
asserts one durable pending Demand, then repeats the identical intake with a
working runtime and asserts the same `demand_id`,
`capture_state_changed=False`, and a successful actor-input receipt.

The checked replay case calls `demand_sys.complete_check` with the exact observed
revision before replay and asserts `pending_count=0`,
`attention_requested=False`, `actor_input=None`, and no runtime inputs.

- [x] **Step 2: Run RED**

```bash
./buddyswitch-test focused tests/unit/demand_sys/test_daemon_adapter.py
```

Expected: import/collection failure because the adapter module does not exist.

- [x] **Step 3: Implement the adapter**

Implement §5.3 in `tools/launcher/demand_sys_daemon_adapter.py`. The module may
import `daemon_contracts`, `env.domain.demand_sys`, and `env.repos.runtime_files`.
It must not import IM, Task Sys, Demand repository storage, daemon core/state, or
Actor Session directly.

- [x] **Step 4: Run GREEN with Demand owner regressions**

```bash
./buddyswitch-test focused \
  tests/unit/demand_sys/test_daemon_adapter.py \
  tests/unit/demand_sys/test_capture_and_check.py \
  tests/unit/demand_sys/test_organization.py
```

Expected: adapter and canonical Demand tests pass; failure tests leave one pending
Demand and no Task bytes.

## Task 5: Replace the IM handler with exact Demand capture

**Files:**

- Modify: `tools/launcher/im_wake_handler.py`
- Modify: `tests/unit/im/test_wake_handler.py`

- [x] **Step 1: Replace the old Task-expectation test with handler RED cases**

Remove `test_im_message_ingests_task_without_parent_or_side_prompt` and the
`task_sys_daemon_adapter` patching fixture. Add helpers that persist a real IM
message through `message_service.send_im_message`, derive its trigger from the
returned ids, and patch only
`im_wake_handler.demand_sys_daemon_adapter.capture_inbound` to record its call.

Add these exact cases:

```text
test_exact_target_visible_message_maps_to_one_demand_capture
test_wrong_target_actor_fails_before_capture
test_missing_message_or_event_fails_before_capture
test_mismatched_conversation_or_event_link_fails_before_capture
test_conversation_member_that_is_not_message_target_fails_before_capture
test_capture_error_returns_failed_and_keeps_task_projection_empty
test_handler_does_not_handle_unrelated_event
```

The success assertion is:

```python
self.assertEqual(result.status, "handled")
self.assertEqual(
    self.capture_calls,
    [{
        "context": context,
        "runtime": runtime,
        "intake_key": f"im.message.created:{message_id}",
        "description": "Support user data CSV export.",
        "detail": "Support user data CSV export.",
        "source_refs": [{
            "type": "im.message.created",
            "ref": {
                "message_id": message_id,
                "conversation_id": conversation_id,
                "event_id": event_id,
            },
        }],
    }],
)
self.assertEqual(self._task_records(), [])
```

For the explicit-recipient case, persist a conversation containing the local
actor, a message targeted to a different actor, and a target-visible event row;
the message service read succeeds through conversation visibility, but handler
recipient validation must fail.

- [x] **Step 2: Run RED**

```bash
./buddyswitch-test focused tests/unit/im/test_wake_handler.py
```

Expected: failures because the handler still imports Task adapters, does not read
IM facts, and does not expose Demand capture.

- [x] **Step 3: Implement exact validation and mapping**

Replace Task imports with:

```python
import demand_sys_daemon_adapter
from env.services import messages as message_service
from env.repos import runtime_files
```

Keep `_context_identity_route` and `_payload_id`. Add one helper that converts
service failures to `ValueError` using the service error message, and one helper
that compares exact identity payloads. Implement the validation matrix and mapping
from §5.4, then call `capture_inbound` once. Return only
`HandlerResult.handled()` or `HandlerResult.failed(message)`.

- [x] **Step 4: Run GREEN**

```bash
./buddyswitch-test focused \
  tests/unit/im/test_wake_handler.py \
  tests/unit/demand_sys/test_daemon_adapter.py
```

Expected: exact source validation, capture mapping, attention policy, failure
effects, and zero Task projection all pass.

## Task 6: Propagate daemon handler failure through IM delivery

**Files:**

- Modify: `scripts/env/tool_runtime/im_actor_delivery.py`
- Modify: `tests/unit/im/test_actor_delivery.py`

- [x] **Step 1: Add failure-status RED**

Add `test_daemon_failed_or_ignored_handling_is_not_reported_as_submitted`:

```python
for status in ("failed", "ignored", None):
    with self.subTest(status=status):
        response = {"ok": True, "result": {}}
        if status is not None:
            response["result"]["handling_status"] = status
        result = module.deliver(
            self._payload(),
            check_reachability_fn=online_reachability,
            request_mailbox_fn=lambda *_args, response=response, **_kwargs: response,
        )
        self.assertEqual(result["actor_handling_status"], "handling_failed")
        self.assertEqual(result["handling_status"], status)
        self.assertIn("did not handle", result["error"])
```

Use the same online endpoint shape as
`test_online_actor_delivery_builds_current_local_trigger`.

- [x] **Step 2: Run RED**

```bash
./buddyswitch-test focused \
  tests/unit/im/test_actor_delivery.py::ImActorDeliveryTests::test_daemon_failed_or_ignored_handling_is_not_reported_as_submitted
```

Expected: current implementation incorrectly reports `submitted`.

- [x] **Step 3: Implement exact mapping**

Replace the unconditional final `submitted` return with §5.5. Do not alter offline
reachability, endpoint validation, mailbox transport errors, or the durable IM
write contract.

- [x] **Step 4: Run GREEN**

```bash
./buddyswitch-test focused tests/unit/im/test_actor_delivery.py
```

Expected: handled delivery remains submitted; failed, ignored, and missing handler
status are observable failures.

## Task 7: Forward-only retirement of IM from Task Sys

**Files:**

- Modify: `tools/launcher/task_sys_ingress.py`
- Modify: `scripts/env/domain/task_sys.py`
- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `tests/integration/task_sys/test_substrate.py`
- Modify: `tests/unit/task_sys/test_direct_input_retirement.py`
- Modify: `tests/unit/task_sys/test_runtime_executor.py`

- [x] **Step 1: Add replacement RED assertions**

Add `test_ingest_rejects_im_message_without_persisting_task` beside the existing
direct-input rejection in `test_substrate.py`:

```python
before = self._task_records()
with self.assertRaisesRegex(ValueError, "im.message.created"):
    task_sys.ingest({
        "source": {
            "type": "im.message.created",
            "ref": {
                "message_id": "msg-retired-1",
                "conversation_id": "conv-retired-1",
                "event_id": "imev-retired-1",
            },
        },
        "actor_target": self._envelope()["actor_target"],
        "context": {"message_id": "msg-retired-1"},
    })
self.assertEqual(self._task_records(), before)
```

Change `test_task_sys_ingress_exposes_only_controlled_inbound_helpers` to assert:

```python
self.assertNotIn("def ingest_im_message(", source)
self.assertIn("def ingest_track_comment(", source)
self.assertNotIn('"im.message.created"', source)
```

Add a runtime source guard:

```python
runtime_source = _source("tools/launcher/task_sys_runtime.py")
self.assertNotIn('_render_im_message_task_guidance', runtime_source)
self.assertNotIn('source_type == "im.message.created"', runtime_source)
self.assertNotIn('For an IM source message:', runtime_source)
```

- [x] **Step 2: Run RED**

```bash
./buddyswitch-test focused \
  tests/integration/task_sys/test_substrate.py::TaskSysSubstrateTests::test_ingest_rejects_im_message_without_persisting_task \
  tests/unit/task_sys/test_direct_input_retirement.py
```

Expected: Task domain still accepts IM and Task ingress/runtime still contain the
retired route.

- [x] **Step 3: Delete the retired implementation**

In `task_sys_ingress.py`, delete `ingest_im_message` completely and leave
`_ensure_state_root_env`, validation helpers, `_result_payload`, and
`ingest_track_comment` only.

In `task_sys.py`, extend the exact negative source tuple:

```python
non_task_sys_sources = (
    "{}_{}.{}".format("app", "server", "turn_completed"),
    "{}.{}".format("user", "input"),
    "{}.{}.{}".format("im", "message", "created"),
)
```

Preserve the current string construction style and reject before `_new_task_id` or
any persistence.

In `task_sys_runtime.py`, delete `_im_message_tool_capability_lines`,
`_render_im_message_task_guidance`, both IM `source_type` branches, and the now
unused local `source_type` values. Side and parent frames always use their current
generic source guidance.

- [x] **Step 4: Delete tests that teach retired behavior**

Delete `_im_instruction` and these tests from `test_runtime_executor.py`:

```text
test_render_side_frame_for_im_source_allows_full_message_tool_surface
test_im_message_frames_share_the_same_message_capability_contract
test_render_parent_frame_for_im_source_allows_full_message_tool_surface
```

Do not replace them with compatibility expectations. Generic Task-frame tests and
Track tests remain.

- [x] **Step 5: Run GREEN plus current Track regression**

```bash
./buddyswitch-test focused \
  tests/integration/task_sys/test_substrate.py \
  tests/unit/task_sys/test_direct_input_retirement.py \
  tests/unit/task_sys/test_runtime_executor.py \
  tests/integration/track/test_comment_added_handler.py
```

Expected: Task rejects IM and direct input byte-identically, Task runtime has no
IM-specific prompt, and Track still creates/executes its current Task path.

## Task 8: Mailbox-to-Demand integration replacement

**Files:**

- Modify: `tests/integration/im/test_external_reply_loop.py`

- [x] **Step 1: Replace the integration dispatcher**

Change `_Runtime` to own actor inputs:

```python
class _Runtime:
    def __init__(self) -> None:
        self.inputs: list[str] = []

    def input_actor(self, text: str) -> dict[str, str]:
        self.inputs.append(text)
        return {"action": "start", "turn_id": f"turn-demand-{len(self.inputs)}"}
```

Delete `_WakeHandlerDispatcher.task_sys_instructions`, `_execute_instruction`, and
Task adapter monkeypatching. Call the handler directly and retain trigger/result
recording.

- [x] **Step 2: Replace socket bridge expectations**

Before calling `im_actor_delivery.deliver`, persist a real external-to-actor IM
message and use its returned message, conversation, and event ids. Then assert:

```python
demands = demand_sys.list_demands(
    {"actor_id": target_identity_id, "role_id": target_role_id},
    state="all",
)
self.assertEqual(len(demands), 1)
self.assertEqual(demands[0]["intake_key"], f"im.message.created:{message_id}")
self.assertEqual(demands[0]["description"], "socket demand probe")
self.assertEqual(demands[0]["checked_revision"], 0)
self.assertEqual(len(dispatcher.runtime.inputs), 1)
self.assertIn("[DEMAND CHECK]", dispatcher.runtime.inputs[0])
self.assertEqual(self._task_records(), [])
```

Apply the same final assertions to the actor-to-actor send test, replacing all
Task instruction/frame assertions.

- [x] **Step 3: Run the resource-owning integration target separately**

```bash
./buddyswitch-test focused tests/integration/im/test_external_reply_loop.py
```

Expected: real mailbox socket/local trigger produces one pending Demand and one
generic actor input per tested message, no Task; mailbox thread/socket and runner
root are removed.

## Task 9: Architecture laws, residue removal, and current docs

**Files:**

- Modify: `tests/unit/architecture/test_demand_sys_boundaries.py`
- Modify: `docs/arch/demand-sys-architecture.md`
- Modify: `docs/arch/daemon-service-architecture.md`
- Modify: `docs/memo/2026-07-19-demand-sys-phase-2-im-proactive-vertical-slice-design.md`

- [x] **Step 1: Replace the Phase 1 absence law with exact Phase 2 dependency laws**

Replace `test_phase_one_has_no_daemon_im_track_or_task_sys_product_integration`
with assertions equivalent to:

```python
for relative in GENERIC_DAEMON_PATHS:
    assert not [name for name in _imports(relative) if "demand" in name], relative

handler_imports = _imports(Path("tools/launcher/im_wake_handler.py"))
adapter_imports = _imports(Path("tools/launcher/demand_sys_daemon_adapter.py"))
track_source = (REPO_ROOT / "tools/launcher/track_comment_added_handler.py").read_text()
task_ingress = (REPO_ROOT / "tools/launcher/task_sys_ingress.py").read_text()
task_runtime = (REPO_ROOT / "tools/launcher/task_sys_runtime.py").read_text()

assert "demand_sys_daemon_adapter" in handler_imports
assert "env.services.messages" in handler_imports
assert not any("task_sys" in name for name in handler_imports)
assert "env.domain.demand_sys" in adapter_imports
assert not any("env.repos.demands" in name for name in adapter_imports)
assert "demand_sys" not in track_source
assert "ingest_im_message" not in task_ingress
assert 'source_type == "im.message.created"' not in task_runtime
```

Add source scans proving `actor_session.py` has no Demand call and generic daemon
contracts/core/state/mailbox/client contain no Demand product token. The only
generic runtime allowance is the method name `input_actor`.

- [x] **Step 2: Run architecture RED/GREEN at the current source state**

Run before final doc edits; if assertions fail, repair the owning code rather than
weakening them:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/daemon/test_decoupling.py
```

Expected: pass only when the adapter is the sole Demand/daemon bridge, IM handler
has no Task dependency, and generic daemon remains product-neutral.

- [x] **Step 3: Update current architecture truth**

In `demand-sys-architecture.md`, replace the Phase 1 text with:

```text
IM message fact -> IM handler -> Demand daemon adapter -> Demand domain
                                      |
                                      -> generic input_actor -> actor Demand Check
```

Document that the adapter owns attention policy but not lifecycle/storage, actor
owns organization judgment, Task Sys has no IM/Demand dependency, Track remains
outside Demand for this phase, and offline capture is not implemented.

In `daemon-service-architecture.md`, add `input_actor(text)` under host runtime
facts and state that prompt/check policy remains product-owned. Do not add Demand
to the generic daemon responsibility list.

Mark the approved design memo `implemented` only after all executable proof and
the real actor milestone pass. Change the observability row to say the public IM
response exposes `actor_handling_status` derived from daemon handling, while raw
daemon handling remains in daemon-owned logs/state.

- [x] **Step 4: Run exact residue scans**

```bash
rg -n "def ingest_im_message|_render_im_message_task_guidance|source_type == \"im.message.created\"|For an IM source message:" \
  tools/launcher scripts/env tests/unit/task_sys

rg -n "demand_sys|demand-sys" \
  tools/launcher/daemon_contracts.py \
  tools/launcher/daemon_state.py \
  tools/launcher/daemon_core.py \
  tools/launcher/daemon_mailbox.py \
  scripts/env/tool_runtime/daemon_client.py

git diff --check
```

Expected: first scan returns only scoped negative assertions, second scan returns
no output, and diff check is clean.

## Task 10: Focused IMPACT verification and review

**Files:** update the progress/evidence sections of this memo only after commands
finish; do not change executable source while recording valid evidence.

- [x] **Step 1: Discover targets from the final diff**

```bash
git status --short
git diff --name-status
rg -n "get_im_event|input_actor|capture_inbound|ingest_im_message|im.message.created" \
  tests tools/launcher scripts/env
```

Confirm the exact changed tests remain the nearest owner/consumer proofs. Add no
directory merely because its name looks related.

- [x] **Step 2: Run compatible focused IMPACT batch**

```bash
./buddyswitch-test focused \
  tests/integration/im/test_product_core.py \
  tests/unit/daemon/test_service_contract.py \
  tests/unit/demand_sys/test_daemon_adapter.py \
  tests/unit/demand_sys/test_capture_and_check.py \
  tests/unit/demand_sys/test_organization.py \
  tests/unit/im/test_wake_handler.py \
  tests/unit/im/test_actor_delivery.py \
  tests/integration/task_sys/test_substrate.py \
  tests/unit/task_sys/test_direct_input_retirement.py \
  tests/unit/task_sys/test_runtime_executor.py \
  tests/integration/track/test_comment_added_handler.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/daemon/test_decoupling.py \
  tests/unit/daemon/test_communication_boundary.py \
  tests/unit/daemon/test_instance_entrypoint.py \
  tests/unit/actor/test_session.py
```

Expected: all direct owner, contract, replacement, Track preservation, and direct
input non-impact tests pass with no runner residue.

- [x] **Step 3: Reuse the separate resource integration evidence**

Do not rerun `tests/integration/im/test_external_reply_loop.py` if its Task 8
evidence identity is still valid. If executable/test state affecting it changed,
rerun only that focused target and replace the stale evidence.

- [x] **Step 4: Review the complete diff against all proof classes**

```text
Product: external IM can reach Demand attention and actor check
Contract: exact source, replay, failure, and acknowledgement effects are explicit
Architecture: one Demand owner; generic daemon and Task Sys remain decoupled
Replacement: no live/test/doc IM-to-Task path remains
Operations: mailbox, actor, web, daemon, socket, and roots clean up
```

Inspect every changed file for guessed payload shapes, copied lifecycle rules,
new registries, hidden retries, fallbacks, aliases, and source-specific logic in
generic daemon. Repair findings at the owner and rerun only invalidated focused
proof.

- [x] **Step 5: Record IMPACT evidence**

Record exact source identity, command, run id, environment, result, cleanup,
claims, and residual risk in this memo. Do not run `./buddyswitch-test full`;
Phase 2 is not an explicit repository-wide FINAL request.

## Task 11: Fresh real actor and real IM MILESTONE

**Files:** no source changes during the accepted run

Use a fresh isolated root, installed Codex, public actor CLI, public web command,
and external IM HTTP API. Do not use `instance input` and do not pre-create Demand
records.

- [x] **Step 1: Run the isolated acceptance harness**

Save the following as a one-shot shell here-document invocation; do not add a
repository script:

```bash
exec bash <<'BASH'
set -euo pipefail
source tools/launcher/env.sh
buddyswitch_env_init
"$BUDDYSWITCH_PYTHON" - <<'PY'
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from urllib import request

repo = Path.cwd()
launcher = repo / "buddyswitch-codex"
run_root = Path(tempfile.mkdtemp(prefix="bs-demand-phase2-", dir="/private/tmp"))
shared_root = run_root / ".codex-buddyswitch"
env = os.environ.copy()
env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
actor_id = ""
web = None
web_stdout = (run_root / "web.stdout").open("w+", encoding="utf-8")
web_stderr = (run_root / "web.stderr").open("w+", encoding="utf-8")
recorded_pids = []
recorded_sockets = []
cleanup_errors = []
no_proxy_opener = request.build_opener(request.ProxyHandler({}))

def cli(*args):
    completed = subprocess.run(
        [str(launcher), *args], cwd=repo, env=env,
        check=False, capture_output=True, text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"CLI failed {args}: {completed.stdout}\n{completed.stderr}")
    return json.loads(completed.stdout)

def http_json(method, url, payload=None, token=None):
    body = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url, data=body, headers=headers, method=method)
    with no_proxy_opener.open(req, timeout=30) as response:
        return json.loads(response.read())

def pid_live(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True

def demand_rows():
    return cli("demand", "list", "--actor", actor_id)["data"]["demands"]

def wait_for(predicate, label, timeout=240):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = demand_rows()
        if predicate(last):
            return last
        time.sleep(2)
    raise RuntimeError(f"timeout waiting for {label}: {json.dumps(last)}")

try:
    started = cli("instance", "start", "--role", "pm")
    actor_id = started["data"]["actor_id"]
    status = cli("instance", "status", actor_id)["data"]
    for section in ("app_server", "daemon", "runtime_broker"):
        row = status.get(section) or {}
        if isinstance(row.get("pid"), int):
            recorded_pids.append(row["pid"])
        for key in ("socket_path",):
            value = row.get(key)
            if isinstance(value, str) and value:
                recorded_sockets.append(Path(value))

    port_probe = subprocess.run(
        [env["BUDDYSWITCH_PYTHON"], "-c",
         "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()"],
        check=True, capture_output=True, text=True,
    )
    port = int(port_probe.stdout.strip())
    base = f"http://127.0.0.1:{port}"
    web = subprocess.Popen(
        [str(launcher), "web", "--host", "127.0.0.1", "--port", str(port)],
        cwd=repo, env=env, stdout=web_stdout, stderr=web_stderr,
        text=True, start_new_session=True,
    )
    recorded_pids.append(web.pid)
    deadline = time.monotonic() + 30
    while True:
        try:
            http_json("GET", f"{base}/api/health")
            break
        except Exception:
            if time.monotonic() >= deadline or web.poll() is not None:
                raise RuntimeError("web service did not become ready")
            time.sleep(0.25)
    central_pid_file = shared_root / "run" / "central-daemon" / "central-daemon.pid"
    if central_pid_file.is_file():
        recorded_pids.append(int(central_pid_file.read_text(encoding="utf-8").strip()))
    recorded_sockets.append(shared_root / "run" / "central-daemon" / "central-daemon.sock")
    recorded_sockets.append(Path(status["daemon"]["runtime_dir"]) / "mailbox.sock")

    session = http_json(
        "POST", f"{base}/api/im/external-sessions",
        {"display_name": "Demand Phase 2 acceptance"},
    )
    token = session["external_session_key"]

    def send(content):
        result = http_json(
            "POST", f"{base}/api/im/messages",
            {"target_identity_id": actor_id, "content": content}, token,
        )
        if result.get("actor_handling_status") != "submitted":
            raise RuntimeError(f"IM handling failed: {result}")
        return result

    c_send = send("Support user data CSV export.")
    c_key = f"im.message.created:{c_send['message']['id']}"
    wait_for(
        lambda rows: any(
            row["intake_key"] == c_key
            and row["terminal"] is None
            and row["checked_revision"] == row["revision"]
            for row in rows
        ),
        "C acknowledgement",
    )

    u_send = send("Fix payment request timeout.")
    u_key = f"im.message.created:{u_send['message']['id']}"
    wait_for(
        lambda rows: any(
            row["intake_key"] == u_key
            and row["description"] == "Fix payment request timeout."
            and row["terminal"] is None
            and row["parent_id"] is None
            and row["depends_on"] == []
            and row["checked_revision"] == row["revision"]
            for row in rows
        ),
        "U independent acknowledgement",
    )

    d_send = send("CSV export must also include the user timezone.")
    d_key = f"im.message.created:{d_send['message']['id']}"

    def final_state(rows):
        by_key = {row["intake_key"]: row for row in rows}
        c = by_key.get(c_key)
        u = by_key.get(u_key)
        d = by_key.get(d_key)
        return bool(
            len(rows) == 3 and c and u and d
            and c["terminal"] is None
            and "timezone" in c["description"].lower()
            and c["checked_revision"] == c["revision"]
            and u["description"] == "Fix payment request timeout."
            and u["terminal"] is None
            and u["parent_id"] is None
            and u["depends_on"] == []
            and u["checked_revision"] == u["revision"]
            and isinstance(d["terminal"], dict)
            and d["terminal"]["type"] == "absorbed"
            and d["terminal"]["ref"] == c["demand_id"]
            and d["checked_revision"] == d["revision"]
        )

    final_demands = wait_for(final_state, "C/U/D organization")
    os.environ["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)
    os.environ["BUDDYSWITCH_STATE_ROOT"] = str(shared_root / "state")
    sys.path.insert(0, str(repo / "scripts"))
    from env.domain import demand_sys as demand_owner
    from env.repos import runtime_files as owner_runtime_files
    owner_runtime_files.refresh_runtime_roots_from_env()
    canonical_demands = demand_owner.list_demands(
        {"actor_id": actor_id, "role_id": "pm"},
        state="all",
    )
    canonical_by_key = {row["intake_key"]: row for row in canonical_demands}
    canonical_c = canonical_by_key[c_key]

    def source_ref_signature(row):
        ref = row["ref"]
        return (
            row["type"],
            ref["message_id"],
            ref["conversation_id"],
            ref["event_id"],
        )

    expected_c_refs = {
        (
            "im.message.created",
            c_send["message"]["id"],
            c_send["message"]["conversation_id"],
            c_send["event_id"],
        ),
        (
            "im.message.created",
            d_send["message"]["id"],
            d_send["message"]["conversation_id"],
            d_send["event_id"],
        ),
    }
    actual_c_refs = {source_ref_signature(row) for row in canonical_c["source_refs"]}
    if actual_c_refs != expected_c_refs or "timezone" not in canonical_c["detail"].lower():
        raise RuntimeError({
            "expected_c_refs": sorted(expected_c_refs),
            "actual_c_refs": sorted(actual_c_refs),
            "canonical_c": canonical_c,
        })
    tasks = cli("task", "list", "--actor", actor_id)["data"]["tasks"]
    if tasks != []:
        raise RuntimeError(f"Task Sys was touched: {tasks}")
    thread_read = subprocess.run(
        [
            env["BUDDYSWITCH_PYTHON"],
            str(repo / "tools" / "launcher" / "app_server.py"),
            "thread-read",
            "--socket", status["app_server"]["socket_path"],
            "--thread-id", status["thread_id"],
            "--include-turns",
        ],
        cwd=repo, env=env, check=True, capture_output=True, text=True,
    )
    thread_record = json.loads(thread_read.stdout)
    turns = thread_record.get("thread", {}).get("turns", [])
    turn_ids = [row.get("id") for row in turns if isinstance(row, dict) and row.get("id")]
    if not turn_ids:
        raise RuntimeError(f"no actor turn ids were observable: {thread_record}")
    daemon_log = Path(status["daemon"]["log_path"])
    daemon_events = []
    if daemon_log.is_file():
        for line in daemon_log.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                event.get("event") in {"notification_received", "handler_result"}
                and event.get("trigger_type") == "im.message.created"
            ):
                daemon_events.append(event)
    print(json.dumps({
        "actor_id": actor_id,
        "thread_id": status["thread_id"],
        "turn_ids": turn_ids,
        "codex_runtime": status["codex_runtime"],
        "messages": [c_send, u_send, d_send],
        "demands": final_demands,
        "canonical_demands": canonical_demands,
        "tasks": tasks,
        "daemon_events": daemon_events,
    }, ensure_ascii=False, indent=2))
finally:
    if actor_id:
        for args in (
            ("instance", "stop", actor_id),
            ("instance", "delete", actor_id, "--yes"),
        ):
            completed = subprocess.run(
                [str(launcher), *args], cwd=repo, env=env,
                check=False, capture_output=True, text=True,
            )
            if completed.returncode != 0:
                cleanup_errors.append({
                    "command": args,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                })
    if web is not None and web.poll() is None:
        os.killpg(web.pid, signal.SIGINT)
        try:
            web.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(web.pid, signal.SIGTERM)
            web.wait(timeout=10)
    reset = subprocess.run(
        [str(launcher), "env", "reset", "--yes"], cwd=repo, env=env,
        check=False, capture_output=True, text=True,
    )
    if reset.returncode != 0:
        cleanup_errors.append({
            "command": ("env", "reset", "--yes"),
            "stdout": reset.stdout,
            "stderr": reset.stderr,
        })
    web_stdout.close()
    web_stderr.close()
    leaked_pids = [pid for pid in recorded_pids if pid_live(pid)]
    leaked_sockets = [str(path) for path in recorded_sockets if path.exists()]
    if run_root.exists():
        shutil.rmtree(run_root)
    if cleanup_errors or leaked_pids or leaked_sockets or run_root.exists():
        raise RuntimeError({
            "cleanup_errors": cleanup_errors,
            "leaked_pids": leaked_pids,
            "leaked_sockets": leaked_sockets,
            "run_root_exists": run_root.exists(),
        })
PY
BASH
```

Expected: exactly three Demand rows; C is live and contains timezone content, U
is an independent root, D is absorbed into C, all final revisions are checked,
Task list is empty, and all recorded processes/sockets/isolated roots are absent.

- [x] **Step 2: Inspect owner logs without treating them as canonical state**

Before cleanup removes the isolated root, preserve the relevant daemon log lines
in the evidence block: trigger type, origin message id, handler result, and any
failure. Do not copy message bodies or complete Demand records into daemon logs.

- [x] **Step 3: Handle nondeterministic failure correctly**

If the actor chooses a wrong Demand action or leaves revisions pending, preserve
the failed run as evidence. Inspect the Demand tool schema, fixed prompt, actor
turn, and daemon logs; fix only the owning contract, rerun invalidated focused
tests, and create a fresh actor/root for the next attempt. Do not steer the actor
with an acceptance-specific corrective prompt and count that as proactive success.

- [x] **Step 4: Record MILESTONE evidence**

Record installed Codex version, source identity, actor/thread/turn ids, three
message/event ids, three Demand ids and public final projections, Task projection,
daemon handler evidence, any retry, exact pids/sockets, and cleanup result.

## Task 12: Final scope audit and single implementation commit

- [x] **Step 1: Audit the final worktree**

```bash
git status --short
git diff --stat
git diff --check
git diff --name-status
```

Expected: every tracked change belongs to this plan; `.superpowers/` is still
untracked and untouched; no generated runtime object, isolated root, log, socket,
pid file, or test artifact is staged.

- [x] **Step 2: Prove the replacement is singular**

```bash
rg -n "def ingest_im_message|task_sys_ingress\.ingest_im_message|_render_im_message_task_guidance|source_type == \"im.message.created\"" \
  tools/launcher scripts/env tests README.md docs/arch

rg -n "demand_sys|demand-sys" \
  tools/launcher/daemon_contracts.py \
  tools/launcher/daemon_state.py \
  tools/launcher/daemon_core.py \
  tools/launcher/daemon_mailbox.py \
  scripts/env/tool_runtime/daemon_client.py
```

Expected: only scoped negative guards may name retired Task symbols; generic
daemon files contain no Demand product token.

- [x] **Step 3: Reconcile plan/design/docs with actual implementation**

Update task checkboxes and evidence in this memo. Mark the design and architecture
docs implemented only for behavior actually proved. Keep Track cutover, offline
capture, startup recovery, and Demand/Task coordination explicitly unimplemented.

- [x] **Step 4: Create one Phase 2 commit**

```bash
git add \
  scripts/env/repos/messages.py \
  scripts/env/services/messages.py \
  scripts/env/tool_runtime/im_actor_delivery.py \
  scripts/env/domain/task_sys.py \
  tools/launcher/daemon_runtime.py \
  tools/launcher/demand_sys_daemon_adapter.py \
  tools/launcher/im_wake_handler.py \
  tools/launcher/task_sys_ingress.py \
  tools/launcher/task_sys_runtime.py \
  tests/integration/im/test_product_core.py \
  tests/integration/im/test_external_reply_loop.py \
  tests/integration/task_sys/test_substrate.py \
  tests/unit/daemon/test_service_contract.py \
  tests/unit/demand_sys/test_daemon_adapter.py \
  tests/unit/im/test_wake_handler.py \
  tests/unit/im/test_actor_delivery.py \
  tests/unit/task_sys/test_direct_input_retirement.py \
  tests/unit/task_sys/test_runtime_executor.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  docs/arch/demand-sys-architecture.md \
  docs/arch/daemon-service-architecture.md \
  docs/memo/2026-07-19-demand-sys-phase-2-im-proactive-vertical-slice-design.md \
  docs/memo/2026-07-20-demand-sys-phase-2-im-proactive-vertical-slice-implementation-plan.md
git diff --cached --check
git commit -m "feat(demand-sys): cut IM intake over to proactive demands"
```

Expected: one implementation commit containing the plan, implementation,
replacement, tests, current architecture docs, and acceptance evidence. Do not
stage `.superpowers/`.

## 6. Evidence ledger

Append evidence here during execution. Never overwrite a newer failure with an
older pass and never claim broader coverage than the command proves.

### Baseline

Verification Evidence
- state: GREEN
- source: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`, HEAD
  `0f49d1a30d22ce74ee5f140fbaf5ce1ca55ad22d`, no tracked patch; untracked
  `.superpowers/` (unrelated), design memo, and this implementation plan
- command: `./buddyswitch-test focused tests/unit/daemon/test_service_contract.py tests/unit/task_sys/test_runtime_executor.py tests/integration/track/test_comment_added_handler.py`
- environment: run id `3a805d6ad96549909fd23a5c352bbf3a`,
  `/Users/chen/miniconda3/bin/python`, isolated runner root under `/private/tmp`
- result: exit 0; 52 tests and 24 subtests passed in 0.31s; runner root removed
- proves: current generic daemon service contract, generic Task runtime frames,
  and current Track-to-Task route are green before Phase 2 replacement
- valid-for: pre-implementation dirty worktree identity above
- residual-risk: IM-to-Demand replacement behavior has not yet been built

### RED/GREEN

Verification Evidence
- state: RED/GREEN
- source: repository HEAD `0f49d1a30d22ce74ee5f140fbaf5ce1ca55ad22d` with the
  cumulative task-related dirty patch at each named TDD boundary; `.superpowers/`
  remained unrelated and untouched
- commands and results:
  - exact IM event read: RED run `9e85c7c1bf954e77b8edc107911cfadc`
    failed because `get_im_event` was absent; GREEN run
    `d3904fcc79774f40aef31776d5c9c6a9` passed 1 test
  - generic daemon input: RED run `00af9e77e5e14a2592eb75258cd2bd46`
    failed on the missing import/method and surface; GREEN run
    `c01fb510f22243278fa36bfd1c500748` passed 13 tests
  - Demand adapter: RED run `90e0f1921a0143ada3d478256e39deac`
    failed because the adapter was absent; GREEN run
    `7d76866cfaf34a5d80d195473dc9eb1d` passed 32 tests and 7 subtests
  - exact IM handler: RED run `7f42594d208e4a94b186f00e49cfdd26`
    exposed the live Task path and missing source validation; GREEN run
    `fd621516ac5a499eb1611bbdf82accd3` passed 11 tests and 7 subtests
  - delivery failure projection: RED run `b899cffc66d24241a7b5e446b8dce2d3`
    showed failed/ignored/missing status as submitted; GREEN run
    `223c4c3cb55b4132b4adfafe44bd8d2b` passed 5 tests and 3 subtests
  - Task replacement: RED run `16aca7f4943946e0b323e97bf9902290`
    showed Task still accepted IM and retained ingress/prompt residue; GREEN run
    `3555c9025a144ca7be2d90bc33b811bd` passed 64 tests and 99 subtests
  - mailbox integration: GREEN run `7171ce30cf1649afbc283187bbd17ac0`
    passed 7 resource-owning tests
  - architecture boundary: GREEN run `4b620d038f624ee39f46894daac3e034`
    passed 21 tests and 10 subtests
- environment: canonical focused runner, `/Users/chen/miniconda3/bin/python`,
  isolated `/private/tmp/bs-test-*` roots
- result: every GREEN exited 0 and every recorded runner root was removed
- proves: direct owner behavior, replay/recovery, exact IM validation, generic
  input delegation, delivery failure semantics, Task retirement, Track
  preservation, mailbox cleanup, and dependency laws
- valid-for: superseded by the later cumulative IMPACT evidence
- residual-risk: real nondeterministic actor organization was still unproved at
  these boundaries

### IMPACT

Verification Evidence
- state: IMPACT
- source: HEAD `0f49d1a30d22ce74ee5f140fbaf5ce1ca55ad22d` plus the
  complete executable/test Phase 2 patch and the two task memos; `.superpowers/`
  unrelated
- command: `./buddyswitch-test focused tests/integration/im/test_product_core.py tests/unit/daemon/test_service_contract.py tests/unit/demand_sys/test_daemon_adapter.py tests/unit/demand_sys/test_capture_and_check.py tests/unit/demand_sys/test_organization.py tests/unit/im/test_wake_handler.py tests/unit/im/test_actor_delivery.py tests/integration/task_sys/test_substrate.py tests/unit/task_sys/test_direct_input_retirement.py tests/unit/task_sys/test_runtime_executor.py tests/integration/track/test_comment_added_handler.py tests/unit/architecture/test_demand_sys_boundaries.py tests/unit/daemon/test_decoupling.py tests/unit/daemon/test_communication_boundary.py tests/unit/daemon/test_instance_entrypoint.py tests/unit/actor/test_session.py`
- environment: final fresh run id `c20c948c69234f9d93c58d819b7eb3cc`,
  `/Users/chen/miniconda3/bin/python`, isolated runner root
- result: exit 0; 197 tests and 155 subtests passed in 1.22s; runner root
  `/private/tmp/bs-test-c20c948c-tp984r66` removed
- proves: cumulative owner, contract, architecture, replacement, Track
  preservation, direct-input non-impact, instance registration, and Actor Session
  behavior
- valid-for: current executable/test candidate; later changes before commit were
  confined to docs/evidence and did not alter executable identity
- residual-risk: repository-wide full was not requested or run; real actor proof
  is recorded separately

Verification Evidence
- state: IMPACT
- source: same executable candidate before architecture-doc-only changes
- command: `./buddyswitch-test focused tests/integration/im/test_external_reply_loop.py`
- environment: run id `7171ce30cf1649afbc283187bbd17ac0`
- result: exit 0; 7 tests passed in 0.29s; mailbox server/thread/socket and runner
  root were removed
- proves: durable IM plus real mailbox/local-trigger reaches one pending Demand
  and one generic actor input with zero Task records
- valid-for: current executable/test candidate
- residual-risk: none at this resource boundary

### Real actor MILESTONE

Verification Evidence
- state: MILESTONE
- source: current Phase 2 executable candidate at HEAD
  `0f49d1a30d22ce74ee5f140fbaf5ce1ca55ad22d`; only memo evidence changed after
  the accepted run
- command: the one-shot isolated harness in Task 11, using public
  `buddyswitch-codex instance start --role pm`, public web/IM HTTP, public Demand
  and Task CLI, installed Codex, and a read-only Demand owner check for hidden
  source refs
- environment: `codex-cli 0.144.4`; actor `act-pm-d52ba0865942`; thread
  `019f7b47-b72a-72d2-9d0d-64a1014c39e9`; actor turn
  `019f7b47-c646-7293-8e96-00d159f6a25f`
- result: exit 0; C message/event `msg-08f881c17c34` /
  `imev-0a1305cde346`, U `msg-3ff9c6ab57b2` /
  `imev-9852c804f1d6`, D `msg-e2948a74eda9` /
  `imev-16ec89134dce`; C `demand-25e6e262d0ab` is live at revision 2
  with timezone in description/detail and exact C+D source refs; U
  `demand-949eea02434b` is an independent live root at revision 1; D
  `demand-8b55069246a2` is absorbed into C at revision 2; every
  `checked_revision == revision`; public Task projection is `[]`; all three daemon
  handler log entries are `handled`
- cleanup: the harness stopped/deleted the actor, stopped web/central daemon,
  ran isolated `env reset`, checked every recorded pid/socket, removed the
  isolated root, and exited 0; no `bs-demand-phase2-*` root remained
- retry history: the first attempt failed before product behavior because local
  health traffic followed the shell HTTP proxy and received 502; cleanup was
  clean. The harness was corrected to use the repository-standard no-proxy
  opener. A second product-success run proved public state; the final fresh run
  added and passed canonical C source-ref/detail proof. No actor was manually
  steered or given an acceptance-specific corrective prompt.
- proves: the complete real consumer loop and frozen C/U/D acceptance sentence
- valid-for: current executable/test candidate
- residual-risk: active actor only; offline capture/replay, Track cutover, and
  Demand/Task coordination remain explicitly later phases

## 7. Definition of done

Phase 2 is complete only when:

1. one real external IM message deterministically creates one actor-owned Demand;
2. durable pending state, not a transient create receipt, controls actor input;
3. replay after input failure retries attention without duplicate Demand;
4. checked replay does not wake;
5. actor organization leaves U independent and atomically absorbs D into C;
6. every final Demand revision is acknowledged;
7. Task Sys rejects IM and contains no IM ingress/prompt path;
8. generic daemon owns only actor-input mechanics and remains Demand-neutral;
9. Demand domain/repository remain the only lifecycle/write owners;
10. Track remains green on its explicitly current Task route;
11. direct actor input remains outside Demand and Task ingress;
12. focused owner/contract/architecture/replacement proof passes;
13. real actor, real IM HTTP, daemon logs, public projections, and cleanup prove the
    complete consumer loop;
14. no process, socket, lock, isolated root, runtime object, or unrelated file is
    left behind;
15. one final commit contains the plan and complete implementation, with no
    fragmented plan-only commit and no `.superpowers/` staging.
