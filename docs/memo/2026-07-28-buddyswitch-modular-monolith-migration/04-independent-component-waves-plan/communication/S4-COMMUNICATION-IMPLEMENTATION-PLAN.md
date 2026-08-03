# S4 Communication Atomic Cutover Implementation Plan

> Required: `superpowers:executing-plans` and the complete
> `$buddyswitch-testing` skill. The executor creates one dirty candidate and
> returns it; it does not commit or push.

**Goal:** Physically aggregate Communication and make generic Web, Daemon,
ToolContext and cleanup hosts product-neutral without changing observable
Message/IM behavior.

## 1. Execution model

```text
verify handoff/runtime/resources
  -> confirm refactor-entry evidence
  -> add topology REDs
  -> one coherent source/test/current-doc replacement block
  -> static/residue inspection
  -> rebuild/install/activate runtime
  -> direct + affected focused proof
  -> freeze candidate
  -> one full FINAL
  -> result packet and stop
```

Do not run public tests while old and new Message owners coexist. Before
FINAL, diagnose and repair only within the classified write set. After FINAL,
make no executable/test/package/runtime mutation and never rerun FINAL.

## 2. Task 0 — verify authority

- [ ] Read the lane documents and current source; repository facts outrank
  example commands.
- [ ] Record HEAD/tree/branch and tracked/index/untracked identities.
- [ ] Prove executable state still matches snapshot `0b2462b...`; later
  coordinating changes must be docs only.
- [ ] Verify installed runtime with the current no-argument `runtime_activation
  verify` contract and confirm no attributable test/process/socket residue.
- [ ] Reuse the three source-equivalent baselines; run a smaller focused entry
  check only if equivalence cannot be proven.
- [ ] Dynamically validate every intended test target with the runner before
  execution. Do not copy a parent-directory target merely because it appears
  in a memo.

Stop before mutation on identity mismatch, invalid runtime, unexplained dirty
state, unclassifiable shared write or contrary semantic evidence.

## 3. Task 1 — establish Communication owner and edges

- [ ] Create the one Communication physical root and small Public surface.
- [ ] Move Message state/domain/service and Tool into Private.
- [ ] Move actor delivery/client, IM inbound/wake, external session, HTTP
  route, Web identity and iMessage channel into Private adapters.
- [ ] Implement only the four approved Public operations.
- [ ] Define the exact Demand enqueue input port and inject it through
  `build_communication_module(...)`.
- [ ] Redirect Demand triage and Context Message cues through Communication
  Public without changing results.
- [ ] Keep other Context aggregation unchanged for the later Context lane.

## 4. Task 2 — add exact passive composition

- [ ] Add only `web_routes` and `web_workers` to the passive assembly types.
- [ ] Flatten and validate them at application build; retain every existing
  duplicate/invariant check.
- [ ] Select Communication once after Evidence and inject Demand enqueue.
- [ ] Contribute one Message Tool, one IM inbound, one `/api/im/` route, one
  iMessage worker, one Actor Console `im` section and Communication cleanup.
- [ ] Preserve the current Daemon reconciliation order and active-Task probe.
- [ ] Prove assembly invokes no route/worker factory.

## 5. Task 3 — make hosts product-neutral

- [ ] Implement generic route dispatch/preparation and worker execution in
  WebHost using the approved contracts.
- [ ] Remove concrete Communication imports, construction, route branch,
  Actor Console `im` DTO and worker helper from WebHost.
- [ ] Preserve route readiness failure, worker fail-soft, shutdown ordering,
  server close and user-visible output.
- [ ] Remove Message import/default registration from instance Daemon; consume
  only `application.inbound_sources` for IM.
- [ ] Remove Message repository and IM delivery objects from ToolContext;
  Communication Tool adapters own their product behavior using generic actor
  directory/daemon primitives.

## 6. Task 4 — cut cleanup to one generic contract

- [ ] Replace `owner_role`/product branches with the approved multi-owner and
  indexed projection contract; do not keep an alias or parallel shape.
- [ ] Move current Message discovery, retired-schema warning and record
  projection into Communication Private.
- [ ] Mechanically project Demand/Task/Track/Artifact contributions onto the
  new single contract.
- [ ] Preserve exact role/all-data selection, plan/result keys, counts,
  warnings, required skeleton directories, guarded paths and deletion effects.
- [ ] Prove a sender role and recipient role both select the same Message
  exactly once and unrelated roles do not.

## 7. Task 5 — tests, package and replacement

- [ ] Move only the manifest's single-module tests under Communication test
  tiers; keep all cross-module/host tests at root.
- [ ] Add root architecture proof for final physical ownership, Public graph,
  passive contributions, generic host independence, test-root dependency
  rules and retired-path absence.
- [ ] Add/extend host-contract tests for invalid/duplicate route and worker
  registrations, no assembly side effects, route preparation, fail-soft
  worker start and clean shutdown.
- [ ] Update package projection and active architecture docs only as required.
- [ ] Delete every absorbed old path and stale current-doc teaching in the
  same block. Historical memos and scoped negative assertions may retain names.

## 8. Task 6 — verify and return

- [ ] Rebuild/install/activate exactly once after the last source mutation and
  before public proof; repeat only if an in-scope pre-FINAL source repair occurs.
- [ ] Dynamically run direct Communication behavior, then affected Demand/Web/
  Daemon/cleanup/Context/Tool/process/package proof at risk-appropriate breadth.
- [ ] Prove consumer outcomes, failure effects, architecture, replacement and
  resource cleanup—not only registration fields.
- [ ] Freeze source/tree/diff identities and run `./buddyswitch-test full`
  exactly once.
- [ ] Return the complete result packet on either pass or failure and stop.

The hub alone accepts, updates migration truth, commits and pushes.
