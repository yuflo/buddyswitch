# S1 C6 Frozen Source Snapshot

> Snapshot ID: `S1-C6-68e1272-20260729`
> Prepared by: coordinating hub
> Purpose: C6 current-guidance replacement, residue proof and frozen FINAL

## 1. Exact repository identity

```text
worktree:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

branch:
fea-tool

upstream:
origin/fea-tool

HEAD:
68e1272eb4dad276c8491f642006bbb24218c3f4

HEAD tree:
8d01c3cf57d25c4e5472eb58140a23c9efe780c4

ahead / behind:
0 / 0

tracked patch:
empty

index patch:
empty

untracked:
empty

tracked files:
588

tracked path/content aggregate SHA-256:
0efc584fc6ea40070424ea25d391f8fd53691343c6928c883b53bcd04d349566
```

The coordinating C6 packet documents are added after this snapshot. They are
instruction artifacts below `docs/memo/**`; they do not change the frozen
non-memo source identity. At executor start, the non-memo patch must still be
empty and the index must still be empty.

## 2. Accepted predecessor

`S1-C2-C5-ACCEPTANCE.md` accepts C2–C5 against the executable content now
committed at `68e1272`. The current installed runtime verifies:

```text
kind:
runtime.verify

ok:
true

source_digest:
0240a6d6897a96fc2538f8b883eee4a48f5830c2deb9928e4d9ccaf44809445f

distribution_digest:
02344c6d8e7edd0489cf02f69a28c991fc7364d833f1c1c72f04348a2505f0d7

package_version:
0.1.0

package_root:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool/.buddyswitch-runtime/venv/lib/python3.13/site-packages/buddyswitch
```

The installed package contains 249 regular non-test source/runtime files.
There are no package-source symlinks and no old runtime-root file or symlink.

## 3. Current-guidance identity

```text
README.md:
f6f9c0f792010e5a43886914de1810bb2df9be5268ec3c6ffcd174bf21881004

AGENTS.md:
f05bdfb55d6b084e6f6ee41fd8c334d06f1db0ddb9111cce988fc0487276347a

docs/arch/daemon-service-architecture.md:
d06e99c6cbcaddd80508e54ca7d3d5744f4c76dc546ff1bf7127d1b8b2484636

docs/arch/demand-sys-architecture.md:
031a3b095f9573f3db711c5821065352747b41b0d7ba10c1a07efbee62c2871c

docs/arch/task-sys-architecture.md:
82e74adc882b134ac53ba6dbef55fec7563f8ee2af8b5d6dd6c8f0d5fe3fcbfb

docs/arch/web-interface-call-architecture.md:
ae6825077c8a5d8f0319626a7683fee86c616ce7a93e2bb1728002f4f9de2c75

tests/unit/architecture/test_package_contract.py:
55054a81d54974e501e6e444d463aeda916dc677e36a8fcf5029eef18da5a8ee

Role AGENTS aggregate SHA-256:
72b2d043b3b18df5eb339708085e31852ac542587653b104dba5451fba59ee0d

Skill SKILL.md aggregate SHA-256:
07cf8106006f9d7b223f172d985fdac838e3eb7257f79cd6641eddfa013e4cc4
```

The complete current-guidance path-set aggregate is
`4953157e01f98c81bdb26fd46d079cf6607fcc0e1247f7ca3f1b973792db1b85`.

## 4. Pre-mutation preservation proof

The nearest affected architecture/current-document group passed without
mutation:

```text
command:
./buddyswitch-test focused \
  tests/unit/architecture/test_package_contract.py \
  tests/unit/architecture/test_repo_contracts.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_external_control.py

run ID:
978f3133b7dc4a689527ebc0e4262187

result:
29 passed, 59 subtests passed in 0.84s

runner result:
passed in 0.96s

cleanup:
run root absent; no process/resource residual
```

This is a refactor/document-replacement baseline, not evidence that current
guidance is already correct. The exact stale guidance is enumerated in
`S1-C6-SCOPE-MANIFEST.md`.

## 5. Toolchain

```text
Python:
3.13.5

pytest:
9.0.3

Node:
v24.13.1

Git:
2.39.5 (Apple Git-154)

test interface:
./buddyswitch-test only
```

## 6. Frozen source rule

C6 may change only the six non-memo files named by
`S1-C6-SCOPE-MANIFEST.md` plus its executor-state memo. Any required change to
`src/**`, `pyproject.toml`, root launchers, another test, persisted state,
Role/Skill content, CLI/help behavior or product semantics invalidates this
snapshot and stops the packet.
