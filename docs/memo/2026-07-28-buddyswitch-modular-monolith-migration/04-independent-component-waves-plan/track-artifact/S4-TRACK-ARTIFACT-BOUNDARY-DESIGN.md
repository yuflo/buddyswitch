# S4 Track–Artifact Boundary Design

> Status: `APPROVED`
> Design source: `25916f58fbce46c4ad28d7359b61340ead59d986`
> Date: 2026-07-30
> Written approval: 2026-07-30
> Scope: final Track and Artifact ownership, cross-component contracts, host
> contributions, atomic cutover, behavioral protection and execution authority

## 1. Acceptance sentence

Track and Artifact become two physically independent product modules selected
once by application composition. Track remains the sole owner of Track state,
comments, updates, Artifact relations and lifecycle invariants. Artifact remains
the sole owner of Artifact content, revisions, attachments, templates and read
policy. Existing product behavior, durable object formats, external interfaces,
failure effects and operational results remain unchanged.

The migration is one atomic candidate because the current implementations read
each other's private repositories and rules. Atomic execution is a migration
constraint, not a final module merger: after acceptance, Track and Artifact have
separate roots, assemblies, Public contracts and owning tests and may evolve
their Private implementations independently.

## 2. Governing principles

This design applies the already accepted independent-module architecture:

- one small Public surface and one large Private change boundary per module;
- physical aggregation of domain, state, adapters, assets, Skills and owning
  tests;
- typed passive module assembly using host-owned contribution contracts;
- one explicit application component set and explicit cross-component wiring;
- Public-only cross-component dependencies with an acyclic source graph;
- business-neutral Daemon, Tool, Web/CLI and state hosts;
- no product discovery, service locator, semantic event bus, dynamic plugin
  loader or generic dependency container;
- direct replacement with no old-path aliases, re-exports or fallback reads.

Observable behavior outranks architectural cleanup. A cleaner dependency graph
cannot compensate for a changed Tool result, state effect, data shape, command,
Daemon result, Web/CLI projection or cleanup outcome.

## 3. Current-source ownership facts

The source at the design identity establishes:

1. `track.artifact_relations` is persisted in the Track record.
2. Track validation requires at least one current proof relation before a Track
   can enter `done`.
3. `track.add_material` and `track.add_proof` validate an Artifact and then
   write only Track state.
4. Artifact read policy uses Track relation and archive facts, but Artifact
   owns the decision about whether its content is readable.
5. Artifact relation summaries and backlinks currently scan Track state
   through shared repositories.
6. Track projections currently inspect Artifact metadata and attachments
   through shared repositories.
7. Context and Evidence currently bypass both owners through broad
   `ToolContext.repos` and `ToolContext.rules`.
8. Track comment inbound registration is currently imported by the generic
   instance Daemon instead of being contributed by Track.
9. `runtime_files` currently names Track and Artifact object directories even
   though product namespaces belong to their modules.

These facts make relation ownership unambiguous: the relation is part of the
Track aggregate, while Artifact visibility is Artifact policy over Track-owned
facts.

## 4. Final dependency shape

The source graph uses the same asymmetric technique already accepted for
Task–Demand:

```text
Artifact Private
  -> Track Public read operations
  -> Track Private state

Application Composition
  -> inject Artifact Public callables
  -> Track consumer-owned input ports
  -> Track Private
```

The reverse dependency is injected to prevent a Public import cycle. There is
no symmetric plumbing framework and no dependency map.

The runtime calls are also non-recursive:

```text
track.add_material / track.add_proof
  -> Track Private
  -> injected Artifact publication resolver
  -> Artifact-only validation
  -> Track-only relation write

artifact.list / artifact.get
  -> Artifact Private
  -> Track Public relation facts
  -> Artifact-owned visibility decision
  -> no Track write
```

## 5. Semantic ownership

### 5.1 Track owns

