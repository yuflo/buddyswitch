# S1 E1 Return Review

> Review authority: coordinating hub
> Returned packet: `BS-MM-S1-E1-20260728-01`
> Decision: prerequisite REJECTED; F-033 accepted; F-034 expanded

## 1. Repository and scope

The executor's identity report matches the current repository:

```text
HEAD:
9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3

tracked patch:
400730f42c705596458f4eaae174017ee7f7606a10b10b1232a507a04421de4e

index:
empty

non-memo untracked paths:
12

non-memo path-set SHA-256:
4fc3101e7c5dc95d8a621ceeb42ded5c1c2d065fbb41d5a7a418d3256e5012e0

non-memo path/content manifest SHA-256:
d3c0ed3ac4b7ed44dfb972f936b01dd9af8c1bcdb1e5d93be08bc993c3594f33
```

Only the eight E1-authorized files changed. HEAD, branch and index remained
unchanged. No C2 source movement, old-root deletion, commit or stage occurred.

## 2. F-033 accepted

The E1 diff changes only the two stale Demand proof projections:

```text
global actions: list/get/resolve_inbound/complete
idempotent writes: resolve_inbound/complete
```

Production Demand, registry, authorization and MCP code did not change.

Source-bound evidence:

```text
reused RED c6e52cb80ffd4f33ba0b19caa83e5249
7 failed, 23 passed, 407 subtests

GREEN af024ab2e7874b01a658f88f4cbafe5e
27 passed, 465 subtests
```

F-033 is CLOSED. The complete C2 pre-move group remains unrun because F-034
stopped E1 first.

## 3. F-034 remains open

E1's intended nested-test boundary has valid partial evidence:

```text
RED 9028d706676a4d8eac5b3bf204a93148
3 failed, 5 passed

GREEN 3405808c51994d9d8082839f73786b18
8 passed
```

That GREEN is insufficient for C1 acceptance. The executor correctly found a
new contradiction before running the C1 milestone:

```text
buddyswitch/launcher/assets/docs/help.md
buddyswitch/linked_package/__init__.py
```

Both files entered a real wheel while changes to their source content left the
activation source digest unchanged.

The hub independently reproduced the same result in an isolated source:

```text
wheel: explicit launcher asset present
wheel: directory-symlink package present
source digest before mutation:
a93665c66ee9d0eac8c8708a8004e2c30d023276febfe465fe13c3ee1b6b8b42
source digest after asset mutation:
a93665c66ee9d0eac8c8708a8004e2c30d023276febfe465fe13c3ee1b6b8b42
source digest after symlink-target mutation:
a93665c66ee9d0eac8c8708a8004e2c30d023276febfe465fe13c3ee1b6b8b42
```

The hub also built and installed a clean wheel, changed
`src/buddyswitch/__init__.py` before first activation, and observed:

```text
runtime.activate return code: 0
kind: runtime.activate
ok: true
```

The activation record therefore stores a source digest and distribution digest
without proving they describe corresponding runtime files.

## 4. Root cause

E1 encoded the wrong invariant in two ways:

1. It interpreted repository-root `docs/**` and `projects/**` exclusions as
   every path segment named `docs` or `projects` below the package. Explicit
   runtime assets such as `launcher/assets/docs/**` are legitimate package
   inputs and must affect runtime identity.
2. `_source_inputs` builds an independent recursive digest, filters before
   complete symlink validation, and never compares its relative paths or bytes
   with the installed package manifest. Directory symlinks and any
   build/install-to-activate source change can therefore escape
   correspondence.

The corrected invariant is not another name filter:

> Every regular non-test file below `src/buddyswitch/**` must correspond by
> exact package-relative path and bytes to one installed package file; every
> installed package file must have that source counterpart; every symlink
> below the package source fails closed; co-located tests and caches remain
> non-runtime.

Root `docs/**`, root `projects/**`, wrappers and runtime state are already
outside `src/buddyswitch/**`; they do not need segment-name filtering inside
the package.

## 5. Acceptance and next gate

E1 is REJECTED as a complete prerequisite. F-034 and R-PKG-019 remain OPEN.
C1 remains reopened; C2 was not started; S1 remains REPLANNING.

No E2 implementation contract is frozen by this review. The maintainer must
select the source/distribution correspondence design. The hub then writes and
reviews one bounded E2 plan and Goal Packet against the identity above.

## 6. Verification and cleanup

- current installed runtime `verify` succeeds for the partial E1 candidate;
- `git diff --check` passes;
- executor test/build/process cleanup is clean;
- the hub's isolated probe and one-off pre-activation environment are absent
  from temporary roots;
- `full`, the C1 milestone and both C2 groups were not run after the stop.

The surviving runtime `verify` proves only self-consistency of the current
partial record. It does not override the source/distribution disagreement.
