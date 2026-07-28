# S1 C2–C5 Atomic Cutover Source Snapshot

> Snapshot state: FROZEN FOR C2–C5 READY REVIEW
> Runtime implementation authorization: this snapshot alone grants none
> Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-tool`

## 1. Executable source identity

```text
branch:
fea-tool

HEAD:
9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3

tracked patch SHA-256:
46f8cbda03078a0db6352ea5e349558616f86fa56d493fafdb35a6871f5029eb

index patch SHA-256:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

non-memo untracked paths:
12

non-memo path-set SHA-256:
b1f4e9eaec7c55d6f845269d2a8b2d7df42a913c8d6ed95746a45a8b87f464b2

non-memo length-framed path/content SHA-256:
4bd55023545f2df66c3a0efdfa86f8588f62cde566ecf124eade7b77a7bbd9e0
```

The tracked patch contains the accepted E0 repair, accepted F-033 proof
correction and the F-036 one-line process-test correction. The twelve
non-memo untracked paths are the accepted C1 package/runtime implementation
and proof candidate. The index is empty.

The path/content identity is computed over sorted non-ignored untracked paths
outside `docs/memo/**`. For every path it hashes, in order:

```text
8-byte big-endian path length
8-byte big-endian content length
UTF-8 path bytes
raw content bytes
```

Coordinating-owned memo files are excluded because READY preparation changes
them. The executor must record and preserve their full starting identity, and
may edit only `S1-C2-C5-EXECUTION-STATE.md`.

## 2. Frozen runtime-source partition

The exact tracked source/resource roots contain:

```text
paths: 228
sorted-NUL path-set SHA-256:
449257b47b957085b2f2596b6c275606eec0dd007f453cb037e44ed33b389477

length-framed path/content SHA-256:
809109763588220b2b74264ed2183d3fa3e9b4e091cdab37adc158d911894239

MOVE: 223
DELETE: 5
target collisions: 0
unmatched: 0
```

The deterministic mapping is frozen in
`02-source-and-asset-move-map.md`. Its five deletes are:

```text
framework/agent-registry.md
scripts/env_legacy_store.py
scripts/env_store.py
scripts/runtime_store/__init__.py
tools/__init__.py
```

Any new, missing, unmatched or colliding source path retires the packet.

## 3. Complete affected preservation evidence

All commands used the sole public test entry.

| Group | Run ID | Result |
|---|---|---|
| accepted C1 package/install/activation | `edc222ac236d4422a5bb9da00e19a26d` | 56 passed, 29 subtests |
| original C2 unit group | `874221ab1d224e90b2258e771cd9b597` | 314 passed, 1035 subtests |
| complementary unit domains | `2f3a913a614949029aaafe71b3679d36` | 113 passed, 94 subtests |
| original C2 integration group | `ffc941cb10b443598e8fcf9e2434404a` | 353 passed, 276 subtests |
| complementary integration domains | `2ed69e58d50a4faf8f1c3a11800159b0` | 403 passed, 164 subtests |
| complete process consumer group | `6768ab5bf5284b3987f1022708caa792` | 250 passed, 379 subtests |
| complete system lifecycle group | `daa2d57225484b38943edd65da7020b4` | 20 passed |

The one process-test edit after the unit/integration runs changes no product,
unit or integration target. Its exact RED/GREEN is:

```text
RED 284ed5522cf44a009fb1c2a7d5567891:
task_sys.close correctly rejected; stale fixture expected private import

GREEN e14d3fb26b0e43c992889e2ecca2dd31:
1 passed, 9 subtests using current task_sys.list
```

All named run roots are absent. No BuddySwitch process, socket, PID, lock or
temporary preflight root remains. `git diff --check` passes.

## 4. Material toolchain

```text
Python: 3.13.5
pip: 25.1
setuptools: 78.1.1
wheel: 0.45.1
pytest: 9.0.3
```

The accepted checkout-local runtime verifies successfully before mutation.
It is generated runtime state, not source truth.

## 5. Invalidation

This snapshot is invalidated by:

- HEAD, tracked/index hash or twelve-path non-memo identity disagreement;
- any changed 228-path partition or target collision;
- an active BuddySwitch process/resource at executor start;
- a new failing or cleanup-residual result in an affected group;
- any requirement for a compatibility path, copied implementation or
  canonical data movement.
