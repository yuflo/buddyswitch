# Modular Monolith Migration Execution Governance

> Historical process record: S0–S7 are accepted and the program is complete.
> This file grants no current execution authority.

## 1. Purpose

This document prevents two failure modes:

1. giving an executor the entire architecture migration as one task;
2. allowing locally reasonable changes to drift away from the accepted target.

It defines the handoff unit, stage authority, checkpoint format, change
control, pause/restart behavior, and acceptance ownership.

Root `AGENTS.md` and `$buddyswitch-testing` own durable repository and testing
policy. This document is the active execution-plan owner for this migration
only; it projects those durable rules into S0–S7 and does not supersede them.

`00-coordination-hub.md` owns how the coordinating Codex session and
independent execution sessions interact. This document owns stage execution
governance within that model.

## 2. Roles

### Migration lead

Owns:

- roadmap and stage boundaries;
- stage readiness;
- stage outcome, architecture boundary, protected contracts and classified
  write scope;
- shared write-surface allocation;
- architecture decisions;
- residue ownership;
- final stage acceptance.

The migration lead is the coordinating session. Only it updates master
program truth.

Does not:

- rewrite a stage implementation plan while its executor is working without
  moving the stage to `REPLANNING`;
- accept a stage from task completion alone;
- authorize compatibility residue for convenience.

### Stage executor

Owns:

- current-source trace;
- the bounded local implementation plan and execution order;
- dynamic test-target discovery and command construction through the current
  public runner;
- RED/GREEN/refactor loop;
- allowed stage files;
- diagnosis and owner-correct repair inside classified scope;
- evidence and cleanup;
- progress updates and restart point.

Does not:

- modify another stage's owner;
- reinterpret architecture from old memos;
- create a new framework to avoid a local direct change;
- weaken proof or preserve an old path;
- declare the stage accepted.

The executor submits proposed finding/residue/acceptance changes; it never
edits their master status.

The executor is not a command transcription worker. A packet may provide
known targets and a suggested sequence, but repository facts, the current
runner and `$buddyswitch-testing` own target validity and exact execution.

### Integration owner

Owns low-frequency shared surfaces:

- application composition root;
- frozen foundation host contracts;
- shared architecture tests;
- final merge ordering for parallel module lanes.

This role may be the migration lead, but its writes remain explicit.

### Reviewer

Reviews:

- stage adherence before code style;
- one semantic owner;
- product behavior preservation;
- old-path absence;
- evidence quality and residual risk.

## 3. Document authority

When documents conflict, use:

```text
root AGENTS.md
  > executable current contracts and tests
    > docs/arch current truth
      > accepted target architecture decision
        > migration roadmap
          > current stage charter
            > current stage implementation plan
              > historical memos
```

The target architecture and roadmap may describe future truth. They do not
override current runtime facts until a stage cuts over that owner.

## 4. Handoff unit

One executor receives one stage or one explicitly independent S4 component
lane.

The handoff begins with this exact summary:

```text
Stage ID and state:
Acceptance sentence:
Owning module/capability:
Source commit and local diff:
Allowed write roots:
Shared files requiring integration-owner approval:
Protected consumer contracts:
First RED/preservation claim and known direct proof:
Old paths that must disappear:
Forbidden scope:
Stop conditions:
Next checkpoint:
```

The handoff links the source documents; it does not paste them all into a
single prompt.

## 5. READY review

READY is an evidence decision, not a judgment that the packet is detailed
enough or safe to stop. The migration lead completes the review before an
independent executor receives the packet.

Required evidence:

| Gate | Required proof |
|---|---|
| Current truth | every affected preservation group the packet will later rely on has run before mutation; every failure is explained and owner-classified |
| Boundary contract | material positive, negative, correspondence, mutation and cleanup claims are proved or explicitly inapplicable |
| Mechanism | packaging, filesystem, process or framework assumptions have an isolated representative final-topology probe |
| Declared environment | the build, test and runtime environment is reproducible from committed declarations; no ad hoc package or hidden local mutation is required |
| Execution order | every environment-consuming proof follows the source mutation and rebuild/install/activate/verify step that makes its runtime current |
| Identity | every proof records source/diff, canonical command with explicit targets, fixture/environment, result, cleanup and residual risk; any custom digest defines its exact path set, exclusions, ordering and byte framing |
| Handoff | no semantic owner, public/foundation contract, state identity or boundary decision remains for the executor to infer; suggested commands are checked against current runner semantics or explicitly left to executor discovery |

