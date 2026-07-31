# S4 Track–Artifact Capability Lane Acceptance

> Decision: `ACCEPTED`
> Product packet: `BS-MM-S4-TRACK-ARTIFACT-R1-20260730-01`
> Test-boundary correction:
> `BS-MM-S4-TRACK-ARTIFACT-R2-20260731-01`
> Authority: coordinating hub
> Acceptance date: 2026-07-31
> Next boundary: remaining S4 lane source refresh only

## 1. Accepted outcome

The atomic lane acceptance sentence is true:

> Track and Artifact are two physically independent product modules selected
> once by application composition. Track is the sole owner of Track state,
> comments, updates, Artifact relations and lifecycle invariants. Artifact is
> the sole owner of Artifact content, revisions, attachments, templates and
> read policy. Existing product behavior, durable object formats, external
> interfaces, failure effects and operational results are unchanged.

The accepted ownership and call graph is:

```text
application composition
  -> Artifact module
    -> Artifact Public operations
  -> Track module
    -> Track-owned input ports receive two Artifact Public callables
      -> Track Public operations

generic Tool/CLI/Web/Daemon/cleanup hosts
  -> typed module contributions or Public operations
  -> no Track/Artifact Private import
```

No shared Track–Artifact service, plugin loader, event bus, service locator,
DI container, compatibility path, fallback, duplicate registration or
alternate implementation root was introduced.

## 2. Frozen candidate identity

The hub reproduced the executor's final candidate identity before writing this
non-executable acceptance record. Coordinating `docs/memo/**` files are
excluded from the executable candidate identity:

```text
worktree:
  /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
branch:
  fea-tool
HEAD and origin/fea-tool:
  ab58b4f46f5da47acb9f6bd68ee8980e1150b128
non-memo tracked binary patch SHA-256:
  c5dce497a21a91887f17ff1a7a90779c2fa3a4063f29eb027e81ba150f4a2a1e
non-memo tracked name/status SHA-256:
  678b1a8799697a7cb4ed16e96dd9c2305d819d42e03030db748c51397bbf7962
index patch SHA-256:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
non-memo untracked files:
  61
non-memo untracked path-set SHA-256:
  7c57ffb2b4fd197c3f5a922f6942f4ffa66b04eb81ce312cd18a69420b42154a
non-memo untracked line-manifest SHA-256:
  a91e603b2fc599e45b4ec26e02cd093bc788b0193b0a415dca3a1cc642e9bf0d
git diff --check:
  clean
```

The R2 result packet, post-FINAL worktree and hub review all reproduced this
identity. The hub changed no executable, test, package, asset, Skill or
current-architecture file after FINAL.

## 3. Product and contract proof

| Material claim | Consumer path | Evidence | Result |
|---|---|---|---|
| Track create/list/open and lifecycle behavior remains exact | Actor Tool -> generic registry -> Track private owner | R1 direct `70b6dff13d724f6183c1868718ac1fb5`; affected `5afac5b2466e4c759e1bafc00a4e2c14`; R2 FINAL | PASS |
| Track comments, replies, resolution and inbound attention preserve effects and source identity | inbound contribution -> generic Daemon -> Track handler/state -> consumer notification | R1 direct/finding-specific/affected proof; R2 FINAL | PASS |
| Artifact drafts, revisions, publication, visibility, attachments and summaries preserve policy and storage | Actor Tool -> Artifact owner -> durable Artifact paths -> Tool/Context result | R1 direct and affected proof; R2 FINAL | PASS |
| Track validates Artifact publication before mutating relations | Track operation -> injected Artifact Public resolver -> Track relation effect or typed rejection | R1 direct and affected proof; R2 FINAL | PASS |
| Context, Evidence, CLI and Web observe the same public results | consumer -> Track/Artifact Public projection -> unchanged envelope/schema | R1 affected proof; R2 FINAL | PASS |
| Tool IDs, actions, error codes, permission decisions, retryability and persisted effects remain exact | public adapter -> owner -> generic result envelope | R1 direct/affected proof; R2 FINAL | PASS |

Success and failure remain terminally consistent: accepted mutations are
persisted exactly once and reported as success; rejected publication,
visibility, authority or validation paths leave both owners unchanged and
report the current typed failure through the existing external envelope.

Durable object names and formats remain:

```text
buddyswitch/objects/tracks
buddyswitch/objects/track-comments
buddyswitch/objects/artifacts
buddyswitch/objects/artifact-attachments
```

No data migration, dual read, dual write or restart compatibility path exists.

## 4. Architecture proof

The accepted candidate has:

