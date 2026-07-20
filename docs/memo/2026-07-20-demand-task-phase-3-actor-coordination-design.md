# Demand / Task Phase 3 Actor Coordination Design

**Date:** 2026-07-20

**Status:** implemented and accepted

**Baseline:** `fea-daemon` at `d5959e41d9cdc713f6ea3429996491aa423c8cc5`

**Scope:** Actor-mediated Demand consumption through one active Task

**Accepted implementation:** the current Phase 3 change set was verified with
focused owner/impact tests and a fresh real CLI-created PM actor using installed
`codex-cli 0.144.6`. The accepted actor processed two real IM Demands through
two sequential parent-handoff Tasks with maximum active count one, exact Task
completion evidence, terminal checked Demand revisions, and clean scoped
runtime teardown.

## 1. Goal and acceptance sentence

Phase 3 closes the first Demand-to-execution loop without coupling the two
product owners:

```text
inbound fact -> Demand -> actor judgment -> optional Task
                                      Task completion -> actor judgment -> Demand
```

The acceptance sentence is:

> A fresh real BuddySwitch actor can receive two real IM needs, organize and
> acknowledge them through Demand Sys, execute them through actor-created Task
> Sys Tasks without ever having more than one active Task, receive a durable Task
> completion check, reread the latest Demand revision, and explicitly complete or
> keep each Demand live; Task Sys never reads or mutates Demand, Demand Sys never
> reads or mutates Task, and the generic daemon remains product-neutral.

## 2. Current bottleneck

Phase 1 built the independent Demand owner. Phase 2 replaced the live IM-to-Task
route with:

```text
IM -> Demand capture -> generic actor input -> Demand Check
```

The actor can organize and acknowledge Demands, but it cannot yet start a Task
from a Demand. The current `task_sys` actor tool exposes only `list`, `get`,
`close`, `cancel`, and `need_parent`. Task creation is still launcher-owned
ingress, and `task_sys.ingest` neither guarantees one active Task nor provides
source replay idempotency.

The missing product loop is therefore not a scheduler or relation engine. It is
one exact actor-owned collaboration contract:

```text
Demand snapshot -> task_sys.create -> one Task lifecycle -> completion receipt
                 -> actor rereads Demand -> demand_sys.complete or keep live
```

## 3. Repository facts

The design is based on the current implementation:

- `scripts/env/domain/demand_sys.py` owns Demand lifecycle, revision,
  organization, acknowledgement, and terminalization.
- `scripts/env/repos/demands.py` serializes each actor's Demand aggregate.
- `tools/launcher/demand_sys_daemon_adapter.py` captures inbound Demand and asks
  the generic runtime to input `[DEMAND CHECK]`; its current prompt explicitly
  forbids Task work.
- `scripts/env/domain/task_sys.py` owns the five canonical Task statuses and the
  legal lifecycle transitions.
- every current Task starts in `in_progress.side_processing`; side may close or
  hand off the same Task through `awaiting_parent` to `parent_processing`.
- `tools/launcher/task_sys_daemon_adapter.py` owns the existing main-thread
  turn-complete Progress Check for a parent-processing Task.
- `tools/launcher/task_sys_ingress.py` is still the current Track comment Task
  ingress until the later Track-to-Demand cutover.
- Task records are file-per-Task atomic replacements, but Task creation has no
  actor-scoped serialization or source replay contract.
- `task_sys.close` and `task_sys.need_parent` currently fail to enforce the
  active actor's ownership before mutation; `get` and `cancel` do enforce it.
- `buddyswitch/skills/shared/task-management/SKILL.md` is installed for every
  role and is the existing actor workflow owner, but it contains retired IM Task
  guidance and no Demand/Task coordination rule.
- `scripts/env/domain/tasks.py` is unreachable retired Task-model source; it
  imports the absent `env.repos.tasks` module and must not remain in the live
  domain tree.

The only unrelated worktree entry at design time is `.superpowers/`; it is not
part of this phase and must remain untouched.

## 4. Phase boundary

### 4.1 In Phase 3

