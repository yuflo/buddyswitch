# Evidence-Backed READY Gate Adoption and E2 Preflight Implementation Plan

> Status: COMPLETE
> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task by task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make evidence-backed READY and the patch-on-patch loop breaker the
single migration handoff rule, then prove the accepted E2
source/distribution-correspondence design without changing product runtime
code.

**Architecture:** Existing governance documents and templates remain the only
live policy owners. The coordinating hub runs one isolated, final-shaped
setuptools/wheel/install prototype and records its source-bound evidence; only
that evidence can unlock preparation of an E2 implementation packet.

**Tech Stack:** Markdown governance, Python 3.13, `setuptools.build_meta`,
wheel `RECORD`, isolated venv, existing BuddySwitch source-identity rules.

---

## Scope and source

```text
Worktree:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

HEAD:
9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3

Accepted design:
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
00-evidence-backed-ready-gate-design.md

Product/runtime/test implementation changes:
forbidden

Commit/stage changes:
forbidden while the accepted E0/C1/E1 dirty candidate and coordinating-owned
untracked migration documents share this worktree
```

## Task 1: Adopt one evidence-backed READY owner

**Files**

- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/decision-log.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/00-execution-governance.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/00-coordination-hub.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/00-program-readiness.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/stage-goal-packet-template.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/stage-implementation-plan-template.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/00-evidence-backed-ready-gate-design.md`

- [x] **Step 1: Accept the migration decision**

Add D-037:

```text
READY requires complete affected preservation evidence, a material
positive/negative/correspondence boundary matrix and representative
final-topology preflight; no architecture question may be delegated to an
executor. A second specification invalidation at the same boundary forbids
another patch-on-patch packet until the boundary architecture and end-to-end
preflight are accepted.
```

- [x] **Step 2: Replace the READY review contract**

In `00-execution-governance.md`, keep the existing `PREPARE -> READY` states
but require:

```text
complete affected pre-mutation preservation baseline
material boundary-contract matrix
representative final-topology probe
source-bound evidence identities
zero delegated architecture questions
```

Add the loop breaker exactly once under change control. Stop conditions remain
damage containment and cannot be cited as READY evidence.

- [x] **Step 3: Update hub and R4 responsibilities**

Make the hub own those preflights before it issues a packet. Make R4 require
an executable entry baseline and material boundary evidence rather than
document consistency alone.

- [x] **Step 4: Update both templates**

The Goal Packet template must carry exact pre-READY evidence identities. The
implementation-plan template must separate:

```text
hub-owned preflight already passed
executor-owned RED/GREEN still to implement
```

Neither template may add a new evidence ledger, reviewer task or lifecycle
state.

- [x] **Step 5: Mark the design adopted**

Change the design status to accepted/adopted and name
`00-execution-governance.md` as the live owner.

- [x] **Step 6: Verify policy consistency**

Run:

```bash
rg -n \
  'SPEC_VALIDATED|patch-on-patch|pre-READY|final-topology|delegated architecture' \
  docs/memo/2026-07-28-buddyswitch-modular-monolith-migration
