# Demand Sys Architecture

## Purpose

Demand Sys owns an Actor's canonical needs. A Demand describes an obligation;
its lifecycle is independent of any individual Task used to make progress.

The current path is:

```text
validated IM or Track fact
  -> private source-keyed ingress receipt
  -> isolated demand-triage side as a new ephemeral thread in the Actor workspace
  -> native selection of the shared $demand-triage Skill
  -> bounded Message context + compact all-state Demand context
  -> demand_triage.resolve
  -> Demand Sys deterministic validation + atomic application
  -> canonical Demand pool + pool revision
  -> independent parent Demand orchestration
  -> at most one active native-Goal Task
```

The ingress receipt is recovery metadata inside the Demand aggregate, not a
product object. It has no Actor tool, Web panel, CLI surface, or selectable
queue.

## One aggregate and one write path

The actor-scoped Demand aggregate contains:

- canonical Demands;
- a monotonic Demand-pool revision;
- source-keyed ingress receipts;
- Actor-create idempotency receipts.

`scripts/env/domain/demand_sys.py` owns Demand mutation, receipt state, triage
application, lifecycle, and opaque references.
`scripts/env/repos/demands.py` owns actor-scoped locking, aggregate validation,
and atomic replacement. One resolution transaction settles the receipt and
applies any Demand change together.

There is no compatibility schema, fallback reader, shadow intake queue, or
second mutation path.

## Isolated inbound triage

IM and Track owners first validate and persist their exact source fact, then
schedule generic `demand.ingress.triage` attention. `DemandTriageHandler`
claims the receipt and starts the isolated demand-triage side as a new
ephemeral App Server thread with the same Actor workspace and project roots.
This is `thread/start`, not a fork of the parent transcript: it shares the
Actor's installed Skills and canonical state, but it does not inherit the
parent context window.

Every role installs the same shared `demand-triage` Skill in its Actor
workspace. The thin side prompt explicitly selects `$demand-triage`, so Codex
natively injects the complete Skill before the first model sampling. BuddySwitch
does not implement a second Skill loader or copy the semantic workflow into the
handler prompt.

The selected Skill owns the one semantic judgment workflow. It reads:

- read-only `demand_sys__list` and `demand_sys__get`;
- the compact all-state Demand pool, followed by full reads of plausible
  targets and all live candidates before create;
- the exact source Message and a bounded latest direct conversation for IM
  sources;
- one capability-bound `demand_triage.resolve` operation.

The side does not receive Demand mutation, Task creation, Message send, or
unrelated product tools. The host validates Actor, main/side identity, purpose,
source key, attempt, and one-use capability before Demand Sys applies the
decision.

Decisions are exactly:

```text
no_action_needed
handled
create
merge_intake
revise
cancel
```

`no_action_needed` and `handled` settle the receipt without creating or
changing a Demand. `create`, `merge_intake`, `revise`, and `cancel` apply one
Demand mutation. `handled` requires verified Message evidence; the side cannot
forge it.

Inbound semantic judgment finishes entirely in the isolated side. There is no
parent escalation branch. The later parent orchestration turn is a different
workflow: it consumes the canonical Demand pool, not an unresolved triage
decision.

The side resolves through a dedicated MCP operation rather than returning a
strict final-message JSON shape. Resolution persists immediately through the
runtime broker. A stale reference returns the receipt to pending without a
partial mutation.

Demand Sys contains no model judgment, embedding, semantic similarity,
keyword classifier, target selection, or scoring. It validates authority,
proposal shape, receipt attempt, current opaque references, idempotency,
lifecycle, and atomic persistence only. `demand_triage.resolve` is the single
triage commit path.

## Two product handlers

Demand work is intentionally split by responsibility:

- `DemandTriageHandler` owns pending receipt recovery and isolated side
  lifecycle only;
- `DemandOrchestrationHandler` owns durable pool attention, terminal Task
  reconciliation, and serialized Task selection only.

Neither responsibility lives in generic daemon code. Both handlers use the
daemon's product-neutral trigger and reconciliation capabilities.

The orchestration handler starts an independent parent turn only when the
parent is idle and product state requires judgment. It rereads canonical state,
reconciles terminal Tasks against their latest Demands, then fills an empty
Task slot from the complete live Demand pool. Busy parent state or an active
Task defers attention without losing it.

## Actor tool boundary

The Actor-facing `demand_sys` tool exposes exactly:

```text
list
get
create
revise
complete
cancel
```

The adapter derives Actor ownership, provenance, source references,
idempotency, and concurrency. The Actor does not supply storage paths, receipt
keys, numeric revisions, or terminal record structures. Mutations use the
opaque current `demand_ref` returned by `get`.

Direct Actor `create` writes a canonical independent Demand immediately. It
does not create an ingress receipt, but increments the same pool revision and
enters the same orchestration path.

## Task boundary

A terminal Task never mutates a Demand automatically. Demand orchestration
rereads the latest Demand and treats the Task result as evidence:

- complete the Demand only if the latest need is satisfied;
- revise or leave it live when more work is required;
- cancel it only when the need itself is withdrawn or no longer valid.

For a Demand sourced from `im.message.created`, user delivery is part of the
latest need. Orchestration copies the exact source `message_id` into the Task
objective and requires `message.send(reply_to=source message_id)` plus an exact
Message reread before Goal completion. The later reconciliation turn verifies
the durable reply again and cites that reply alongside Task evidence. A Codex
final answer or a completed Task/Goal is not Central IM delivery; without a
matching reply, the Demand stays live and is revised when a fresh Task is
needed for the remaining delivery.

The current product constraint is one Task per Demand at a time and one active
Task per Actor. Demand and Task remain separate owners so future Task
decomposition does not require changing Demand lifecycle semantics.

## Recovery

Canonical receipts, Demand pool revision, Task state, and handler checkpoints
are recovery truth. Notifications accelerate attention but are not required
for correctness. On startup and bounded polling:

- triage reconciliation restarts pending work and repairs orphaned side state;
- orchestration reconciliation detects unconsumed pool revisions and terminal
  Task evidence.

Daemon state stores only opaque handler checkpoints. It does not interpret
Demand fields or select work.

## Explicit non-goals

- No first-class pre-Demand product object.
- No Demand graph or dependency engine.
- No parent inbound-triage judgment.
- No alternate Skill loader or handler-owned copy of the triage SOP.
- No model judgment in Demand Sys or daemon-service core.
- No automatic Demand completion from Task status.
- No Demand business rule in daemon-service core.
- No resolver in the six-action Actor tool catalog.