- one actor-facing action: `task_sys.create`;
- one exact `DemandRef` and self-contained execution brief contract;
- source-idempotent Task creation;
- one atomic active-Task gate shared by actor creation and current Track ingress;
- the existing side-first lifecycle, unchanged;
- a Task-owned completion frame delivered to the parent actor;
- actor-owned Demand/Task coordination in the installed `task-management` skill;
- explicit latest-revision Demand reconciliation after Task completion;
- exact actor ownership checks for every Task mutation action;
- safe public DemandRef projection on Task list/get;
- deletion of retired Task domain and IM Task guidance residue;
- focused automated proof plus a real BuddySwitch CLI / real Codex actor
  milestone in the default product environment.

### 4.2 Not in Phase 3

- Track comment cutover to Demand; that remains Phase 4;
- offline Demand capture, startup recovery, or a pending-work worker;
- queues, priority, schedulers, workflow engines, rule engines, or event buses;
- multiple active Tasks, waiting Tasks, Task dependency graphs, or Task relations;
- automatic Demand-to-Task matching or programmatic Task selection;
- mutation of an active Task when its Demand revision changes;
- automatic Demand completion from Task completion;
- a shared Demand/Task transaction, callback, subscription, or repository;
- exact-once actor prompt delivery infrastructure;
- direct TUI input as Demand or Task intake;
- a public CLI mutation action or Web mutation UI;
- compatibility aliases such as `task_sys.start`, `task_sys.begin`, or a second
  Task create schema.

## 5. Alternatives considered

### 5.1 Actor creates a side Task and receives a completion check — selected

`task_sys.create` creates the same `in_progress.side_processing` Task used by the
current lifecycle. Side either completes its scope or hands the same Task to
parent. On terminal close, Task Sys sends a completion receipt to the parent
actor. The actor then reconciles Demand.

This preserves the already accepted lifecycle and adds only the missing actor
entry and exit checks.

### 5.2 Actor creates a Task directly in `parent_processing` — rejected

This is shorter locally but introduces a second create transition while the
frozen lifecycle says creation begins in side. Once external ingress is removed,
`side_processing` and `awaiting_parent` would become unexplained or unreachable.
That is structural drift rather than forward convergence.

### 5.3 Task completion automatically completes Demand — rejected

A completed Task proves that one execution against one observed Demand revision
ended. It does not prove that the latest Demand is satisfied. Automatic
completion would make Task Sys interpret Demand semantics and would overwrite
supplements or revisions that arrived during execution.

### 5.4 Reconcile only on the next inbound event — rejected

The state would eventually recover, but a successful Task could leave its Demand
live forever when no later inbound arrives. Phase 3 must close the normal
proactive loop directly.

## 6. Target architecture

```text
IM source adapter
  -> Demand daemon adapter
      -> Demand domain create/check
      -> generic DaemonRuntime.input_actor("[DEMAND CHECK]")
          |
          v
parent Actor + installed task-management skill
  -> demand_sys.check/get_many/organization/complete_check
  -> task_sys.list(status=active)
  -> task_sys.create(demand_ref, execution_brief)       [at most one]
          |
          v
Task Sys domain
  -> actor-scoped creation lock
  -> exact source replay / active conflict decision
  -> durable in_progress.side_processing Task
  -> existing start_side runtime instruction
          |
          v
side Actor -> close OR need_parent -> parent Actor -> close
          |
          v
Task Sys completion frame -> generic parent submit
          |
          v
parent Actor + installed task-management skill
  -> demand_sys.get(latest revision)
  -> demand_sys.complete(task evidence) OR keep live
  -> demand_sys.complete_check(completed revision when changed)
  -> shared at-most-one Task selection rule for another live Demand
```

The generic daemon transports triggers, mailbox commands, and actor input. It
does not import or branch on either product.

## 7. Ownership

| Owner | Owns | Must not own |
| --- | --- | --- |
| Demand Sys | Demand truth, revision, organization, check, terminal state | Task state, Task selection, Task lifecycle |
| Task Sys | Task creation idempotency, single-active gate, lifecycle, completion receipt | Demand lookup, revision validation, Demand terminal state |
| Actor | semantic matching, which Demand to work, whether changed Demand invalidates work, final reconciliation | direct storage writes or copied lifecycle rules |
| `task-management` skill | durable actor workflow guidance joining the two public action catalogs | canonical state or automatic decisions |
| Demand daemon adapter | inbound capture, pending attention, Demand Check prompt | Task import, call, schema, or decision |
| Task runtime adapter | Task frame rendering/submission and cleanup | Demand import, call, mutation, or satisfaction judgment |
| generic daemon | product-neutral delivery and host mechanics | Demand/Task tokens, schemas, prompts, or policies |

