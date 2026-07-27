---
name: demand-triage
description: Resolve one raw inbound fact against the Actor's complete canonical Demand context in an isolated triage side.
---

# Demand triage

## Boundary

This Skill runs only in an isolated Demand-triage side. The inbound fact is
source evidence, not yet a Demand. Complete the semantic judgment here. Do not
mutate Demand state through ordinary Demand write tools, send a Message
directly, or defer judgment to another thread.

The ordinary tools on this side are intentionally limited to
`demand_sys__list`, `demand_sys__get`, `message__get`, and
`message__conversation`.

## Judge one inbound

1. Read the exact inbound fact.
2. When the source is an IM Message, read that exact source Message with
   `message__get`, then read the latest direct conversation with
   `message__conversation` and a fixed `limit` of `20`.
3. Call `demand_sys__list(state="all")` so both live and terminal Demands can
   be referenced correctly.
4. Resolve the referenced acceptance unit before choosing an effect. An
   acceptance unit is the result and delivery grouping the user currently asks
   to accept as one outcome. Determine whether the inbound refers to one
   current live Demand, one terminal Demand, or a genuinely new independently
   requested result.
5. Reread every plausible target in full with `demand_sys__get`. Before
   `create`, reread every live Demand in full to rule out a duplicate
   acceptance unit. For a terminal correction, reread that terminal Demand in
   full before creating the correction Demand.
6. Apply this evidence precedence:
   - the explicit current user statement of the relationship and
     user-requested grouping outrank an earlier boundary inferred or written
     by the model or a Demand;
   - “same deliverable”, “supplement”, “continue”, or equivalent wording is
     strong evidence of one acceptance unit. A compatible addition to that
     result is `merge_intake`; a change to what that same result must mean is
     `revise`;
   - “independent deliverable”, “separate acceptance”, or equivalent wording
     is strong evidence of a new acceptance unit and `create`;
   - technical separability is not product independence. Being implementable,
     testable, scheduled, canceled, or delivered in a separate step does not by
     itself create a new acceptance unit when the user groups the addition into
     the same deliverable;
   - an earlier request for an Actor-proposed future improvement governs that
     future Actor proposal. It does not reclassify a later explicit current user
     addition to the same deliverable as the proposed independent improvement;
   - use `create` only when the current user requests a distinct result or
     delivery that stands alone and has not been grouped into an existing
     result;
   - a terminal Demand is immutable. A new defect, correction, or follow-up
     that remains unmet becomes a new correction Demand whose canonical text
     names the prior result being corrected. Never target the closest unrelated
     live Demand merely because the actual referent is terminal.
7. First determine whether continuing work remains, then choose exactly one
   resolution:
   - `no_action_needed`: no unmet obligation and no reply is required;
   - `handled`: one immediate reply fully satisfies the need;
   - `create`: a new independently acceptable unmet result;
   - `merge_intake`: compatible evidence, detail, or constraint added to the
     same intended result without changing its acceptance unit;
   - `revise`: the same result remains the acceptance unit, but its outcome,
     boundary, binding constraint, delivery, or satisfaction meaning changes;
   - `cancel`: the explicit current user statement withdraws or invalidates
     one live Demand.
8. Make the `reason` cite the observed relationship and acceptance-unit
   evidence rather than restating the chosen enum. Construct the complete
   post-resolution canonical description and detail using the exact runtime
   field descriptions for
   `demand_triage.resolve`.
9. Call `demand_triage.resolve` exactly once and follow stale-reference
   feedback. Do not return an uncommitted proposal.

## Counterexamples

**Same-deliverable supplement:** Adding a compatible field to one existing
deliverable is `merge_intake`, not `create` merely because the field could be
implemented or tested later, or because an earlier Demand requested a future
Actor-proposed improvement.

**Independent deliverable:** A separately accepted and canceled
library, report, or tool is `create`, not `merge_intake` merely because it is
related to the same project.

**Terminal correction:** A defect or change to a terminal result creates a
correction Demand naming that result; it never revises an unrelated live
Demand.

Do not decide from compact summaries, Task text, or memory of an earlier
Demand revision. Do not emit an uncommitted proposal as the final answer.
