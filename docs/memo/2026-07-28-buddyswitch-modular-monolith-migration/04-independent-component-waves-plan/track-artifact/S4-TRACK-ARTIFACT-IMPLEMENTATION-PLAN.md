# S4 Track–Artifact Atomic Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and `$buddyswitch-testing` to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **R2 correction:** Packet
> `BS-MM-S4-TRACK-ARTIFACT-R2-20260731-01` overrides only the test-location
> wording in Tasks 3 and 5. It preserves the complete R1 product candidate and
> moves cross-component tests back to root tiers.
>
> **Execution rule:** This plan produces one atomic dirty candidate for hub
> acceptance. The executor does not commit or push. That repository rule
> replaces the generic writing-plan recommendation for intermediate commits.

**Goal:** Replace the scattered Track and Artifact implementations with two
physically independent, explicitly composed modules while preserving every
observable contract and removing all retired live paths.

**Architecture:** Track owns Track state, comments, updates, Artifact relations
and lifecycle invariants. Artifact owns Artifact content, revisions,
attachments, source references, selection and read policy. Artifact reads
Track Public facts directly; Track consumes two Artifact Public callables
injected by the application composition root, yielding an acyclic source graph.

**Tech Stack:** Python 3.13, immutable dataclass/protocol contracts, passive
`ModuleAssembly`, JSON durable state, BuddySwitch public test runner, PEP 517
wheel activation.

---

## 1. Non-negotiable execution model

This is one atomic replacement candidate, not a sequence of independently
acceptable partial architectures.

```text
verified refactor baseline
  -> one coherent Track + Artifact edit block
  -> static/source checks
  -> non-editable runtime reprovision
  -> exact and affected focused proof
  -> architecture/replacement/operations proof
  -> frozen candidate
  -> one FINAL
  -> return to coordinating hub
```

No public test runs while old and new owners coexist. No compatibility path is
created to make an intermediate state runnable. The executor may diagnose and
repair in-scope failures before FINAL; after FINAL it makes no executable
change and performs no retry.

## 2. Approved contract shapes

The following names and meanings are stable. Private implementations and exact
immutable field decomposition remain executor-owned.

```python
# buddyswitch.modules.track.public
def read_track_scope(track_id: str) -> TrackScope | None: ...
def read_artifact_usage(artifact_id: str) -> ArtifactUsage: ...
def list_external_tracks(*, owner_identity=None) -> list[dict[str, object]]: ...
def get_external_track(track_id: str, *, current_identity=None) -> dict[str, object] | None: ...
def context_snapshot(*, current_identity, track_filter=None, limit=20) -> TrackContextSnapshot: ...
```

`TrackScope` exposes Track identity and archive facts only.
`ArtifactUsage` exposes immutable relation and Track-update-reference facts
needed by Artifact policy/projections. Public results cannot expose mutable
Track records or repository objects.

```python
# buddyswitch.modules.artifact.public
def resolve_publication_candidate(
    artifact_id: str,
    owner_identity_id: str,
) -> PublicationCandidate: ...

def read_reference_metadata(artifact_id: str) -> ArtifactReferenceMetadata: ...
def list_readable_summaries(*, current_identity, track_id=None, limit=20) -> list[dict[str, object]]: ...
def resolve_evidence_target(
    artifact_id: str,
    author_identity_id: str,
) -> EvidenceTarget: ...
```

`PublicationCandidate` contains only Artifact id and template.
`ArtifactReferenceMetadata` contains content-free template and attachment
summary facts. Typed Artifact errors distinguish not-found, ownership denial
and not-publishable state; Track maps them to the current external Tool
results without parsing messages.

Track declares two concrete callable input ports:

```python
class ResolvePublicationCandidate(Protocol):
    def __call__(self, artifact_id: str, owner_identity_id: str) -> PublicationCandidate: ...

class ReadReferenceMetadata(Protocol):
    def __call__(self, artifact_id: str) -> ArtifactReferenceMetadata: ...
```

Application composition wires only these callables. There is no generic
dependency dictionary or service container.

The sole host-contract extension is:

```python
@dataclass(frozen=True)
class ModuleAssembly:
    name: str
    # existing fields unchanged
    inbound_sources: tuple[InboundSourceRegistration, ...] = ()
```

