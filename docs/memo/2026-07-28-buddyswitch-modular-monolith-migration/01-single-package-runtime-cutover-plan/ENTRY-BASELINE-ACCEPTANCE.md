# S1 Entry Baseline Repair Acceptance

> Decision: ACCEPTED
> Packet: `BS-MM-S1-E0-20260728-01`
> Authority: coordinating hub
> Formal S1 state after acceptance: PROPOSED

## 1. Accepted outcome

> The accepted current Web/CLI boundary, Parent/Main Tool catalog and direct
> Tool dispatch contract are mutually consistent and pass their exact and
> affected proofs without beginning package/runtime migration.

## 2. Source identity

```text
worktree: /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
branch: fea-tool
HEAD: 9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3
tracked patch:
7c861a672c53231aea422660f38ae3c2f0114837d67a4f5f84992da866c785ab
index patch:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
untracked paths: 44 coordinating-owned docs/memo files
untracked path-set:
d5ffa90cba59cdd2af4c36a32fc7165a6b16bcdd63f84c48a1475db6752844ff
```

## 3. Reviewed diff

Only:

```text
scripts/runtime_kernel/__init__.py
tests/integration/runtime/test_runless_contract.py
tests/unit/architecture/test_external_control.py
```

The Runtime Kernel package no longer eagerly imports/re-exports Broker. Current
search finds no consumer of the removed package-root re-export and no lazy
alias/fallback replacement.

The tests now prove:

- current Web/CLI/Actor Session/IM owner paths and forbidden calls from the
  current `docs/arch` truth;
- the global registry retains side-only `demand_sys.resolve_inbound`;
- Parent/Main Context exposes only Demand `list`, `get`, `complete` across all
  projected catalog sections;
- unrelated complete input schemas remain visible;
- direct selected/probe Tool dispatch survives independent imports.

No current architecture document, migration stage, package, Actor projection,
canonical data or external contract changed.

## 4. Verification

Executor exact GREEN evidence:

```text
F-026: 892d9d9a67ed4caaa7109b76e8343ca5
F-027: 8cb11b8a0df243c39843540661ef15a3
F-028: 5fbe008c22d14a9dab98c96c7985772a
milestone: 4afc6e2ee8824e32920bd5d87c358ba8
```

The hub inspected the live diff and ran the complete affected milestone again:

```text
run id: e0b6718a11b2498da29d09309bb7766e
result: 261 passed, 447 subtests passed
duration: 39.88s
cleanup: run root absent; no BuddySwitch process/PID/socket/lock residue
patch after run: unchanged
git diff --check: pass
```

`./buddyswitch-test full` was intentionally not run because the prerequisite
packet forbade repository-wide FINAL and the affected milestone is the exact
accepted claim.

## 5. Finding decision

```text
F-026 CLOSED
F-027 CLOSED
F-028 CLOSED
```

No new finding or residue was discovered.

## 6. Scope decision

The prerequisite is accepted. This does not accept S1, authorize runtime
migration, or authorize a commit/merge. Formal S1 may become READY only after
its repaired-source snapshot, exact Goal Packet and READY review are complete.
