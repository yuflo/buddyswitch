# Demand Sys Architecture

## Purpose

Demand Sys owns the actor's canonical needs. A Demand is an obligation whose
meaning and lifecycle are independent of execution work.

The current ingress path is:

```text
validated IM or Track fact
  -> source-keyed private ingress receipt
  -> isolated demand-triage side
  -> thread-only demand_triage.resolve
  -> Demand-owned atomic resolution
  -> canonical Demand pool
  -> durable demand_pool_revision attention
  -> parent demand-orchestration
  -> at most one current Task
```

The receipt is private recovery metadata inside the Demand aggregate. It has no
product identity, actor tool, read model, Web panel, CLI surface, or selectable
queue.

## One aggregate and one write path

The schema-v4 actor aggregate contains:

- canonical Demands;
- monotonic `demand_pool_revision`;
- source-keyed `ingress_receipts`;
- actor-create idempotency receipts.

`scripts/env/domain/demand_sys.py` owns receipt state, triage application,
Demand mutation, opaque references, and lifecycle.
`scripts/env/repos/demands.py` owns actor-scoped locking, full aggregate
validation, and atomic replacement. One resolution transaction updates the
receipt and any affected Demand together.

There is no compatibility reader, fallback schema, dual write, shadow queue,
or second Demand owner.

## Isolated triage and direct resolution

IM and Track owners validate and materialize their exact source facts, then use
the Demand adapter to create a due-now generic `demand.ingress.triage`
schedule. The registered Demand handler claims the source key and starts an
ephemeral isolated side.

That side receives:

- read-only `demand_sys__list` and `demand_sys__get`;
- source-local `message__get` and `message__conversation`;
- one dedicated `demand_triage.resolve` MCP tool.

It does not receive Message send, Demand mutation, Task, or unrelated product
tools. The host mints a one-side capability, stores only its hash and binding
in the side lease, and passes the raw token only to that side's MCP process.
The runtime broker validates the active actor, main/side identity, exact
purpose, source key, attempt, and open capability before calling the Demand
owner.

The resolver schema has six flat required fields and uses null for values that
do not apply. The decisions are:

```text
no_action_needed
handled
create
merge_intake
revise
cancel
```

`handled` is valid only for an exact IM source. The dedicated runtime finds an
existing actor reply by `reply_to` or sends it once through the Message owner,
verifies the stored Message, and only then supplies verified evidence to the
Demand transaction. The side cannot forge a Message receipt.

The turn has no `outputSchema`, final-message JSON parser, item-completed
consumer, or turn-completed consumer. A stale Demand reference returns the
source receipt to pending without partial mutation.

## Recovery and pool attention

The generic daemon core optionally invokes each registered handler's
`reconcile(context, state, runtime)` hook after actor registration and on
bounded timeout polling. It records results and isolates handler failures, but
does not know Demand states, revisions, prompts, or side purposes.

`DemandTriageHandler.reconcile` alone:

- starts pending source receipts;
- recovers a resolving receipt whose side lease was never registered;
- detects idle or system-error sides that ended without resolving;
- removes settled side leases;
- compares `demand_pool_revision` with its durable handler checkpoint;
- requests one duplicate-safe parent attention turn when no Task is active and
  the parent is idle.

If a Task is active or the parent is busy, the revision remains deferred. A
later poll rereads the one-active-Task and parent-activity invariants before
starting work. Resolution remains durable when the instance daemon is stopped
because the dedicated MCP process commits through the still-live runtime
broker; daemon reconciliation catches up from canonical state after restart.

## Actor tool boundary

The actor-facing `demand_sys` tool exposes exactly:

```text
list
get
create
revise
complete
cancel
```

The adapter derives actor ownership, provenance, idempotency, source
references, and concurrency from host context. The actor never supplies
storage paths, receipt keys, numeric revisions, terminal record structures, or
resolution authority. Mutations use the current opaque `demand_ref` returned
by `get`. `demand_pool_revision` and ingress receipts never appear in actor
responses.

Direct actor `create` declares a canonical independent Demand immediately. It
does not create an ingress receipt, but it increments the same private pool
revision and therefore enters the same serialized orchestration path.

## Demand and Task boundary

Demand completion and Task completion are independent. A terminal Task is
evidence; it never mutates a Demand automatically. The parent workflow rereads
the latest Demand and explicitly completes, cancels, revises, or leaves it live.

During the Phase 1 cutover, Task Sys retains its current execution lifecycle,
while Demand ingress and selection use only the architecture above. Phase 2
replaces that executor with native Codex Goal and removes the old Task frames;
it does not add a parallel Task path.

Task domain code does not import or mutate Demand state. Demand domain code
does not import or mutate Task state. The parent workflow is the semantic
composition point.

## Explicit non-goals

- No Demand graph, hierarchy, prerequisite engine, or semantic taxonomy.
- No first-class pre-Demand product object or second queue.
- No parent triage or semantic interrupt path.
- No automatic Demand completion from Task state.
- No Demand business rule in generic daemon-service code.
- No resolver in the six-action actor tool catalog.
- No alias, fallback, compatibility schema, dual read, or dual write for the
  retired triage path.
