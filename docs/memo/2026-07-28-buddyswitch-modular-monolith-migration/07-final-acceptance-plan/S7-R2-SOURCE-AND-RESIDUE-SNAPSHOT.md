# S7 R2 Source and Residue Snapshot

## Frozen candidate checkpoint

```text
branch:                  fea-tool
candidate HEAD:          7efd2a038e4604b0c3a20c8fb678980638113a2e
origin/fea-tool:         same
tracked/index/untracked: empty
git diff --check:        clean
predecessor:             S3 current-guidance repair ACCEPTED
```

The R2 preparation commit may be newer but is memo-only. Admission must prove
that HEAD equals upstream, the worktree is clean, and every post-`7efd2a0…`
change is under this migration memo path.

## Exact change since R1

R1 found one Replacement contradiction. The repair checkpoint changes only:

- root `README.md`, replacing `task.*` and retired per-instance taskbox paths
  with `task_sys.*` and `buddyswitch/objects/task-sys/tasks/*.json`;
- the existing Task architecture proof, adding one direct assertion over
  root/current guidance;
- historical/active migration control records.

There is no delta after the S6 executable checkpoint under `src/**`,
`pyproject.toml`, `buddyswitch-codex` or `buddyswitch-test`. Runtime identity
therefore remains:

```text
activated_at:         2026-08-13T04:26:32.591975Z
source_digest:        28cbef6f68c12b9a9cdddbff94b326eb8b83453f475f1a74f62642cdccc64f38
distribution_digest:  b16a15a225b592414e1fcf89347f2f2fc00d5a32750f56d4359a2c51adebf62f
package_version:      0.1.0
runtime.verify:       ok=true
```

## R2 preflight

```text
S3 repair RED:       5cb7ecb2954a416e85e44d7d276c9d56
S3 exact GREEN:      90a672c1176049428c05db2faa3d8b4f
S3 affected GREEN:   9ccc06e6baa34221a61c2fef85907848
architecture/package:458b7eb164544f7da8b2ef45b52a2148
                     164 passed, 85 subtests passed
R1 behavioral FINAL: c43014696e8b473c93e804ff73a0a408
                     1,725 tests, 1,687 subtests passed
```

R1's FINAL is behavioral baseline only. It cannot accept R2 because R2 adds a
new replacement test and current-guidance candidate. R2 must run one new
frozen FINAL.

At snapshot capture there was no `bs-test-*` root, attributable process,
socket, lock or temp residue. `R-DOC-002` is closed by the accepted S3 repair.
`R-DOC-005` remains open until S7 acceptance and historical-only promotion.
