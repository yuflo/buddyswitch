# BuddySwitch Modular Monolith Implementation Readiness Audit

> Audit status: COMPLETE
> Program admission: ACCEPTED
> Current implementation decision: NO-GO
> Runtime migration authorization: none
> Evidence baseline: `9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3`

## 1. Audit outcome

This audit is accepted only when the following sentence is true:

> The proposed modular-monolith migration accounts for every current
> repository owner, public entrypoint, Actor lifecycle phase, runtime
> distribution surface, workspace projection, Role/Skill/configuration input,
> canonical state path, operational resource, test owner, and current
> documentation consumer; the final repository and deployed-runtime topologies
> are explicit; every migration stage is independently runnable with one live
> path per migrated owner; and an executor can begin the first stage without
> discovering an unowned architecture decision.

The audit pack proves this sentence at the architecture/preparation boundary.
The maintainer accepted R4 on 2026-07-28, closing S0. S1 is now the active
proposed stage, but implementation remains unauthorized until its source
snapshot is refreshed and its READY review passes.

## 2. Why the previous preparation is insufficient

Two direct questions exposed missing system boundaries:

1. `src/buddyswitch/**` described a target code package but did not fully
   specify the final repository topology, packaging, entrypoints, configuration,
   runtime data, and deletion map.
2. The design did not account for the Actor creation pipeline that copies an
   exact runtime surface into a Git-free workspace and starts the Runtime Broker
   from that projection.

These are not local documentation omissions. They show that the earlier target
was derived primarily from source ownership and composition, without first
closing every runtime consumer path.

## 3. Audit law

The audit proceeds from current executable facts toward the target:

```text
current consumer action
  -> current entrypoint
    -> semantic/runtime owners
      -> files, configuration, state, assets, and processes consumed
        -> required target owners and projections
          -> migration stage and replacement proof
```

No target directory, host, package, registry, or stage is accepted from
conceptual elegance alone.

Every material target claim must have:

- current source evidence;
- an owning target boundary;
- an exact consumer path;
- startup/runtime/failure/cleanup semantics;
- a migration owner and stage;
- direct replacement proof;
- an acceptance check at the nearest meaningful boundary.

## 4. Audit surfaces

| ID | Surface | Required closure |
|---|---|---|
| A01 | repository and Python package topology | final source, package, asset, config, test, entrypoint, and deletion layout |
| A02 | public CLI and shell bootstrap | every command reaches one final package entrypoint without old path lookup |
| A03 | Actor start/build/publish | preflight, staging, runtime projection, Role projection, shared project, atomic publish |
| A04 | Actor resume/clear/stop/delete/retry | final paths, process identity, recovery, cleanup, and recorded state agree |
| A05 | runtime distribution and provenance | one attributable immutable runtime projection per Actor; no split source truth |
| A06 | Runtime Broker and Tool/MCP execution | package location, catalog, authority, state, socket, and failure semantics |
| A07 | Daemon and inbound lifecycles | central/instance daemon, triggers, handlers, schedules, recovery, notifications |
| A08 | Web, App Server, Browser, IM, and side threads | host/product ownership, process entrypoints, routes, projections, cleanup |
| A09 | product modules and cross-module Public | one state owner/write path, exact Public graph, host contributions, assets |
| A10 | Role, Skill, capability, contract, and schema | RoleHost input, Actor projection, executable private code, fail-closed startup |
| A11 | configuration, canonical state, runtime files, and security boundaries | source/config/state distinction, path authority, locks, atomic writes, permissions |
| A12 | tests, packaging, release, docs, and observability | one test entry, distribution proof, current paths, logs/status, deployment identity |

## 5. Evidence and finding rules

The audit pack lives at:

```text
docs/memo/2026-07-28-buddyswitch-modular-monolith-readiness-audit/
```

It contains:

- `README.md` — navigation and authority;
- `audit-ledger.md` — live audit state and next gate;
- `evidence-map.md` — current consumers and target obligations;
- `finding-register.md` — omissions, conflicts, and required closures;
- focused reports 01–05 for current topology, lifecycle, ownership, target
  topology, and stage readiness;
- `06-final-readiness-decision.md` for the admission result.

Finding severities:

- CRITICAL — implementation can produce a non-runnable, unsafe, dual-truth, or
  unrecoverable system;
- HIGH — a stage cannot be independently accepted or a major consumer is
  unowned;
- MEDIUM — target behavior or proof is ambiguous but can be resolved within a
  named stage;
- LOW — legibility or evidence weakness that does not alter ownership.

No CRITICAL or HIGH architecture finding may remain OPEN when S0 requests
acceptance. Runtime residue remains open under its implementation-stage owner
until direct replacement proof closes it.

## 6. Readiness gates

### Gate R0 — complete current-system trace

- all A01–A12 surfaces have source-bound evidence;
- every public/operational entrypoint is classified;
- all Actor lifecycle phases and process owners are traced;
- all hard-coded repository/runtime paths are classified.

### Gate R1 — complete target topology

- final repository tree is explicit;
- final Python packaging/import/bootstrap model is explicit;
- final runtime distribution and Actor workspace tree are explicit;
- Role runtime projection is explicit;
- source, runtime assets, canonical state, and project workspace are distinct.

### Gate R2 — complete migration topology

- every current owner and path has one destination or deletion outcome;
- every stage stands as an independently runnable current truth;
- stage dependencies include runtime consumers, not only source imports;
- no stage needs a later stage to repair its Actor/startup/cleanup behavior.

### Gate R3 — complete proof topology

- product, contract, architecture, replacement, and operations proof is named
  per stage;
- packaging and real Actor workspace execution are directly covered;
- no catalog, import, or directory-shape test substitutes for consumer proof.

### Gate R4 — maintainer acceptance

- all CRITICAL/HIGH findings are CLOSED;
- target and migration documents agree;
- exact remaining risks are accepted;
- S0 becomes ACCEPTED only through an explicit maintainer decision.

## 7. Non-goals

This audit does not:

- migrate runtime code;
- create `src/buddyswitch/**`;
- implement Runtime Distribution or RoleHost;
- change product behavior;
- preserve compatibility with retired internal paths;
- run the full repository test suite for prose-only preparation.

## 8. Final audit state

R0–R3 are complete. Twenty-five architecture findings are closed through
accepted target decisions, migration owners and proof obligations. Their
executable old-path surfaces remain registered as implementation residue.

The previous Demand-first S0–S6 sequence is withdrawn. The revised target,
S0–S7 roadmap, stage charters and S1 plan pack are the future-architecture
preparation authority. Current code and `docs/arch/**` remain the sole
executable truth until each accepted cutover.

Current decision:

```text
S0: ACCEPTED
S1: PROPOSED, not authorized
S2–S7: BLOCKED
runtime changes: none
```
