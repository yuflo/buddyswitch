# Task Sys Architecture

## Purpose

Task Sys organizes execution of one actor-owned unit of work. The current
product invariant is one actor-scoped active Task. Every Task uses the same
side-first lifecycle:

```text
in_progress.side_processing
  |-> completed | canceled
  `-> in_progress.awaiting_parent
        `-> in_progress.parent_processing
              `-> completed | canceled
```

Task Sys does not own needs, matching, queueing, or coordination among needs.
Demand Sys owns those facts. The Actor + installed task-management skill is the
only semantic composition boundary between the two products.

Every Task is created from one exact DemandRef. The reference is an opaque
snapshot of the actor's selection, not permission for Task Sys to read or
interpret Demand state.

## Creation owner

`scripts/env/domain/task_sys.py` owns Task creation, source idempotency, the
single-active gate, lifecycle transitions, and Task frame construction.
`task_sys.create` is the sole Task creation path. It accepts one opaque
DemandRef snapshot plus a self-contained execution brief; Task Sys
validates their shape but does not read or interpret Demand state.

Inside its actor-scoped lock Task Sys:

1. returns an exact source/context replay without another runtime instruction;
2. rejects a reused source identity with different context;
3. rejects a different source while any Task is active;
4. otherwise persists one `in_progress.side_processing` Task and returns one
   `start_side` instruction.

Lock files are local coordination facts. Task JSON is the canonical product
truth. No inbound product handler can create a Task; the actor first
canonicalizes Demand state and then explicitly selects at most one Demand through
`task_sys.create`.

## Actor tool boundary

The actor tool adapter derives actor identity and role from `ToolContext`.
Callers cannot supply an actor target. Every Task read or mutation verifies the
same exact owner before access. The public action set is `create`, `list`,
`get`, `close`, `cancel`, and `need_parent`.

The adapter reaches Task semantics only through `ToolContext.rules.task_sys`
and runtime work only through `TaskSysRuntimeAccess`. It does not import a
Demand domain or repository, query Demand state, or mutate another product.

## Runtime frames

Task Sys owns three strict frame kinds:

- `task_sys.side_frame` starts every new Task;
- `task_sys.parent_frame` hands the same Task from side to parent;
- `task_sys.outcome_frame` returns a terminal Task receipt and its exact
  DemandRef to the parent Actor.

Parent handoff and outcome attention both reuse the existing `submit_parent`
runtime instruction. An outcome frame contains the Task id, canonical terminal
status, opaque DemandRef, exact `task_sys.task` evidence reference, and matching
completion or cancellation result only. It does not contain or copy Demand
status, lifecycle, detail, provenance, canonicalization judgment, or selection
policy.

Closing or canceling a Task persists terminal truth before outcome attention is
submitted. Submission failure is explicit feedback and never rolls back the
terminal Task. Every terminal Task emits the same outcome frame. The Actor
rereads Demand-owned state, decides any later Demand mutation, acknowledges the
resulting Demand revision when required, and then applies the same at-most-one
Task selection rule to another live Demand. Task cancellation never implies
Demand cancellation.

## Lifecycle attention

Every side processor runs in a fresh isolated ephemeral App Server thread.
`side_thread_lifecycle` creates it with `thread/start`, explicit side developer
instructions and runtime capability. It registers a `starting` lease before
submitting the self-contained side frame, atomically advances that lease to the
exact `work` turn, then reads the resulting generic thread status. Side
creation never inherits parent conversation history and has no fork or
boundary-injection path. A post-submit setup failure is retryable only after the
exact returned turn is interrupted and its lease is removed. If the starting
lease disappeared before binding, Task Sys rereads canonical Task status: only
a Task that already left `side_processing` is accepted as a legitimate
terminal/handoff consume; otherwise the exact unleased turn is interrupted and
the Task records a non-retryable runtime failure.

Task Sys owns one processor-aware Task Progress Check. The Task Sys daemon
adapter resolves the exact active Task from each processor's real yield signal:

- a completed main-thread turn may check only the actor's
  `in_progress.parent_processing` Task;
- an idle registered `task_sys.side_frame` thread may check only the exact
  actor-owned `in_progress.side_processing` Task named by its current lease and
  `work` turn id.

The runtime returns the check to the same processor: parent checks use the main
thread, while side checks use the exact registered side thread. A side work
turn is claimed by one atomic `work -> progress_check_pending -> progress_check`
lease transition; the creator performs the same claim immediately when its
post-start read finds that the first work turn already became idle. This closes
the notification-before-registration race without polling or retry logic. A
check turn is not eligible to create another check, including after daemon
restart. Side keeps `progress_check_pending` whenever external submission may
have happened but the returned turn identity could not be persisted; it rolls
back to `work` only when the lifecycle owner proves submission was not
attempted. Parent stores a `submitting` checkpoint before external submission,
then adds the submitted turn id after receipt. Generic daemon state persists
this opaque handler checkpoint; only the Task adapter interprets it. A completion or
idle signal itself never changes Task status; only actor-selected Task actions
do so.

Side frames may use only frame data and explicitly allowed product tools. Local
filesystem or shell inspection, including read-only workspace files, belongs to
parent processing and must use `task_sys.need_parent`.

## Read boundaries

Internal actor tools use `actor_task_projection`, which exposes canonical Task
status and execution facts for the active actor. Public CLI and Web surfaces
use `task_read`, an exact allowlist. Its `demand_ref` is the safe two-field
object copied from every Task's exact source snapshot. Malformed or non-Demand
records are rejected; they are not projected as a second supported shape. The
read model never projects execution briefs, events, runtime instructions, paths,
or raw context.

## Dependency laws

Allowed:

```text
Task tool -> ToolContext.rules.task_sys + TaskSysRuntimeAccess
Task read projection -> Task domain
Task runtime adapter -> Task domain + generic actor/runtime primitives
Actor workflow -> independent Demand Sys and Task Sys actor actions
```

Forbidden:

```text
Task implementation -> Demand import, read, validation, call, subscription, or mutation
Demand implementation -> Task import, read, call, or mutation
generic daemon -> Task or Demand business semantics
generic daemon checkpoint storage -> interpretation of Task turn identities
side lifecycle -> inherited parent conversation or parallel fork path
second create name, gate, source write path, lifecycle, or shadow Task state
Task outcome mutating Demand without an Actor decision
inbound product handler -> Task creation
```

These laws are enforced by
`tests/unit/architecture/test_task_sys_boundaries.py` and the adjacent Demand
and daemon boundary tests.
