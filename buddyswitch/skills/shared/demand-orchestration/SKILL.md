---
name: demand-orchestration
description: Use in an independent parent turn when terminal Tasks need Demand reconciliation or live Demands need serialized native-Goal Task selection.
---

# Demand orchestration

Own the Actor judgment between the canonical Demand pool and one native-Goal
Task slot. Task completion is evidence, not Demand completion. One Task per
Demand is the current Phase 2 constraint; Demand and Task lifecycles remain
decoupled.

Use native BuddySwitch env MCP tools. Read exact contracts from
`context.get.tool_catalog`.

## Run this exact loop

1. Call `task_sys__list(status="terminal")`. For each newly terminal Task,
   call `task_sys__get`.
2. Call `demand_sys__get` with that Task's opaque Demand reference and judge
   the latest need, not the old Task objective.
3. Apply the IM delivery invariant below whenever the Demand has an
   `im.message.created` source. Use `demand_sys__complete` only when the latest
   need and its required delivery are both satisfied, and cite Task,
   deliverable, and reply evidence. Otherwise use `demand_sys__cancel`,
   `demand_sys__revise`, or deliberately leave the Demand live. Do not
   automatically complete or cancel a Demand from Task status.
4. Call `task_sys__list(status="active")`. If one Task is active, stop; native
   Goal execution owns that slot.
5. Call `demand_sys__list(status="live")`.
6. If no live Demand exists, stop without creating a Task.
7. Compare every live Demand by urgency, user commitment, blocked downstream
   work, continuity, evidence readiness, and staleness.
8. When any live Demand exists and the slot is empty, select exactly one.
   Reread it with `demand_sys__get`; choosing none is not a steady-state result.
9. Write a self-contained objective with an observable completion result,
   required user-facing delivery, and the rule to call native `update_goal`
   with `complete` only after delivery. The Goal must not reconcile the Demand
   or select later work. For an IM-origin Demand, construct the objective using
   the exact source and verification rules below.
10. Call `task_sys__create` once with only `demand_ref`, `objective`, and
    `selection_reason`.

## IM delivery invariant

When a Demand's `source_refs` contains `type="im.message.created"`:

1. Extract the exact source `message_id` and call `message__get` to reread the
   originating request. Never infer its content or sender from Task text.
2. The Task objective must name the exact source message_id. It must require
   `message__send` with `reply_to` equal to that source message_id, retain the
   returned reply message id, call `message__get` for that reply, and verify
   its content and `reply_to` before native `update_goal(status="complete")`.
   A Codex final answer is not a Central IM delivery.
3. During terminal reconciliation, reread the source with `message__get`, use
   `message__conversation` for its sender to locate the Actor-authored reply,
   and verify the complete durable reply row it returns. If that projection
   does not contain complete content and `reply_to`, reread the candidate with
   `message__get`. A matching durable reply must have `reply_to` equal to the
   source message_id and content that satisfies the latest Demand.
4. Task and native Goal completion do not prove delivery. If no matching
   durable reply exists, do not call `demand_sys__complete`; leave the Demand
   live. When the terminal Task omitted delivery, use `demand_sys__revise` to
   make the remaining delivery explicit so a new Task can bind the refreshed
   Demand reference.
5. A completed IM-origin Demand must cite both the terminal Task and the exact
   reply as evidence. Use an `im.message.reply` evidence ref with `id` equal to
   the reply message id and `key` equal to `reply_to:<source message_id>`.

Do not call `create_goal` or `update_goal` in this orchestration turn. Task Sys
binds the objective to the persistent main-thread native Goal after Task
creation.