`ApplicationAssembly` carries the flattened tuple. Application build validates
the existing `InboundSourceRegistration` contract and duplicate event types.

## 3. Task 0 — Verify handoff and refactor entry

**Files:** read-only repository, packet and source snapshot.

- [ ] Read root `AGENTS.md`, complete `$buddyswitch-testing` and its routed
  references, migration governance, approved boundary design, source snapshot,
  owner/consumer manifest, this plan and READY review.
- [ ] Record HEAD, tree, branch, tracked/index patch digests and every
  non-ignored untracked path/content identity.
- [ ] Prove that changes after `5c065a6d85bae8723ab0a29f602a09ac7f179a67`
  are coordinating documents only and that executable source still matches
  the snapshot.
- [ ] Run installed `runtime_activation verify` and record the exact runtime
  identity.
- [ ] Reuse Search FINAL
  `7ecfb65c5e0643c6b112cc8af3c7e98b` as repository refactor-entry evidence
  only if source/test/runtime equivalence is proven.
- [ ] Dynamically discover the smallest direct Track–Artifact behavior targets
  from current owners, public symbols, Tool IDs, routes, inbound event,
  cleanup categories, Skills, selection command and durable paths.
- [ ] If narrower source-equivalent entry evidence is needed, run only those
  focused targets before mutation and record their GREEN/IMPACT result.
- [ ] Stop before mutation on identity mismatch, unresolved contrary evidence,
  invalid runtime, active attributable resource or an unclassifiable write.

Expected entry result: current behavior has source-bound GREEN evidence; no
RED is manufactured for a behavior-preserving refactor.

## 4. Task 1 — Establish final Public owners

**Files:**

- Create/modify: `src/buddyswitch/modules/track/public/**`
- Create/modify: `src/buddyswitch/modules/artifact/public/**`
- Create/modify: final module-private code inside the two authorized roots

- [ ] Define immutable Track Public facts and operations for Track scope,
  Artifact usage, external projections and Context projection.
- [ ] Define immutable Artifact Public facts, typed errors and operations for
  publication, reference metadata, readable summaries and Evidence targets.
- [ ] Define Track's two consumer-owned callable ports.
- [ ] Move Track state/domain/read implementations into Track Private and
  Artifact state/domain/read implementations into Artifact Private.
- [ ] Replace Artifact's direct Track repository access with Track Public.
- [ ] Replace Track's direct Artifact repository access with its two input
  ports.
- [ ] Ensure Artifact validation completes before Track relation mutation and
  that rejection leaves both owners unchanged.
- [ ] Remove error-string inspection from the Track adapter; typed errors map
  to the existing exact Tool rejection.

Required source graph:

```text
Artifact Private -> Track Public -> Track Private
Application composition -> Artifact Public callable -> Track input port
```

Forbidden source graph:

```text
Track Private <-> Artifact Private
Track Public <-> Artifact Public
module -> generic locator/container -> other module
```

## 5. Task 2 — Assemble Track and Artifact

**Files:**

- Create/modify: `src/buddyswitch/modules/track/module.py`
- Create/modify: `src/buddyswitch/modules/artifact/module.py`
- Modify: `src/buddyswitch/foundation/composition/__init__.py`
- Modify: `src/buddyswitch/application/build.py`
- Modify: `src/buddyswitch/application/composition.py`

- [ ] Build Artifact as a passive assembly with one Artifact Tool, Artifact
  Skill and Artifact cleanup contributions.
- [ ] Build Track as a passive assembly with one Track Tool, Track CLI,
  Track Actor Console section, Track comment inbound registration, Track
  Skills and Track/comment cleanup contributions.
- [ ] Add only the approved `inbound_sources` host field.
- [ ] Validate inbound-source type, event type, payload contract, factory and
  duplicate event type using the existing notification contract.
- [ ] Construct Artifact first, then construct Track with the two Artifact
  Public callables, then select both exactly once in `COMPONENTS`.
- [ ] Preserve existing Demand/Task/Search construction, active-Task probe and
  exact Daemon handler order.
- [ ] Reject duplicate module, Tool, CLI, Skill, cleanup, Actor Console,
  Daemon handler and inbound event identities at application build.

Expected application module order:

