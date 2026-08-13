# S7 Source and Residue Snapshot

> Historical R1 entry snapshot. Its open-row and stage-state statements record
> the pre-acceptance instant only; see `S7-ACCEPTANCE.md` for current status.

## Frozen entry identity

```text
branch:                      fea-tool
HEAD:                        6a51244192f5bad36a4438f030183acc4c5f9529
origin/fea-tool:             6a51244192f5bad36a4438f030183acc4c5f9529
tracked/index/untracked:     empty
git diff --check:            clean
predecessor:                 S6 ACCEPTED
```

The only changes after the accepted S6 executable freeze were its coordinating
acceptance/truth records and the commit itself. Canonical runtime verification
still resolves the exact accepted executable identity:

```text
activated_at:        2026-08-13T04:26:32.591975Z
source_digest:       28cbef6f68c12b9a9cdddbff94b326eb8b83453f475f1a74f62642cdccc64f38
distribution_digest: b16a15a225b592414e1fcf89347f2f2fc00d5a32750f56d4359a2c51adebf62f
package_version:     0.1.0
runtime.verify:      ok=true
```

Declared test environment:

```text
Python: 3.13.5
pytest: 9.0.3
Node:   v24.13.1
runner: ./buddyswitch-test only
```

Ignored `.buddyswitch-runtime/`, `build/` and
`src/buddyswitch.egg-info/` paths predate S7 and are not dirty source. S7 may
not delete or rebuild them merely for tidiness. At snapshot capture there was
no `bs-test-*` root and no attributable BuddySwitch/pytest/runner process.

## Current topology

The committed product has one live topology:

```text
one pyproject.toml + src/buddyswitch/**
  -> one non-editable activated distribution
  -> Application explicit composition
       -> physically aggregated product modules
       -> product-neutral Foundation owners
       -> narrow RoleHost + reviewed Role packages
  -> code-free selected Actor workspace
```

The only file below `src/buddyswitch/launcher/` is its inert `__init__.py`.
The following retired roots are absent:

```text
src/buddyswitch/runtime_support/
src/buddyswitch/catalog/
src/buddyswitch/skills/
src/buddyswitch/launcher/assets/roles/
```

All current boundaries are owned by `docs/arch/**`, root `AGENTS.md`, current
Role-package guidance and executable contracts/tests. The target-design and
migration-roadmap memos remain historical rationale plus active S7 execution
context until final hub acceptance; they do not override current executable
truth.

## Residue disposition

R-PKG-001–019, R-COMP rows, R-FND rows, R-ROLE-001–007 and R-DOC-001–004 are
closed by their accepted stages. S7 owns no product-path deletion.

The only open row is R-DOC-005:

```text
migration instructions presented as current policy after completion
```

It is intentionally still open while S7 is active. It closes only after a
passing frozen FINAL, coordinating acceptance and an explicit historical-only
promotion of this migration pack. The executor proposes that closure but does
not edit the master README, ledger, decision log or residue register.

## S7 mutation boundary

S7 performs no implementation. Any required change to `src/**`, tests,
contracts, runtime inputs, current docs or packaging is a material finding and
reopens its semantic owner. This prevents a final-acceptance task from becoming
an unreviewed cross-system patch lane.