- Track record schema, validation, persistence and archive state;
- `artifact_relations`, including current/history selection;
- Track update rows and Artifact update references;
- the invariant that `done` requires a current proof relation;
- Track comments and comment threads;
- Track Tool semantics and Track-owned result projections;
- Track external CLI/Web projections;
- Track Actor Console projection;
- Track comment inbound registration, handler and Demand Public handoff;
- Track-owned cleanup discovery;
- Track Skill and module-local tests.

### 5.2 Artifact owns

- Artifact record schema, validation and persistence;
- Artifact body, title, summary, template and revision lineage;
- attachment metadata and attachment bytes;
- source-reference normalization associated with Artifact writes;
- Artifact read policy and relation/backlink projections;
- Artifact Tool semantics and Artifact-owned result projections;
- Artifact selection rules, configuration and command adapter;
- Evidence target facts required by the existing Evidence consumer;
- Artifact-owned cleanup discovery;
- Artifact Skill and module-local tests.

### 5.3 Neither owns

- the other module's repository or mutable record;
- a shared Track–Artifact relationship service;
- a generic product capability registry;
- a product-aware Daemon or Tool host;
- a copied visibility or lifecycle rule in Context, Evidence, Web or CLI.

## 6. Public contracts

Public contracts are capability-shaped, immutable and consumer-earned. They do
not expose repositories, mutable internal dictionaries, storage paths or
Private implementation types.

### 6.1 Track Public

Track Public provides:

- `read_track_scope(track_id) -> TrackScope | None`
  - returns only identity and archive facts needed by Artifact policy;
- `read_artifact_usage(artifact_id) -> ArtifactUsage`
  - returns immutable Track relation and update-reference facts, including
    whether the owning Track is archived;
- `list_external_tracks(...)` and `get_external_track(...)`
  - preserve the current external-safe CLI/Web DTOs;
- `context_snapshot(...)`
  - returns the current Context consumer's active Track, recent update and open
    comment-thread projections without exposing Track records.

Track Public returns facts. It does not decide whether Artifact content is
readable.

### 6.2 Artifact Public

Artifact Public provides:

- `resolve_publication_candidate(artifact_id, owner_identity_id)`
  - returns only the immutable Artifact id and template required by Track;
  - raises typed not-found, ownership-denied or not-publishable errors;
- `read_reference_metadata(artifact_id)`
  - returns content-free template and attachment summaries required by a
    Track-owned relation projection;
- `list_readable_summaries(...)`
  - preserves the exact current Context Artifact projection and applies
    Artifact-owned visibility policy;
- `resolve_evidence_target(artifact_id, author_identity_id)`
  - preserves the current Evidence target existence and active-author check
    without exposing Artifact storage.

Artifact Public returns facts or Artifact-owned decisions. It does not mutate
Track or decide whether Track may add a relation.

### 6.3 Track consumer-owned input ports

Track declares callable protocols for the two Artifact operations it consumes:

- publication candidate resolution;
- reference metadata reading.

`build_track_module(...)` receives the corresponding Artifact Public callables
from application composition. The input ports are concrete and typed; they are
not a general injection facility.

### 6.4 Error boundary

Cross-module failures use typed Public exceptions or explicit query absence.
Track adapters map them to the same current Tool error code, permission
boundary, retryability, correctable fields and state effect. Error-string
inspection such as matching `"owned by another identity"` is removed.

## 7. Physical topology

The target roots are:

```text
src/buddyswitch/modules/track/
  module.py
  public/
  private/
    domain/
    state/
    read_model/
    adapters/
      tool/
      daemon/
      cli.py
      web.py
      cleanup.py
  skills/
  tests/
    unit/
    integration/

src/buddyswitch/modules/artifact/
  module.py
  public/
  private/
    domain/
    state/
    adapters/
      tool/
      cleanup.py
  entrypoints/
    artifact_selection.py
  assets/
  skills/
  tests/
    unit/
    integration/
```

Private subdirectory names are descriptive, not a framework contract. The
enforced topology is one physical owner, small Public, passive `module.py`,
module assets and co-located owning tests.

Cross-module, Process, System and repository-wide Architecture tests remain at
the root test tiers.

