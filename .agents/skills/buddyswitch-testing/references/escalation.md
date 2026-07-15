# Claim-Scoped Escalation

States describe the breadth of the claim already proved. They are not a checklist
of commands and do not require separate actors.

## State Table

| State | Enter when | Proof scope | Exit claim |
|---|---|---|---|
| RED | Behavior changes or a defect needs reproduction | Exact behavior/regression target | Failure is caused by the intended missing or broken behavior |
| GREEN | RED is understood, or a refactor baseline is required | Same exact target | Exact behavior passes cleanly |
| IMPACT | Direct owner or contract boundaries are known | Exact proof plus affected current boundaries | Local behavior and direct contracts pass |
| MILESTONE | A coherent cross-boundary block freezes or impact remains ambiguous | Relevant current broad gates only | Named cross-boundary claim passes without repository-wide acceptance |
| FINAL | Candidate is frozen for merge/release or repository-wide acceptance is explicit | Final command from `AGENTS.md` | Repository acceptance passes on the recorded identity |
| FIX_AFTER_FINAL | Executable/test/runner state changes after FINAL | Exact regression, affected focused targets, then one final run after freeze | New frozen candidate has local proof and one new FINAL result |

## Transition Rules

- One command may prove GREEN and IMPACT. Record both claims; do not rerun it.
- MILESTONE is not mandatory for a local change whose direct boundaries are proved.
- FINAL is not ordinary task completion. Enter it only for a frozen merge/release
  candidate, explicit repository-wide acceptance, or direct user request.
- Reviewer or controller identity does not cause a transition. Repository state and
  claim breadth do.
- Broaden only to the missing proof. Do not discard valid narrower evidence.

## Invalidation

- Relevant source, test, fixture, or contract changes invalidate affected focused
  evidence.
- Runner, dependency, or material environment changes invalidate evidence produced
  under the prior execution contract.
- Any executable/test/runner change after FINAL enters FIX_AFTER_FINAL.
- Read-only review and non-executable prose changes outside executable contracts do
  not invalidate otherwise equivalent evidence.

## Failure Path

A failure, flake, timeout, cleanup residual, or unexpected environment error is new
evidence. Stop escalation, diagnose the signal, and rerun only the probe needed to
confirm the diagnosis. An older pass does not override a newer failure.