```text
demand, task, search, artifact, track
```

The order is explicit composition, not an execution priority or dynamic
discovery rule.

## 6. Task 3 — Move adapters, assets and owning tests

**Files:**

- Create/move within: `src/buddyswitch/modules/track/**`
- Create/move within: `src/buddyswitch/modules/artifact/**`
- Modify: `pyproject.toml`
- Modify: `src/buddyswitch/catalog/manifest.toml`
- Move owner tests named by the source snapshot

- [ ] Move Track Tool, comment inbound/handler, CLI/Web projector, cleanup and
  Skills into Track.
- [ ] Move Artifact Tool, selection entrypoint/config, cleanup and Skill into
  Artifact.
- [ ] Keep Tool IDs, action definitions, operation semantics, result envelopes
  and native MCP projection byte-for-byte equivalent where ownership does not
  require a typed dependency change.
- [ ] Keep stable Skill IDs `triage-track`, `track-tool` and `artifact-tool`,
  their role membership and content.
- [ ] Keep stable Artifact selection command behavior and config contents.
- [ ] Add module package-data declarations for the moved Skills/assets.
- [ ] Move only single-module owning tests under the corresponding module test
  roots. A test that imports another module's Private fixture or proves a
  multi-module path remains in the root test tiers.
- [ ] Keep cross-component, Process, System and repository architecture proof
  at root.

## 7. Task 4 — Cut consumers and generic hosts to final edges

**Files:** exact COMPOSITION, host and consumer files classified in the
owner/consumer manifest.

- [ ] Pass `application.inbound_sources` through the application instance
  Daemon entrypoint.
- [ ] Make the generic instance Daemon combine built-in current sources with
  contributed sources without importing Track.
- [ ] Preserve Message and Browser source behavior for their later lanes.
- [ ] Replace CLI/Web Track private reads with Track Public operations.
- [ ] Replace Context Track/Artifact private reads with the two approved Public
  projections without changing Context output.
- [ ] Replace Evidence Artifact repository access with
  `resolve_evidence_target` without changing Evidence results or token effects.
- [ ] Remove Track/Artifact repositories and rules from generic `ToolContext`.
- [ ] Remove only unused Track/Artifact methods from generic runtime object
  access.
- [ ] Remove Track/Artifact path constants and eager directories from generic
  runtime files; module state derives the unchanged durable paths from
  `OBJECTS_ROOT`.
- [ ] Remove Track/Artifact discovery from generic cleanup; preserve cleanup
  host behavior through module contributions.
- [ ] Keep `application.entrypoints.artifact_selection` as the stable command
  and delegate directly to the Artifact owner.

## 8. Task 5 — Replace, prove structure and update current truth

**Files:**

- Delete every absorbed retired owner path from manifest sections 2 and 3
- Create three root architecture tests named in the manifest
- Update classified root tests and current docs

- [ ] Delete all retired sources, assets, Skills and duplicate test copies in
  the same candidate. Root cross-component tests are current proof, not
  retired residue.
- [ ] Add Track boundary proof for physical ownership, Public/Private
  dependency direction, exact assembly contributions, stable paths and old
  owner absence.
- [ ] Add Artifact boundary proof for physical ownership, Public/Private
  dependency direction, exact assembly contributions, assets and old owner
  absence.
- [ ] Prove module-local tests import only their own Private implementation or
  another module's Public contract. Do not exclude module test directories
  from this proof.
- [ ] Add inbound-source proof for type validation, duplicate rejection,
  explicit Track contribution, generic Daemon independence and unchanged
  Message/Browser behavior.
- [ ] Update root consumer tests mechanically; do not weaken behavior or
  negative residue assertions.
- [ ] Update README and current architecture docs to final owners and Public
  edges.
- [ ] Search code, tests, package metadata and current docs for retired
  imports, paths, discovery, Skill/config locations and generic host fields.
- [ ] Allow retired text only in historical memos and scoped negative absence
  guards.
- [ ] Parse every changed/untracked Python source and run `git diff --check`.

No `./buddyswitch-test` command is run until Tasks 1–5 form the complete
candidate.

## 9. Task 6 — Reprovision the installed runtime

**Files:** no repository mutation.

