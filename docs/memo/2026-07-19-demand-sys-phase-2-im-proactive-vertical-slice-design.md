# Demand Sys Phase 2 IM Proactive Vertical Slice Design

**Date:** 2026-07-19

**Status:** implemented and accepted on 2026-07-20

**Baseline:** `fea-daemon` at `0f49d1a30d22ce74ee5f140fbaf5ce1ca55ad22d`

**Scope:** one active-actor `im.message.created` source cutover only

## 1. Goal and acceptance sentence

Phase 2 proves the first real proactive Demand path, not another isolated
infrastructure layer:

```text
durable IM message
  -> exactly one actor-owned Demand
      -> Demand-owned attention decision
          -> generic actor input start/steer
              -> actor two-pass Demand check and organization
                  -> durable acknowledged Demand result
```

The acceptance sentence is:

> A fresh active BuddySwitch actor receives three real IM messages representing
> an initial need C, an unrelated need U, and a supplement D to C; each message
> creates exactly one actor-owned Demand, generic daemon delivery gives the actor
> a Demand Check turn, the actor leaves U independent and atomically absorbs D
> into C, all observed revisions are acknowledged, public projections and owner
> logs preserve the causal evidence, and Task Sys remains unused and contains no
> IM ingress path.

Phase 2 is successful only when this sentence is observable end to end. Merely
registering a handler, emitting a prompt, or creating a Demand is insufficient.

## 2. Why this is the current bottleneck

Phase 1 completed the standalone Demand owner, atomic actor aggregate, actor
actions, two-pass check contract, organization actions, terminal lineage, and
read-only public CLI. It deliberately did not connect inbound, daemon wake, or
Task Sys.

The live IM path still bypasses Demand completely:

```text
im.message.created
  -> tools/launcher/im_wake_handler.py
      -> task_sys_ingress.ingest_im_message
          -> Task Sys ingest
              -> start_side runtime instruction
```

This means a real inbound need is still immediately treated as execution. Until
one source is replaced, the proactive Demand architecture has not been proved.

## 3. Repository facts

The design is grounded in current code rather than the earlier prototype alone:

- `scripts/env/domain/demand_sys.py` is the sole Demand lifecycle, revision,
  organization, check, and terminal owner.
- `scripts/env/repos/demands.py` is the sole Demand persistence owner and already
  serializes concurrent actor aggregate writes.
- `demand_sys.create` is intake-key idempotent; `check` derives durable pending
  attention from `revision > checked_revision`.
- `demand_sys.check` returns full pending rows plus the compact live
  id/description index required for two-pass actor matching.
- `tools/launcher/im_wake_handler.py` currently calls Task ingress and executes
  the resulting Task runtime instruction.
- `tools/launcher/task_sys_ingress.py` currently contains separate IM and Track
  Task ingestion helpers.
- `tools/launcher/task_sys_runtime.py` still contains IM-source Task prompt
  branches and message-operation guidance.
- `scripts/env/services/messages.py` owns identity-scoped IM message reads, while
  `scripts/env/repos/messages.py` owns durable message and event records.
- `scripts/env/tool_runtime/im_actor_delivery.py` sends
  `im.message.created` through a generic daemon local trigger.
- `tools/launcher/daemon_runtime.py` already owns product-neutral host runtime
  access but does not yet project the existing Actor Session input primitive.
- `tools/launcher/actor_session.py::input_actor_turn` and
  `tools/launcher/app_server.py::input_turn` already implement the generic
  idle `turn/start` and active `turn/steer` mechanics.
- `tools/launcher/daemon_core.py` already logs generic notification and handler
  results without importing product semantics.
- `tools/launcher/instance_daemon.py` remains the explicit composition root for
  source registrations and product handlers.

The tracked worktree was clean at design start. The pre-existing untracked
`.superpowers/` directory is unrelated and must remain untouched.

## 4. Phase boundary

### 4.1 In Phase 2

