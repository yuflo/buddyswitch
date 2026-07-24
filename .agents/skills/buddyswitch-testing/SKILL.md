---
name: buddyswitch-testing
description: Use when changing, reviewing, or claiming completion for executable code, tests, runtime contracts, or test infrastructure in the BuddySwitch repository.
---

# BuddySwitch Testing

## Core Principle

Prove the current claim with the shortest sufficient verification. Discover test
targets from the repository as it exists now, reuse evidence while its identity is
valid, and broaden only when the claim or an unresolved boundary requires it.

This skill owns test-selection decisions. `AGENTS.md` owns the repository
verification contract, and the existing runner owns execution, isolation,
exclusivity, and cleanup.

## Decision Loop

1. Name the exact behavior, contract, or acceptance claim.
2. Classify the intent: behavior change, defect repair, refactor, test
   infrastructure, or non-executable change.
3. Inspect current modified and non-ignored untracked facts. Partition task-related
   changes from unrelated pre-existing worktree changes.
4. Read [discovery.md](references/discovery.md) and choose current exact and direct
   contract targets. Stop when the claim is covered.
5. Run the focused command published by `AGENTS.md`. Batch only compatible targets;
   isolate work the current runner marks exclusive.
6. Read [escalation.md](references/escalation.md) before widening the claim or
   entering final acceptance. States are breadth labels, not mandatory reruns.
7. Record evidence using [evidence.md](references/evidence.md). Reuse it when source,
   command, environment, result, and claim remain equivalent.
8. For review or handoff, apply [review.md](references/review.md). Review alone does
   not invalidate evidence.

## Intent Entry

| Intent | First proof |
|---|---|
| New or changed behavior | RED exact behavior test, then the same target GREEN |
| Defect repair | Smallest regression test fails for the escaped defect |
| Behavior-preserving refactor | Establish current behavior GREEN before editing |
| Test or runner change | Changed tests and current runner-contract tests |
| Non-executable prose/artifact | Artifact-specific verification; do not invent a test run |

## Terminal Truth Proof

For every new or changed mutating boundary, name and prove the complete terminal
path:

```text
owner effect -> public contract -> adapter/envelope
             -> client/tool interpretation -> consumer-observed status
```

Success proof requires the intended effect exactly once, a real success envelope,
success as interpreted by the client or tool, success at the final consumer, and no
attributable contradictory error. Failure proof requires the real envelope and
consumer to observe failure with no undeclared effect. If commit uncertainty is
intentional, expose it as an explicit contract state rather than an ordinary
failure. State convergence alone does not prove success.

## Non-Negotiable Rules

- Do not store feature names, source-to-test maps, fixed test directories, test
  counts, or elapsed-time thresholds in this skill.
- Do not add a test entry, runner mode, impact engine, evidence ledger, or second
  policy owner.
- Do not flatten success and error envelopes into one result shape, copy business
  fields from an error into a success-shaped result, or omit assertions for
  `ok`, status, and error semantics at the boundary under test.
- Fakes may control inputs and external dependencies; they must not author the
  success conclusion that the system under test is responsible for producing.
- A state transition does not require a new command when valid evidence already
  proves the broader claim.
- Ordinary local completion is not FINAL. Use the final command only for a frozen
  merge/release candidate, explicit repository-wide acceptance, or direct user
  request.
- After FINAL, run exact and affected focused proof for any executable change. Run
  final once again only after the candidate freezes.
- Failure, flake, timeout, or cleanup residue supersedes earlier passing evidence.
  Diagnose it; do not blind-rerun until a pass hides the signal.

## Example

An implementer records a passing focused command with complete identity. A reviewer
reads the change, makes no finding, and changes no files. Reuse that evidence; run no
command merely to make review "fresh." If the same candidate later enters FINAL,
run the final command once after all review-driven edits are complete.

## Common Mistakes

| Mistake | Required correction |
|---|---|
| "Fresh" means rerun after every handoff | Freshness is unchanged evidence identity, not actor identity |
| "Task complete" means run the full repository | Match verification breadth to the claim; FINAL is a separate claim |
| Every reviewer should prove independence with a broad run | Inspect existing evidence and run only finding-specific probes |
| Every breadth state needs its own command | Reuse one command across every state it actually proves |
| No direct test was found, so broad tests are enough | Add/select RED or state the unresolved boundary and escalate |
| The whole dirty worktree belongs to this task | Partition claim scope, but record the complete tested source identity |
| State converged, so the operation succeeded | Prove effect, envelope, client/tool status, consumer status, and attributable errors agree |

## Red Flags

- Running the final command "just in case"
- Repeating an unchanged command only because the actor or phase changed
- Selecting tests from a remembered module map instead of current repository facts
- Treating a failed or flaky run as invalid merely because an older pass exists
- Claiming success when target discovery found no proof
- Excusing a contradictory error because downstream state converged

Stop at a red flag and return to claim, discovery, or evidence analysis.

## Required Report

Report:

- claim and breadth state
- exact commands and targets actually run
- result and cleanup/residual state
- evidence identity and whether earlier evidence was reused
- residual risk, ambiguity, or blocker
