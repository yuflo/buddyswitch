# S1 E2 Formal Source and Preservation Snapshot

> Snapshot state: FROZEN FOR E2 PLAN REVIEW
> Runtime implementation authorization: this snapshot alone grants none; see
> historical `S1-E2-READY-REVIEW.md` and current `S1-E2-ACCEPTANCE.md`
> Preflight: `E2P-1c5a001693442adc`

## 1. Executable source identity

```text
repository:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

HEAD:
9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3

tracked patch SHA-256:
400730f42c705596458f4eaae174017ee7f7606a10b10b1232a507a04421de4e

index patch SHA-256:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

non-memo untracked paths:
12

non-memo path-set SHA-256:
b1f4e9eaec7c55d6f845269d2a8b2d7df42a913c8d6ed95746a45a8b87f464b2

non-memo path/content manifest SHA-256:
8fba07ee7143c6efa7bd57f75a4fbf578b7c8e69a6588ff6ede390b04f665508
```

The twelve non-memo paths are the current partial C1/E1 package,
activation and proof candidate. The tracked patch contains the accepted E0
repair and accepted F-033 proof correction. The index is empty. No commit,
source move, C2 change or old-root deletion exists.

Coordinating-owned `docs/memo/**` files are excluded from the executable
path/content identity because packet preparation changes them. An executor
must still record and preserve their complete current identity at start.

## 2. Pre-READY design proof

`S1-E2-PREFLIGHT.md` records:

```text
evidence ID:
E2P-1c5a001693442adc

probe source SHA-256:
908e638ba73fdc2a1725674b557ca5ff207ceed69cbf337020c316f3f010907b

canonical semantic result SHA-256:
1c5a001693442adc57cfd0691ef1ebc4ffcf7202a6cad43fa44b7f20538c0102

scenario result:
11/11 discriminated
```

The probe includes a legitimate `assets/docs` runtime asset, co-located
tests/cache, source/installed add/missing/byte drift, ordinary file and
directory symlinks, and a source symlink inside an otherwise excluded real
tests subtree.

## 3. Complete pre-mutation preservation baseline

### C1 package/install/activation matrix

```text
run ID:
d2fe4bb7b85f416fb42aacfd6798146e

result:
53 passed, 29 subtests passed

duration:
18.48s pytest / 18.64s runner

cleanup:
run root absent
```

### C2 unit pre-move group

```text
run ID:
90678f930b614b91a2c2df0ff66016e8

result:
314 passed, 1035 subtests passed

duration:
2.21s pytest / 2.37s runner

cleanup:
run root absent
```

### C2 integration pre-move group

```text
run ID:
a5b0e1edee794816801d996438eb3f98

result:
353 passed, 276 subtests passed

duration:
10.05s pytest / 10.22s runner

cleanup:
run root absent
```

All commands used `./buddyswitch-test focused`. `full` remains forbidden until
the frozen S1 C6 candidate.

## 4. Gate decision

The affected current behavior is green before E2 mutation, and the selected
replacement mechanism has representative positive, negative and exact
correspondence evidence.

This snapshot permits the coordinating hub to write and READY-review one
bounded E2 implementation plan and Goal Packet. It does not authorize product
changes by itself.

The snapshot is invalidated by:

- any executable, test, fixture, `pyproject.toml` or runner change;
- HEAD, branch, index or non-memo path/content identity change;
- package/runtime boundary change;
- a newer failing, flaky or cleanup-residual result in the affected groups.
