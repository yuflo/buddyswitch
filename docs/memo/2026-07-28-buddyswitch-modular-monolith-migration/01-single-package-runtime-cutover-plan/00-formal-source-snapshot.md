# S1 Formal Source Snapshot

> Current disposition: SUPERSEDED FOR EXECUTION by
> `S1-REPLAN-REVIEW.md`. This remains the source identity that authorized the
> stopped packet; it does not authorize resuming C2.

> Snapshot state: CURRENT FOR GOAL PACKET PREPARATION
> Captured: 2026-07-28 after accepted E0 repair
> Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-tool`

## 1. Source and dirty identity

```text
branch: fea-tool
HEAD: 9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3
tracked patch:
7c861a672c53231aea422660f38ae3c2f0114837d67a4f5f84992da866c785ab
index patch:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
tracked dirty files:
  scripts/runtime_kernel/__init__.py
  tests/integration/runtime/test_runless_contract.py
  tests/unit/architecture/test_external_control.py
```

Those three tracked changes are the accepted E0 prerequisite and are part of
the S1 starting truth. The index is empty. All non-ignored untracked files are
coordinating-owned architecture/migration documents below `docs/memo/**`;
the executor must preserve and must not stage them.

The executor records the current untracked path and content manifest again
before editing. A changed path set or changed tracked patch stops execution
unless the coordinating hub refreshed this packet.

## 2. Runtime source disposition

Current tracked implementation/runtime roots contain exactly 228 paths and
all 228 match the frozen S1 move/delete map:

```text
path-set SHA-256:
ffdcc6f0dd81b92ea80230ab1fca3ba02bf69eece13bfbb2e907849f306c5726

path/content manifest SHA-256:
298a91c631d444501d36b578df3d02482ff507828bd7cf7fa44f1feab231b8cd

unmatched paths: 0
```

The manifest covers:

```text
scripts/**
tools/launcher/**
tools/__init__.py
buddyswitch/manifest.toml
buddyswitch/env-profiles/**
buddyswitch/skills/**
framework/contracts/**
framework/config/**
framework/schemas/**
framework/agent-registry.md
```

Every path disposition remains exactly as frozen in
`02-source-and-asset-move-map.md`. A newly discovered tracked path stops S1.

## 3. Accepted preservation baseline

The hub freshly reran the complete affected E0 milestone:

```text
command: exact 21-target command in ENTRY-BASELINE-ACCEPTANCE.md
run id: e0b6718a11b2498da29d09309bb7766e
result: 261 passed, 447 subtests passed
duration: 39.88s
cleanup: run root absent; no process/PID/socket/lock residue
```

F-026, F-027 and F-028 are CLOSED. No known current baseline failure may be
carried into S1.

## 4. Build/install feasibility

Current bootstrap environment:

```text
Python: /Users/chen/miniconda3/bin/python
version: 3.13.5
pip: 25.1
setuptools: 78.1.1
wheel: 0.45.1
pytest: 9.0.3
```

The hub ran a throwaway `setuptools.build_meta` proof with a `src` package:

```text
pip wheel --no-deps --no-build-isolation: PASS
new venv: PASS
non-editable wheel install: PASS
isolated import with empty PYTHONPATH: PASS
resolved import: <throwaway-venv>/lib/python3.13/site-packages/...
cleanup: throwaway source/runtime removed
```

This proves the selected local build strategy is available. It does not prove
BuddySwitch package content; S1.1 owns that RED/GREEN.

## 5. Runtime and state preconditions

At capture:

```text
checkout-local .buddyswitch-runtime: absent
current Actor instances in this checkout: none observed
persistent BuddySwitch process: none observed
repository PID/socket/lock residue: none observed
```

Canonical user/runtime data remains protected in its current explicit roots.
S1 moves implementation and projections only. It may update locator code but
must not relocate, rewrite or dual-write canonical data.

## 6. READY corrections discovered during refresh

The formal refresh found and closed three plan-level contradictions before
handoff:

```text
F-029 / D-033: dynamic build/install proof belongs to process tier
F-030 / D-034: explicit external provisioning closes first-install bootstrap
F-031 / D-035: root test runner is the test-only .py-path exception
F-032 / D-036: shell selects deterministic venv Python; package verifies JSON
```

These corrections change no current executable behavior. Formal S1 remains
unauthorized until its Goal Packet and READY review are complete.
