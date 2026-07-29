# Demand Sys Architecture

## Purpose

Demand Sys owns one Actor's canonical needs. A Demand describes an acceptance
obligation; its lifecycle is independent of any individual Task used to make
progress.

The current path is:

```text
validated IM or Track fact
  -> private source-keyed ingress receipt
  -> isolated demand-triage side as a new ephemeral Actor thread
  -> exact buddyswitch-env side projection + shared $demand-triage Skill
  -> bounded Message context + complete current Demand context
  -> demand_sys__resolve_inbound through the normal unified env.tool wire
  -> one-use capability and side-thread authority validation
  -> Demand Sys atomic ingress application
  -> canonical Demand pool + pool revision
  -> independent parent Demand orchestration
  -> at most one active native-Goal Task
```

The ingress receipt is recovery metadata inside the Demand aggregate, not a
product object. It has no Actor tool, Web panel, CLI surface, or selectable
queue.

## One aggregate and one write path

The actor-scoped schema-version-5 aggregate contains exactly:

- `schema_version`;
- `actor_target`;
- canonical `demands`;
- monotonic `demand_pool_revision`;
- source-keyed `ingress_receipts`.

`src/buddyswitch/env/domain/demand_sys.py` is the only Demand mutation owner. Its
private record operations create, merge, revise, and terminalize records for
the two current application paths: bound inbound resolution and Parent
completion. Inbound cancellation and completion share one terminal-record
implementation.

`src/buddyswitch/env/repos/demands.py` owns actor-scoped locking, exact aggregate
validation, and atomic replacement. One inbound-resolution transaction settles
the receipt and applies any Demand change together.

There is no compatibility schema, fallback reader, shadow intake queue,
Actor-originated mutation path, or second write owner.

## Isolated inbound triage

IM and Track owners first validate and persist their exact source fact, then
schedule generic `demand.ingress.triage` attention. `DemandTriageHandler`
claims the receipt and starts the isolated demand-triage side as a new
ephemeral App Server thread with the same Actor workspace and project roots.
This is `thread/start`, not a fork of the parent transcript.

The side receives one exact `buddyswitch-env` projection:

```text
demand_sys__list
demand_sys__get
message__get
message__conversation
demand_sys__resolve_inbound
```

It also receives the selected shared `$demand-triage` Skill. It does not
receive Demand completion, Task mutation, Message send, or unrelated product
tools. BuddySwitch does not implement a second Skill loader or copy semantic
judgment into the handler prompt.

The selected Skill owns the semantic workflow. It reads the exact source
Message and bounded direct conversation for IM sources, lists all live and
terminal Demands, rereads every plausible target in full, and commits exactly
one resolution.

Decisions are exactly:

```text
no_action_needed
handled
create
merge_intake
revise
cancel
```

`no_action_needed` and `handled` settle the receipt without changing a Demand.
`create`, `merge_intake`, `revise`, and `cancel` apply one canonical Demand
mutation. `handled` requires verified Message evidence.

The side commits with `demand_sys__resolve_inbound` through the normal unified
environment MCP server and `env.tool` broker method. A private one-use
capability is injected only into that side process and becomes a private
invocation fact; it is not an action payload field.

Before mutation, the host application validates Actor, main-thread identity,
actual side-thread identity, side purpose, source key, receipt attempt, and
capability state. The normal Demand adapter then invokes the narrow
host-composed ingress application. Success truthfully reports both ingress
state change and capability consumption. Stale, foreign, missing, or consumed
authority cannot mutate the aggregate.

Demand Sys contains no model judgment, embedding, semantic similarity,
keyword classifier, target selection, or scoring. It validates authority,
proposal shape, receipt attempt, current opaque references, idempotency,
lifecycle, and atomic persistence only.

## Parent and Goal boundary

The public `demand_sys` definition contains exactly four actions:

```text
list
get
resolve_inbound
complete
```

Thread configuration projects that one definition into exact working surfaces:

- the isolated triage Side receives list, get, and resolve_inbound;
- Parent and Goal receive list, get, and complete;
- Parent configuration disables resolve_inbound.

No Actor thread can directly create, revise, or cancel a Demand. Those are
inbound triage decisions implemented privately by the Demand owner, not public
actions. Parent and Goal cannot obtain the private resolver capability.

The adapter derives Actor ownership and uses the opaque current `demand_ref`
returned by `get`. The Actor does not supply storage paths, receipt keys,
numeric revisions, or terminal record structures.

## Task completion boundary

A terminal Task never mutates a Demand automatically. An independent Parent
Demand-orchestration turn rereads the terminal Task, the latest Demand, and
the owning delivery products before deciding whether the acceptance obligation
is satisfied.

`demand_sys__complete` requires:

- the latest opaque `demand_ref`;
- at least one `task_sys.task` evidence reference;
- every referenced Task to be same Actor, same Demand, and completed;
- concrete delivery evidence beyond terminal Task status, such as an artifact
  or verified `im.message.reply`.

Task Sys owns Task identity, Actor binding, Demand binding, and terminal-status
validation through a narrow read contract. The Demand adapter validates all
Task and delivery evidence before calling the Demand domain owner. A stale
Demand reference or invalid evidence leaves Demand state unchanged.

For an IM-origin Demand, Parent verifies the exact durable reply content and
`reply_to` binding and cites both the completed Task and reply. If the latest
need or delivery is not satisfied, Parent leaves the Demand live. Any later
merge, revision, or cancellation still requires a new inbound triage fact.

The product constraint is one active Task per Actor. Empty-slot orchestration
compares the complete live Demand pool and selects at most one next Demand.

## Product handlers and recovery

Demand work is split by responsibility:

- `DemandTriageHandler` owns pending receipt recovery and isolated-side
  lifecycle;
- `DemandOrchestrationHandler` owns pool attention, terminal Task
  reconciliation, and serialized next-Task selection.

Both are product handlers composed by `instance_daemon.py`. Generic daemon
code supplies triggers, schedules, reconciliation activation, and opaque
checkpoints but contains no Demand meaning.

Canonical receipts, Demand pool revision, Task state, native Goal state, and
handler checkpoints are recovery truth. Notifications accelerate attention
but are not required for correctness. Triage reconciliation restarts pending
work and repairs orphaned Side state; orchestration reconciliation detects
unconsumed pool revisions and terminal Task evidence.

## Explicit non-goals

- No first-class pre-Demand product object.
- No Demand graph or dependency engine.
- No parent inbound-triage judgment.
- No Actor self-Demand mutation.
- No alternate Skill loader or handler-owned copy of the triage SOP.
- No dedicated Demand-triage MCP server or special broker route.
- No model judgment in Demand Sys or daemon-service core.
- No automatic Demand completion from Task status.
- No Demand business rule in daemon-service core.
