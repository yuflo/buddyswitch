# S4 Communication Cleanup Repair Goal Packet

> Packet state: `READY`
> Packet ID: `BS-MM-S4-COMMUNICATION-R2-20260803-01`
> Breadth: `FIX_AFTER_FINAL`
> Consumes: `BS-MM-S4-COMMUNICATION-R1-20260803-01`
> Prepared date: 2026-08-03

## 0. Copy-paste independent-task request

```text
Create and pursue this goal:

Execute BuddySwitch packet BS-MM-S4-COMMUNICATION-R2-20260803-01 as the sole
active authority for the current dirty candidate in
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool.

Read root AGENTS.md, use superpowers:executing-plans, read the complete
$buddyswitch-testing skill and its routed references, then read the complete
Communication lane directory. Treat R1 as consumed historical evidence and
read these two R2 documents last:

S4-COMMUNICATION-R2-CLEANUP-REPAIR-PLAN.md
S4-COMMUNICATION-R2-GOAL-PACKET.md

First reproduce the packet's branch, HEAD, non-memo candidate identity,
installed runtime identity and clean resource state. Preserve the current R1
dirty candidate directly. Do not reset, stash, reconstruct, cherry-pick or
layer an independent patch over it.

Add an exact regression that proves the uncovered cleanup gap on the current
installed candidate: role cleanup selects only valid sender/recipient-owned
Messages; explicit all-data cleanup recursively selects and deletes current
non-JSON/nested residue and retired Message residue; leaf symlinks are unlinked
without reading, following or deleting their targets; warnings and Message
index projection agree with those effects. Dynamically validate the exact
runner target and obtain an attributable RED before production repair.

Repair the Communication-private cleanup owner. Change the generic cleanup
host only if necessary to allow safe unlinking of a contributed leaf symlink
while still rejecting symlinked parents and path escapes. Keep the existing
OwnedStatePath, multi-owner and index-projection architecture. Do not introduce
scope-aware discovery, a warning framework, a second cleanup shape, product
branches in the host, compatibility or fallback.

After the last source mutation, rebuild/install/activate the non-editable
runtime and run no-argument runtime_activation verify. Run the exact regression
to GREEN, dynamically select affected proof from current repository facts,
then freeze the complete candidate and run ./buddyswitch-test full exactly
once. R1 FINAL is superseded only for final acceptance; reuse it as evidence
for unchanged investigation context.

After FINAL, make no executable/test/package/runtime mutation and do not rerun
it. Return the complete R2 result packet whether it passes or fails, then stop.
Do not commit, push, edit migration master truth, modify unrelated
Communication/Public/Web/Daemon behavior, or begin Context. Stop once rather
than looping if a genuine packet stop condition occurs.
```

## 1. Continuation identity

The executor must independently reproduce the non-memo candidate before
mutation. Coordinating files under `docs/memo/**` are excluded because this
packet changes that set.

```text
worktree: /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
branch: fea-tool
HEAD and origin/fea-tool: b0e343c4e4b546a2a06cd3ff6e57dd4d06c052d5
HEAD tree: e5ce2557f2e702e2e4d0b2cc971d3de68db35dd0
non-memo tracked binary patch SHA-256:
  761e4460cd052f621ffe262b5f29247e83c106b1d5ed5d2dfeec7cccac1790a8
index patch SHA-256:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
non-memo untracked files: 46
non-memo untracked sorted-NUL path-set SHA-256:
  6aaaf167a7e8d1ded6ff31e20d139cc7887ddf00b5ca1531b8395d221b608fdb
non-memo untracked sorted line-manifest SHA-256:
  e8da4f635de8e6a5602c7646001ab7e21cd5ff52d92a14e4e64c70eeac4c3c4a
git diff --check: clean
```

The line manifest consumes ordinary `shasum -a 256 <path>` output in sorted
path order. The path-set digest consumes each sorted UTF-8 path followed by
NUL.

Installed runtime identity before R2:

```text
activated_at: 2026-08-03T04:56:05.869318Z
source_digest: 8ca0ea8cf4dd5fba253c71d1b2b389507753577c63e23e22cf7c5be7e5b6d4a4
distribution_digest: 25bb24fc1b21dd8e78d58d4f010e60240c121e05bf53af6967af2de4fa20a23f
package_version: 0.1.0
runtime.verify: ok=true
```

## 2. Acceptance sentence

> Communication cleanup recursively owns current and retired Message residue;
> role scope deletes only safely attributable current Messages, explicit
> all-data scope deletes every safely owned Message entry without following
> symlinks, warnings and index projection match the action, and the existing
> Communication/Public/Web/Daemon architecture and all other product behavior
> remain unchanged.

## 3. Required proof classes

| Proof | Required outcome |
|---|---|
| Product | role and all-data cleanup produce the promised selected/deleted state |
| Contract | warnings, counts, Message IDs/records and required directories agree with effects |
| Architecture | Message discovery remains Communication Private; generic cleanup has no Message branch |
| Replacement | retired Message state has no read path and is removed only by explicit all-data cleanup |
| Operations | nested residue and leaf links are removed without following targets; cleanup leaves no process/temp residue |

The exact regression must fail on the R1 candidate for the known omission and
pass after repair. Existing passing tests alone do not prove this claim.

## 4. Write and no-write boundary

Authorized:

```text
src/buddyswitch/modules/communication/private/adapters/cleanup.py
tests/integration/env_tool/test_cleanup.py
```

Conditionally authorized only for the frozen symlink/architecture proof:

```text
src/buddyswitch/runtime_support/env_cleanup.py
tests/unit/architecture/test_communication_component_boundaries.py
docs/arch/communication-capability-architecture.md
```

Everything else is read-only. A need outside this set is a stop condition, not
implicit permission to expand.

## 5. Evidence and return contract

Return:

```text
Packet ID and proposed ACCEPTED/REJECTED disposition
starting/final HEAD, tracked/index/non-memo-untracked identities
exact changed paths and why each was required
R1 contrary-signal reproduction or equivalent RED run ID/result
runtime rebuild/install/verify identity after the final source mutation
exact GREEN, affected and single replacement FINAL commands/run IDs/results
role/all-data selected paths, warnings, indices and executed deletion outcomes
leaf-symlink target preservation and traversal-rejection evidence
architecture/residue proof and complete cleanup/resource audit
every failure/timeout/flake/residue signal and its disposition
omitted checks, residual risk and any stop/replan discovery
```

The coordinating hub alone accepts the result, writes acceptance truth,
commits and pushes. The executor stops after returning the packet.