## 8. Typed host contributions

### 8.1 Track assembly

Track contributes:

- one Track Tool registration;
- its public CLI command;
- its Actor Console section;
- one Track comment inbound-source registration;
- its Track Skill export;
- Track record and Track comment cleanup contributions.

### 8.2 Artifact assembly

Artifact contributes:

- one Artifact Tool registration;
- its Artifact Skill export;
- Artifact object and attachment cleanup contributions.

The stable command
`buddyswitch.application.entrypoints.artifact_selection` remains current and
delegates directly to the Artifact-owned module entrypoint. The command name is
a current external interface, not a retired implementation path.

### 8.3 Earned inbound-source contribution

`ModuleAssembly` and `ApplicationAssembly` gain one host-owned field:

```text
inbound_sources: tuple[InboundSourceRegistration, ...]
```

This is earned by the current Track comment source and the existing
Communication source. Application build validates the existing contract,
rejects duplicate event types and passes the flattened registrations to the
generic instance Daemon.

The generic Daemon:

- subscribes to declared event types;
- constructs and dispatches declared handlers;
- preserves the current handler/subscription behavior and observable status;
- never imports Track Private or interprets Track payload meaning.

This is not a new event bus, plugin system or discovery mechanism.

## 9. Product-neutral host cleanup

The atomic candidate removes Track/Artifact-specific access from generic hosts:

- `ToolContext.rules` no longer exposes Artifact relation/visibility,
  source-reference or Track relation/comment rules;
- `ToolContext.repos` no longer exposes Track, Track comment or Artifact
  repositories;
- unused Track/Artifact methods leave `RuntimeObjectAccess`;
- `runtime_files` no longer defines or eagerly creates Track-, Track-comment-
  or Artifact-specific object directories;
- generic cleanup no longer owns Track/Artifact discovery semantics;
- generic instance Daemon no longer imports Track inbound or handler modules.

Track and Artifact state calculate their unchanged durable paths from generic
runtime roots inside their own Private state owners. No persisted path changes.

Context and Evidence change only their dependency edge:

- Context consumes Track and Artifact Public projections;
- Evidence consumes Artifact Public target resolution.

Their product behavior and physical migration remain outside this candidate.

## 10. Atomic replacement

One candidate performs:

1. create both final module roots and Public contracts;
2. add the exact typed inbound-source host contribution;
3. wire Artifact Public into Track input ports in application composition;
4. select both module assemblies once;
5. update Context, Evidence, Web, CLI and stable entrypoint consumers;
6. update packaging for module Skills and Artifact assets;
7. move owning tests and add boundary proofs;
8. remove product knowledge from generic ToolContext, runtime paths, cleanup
   and instance Daemon;
9. delete all retired Track/Artifact domain, repository, Tool, launcher,
   runtime-support, shared Skill and shared config paths;
10. prove no old import, discovery, generated path or package projection
    remains.

No intermediate candidate is accepted. There is no compatibility alias,
re-export, fallback, dual registration or wrapper around an old
implementation.

## 11. Protected observable behavior

The candidate must preserve:

- every current `track.*` and `artifact.*` Tool id, action, input schema,
  output envelope and operation semantics;
- all success and rejection codes, permission boundaries, retryability,
  correctable fields and terminal state effects;
- Track and Artifact JSON schemas and durable object paths;
- Track lifecycle, relation supersession, update-reference and `done` proof
  rules;
- Artifact ownership, visibility, revision, source-reference and attachment
  rules;
- Track comment creation, delivery, inbound attention and recovery;
- Context, Evidence, Web, CLI and Actor Console results;
- selected Artifact input results and the stable selection command;
- Daemon subscription, handler, telemetry and cleanup behavior;
- role-visible Skill ids and packaged Skill/config contents.

No schema migration, fallback read, data rewrite or new external interface is
authorized.

## 12. Failure semantics

