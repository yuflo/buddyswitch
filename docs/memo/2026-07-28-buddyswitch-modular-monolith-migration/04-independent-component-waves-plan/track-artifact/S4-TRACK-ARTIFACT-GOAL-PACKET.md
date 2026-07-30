# S4 Track–Artifact Atomic Cutover Goal Packet

> Packet state: `READY`
> Packet ID: `BS-MM-S4-TRACK-ARTIFACT-R1-20260730-01`
> Stage/lane: `S4 / Track–Artifact`
> Prepared date: 2026-07-30

## 0. Copy-paste independent-task request

```text
Create and pursue this goal:

Execute BuddySwitch packet BS-MM-S4-TRACK-ARTIFACT-R1-20260730-01 from the
exact preparation checkpoint supplied by the coordinating hub.

Work only in /Users/chen/Dev/buddyswitch/.worktrees/fea-tool. Read root
AGENTS.md, use superpowers:executing-plans, read the complete
$buddyswitch-testing skill and its routed references, then follow the ordered
packet documents under:
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
04-independent-component-waves-plan/track-artifact/

First verify source, worktree, runtime, baseline and resource identity. This is
a behavior-preserving atomic replacement: build two final modules, not one.
Track owns Track state, comments, updates, Artifact relations and lifecycle
invariants. Artifact owns Artifact content, revisions, attachments, source
references, selection and read policy. Artifact reads Track Public. Track
receives only the two approved Artifact Public callables through concrete
consumer-owned ports wired by application composition.

Perform one coherent no-public-test cutover block: create both module owners,
add only the inbound_sources assembly seam, wire and select both modules once,
move their Tools/state/domain/adapters/Skills/assets/owning tests, replace the
approved Context/Evidence/Web/CLI dependency edges, remove product knowledge
from generic ToolContext/runtime paths/cleanup/instance Daemon, update package
and current docs, and delete every retired live path. Do not create
compatibility, fallback, re-export, dual registration, a relationship module,
plugin loader, bus, locator, DI container or second host abstraction.

After the candidate is coherent, run static/source checks, reprovision the
installed runtime non-editably, dynamically discover runner-valid exact and
affected targets from the actual diff, and prove Product, Contract,
Architecture, Replacement and Operations claims. You own target discovery,
mechanically equivalent runner commands, Private file organization and local
owner-correct repair inside classified scope before FINAL. Do not use a
prewritten test-directory guess as runner authority.

When focused proof is clean, freeze the candidate and run
./buddyswitch-test full exactly once. After FINAL, make no executable/test/
package mutation and do not rerun it. Return the complete result packet
whether it passes or fails.

Do not implement Communication, Evidence or Context as components, start
another S4 lane or S5, edit migration master truth/packet history, commit,
push, rebase or switch branches. Stop once on a semantic/Public/storage/
external/failure-contract change, second host abstraction, unclassified shared
production write, protected decision, unexplained external failure, invalid
runtime/cleanup state or FINAL failure. A mechanically projected test import or
retired path covered by manifest section 7 is in scope and must not trigger a
coordination round-trip. Never loop in blocked turns or create patch-on-patch
R2 work yourself.
```

## 1. Identity

```text
Packet:
  BS-MM-S4-TRACK-ARTIFACT-R1-20260730-01
Source snapshot HEAD:
  5c065a6d85bae8723ab0a29f602a09ac7f179a67
Source snapshot tree:
  7d290b313c7ac754e8d07e96e72dee1676b9c85a
Accepted executable predecessor:
  25916f58fbce46c4ad28d7359b61340ead59d986
Track owner source manifest:
  429f88387c78ad8e55c1ba2a2e38d14eb670ad99e9182a40dbd5bba82fcf35b3
Artifact owner source manifest:
  b252d5e66f81668b208153b2ef7c6672bfc4cac132962aca4fb36260da7c8706
Snapshot tracked/index/untracked state:
  clean
Execution worktree:
  /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
```

The hub preparation commit after this packet may change coordinating documents
only. Any pre-execution source/test/fixture/package/runtime-asset change from
the snapshot is an identity mismatch.

## 2. Ordered authority

Read in order:

1. root `AGENTS.md`;
2. `.agents/skills/buddyswitch-testing/SKILL.md` and every routed reference;
3. `../../00-execution-governance.md`;
4. `S4-TRACK-ARTIFACT-BOUNDARY-DESIGN.md`;
5. `S4-TRACK-ARTIFACT-SOURCE-SNAPSHOT.md`;
6. `S4-TRACK-ARTIFACT-OWNER-CONSUMER-MANIFEST.md`;
7. `S4-TRACK-ARTIFACT-IMPLEMENTATION-PLAN.md`;
8. `S4-TRACK-ARTIFACT-READY-REVIEW.md`;
9. this Goal Packet.

The approved boundary design owns product meaning. The manifest owns write
classification. The implementation plan owns sequence. `$buddyswitch-testing`
and the current runner own target selection and execution validity.

## 3. Executor discretion

The executor owns:

- dynamic current target discovery and command construction;
- runner-valid file/node/tier selection;
- module-private file organization inside the two final roots;
- the smallest owner-correct implementation of the approved contracts;
- diagnosis and repair inside classified scope before FINAL;
- mechanical test import/path/package projection under manifest section 7;
- exact evidence and cleanup reporting.

The executor does not need hub approval for those choices.

## 4. Frozen boundaries

The executor may not change:

- semantic ownership;
- Public operation meaning;
- dependency direction or input-port mechanism;
- the sole `inbound_sources` host seam;
- observable Tool/CLI/Web/Daemon/selection/Skill behavior;
- durable schemas or paths;
- authorized production write classes;
- atomic replacement/no-compatibility rule;
- one-FINAL rule;
- Git and acceptance authority.

## 5. Verification authority

The only public test commands are:

```bash
./buddyswitch-test focused <executor-discovered file-or-nodeid targets>
./buddyswitch-test full
```

The packet freezes proof classes, not test paths. The executor records every
target actually selected and why it is sufficient. A newer failure, timeout,
flake, no-test result, runtime mismatch or cleanup residue supersedes older
passing evidence until diagnosed.

## 6. Closure authority

The executor may propose `ACCEPTED` or `REJECTED`. It may not:

- update migration master truth;
- close residue/finding records formally;
- commit or push;
- start the next lane.

The coordinating hub alone reviews the returned repository and evidence,
accepts/rejects the candidate, records closure and creates the remote
checkpoint.
