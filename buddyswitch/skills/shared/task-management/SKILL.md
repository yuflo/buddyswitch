---
name: task-management
description: Use when an actor receives [DEMAND CHECK], a Task Sys side, parent, or completion frame, or must inspect or advance ongoing Task Sys state.
---

# task-management

## Ownership

- Demand Sys owns the need, its latest revision, organization, and terminal state.
- Task Sys owns one actor Task's creation, source snapshot, status, execution, and terminal result.
- The actor is the semantic bridge. Neither system's state implies a mutation in the other.
- Task `status` is the only lifecycle truth: `in_progress.side_processing`, `in_progress.awaiting_parent`, `in_progress.parent_processing`, `completed`, or `canceled`.
- Use native BuddySwitch env MCP tools through `env.tool`; never edit runtime objects directly.

## [DEMAND CHECK]

1. Call `demand_sys.check`. Compare pending descriptions with the live index, load only plausible matches with `demand_sys.get_many`, apply necessary organization actions, then call `demand_sys.complete_check` for the exact observed revisions.
2. Continue now with the Task Selection Rule.

## Task Selection Rule

1. Call `task_sys.list(status=active)`.
2. If a Task is active, do not create another. Leave other live Demands for a later check.
3. If none is active, call `demand_sys.list(state=live)`, choose at most one live Demand by current judgment, reread it with `demand_sys.get`, then call `task_sys.create` once with that exact `demand_id`, `basis_revision`, and a self-contained execution brief.

There is no queue, automatic selection, or automatic Demand-to-Task transition.

## Task Frames

- On `task_sys.side_frame`, call `task_sys.close` when side completes the frame, `task_sys.need_parent` when parent resources are required, or `task_sys.cancel` when work must stop.
- On `task_sys.parent_frame`, complete the requested parent work and call `task_sys.close`; cancel only when work must stop without completion.
- On a parent Progress Check, close, cancel, or continue parent work without changing status. Turn completion alone never completes a Task.
- Use `task_sys.list` or `task_sys.get` to read ongoing Task Sys task state.
- Use `task_sys.cancel` when the actor decides an active Task must stop without completion.

## Task Completion Check

On `task_sys.completion_frame`, the Task is already terminal:

1. Call `demand_sys.get` for the Demand named by the frame's source ref. If it is already terminal, do not mutate it.
2. For a live Demand, decide whether the latest Demand revision—not merely the Task's basis revision—is satisfied by the completion receipt.
3. If satisfied, call `demand_sys.complete` with the latest exact revision and pass the frame's `evidence_ref` unchanged: `{"type":"task_sys.task","ref":{"task_id":"<task_id>"}}`. Then acknowledge the returned completed revision with `demand_sys.complete_check`. Otherwise keep the Demand live.
4. Do not reopen or replace the completed Task for the same source snapshot. After reconciliation, continue now with the Task Selection Rule so at most one other live Demand can start.

Exact payloads and rejection recovery come from native schemas and `context.get.tool_catalog`. Product tools remain authoritative for their own data.