- Artifact candidate validation completes before any Track relation write.
- A rejected candidate causes no Track or Artifact mutation.
- Track relation persistence failure never reports success.
- Artifact reads over absent, archived or unrelated Track facts preserve the
  current denial result and expose no Artifact body or attachment content.
- Evidence target rejection creates no token metadata.
- Track inbound handler failure remains an attributable failed handler result;
  it is not converted to success or swallowed.
- Duplicate modules, tools, inbound event types, commands, Skills, cleanup
  categories or Actor Console sections fail application construction.
- Runtime activation cannot partially install one module while skipping the
  other.

## 13. Verification design

This is a behavior-preserving refactor. The executor dynamically discovers
current targets from source, tests, contracts and runner rules rather than
receiving a brittle frozen directory command.

### 13.1 Evidence classes

| Proof class | Required claim |
|---|---|
| Product | Track create/open/material/proof/update/status/archive, Artifact create/list/get/revision/metadata/attachments, comments/inbound, Context, Evidence, Web/CLI and selection preserve results |
| Contract | Tool schemas/envelopes/errors, Public types, input-port wiring, inbound registration and typed assembly are exact |
| Architecture | two physical owners, acyclic Public graph, explicit composition, product-neutral hosts and no cross-Private import |
| Replacement | all retired files, imports, literal paths, discovery paths, package projections and owning-test duplicates are absent |
| Operations | Daemon subscription/handler behavior, cleanup contributions, package assets, runtime activation/verify and resource cleanup are correct |

### 13.2 Evidence sequence

```text
current source
  -> dynamically discovered behavior-preserving baseline GREEN

atomic candidate
  -> exact focused proof
  -> affected focused proof
  -> architecture and residue proof
  -> runtime activation and verify
  -> frozen candidate
  -> one repository FINAL
  -> cleanup and source/environment identity record
```

The only test entrypoints remain:

```text
./buddyswitch-test focused <executor-discovered targets>
./buddyswitch-test full
```

A newer failure, timeout, flake, environment mismatch or cleanup residue
supersedes earlier passing evidence until its owning cause is diagnosed. A
read-only review reuses identity-valid evidence and does not rerun tests for
freshness.

## 14. Executor authority

The implementation plan and Goal Packet freeze:

- the acceptance sentence;
- the two semantic owners;
- Public contract meanings;
- the acyclic dependency mechanism;
- the exact typed inbound-source host seam;
- protected observable behavior;
- classified change scope;
- required evidence classes;
- one atomic candidate and no compatibility residue.

The independent executor owns:

- current target discovery and command construction;
- Private file organization within each final owner;
- the smallest owner-correct implementation;
- local diagnosis and repair inside classified scope;
- mechanically equivalent runner target corrections;
- evidence identity and cleanup reporting.

The executor must stop when work requires:

- a changed product, storage, external interface or failure contract;
- a changed approved Public meaning or dependency direction;
- a second host abstraction;
- Communication, Evidence or Context behavior changes beyond replacing a
  private dependency with an approved Public call;
- an unclassified shared-file write;
- a real external compatibility, data migration, security, privacy,
  permission or irreversible-operation decision;
- an unexplained failure outside the authorized ownership boundary.

A stopped packet is not repaired by automatic patch-on-patch instructions. The
hub first diagnoses the owning cause and either proves that the same design
still holds or reopens the boundary design.

## 15. Non-goals

- changing Track or Artifact product behavior;
- combining Track and Artifact into one module;
- creating a relationship module;
- migrating Communication, Evidence or Context as components;
- redesigning Browser, IM or worker lifecycle;
- changing Role packages or adding the secondary-market investor Role;
- adding remote plugins, dynamic discovery or hot reload;
- changing durable data, external command names or Tool schemas;
- performing unrelated foundation cleanup.

## 16. Design decision

The accepted design is:

> two final modules; Track owns relation state, Artifact owns content and read
> policy; Artifact reads Track Public directly; Track receives the two Artifact
> Public facts it needs through typed consumer-owned input ports; application
> composition selects and wires both; one atomic migration removes all retired
> paths while preserving every observable effect.
