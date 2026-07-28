# Stage Acceptance Record Template

> This template is completed after implementation freezes. Replace every
> `[REQUIRED: ...]` field with exact evidence. Task completion alone is not
> acceptance.

## 1. Identity

```text
Stage:
Charter acceptance sentence:
Source commit:
Exact local diff:
Executor:
Migration lead:
Acceptance date:
Public test run IDs:
Real Actor/process identities where applicable:
```

## 2. Outcome

State whether the acceptance sentence is true.

Required form:

```text
ACCEPTED / REJECTED

Observed consumer action:
Owning path:
Observable result:
```

If rejected, name the owning stage checkpoint to reopen.

## 3. Product proof

| Claim | Consumer path | Evidence | Result |
|---|---|---|---|
| `[REQUIRED: exact behavior]` | `[REQUIRED: action -> owner -> result]` | `[REQUIRED: test/run/Actor]` | PASS / FAIL |

Registration/catalog presence alone is not product proof.

## 4. Contract proof

Record exact:

- success;
- failure;
- authority;
- persisted state effect;
- restart/recovery effect;
- terminal result;
- consumer-observed status.

Any contradiction rejects acceptance.

## 5. Architecture proof

Record:

- one semantic and physical owner;
- allowed imports;
- forbidden import absence;
- app composition boundary;
- foundation neutrality;
- Public dependency graph;
- state owner/schema/storage identity/write path;
- test ownership and single runner.

## 6. Replacement proof

List every stage residue ID:

| Residue ID | Old surface | Absence check | Consumer replacement | Status |
|---|---|---|---|---|
| `[REQUIRED]` | `[REQUIRED]` | `[REQUIRED]` | `[REQUIRED]` | CLOSED / OPEN |

Any OPEN live-path row rejects acceptance.

## 7. Operations proof

Record:

- startup behavior;
- failure attribution;
- restart/recovery;
- process/Actor/socket/lock/temp-root cleanup;
- logs/telemetry where applicable.

## 8. Current-document proof

List:

- current architecture docs changed;
- root guidance/stable paths changed;
- Skills/help/fixtures changed;
- historical memos intentionally unchanged.

Confirm no current surface teaches the retired path.

## 9. Verification commands

Record exact public commands and outcomes:

```text
command:
run ID:
source/diff identity:
tests/subtests:
duration:
result:
cleanup:
```

Include `git diff --check` and exact residue scans.

## 10. Omitted checks and residual risk

For each omission:

```text
omitted check:
why not material to this claim:
remaining risk:
next owner/action:
```

Do not describe a material blocked proof as low risk merely to accept the
stage.

## 11. Final review

- [ ] Product proof agrees with persisted and consumer-visible effects.
- [ ] Contract proof includes failure and authority.
- [ ] Architecture boundary is machine-proved.
- [ ] Every owned residue row is CLOSED.
- [ ] Operations and cleanup are clean.
- [ ] Current docs match executable truth.
- [ ] No unrelated work was staged or rewritten.
- [ ] Stage can stand without a later stage making it truthful.

## 12. Transition proposal

```text
Proposed ledger transition:
Authority:
Evidence links:
Next stage:
Next stage inputs:
```

Only the migration lead performs the ledger transition.
