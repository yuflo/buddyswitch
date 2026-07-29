# S3 R1 Formal Source and Partial-Candidate Snapshot

> Snapshot state: `READY INPUT`
> Date: 2026-07-30

## 1. Git identity before R1 preparation commit

```text
branch: fea-tool
HEAD: 1c99816c57196e47ddbff38bdd0d143bf5084e24
tree: d93db54fbc75c1c4f7d832c91269c64dd7802043
origin/fea-tool: 1c99816c57196e47ddbff38bdd0d143bf5084e24
index patch SHA-256:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

The hub will commit only R1 coordinating documents after this snapshot. The
launch message supplies that preparation checkpoint because a document cannot
contain its own commit SHA.

## 2. Preserved product candidate identity

The initial executor's unaccepted candidate remains deliberately dirty:

```text
tracked src/tests binary patch SHA-256:
  b70c08475d5ecb0ebd641bd1ba4880905bd5375b237ad1f37ae753e80ae441eb
tracked src/tests name/status SHA-256:
  de4e0d282379141015ab21284b3ddf3aba7002113e2ffaac264c3ec4ad7d4154
tracked changed src/tests paths: 59
non-ignored untracked src/tests paths: 30
untracked path-set SHA-256:
  989ffcdf6b5c08190c19a991a8b33b5a7e534dd5ddfade46f909dc8594bcd658
untracked path/content manifest SHA-256:
  44c5c5359f780f127bbcd3a4f3520664db2bb2053c837a4b502b1ae06d5d82f4
porcelain entries with normal untracked collapsing: 62
git diff --check: PASS
```

`S3-R1-CONSUMER-AUDIT.md` owns the exact path classification. A mismatch in
any digest, count or path class stops execution before mutation.

## 3. Current runtime identity

The installed runtime still represents the pre-S3 source:

```text
activated_at: 2026-07-29T11:44:27.023663Z
package version: 0.1.0
source digest:
  664dc704b9c76293761dd4c36e12f3c38403b73d183a1fceec365e22dcb9963a
distribution digest:
  9c9483635358ce4dd66cd3f9107969c2d11efd637bb575efe31c15d3ba88540b
./buddyswitch-codex env status: RUNTIME_MISMATCH
```

This mismatch is expected because `src/buddyswitch/**` is already changed.
It is a mandatory pre-test gate, not a product failure. R1 must rebuild,
non-editably install, activate and verify the current partial candidate before
the first public test.

## 4. Execution evidence status

The initial S3 task stopped on scope before running a valid post-mutation
public test. Therefore:

- the pre-S3 preservation runs in `S3-SOURCE-SNAPSHOT.md` remain historical
  behavior baselines;
- no GREEN or acceptance evidence exists for the partial candidate;
- no public test may run against the stale installed runtime;
- R1 begins with reprovision, then the two exact known RED consumers.

The hub ran only read-only source checks:

```text
AST parse of changed/untracked Python: 76/76 PASS
direct/private dependency audit: PASS with the one declared test fixture edge
retired path/import scan: only negative absence guards and four stale current docs
dynamic consumer classification: two required new test writes identified
git diff --check: PASS
```

These checks admit the candidate to execution; they do not accept behavior.

## 5. Invalidation

Before R1 starts, any change to:

- the supplied preparation checkpoint;
- the tracked candidate patch;
- the untracked path/content manifest;
- the empty index;
- the R1 packet documents;
- the four frozen D-045–D-048 boundaries;

invalidates READY and requires hub review.

After execution begins, only the exact R1 scope may evolve. A new required
path or boundary does not expand the packet automatically.
