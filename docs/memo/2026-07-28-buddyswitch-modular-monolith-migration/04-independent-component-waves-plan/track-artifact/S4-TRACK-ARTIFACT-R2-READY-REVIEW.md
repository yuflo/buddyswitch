# S4 Track–Artifact R2 Ready Review

> Packet: `BS-MM-S4-TRACK-ARTIFACT-R2-20260731-01`
> Stage/lane: `S4 / Track–Artifact / R2 test-boundary correction`
> Decision: `READY`
> Prepared date: 2026-07-31

## 1. Exact bottleneck

R1 produced a behavior-green Track–Artifact product candidate, but its test
topology does not yet prove the approved independent-module architecture.
Several cross-component integration tests were physically moved under one
module while importing another module's Private implementation.

The coordinating review found 16 direct cross-module Private imports beneath
the Track and Artifact module roots:

- Track module tests import Demand Private and Artifact Private;
- Artifact module tests import Track Private;
- the new Track architecture proof explicitly skips paths containing
  `tests`, so the violation was invisible to R1 focused and FINAL evidence.

This is not a product implementation failure. It is a test-classification and
architecture-proof failure.

## 2. Planning correction

The R1 preparation documents contained conflicting instructions:

- the approved Boundary Design says cross-module tests remain in root tiers;
- the R1 Owner/Consumer Manifest broadly said all source-snapshot owner tests
  move beneath a module.

R2 resolves the conflict in favor of the approved architectural principle:

```text
single-module behavior/fixture -> module-local test
cross-component behavior or another module's Private fixture -> root test
```

The corrected Owner/Consumer Manifest and Implementation Plan are current
authority. R1 remains consumed history and is not rewritten.

## 3. Preserved R1 candidate

R2 starts from the exact dirty R1 candidate and preserves all product,
contract, package, runtime-asset and current-architecture-doc content.

```text
worktree:
  /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
branch:
  fea-tool
HEAD and origin/fea-tool:
  ab58b4f46f5da47acb9f6bd68ee8980e1150b128
non-memo tracked binary patch SHA-256:
  90d3010925ac1366d94211bcc1015dbeb5a20cc633b46db2d4eeed79211a2975
non-memo tracked name/status SHA-256:
  ef1b5d81a8a1840fb4a9602329108401ae1602445bbaa7fe7f112d514e2a5324
index patch SHA-256:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
non-memo untracked files:
  72
non-memo untracked path-set SHA-256:
  7c0d5e31c28d7407367b66d6ebf7c2c60f3b2ab6229c533328b03ce110d76511
non-memo untracked line-manifest SHA-256:
  32c44453d7bf2c0b679dc8a99907dad6ebee09359a52b430d1084b73d05a6dfb
git diff --check:
  clean
```

The line manifest is the SHA-256 of sorted lines:

```text
<file-content-sha256><two spaces><UTF-8 path><newline>
```

Only `docs/memo/**` coordinating changes are excluded from the candidate
identity. The executor records and preserves them but does not edit them.

## 4. Reusable and invalidated evidence

The following R1 facts remain reusable:

- product source and installed runtime identity;
- production Public/Private dependency review;
- absence of retired product paths;
- focused and affected behavior proof for unchanged product code;
- R1 FINAL as evidence that the preserved product candidate passed before the
  test-topology correction.

R1 FINAL is not final acceptance for R2 because R2 changes executable tests and
architecture proof. Under `$buddyswitch-testing`, R2 is
`FIX_AFTER_FINAL`:

```text
architecture RED
  -> test-topology correction
  -> exact GREEN
  -> affected focused proof
  -> freeze
  -> one new FINAL
```

No product runtime reprovision is required while R2 changes only tests and
coordinating documents and installed `runtime_activation verify` remains
exact. Any required `src/buddyswitch/**`, package, asset or runtime mutation is
outside R2 and stops execution.

## 5. Exact test disposition

Remain module-local:

```text
src/buddyswitch/modules/track/tests/integration/test_track_comment.py
src/buddyswitch/modules/track/tests/unit/test_comments_repo.py
src/buddyswitch/modules/artifact/tests/unit/test_artifact_selection.py
```

Return to root cross-component tiers:

```text
src/buddyswitch/modules/artifact/tests/integration/_artifact_env_tool_case.py
  -> tests/integration/env_tool/_artifact_env_tool_case.py
src/buddyswitch/modules/artifact/tests/integration/test_artifact_attachments.py
  -> tests/integration/env_tool/test_artifact_attachments.py
src/buddyswitch/modules/artifact/tests/integration/test_artifact_listing.py
  -> tests/integration/env_tool/test_artifact_listing.py
src/buddyswitch/modules/artifact/tests/integration/test_artifact_publication.py
  -> tests/integration/env_tool/test_artifact_publication.py
src/buddyswitch/modules/artifact/tests/integration/test_artifact_relations.py
  -> tests/integration/env_tool/test_artifact_relations.py
src/buddyswitch/modules/artifact/tests/integration/test_artifact_validation.py
  -> tests/integration/env_tool/test_artifact_validation.py
src/buddyswitch/modules/artifact/tests/integration/test_response_artifact.py
  -> tests/integration/env_tool/test_response_artifact.py
src/buddyswitch/modules/track/tests/integration/test_track.py
  -> tests/integration/env_tool/test_track.py
src/buddyswitch/modules/track/tests/integration/test_comment_added_handler.py
  -> tests/integration/track/test_comment_added_handler.py
src/buddyswitch/modules/track/tests/integration/test_owner_actor_model.py
  -> tests/integration/track/test_owner_actor_model.py
```

These are moves, not duplicate copies. Assertions and product behavior remain
unchanged. Imports change only as required by the final test locations.

## 6. Architecture-proof correction

R2 modifies only:

```text
tests/unit/architecture/test_track_component_boundaries.py
tests/unit/architecture/test_artifact_component_boundaries.py
```

The final proofs must:

1. expect only the three real module-local tests listed above;
2. treat the ten root cross-component tests as current, not retired;
3. scan module-local test sources instead of excluding `tests`;
4. reject any module-local import of another module's Private package;
5. continue permitting a module-local test to import its own Private package;
6. preserve all R1 production, composition, storage, package and residue
   assertions.

Root cross-component tests may use Private fixtures because they do not claim
one module's physical ownership. R2 does not redesign the repository-wide
test-fixture API.

## 7. Allowed writes

R2 may write only:

- the ten source/destination test paths in section 5;
- the two architecture tests in section 6;
- package `__init__.py` files inside the affected module/root test directories
  only if needed to preserve current collection behavior.

R2 may not change:

- production source under `src/buddyswitch/**` outside the exact test moves;
- Tool, Public, Private, composition, host or cleanup behavior;
- package declarations, assets, Skills or current architecture docs;
- another module's tests;
- runner or test infrastructure;
- migration master truth or coordinating memos;
- Git history, staging, branch or remote state.

## 8. READY decision

R2 is a bounded test-topology correction. The starting candidate is fully
identified, the escaped invariant is reproducible by architecture proof, the
write set is exact, no product redesign is required, and acceptance can be
proved through one `FIX_AFTER_FINAL` cycle.

Decision: `READY`.
