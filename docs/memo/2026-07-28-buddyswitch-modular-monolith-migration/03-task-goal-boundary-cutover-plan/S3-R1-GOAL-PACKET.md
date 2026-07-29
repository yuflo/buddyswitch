# S3 R1 Task and Goal Cutover Completion Goal Packet

> Packet state: `READY`
> Packet ID: `BS-MM-S3-R1-20260730-01`

## 0. Copy-paste independent-task request

```text
Create and pursue this goal:

Execute BuddySwitch packet BS-MM-S3-R1-20260730-01 from the exact preparation
checkpoint supplied by the coordinating hub. This is a continuation of the
preserved, unaccepted S3 partial candidate; do not roll it back and do not
resume retired packet BS-MM-S3-20260729-01.

Read root AGENTS.md, the complete $buddyswitch-testing skill and routed
references, the current migration execution governance, then
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
03-task-goal-boundary-cutover-plan/README.md in its exact order.

First verify the preparation commit and every tracked/index/untracked
partial-candidate identity. The installed runtime is expected to be stale:
rebuild, non-editably install, activate and verify the current candidate
before any ./buddyswitch-test command. Capture the two specified existing
consumer failures as RED. Repair their generic ownership boundary without
adding Task-specific exceptions; close the three named proof-quality drifts;
finish the frozen D-045–D-048 Task/Goal cutover and four current architecture
documents; prove the complete affected path; run one single frozen full suite;
return the exact evidence packet; and stop.

Ordinary implementation defects may be fixed only inside the exact classified
candidate scope. Stop on a new required file, architecture/public-contract
change, data migration, unexplained failure, environment mutation, cleanup
residue or FINAL failure. Do not start S4, edit migration master truth, commit,
push, switch branches, rebase, add compatibility, or create a generic plugin,
DI, route or event framework.
```

## 1. Read order

1. root `AGENTS.md`;
2. `.agents/skills/buddyswitch-testing/SKILL.md` and every reference it routes
   for this execution;
3. `../00-execution-governance.md`, especially D-037, D-044 and D-049;
4. `../02-demand-component-pilot-plan/S2-DELIVERY-RETROSPECTIVE.md` as
   historical rationale only;
5. `S3-INITIAL-RETURN-REVIEW.md`;
6. `S3-R1-SOURCE-SNAPSHOT.md`;
7. `S3-R1-CONSUMER-AUDIT.md`;
8. `S3-BOUNDARY-DESIGN-AND-PREFLIGHT.md`;
9. `S3-R1-IMPLEMENTATION-PLAN.md`;
10. this Goal Packet;
11. `S3-R1-READY-REVIEW.md`.

The initial S3 source snapshot, manifest, plan, Goal Packet and READY review
remain historical inputs. When they conflict with an R1 document, R1 governs.

## 2. Identity

```text
Packet: BS-MM-S3-R1-20260730-01
Stage: S3 Task and Goal Boundary Cutover
Master state: READY — R1 COMPLETION
Prepared date: 2026-07-30
Preparation checkpoint: supplied by hub after coordinating-doc commit
Partial candidate base HEAD before preparation:
  1c99816c57196e47ddbff38bdd0d143bf5084e24
Tracked src/tests patch:
  b70c08475d5ecb0ebd641bd1ba4880905bd5375b237ad1f37ae753e80ae441eb
Index patch:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
Untracked src/tests path set:
  989ffcdf6b5c08190c19a991a8b33b5a7e534dd5ddfade46f909dc8594bcd658
Untracked src/tests path/content manifest:
  44c5c5359f780f127bbcd3a4f3520664db2bb2053c837a4b502b1ae06d5d82f4
Execution branch/worktree: current fea-tool worktree only
Predecessor packet: rejected and consumed
```

The hub launch message supplies the preparation commit. The executor verifies
that its delta is coordinating documents only and that the product-candidate
identity still matches this packet.

## 3. Authority

Allowed:

- all preserved candidate files classified in
  `S3-R1-CONSUMER-AUDIT.md`;
- the two newly classified process tests;
- the four exact current architecture documents;
- in-scope implementation repairs discovered by the frozen focused proof;
- declared build/install/activate/test operations.

Forbidden:

- any other path;
- migration master or packet document edits;
- S4 work;
- compatibility/fallback/dual owner;
- new product action, route or schema;
- generic plugin/container/bus/priority/discovery framework;
- data migration;
- Git commit/push/rebase/branch change.

## 4. Action-time gates

- The expected initial `RUNTIME_MISMATCH` requires reprovision; it does not
  authorize a public test.
- The two named current consumer failures are authorized RED only after
  activation verifies.
- Do not patch `task_sys` into another generic-test exception. Derive from the
  owning package/composition/registration.
- A later pass never erases a failure, timeout, flake or residue.
- No undeclared dependency or hidden environment mutation is acceptable.
- Every later package-source mutation requires another
  build/install/activate/verify boundary before testing.
- Preserve parent-known resource identity until the owner stops.
- No patch-on-patch repair: fix the semantic owner or return the finding.

## 5. Frozen architecture

R1 does not reconsider:

- Task-owned `DemandSelectionResolver`;
- application-injected Demand Public resolver;
- Demand-to-Task Public reads;
- exact daemon order;
- registration-owned Task command factory;
- exact Actor Console section contribution;
- application-injected active Task probe;
- Task-private Goal client constructed from generic instance facts;
- final Task physical paths and local tests.

## 6. Verification authority

The executor follows the exact sequence and minimum commands in
`S3-R1-IMPLEMENTATION-PLAN.md`.

Public test entrypoints are only:

```bash
./buddyswitch-test focused <file-or-nodeid>...
./buddyswitch-test full
```

`full` is authorized once, after the candidate and activation are frozen.
The executor may run additional focused targets only to own an in-scope
failure; all such attempts must be returned.

## 7. Replacement closure proposal

The executor may propose but not record closure of:

- `R-TASK-001`;
- Task portions of `R-FND-001/002/003/004/006/008/011/012`;
- Task portions of `R-DOC-002/003`.

Closure requires source-bound positive behavior and absence proof. The partial
candidate itself closes nothing.

## 8. Stop and return

On a stop condition, return once with the exact format in the implementation
plan. Do not wait for repeated turns and do not mark the goal blocked merely
because the coordinating hub must decide next authority.

On success, return the same complete packet and stop. The hub alone reviews,
commits, pushes and transitions S3.