The Actor is the only semantic bridge. A reference in a Task record is a
collaboration fact, not a cross-domain call.

## 8. Public collaboration contract

### 8.1 Actor action

Phase 3 adds exactly:

```text
task_sys.create(
  demand_ref={
    demand_id: string,
    basis_revision: positive integer
  },
  execution_brief={
    description: non-empty string,
    detail: non-empty string
  }
)
```

`basis_revision` records what the actor observed. Task Sys validates shape only;
it never queries Demand or decides whether the reference is current.

The Task record uses existing fields:

```json
{
  "source_type": "demand",
  "source_ref": {
    "demand_id": "demand-...",
    "basis_revision": 4
  },
  "inbound_context": {
    "execution_brief": {
      "description": "...",
      "detail": "..."
    }
  },
  "status": "in_progress.side_processing"
}
```

There is no copied Demand status, priority, relation graph, current revision, or
completion flag in Task state.

### 8.2 Create outcomes

```text
created
  no exact source exists and no active Task exists
  -> persist one Task and execute one start_side instruction

existing
  exact actor + source_type + source_ref + execution brief already exists
  -> return the same Task; create no Task and start no second side thread

source_conflict
  same actor + source identity exists with a different execution brief
  -> reject; no state change

active_conflict
  a different active Task exists for the actor
  -> reject with active task id/status; no state change
```

The same creation owner is used by current `task_sys.ingest`. A Track source
replay therefore becomes idempotent, and a different Track or Demand source
cannot race a second active Task into existence.

Track remains an independently current source in Phase 3, not a compatibility
path. While an actor is busy, a new different Track comment is rejected
explicitly by the same gate; Phase 4 replaces that remaining direct ingress with
Demand intake so the need can remain durable without creating a Task.

### 8.3 Completion receipt

When a Demand-sourced Task closes, Task Sys can derive:

```json
{
  "task_id": "task-demand-...",
  "demand_ref": {
    "demand_id": "demand-...",
    "basis_revision": 4
  },
  "outcome": "completed",
  "summary": "..."
}
```

Task Sys submits this through the existing Task runtime command path as a strict
`task_sys.completion_frame`. It does not invoke Demand Sys. Delivery is
at-least-once safe: duplicate completion checks can only cause actor actions that
are already revision guarded or idempotent.

Non-Demand Tasks keep their current close behavior and receive no Demand
completion frame.

## 9. Actor workflow

The installed `task-management` skill becomes the sole durable coordination
guidance.

### 9.1 Demand Check

1. call `demand_sys.check`;
2. perform two-pass matching and only necessary Demand organization actions;
3. call `demand_sys.complete_check` for exact observed revisions;
4. call `task_sys.list(status=active)`;
5. if an active Task exists, do not create another;
6. if no active Task exists, choose at most one live Demand by actor judgment;
7. reread its exact current revision and call `task_sys.create` once.

There is no queue ordering rule. “Which one now?” remains an actor decision.

If a Demand associated with the active Task changes, the actor may:

- leave the Task active when its work remains useful; completion reconciliation
  will compare against the latest revision; or
- cancel the Task when the revision invalidates the execution basis, then create
  at most one replacement Task from the latest revision.

There is no Task alignment status or mutable Demand cursor.

### 9.2 Task completion check

1. treat the Task as already terminal;
2. read the Demand named by `demand_ref` through `demand_sys.get`;
3. if it is already terminal, perform no Demand mutation;
4. if the latest revision is satisfied by the Task result, call
   `demand_sys.complete` with that exact revision and a Task evidence ref;
5. otherwise keep the Demand live; do not reopen or rewrite the completed Task;
6. when no active Task exists, the actor may select at most one next live Demand.

The completion evidence is:

```json
{
  "type": "task_sys.task",
  "ref": {"id": "task-demand-..."}
}
```

## 10. Failure semantics

### 10.1 Concurrent creation