- cut over only `im.message.created` for an active target actor;
- validate the exact IM message/event fact before Demand capture;
- map the IM fact deterministically to the existing canonical Demand schema;
- add a thin Demand-owned daemon adapter for capture plus attention request;
- project generic Actor Session input through the product-neutral daemon runtime;
- deliver a fixed Demand Check prompt with no canonical payload embedded;
- let the actor use existing Demand actions for two-pass matching and
  organization;
- make IM handling failure observable to its caller;
- remove all live IM-to-Task ingress and IM-source Task runtime behavior;
- prove the C/U/D scenario, failure recovery, zero Task effects, resource cleanup,
  and architecture boundaries;
- update current architecture documentation after implementation.

### 4.2 Not in Phase 2

- Track comment cutover;
- any second inbound source;
- offline-actor inbound backlog capture or replay;
- a retry scheduler, worker, event bus, ChangeSet ledger, or queue engine;
- Demand priority, ready queue, or task scheduling;
- Demand-to-Task references, imports, calls, callbacks, or shared transactions;
- Task creation from Demand, Task/Demand completion reconciliation, or a
  Demand-aware Task schema;
- Web Demand mutation UI;
- embeddings, vector search, a relation service, or programmatic similarity
  rules;
- direct user input as Demand inbound;
- compatibility aliases, dual writes, fallback reads, feature flags, or an old/new
  IM path switch.

### 4.3 Explicit active-actor precondition

The first vertical slice starts after the target actor is online and its daemon
accepts the `im.message.created` trigger. If the target is offline, current IM
delivery reports `target_not_online` and no Demand is created. This is a named
remaining boundary, not an implicit success case.

## 5. Alternatives considered

### 5.1 Target actor handler captures, then requests attention — selected

The existing target daemon handler validates the IM fact, calls the Demand-owned
adapter, and requests actor input only when durable pending Demand revisions
exist.

This is the shortest owner-correct replacement. It reuses the current source
delivery, Demand owner, and Actor Session primitive without centralizing target
Demand writes or adding asynchronous infrastructure.

### 5.2 Central IM writes the target Demand before delivery — rejected for Phase 2

This could create Demands while an actor is offline, but it makes the central IM
write path resolve target roles, write another actor's aggregate, and own backlog
recovery. That larger boundary is not required to prove the first active-actor
vertical slice.

### 5.3 Wake the actor and let the actor create the Demand — rejected

This leaves no canonical Demand when the actor cannot act and makes
`inbound -> Demand` depend on nondeterministic model success. Capture must precede
attention.

## 6. Target architecture

```text
Central IM owner
  save Message + visible Event
        |
        v
generic daemon local trigger: im.message.created
        |
        v
ImMessageCreatedHandler                         [IM source adapter]
  validate target + exact visible message/event
  map raw fact -> Demand intake
        |
        v
demand_sys_daemon_adapter.capture_inbound       [Demand runtime adapter]
  derive actor target from DaemonContext
  call demand_sys.create                         [canonical owner]
  call demand_sys.check                          [durable attention truth]
  if pending_count > 0:
      runtime.input_actor(DEMAND_CHECK_PROMPT)   [generic capability]
        |
        +--> idle thread   -> turn/start
        +--> active thread -> turn/steer
        |
        v
actor
  demand_sys.check
  coarse description match over live_index
  demand_sys.get_many for a small candidate set
  explicit organization action or no relation
  demand_sys.complete_check
```

There is no `demand_check_requested` event, intermediate event bus, or persisted
receipt stream. The inbound handler already runs at the correct trigger boundary,
so a direct capability call is clearer than redispatching the same fact.

## 7. Ownership and dependency rules

### 7.1 IM source adapter

`tools/launcher/im_wake_handler.py` owns:

- target actor and role validation;
- exact message, conversation, event, and recipient validation through IM-owned
  read contracts;
- deterministic conversion of the message fact to a Demand intake;
- calling the Demand runtime adapter once.

It may depend on IM services and the public Demand runtime adapter. It may not
import Task Sys, write Demand storage, construct actor input directly, infer
Demand relations, or mutate IM disposition as part of capture.

