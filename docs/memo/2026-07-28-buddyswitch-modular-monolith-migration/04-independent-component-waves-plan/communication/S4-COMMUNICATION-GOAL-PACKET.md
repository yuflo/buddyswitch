# S4 Communication Atomic Cutover Goal Packet

> Packet state: `READY`
> Packet ID: `BS-MM-S4-COMMUNICATION-R1-20260803-01`
> Stage/lane: `S4 / Communication`
> Prepared date: 2026-08-03

## 0. Copy-paste independent-task request

```text
Create and pursue this goal:

Execute BuddySwitch packet BS-MM-S4-COMMUNICATION-R1-20260803-01 from the
exact preparation checkpoint supplied by the coordinating hub.

Work only in /Users/chen/Dev/buddyswitch/.worktrees/fea-tool. Read root
AGENTS.md, use superpowers:executing-plans, read the complete
$buddyswitch-testing skill and its routed references, then read every document
in order under:
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
04-independent-component-waves-plan/communication/

First verify the executable source is still exactly snapshot
0b2462beffaa775980b096b7504bef341fb907bd and any later hub changes are
coordinating documents only. Verify the installed runtime using the current
no-argument runtime_activation verify contract and prove clean resource state.

Perform one behavior-preserving Forward replacement. Create the single
src/buddyswitch/modules/communication owner for Message state/semantics, the
Message Tool, actor delivery, IM inbound, external sessions, /api/im route,
Web identity, iMessage channel and cleanup. Expose only the four approved
Communication Public operations. Inject Demand's enqueue_inbound callable at
application composition so Communication never imports Demand. Redirect
Demand and Context through Communication Public.

Add only the approved passive web_routes and web_workers assembly fields.
Make generic WebHost prepare contributed routes, run optional workers
fail-soft and stop started workers before server close without importing IM.
Move the Actor Console im section into Communication's existing section
contribution. Make instance Daemon consume the existing inbound contribution
without importing Message. Replace Message-specific central cleanup with the
one approved generic multi-owner/index projection and mechanically move the
already accepted module cleanup contributors onto that same single contract.
Preserve every current observable Tool, route, Demand, identity, worker,
cleanup and failure effect.

Keep cross-component/host/process tests at root and move only the explicitly
classified single-module tests. Architecture proof must inspect module test
roots. Delete every absorbed old path in the same candidate; create no alias,
re-export, fallback, duplicate registration, plugin discovery, DI container,
event bus, lifecycle framework or second Communication package.

Treat the source replacement as one no-public-test block. After the last
source mutation, rebuild/install/activate the non-editable runtime before any
public test. Dynamically validate and select runner targets from the actual
candidate; memo examples do not override runner facts. Prove Product,
Contract, Architecture, Replacement and Operations outcomes. Repair only
classified, owner-correct failures before FINAL.

When direct and affected proof is clean, freeze the candidate and run
./buddyswitch-test full exactly once. After FINAL, make no executable, test,
package or runtime-asset mutation and do not rerun it. Return the complete
result packet whether FINAL passes or fails, then stop.

Do not implement Context as a module, change protected schemas/authority/state
formats, edit migration master truth, commit, push, rebase, switch branches or
begin another lane. Stop once on a new semantic/shared-host/storage decision,
an unclassified production write, compatibility need, invalid runtime/cleanup
state or FINAL failure. Never loop in blocked turns and never create a
patch-on-patch successor.
```

## 1. Identity

```text
Packet: BS-MM-S4-COMMUNICATION-R1-20260803-01
Executable base HEAD: 0b2462beffaa775980b096b7504bef341fb907bd
Executable base tree: 1fa512c61fd4cdf3d5590381acbae55e08baf961
Material source manifest: 6d8d3837f358bcedb8ce48f7d3fb8c6ee697e0745dca0c33526bfd381c52f8f8
Executable tracked/index/untracked state: clean
Execution worktree: /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
Predecessors: S1-S3 accepted; Search, Track-Artifact and Evidence accepted
```

## 2. Required order

```text
identity/runtime/resource verification
  -> refactor-entry evidence confirmation
  -> topology/host-contract REDs
  -> coherent replacement block
  -> runtime reprovision + verify
  -> direct and affected focused proof
  -> architecture/replacement/cleanup proof
  -> frozen identity
  -> one FINAL
  -> result packet and stop
```

## 3. Return contract

Return:

```text
Packet ID and proposed ACCEPTED/REJECTED disposition
starting/final HEAD, tree, tracked/index/untracked identities
complete changed/created/deleted path list by owner class
runtime activation and verification identity
direct, affected and FINAL commands, run IDs, results and cleanup
consumer-observed Message Tool, Demand ingress, Web route and cleanup outcomes
route preparation and worker start/stop/failure evidence
Public graph, generic-host independence and retired-path absence proof
every failure/timeout/flake/residue signal and owner disposition
omitted checks, residual risk and stop/replan discoveries
```

The coordinating hub alone reviews, accepts, updates master truth, commits and
pushes. The executor stops after returning the packet.