The actor-scoped Task creation lock serializes all Task sources. Exactly one
different source can create an active Task. Losers receive `active_conflict` and
write nothing.

### 10.2 Create persistence succeeds, side start fails

The existing Task runtime records a recoverable side failure on the same Task.
The create response exposes durable Task state and runtime failure. It does not
delete the Task, fabricate success, or create a fallback Task.

### 10.3 Task closes, completion-frame submission fails

The Task remains completed. The Demand remains live. The close response exposes
completion-attention failure. A later Demand Check can call `task_sys.create`
with the same DemandRef, receive the existing completed Task, and reconcile it;
no worker or hidden retry is added.

### 10.4 Task completes against an older Demand revision

The actor reads the latest Demand. It completes only when the latest need is
satisfied; otherwise it leaves the Demand live and may create a new Task at the
new revision after the active count is zero.

### 10.5 Demand completion rejects a stale revision

The Task stays completed and the Demand stays live. The actor rereads before any
retry. There is no fallback completion or cross-owner rollback.

### 10.6 Wrong actor attempts mutation

`get`, `close`, `cancel`, and `need_parent` all reject before mutation. Create
always derives the actor target from runtime identity.

## 11. Forward-only replacement and residue rules

The implementation must leave one current actor Task action surface:

```text
create, list, get, close, cancel, need_parent
```

It must not leave:

- `task_sys.start`, `begin`, `create_from_demand`, or payload aliases as actor
  actions;
- the Phase 2 sentence forbidding Task work during Demand Check;
- retired IM Task instructions in `task-management`;
- `scripts/env/domain/tasks.py` or tests that preserve it;
- a second single-active check in the tool or daemon;
- a second Demand/Task coordinator module, callback, registry, or event type;
- Demand imports in Task implementation or Task imports in Demand
  implementation;
- raw Demand/Task repository reads from actor guidance or adapters;
- same-source dual creation, fallback reads, dual writes, feature flags, or
  compatibility translation.

Current Track ingress remains only because Phase 4 has not yet replaced that
source. It calls the same canonical Task creation owner and has no alternate
gate, schema, or persistence path.

## 12. Observability

No new event store is needed.

| Surface | Evidence |
| --- | --- |
| public Demand CLI | current revision/check state and terminal evidence refs |
| public Task CLI | Task id, canonical status, source type, safe DemandRef |
| actor Task tool | create outcome, active conflict, runtime result, completion receipt |
| canonical Task record | one lifecycle, exact DemandRef, execution brief, events, result |
| app-server thread | Demand Check, Task frames, completion check, actor tool decisions |
| daemon/runtime logs | product-neutral trigger and Task runtime delivery outcomes |

The public Task projection adds only safe `demand_ref` for a Demand-sourced Task.
It does not expose raw context, events, runtime instructions, or arbitrary source
refs.

## 13. Verification design

The efficient evidence stack is:

1. **Owner RED/GREEN:** exact create/replay/conflict semantics and lifecycle.
2. **Atomic proof:** concurrent different sources create at most one active Task;
   failed losers write no Task.
3. **Tool/contract proof:** schema, permission, actor scope, runtime result, and
   public DemandRef projection.
4. **Completion proof:** side/parent close produces one strict completion frame;
   latest-revision Demand completion remains actor-owned.
5. **Architecture/replacement proof:** no cross-domain imports, generic daemon
   remains neutral, retired Task model and IM guidance are absent.
6. **Affected regression batch:** Task lifecycle, Track current ingress, Demand
   organization, IM capture, runtime broker, CLI projection, and role bootstrap.
7. **Real actor milestone:** public BuddySwitch CLI starts a fresh real Codex
   actor in the default environment; real external IM creates two Demands; actor
   creates and completes two Tasks sequentially; maximum observed active count is
   one; each completed Demand cites its Task; actor/process cleanup is scoped and
   verified.

`./buddyswitch-test full` is not planned. It remains reserved for an explicit
repository-wide or frozen release acceptance request.

## 14. Exit and next phase

Phase 3 exits when the acceptance sentence is proved and all replacement scans
are clean. Phase 4 then cuts Track comment intake to Demand and deletes the last
external Task ingress. Phase 3 must not prebuild that cutover or keep a second
Task path for future compatibility.