### 7.2 Demand domain and runtime adapter

`scripts/env/domain/demand_sys.py` remains the only lifecycle and mutation owner.
It must not import daemon, IM, or Task modules.

`tools/launcher/demand_sys_daemon_adapter.py` is the Demand product adapter used
by source handlers running inside the actor daemon. It
owns only:

- deriving the exact `{actor_id, role_id}` target from `DaemonContext`;
- calling `demand_sys.create` with source-normalized intake data;
- checking durable pending attention;
- the fixed Demand Check prompt;
- requesting generic actor input when pending work exists;
- returning an internal capture/attention receipt for tests and handler error
  propagation.

It is not a second write owner. It calls the same Demand domain action used by the
actor tool and never reads the Demand repository directly.

Its non-persisted internal receipt is deliberately compact:

```json
{
  "demand_id": "<demand-id>",
  "revision": 1,
  "capture_state_changed": true,
  "pending_count": 1,
  "attention_requested": true,
  "actor_input": {
    "action": "start|steer",
    "turn_id": "<turn-id>"
  }
}
```

`actor_input` is `null` when no attention is requested. Adapter errors raise to
the source handler. The receipt is test and propagation evidence only: it is not
stored, exposed as a second read model, or used instead of `demand_sys.check` on a
later delivery.

### 7.3 Generic daemon runtime

`tools/launcher/daemon_runtime.py` adds one product-neutral
`input_actor(text)` capability that delegates to the existing Actor Session
primitive using the current context socket, instance JSON, main thread,
permissions, model, and effort. It returns the existing input result, including
`action=start|steer` and `turn_id`; it does not normalize a Demand-specific
result.

The generic runtime does not own the Demand prompt, check policy, schema, ids,
errors, or state. Generic daemon core, contracts, state, mailbox, trigger, and
client modules remain free of Demand imports and tokens.

### 7.4 Actor

The actor owns every relation and organization judgment. No program rule decides
that D supplements C. The fixed prompt tells the actor to use existing Demand
actions and forbids Task operations during this Demand Check.

### 7.5 Task Sys

Task Sys is not registered as a consumer of Demand changes. It does not receive
raw IM, Demand ids, Demand snapshots, or check events in Phase 2.

## 8. IM-to-Demand capture contract

The handler loads the exact target-visible IM message through the existing
`messages.get_im_message` service and the exact event through a new
`messages.get_im_event` identity-scoped service backed by an exact repository
path lookup. The message id, conversation id, target actor, and event-to-message
link must all match the trigger. The event row must be the durable
`message.created` event visible to the target actor. A missing or mismatched fact
fails before any Demand mutation. The handler must explicitly verify that the
message target is the local actor; conversation membership alone is not enough.

The deterministic mapping is:

```json
{
  "actor_target": {
    "actor_id": "<DaemonContext.actor_id>",
    "role_id": "<DaemonContext.role>"
  },
  "intake_key": "im.message.created:<message_id>",
  "description": "<exact trimmed message.content>",
  "detail": "<exact trimmed message.content>",
  "source_refs": [
    {
      "type": "im.message.created",
      "ref": {
        "message_id": "<message_id>",
        "conversation_id": "<conversation_id>",
        "event_id": "<event_id>"
      }
    }
  ]
}
```

The adapter performs no summarization, truncation, prioritization, matching, or
relation inference. A temporarily long intake description is preferable to a
fabricated summary; the actor may revise it during the check.

`message_id`, rather than a delivery or correlation id, is the stable idempotency
identity. Re-delivery of the same source fact therefore returns the existing
Demand identity and cannot create a duplicate.

Direct user input remains an Actor Session primitive and never calls this mapping.

## 9. Attention policy

Attention is derived from canonical Demand state, not from whether the latest
capture receipt reported a state change:

```text
capture result
  -> demand_sys.check(actor_target)
      pending_count == 0 -> no actor input
      pending_count > 0  -> runtime.input_actor(fixed prompt)
```

