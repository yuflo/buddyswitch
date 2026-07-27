---
name: demand-orchestration
description: Reconcile newly terminal Tasks against their latest Demands and fill the single empty Task slot from the complete current live Demand pool.
---

# Demand orchestration

This Skill runs only in an independent parent Demand-orchestration turn. It
owns Actor judgment between the canonical Demand pool and one native-Goal Task
slot. Task completion is evidence, not Demand completion. Demand and Task
lifecycles remain decoupled.

Use native BuddySwitch env MCP tools. Read exact contracts from
`context.get.tool_catalog`.

Do not call `create_goal` or `update_goal` in this turn. Task Sys owns Goal
reconciliation after Task creation, and Task Goal work owns Goal completion.

## Reconcile newly terminal Tasks

For every newly terminal Task:

1. Read the exact Task with `task_sys__get`.
2. Read its latest canonical Demand with `demand_sys__get`.
3. Verify actual deliverables and required user-facing delivery through their
   owning products. Task or Goal status alone is not proof.
4. Use `demand_sys__complete` only when the latest complete need is satisfied
   by exact durable evidence; otherwise deliberately leave the Demand live.
   Parent/Main never creates, revises, or cancels a Demand. Do not
   automatically complete a Demand from Task status.
5. After all terminal Task judgments, reread every live Demand before deciding
   whether later work should fill the empty Task slot.

## Fill the Task slot

1. Read active Tasks with `task_sys__list(status="active")` after terminal
   reconciliation.
2. If one Task is active, stop. If more than one is active, surface the
   invariant failure and create nothing.
3. If the slot is empty, call `demand_sys__list(state="live")` and read every
   candidate in full with `demand_sys__get`.
4. Compare only grounded facts: explicit urgency or deadline, user commitment,
   blocked downstream work, continuity, evidence readiness, and staleness. Do
   not invent priority, deadlines, dependencies, or commitments.
5. When live Demands exist, select at most one and state the decisive grounded
   comparison in `selection_reason`.
6. Convert that Demand into one Task-sized execution commitment using the
   exact runtime field contract of `task_sys__create`.
7. Call `task_sys__create` once and follow its feedback.

The Task objective must not reconcile the Demand or select later work. Native
Goal completion is allowed only after the objective's observable result,
durable user-facing delivery, evidence, and checks are complete.

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
   live so another Task can address the unmet delivery.
5. A completed IM-origin Demand must cite both the terminal Task and the exact
   reply as evidence. Use an `im.message.reply` evidence ref with `id` equal to
   the reply message id and `key` equal to `reply_to:<source message_id>`.

Task Sys binds the objective to the persistent main-thread native Goal after
Task creation.
