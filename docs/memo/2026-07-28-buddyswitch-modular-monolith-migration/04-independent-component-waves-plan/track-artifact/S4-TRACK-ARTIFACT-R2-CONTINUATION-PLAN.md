# S4 Track–Artifact R2 Test-Boundary Correction Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and `$buddyswitch-testing` to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the complete R1 Track–Artifact product candidate while
making test ownership match the approved independent-module boundary.

**Architecture:** Module-local tests may depend on their own Private
implementation and other modules' Public contracts. Tests requiring another
module's Private fixture or proving a multi-module path remain in the root
test tiers; root architecture proof enforces this distinction.

**Tech Stack:** Python 3.13, AST-based architecture tests, BuddySwitch public
test runner, existing non-editable product runtime.

---

## Task 0 — Verify the continuation identity

- [ ] Read the ordered authority in the R2 Goal Packet.
- [ ] Reproduce HEAD, origin, branch, non-memo tracked patch, index and
  non-memo untracked identities from the READY review.
- [ ] Confirm the only additional dirty state belongs to coordinating
  `docs/memo/**` files and preserve it untouched.
- [ ] Run installed `runtime_activation verify`; require the R1 runtime:
  source `e36160bf6172d497827394eb687fe073082a60faa136a91965390c833f14fa1f`
  and distribution
  `2d09c0a2e120ffa64a8868c221d58a1ece590a28a3f42ee1f069e9241a774b13`.
- [ ] Confirm zero active instances, inactive Browser and no attributable
  test/build process or root.
- [ ] Stop before mutation on any mismatch.

## Task 1 — Make the escaped invariant observable

- [ ] Modify the two Track/Artifact architecture proof files within R2 scope
  so they enforce the six requirements in READY review section 6.
- [ ] Do not move tests yet.
- [ ] Run:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_track_component_boundaries.py \
  tests/unit/architecture/test_artifact_component_boundaries.py
```

- [ ] Record RED only when it fails because current module-local tests import
  another module's Private package or because cross-component tests occupy the
  module-local paths. Collection, environment or unrelated failures are not
  valid RED.
- [ ] Clean the run root and record the exact run identity.

## Task 2 — Correct physical test ownership

- [ ] Move the ten cross-component tests exactly as listed in READY review
  section 5; do not copy them and do not change assertions.
- [ ] Update imports only for the final root paths, including the shared
  Artifact test case import.
- [ ] Keep Track comment/repository tests and Artifact selection test in their
  module roots.
- [ ] Remove only empty module test directories or package markers made
  unnecessary by these moves.
- [ ] Confirm no module-local Track/Artifact test imports another module's
  Private package.
- [ ] Confirm the root cross-component tests exist once and the old
  module-local copies are absent.
- [ ] Parse every changed Python test and run `git diff --check`.

## Task 3 — Prove exact and affected behavior

- [ ] Re-run the exact architecture command from Task 1 and require GREEN.
- [ ] Dynamically discover runner-valid targets from the final changed test
  paths and their direct current consumers.
- [ ] Run the moved root cross-component tests, the remaining module-local
  tests and the two changed architecture proofs through
  `./buddyswitch-test focused`.
- [ ] Add only direct package/collection or consumer targets required by
  current target discovery.
- [ ] Treat any failure, timeout, flake, no-test result or cleanup residue as
  new evidence. Diagnose before rerunning.
- [ ] Repair only test locations/imports or the two architecture proofs.
  Assertion weakening, production mutation or runner change stops execution.
- [ ] Record exact commands, targets, run IDs, results, source identity and
  cleanup.

## Task 4 — Freeze and run one new FINAL

- [ ] Confirm no remaining in-scope edit or review finding.
- [ ] Confirm installed runtime correspondence; do not rebuild or reprovision
  because R2 changes no packaged source.
- [ ] Record final HEAD, non-memo tracked patch, index, non-memo untracked
  manifest and `git diff --check`.
- [ ] Run exactly once:

```bash
./buddyswitch-test full
```

- [ ] Preserve the complete result whether pass or fail.
- [ ] Make no executable/test/package mutation and do not rerun FINAL.
- [ ] Prove every attributable test root, process, socket, lock, instance,
  Browser state and temporary root is clean.
- [ ] Return the required result packet to the coordinating hub.

## Stop conditions

Stop once and return `REPLANNING REQUIRED` when:

- starting candidate/runtime/resource identity does not match;
- valid RED requires changing product behavior;
- a source/package/asset/runtime mutation is required;
- an assertion must be removed or weakened;
- the public runner rejects a target after current-path validation;
- an unrelated test or external failure cannot be separated;
- cleanup cannot be made exact;
- FINAL fails.

Do not loop in blocked turns. Do not rollback or reconstruct R1. Do not create
an R3 patch.
