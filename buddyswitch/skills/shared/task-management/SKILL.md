---
name: task-management
description: Use when an actor receives [DEMAND CHECK], a Task Sys side, parent, outcome, or Progress Check, or must inspect or advance ongoing Task Sys state.
---

# task-management

## Ownership

- Demand Sys owns the need, its provenance, latest revision, canonical identity, and terminal state.
- Task Sys owns one actor Task's creation, source snapshot, status, execution, and terminal result.
- The actor is the semantic bridge. Neither system's state implies a mutation in the other.
- Task `status` is the only lifecycle truth: `in_progress.side_processing`, `in_progress.awaiting_parent`, `in_progress.parent_processing`, `completed`, or `canceled`.
- Use native BuddySwitch env MCP tools through `env.tool`; never edit runtime objects directly.
- Exact Task Sys payloads, effects, and response meanings come from native schemas and `context.get.tool_catalog['task_sys']`.
- Diagnostic fallback: `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`.

## [DEMAND CHECK]

1. Call `demand_sys.check` and compare every pending description with the compact live index.
2. Only for plausible candidates, call `demand_sys.get_many` and compare complete descriptions and details.
3. For each pending Demand, decide whether to revise it, absorb it, keep it independent, or cancel it.
4. Before calling `demand_sys.absorb_into`, call `task_sys.list(status=active)`. If exactly one active Task references either Demand, that active Task's Demand must remain the absorption target. Never update the active Task's `basis_revision` after absorption; reread the latest Demand during progress and outcome checks.
5. Call `demand_sys.complete_check` for the exact revisions actually observed, including the exact returned revision of every mutation.
6. Continue now with the Task Selection Rule.

Demand source refs are provenance and retrieval context, not Demand identity. When a
`track.comment.added` Demand needs more context than its stored detail, use the
exact Track id with Track reads. Track thread structure alone never decides
whether two Demand rows express the same need.

## Task Selection Rule

1. Call `task_sys.list(status=active)`.
2. If a Task is active, do not create another. Leave other live Demands for a later check.
3. If none is active, call `demand_sys.list(state=live)`, choose at most one live Demand by current judgment, reread it with `demand_sys.get`, then call `task_sys.create` once with that exact `demand_id`, `basis_revision`, and a self-contained execution brief.

There is no queue, automatic selection, or automatic Demand-to-Task transition.

## Task Frames

- On `task_sys.side_frame`, call `task_sys.close` when side completes the frame, `task_sys.need_parent` when parent resources are required, or `task_sys.cancel` when work must stop.
- On `task_sys.parent_frame`, complete the requested parent work and call `task_sys.close`; cancel only when work must stop without completion.
- On a side Progress Check, close, cancel, request parent work, or continue side work without changing status merely for continuing.
- On a parent Progress Check, close, cancel, or continue parent work without changing status merely for continuing. Turn completion alone never completes a Task.
- Use `task_sys.list` or `task_sys.get` to read ongoing Task Sys task state.
- Use `task_sys.cancel` when the actor decides an active Task must stop without completion.

## Task Outcome Check

On `task_sys.outcome_frame`, the Task is already terminal:

1. Call `demand_sys.get` for the Demand named by the frame's source ref. If it is already terminal, do not mutate it.
2. If Task status is `completed`, decide whether the latest Demand revision—not merely the Task's basis revision—is satisfied by the completion receipt. If satisfied, call `demand_sys.complete` with the latest exact revision and pass the frame's `evidence_ref` unchanged: `{"type":"task_sys.task","ref":{"task_id":"<task_id>"}}`. Otherwise keep the Demand live.
3. If Task status is `canceled`, remember that Task cancellation does not imply Demand cancellation. Decide from the latest Demand whether to complete, cancel, revise, or keep it live, then use the corresponding Demand Sys action only when a mutation is warranted.
4. After any Demand mutation, acknowledge its exact returned revision with `demand_sys.complete_check`. Do not invent a revision when reconciliation makes no mutation.
5. Do not reopen or replace the terminal Task for the same source snapshot. After reconciliation, continue now with the Task Selection Rule so at most one other live Demand can start.

For action details and rejection recovery, inspect `context.get.tool_catalog['task_sys']` or `"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status`; runtime response fields and product tools remain authoritative for their own data.