This distinction is required because an exact create replay is a no-op even when
an earlier wake failed and the Demand revision remains unchecked.

The prompt is fixed and product-owned. Its semantic content is:

```text
[DEMAND CHECK]
Actor-owned Demand revisions require attention.
Call demand_sys.check(). Compare pending Demand descriptions with the live index,
load only plausible candidates with demand_sys.get_many, apply only necessary
Demand organization actions, and call demand_sys.complete_check with the exact
revisions observed. Do not create or modify Task Sys during this Demand Check.
```

Canonical Demand content is not copied into the prompt. One check handles the
entire pending set observed at that time. Multiple rapid IM events may produce a
start followed by steer, but they do not create a separate queue, waiting Task, or
one prompt per Demand invariant.

Actor-created Demand changes do not need an off-turn wake: the actor is already
active and receives the action receipt. Future off-turn sources reuse the same
Demand runtime adapter.

## 10. Failure and recovery semantics

### 10.1 IM persistence fails

No trigger is delivered and no Demand exists. IM remains the error owner.

### 10.2 Trigger fact is invalid or mismatched

The IM handler fails before Demand capture. Demand and Task state remain unchanged.

### 10.3 Demand capture fails

No actor input is requested. The handler returns failed and the delivery response
must expose handling failure.

### 10.4 Demand capture succeeds and actor input fails

The Demand remains durable with `revision > checked_revision`. The handler returns
failed. Re-delivery of the same trigger performs an idempotent create replay,
rechecks pending state, and attempts actor input again.

Phase 2 adds no autonomous retry scheduler. A later inbound event also checks the
entire pending set. Offline backlog and startup recovery remain explicit later
work.

### 10.5 Actor organization sees a stale revision

The existing Demand domain rejects the action atomically with
`E_DEMAND_REVISION_CONFLICT`. The actor must check or reread before retrying; no
fallback merge is allowed.

### 10.6 Actor does not acknowledge

The affected revision remains pending. No handler or timer marks it checked on the
actor's behalf.

### 10.7 IM handling response

`scripts/env/tool_runtime/im_actor_delivery.py` must stop reporting a failed
handler as successfully submitted:

```text
handling_status=handled -> actor_handling_status=submitted
handling_status=failed  -> actor_handling_status=handling_failed
```

The durable IM message remains accepted even when actor handling fails. Product
callers can distinguish storage success from proactive handling success.

## 11. Forward-only replacement

The same IM source may have only one live path after Phase 2:

```text
retired: im.message.created -> Task ingest -> Task side frame
current: im.message.created -> Demand capture -> Demand Check
```

The implementation must remove, not preserve:

- `task_sys_ingress.ingest_im_message`;
- IM imports/calls to `task_sys_ingress` and `task_sys_daemon_adapter`;
- IM-specific Task runtime prompt functions and branches;
- tests that teach IM messages as Task Sys ingress;
- Task Sys acceptance of `im.message.created` as a generic ingest source;
- current architecture assertions that Phase 1 has no IM integration, replacing
  them with exact Phase 2 boundary assertions;
- stale docs that describe the IM-to-Task path as current.

Task Sys must explicitly reject `im.message.created`, so a future caller cannot
silently recreate the retired route through the generic ingest function.

Track remains a separate current source and continues to use its existing Task
path during Phase 2. This is not a same-source compatibility path. Its removal
trigger is the later Track cutover; when that occurs,
`task_sys_ingress.ingest_track_comment` and the file itself are deleted if no
other current source remains.

## 12. Observability without a second truth

Phase 2 does not add a Demand change log. Canonical state remains the primary
evidence; logs prove delivery and causality:

| Evidence owner | Observable fact |
| --- | --- |
| IM service/repository | message id, event id, conversation id, target, original content |
| IM delivery response | target reachability and `actor_handling_status` derived from daemon handling; raw daemon status remains in daemon-owned logs/state |
| generic daemon log/state | trigger type, origin message id, handler result and failure |
| Actor Session/app-server thread | start or steer action and turn id |
| Demand actor aggregate | exact internal source refs, revisions, checked revisions, relations and lineage |
| public Demand CLI | intake key, description, revision/check state, parent/dependency ids and terminal lineage |
| public Task CLI | empty Task projection |

