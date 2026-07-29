# Task Sys Architecture

## Purpose

Task Sys owns one Actor's canonical execution commitment. A Task binds one
current Demand snapshot to one self-contained objective and one native Codex
Goal on the Actor's persistent main thread.

The current execution path is:

```text
independent parent Demand orchestration
  -> task_sys__create
  -> durable active Task
  -> task_goal.reconcile_task
  -> TaskGoalHandler
  -> Codex App Server thread/goal/set
  -> native Goal continuation on the main thread
  -> Goal notification or goal/get recovery
  -> durable completed or canceled Task
  -> Demand orchestration attention
```

Task Sys does not run work in an auxiliary thread, interpret inbound facts, or
decide whether a Demand is satisfied. Native Goal is the only Task execution
loop.

## One owner and one record

`src/buddyswitch/env/domain/task_sys.py` is the canonical Task owner. Its record has
exactly:

```text
schema_version
id
actor_target { actor_id, role_id }
demand_ref { demand_id, basis_revision, demand_ref }
objective
selection { reason, selected_at }
goal_binding | null
status
result | null
created_at
updated_at
```

Statuses are exactly `active`, `completed`, and `canceled`. At most one Task
may be active for an Actor. A Task remains bound to the Demand snapshot it was
created from; later Demand revisions are judged by Demand orchestration after
the Task is terminal.

There is no second Task schema, compatibility reader, alternate write path, or
execution state hidden in a side-thread lease.

## Actor tool boundary

The Actor-facing tool exposes exactly:

```text
list
get
create
cancel
```

`task_sys__create` accepts only an opaque `demand_ref`, a self-contained
`objective`, and a `selection_reason`. The tool boundary resolves the current Demand through
the Demand rule capability, derives the Actor target, writes the Task through
the Task owner, and requests idempotent Goal reconciliation.

The Actor cannot bind a Goal, mark a Task successful, write terminal host
snapshots, supply revisions, or synchronize a Demand. Successful completion
comes only from a matching native Goal becoming `complete`. `cancel` records
an explicit Actor decision to stop active work and requests matching Goal
cleanup.

## Task–Goal convergence

`src/buddyswitch/launcher/task_goal_handler.py` is the sole semantic adapter between Task
and native Goal state:

- an unbound active Task with no Goal causes `thread/goal/set`, then binds the
  returned Goal;
- an unbound active Task with the exact matching Goal binds it without
  creating another Goal;
- a bound Task with a matching non-complete Goal remains active;
- a bound Task with a matching complete Goal records one durable completed
  result;
- a bound Task whose Goal disappeared becomes canceled with an explicit host
  reason;
- a canceled Task clears only its matching Goal;
- a completed Goal already consumed by a prior Task is cleared before the next
  Task receives a fresh Goal;
- a different unfinished Goal is an invariant conflict and is never
  overwritten.

Non-complete native statuses such as paused, blocked, usage-limited, or
budget-limited keep the Task active. They are Goal execution state, not a
second Task lifecycle.

App Server owns Goal persistence, continuation, turn scheduling, and model
calls. The instance daemon hosts the adapter and accelerates convergence; it
does not execute the objective.

## Recovery

Task and `thread/goal/get` are canonical recovery truth. Goal notifications
accelerate convergence, but correctness does not depend on notification
history. The registered handler rereads both truths during daemon startup and
bounded generic reconciliation.

This makes these interruptions recoverable without a fallback path:

- Task persisted before the reconcile command reaches the daemon;
- Goal set before Task binding is persisted;
- Goal becomes complete while the daemon is unavailable;
- Goal cleanup notification is missed.

Repeated reconciliation is idempotent.

## Demand boundary

Task completion and Demand completion are deliberately independent. A terminal
Task is evidence. A later independent parent Demand orchestration turn rereads
the latest Demand and its owning delivery products. It calls
`demand_sys__complete` only when the complete latest need is satisfied;
otherwise it keeps the Demand live. Demand creation, merge, revision, and
cancellation remain exclusively bound-inbound triage decisions.

Demand completion requires at least one Task evidence reference. A narrow Task
Sys read contract verifies that every cited Task exists, belongs to the same
Actor, is bound to the same Demand, and is completed. The Demand adapter also
requires concrete delivery evidence beyond Task status and performs every
check before Demand mutation. Missing, active, canceled, cross-Actor,
cross-Demand, stale, or delivery-free evidence leaves the Demand unchanged.

Only after terminal reconciliation may an empty Task slot be filled from the
whole live Demand pool, and orchestration selects at most one next Demand.

Task domain code does not import or mutate Demand state. Demand domain code
does not import or mutate Task state. Demand orchestration is their explicit
product composition point.

## Projections

External-safe Task projections contain only:

```text
task_id
demand_ref
objective
selection
goal_binding
status
result
actor
updated_at
```

Actor Console exposes active and terminal collections only. Web and public CLI
are read-only Task consumers.
