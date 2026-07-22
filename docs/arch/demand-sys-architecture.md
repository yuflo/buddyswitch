# Demand Sys Architecture

## Purpose

Demand Sys is the local product module that captures and canonicalizes needs
owned by one actor. A Demand records what requires attention. It is not an
execution record and does not imply that work has started.

The implemented inbound paths are:

```text
IM message fact -> IM handler -> Demand daemon adapter -> Demand domain
Track comment fact -> Track handler -> Demand daemon adapter -> Demand domain
                                             |
                                             -> generic input_actor -> actor Demand Check

actor judgment -> demand_sys action -> Demand domain
```

Each inbound handler validates one exact target-visible source fact and maps it
deterministically to Demand intake. The Demand daemon adapter coordinates
capture, checks durable pending attention, and supplies one fixed Demand Check
prompt through generic actor input. It does not decide canonical identity,
select execution, or own storage.

## One canonical Demand set

The actor aggregate uses schema v2. It stores its actor target once and one
canonical Demand set keyed by Demand id. Each Demand carries its intake
identity, descriptive content, provenance, revision/check cursor, lifecycle
terminal, and timestamps. A null terminal means live. The only terminal
outcomes are completed, canceled, or absorbed into another live canonical
Demand.

`scripts/env/domain/demand_sys.py` is the single semantic owner for capture,
revision, attention, canonicalization, and lifecycle. It is the only caller of
the aggregate transaction operation. `scripts/env/repos/demands.py` is the
single storage owner at:

```text
buddyswitch/objects/demand-sys/actors/<actor-id>-<role-id>.json
```

The Domain validates current records and every mutation input before returning
a next state. The repository takes an exclusive actor-scoped lock, validates
the aggregate envelope, and atomically replaces the file only when state
changes. Normal reads accept schema v2 only. There is no aggregate discovery,
cross-actor fallback, older-schema translation, or second write path.

## Two-pass actor canonicalization

Inbound and actor sources always capture a new need before semantic judgment.
On Demand Check the actor performs two-pass actor canonicalization:

1. compare every pending description with the compact live index;
2. load complete records only for plausible candidates;
3. revise the row, absorb it into the same canonical need, keep it independently
   live, or cancel it;
4. acknowledge only the exact revisions actually observed.

`absorb_into` is the only cross-record semantic mutation. It validates two
distinct live rows and both expected revisions in one transaction. The actor
provides the merged target description and detail. The domain merges provenance
in target-first unique order, advances the target, and makes the source an
immutable absorbed terminal pointing to the target Demand id.

Source references are provenance and retrieval context, not canonical identity.
For a Track-backed Demand the actor may use the stored Track identity to read
more source context. Track thread structure never decides canonical Demand
identity.

Before absorption, the Actor + installed task-management skill reads active
Task state. If exactly one of the two Demand rows is already represented by the
active Task, that row remains the absorption target. This is actor workflow
guidance, not a Demand domain dependency. The Task keeps its original opaque
DemandRef snapshot; the actor rereads the latest Demand during later progress
and outcome checks.

## Attention and lifecycle

`check` is read-only. It returns every revision newer than its check cursor, a
compact id/description index of live Demands, and the pending count.
`complete_check` advances only revisions the actor actually observed, so a
concurrent newer revision remains pending. This cursor is Demand attention
state, not Task progress and not a daemon subscription.

Demand completion is independent of Task completion. A terminal Task produces
an outcome frame, after which the actor rereads the latest Demand and explicitly
decides whether the need is satisfied, canceled, revised, or still live. A
Task outcome never mutates Demand state by implication.

The actor tool exposes capture, revision, reads, attention acknowledgement,
absorption, completion, and cancellation. Exact payloads and response contracts
belong to `scripts/env/tools/demand_sys/tool.py`; this document does not mirror
them. Existing-record writes are expected-revision guarded. Exact intake and
terminal replays are idempotent; conflicting or stale writes leave the
aggregate unchanged.

## Product boundaries

The only actor tool id is `demand_sys`. Its adapter derives actor identity and
role from `ToolContext` and reaches the owner only through
`ToolContext.rules.demand_sys`. It has no repository, Task runtime, daemon,
inbound, actor-override, alias, or fallback capability.

Public reads use `scripts/env/domain/demand_read.py`, which projects an
actor-scoped allowlist and omits private detail and provenance. The CLI remains
read-only:

```text
buddyswitch-codex demand list --actor <actor-id>
buddyswitch-codex demand get <demand-id> --actor <actor-id>
```

Task Sys stores only the opaque DemandRef `{demand_id, basis_revision}` selected by the
actor. Task implementation does not import, read, validate, call, subscribe to,
or mutate Demand state. Generic daemon infrastructure delivers opaque trigger
and actor-input mechanics; it contains no Demand rule.

Allowed dependencies:

```text
Demand domain -> Demand repository -> runtime file primitives
Demand read projection -> Demand domain
Demand tool adapter -> ToolContext.rules.demand_sys
public CLI -> Demand read projection
IM/Track handler -> owning source read + Demand daemon adapter
Demand daemon adapter -> Demand domain + generic input_actor
Actor workflow -> independent Demand Sys and Task Sys actions
```

## Explicit non-goals

- No cross-Demand graph, hierarchy, prerequisite network, or general semantic
  taxonomy.
- No queue, scheduler, automatic work selection, or automatic Demand-to-Task
  transition.
- No Demand-to-Task callback and no Task-to-Demand completion callback.
- No business rule in generic daemon infrastructure.
- No schema compatibility reader, alias, dual write, shadow state, or migration
  framework.

These boundaries are enforced by
`tests/unit/architecture/test_demand_sys_boundaries.py` plus direct domain,
repository, tool, inbound, and process tests.
