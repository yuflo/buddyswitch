---
name: demand-triage
description: Resolve one raw inbound fact against the complete current live Demand pool in an isolated triage side.
---

# Demand triage

## Boundary

This Skill runs only in an isolated Demand-triage side. The inbound fact is
source evidence, not a Demand. Do not create Task work, mutate Demand state
through ordinary Demand write tools, send a Message directly, or defer the
semantic judgment to the parent.

The ordinary tools on this side are intentionally limited to
`demand_sys__list`, `demand_sys__get`, `message__get`, and
`message__conversation`.

## Resolve one inbound

1. Read the exact inbound fact.
2. Call `demand_sys__list(state="live")`.
3. Before `create`, read every live Demand in full with `demand_sys__get`.
   Before targeting an existing Demand, reread that Demand in full.
4. Read the source Message when sender, conversation, exact wording, or reply
   relationship affects the judgment.
5. Choose exactly one resolution:
   - `no_action_needed`: no unmet obligation and no reply is required;
   - `handled`: one immediate reply fully satisfies the need;
   - `create`: a new independent unmet need;
   - `merge_intake`: compatible evidence, detail, or constraint for one
     existing Demand without changing its intended outcome;
   - `revise`: the intended outcome, boundary, binding constraint, delivery,
     or satisfaction meaning changed;
   - `cancel`: the need was explicitly withdrawn or invalidated.
6. Construct arguments using the exact runtime field descriptions for
   `demand_triage.resolve`.
7. Call `demand_triage.resolve` exactly once and follow its feedback.

Do not decide from compact summaries, Task text, or memory of an earlier
Demand revision. Do not emit an uncommitted proposal as the final answer.
