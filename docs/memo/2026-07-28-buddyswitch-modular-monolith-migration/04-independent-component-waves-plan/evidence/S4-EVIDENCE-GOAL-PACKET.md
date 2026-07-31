# S4 Evidence Capability Cutover Goal Packet

> Packet state: `READY`
> Packet ID: `BS-MM-S4-EVIDENCE-R1-20260731-01`
> Stage/lane: `S4 / Evidence`
> Prepared date: 2026-07-31

## 0. Copy-paste independent-task request

```text
Create and pursue this goal:

Execute BuddySwitch packet BS-MM-S4-EVIDENCE-R1-20260731-01 from the exact
preparation checkpoint supplied by the coordinating hub.

Work only in /Users/chen/Dev/buddyswitch/.worktrees/fea-tool. Read root
AGENTS.md, use superpowers:executing-plans, read the complete
$buddyswitch-testing skill and its routed references, then follow the ordered
Evidence lane documents under:
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
04-independent-component-waves-plan/evidence/

First verify that the preparation checkpoint differs from executable base
ba292e9781400ee55ecf75a0da0271bb79c87324 only through coordinating
documents, and verify the installed runtime and clean resource state. This is
a behavior-preserving Forward cutover: Evidence is a stateless capability
module contributing one Tool through the existing ModuleAssembly.tools field.
It consumes Artifact Public only, has no Public API of its own, and has no
Browser lifecycle dependency.

Create the Evidence owner under src/buddyswitch/modules/evidence, select its
passive assembly once after Track, redirect the stable browser_evidence
application entrypoint to the module-owned command adapter, delete the old
env/tools/evidence package and runtime_support/browser_evidence.py, and remove
only the two unused Evidence-shaped BrowserAccess methods while retaining
BrowserAccess.status. Keep all current cross-component/host/process tests at
root. Do not create compatibility, re-exports, dual registration, a Browser
port, Public Evidence API, persisted token store, plugin loader, bus, DI
container, or new ModuleAssembly/host field.

Treat the source cutover as one coherent no-public-test block. After the last
src/buddyswitch source mutation, reprovision and verify the installed runtime
before any public test. Dynamically discover runner-valid direct and affected
targets from the actual candidate and prove Product, Contract, Architecture,
Replacement, and Operations claims. You own exact target construction,
mechanically derived proof updates, Private file organization, and
owner-correct repair inside classified scope before FINAL; the packet does
not override current repository or runner facts with a command transcript.

When direct and affected proof is clean, freeze the candidate and run
./buddyswitch-test full exactly once. After FINAL, make no executable, test,
package, or runtime-asset mutation and do not rerun it. Return the complete
result packet whether FINAL passes or fails, then stop.

Do not implement Communication or Context, redesign Browser/Artifact/Runtime
Broker, alter protected Tool/CLI/authority/state behavior, edit migration
master truth, commit, push, rebase, switch branches, or begin another lane.
Stop once on a new semantic/Public/host/storage decision, an unclassified
production write, compatibility need, invalid runtime/cleanup state, or FINAL
failure. Never loop in blocked turns or create a patch-on-patch successor.
```

## 1. Identity

```text
Packet: BS-MM-S4-EVIDENCE-R1-20260731-01
Executable base HEAD: ba292e9781400ee55ecf75a0da0271bb79c87324
Executable base tree: 3bdb9a687fae8b8a28a253639c931844560b734e
Material source manifest:
  1608421bcbc7979c46266d8099a5ef529f3cebe11268d09f2b18a2d8fe50fcf2
Executable tracked/index/untracked state: clean
Execution worktree:
  /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
Predecessors:
  Search ACCEPTED; Track–Artifact ACCEPTED
```

The coordinating preparation commit may change only migration documents.
Any executable source, test, fixture, package, or runtime-asset change from
the base before execution is an identity mismatch.

## 2. Authority and protected behavior

Allowed writes are the classified paths in
`S4-EVIDENCE-IMPLEMENTATION-PLAN.md`. Mechanically derived generic proof
updates are allowed only under D-051 and must be reported. All other paths are
forbidden until the hub classifies them.

Protected:

- Tool `evidence` and actions `issue_browser` / `approve_downgrade`;
- input schemas, Role authority, success/rejection envelopes, token fields;
- `durability=transient`, `mutates_product_state=false`, no durable Evidence;
- active-author Artifact target validation through Artifact Public;
- stable `buddyswitch.application.entrypoints.browser_evidence`;
- Runtime Broker protocol and installed package entrypoint;
- Browser status and all Artifact durable data.

## 3. Required order

```text
identity/runtime/resource verification
  -> refactor-entry GREEN confirmation
  -> structural topology detector
  -> one coherent source/test/current-doc cutover
  -> runtime reprovision + activation verify
  -> direct and affected focused proof
  -> architecture/replacement/cleanup proof
  -> frozen identity
  -> one FINAL
  -> result packet and stop
```

After any later in-scope source repair before FINAL, repeat runtime
reprovision/verify before another public-runner command.

## 4. Evidence and return

Pre-READY evidence:

```text
direct:   244e12758d9f41bebe4bd3754ab1f163 — 9 passed
affected: 158f68a5d618496eb8444310f621162a — 143 passed,
          540 subtests
topology: EVIDENCEP-20260731-01 — PASS
runtime:  verify ok=true
cleanup:  clean
```

Return:

```text
Packet ID and lane
starting/final source, tree, tracked/index/untracked identities
complete changed/created/deleted file list
runtime activation/verification identity
direct, affected and FINAL commands, run IDs and results
every failure/timeout/flake/residue signal and owning disposition
consumer-observed Tool and stable-command results
architecture and retired-path absence proof
process/resource identity and cleanup
omitted checks and residual risk
stop/replan discoveries
proposed ACCEPTED or REJECTED
```

The coordinating hub alone reviews, accepts, updates master truth, commits,
and pushes. The executor stops after returning this packet.
