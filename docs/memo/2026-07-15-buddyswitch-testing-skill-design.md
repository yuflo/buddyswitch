# BuddySwitch Testing Skill Design

Interactive design artifact: [open the Shape HTML](./2026-07-15-buddyswitch-testing-skill-design.html)

## Decision

Deploy `buddyswitch-testing` as a repository-local Codex skill, but keep its logic
independent from BuddySwitch product evolution.

The stable ownership split is:

- `AGENTS.md`: triggers the skill and publishes the repository verification
  contract: focused command, final command, authoritative test surface, and runner
  ownership of isolation/exclusivity.
- `.agents/skills/buddyswitch-testing/SKILL.md`: claim-scoped escalation, dynamic
  target discovery, evidence reuse/invalidation, and reviewer behavior.
- Current repository facts: the working diff, untracked files, code references,
  tests, contracts, and runner constraints inspected for each task.
- `./buddyswitch-test`: execution only; retain `focused` and `full` as its public
  modes.

The skill must not contain feature names, source-to-test mappings, fixed test
directories, current test counts, or elapsed-time thresholds. Product features,
modules, and tests can be added, removed, or renamed without editing the skill.

Generic Superpowers guidance retains RED/GREEN and evidence-before-claims
discipline. The repository skill specializes only the sufficient verification
scope for the current claim; generic completion and review rules must not silently
promote focused evidence to a repository-wide `full` run.

## Proposed Shape

```text
.agents/skills/buddyswitch-testing/
|-- SKILL.md
|-- agents/
|   `-- openai.yaml
`-- references/
    |-- discovery.md
    |-- escalation.md
    |-- evidence.md
    `-- review.md
```

`discovery.md` defines a stable discovery ladder rather than a topology snapshot:

1. Name the exact behavioral claim.
2. Inspect modified and untracked source, tests, configuration, and contracts;
   partition task-related changes from pre-existing unrelated worktree changes.
3. Prefer new or changed exact tests.
4. Search current tests for changed public symbols, commands, contracts, and direct
   callers.
5. Stop as soon as the current claim and direct boundaries are covered; expand only
   across unresolved current boundaries.
6. Use the current runner's compatibility and exclusivity rules when batching.

Entry is intent-sensitive: behavior changes and defects require RED; a pure refactor
first establishes a passing behavior baseline and then proceeds through affected
proof. Deleted tests require a surviving proof or an explicit coverage decision.

The escalation states remain:

`RED -> GREEN -> IMPACT -> MILESTONE -> FINAL`

These are claim-breadth states, not mandatory test runs. A command may satisfy more
than one state, valid evidence is reused across transitions, and ordinary local
work does not enter MILESTONE or FINAL without the corresponding broader claim.

`FIX_AFTER_FINAL` handles executable changes after final acceptance. It runs exact
and affected focused proof first, then runs `full` once after the repository state
freezes again.

## Maintenance Boundary

These changes must not require a skill edit:

- new or deleted product features
- module or test renames
- new tests or growth of the existing test tree
- changed test counts and execution durations
- new current contracts discoverable from code and tests

Only a change to the repository verification protocol itself may require an edit,
such as replacing the public runner, changing `focused/full` semantics, or changing
the evidence identity contract.

## Acceptance

The implementation is accepted when pressure scenarios prove that:

1. A future module unknown when the skill was written is verified without editing
   the skill.
2. Renamed source and tests are found from the current diff and current references.
3. New or modified exact tests are selected before broader owner tests.
4. Missing or ambiguous coverage causes a RED test or explicit escalation, not a
   guessed success claim.
5. Compatible targets are batched and currently exclusive targets are isolated.
6. Reviewers reuse identity-valid evidence and run finding-specific probes only.
7. `full` runs once for frozen merge/release or explicit repository-wide acceptance.
8. A post-final fix does not cause repeated full runs between edits.
9. Generic TDD and verification skills keep their discipline without overriding
   repository-specific scope.
10. The public test surface remains exactly `focused` and `full`.
11. Pure refactors establish a behavior baseline without manufacturing a failing
    test.
12. Pre-existing unrelated worktree changes are not silently pulled into the task
    claim, while the evidence identity still records the tracked patch and all
    non-ignored untracked files visible to the test command.
13. Discovery stops when the claim is covered, and a state transition never repeats
    an equivalent command only to mark progress.

The HTML contains the complete ownership model, dynamic discovery ladder, state
machine, evidence schema, maintenance boundary, pressure scenarios, review passes,
implementation sequence, and source references.
