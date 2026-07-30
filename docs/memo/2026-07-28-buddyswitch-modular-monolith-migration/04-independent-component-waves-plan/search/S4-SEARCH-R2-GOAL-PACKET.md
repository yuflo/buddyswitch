# S4 Search R2 Continuation Goal Packet

> Packet state: `READY`
> Packet ID: `BS-MM-S4-SEARCH-R2-20260730-01`
> Predecessor: `BS-MM-S4-SEARCH-R1-20260730-01` rejected and consumed

## Independent-task request

```text
Create and pursue this goal:

Execute BuddySwitch packet BS-MM-S4-SEARCH-R2-20260730-01 in the current
fea-tool worktree from the preparation checkpoint supplied by the
coordinating hub.

Read root AGENTS.md, the complete $buddyswitch-testing skill and routed
references, D-051, S4-SEARCH-R1-RETURN-REVIEW.md and
S4-SEARCH-R2-CONTINUATION-PLAN.md.

Preserve the existing dirty Search candidate. Do not roll it back, replay the
cutover, or treat the R1 no-collection result as a Search implementation
failure. Verify candidate and runtime identity, then resume at direct and
affected focused proof. Use current repository facts and the public runner to
select exact targets. The known valid replacement for the rejected module
test parent is src/buddyswitch/modules/search/tests/integration.

You own exact target discovery, compatible grouping, local command
construction, diagnosis and owner-correct repair inside the existing
classified scope. If a packet suggestion is mechanically invalid and the
runner proves one equivalent with unchanged proof breadth, correct it,
continue and record the correction. Stop only for identity mismatch,
ambiguous proof, reduced proof breadth, unclassified or cross-lane writes,
architecture/protected-contract change, unexplained failure, undeclared
environment mutation or cleanup residue.

After focused and affected proof pass, audit replacement and cleanup, freeze
the candidate and run FINAL. A failed FINAL must be diagnosed; repair only an
owner already inside classified scope, reprove exact and affected behavior,
reprovision first when package source changed, then freeze and run FINAL once
for the new candidate. Never blind-rerun an unchanged candidate.

Do not edit migration master truth, commit, push, change branches, start
another S4 lane, add compatibility or create a framework. Return the complete
R2 result packet and stop.
```

## Authority

The fixed authority is:

- acceptance sentence and protected behavior in
  `S4-SEARCH-R2-CONTINUATION-PLAN.md`;
- write classifications in `S4-SEARCH-OWNER-CONSUMER-MANIFEST.md`;
- architecture decisions D-039, D-040, D-044, D-049, D-050 and D-051;
- runtime and test policy in root `AGENTS.md` and
  `$buddyswitch-testing`.

The executor owns local execution mechanics inside that authority. Suggested
commands in R1 are historical inputs, not executable truth.

## Source handoff

```text
Preparation checkpoint:
  supplied by the coordinating hub after R2 documents are committed
Preserved candidate tracked patch:
  144a55b06bf89be3b2850baca89976dbeb61bf6ba3154a9467f5f87bbefbe059
Preserved candidate index:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
Preserved candidate untracked manifest:
  2f76f0d1c69a1289d87e8172859a6808344e935ae45b431c0877be30cd0641b1
Preserved candidate untracked count:
  13
```

Any product/test/current-architecture delta outside the R1 candidate and its
existing manifest stops execution. R2 coordinating documents themselves are
not product candidate writes.

## Verification boundary

Use only:

```bash
./buddyswitch-test focused <executor-selected current targets>
./buddyswitch-test full
```

`full` is authorized only for a frozen repository-wide Search lane acceptance
candidate. Exact target selection follows dynamic discovery; it is not copied
from the invalid R1 parent-directory command.

## Closure authority

The executor proposes `ACCEPTED` or `REJECTED`. Only the coordinating hub may
accept Search, update ledger/residue/decision truth, commit the candidate,
push it or authorize another S4 lane.
