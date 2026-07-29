# S3 R1 READY Review

> Review result: `READY`
> Packet: `BS-MM-S3-R1-20260730-01`
> Review date: 2026-07-30

## FRAME

The bottleneck is no longer Task architecture selection. It is the inability
to complete and verify an otherwise coherent partial candidate because the
old READY consumer manifest omitted indirect package/router consumers and
contained weak test projections.

Observable acceptance:

> The preserved Task candidate completes through one exact scope, generic
> package/router tests require no Task-specific exception, and the entire
> Task/Goal/Demand consumer path passes against one verified installed
> runtime.

## TRACE

The hub re-traced:

- all current dirty source/test paths;
- every direct Task import and retired source path;
- Tool IDs in expected/shipped/discovered tables;
- generated `env.tools.{tool}` modules and package paths;
- subprocesses with and without application activation;
- module-local test discovery and wheel exclusion;
- root fixture/private-import edges;
- current Web and cleanup proof.

`S3-R1-CONSUMER-AUDIT.md` classifies two newly required writes, four candidate
proof corrections and all proof-only neighboring consumers.

## PROVE

The current runtime mismatch is explained and schedules reprovision before
proof. R1 then has two deterministic existing REDs:

1. retired Task directory/discovery expectation;
2. retired selected Task private-module expectation.

Both directly distinguish the stale generic-test coupling from the target.
They do not require product behavior to change.

No candidate GREEN is reused because no valid post-mutation S3 run occurred.
The original pre-S3 runs remain preservation baselines only.

## BUILD / REPLACE

The partial product candidate passed static architecture admission:

- one final Task physical owner;
- exact acyclic Demand/Task source graph;
- explicit application wiring;
- typed generic-host contributions;
- no old owner or compatibility path;
- moved domain/tests preserve content and intended semantics.

R1 does not roll back or invent a replacement architecture. It repairs the
generic proof owner, finishes current docs, then verifies the candidate.

## Scope completeness

| Representation class | R1 disposition |
|---|---|
| imports | AST-classified |
| literal owner paths | positive/absence-classified |
| product/tool ID sets | exact data-table audit |
| generated module/path names | router/package tests classified |
| activation-dependent subprocesses | activated vs discovery-only behavior recorded |
| package/test projection | runner and wheel proofs classified |
| fixture/private test access | one adapter and quality corrections classified |

There is no remaining unclassified known executable write.

## S2 and D-037 ratchet

R1 incorporates the prior delivery lessons:

- it diagnoses the packet owner rather than blaming or looping the executor;
- it consumes the contradictory predecessor packet;
- it fixes a generic test boundary instead of adding another special case;
- it orders reprovision before RED because package source is already dirty;
- it carries complete contrary evidence and allows one FINAL only;
- it stops on genuinely new scope, not on an ordinary in-scope
  implementation defect;
- it returns once to the hub instead of entering repeated blocked turns.

D-049 makes the missing consumer-representation class explicit for later
READY reviews.

## Proof-class admission

| Proof class | Admission |
|---|---|
| Product | full original affected Task/Goal/Demand/CLI/Web/system set retained |
| Contract | exact Tool/Goal/daemon/DTO/state contracts unchanged |
| Architecture | current candidate statically matches D-045–D-048 |
| Replacement | old paths and private-import allowlist explicitly scanned |
| Operations | activation-first, declared environment, single FINAL and cleanup frozen |

## Determination

`READY`.

Only packet `BS-MM-S3-R1-20260730-01` may continue S3. The old packet is
consumed. S4 remains blocked. The coordinating hub alone accepts the result
and creates the next Git checkpoint.
