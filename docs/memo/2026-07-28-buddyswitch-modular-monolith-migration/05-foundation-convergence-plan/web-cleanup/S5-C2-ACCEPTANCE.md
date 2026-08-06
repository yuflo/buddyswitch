# S5 C2 WebHost and Cleanup Acceptance

> Decision: `ACCEPTED`
> Product packet: `BS-MM-S5-WEB-CLEANUP-R1-20260804-01`
> Evidence-only continuation: coordinating-hub R2 authorization
> Authority: coordinating hub
> Acceptance date: 2026-08-06
> Stage effect: C2 accepted; C3 source refresh and READY preparation unblocked

## 1. Accepted outcome

The C2 acceptance sentence is true:

> Browser Track reads and Communication IM traffic reach product-owned route
> adapters selected once by application composition; generic WebHost imports
> no product module and dispatches collision-safe exact/prefix matches; cleanup
> derives all product fields from selected contributions and reports only
> actual guarded effects, with current observable behavior unchanged.

The accepted consumer paths are:

```text
Browser -> generic WebHost matcher -> Track Web adapter -> Track Public
Browser -> generic WebHost matcher -> Communication Web adapter
public CLI -> cleanup host -> selected typed contributions -> guarded effects
```

C2 does not accept S5 as a whole and does not authorize C3 implementation.

## 2. Frozen candidate identity

The executor and coordinating hub reproduced the same candidate:

```text
worktree: /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
branch: fea-tool
HEAD: 1c10e154d056adf85aa4771237bdef70bb4eece5
tracked patch SHA-256:
  80f1aeeb352634c68f0416c574fc41bb6ea9dad3c5dbe7e09a18349f6b2bba95
index patch SHA-256:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
non-ignored untracked-list SHA-256:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
git diff --check: clean
```

Installed runtime identity:

```text
activated_at: 2026-08-04T13:02:48.467229Z
source_digest: 9f138cbccf464216292a59729a940ec7b3b85045fe772216be9fabdf36f89e34
distribution_digest: 996ac858d9ed8dd395c9eb0ce02e33704020024c388d2fdc9ebc1dfeaa1ff0da
package: buddyswitch 0.1.0
runtime.verify: ok=true
```

## 3. Product and contract proof

| Material claim | Consumer path | Evidence | Result |
|---|---|---|---|
| Track list/detail and Communication IM routes retain their DTO, query/body/header and 400/404 behavior | Browser -> WebHost -> contributed owner adapter | Web/IM `97e1a28d6a194ca4bb34a2d7ff3c5367`; FINAL | PASS |
| malformed, duplicate, reserved and overlapping contributed matchers fail before factories run | application composition -> Web route contract validation | overlap RED `14ce07ca83d04b3c9e114db2c55fb22d`; GREEN `d21bcab06d024b6f9810c20bb6ecfb0d`; architecture/Web `f82b2f630e0142be88b6a6f17fd33430` | PASS |
| cleanup fields derive from selected contributions and novel projections need no host edit | cleanup contribution -> plan -> guarded effect -> result | cleanup `fdc8e44e8c5441bc8b980f1af67d68af`; CLI `c05aecfd37084c368bfaba405f6c4003`; FINAL | PASS |
| only actually deleted, category-attributable objects are reported | effect-time safety owner -> result projection -> CLI | cleanup integration and complete FINAL | PASS |
| installed distribution carries the accepted source | package build/install/activation | distribution `5c4ddd06a0bb42758bf884e337d5d0f8`; runtime identity above | PASS |

No Track/Communication Public contract, persisted path, cleanup authority,
public CLI effect or Browser-visible route changed.

## 4. Architecture and replacement proof

The accepted candidate has:

- one passive `WebRouteRegistration` contract with validated exact paths and
  prefixes;
- Track-owned `/api/tracks` and `/api/tracks/` projection selected once by
  application composition;
- Communication-owned `/api/im/` projection on the same generic boundary;
- a generic WebHost with no component import, Track path literal, Track branch
  or Track parser;
- cleanup category counts, plan projection lists, actual-ID reconciliation and
  result ID fields derived from selected `CleanupContribution` values;
- no host enumeration of Artifact, Message or Comment categories/fields;
- no discovery, fallback, compatibility alias, second registry, DI container
  or service locator.

`R-FND-004` and `R-FND-008` are closed. Physical host/state movement remains
owned by later S5 checkpoints exactly as D-060 requires.

## 5. Verification evidence

```text
matcher-overlap exact GREEN:
  run: d21bcab06d024b6f9810c20bb6ecfb0d
  result: 1 passed

architecture/Web unit:
  run: f82b2f630e0142be88b6a6f17fd33430
  result: 38 passed, 33 subtests

Web/IM integration:
  run: 97e1a28d6a194ca4bb34a2d7ff3c5367
  result: 76 passed, 95 subtests

cleanup integration:
  run: fdc8e44e8c5441bc8b980f1af67d68af
  result: 17 passed

cleanup CLI/process:
  run: c05aecfd37084c368bfaba405f6c4003
  result: 6 passed, 10 subtests

distribution:
  run: 5c4ddd06a0bb42758bf884e337d5d0f8
  result: 3 passed

frozen FINAL:
  command: ./buddyswitch-test full
  run: c1a3466da1b6455ead00dfcdca86bf46
  result:
    Unit Python 479 passed, 1,144 subtests
    Unit JavaScript 147 passed
    Integration 771 passed, 458 subtests
    Process 260 passed, 374 subtests
    System 22 passed
    shell syntax PASS
    runner diff-check PASS
    parent exit 0
  cleanup: run root and attributable resources absent
```

The hub performed a read-only diff and identity review, reproduced runtime
identity and cleanup state, and reused source-equivalent executor evidence. It
did not rerun focused or FINAL merely because the reviewer changed.

## 6. Contrary evidence and operations

The executor classified and resolved three proof-construction signals: an
invalid RED missing its `pytest` import, an assertion against exception string
format rather than typed fields, and one invalid CLI class node ID. Reviewer
discovery of same-registration matcher overlap produced a valid RED, an
owner-correct source repair, reprovision, exact GREEN and complete affected
proof before freeze.

The first frozen FINAL attempt
`1bc63a382cd54195a1e118a706cc1182` lost its system-tier terminal output and
numeric exit status. It was never used as acceptance evidence and did not
report a product failure, timeout, flake or residue. A coordinating-hub
evidence-only continuation preserved the exact candidate/runtime and ran one
new FINAL with a parent-owned session through numeric exit. That run passed and
closed the evidence-capture gap.

No failure, timeout, flake, contradictory result or cleanup residue remains
unresolved. No required check was omitted.

## 7. Acceptance and next boundary

Product, Contract, Architecture, Replacement and Operations proof pass. C2 is
`ACCEPTED`; its implementation authority is consumed and must never resume.

The only unlocked action is:

```text
commit and push the C2 safe checkpoint
  -> refresh current C3 Browser source, consumers, lifecycle and tests
    -> issue C3 execution authority only after its own READY review
```

C3–C7 implementation and S6 remain unauthorized until their own gates pass.
