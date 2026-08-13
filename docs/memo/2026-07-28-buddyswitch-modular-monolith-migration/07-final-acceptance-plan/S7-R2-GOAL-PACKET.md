# S7 R2 Final System Acceptance Goal Packet

## 1. Copy-paste session request

```text
Create and pursue the following goal in this independent session:

Prove on the frozen BuddySwitch R2 candidate that Product, Contract,
Architecture, Replacement and Operations evidence agree that the packaged
explicit modular monolith and narrow RoleHost are the only live architecture.
This is validation-only: do not edit any repository or runtime file. A
material defect must be returned with its semantic owner/originating stage;
do not repair it inside S7.

Use only
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
07-final-acceptance-plan/S7-R2-GOAL-PACKET.md
and its governing repository instructions. Execute the linked S7 plan, return
the required result packet, and stop. Do not resume R1, update master migration
truth, declare S7 accepted, commit, push or begin unrelated work.
```

## 2. Packet identity

```text
Packet ID:           BS-MM-S7-FINAL-R2-20260813-01
Stage:               S7 / final system acceptance
Master state:        S0–S6 ACCEPTED; S7 READY — R2 ONLY
Candidate checkpoint:7efd2a038e4604b0c3a20c8fb678980638113a2e
Execution branch:    fea-tool
Execution worktree:  /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
Predecessor:         S7 R1 rejected/consumed; S3 guidance repair accepted
```

The commit carrying this R2 packet may be newer than the candidate checkpoint
only through `docs/memo/**`. Before execution, prove HEAD equals
`origin/fea-tool`, the worktree is clean, and no executable/runtime input
changed after `7efd2a0…`. Any other delta rejects admission.

## 3. Goal and acceptance

> Product, Contract, Architecture, Replacement and Operations evidence agree
> that the packaged explicit modular monolith and narrow RoleHost are the only
> live BuddySwitch architecture.

R2 specifically proves that root/current guidance now agrees with the current
`task_sys` Tool and canonical Task object path while all executable product
and operational behavior remains intact.

Non-goals:

- no feature, refactor, repair, test edit or documentation edit;
- no runtime reprovision or dependency install;
- no migration-truth update, commit, push or next-stage work.

## 4. Mandatory read order

1. root `AGENTS.md`;
2. `.agents/skills/buddyswitch-testing/SKILL.md` completely;
3. `S7-R1-RETURN-REVIEW.md`;
4. `../03-task-goal-boundary-cutover-plan/S3-DOCUMENTATION-REPAIR-ACCEPTANCE.md`;
5. `S7-R2-SOURCE-AND-RESIDUE-SNAPSHOT.md`;
6. `S7-IMPLEMENTATION-PLAN.md` and `S7-R2-READY-REVIEW.md`;
7. current `docs/arch/**`, root/current guidance, D-078/D-079 and R-DOC-005;
8. current executable contracts/tests.

Repository facts and the current runner outrank examples. Do not use system
shell variables such as `path`, `PATH`, `HOME` or `CODEX_HOME` as local probe
variables.

## 5. Authority boundary

```text
OWNER / CONSUMER / HOST / COMPOSITION / CURRENT DOC: READ ONLY
PROOF: execute existing tests through ./buddyswitch-test only
MASTER TRUTH: READ ONLY
RUNTIME/USER STATE: runner-owned temporary effects only
```

Every repository write is forbidden. Do not stage, restore, clean, delete,
reprovision, patch or use an alternate test entry. Do not delete unrelated or
ignored state merely for tidiness.

## 6. Pre-READY evidence

```text
S3 exact replacement:  90a672c1176049428c05db2faa3d8b4f
S3 affected:           9ccc06e6baa34221a61c2fef85907848
architecture/package:  458b7eb164544f7da8b2ef45b52a2148
R1 behavior baseline:  c43014696e8b473c93e804ff73a0a408
runtime source:         28cbef6f68c12b9a9cdddbff94b326eb8b83453f475f1a74f62642cdccc64f38
runtime distribution:   b16a15a225b592414e1fcf89347f2f2fc00d5a32750f56d4359a2c51adebf62f
```

## 7. Execution sequence

1. Admit the exact clean upstream candidate and canonical runtime/toolchain.
2. Rediscover and run one focused architecture/distribution/activation group
   equivalent in breadth to:

   ```text
   tests/unit/architecture
   tests/process/package/test_distribution_install.py
   tests/process/package/test_runtime_activation.py
   ```

3. Audit root/current guidance for the R1 defect and neighboring retired
   Task guidance. Prove current `task_sys` and canonical Task state facts.
4. Recheck clean source/runtime/resource identity and freeze the candidate.
5. Run exactly one `./buddyswitch-test full`.
6. Audit terminal process/socket/lock/temp cleanup and all five proof classes.
7. Return the result packet and stop.

No `src/**` mutation is authorized, so runtime reprovision is inapplicable. If
source mutation or runtime drift exists, stop before any runner command.

## 8. FINAL and failure rule

The R2 `full` is the sole FINAL for this candidate. Do not rerun a failed
FINAL, and do not count R1's FINAL as R2 acceptance. A mechanical pre-run
command error may be corrected only when no candidate/test process ran and
proof breadth is unchanged; record it.

Any failure, timeout, flake, missing tier, cleanup residue, runtime drift or
guidance contradiction returns `REJECTED — REPLANNING REQUIRED` with its
semantic owner. A later pass does not erase a contrary signal.

## 9. Required result packet

```text
Packet ID and proposed disposition
Start/final HEAD and origin identity
Tracked/index/untracked and diff-check identity
Runtime source/distribution/interpreter/package identity
Focused command, targets, run ID, result, duration and cleanup
Root/current-guidance audit result
Sole R2 FINAL command, run ID, every tier/result/duration and cleanup
Investor Role and Web Actor→Goal→Demand inclusion/result
Product/Contract/Architecture/Replacement/Operations conclusion
Every failure/timeout/flake/no-collection/residue signal and owner
Terminal test-root/process/socket/lock/temp state
R-DOC-005 closure proposal
Omitted checks and residual risk
Proposed ACCEPTED / REJECTED
```

Stop after returning. Wait for the user to bring the result to the
coordinating hub.