Correlation uses the stable message id in both the public Demand `intake_key` and
the IM record. Internal owner tests and the accepted real-actor owner read prove
the exact event and conversation source refs. Generic daemon logs remain
product-neutral; they do not copy Demand records or mutation receipts.

## 13. Core product scenarios

A fresh active actor receives these messages in order, waiting for each Demand
check to settle before the next:

```text
C: Support user data CSV export.
U: Fix payment request timeout.
D: CSV export must also include the user timezone.
```

Expected final semantics:

```text
C: live; description/detail include the timezone supplement and source refs include C and D
U: live root; independent and unchanged by C/D organization
D: terminal absorbed; ref == C

C.checked_revision == C.revision
U.checked_revision == U.revision
D.checked_revision == D.revision
pending_count == 0
Task records == []
```

For D, the actor calls `absorb_into` with C's merged description, detail, and
source refs. The existing domain action atomically revises C and terminalizes D;
there is no separate best-effort revise followed by lineage write.

The exact revision numbers are not frozen because the actor may legitimately
revise a description before consolidation. The semantic assertions are stable:
one intake per message, U remains independent, D terminates into C, C contains the
supplement, and every observed final revision is acknowledged.

## 14. Verification design

### 14.1 Exact RED/GREEN proof

Direct tests must first fail for the intended missing behavior, then pass through
the public BuddySwitch test runner:

- exact message/event validation and deterministic capture mapping;
- same-message idempotency and stable Demand identity;
- no pending Demand means no actor input;
- pending Demand uses generic input and preserves start/steer results;
- capture success plus input failure leaves one pending Demand;
- same-trigger redelivery retries wake without duplicate Demand;
- checked replay does not wake;
- wrong target, missing source fact, mismatched conversation/event, and payload
  failure leave Demand and Task bytes unchanged;
- IM handling failure is returned as `handling_failed`;
- direct actor input creates no Demand;
- every IM-trigger case leaves Task projection empty.

### 14.2 Architecture and replacement proof

Machine assertions must prove:

- Demand domain, repository, read projection, and actor tool import no IM, daemon,
  or Task product module;
- generic daemon core/contracts/state/mailbox/triggers/client import and name no
  Demand product concept;
- `daemon_runtime.py` exposes only generic actor input mechanics;
- only the IM handler and Demand daemon adapter connect the source to the Demand
  public owner;
- IM handler imports no Task module;
- Task ingress has no IM helper or source token;
- Task runtime has no IM-source prompt branch;
- Task domain rejects `im.message.created`;
- Track remains the only controlled source still using Task ingress;
- no alternate Demand store, write path, alias, fallback, feature flag, or dual
  source route exists.

### 14.3 IMPACT proof

Batch only compatible direct targets covering Demand owner, IM delivery and handler,
generic runtime input, Task retirement, architecture rules, native actor tool, and
public read projection. Resource-owning service or instance tests run separately.
Target selection is discovered from the final diff; no fixed suite count is a
contract.

### 14.4 Real actor MILESTONE

Use the public BuddySwitch CLI to create a new isolated actor with the installed
real Codex runtime. Use the real external IM HTTP surface to send C, U, and D. Do
not call `instance input` to simulate inbound and do not pre-create Demands through
the actor prompt.

Observe only supported product surfaces and owned logs:

- IM send/delivery responses;
- public `demand list/get` projection;
- public `task list` projection;
- daemon logs plus actor thread/turn records for trigger and input evidence.

The accepted run records source identity, Codex version, actor/thread/turn ids,
message/event ids, Demand ids and final projections, delivery responses, retries,
and exact process/socket/root cleanup. The nondeterministic actor sample supplements
repeatable tests; it does not replace them.

