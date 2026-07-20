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

## Creation owner

`scripts/env/domain/task_sys.py` owns Task creation, source idempotency, the
single-active gate, lifecycle transitions, and Task frame construction.
`task_sys.create` is the only actor-facing creation action. It accepts one
opaque DemandRef snapshot plus a self-contained execution brief; Task Sys
validates their shape but does not read or interpret Demand state.

Actor creation and current Track comment ingress call the same private creation
primitive under one actor-scoped lock. Inside that lock Task Sys:

1. returns an exact source/context replay without another runtime instruction;
2. rejects a reused source identity with different context;
3. rejects a different source while any Task is active;
4. otherwise persists one `in_progress.side_processing` Task and returns one
   `start_side` instruction.

Lock files are local coordination facts. Task JSON is the canonical product
truth. Track comment ingress remains one current source until its planned
Demand intake cutover; it does not own a separate gate or write path.

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
- `task_sys.completion_frame` returns a terminal Demand-sourced Task receipt to
  the parent Actor.

Parent handoff and completion attention both reuse the existing
`submit_parent` runtime instruction. A completion frame contains the Task id,
opaque DemandRef, exact `task_sys.task` evidence reference, and Task completion
result only. It does not contain or copy Demand status, lifecycle, detail,
relation state, or selection policy.

Closing a Task persists terminal truth before completion attention is
submitted. Submission failure is explicit feedback and never rolls back the
completed Task. Non-Demand Tasks do not emit a completion frame. The Actor
rereads source-owned state, decides any later source mutation, acknowledges the
resulting Demand revision, and then applies the same at-most-one Task selection
rule to another live Demand.

Side frames may use only frame data and explicitly allowed product tools. Local
filesystem or shell inspection, including read-only workspace files, belongs to
parent processing and must use `task_sys.need_parent`.

## Read boundaries

Internal actor tools use `actor_task_projection`, which exposes canonical Task
status and execution facts for the active actor. Public CLI and Web surfaces
use `task_read`, an exact allowlist. Its `demand_ref` is the safe two-field
object only for Demand-sourced Tasks and `null` for every other source. It never
projects arbitrary source refs, execution briefs, events, runtime instructions,
paths, or raw context.

## Dependency laws

Allowed:

```text
Task tool -> ToolContext.rules.task_sys + TaskSysRuntimeAccess
Task read projection -> Task domain
Task runtime adapter -> Task domain + generic actor/runtime primitives
Track comment handler -> shared Task ingress
Actor workflow -> independent Demand Sys and Task Sys actor actions
```

Forbidden:

```text
Task implementation -> Demand import, read, validation, call, subscription, or mutation
Demand implementation -> Task import, read, call, or mutation
generic daemon -> Task or Demand business semantics
second create name, gate, source write path, lifecycle, or shadow Task state
Task completion mutating Demand without an Actor decision
```

These laws are enforced by
`tests/unit/architecture/test_task_sys_boundaries.py` and the adjacent Demand
and daemon boundary tests.