For every protected consumer interface, READY evidence is assertion-level:

- a test filename, test count, suite label or prior GREEN is not proof unless
  the reviewed assertions exercise the protected observable result;
- a stable CLI/process/transport path requires at least one successful
  terminal request and its material rejection/error mapping through the real
  entrypoint and transport owner;
- if the existing proof cannot detect that loop, the required behavior-test
  write is classified before scope freezes;
- the proof-gap audit precedes the final scope ledger. Scope completeness may
  not be inferred from an architecture-only consumer inventory.

The ordinary READY questions still apply:

- Can the executor explain the product/host outcome in one sentence?
- Is every affected current consumer named across direct imports, literal
  paths, data-driven IDs, generated module/path names, directory discovery,
  activation-dependent subprocesses and package/test projections?
- Do generic proofs derive expected topology from their semantic owner or
  explicit composition instead of accumulating product-specific exceptions?
- Does each new contract have one owner?
- Does the entry proof match the change intent: an attributable RED for new or
  repaired behavior, or an identity-valid current GREEN for a
  behavior-preserving refactor? A structural refactor must not manufacture a
  RED merely to make the future topology fail against the current topology.
- Is every removal target explicit?
- Can the stage merge without a later stage repairing its runtime truth?
- Are shared files and their integration owner named?
- Are omitted checks justified?

A planned test, future implementation proof, stop condition or happy-path tool
spike is not pre-READY evidence for an unresolved boundary. Risks may cross
READY only when they are private implementation choices or implementation
defects detectable by the frozen proof. External/protected uncertainty needs
its named Protected decision. An unresolved architecture or boundary
assumption keeps the stage `PROPOSED`.

Changes to source, build declaration, boundary contract, representative
topology or affected preservation set invalidate the relevant evidence and
return the packet to READY review.

## 6. Checkpoint cadence

Checkpoints occur:

- after current-source trace;
- after RED or the behavior-preserving refactor baseline;
- after each coherent GREEN block;
- before deleting the old path;
- after residue removal;
- before acceptance.

Each update uses:

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

Avoid narrative diaries. Record only information needed to review, pause, or
resume the stage.

## 7. Stage scope ledger

The implementation plan classifies every touched file:

| Class | Meaning |
|---|---|
| OWNER | lives under the stage's product/capability root |
| CONSUMER | must change to call the new owner |
| HOST CONTRACT | stable typed boundary owned by a foundation host |
| COMPOSITION | low-frequency application assembly |
| PROOF | tests, residue checks, acceptance evidence |
| CURRENT DOC | current architecture/guidance changed by executable truth |
| UNRELATED | forbidden |

An unclassified touched file stops work until classified.

## 8. Change control

### Local implementation discovery

The executor may resolve implementation and execution details without
replanning when:

- the owner and public effect do not change;
- no new dependency direction appears;
- no shared host contract changes;
- no additional old path is created;
- every write remains inside classified scope;
- proof breadth is preserved or increased.

Record the choice in the stage plan.

This authority includes correcting a mechanically invalid packet instruction
when there is one repository-proved equivalent. Examples include replacing a
test-parent directory with its one valid tier root, correcting an obsolete
file path after an authorized move, or reordering a verification command
behind an already accepted activation gate. The executor records the original
instruction, repository authority, correction and unchanged claim. It does
not stop merely because the coordinating packet contained the invalid local
instruction.

Stop and request replanning when equivalence is ambiguous, the correction
narrows proof, changes product semantics, requires a new write class, changes
a protected contract or state, or crosses a stage/lane boundary.

### Stage-affecting discovery

Move to `REPLANNING` when:

