# S7 Final System Acceptance Goal Packet

## 1. Copy-paste session request

```text
Create and pursue the following goal in this independent session:

Prove on the frozen BuddySwitch candidate that Product, Contract,
Architecture, Replacement and Operations evidence agree that the packaged
explicit modular monolith and narrow RoleHost are the only live architecture.
This is validation-only: do not edit any repository or runtime file. A
material defect must be returned with its semantic owner/originating stage;
do not repair it inside S7.

Use only
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
07-final-acceptance-plan/S7-GOAL-PACKET.md
and its governing repository instructions. Execute the linked S7 plan, return
the required result packet, and stop. Do not update master migration truth,
declare S7 accepted, commit, push or begin unrelated product work.
```

## 2. Packet identity

```text
Packet ID:             BS-MM-S7-FINAL-R1-20260813-01
Stage:                 S7 / final system acceptance
Master state:          S0–S6 ACCEPTED; S7 READY
Prepared by:           coordinating hub
Prepared date:         2026-08-13
Executable source:     6a51244192f5bad36a4438f030183acc4c5f9529
Tracked/index state:   empty at source refresh
Untracked state:       empty at source refresh
Execution branch:      fea-tool
Execution worktree:    /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
Predecessor:           S6 ACCEPTED and pushed
```

The commit carrying this preparation packet may be memo-only and therefore
newer than the executable source checkpoint. Before execution, prove that no
non-memo or declared runtime input changed after `6a512441…`, that HEAD equals
`origin/fea-tool`, and that the worktree is clean. Any executable delta rejects
admission.

## 3. Goal and acceptance

Acceptance sentence:

> Product, Contract, Architecture, Replacement and Operations evidence agree
> that the packaged explicit modular monolith and narrow RoleHost are the only
> live BuddySwitch architecture.

Consumer path:

```text
public consumer action -> Application composition -> owning module/Foundation
-> installed runtime + canonical effect -> terminal result + clean resources
```

Non-goals:

- no feature, refactor, bug fix or test edit;
- no dependency install or runtime reprovision;
- no acceptance/truth/doc update;
- no commit, push or next-stage work.

## 4. Read order

1. root `AGENTS.md`;
2. `.agents/skills/buddyswitch-testing/SKILL.md` completely;
3. `docs/arch/**` current boundaries;
4. migration roadmap and `00-coordination-hub.md`;
5. `07-final-acceptance.md`;
6. this directory's source snapshot, proof matrix, plan and READY review;
7. D-001–D-078 and R-DOC-005;
8. current executable contracts/tests.

Repository facts and the current runner outrank target examples. Do not use a
system shell variable such as `path`, `PATH`, `HOME` or `CODEX_HOME` as a local
probe variable.

## 5. Allowed and forbidden scope

```text
OWNER:              READ ONLY
CONSUMER:           READ ONLY
HOST CONTRACT:      READ ONLY
COMPOSITION:        READ ONLY
PROOF:              execute existing tests only
CURRENT DOC:        READ ONLY
MASTER TRUTH:       READ ONLY
RUNTIME/USER STATE: runner-owned temporary effects only
```

Every repository write is forbidden. Do not stage, restore, clean, delete or
rewrite unrelated/ignored state. Do not use `git clean`, rollback, patch,
reprovision or an alternate test entry.

## 6. Frozen decisions and behavior

- one source/build/runtime truth and one installed distribution;
- physically aggregated explicit product modules;
- product-neutral Foundation hosts and primitives;
- one narrow RoleHost discovering only reviewed local Role packages;
- code-free selected Actor workspaces;
- one public test runner with owner-local approved tiers;
- no alias, fallback, compatibility path, scanner or duplicate catalog;
- current success, rejection, authority, persistence, recovery and cleanup
  effects remain exact.

## 7. Pre-READY evidence

```text
architecture/package: 5e822ce3503c46b7818bb447fc239a27
real Actor/product:   9a85e5acda2846c6bd0a1b2e2b4ab9e5
source-equivalent full baseline: 56b2be7f071942b89ffecad5e2891bc9
runtime source:       28cbef6f68c12b9a9cdddbff94b326eb8b83453f475f1a74f62642cdccc64f38
runtime distribution:b16a15a225b592414e1fcf89347f2f2fc00d5a32750f56d4359a2c51adebf62f
```

Full commands, results, environment, cleanup and contrary-signal disposition
are in `S7-PROOF-MATRIX-AND-PREFLIGHT.md`.

## 8. Execution sequence

1. Admit the exact clean upstream candidate and canonical runtime/toolchain.
2. Rediscover and run one focused architecture/distribution/activation group
   equivalent in proof breadth to the preflight group.
3. Recheck clean source/runtime/resource identity and freeze the candidate.
4. Run exactly one `./buddyswitch-test full`.
5. Audit terminal runtime/process/socket/lock/temp cleanup and current guidance.
6. Return the result packet and stop.

Known current focused targets are:

```text
tests/unit/architecture
tests/process/package/test_distribution_install.py
tests/process/package/test_runtime_activation.py
```

They were runner-validated at READY. The executor owns equivalent current
target construction if repository discovery proves a mechanical difference;
proof breadth may not shrink.

No `src/buddyswitch/**` mutation is authorized, so D-044 reprovision is
inapplicable. If source mutation exists, stop before any runner command.

## 9. Final and failure rule

`full` is authorized only after focused proof and frozen identity pass. It is
the sole S7 FINAL. Do not rerun a failed FINAL. Do not introduce a
FIX_AFTER_FINAL loop because S7 owns no writes. A mechanical pre-run command
error may be corrected only if no candidate/test process was exercised and the
equivalence is exact; record it.

Any product/test/cleanup failure, timeout, flake, missing tier, runtime drift
or doc contradiction returns `REJECTED — REPLANNING REQUIRED` with the owning
stage. A later pass never erases a signal.

## 10. Required result packet

```text
Packet ID and proposed disposition
Start/final HEAD and origin identity
Tracked/index/untracked and diff-check identity
Runtime source/distribution/interpreter/package identity
Declared Python/pytest/Node identity
Focused command, discovered targets, run ID, result, duration and cleanup
Single FINAL command, run ID, every tier/result/duration and cleanup
Representative investor Role and Web Actor→Goal→Demand inclusion/result
Product/Contract/Architecture/Replacement/Operations conclusion
Retired-root/current-guidance/manual residue audit
Every failure/timeout/flake/no-collection/residue signal and owning disposition
Parent-known process/socket/lock/temp identities before cleanup where created
Terminal test-root/process/socket/lock/temp state
R-DOC-005 closure proposal
Omitted checks and residual risk
Stop/replan discoveries with semantic owner and originating stage
Proposed ACCEPTED / REJECTED
```

Stop after returning. Wait for the user to bring the result to the coordinating
hub.
