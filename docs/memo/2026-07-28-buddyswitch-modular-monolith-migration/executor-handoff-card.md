# Stage Executor Handoff Card

> Copy this card into the stage task. Replace every required field with an exact
> value and links. Do not attach future stage plans as active instructions.

## Mission

```text
Stage:
Current state:
Acceptance sentence:
Owning module/capability:
Source commit:
Exact dirty diff:
Implementation plan:
Live delivery rules:
Stage-specific historical rationale:
```

## Read in this order

1. root `AGENTS.md`;
2. `$buddyswitch-testing`;
3. target architecture design;
4. master roadmap;
5. execution governance;
6. current stage charter;
7. current stage implementation plan;
8. relevant decision and residue rows.

## Before acting

Durable authority: root `AGENTS.md` and `$buddyswitch-testing`. Active
migration-plan projection: `00-execution-governance.md`, D-037 and D-044.
A stage retrospective is historical rationale only.

- unresolved failure/timeout/flake/residue: diagnose and stop; a later pass
  does not erase it;
- undeclared dependency or hidden environment mutation: stop;
- `src/buddyswitch/**` mutation: rebuild/install/activate/verify before the
  next `./buddyswitch-test` command;
- resource cleanup: capture parent-known identity and stop the owner before
  deleting attribution;
- repeated branch-local lifecycle repair: inspect all terminal exits and
  relevant history before editing.

## Allowed work

```text
Owner roots:
Consumer files:
Shared files:
Shared-file owner:
Proof files:
Current docs:
```

Any touched file outside this list requires classification before editing.

## Frozen behavior

```text
Consumer action:
Success:
Failure:
Authority:
Persisted effect:
Restart/recovery:
Cleanup:
```

## First proof

```text
Exact RED or preservation target:
Public command:
Expected initial result:
Why this proof detects the stage outcome:
```

## Old paths to remove

```text
Residue IDs:
Files:
Imports/callers:
Registrations:
Tests/assets/docs:
Absence checks:
```

## Forbidden expansion

- no product feature change;
- no work from another stage;
- no compatibility alias/fallback/dual path;
- no speculative framework;
- no weakened proof;
- no unrelated cleanup.

Add charter-specific forbidden items below:

```text
Stage-specific forbidden scope:
```

## Stop immediately when

```text
semantic owner changes
accepted mechanism or READY specification is contradicted
direct proof cannot detect the claimed outcome
public/host contract must change outside the plan
persisted state identity/schema changes
another stage's owner is required
protected external behavior cannot be preserved
compatibility coexistence appears necessary
```

Move the ledger state to `REPLANNING` through the migration lead before
continuing.

## Checkpoint update

```text
Stage / checkpoint:
Source/diff identity:
Completed outcome:
Evidence:
Failure/timeout/flake/residue signals since candidate freeze and owning disposition:
Files changed:
Residue closed/discovered:
Declared dependency/runtime identity:
Process/resource identity captured before cleanup deletion:
Current risk:
Next exact action:
Stop/replan condition:
```

## Finish boundary

Stop after submitting the stage acceptance record. Do not begin the next stage
under this task or implementation plan.