- the semantic owner differs from the charter;
- a public contract must change;
- a foundation contract needs a new concept;
- persisted state identity or schema changes;
- another stage's files become required;
- the protected consumer contract cannot be preserved;
- a compatibility period appears necessary.

The migration lead updates the charter or roadmap before code resumes.

### Specification invalidation and loop breaker

Stop conditions contain damage; they do not make a packet READY.

An invalid local instruction with one mechanically provable equivalent is not
a specification invalidation; use the local execution authority above.

When execution contradicts the READY outcome, boundary, protected contract,
classified write scope or accepted mechanism:

1. stop and permanently retire that packet;
2. move the stage to `REPLANNING`;
3. record the root cause and the missing pre-READY proof;
4. restate the invariant and rerun the complete affected boundary preflight;
5. issue no successor packet until the new design and evidence are accepted.

If a successor repair for the same boundary is contradicted again, another
patch-on-patch packet is forbidden. Reopen the boundary architecture, compare
alternatives, obtain maintainer approval and prove the selected mechanism end
to end before writing an implementation plan. There is no automatic third
repair packet.

### Protected-mode discovery

Stop immediately if the work uncovers:

- a real external API obligation;
- irreversible user-data migration;
- security, privacy, permission, payment, or release constraint;
- an external consumer of an internal path proposed for deletion.

Protected coexistence requires its own bounded plan and removal trigger. It is
never inferred.

## 9. Drift review

At every PR or merge checkpoint, run this conceptual diff:

```text
accepted stage outcome
vs.
current diff behavior
vs.
remaining old path
```

Drift indicators:

- new product behavior in a structural stage;
- a generic abstraction with one speculative consumer;
- product names in foundation;
- application composition importing module private code;
- module code outside its physical owner;
- directory scanning for product activation;
- state identity inferred from path;
- duplicate old/new tests;
- new fallback or error suppression;
- broad changes justified only as “cleanup.”

Any indicator needs removal or an accepted decision-log entry before
acceptance.

## 10. Parallel work governance

Parallel lanes must publish:

- owned root;
- shared files;
- integration order;
- base commit;
- expected composition-root edit;
- tests requiring exclusive resources.

Rules:

- one lane never edits another lane's private root;
- one integration owner serializes composition-root updates;
- shared host contracts are frozen during a wave;
- architecture tests are changed by their named owner;
- a lane rebases before final acceptance and re-runs affected proof;
- resource-owning tests use the repository's existing locking and cleanup
  policy.

## 11. Pause and resume

Before pausing, record:

```text
last accepted checkpoint
current commit/diff
running or residual resources
test run ids and results
known failing proof
next exact command/action
decision needed
```

Resume begins by:

1. confirming repository identity;
2. confirming the declared dependency/runtime environment is current;
3. confirming no external stage changed the owner/contract;
4. diagnosing every unresolved failure, timeout, flake or residue signal;
5. re-running the nearest completed proof only after its owning diagnosis and
   any required rebuild/install/activate/verify step;
6. updating the stage plan if facts changed.

Do not reconstruct state from chat history alone.

## 12. Stage acceptance

The executor submits evidence using `stage-acceptance-template.md`.

The migration lead verifies:

- Product;
- Contract;
- Architecture;
- Replacement;
- Operations;
- declared dependency/runtime reproducibility;
- complete failure, timeout, flake and residue history since candidate freeze,
  with an owning disposition for every signal;
- process/resource identity captured before cleanup removes its attribution;
- documentation current truth;
- residue register closure.

A later pass never erases an unresolved contrary signal. Material undeclared
environment mutation or unresolved failure history rejects acceptance.

Only the migration lead changes the ledger state to `ACCEPTED`.

## 13. No-dump rule

An executor must never receive an instruction like:

> Implement S1 through S7 according to all architecture memos.

The correct handoff is:

> Execute S1 only. Here is its acceptance sentence, source identity, charter,
> exact implementation plan, allowed scope, and relevant residue rows. Stop at
> the S1 acceptance gate.

This rule is itself part of migration acceptance.
