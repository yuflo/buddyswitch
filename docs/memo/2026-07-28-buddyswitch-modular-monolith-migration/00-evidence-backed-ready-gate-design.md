# Evidence-Backed READY Gate Design

> Status: ACCEPTED; adoption is governed by
> `00-evidence-backed-ready-gate-adoption-plan.md`
> Scope: migration handoff quality only
> State-model decision: keep `PREPARE -> READY`; add no new lifecycle state
> Policy owner after adoption: `00-execution-governance.md`

## 1. Bottleneck

S0, S1 and E1 each passed a preparation or READY decision before a later
executor discovered a contradiction that the coordinating hub could have
detected beforehand:

| Invalidated handoff | Late discovery | Required earlier owner |
|---|---|---|
| S0 to E0 | the selected source baseline had ten failures in three families | S0 admission proof |
| S1 to E1 | stale Demand preservation expectations and nested test packages entering the wheel | S1 preservation and target-topology preflight |
| E1 to E2 | legitimate runtime assets excluded, directory symlinks ignored, and source/install content never compared | E1 boundary-contract preflight |

The executors stopped correctly. The repeated loss came from the hub treating
READY as proof that a packet was complete and safe to stop, rather than proof
that its specification was already coherent and executable.

The resulting role inversion was:

```text
executor = specification validator + implementer
```

The required model is:

```text
hub closes and proves the specification
  -> executor implements one frozen contract
    -> hub accepts or rejects the implementation
```

## 2. Design decision

Do not add `SPEC_VALIDATED`, another reviewer task, or another policy
document. Redefine the existing READY transition:

> A Goal Packet is READY only when the exact source baseline and every
> material new boundary assumption have source-bound evidence. A planned test,
> a stop condition, or an implementation-stage risk is not READY evidence.

`00-execution-governance.md` remains the single policy owner. This design
document records why and how that owner must change; it does not become a
parallel live policy.

## 3. Required READY evidence

### 3.1 Complete preservation baseline

Before the first mutation, run every affected preservation group that the
packet will later use to claim behavior preservation.

- A representative subset is insufficient.
- A group may be omitted only when the target change makes it impossible to
  run before implementation; the packet must name that impossibility and use
  the nearest earlier consumer proof.
- Any unexplained failure keeps the stage in `PREPARE`.

This moves baseline discovery before development rather than between
implementation checkpoints.

### 3.2 Boundary-contract matrix

For each new package, runtime, host, state, composition, or projection
boundary, enumerate the material claim classes:

| Claim class | Question |
|---|---|
| Positive | What required input or consumer must succeed and remain present? |
| Negative | What forbidden input, path, dependency, or residue must fail or remain absent? |
| Correspondence | When two representations claim one identity, how is path/content/state equality proved? |
| Mutation | What changes after creation, activation, restart, or replacement, and what must then fail? |
| Cleanup | What process, file, socket, lock, temporary root, or partial state must not survive? |

Not every boundary needs every class. Every omitted material class requires an
explicit inapplicability reason.

### 3.3 Representative final-topology preflight

When correctness depends on a packaging tool, configuration language,
filesystem behavior, process boundary, or framework convention, the hub must
exercise the selected mechanism in an isolated final-shaped fixture before
READY.

The fixture must include both:

- the most important required case; and
- the most plausible forbidden or adversarial case.

A toy happy-path package proves tool availability only. It does not prove the
product boundary.

The preflight may use temporary sources and runtimes. It may not edit live
product code or stand in for the executor's RED/GREEN proof.

### 3.4 No delegated architecture question

The READY review must classify every remaining risk:

```text
private implementation choice
implementation defect detectable by the frozen RED
external/protected uncertainty
unresolved architecture or boundary assumption
```

Only the first two may enter an ordinary Goal Packet. External/protected
uncertainty requires its named protected decision. Any unresolved architecture
or boundary assumption keeps the stage in `PREPARE`.

Wording such as the following is forbidden in a READY decision:

```text
implementation will determine
executor should confirm
owned by later direct proof
package-data completeness remains a known implementation risk
```