- one Track physical owner at `src/buddyswitch/modules/track/**`;
- one Artifact physical owner at `src/buddyswitch/modules/artifact/**`;
- one passive assembly for each module and one selection of each in
  application composition;
- an acyclic production graph:
  `Artifact Private -> Track Public -> Track Private`;
- two concrete Track-owned input callables injected from Artifact Public;
- no Track Private import of Artifact;
- no Artifact Private import of Track Private;
- one typed `track.comment.added` inbound-source contribution;
- generic Daemon, Tool, CLI, Web and cleanup hosts without Track/Artifact
  product semantics;
- owner-local Skills/assets packaged from their module roots;
- module-local tests only for single-module behavior;
- root-owned tests for cross-component, Process, System and repository
  Architecture behavior;
- one public test runner.

R2 corrected the escaped test-boundary invariant. The final physical
classification is:

```text
module-local:
  src/buddyswitch/modules/track/tests/integration/test_track_comment.py
  src/buddyswitch/modules/track/tests/unit/test_comments_repo.py
  src/buddyswitch/modules/artifact/tests/unit/test_artifact_selection.py

root cross-component:
  tests/integration/env_tool/_artifact_env_tool_case.py
  tests/integration/env_tool/test_artifact_attachments.py
  tests/integration/env_tool/test_artifact_listing.py
  tests/integration/env_tool/test_artifact_publication.py
  tests/integration/env_tool/test_artifact_relations.py
  tests/integration/env_tool/test_artifact_validation.py
  tests/integration/env_tool/test_response_artifact.py
  tests/integration/env_tool/test_track.py
  tests/integration/track/test_comment_added_handler.py
  tests/integration/track/test_owner_actor_model.py
```

The Track and Artifact architecture tests scan their module test roots and
reject an import of another module's Private package. Same-module Private and
other-module Public imports remain valid. Root cross-component tests may use
multiple Private fixtures without claiming a false module owner.

## 5. Replacement and residue proof

`R-TRACK-001` and `R-ARTIFACT-001` are closed completely. The
Track/Artifact portions of `R-FND-001`–`R-FND-004`, `R-FND-006`,
`R-FND-008`, `R-FND-011`, `R-FND-012`, `R-DOC-002` and `R-DOC-003` are
closed.

Absent live implementation roots include:

```text
src/buddyswitch/env/domain/track_*.py
src/buddyswitch/env/domain/artifact_*.py
src/buddyswitch/env/domain/source_refs.py
src/buddyswitch/env/repos/tracks.py
src/buddyswitch/env/repos/track_comments.py
src/buddyswitch/env/repos/artifacts.py
src/buddyswitch/env/tools/track/**
src/buddyswitch/env/tools/artifact/**
src/buddyswitch/launcher/track_comment_inbound.py
src/buddyswitch/launcher/track_comment_added_handler.py
src/buddyswitch/runtime_support/artifact_selection.py
src/buddyswitch/config/artifact-selection-v*.json
src/buddyswitch/skills/shared/{track-tool,artifact-tool}/**
src/buddyswitch/skills/pm/triage-track/**
```

The stable Artifact selection command delegates directly to the Artifact
owner and is a current interface, not compatibility residue. Negative
architecture guards and historical memos may name retired paths only to prove
absence or preserve investigation history.

## 6. Verification evidence

R1 product GREEN:

```text
run:
  70b6dff13d724f6183c1868718ac1fb5
result:
  103 passed, 72 subtests; exit 0
cleanup:
  run root absent
```

R1 finding-specific GREEN:

```text
run:
  0ebb6fc383bb4168b00743942662b7e0
result:
  8 passed, 84 subtests; exit 0
cleanup:
  run root absent
```

R1 affected GREEN/IMPACT:

```text
run:
  5afac5b2466e4c759e1bafc00a4e2c14
result:
  427 passed, 612 subtests; exit 0
cleanup:
  run root absent
```

R2 architecture RED:

```text
command:
  ./buddyswitch-test focused \
    tests/unit/architecture/test_track_component_boundaries.py \
    tests/unit/architecture/test_artifact_component_boundaries.py
run:
  b59e5b1825bf4bde9dcca817dd5d2ba5
result:
  4 failed, 4 passed for the intended escaped topology
cleanup:
  run root absent
```

R2 exact GREEN used the same command:

```text
run:
  65c9520b0b984c639cb49aa5bc18959b
result:
  8 passed; exit 0
cleanup:
  run root absent
```

R2 dynamically discovered affected GREEN/IMPACT covered all ten root
cross-component tests, all three module-local tests and both architecture
proofs:

```text
run:
  034adb94a4fc43adb88ee73123909968
result:
  99 passed, 72 subtests; exit 0
cleanup:
  run root absent
```

