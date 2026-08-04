# Verification Responsibilities

These are responsibilities, not required agent counts. One actor may hold several
roles, and adding actors does not create new test obligations.

## Implementer

- Name the behavior and claim before selecting commands.
- Establish RED or refactor baseline as appropriate.
- Run exact and affected focused proof.
- Record evidence identity, result, and residual risk.

## Reviewer

- Inspect the claim, diff, target selection, result, and evidence identity.
- Reuse identity-valid evidence when review changes no repository state.
- Run a finding-specific probe when a suspected issue needs evidence.
- If the review needs a broader claim, run only the missing breadth.
- Do not rerun focused or final verification merely to demonstrate independence.
- For process-lifecycle proof, require a parent-known real process identity;
  reject child-authored PID/timing markers as the sole observation boundary.
- Require the owning controller to stop the process before deleting its root,
  identity file, socket, or other attribution state.
- Before adding another cleanup call to one return/exception branch, inspect
  every terminal exit and relevant current history for the same invariant;
  repair the lifecycle owner instead of stacking branch-local patches.
- For a destructive two-phase boundary such as discover/plan then execute,
  require the effect owner to revalidate safety at execution time. Proof must
  change the relevant path or ownership state between the phases and assert the
  real external effect and reported result; planner rejection alone does not
  prove executor safety.

## Controller

- Confirm all review-driven executable changes are complete before FINAL.
- Reuse valid implementer and reviewer evidence for narrower claims.
- Run the final command once on the frozen candidate when merge/release or explicit
  repository-wide acceptance is required.
- If FINAL is invalidated, keep repair in focused scope and return to one final run
  only after the candidate freezes again.

## Runner

- Own target validation, environment isolation, exclusivity, cleanup, and exit
  status.
- Runner output is evidence, not a scope-selection policy.

## Handoff Checklist

Provide the next actor with:

- exact claim and breadth state
- changed behavior and direct boundaries
- canonical commands and targets already run
- source/environment identity and clean result
- every contrary signal since freeze, its owning diagnosis, and disposition
- process/resource identity captured before destructive cleanup where material
- findings, residual risk, and any missing proof

Review or handoff without repository changes does not make evidence stale.
