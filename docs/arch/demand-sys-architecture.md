# Demand Sys Architecture

## Purpose

Demand Sys is the local product module that captures and organizes needs owned
by one actor. A Demand records what requires attention; it is not a Task Sys
execution record and does not imply that work has started.

The implemented inbound boundary is:

```text
IM message fact -> IM handler -> Demand daemon adapter -> Demand domain
                                      |
                                      -> generic input_actor -> actor Demand Check

actor judgment -> demand_sys action -> Demand domain
```

The IM handler validates one exact target-visible message/event fact and maps it
deterministically to Demand intake. The Demand daemon adapter owns only capture
coordination, pending-attention policy, and the fixed Demand Check prompt. It
calls the same domain owner used by actor actions and uses the generic daemon
`input_actor` host capability; it does not own lifecycle or storage.

The actor owns matching and organization judgment. Task Sys has no IM or Demand
dependency. Track remains on its separate current Task path. This phase captures
only for an already-active target actor; offline capture, replay, and startup
recovery are not implemented.

## Ownership and storage

`scripts/env/domain/demand_sys.py` is the sole owner of Demand lifecycle,
revision, check, relation, and terminal-lineage rules. Only this module calls
the aggregate transaction operation.

`scripts/env/repos/demands.py` is the sole storage owner. It persists one
atomic aggregate per exact actor identity and role at:

```text
buddyswitch/objects/demand-sys/actors/<actor-id>-<role-id>.json
```

The aggregate contains only its schema version, exact actor target, and Demand
records keyed by Demand id. Mutations take an exclusive per-actor lock and
atomically replace the aggregate only when the domain reports a state change.
There is no aggregate-wide discovery or cross-actor fallback read.

## Demand record

A Demand is a revisioned need with:

- an actor-scoped intake key;
- compact `description` and detailed `detail` content;
- source references;
- optional `parent_id` and `depends_on` live structure;
- `revision` and `checked_revision` attention state;
- one optional terminal record;
- creation and update timestamps.

The canonical terminal types are `completed`, `canceled`, `absorbed`,
`duplicate`, and `superseded`. Terminal lineage belongs to the source Demand;
live organization edges remain limited to parent and dependency relations.

## Domain actions

The current domain and actor tool expose one action vocabulary:

- capture and content: `create`, `revise`;
- reads and attention: `list`, `get`, `get_many`, `check`, `complete_check`;
- live organization: `set_parent`, `add_dependency`, `remove_dependency`,
  `split`;
- consolidation and lineage: `absorb_into`, `mark_duplicate`, `supersede`;
- terminal decisions: `complete`, `cancel`.

Exact input schemas and action semantics are owned by
`scripts/env/tools/demand_sys/tool.py`; this document does not duplicate that
contract.

All existing-Demand mutations are revision guarded. Multi-record actions such
as `split` and `absorb_into` validate and mutate inside one actor aggregate
transaction. Parent and dependency cycles are rejected. Exact intake and
terminal action replays are idempotent; conflicting replays are rejected.

## Check semantics

`check` is read-only. It returns:

- every record whose `revision` is newer than `checked_revision`;
- a compact id/description index of all live Demands for first-pass matching;
- the pending count.

The actor may use `get_many` for detailed comparison of selected candidates,
apply any required organization actions, then call `complete_check` with only
the exact Demand revisions it observed. Acknowledgement never advances past an
observed revision, so a concurrent newer revision remains pending.

This is attention state, not Task progress state and not a daemon subscription.
After inbound capture, the Demand daemon adapter derives attention only from
this durable pending state. A create replay therefore retries actor input while
the revision remains unchecked and does not wake after acknowledgement.

## Actor tool boundary

The only actor tool id is `demand_sys`. Its adapter derives the actor target
only from `ToolContext.current_actor_identity_profile` and reaches the domain
only through `ToolContext.rules.demand_sys`.

The adapter has no Demand repository capability, Task Sys dependency, daemon
capability, inbound capability, actor-id payload override, alias, or fallback.
All manifest roles receive the exact `demand_sys.*` permissions declared by the
tool actions.

## Public read boundary

`scripts/env/domain/demand_read.py` projects an actor-scoped allowlist that
omits Demand detail and source refs. The public CLI is a thin consumer:

```text
buddyswitch-codex demand list --actor <actor-id>
buddyswitch-codex demand get <demand-id> --actor <actor-id>
```

Both commands require an actor id. The CLI exposes no Demand mutation and does
not read aggregate files directly.

## Dependency laws

Allowed:

```text
Demand domain -> Demand repository -> runtime file primitives
Demand read projection -> Demand domain
Demand tool adapter -> ToolContext.rules.demand_sys
public CLI -> Demand read projection
IM handler -> IM read service + Demand daemon adapter
Demand daemon adapter -> Demand domain + generic DaemonRuntime.input_actor
```

Forbidden:

```text
Demand implementation -> Task Sys
Demand implementation -> daemon modules or launcher product adapters
generic daemon -> Demand implementation or Demand semantics
IM handler -> Task Sys
Task Sys -> IM or Demand
Track handler -> Demand implementation in this phase
public CLI or actor tool -> Demand repository/raw aggregate files
new Demand alias, fallback read, dual write, shadow state, or second schema
```

These laws are enforced by
`tests/unit/architecture/test_demand_sys_boundaries.py` in addition to the
behavioral and atomicity tests.
