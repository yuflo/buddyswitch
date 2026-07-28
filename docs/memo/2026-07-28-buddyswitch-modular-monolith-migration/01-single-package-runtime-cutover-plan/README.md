# S1 Single Package and Runtime Cutover Implementation Plan Pack

> Current state: IN_PROGRESS — C1–C5 ACCEPTED, C6 PENDING
> Formal packet `BS-MM-S1-20260728-01` is stopped and no longer authorized.
> Bounded repair packet `BS-MM-S1-E1-20260728-01` also stopped and authorizes
> no further execution. `BS-MM-S1-E2-20260728-01` is accepted and consumed.
> `BS-MM-S1-C2C5-20260728-01` is accepted and consumed. No packet is
> currently authorized.
>
> **For the independent S1 agent:** REQUIRED SUB-SKILL:
> `superpowers:executing-plans`; execute this pack checkpoint by checkpoint and
> stop at its review gates.
> Plan state: C6 PREPARATION REQUIRED
> Source baseline: `9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3`
> Runtime work: C1–C5 accepted; C6 pending
> Charter: `../01-single-package-runtime-cutover.md`

## Goal

Move the current BuddySwitch runtime to one installed package and one runtime
identity without changing product behavior, then remove all old executable
roots and Actor implementation copies.

## Why this is a pack

S1 crosses package, source/assets, processes, Actor publication, every
lifecycle transition, tests and guidance. One giant checklist would force an
executor to hold unrelated concerns at once.

The executor works one checkpoint document at a time:

1. `01-package-contract.md`;
2. `02-source-and-asset-move-map.md`;
3. `03-process-entrypoint-cutover.md`;
4. `04-actor-workspace-projection.md`;
5. `05-lifecycle-and-consumer-proof.md`;
6. `06-replacement-and-acceptance.md`.

The current independent packet may not stage or commit checkpoints. None is
independently mergeable. The accepted mainline remains pre-S1 until C6 accepts
the complete S1 candidate.

## S1 intermediate package shape

S1 solves package/runtime provenance before product modularization. Current
product semantics may temporarily retain technical package grouping:

```text
src/buddyswitch/
  application/entrypoints/
  foundation/process_runtime/      activation and runtime identity
  env/                         current env domain/repo/tool code
  runtime_kernel/
  runtime_store/
  launcher/                    current host/process/product handler code
  runtime_support/             current top-level runtime helpers
  catalog/                     current manifest/profile truth
  contracts/                   current Role/runtime contracts
  config/                      current product config
  skills/                      current Skill packages
```

This is one current packaged truth, not a compatibility path. S2–S6 move these
current owners directly into final `foundation/modules/roles` roots and delete
the corresponding technical package paths.

The accepted S1 candidate contains no executable old root outside
`src/buddyswitch`.

## Handoff

Before execution, refresh:

```text
source commit
local diff
package dependency availability
exact file inventory
exact S1 tests/nodeids
protected data paths
active processes/resources
```

Source refresh may update file identities and test node IDs. It may not choose
a build backend, runtime location, Actor projection, source disposition,
process entrypoint or residue policy: those decisions are frozen in this pack.
If current facts invalidate one, set S1 to `REPLANNING`; do not invent an alias
or broaden the plan silently.

The first refresh is recorded in `00-source-snapshot.md`. It discovered
F-026–F-028. The bounded prerequisite is defined by:

- `00-entry-baseline-repair-plan.md`;
- `ENTRY-BASELINE-GOAL-PACKET.md`.

The prerequisite was accepted in `ENTRY-BASELINE-ACCEPTANCE.md`. The formal
source identity, verification matrix and Goal Packet passed
`S1-READY-REVIEW.md`. Package, source-root, runtime-activation and
Actor-projection migration was authorized only through packet
`BS-MM-S1-20260728-01`; that packet stopped before C2 and is no longer
executable.

Current execution control:

- `S1-REPLAN-REVIEW.md`;
- `S1-E1-RETURN-REVIEW.md`;
- `S1-E2-PREFLIGHT.md`;
- `S1-E2-SOURCE-SNAPSHOT.md`;
- `S1-E2-REPAIR-PLAN.md`;
- `S1-E2-GOAL-PACKET.md`;
- `S1-E2-READY-REVIEW.md`;
- `S1-E2-ACCEPTANCE.md`;
- `S1-C2-READY-PREFLIGHT.md`;
- `S1-C2-C5-SOURCE-SNAPSHOT.md`;
- `S1-C2-C5-CONSUMER-MANIFEST.md`;
- `S1-C2-C5-PREFLIGHT.md`;
- `S1-C2-C5-IMPLEMENTATION-PLAN.md`;
- `S1-C2-C5-GOAL-PACKET.md`;
- `S1-C2-C5-READY-REVIEW.md`;
- `S1-C2-C5-EXECUTION-STATE.md`;
- `S1-C2-C5-ACCEPTANCE.md`.

`S1-E1-REPAIR-PLAN.md`, `S1-E1-GOAL-PACKET.md`, and
`S1-E1-READY-REVIEW.md` are historical records of the stopped bounded repair.
The replacement E2 design and isolated preflight are accepted. The
coordinating hub prepared and evidence-reviewed one bounded E2 implementation
plan and Goal Packet. Packet `BS-MM-S1-E2-20260728-01` returned and was
accepted by the hub. F-034/R-PKG-019 are closed and C1 is accepted. Do not
execute that consumed packet or resume the retired formal packet. The hub must
not issue standalone C2: F-035 proves the old technical checkpoint order
deletes live process and Actor inputs before their consumers cut over. The
minimum runnable replacement boundary is C2 move + C3 process + C4 projection
+ C5 lifecycle proof in one source-bound packet. The maintainer accepted that
boundary as D-038. Complete preservation evidence and isolated preflight
`C2C5P-d24c5a85fec6b34a` passed. Packet
`BS-MM-S1-C2C5-20260728-01` then executed, returned at C5 and was accepted by
the coordinating hub. It is consumed and cannot be resumed. The next
permissible action is C6 source refresh, plan/Goal Packet preparation and
READY review.

The formal refresh additionally closed four plan-execution ambiguities before
handoff:

- static package policy remains in the process-free unit tier, while actual
  build/install/activation proof lives under `tests/process/package/**`;
- runtime provisioning is an explicit pre-launch PEP 517/venv/install/activate
  setup operation, never a launcher fallback or Actor side effect;
- the root test runner is a test-only repository interface using the activated
  interpreter; production launchers and child processes remain package-only;
- shell wrappers select only deterministic `venv/bin/python`; the installed
  package alone parses and verifies activation JSON.