`./buddyswitch-test full` is not part of ordinary Phase 2 completion. It is reserved
for an explicit repository-wide acceptance or frozen merge/release candidate.

## 15. Intended change map

The implementation plan must validate these paths against the live repository
before editing, but the current owner-correct map is:

| Path | Intent |
| --- | --- |
| `tools/launcher/demand_sys_daemon_adapter.py` | new Demand-owned capture and attention adapter |
| `tools/launcher/daemon_runtime.py` | generic `input_actor` capability only |
| `tools/launcher/im_wake_handler.py` | replace Task ingestion with validated Demand intake |
| `scripts/env/repos/messages.py` | add exact event-by-id-and-visible-identity read |
| `scripts/env/services/messages.py` | add identity-scoped `get_im_event` projection |
| `scripts/env/tool_runtime/im_actor_delivery.py` | propagate handler failure accurately |
| `tools/launcher/task_sys_ingress.py` | delete IM helper; retain Track helper temporarily |
| `scripts/env/domain/task_sys.py` | explicitly reject retired IM ingest source |
| `tools/launcher/task_sys_runtime.py` | delete IM-source Task prompt behavior |
| `tests/unit/demand_sys/` | Demand attention adapter policy tests |
| `tests/unit/im/test_wake_handler.py` | exact source validation, capture, wake, failure and no-Task tests |
| `tests/integration/im/test_external_reply_loop.py` | source-to-Demand delivery integration replacement |
| `tests/unit/daemon/test_service_contract.py` | generic actor input capability and surface tests |
| `tests/unit/task_sys/` | retired IM source rejection and prompt residue tests |
| `tests/unit/architecture/test_demand_sys_boundaries.py` | replace Phase 1 absence law with exact Phase 2 dependency law |
| `tests/unit/daemon/` and `tests/unit/architecture/` | generic daemon and one-write-path guards |
| `docs/arch/demand-sys-architecture.md` | update implemented boundary only after implementation |
| `docs/arch/daemon-service-architecture.md` | document generic actor input capability if implementation changes its current contract |

No source-specific test runner, registry, event type, feature flag, compatibility
adapter, or migration command is added.

## 16. Expansion and recovery ledger

These items are deliberately not implemented in Phase 2, but are recorded here so
later work does not rediscover or forget them:

1. **Track cutover:** map exact Track comment facts to Demand, reuse the same
   attention adapter, delete `ingest_track_comment`, and delete
   `task_sys_ingress.py` when its last consumer is gone.
2. **Remaining inbound sources:** migrate one current source at a time; each source
   gets one direct replacement and removes its old destination in the same change.
3. **Offline actor capture:** decide whether capture moves source-side or whether an
   actor-start backlog replay consumes durable source events. Do not add both.
4. **Startup/pending recovery:** if real operation proves later inbound is
   insufficient recovery, add one Demand-owned recovery trigger using generic
   capabilities; do not add a global worker by default.
5. **Demand/Task coordination:** actor independently reads Demand and calls Task Sys
   in Phase 3. Neither module imports, subscribes to, or mutates the other.
6. **Task/Demand completion reconciliation:** Task completion is evidence only;
   actor reads the latest Demand revision and explicitly decides complete or keep
   live.
7. **Additional source observability:** extend existing source and public projections
   only when a real operator question cannot be answered by intake key, canonical
   Demand state, and owner logs.

## 17. Definition of done

Phase 2 is done only when:

1. the acceptance sentence is true for a fresh real actor and real IM source;
2. deterministic tests prove capture, attention, idempotency, recovery, and no Task
   side effects;
3. generic daemon remains semantically product-neutral;
4. Demand remains independently runnable and has one canonical write owner;
5. IM has one live destination path and Task rejects the retired source;
6. public state plus owner logs explain the C/U/D causal chain;
7. resource-owning tests and the real actor run leave no process, socket, lock, or
   isolated root residue;
8. Track and offline recovery remain explicitly bounded later work rather than
   hidden gaps;
9. current architecture docs describe only the implemented truth;
10. unrelated `.superpowers/` files remain untouched.
