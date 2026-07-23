---
name: demand-triage
description: Use only on an isolated Demand triage side to resolve one inbound fact against the actor's canonical Demand pool.
---

# demand-triage

## Boundary

This is a side-only judgment. Read the exact inbound fact in the turn prompt,
compare it with live Demands, and commit one decision through the thread-only
`demand_triage.resolve` tool before ending.

The ordinary tools on this side are intentionally limited to
`demand_sys__list`, `demand_sys__get`, `message__get`, and
`message__conversation`. Never create or mutate a Demand directly, create Task
work, send a Message directly, or defer semantic judgment to the parent.

## Choose exactly one decision

- `no_action_needed`: acknowledgement, FYI, duplicate delivery, or information with no unmet obligation.
- `handled`: the exact IM need can be answered immediately; provide `reply_content`. The resolver owns idempotent reply delivery and verification.
- `create`: a new independent unmet need.
- `merge_intake`: supplemental detail or constraint for the same live need.
- `revise`: the goal, boundary, or constraints of one live need changed.
- `cancel`: the source explicitly withdraws or invalidates one live need.

For `merge_intake`, `revise`, or `cancel`, reread the target and use its current
opaque `demand_ref`. For `create`, `merge_intake`, or `revise`, provide the
intended canonical `description` and `detail`. Always provide a concrete
`reason`.

Call `demand_triage.resolve` exactly once with all six schema fields:
`decision`, `reason`, `demand_ref`, `description`, `detail`, and
`reply_content`. Use `null` for fields that do not apply. Do not return a JSON
proposal in the final message; the resolver call is the commit.
