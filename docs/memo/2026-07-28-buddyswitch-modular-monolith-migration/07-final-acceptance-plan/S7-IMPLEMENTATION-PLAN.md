# S7 Final System Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to execute this validation plan task by task.
> Follow root `AGENTS.md` and `$buddyswitch-testing`.

**Goal:** Prove on one frozen committed candidate that the explicit packaged
modular monolith and narrow RoleHost are the only live BuddySwitch system.

**Architecture:** S7 is validation-only. Existing product modules, Foundation,
Application composition and RoleHost remain unchanged; focused proof establishes
the final topology, then one repository FINAL establishes the complete product
and operations claim. Any material defect reopens its owner instead of being
patched inside S7.

**Tech stack:** Python 3.13.5, pytest 9.0.3, Node v24.13.1, activated
non-editable BuddySwitch distribution, existing `./buddyswitch-test`.

---

## 1. Stage identity

```text
Stage:               S7 / final system acceptance
Charter:             ../07-final-acceptance.md
State:               READY — R2 VALIDATION ONLY
Candidate checkpoint:7efd2a038e4604b0c3a20c8fb678980638113a2e
Executable source:   unchanged from 6a51244192f5bad36a4438f030183acc4c5f9529
Source dirty diff:   none; later packet commit may be memo-only
Owning capability:   repository-wide acceptance only; no implementation owner
Stage executor:      one independent session
Migration lead:      coordinating hub
Integration owner:   coordinating hub
Plan review date:    2026-08-13
```

## 2. Acceptance sentence

> Product, Contract, Architecture, Replacement and Operations evidence agree
> that the packaged explicit modular monolith and narrow RoleHost are the only
> live BuddySwitch architecture.

Consumer path:

```text
public CLI/Web/IM/Actor action
  -> explicit Application composition
    -> one product module or product-neutral Foundation owner
      -> one installed runtime and canonical state/effect
        -> terminal consumer result and clean resources
```

## 3. Scope ledger

S7 has an intentionally empty write ledger.

```text
OWNER:                 no writes
CONSUMER:              no writes
HOST CONTRACT:         no writes
COMPOSITION:           no writes
PROOF:                 execute existing tests; do not edit them
CURRENT DOC:           inspect only; coordinating hub owns final promotion
SHARED/INTEGRATION:    no writes
UNRELATED DIRTY WORK:  none at READY
```

Forbidden writes include the entire repository, generated runtime identity,
user state and master migration truth. Test-created resources may exist only
inside runner-owned temporary roots and must be cleaned by the runner.

## 4. Protected behavior

- Role list/start/bootstrap remains RoleHost-derived and fail-closed.
- Actor workspaces contain selected Role/Skill/config/private/project
  projections and no BuddySwitch implementation.
- Tools, Daemon, Broker, Browser, Web/CLI and component state preserve their
  current success, rejection, authority, persistence, recovery and cleanup.
- One package/source/runtime identity remains exact.
- No retired name, path or fallback becomes reachable.

No internal Python import path is protected; no import path changes in S7.

## 5. Task sequence

### Task 1: Admit the exact committed candidate

- [ ] Confirm the branch, HEAD and upstream relationship from repository facts.
- [ ] Confirm tracked, index and untracked state are empty and `git diff --check`
  is clean.
- [ ] Run canonical runtime verification and compare all material identity fields
  to the source snapshot.
- [ ] Confirm the declared Python, pytest and Node versions.
- [ ] Inventory pre-existing test roots and attributable processes without
  deleting unrelated ignored or user state.
- [ ] Stop if source, runtime, dependency or resource identity differs.

### Task 2: Prove the final architecture and package boundary

- [ ] Rediscover current runner-valid targets for the claims in
  `S7-PROOF-MATRIX-AND-PREFLIGHT.md`; the known current target group is review
  input, not an immutable shell transcript.
- [ ] Run one focused group covering all current architecture owners, clean
  distribution contents and activation drift rejection.
- [ ] Confirm source/install correspondence, explicit composition, Foundation
  neutrality, Role-local extension, one test runner and retired-root absence.
- [ ] Record exact command, run ID, result, duration, source/runtime identity and
  cleanup.
- [ ] Stop on any failure, no-collection result, unexplained flake, timeout or
  residue. Do not edit or rerun blindly.

### Task 3: Freeze and run the one repository FINAL

- [ ] Reconfirm no repository or runtime mutation occurred after focused proof.
- [ ] Reconfirm no attributable process or prior runner root remains.
- [ ] Freeze the candidate identity.
- [ ] Run exactly one `./buddyswitch-test full`.
- [ ] Confirm every current tier completed: Python unit, JavaScript unit,
  Role-local contract, integration, process, system, shell syntax and diff
  hygiene.
- [ ] Confirm the FINAL includes the representative investor Role start and
  Web Actor→Goal→Demand product journey through the current system tier.
- [ ] Capture terminal cleanup and runtime identity. A test failure or cleanup
  contradiction stops S7 and reopens the owning stage; it is not repaired here.

### Task 4: Return an acceptance proposal without changing truth

- [ ] Inspect root/current architecture/Role guidance against executable facts.
- [ ] Propose R-DOC-005 closure only if all proof classes pass.
- [ ] Return every command, run identity, failure/timeout/flake/residue signal,
  cleanup result, omitted check and residual risk.
- [ ] Propose `ACCEPTED` or `REJECTED` and stop.
- [ ] Do not edit the migration ledger, decision log, residue register, stage
  charter, architecture docs or acceptance record; do not commit or push.

## 6. Verification boundary

Only these public test forms are permitted:

```bash
./buddyswitch-test focused <executor-discovered current targets>
./buddyswitch-test full
```

No product/test mutation is authorized, so runtime reprovision is inapplicable.
If any `src/buddyswitch/**` mutation is observed, stop: the S7 candidate has
been invalidated.
