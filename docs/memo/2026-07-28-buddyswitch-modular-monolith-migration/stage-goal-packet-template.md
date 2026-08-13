# Stage Goal Packet Template

> Historical template: the S0–S7 migration program is complete. This file
> cannot create or grant current execution authority.

> This file is filled by the coordinating session only.
> An execution session receives one complete packet and no future-stage packet.

## 1. Copy-paste session request

```text
Create and pursue the following goal in this independent session:

[EXACT STAGE GOAL]

Use only the linked Stage Goal Packet and its governing repository
instructions. Do not begin another stage. When implementation and verification
finish, return the required execution result packet and stop; do not update the
master migration ledger or declare the stage accepted.
```

## 2. Packet identity

```text
Packet ID:
Stage:
Master state:
Prepared by:
Prepared date:
Source commit:
Tracked patch identity:
Non-ignored untracked identity:
Execution branch/worktree:
Predecessor acceptance:
```

Any custom patch or manifest digest must define the exact path set,
exclusions, ordering, byte framing and command used to reproduce it. Prefer a
commit/tree plus explicit diff when that already identifies the clean source.

## 3. Goal and acceptance

```text
Goal:
Acceptance sentence:
Consumer path:
Explicit non-goals:
```

## 4. Pre-READY evidence

```text
Complete affected preservation command/run identity:
Boundary positive proof:
Boundary negative proof:
Correspondence/mutation/cleanup proof or exact inapplicability:
Representative final-topology probe:
Protected consumer assertion inventory:
Real entrypoint/transport success and material failure probe:
Source/diff and material toolchain identity:
Declared dependency/build/test/runtime inputs:
Source-mutation -> rebuild/install/activate/verify -> proof order:
Cleanup:
Residual private implementation risk:
```

Every referenced proof must already exist. A planned executor RED does not
replace hub-owned preflight. If any semantic owner, public/foundation contract,
state identity, packaging boundary or selected mechanism remains undecided,
the packet is not READY.

Cross-session evidence reuse additionally requires the canonical public
command with explicit targets, material runtime/toolchain identity, result,
cleanup and contrary-signal disposition. A run ID, filename, suite label or
test count by itself is not reusable evidence.

For a protected CLI, process, socket or broker-backed contract, identify the
exact assertions that observe one terminal success and each material
rejection/error class. Test filenames, test counts and broad suite results are
insufficient. If those assertions do not exist, classify the owning
behavior-test write before freezing section 6.

## 5. Read order

1. root `AGENTS.md`;
2. `$buddyswitch-testing`;
3. target architecture;
4. migration roadmap and coordination hub;
5. current stage charter;
6. current stage implementation plan/checkpoints;
7. applicable decisions, findings and residue rows;
8. current executable contracts/tests/docs.

### Before acting

Durable authority: root `AGENTS.md` and `$buddyswitch-testing`. Active
migration-plan projection: `00-execution-governance.md`, D-037 and D-044.
Link any stage retrospective only as historical rationale.

- unresolved failure/timeout/flake/residue: diagnose and stop; a later pass
  does not erase it;
- undeclared dependency or hidden environment mutation: stop;
- `src/buddyswitch/**` mutation: rebuild/install/activate/verify before the
  next `./buddyswitch-test` command;
- resource cleanup: capture parent-known identity and stop the owner before
  deleting attribution;
- repeated branch-local lifecycle repair: inspect all terminal exits and
  relevant history before editing.

## 6. Allowed and forbidden scope

```text
OWNER:
CONSUMER:
HOST CONTRACT:
COMPOSITION:
PROOF:
CURRENT DOC:
SHARED/INTEGRATION OWNER:
UNRELATED DIRTY WORK TO PRESERVE:
FORBIDDEN:
```

No unclassified file may be modified.

## 7. Frozen decisions and behavior

```text
Decision IDs:
Protected contracts/data:
Success:
Failure:
Authority:
Persisted effect:
Restart/recovery:
Cleanup:
```

## 8. Execution sequence

Link checkpoint documents and state the required dependency order. For each
checkpoint name:

- intent-appropriate entry proof: attributable RED for changed/repaired
  behavior, or identity-valid current GREEN for a behavior-preserving
  refactor;
- exact files/disposition;
- declared environment and, after any `src/buddyswitch/**` mutation, the
  rebuild/install/activate/verify gate before another public-runner command;
- focused verification claim and known current direct targets;
- required checkpoint return;
- stop condition.

The packet fixes outcomes, boundaries, protected contracts, evidence classes
and required ordering. The executor owns exact target discovery, compatible
grouping and local command construction under `$buddyswitch-testing`.

## 9. Residue and replacement

```text
Owned residue IDs:
Exact old files/imports/registrations/assets/tests/docs:
Consumer replacement:
Absence checks:
```

## 10. Verification

Use only:

```bash
./buddyswitch-test focused <executor-selected current targets>
./buddyswitch-test full
```

The packet states when `full` is authorized. Known targets may be supplied as
review input, not as an unchangeable command transcript. The executor may
correct a mechanically invalid suggested target when the runner proves one
equivalent and proof breadth is unchanged; record the correction and
authority. It also names manual/real-Actor proof and resource cleanup where
material.

## 11. Stop and return early

Stop without broadening scope when:

- semantic owner or accepted decision is contradicted;
- another stage's owner is required;
- a public/foundation contract must change outside the packet;
- canonical persisted data must move;
- protected external behavior requires coexistence;
- a compatibility/fallback/second runtime appears necessary;
- unrelated dirty work overlaps required writes;
- direct proof cannot detect the claimed outcome.

Return the evidence and proposed replan. Do not repair outcome, architecture,
protected-contract, scope or ambiguous proof changes locally. A single
mechanically provable execution correction inside the accepted boundary is
executor-owned and does not retire the packet. If this is the second
substantive specification invalidation at the same boundary, state that
another patch-on-patch packet is forbidden and request architecture review.

## 12. Checkpoint update

```text
Packet / stage / checkpoint:
Source/diff identity:
Completed outcome:
Evidence:
Files changed:
Proposed residue changes:
Current risk:
Next exact action:
Stop/replan condition:
```

## 13. Final asynchronous return

```text
Packet ID and stage:
Source commit and exact final diff:
Completed checkpoints:
Changed/created/deleted files:
Focused/final commands and run IDs:
Declared dependency/runtime identity:
Every failure/timeout/flake/residue signal since candidate freeze:
Owning diagnosis and disposition for every signal:
Consumer-observed result:
Runtime/process/Actor identities:
Process/resource identity captured before cleanup deletion:
Cleanup/residual state:
Proposed residue closures/new residue:
Current docs changed:
Omitted checks and residual risk:
Stop/replan discoveries:
Proposed ACCEPTED / REJECTED:
```

Stop after returning this packet. Wait for the user to bring the result to the
coordinating session.
