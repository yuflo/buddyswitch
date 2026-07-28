# S1 E2 Exact Runtime Correspondence Acceptance

> Decision: ACCEPTED
> Packet: `BS-MM-S1-E2-20260728-01`
> Authority: coordinating hub
> Accepted checkpoint: S1 / C1
> S1 stage state after acceptance: REPLANNING for a fresh C2 packet

## 1. Accepted outcome

> BuddySwitch runtime activation now accepts one non-editable installed
> distribution only when every valid non-test file below
> `src/buddyswitch/**` corresponds by exact relative path and bytes to the
> installed package, the installed package has no unrecorded counterpart, and
> neither package tree contains a symlink.

Observed terminal paths:

```text
exact source/install correspondence
  -> installed runtime_activation activate
    -> atomic 0600 activation record
      -> verify/status return the same identity

path/content/symlink disagreement
  -> installed runtime_activation activate|verify|status
    -> exit 6 / ok=false / RUNTIME_MISMATCH
      -> no first record or byte-identical existing record
```

## 2. Source and scope identity

```text
worktree:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

HEAD:
9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3

tracked patch:
400730f42c705596458f4eaae174017ee7f7606a10b10b1232a507a04421de4e

index:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

non-memo paths:
12

non-memo path set:
b1f4e9eaec7c55d6f845269d2a8b2d7df42a913c8d6ed95746a45a8b87f464b2

executor final non-memo content manifest:
7b5f6bba783b2d1010168399259a35e3317cf8a27ce6b2de996e1ab8fe0b2849
```

The hub reproduced HEAD, tracked/index identities, the twelve-path set and
the final hashes of all six writable files:

```text
27edbec5a20cb3adef135702c41cbc89097c90213af371e068eaeaaeaf4cd7af
  pyproject.toml
be91375b178a2ec071f13f7e3bc31dcc1e90ac8844be6e8c4f486db3fb1ce222
  src/buddyswitch/foundation/process_runtime/activation.py
19d69e6800811e06ddcb81681380429ff887988623db0e65915ccaacea92a421
  tests/support/package_runtime.py
50b36e6d8c63c56e8071ec36a8b3f0d9cce6d58cd441f91321f498109b1e472c
  tests/unit/architecture/test_package_contract.py
e3de6351be6163073df2376637957629b26a6d0490f83e1f107b93a1b8cf5d0a
  tests/process/package/test_distribution_install.py
9098fdbd1080b46251cb2c85cc92e6715951c7f89d35003d295e207adee1c50f
  tests/process/package/test_runtime_activation.py
```

No seventh executable/test file, C2 source movement, Demand change, commit,
stage or branch change occurred. Coordinating-owned migration documents were
preserved by the executor.

## 3. Product and contract proof

| Claim | Evidence | Result |
|---|---|---|
| required runtime asset ships and participates in identity | wheel proof plus `launcher/assets/docs/help.md` mutation | PASS |
| co-located tests/cache do not ship or affect identity | distribution and verify proofs | PASS |
| source/install path sets and bytes correspond | source/installed add, missing and byte-drift cases | PASS |
| every source-tree symlink fails before exclusion | file, directory and excluded-tests-subtree cases | PASS |
| disagreement is terminal failure | exit 6, `ok=false`, `RUNTIME_MISMATCH`, exact details | PASS |
| failed activation does not mutate durable truth | no first record or byte-identical existing `activation.json` | PASS |
| public activation contract remains current | activate/verify/status, schema 1, record fields and 0600 mode unchanged | PASS |

## 4. Architecture and replacement proof

The hub reviewed the current implementation against
`S1-E2-REPAIR-PLAN.md`:

- `pyproject.toml` remains the only build/content declaration;
- `_source_package_manifest` is the only valid source-content selector;
- `_distribution_manifest` owns raw wheel `RECORD` plus actual installed-tree
  validation;
- `_require_package_correspondence` compares the two manifests once at the
  activation boundary;
- `_source_inputs`, `NON_RUNTIME_SOURCE_PARTS`, the ambiguous fixture and the
  false package-internal `docs/projects` exclusions are absent;
- no custom backend, generated manifest, setuptools parser, fallback or
  compatibility owner was added.

F-034 and R-PKG-019 therefore satisfy their executable closure obligations.
C1 is accepted as a checkpoint. This does not accept S1 or authorize C2.

## 5. Verification evidence

The current candidate matches the executor's recorded final identity, so the
hub reused source-bound public-runner evidence rather than rerunning unchanged
commands merely because the reviewer changed.

```text
RED:
ce3cebb704524413a54bc108b67739a5
5 failed, 1 passed
intended correspondence/exclusion/symlink failures only
cleanup: run root absent

direct GREEN:
84b9556aa9754168a7af46bec4179aa0
11 passed
cleanup: run root absent

C1 MILESTONE:
edc222ac236d4422a5bb9da00e19a26d
56 passed, 29 subtests passed
cleanup: run root absent

C2 unit preservation:
874221ab1d224e90b2258e771cd9b597
314 passed, 1035 subtests passed
cleanup: run root absent

C2 integration preservation:
ffc941cb10b443598e8fcf9e2434404a
353 passed, 276 subtests passed
cleanup: run root absent
```

Hub current-runtime verification returned:

```text
ok: true
source digest:
1e32824cbdc3442dddf1f6cbaf0758e4c6c19519fec1f4ea0d164e2335e22204
distribution digest:
aad81cb22e59acbeb8b3353703e87cdb7c1ce24d0a18c79b300fb81f7036f8f8
package version: 0.1.0
activation schema: 1
```

Hub residue scans found no retired source selector or ambiguous probe name.
`git diff --check` passes. The index and active test/build temporary-root set
are empty.

## 6. Omitted checks and residual risk

`./buddyswitch-test full` was intentionally not run. E2 is a C1 checkpoint,
not a frozen merge/release candidate or repository-wide S1 acceptance. The
direct, complete C1 and complete pre-move C2 groups prove the accepted scope.

No material E2 proof remains blocked. The remaining risk belongs to unstarted
C2–C6 migration work, not this correspondence boundary.

## 7. Finding, residue and transition decision

```text
F-034: CLOSED
R-PKG-019: CLOSED
C1: ACCEPTED
S1: remains REPLANNING
BS-MM-S1-E2-20260728-01: consumed; no longer executable
C2: not authorized
```

The next permissible action is a source refresh and evidence-backed READY
review for one bounded C2 Goal Packet. The retired formal S1 packet must not be
resumed.
