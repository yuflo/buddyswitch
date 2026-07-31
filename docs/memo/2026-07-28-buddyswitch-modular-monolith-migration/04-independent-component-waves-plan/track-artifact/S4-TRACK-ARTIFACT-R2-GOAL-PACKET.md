# S4 Track–Artifact R2 Goal Packet

> Packet state: `READY`
> Packet ID: `BS-MM-S4-TRACK-ARTIFACT-R2-20260731-01`
> Stage/lane: `S4 / Track–Artifact / R2 test-boundary correction`
> Prepared date: 2026-07-31

## 0. Copy-paste independent-task request

```text
Create and pursue this goal:

Execute BuddySwitch packet BS-MM-S4-TRACK-ARTIFACT-R2-20260731-01 as a
continuation of the exact preserved R1 dirty candidate.

Work only in /Users/chen/Dev/buddyswitch/.worktrees/fea-tool. Read root
AGENTS.md, use superpowers:executing-plans, and read the complete
$buddyswitch-testing skill plus its routed references. Then read the ordered
R2 authority under:
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
04-independent-component-waves-plan/track-artifact/

R1 product implementation is frozen and must not be rolled back, reconstructed
or modified. R2 repairs only test physical ownership and its architecture
proof. First reproduce the candidate, coordinating-doc, runtime and resource
identities. Treat docs/memo changes as coordinating-owned input and preserve
them untouched.

Establish a valid architecture RED before moving tests: module-local tests may
import their own Private implementation or another module's Public contract,
but never another module's Private package. Then move the ten cross-component
Track/Artifact tests listed in the R2 READY review back to their exact root test
tiers, keep the three genuinely module-local tests in their module roots, and
strengthen the Track/Artifact architecture proofs so module test directories
are not excluded. Preserve every test assertion and all product behavior.

This is FIX_AFTER_FINAL. Reuse R1 behavior evidence only where source identity
and claim remain equivalent. After correction, run exact GREEN and dynamically
discovered affected focused proof. Do not rebuild or reprovision the installed
runtime because R2 changes no packaged source; a need to mutate or reprovision
product source is a stop condition. Freeze the new candidate and run
./buddyswitch-test full exactly once. After FINAL, make no executable/test/
package mutation and do not rerun it. Return the complete result packet whether
it passes or fails.

Do not change production source, package declarations, Skills, assets, current
architecture docs, runner infrastructure, another component lane, migration
master truth, coordinating memos, Git index/history/branch or remote state.
Stop once on identity mismatch, non-topology product need, assertion weakening,
unclassified failure, invalid runtime/cleanup state or FINAL failure. Do not
loop in blocked turns and do not create R3 yourself.
```

## 1. Candidate identity

R2 candidate identity excludes coordinating `docs/memo/**` paths:

```text
worktree:
  /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
branch:
  fea-tool
HEAD and origin/fea-tool:
  ab58b4f46f5da47acb9f6bd68ee8980e1150b128
non-memo tracked binary patch SHA-256:
  90d3010925ac1366d94211bcc1015dbeb5a20cc633b46db2d4eeed79211a2975
non-memo tracked name/status SHA-256:
  ef1b5d81a8a1840fb4a9602329108401ae1602445bbaa7fe7f112d514e2a5324
index patch SHA-256:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
non-memo untracked files:
  72
non-memo untracked path-set SHA-256:
  7c0d5e31c28d7407367b66d6ebf7c2c60f3b2ab6229c533328b03ce110d76511
non-memo untracked line-manifest SHA-256:
  32c44453d7bf2c0b679dc8a99907dad6ebee09359a52b430d1084b73d05a6dfb
```

The line manifest uses sorted
`<content-sha256><two spaces><path><newline>` records. The executor must
independently reproduce every value before mutation.

## 2. Runtime identity

```text
activated:
  2026-07-30T12:30:57.935144Z
source:
  e36160bf6172d497827394eb687fe073082a60faa136a91965390c833f14fa1f
distribution:
  2d09c0a2e120ffa64a8868c221d58a1ece590a28a3f42ee1f069e9241a774b13
package:
  buddyswitch==0.1.0
Python:
  3.13.5
```

Installed `runtime_activation verify` must pass. R2 does not alter or
reprovision this runtime.

## 3. Ordered authority

Read in order:

1. root `AGENTS.md`;
2. `.agents/skills/buddyswitch-testing/SKILL.md` and every routed reference;
3. `../../00-execution-governance.md`;
4. `S4-TRACK-ARTIFACT-BOUNDARY-DESIGN.md`;
5. `S4-TRACK-ARTIFACT-R2-READY-REVIEW.md`;
6. `S4-TRACK-ARTIFACT-OWNER-CONSUMER-MANIFEST.md`;
7. `S4-TRACK-ARTIFACT-R2-CONTINUATION-PLAN.md`;
8. this Goal Packet.

R2 READY owns the corrected test classification. The amended manifest owns the
write set. The continuation plan owns sequence. `$buddyswitch-testing` and the
current runner own target selection and evidence validity.

## 4. Executor discretion

The executor owns:

- exact file-move mechanics;
- import projection required by the final test locations;
- AST/source-test implementation of the frozen module-test invariant;
- dynamic runner-valid target discovery;
- diagnosis and test-topology repair before FINAL;
- evidence and cleanup reporting.

The executor does not need hub approval for equivalent mechanics inside the
exact write set.

## 5. Frozen boundaries

The executor may not:

- change product source, behavior, Public/Private meaning or composition;
- change an assertion's semantic strength;
- change package, Skill, asset, durable path or runtime state;
- add a test-fixture framework, compatibility path or abstraction;
- update coordinating documents or migration master truth;
- stage, commit, push, rebase or switch branches;
- start another lane or create R3.

## 6. Verification and FINAL

The only public test commands are:

```bash
./buddyswitch-test focused <current explicit file-or-nodeid targets>
./buddyswitch-test full
```

The required state path is:

```text
RED -> GREEN -> IMPACT -> freeze -> one FINAL
```

Any newer failure, timeout, flake, no-test result or cleanup residue supersedes
older evidence until diagnosed. After FINAL, no mutation or retry is allowed.

## 7. Required result packet

Return:

- packet ID and proposed `ACCEPTED` or `REJECTED`;
- starting and final candidate identities;
- full coordinating-doc identity and proof it remained untouched;
- installed runtime verify identity;
- exact move manifest and final module/root test classification;
- RED, GREEN, affected and FINAL commands, targets, run IDs and complete
  results;
- every contrary signal and owning disposition;
- assertion-preservation and architecture-proof result;
- cleanup/residual state;
- omitted checks and residual risk;
- confirmation of no product mutation, Git mutation, next-lane work or
  post-FINAL retry.

The coordinating hub alone accepts, records closure, commits and pushes.
