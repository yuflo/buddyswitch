---
name: demand-orchestration
description: Use in the parent thread when the Demand pool needs terminal-Task reconciliation or serialized selection of one current Task.
---

# demand-orchestration

## Ownership

This parent-only workflow owns Demand reconciliation and serialized work
selection. During the Phase 1 cutover, Task execution still follows the current
Task Sys lifecycle; Demand ingress and selection no longer do.

Use native BuddySwitch MCP tools through `env.tool`; exact contracts come from
`context.get.tool_catalog`.

## Reconcile a terminal Task

On `task_sys.outcome_frame`, reread the named Demand with `demand_sys__get`.
Task completion is evidence, not Demand completion. Complete the Demand only
when its latest need is satisfied. Otherwise revise it or leave it live.
Task cancellation likewise does not cancel the Demand automatically.

## Select current work

1. Call `task_sys__list` for active Tasks. If one is active, create none.
2. Otherwise call `demand_sys__list` for all live Demands.
3. Compare urgency, user commitment, blocked downstream work, continuity, evidence readiness, and staleness.
4. If any live Demand exists, select exactly one and record the selection reason. If none exists, create no Task.
5. Reread the selected Demand with `demand_sys__get`.
6. Call `task_sys__create` once with its opaque `demand_ref` and a self-contained execution brief containing the completion target and selection reason.

There is one current Task, while any number of live Demands may wait in the
canonical pool.