- [ ] Freeze the current tracked/index/untracked candidate identity.
- [ ] Build with the repository's declared PEP 517 path.
- [ ] Non-editably install the resulting wheel into
  `.buddyswitch-runtime/venv` using the declared dependency environment.
- [ ] Activate against the current source root and run
  `runtime_activation verify`.
- [ ] Record activation time, source digest, distribution digest, package
  version, Python and installed package root.
- [ ] Prove the temporary build root and attributable process/resource state
  are clean.

If later repair changes `src/buddyswitch/**`, `pyproject.toml` or packaged
assets, repeat this task before the next public-runner command.

## 10. Task 7 — Dynamically prove the candidate

**Files:** test runner is read-only; in-scope repair may return to Tasks 1–6.

- [ ] Re-run target discovery against the actual final diff. Changed tests,
  moved owner tests and newly added architecture proofs are the first targets.
- [ ] Add direct current consumers for every changed Public, assembly, Tool,
  inbound, runtime path, cleanup, Skill, asset, CLI/Web, Context, Evidence and
  selection boundary.
- [ ] Validate each target with the runner; never assume a module test parent
  is one valid tier.
- [ ] Run the smallest compatible focused GREEN group.
- [ ] Run focused affected proof for direct consumer and operational
  boundaries not already covered.
- [ ] Run finding-specific probes only when a failure or unresolved boundary
  requires them.
- [ ] Treat every failure, timeout, flake, no-test result or cleanup residue as
  evidence; diagnose the owning cause before any rerun.
- [ ] Repair only inside the classified scope and repeat exact/affected proof
  invalidated by that repair.
- [ ] Record commands, explicit targets, run IDs, results, duration, source and
  runtime identities, contrary signals and cleanup.

Focused acceptance must cover all five proof classes from the approved design.
No fixed target list in this memo overrides current repository or runner facts.

## 11. Task 8 — Freeze and run FINAL once

**Files:** read-only frozen candidate.

- [ ] Confirm all review-driven executable changes are complete.
- [ ] Confirm focused evidence is source/runtime-equivalent to the candidate.
- [ ] Record final HEAD, tree, tracked/index/untracked identities and
  `git diff --check`.
- [ ] Confirm installed runtime correspondence and clean resource state.
- [ ] Run exactly:

```bash
./buddyswitch-test full
```

- [ ] Preserve the complete result whether it passes or fails.
- [ ] Prove no attributable test root, process, socket, lock, instance,
  Browser state, deleted-open file, build root or hidden environment mutation
  remains.
- [ ] Make no executable/test/package mutation and do not rerun FINAL after
  this point.
- [ ] Return the result packet to the coordinating hub.

## 12. Stop conditions

Return `REPLANNING REQUIRED` once when:

- executable handoff identity or baseline cannot be established;
- a changed product/storage/external/failure contract is required;
- approved Public meaning or dependency direction must change;
- a second host abstraction or generic framework appears necessary;
- Communication, Evidence or Context behavior must change beyond the approved
  dependency-edge replacement;
- a shared production write is outside the classified manifest;
- a protected migration/security/privacy/permission/irreversible decision is
  required;
- a failure remains unexplained or owned outside authorized scope;
- runtime activation or attributable cleanup cannot be made exact;
- FINAL fails.

Mechanical test import/path projection covered by manifest section 7 does not
stop execution. A stopped execution returns once; it does not wait, loop, edit
the packet, create an R2 patch or claim completion.

## 13. Result packet

```text
Packet ID and stage:
Starting preparation/source/runtime identities:
Final HEAD/tree/tracked/index/untracked identities:
Final runtime activation/source/distribution identity:
Completed plan tasks:
Created/moved/modified/deleted paths by manifest class:
Refactor-entry evidence reused or run:
Focused GREEN commands, explicit targets, run IDs and results:
Affected commands, explicit targets, run IDs and results:
Architecture and replacement evidence:
FINAL command, frozen identity, run ID and complete result:
Every contrary signal and owning disposition:
Consumer-observed Track contract:
Consumer-observed Artifact contract:
Public graph and composition proof:
Inbound/Daemon/cleanup/package/asset proof:
Cleanup and residual state:
Omitted checks and residual risk:
Unclassified discoveries or stop cause:
Proposed ACCEPTED / REJECTED:
```