Frozen R2 FINAL:

```text
command:
  ./buddyswitch-test full
run:
  83f35f08d4de4f4fb211314b936e5e3f
result:
  Unit Python 452 passed, 1,120 subtests
  Unit JavaScript 147 passed
  Integration 761 passed, 442 subtests
  Process 262 passed, 375 subtests
  System 22 passed
  shell syntax PASS
  diff check PASS
  exit 0
cleanup:
  run root absent
```

FINAL ran once on the R2 frozen candidate. The hub performed read-only
identity, boundary, runtime and cleanup review and reused the source-equivalent
evidence instead of rerunning the repository-wide suite.

## 7. Contrary evidence disposition

| Signal | Owning diagnosis | Disposition | Resolved |
|---|---|---|---|
| R1 duplicate explicit/discovered Tool collection failure | two retired package markers remained | markers removed before R1 freeze; direct, affected and FINAL passed | YES |
| R1 broad Skill dual-registration failures | static and contributed Skill registration coexisted | static rows and empty retired roots removed; current role membership preserved and proved | YES |
| R1 affected failures in cleanup skeleton, Skill paths, current docs and inbound metadata | incomplete direct-consumer projection during implementation | repaired at the owning contribution/consumer paths and proved by `0ebb6fc3…` and `5afac5b2…` before R1 FINAL | YES |
| Hub review rejected R1 acceptance despite passing FINAL | cross-component tests were physically under one module and architecture proofs skipped test roots | R2 moved ten tests to root tiers and made the invariant machine-enforced | YES |
| R2 architecture RED `b59e5b18…` | intended reproduction of the escaped topology | same proof passed as `65c9520b…` after topology-only correction | YES |
| R2 initial untracked hash framing differed from the packet | diagnostic framing, not source mismatch | recomputed with sorted-NUL paths and path-ordered content lines; exact identities matched | YES |
| R2 wrong Browser help probe and unrelated process matches | read-only diagnostic mistakes outside the candidate | current Browser status and attributable cleanup proved; no mutation | YES |
| R2 first empty move patch was rejected | edit mechanism contained no context and wrote nothing | context-bearing moves completed; final identity and assertions proved | YES |

No R2 timeout, flake, no-test result, unexplained failure, undeclared
dependency, hidden environment mutation or attributable cleanup residue
remains.

## 8. Runtime and operations

```text
activated_at:
  2026-07-30T12:30:57.935144Z
source_digest:
  e36160bf6172d497827394eb687fe073082a60faa136a91965390c833f14fa1f
distribution_digest:
  2d09c0a2e120ffa64a8868c221d58a1ece590a28a3f42ee1f069e9241a774b13
package:
  buddyswitch 0.1.0
Python:
  3.13.5
runtime.verify:
  ok=true
instances:
  0
Browser:
  inactive
```

No attributable process, socket, open lock, deleted-open file, test root,
build directory, egg-info, pytest cache or source/test bytecode cache remains.
R2 changed no packaged source, so the unchanged installed runtime was not
rebuilt or reprovisioned.

## 9. Current documents

Executable truth is reflected in:

```text
README.md
docs/arch/track-capability-architecture.md
docs/arch/artifact-capability-architecture.md
docs/arch/daemon-service-architecture.md
docs/arch/web-interface-call-architecture.md
```

Module Skill paths and Artifact assets are current in
`src/buddyswitch/catalog/manifest.toml` and `pyproject.toml`. No current
guidance teaches a retired Track or Artifact implementation root.

## 10. Omitted checks and residual risk

No manual UI session was run. Automated Tool, CLI, Web, Daemon, Process and
System consumer proof covers the unchanged observable contract, so no material
claim depends on a manual UI-only result.

No second R2 FINAL was run. Candidate identity remained exact after the passing
FINAL, and reviewer identity does not invalidate evidence.

No Communication, Evidence or Context physical migration was attempted.
Their remaining private edges are inputs to later source-refreshed S4 lanes,
not incomplete Track/Artifact replacement.

Residual implementation risk within this lane: none identified.

## 11. Acceptance and next boundary

Product, Contract, Architecture, Replacement and Operations proof all pass.
Every material contrary signal has an owning resolved disposition.

Track–Artifact is therefore `ACCEPTED`. Both execution packets are consumed
and must not resume. This record authorizes only:

```text
checkpoint accepted Track–Artifact
  -> refresh Communication, Evidence and Context source/boundary facts
    -> select one next admissible lane
      -> prepare and READY-review one new lane-sized packet
```

It does not authorize another S4 lane implementation, S5, S6 or S7.