when the subject changes the boundary contract or accepted architecture.

## 4. Evidence identity

Every pre-READY proof records:

```text
claim
source commit and exact local diff
fixture or current consumer topology
exact command/probe
expected discriminating result
actual result
cleanup
remaining risk
```

The Goal Packet references these identities. It does not merely restate their
conclusions.

If source, build declaration, boundary contract, fixture topology, or affected
test set changes, the relevant preflight is invalid and READY must be reviewed
again.

## 5. Handoff responsibility

### Coordinating hub

Before READY, the hub owns:

- complete affected preservation discovery;
- contract-language disambiguation;
- representative target-topology probes;
- source-bound evidence identity;
- confirmation that the executor has no architecture decision left to infer.

### Independent executor

After READY, the executor owns:

- writing or reusing the frozen RED;
- implementing the smallest owner-correct change;
- GREEN, refactor, affected verification and cleanup;
- stopping when current facts contradict the frozen contract.

An executor-discovered architecture contradiction is a hub preparation defect,
even when the stop mechanism works correctly.

## 6. Loop breaker

Stop conditions contain damage; they do not make a packet READY.

When a READY packet stops because its specification is contradicted:

1. kill the packet permanently;
2. return the stage to `REPLANNING/PREPARE`;
3. write a root-cause review that names the missed pre-READY proof;
4. restate the invariant before proposing another repair;
5. run the complete boundary preflight before generating a successor packet.

If a successor repair for the same boundary is invalidated again:

> Do not issue another patch-on-patch repair packet. Reopen the boundary
> architecture, compare alternative designs, obtain maintainer approval, and
> prove the selected mechanism end to end before planning implementation.

This is the current S1 package/runtime state. E2 is permitted only after the
new source/distribution correspondence design passes its hub preflight. There
is no automatic E3.

## 7. E2 application

The accepted E2 invariant is:

> Every regular non-test file below `src/buddyswitch/**` corresponds by exact
> package-relative path and bytes to exactly one installed package file; every
> installed package file has that source counterpart; every package-source
> symlink fails closed; co-located tests and caches remain non-runtime.

Before an E2 Goal Packet exists, the hub must prove in an isolated current-tool
fixture:

1. a legitimate package-owned asset below an `assets/docs/**` path is present
   and byte-identical after installation;
2. a co-located test subtree and cache content are absent;
3. a source-only file, installed-only file, missing file, or byte change is
   rejected;
4. file and directory symlinks anywhere below package source are rejected
   before exclusions, including inside a real co-located tests subtree;
5. source drift between wheel build/install and first activation is rejected;
6. exact correspondence works with `setuptools.build_meta`, the wheel
   `RECORD`, and no custom build backend or duplicate selection engine.

Only then may the hub write the E2 implementation plan, Goal Packet and READY
review.

## 8. Adoption surfaces

After written-design review, adoption updates only existing owners:

- `decision-log.md`: accept one decision defining evidence-backed READY;
- `00-execution-governance.md`: replace the current document-completeness
  READY contract and add the loop breaker;
- `00-coordination-hub.md`: require preflight identities in just-in-time Goal
  Packets;
- `00-program-readiness.md`: make executable entry-baseline proof part of R4;
- `stage-goal-packet-template.md`: require pre-READY evidence identities and
  forbid delegated boundary questions;
- `stage-implementation-plan-template.md`: require the boundary-contract
  matrix and distinguish hub preflight from executor RED/GREEN;
- current S1 ledger/review documents: keep S1 in `REPLANNING` until E2
  preflight and READY complete.

No new runtime state, plugin, service, reviewer role, test runner, evidence
ledger, or long-lived policy document is introduced.

## 9. Success measure

For each future handoff:

```text
post-READY specification invalidations: 0
executor-discovered architecture decisions: 0
unexplained pre-mutation preservation failures: 0
```

Implementation defects and legitimate new repository facts may still stop a
packet. Repeated failure of an assumption already available to the hub before
handoff is not treated as normal iteration.
