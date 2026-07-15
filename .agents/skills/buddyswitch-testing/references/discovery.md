# Dynamic Target Discovery

Use this reference whenever focused targets are not already explicit or when the
affected boundary is uncertain.

## Inputs

- current task claim and intent
- tracked modifications and deletions
- non-ignored untracked files
- current code, tests, contracts, fixtures, configuration, and runner constraints
- pre-existing unrelated worktree changes that must remain untouched

Repository facts are authoritative. Do not consult or create a persistent feature
catalog or source-to-test map.

## Discovery Ladder

1. **Name the claim.** State the behavior or contract that must be proved. A vague
   "all good" claim is not selectable.
2. **Read and partition working state.** Use `git status --short`, rename-aware diff,
   and the non-ignored untracked list. Separate task-related changes from unrelated
   existing changes without reverting either.
3. **Prefer changed exact tests.** New or modified tests are the highest-confidence
   candidates. A deleted test requires surviving equivalent proof or an explicit
   coverage decision.
4. **Trace live references.** Search current tests for changed public symbols,
   imports, commands, schemas, output text, contracts, fixtures, and direct callers.
   Use `rg` and current paths; do not infer from old names alone.
5. **Add direct boundaries only.** Include current owner and direct contract tests
   needed by the claim. Do not add neighbors because their directory names look
   related.
6. **Stop when sufficient.** Once exact behavior and direct affected boundaries are
   covered, stop searching and run the focused command from `AGENTS.md`.
7. **Escalate uncertainty.** If ownership or a shared boundary remains unresolved,
   state the uncertainty and enter MILESTONE. Never translate an empty search into
   success.

## Intent-Sensitive Discovery

### Behavior change or new behavior

Create or select the smallest exact test and observe intended RED before production
implementation. The same target supplies GREEN.

### Defect repair

Select the smallest regression that reproduces the escaped defect. A failure caused
by setup, import, or environment is not valid RED.

### Behavior-preserving refactor

Do not manufacture failure. Run current exact behavior tests before structural
changes, then rerun affected proof while refactoring.

### Test-only or runner-contract change

Start with changed tests or the current tests for the changed runner contract. A
change to execution semantics may require broader final acceptance, but it does not
justify broad runs between edits.

### Non-executable prose or artifact

Use document, link, schema, rendering, or other artifact-specific verification.
Executable evidence remains valid if executable state and its material environment
did not change.

## Batching and Exclusivity

- Batch compatible explicit targets when that removes startup overhead without
  widening resource ownership.
- Keep runner-declared exclusive targets separate so the exclusive interval remains
  narrow.
- Let the runner enforce compatibility, isolation, locks, cleanup, and target
  validity. Do not reproduce those rules here.

## Stop Conditions

Stop discovery and report a blocker or uncertainty when:

- no existing proof covers changed behavior and adding RED is outside the task
- the current runner cannot execute the required proof
- environment or dependency state prevents a meaningful result
- task scope cannot be separated safely from unrelated worktree changes