git diff --check
```

Expected:

- no new lifecycle state is introduced;
- patch-on-patch prohibition and evidence-backed READY have one semantic owner
  and consistent projections;
- no whitespace error.

## Task 2: Prove E2 correspondence in isolation

**Files**

- Create temporarily:
  `/private/tmp/buddyswitch-s1-e2-preflight-20260728/probe.py`
- Create temporarily below the same root: source, wheel and venv fixtures
- Delete or move the entire temporary root to Trash after evidence capture
- Do not modify: `pyproject.toml`, `src/**`, `tests/**`, runner or active runtime

- [x] **Step 1: Record executable source identity**

Record HEAD, tracked patch SHA-256, index SHA-256, non-memo path-set/content
identity and Python/setuptools/wheel versions before the probe.

- [x] **Step 2: Build a final-shaped isolated fixture**

Use `setuptools.build_meta`, one `src/buddyswitch` package and explicit package
data. The fixture must contain:

```text
buddyswitch/__init__.py
buddyswitch/launcher/__init__.py
buddyswitch/launcher/assets/docs/help.md
buddyswitch/modules/__init__.py
buddyswitch/modules/probe/__init__.py
buddyswitch/modules/probe/tests/__init__.py
buddyswitch/modules/probe/tests/test_probe.py
buddyswitch/modules/probe/__pycache__/probe.pyc
```

Build one wheel, install it non-editably into one fresh venv, and confirm:

```text
launcher/assets/docs/help.md is installed
modules/probe/tests/** is not installed
__pycache__ and *.pyc are not installed
build backend remains setuptools.build_meta
```

- [x] **Step 3: Prototype the exact correspondence owner**

The source side must:

- walk every package-source entry without following symlinks;
- reject file or directory symlinks before exclusions;
- exclude only co-located `tests` subtrees, `__pycache__` and `.pyc`;
- produce `relative-path -> bytes`.

The installed side must:

- use distribution `RECORD` for recorded `buddyswitch/**` files;
- reject missing recorded files and installed symlinks;
- scan the installed package root for unrecorded files;
- produce the same package-relative `path -> bytes`.

Correspondence succeeds only when both path sets and all bytes are equal.

- [x] **Step 4: Run the discriminating scenario matrix**

The probe must independently prove:

| Scenario | Expected result |
|---|---|
| baseline including `assets/docs/help.md` | PASS |
| co-located tests/cache | absent and ignored |
| source-only regular file | FAIL |
| installed-only unrecorded file | FAIL |
| source file missing | FAIL |
| installed recorded file missing | FAIL |
| source byte drift after install/before activation | FAIL |
| installed byte drift | FAIL |
| source file symlink | FAIL |
| source symlink inside an otherwise excluded real tests subtree | FAIL |
| source directory symlink | FAIL |

Reset only the isolated fixture between scenarios so one failure cannot mask
the next.

- [x] **Step 5: Capture and clean**

Record exact command, result, scenario count, toolchain, source identity and
cleanup. Remove the temporary root and confirm no probe process remains.

Any unexpected success, setup ambiguity or cleanup residue keeps E2 in
`REPLANNING` and forbids an implementation plan.

## Task 3: Record the E2 gate result

**Files**

- Create on GREEN only:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/01-single-package-runtime-cutover-plan/S1-E2-PREFLIGHT.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/01-single-package-runtime-cutover.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/01-single-package-runtime-cutover-plan/01-package-contract.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/01-single-package-runtime-cutover-plan/S1-REPLAN-REVIEW.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/migration-ledger.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/residue-register.md`
- Modify:
  `docs/memo/2026-07-28-buddyswitch-modular-monolith-readiness-audit/finding-register.md`

- [x] **Step 1: Record proof without authorizing implementation**

The preflight record contains the evidence identity, algorithm boundary,
scenario results, cleanup and remaining risk. It states:

```text
design feasibility accepted
F-034 and R-PKG-019 remain OPEN until executable E2 GREEN
C1 remains reopened
C2 remains not started
no Goal Packet is authorized
```

- [x] **Step 2: Replace the ambiguous package contract**

Remove blanket package-internal `docs/projects` exclusions. Keep repository
root docs/projects outside `src/buddyswitch`; exclude only co-located tests and
caches from runtime correspondence. Require exact source/install
path-and-byte equality and fail all package-source symlinks.

- [x] **Step 3: Retire stale execution directions**

Make `S1-REPLAN-REVIEW.md` historical for E1 execution, point current control
to the E1 return and E2 preflight records, and ensure no text authorizes the
stopped S1 or E1 packets.

- [x] **Step 4: Verify the adoption candidate**

Run artifact-specific checks:

```bash
rg -n 'execute only|authorized|READY|REPLANNING|docs/projects|correspond' \
  docs/memo/2026-07-28-buddyswitch-modular-monolith-migration
rg -n 'F-034|R-PKG-019|S1-E2-PREFLIGHT' \
  docs/memo/2026-07-28-buddyswitch-modular-monolith-migration \
  docs/memo/2026-07-28-buddyswitch-modular-monolith-readiness-audit
git diff --check
```

Expected:

- one current S1 state: `REPLANNING`;
- no executable S1/E1/E2 packet;
- no blanket package-internal docs exclusion;
- E2 feasibility evidence is exact and cleanup is clean.

## Acceptance

This plan is complete when:

1. existing governance owners enforce evidence-backed READY and the loop
   breaker without a new state or policy owner;
2. the E2 mechanism passes all isolated scenarios on the recorded source and
   toolchain;
3. S1 remains `REPLANNING` with no executable packet;
4. the next permissible action is writing and reviewing one E2 implementation
   plan, not executing product changes.
