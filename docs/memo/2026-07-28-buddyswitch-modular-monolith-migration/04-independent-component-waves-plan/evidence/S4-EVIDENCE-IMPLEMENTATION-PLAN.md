# S4 Evidence Capability Cutover Implementation Plan

> **For agentic workers:** use `superpowers:executing-plans` and the complete
> `$buddyswitch-testing` skill. This plan produces one atomic dirty candidate
> for coordinating-hub acceptance. Do not commit or push.
>
> Plan state: `CONSUMED — REJECTED`; do not resume.

**Goal:** Physically aggregate Evidence, select it explicitly once, preserve
its Tool and stable command behavior, and remove every retired live path.

**Architecture:** Evidence is a stateless capability module with one existing
Tool contribution. Its Private implementation consumes Artifact Public for
scope validation; it has no Public surface and no Browser lifecycle
dependency.

## 1. Acceptance sentence

An Actor can issue or approve transient Artifact-scoped Evidence metadata
through the same Tool and stable command contracts, while all Evidence
implementation is owned under one explicitly composed module and neither the
generic host nor Browser contains Evidence semantics.

```text
Actor/CLI request
  -> Runtime Broker
    -> explicitly composed Evidence Tool
      -> Artifact Public scope decision
        -> unchanged transient result or rejection
```

## 2. Frozen identity and decisions

- executable base: `ba292e9781400ee55ecf75a0da0271bb79c87324`;
- tree: `3bdb9a687fae8b8a28a253639c931844560b734e`;
- decisions: D-001–D-010, D-013, D-019, D-020, D-034–D-037,
  D-044, D-049–D-052;
- residue: R-EVIDENCE-001 plus the Evidence portion of R-FND-002,
  R-FND-003, R-FND-011, R-FND-012, and R-DOC-002.

No internal Python path is protected. The Tool ID/action/schema/results,
application command, Artifact durable data, Artifact Public meanings, Role
authority, Runtime Broker protocol, Browser status, and package entrypoint are
protected current contracts.

## 3. Classified write scope

| Path | Class | Disposition |
|---|---|---|
| `src/buddyswitch/modules/evidence/**` | OWNER | CREATE from current owner code; no wrapper |
| `src/buddyswitch/env/tools/evidence/**` | RETIRED OWNER | DELETE |
| `src/buddyswitch/runtime_support/browser_evidence.py` | RETIRED OWNER | DELETE |
| `src/buddyswitch/application/composition.py` | COMPOSITION | select `EVIDENCE` once |
| `src/buddyswitch/application/entrypoints/browser_evidence.py` | CONSUMER | delegate to module entrypoint |
| `src/buddyswitch/env/tool_runtime/context.py` | HOST | remove only two unused Evidence placeholders |
| `tests/unit/architecture/test_evidence_component_boundaries.py` | PROOF | CREATE |
| `tests/unit/architecture/test_search_component_boundaries.py` | PROOF | stop asserting Evidence placeholders remain |
| `README.md` | CURRENT DOC | name Evidence module owner |
| `docs/arch/evidence-capability-architecture.md` | CURRENT DOC | CREATE current boundary |
| `docs/arch/daemon-service-architecture.md` | CURRENT DOC | add Evidence to explicit component order only |

The executor may update an existing generic architecture/package/discovery
proof only when its current representation derives a now-changed path or
component enumeration. Such a mechanical projection remains `PROOF`, must
preserve the same semantic breadth, and must be reported exactly. A required
production, fixture, contract, or behavior-test write outside this table is a
stop, not an invitation to broaden scope.

Forbidden: Communication, Context, Browser lifecycle, Artifact semantics or
storage, Runtime Broker behavior, ModuleAssembly/registry contracts,
Role/permission changes, package-data additions, compatibility, unrelated
cleanup, and all migration master-truth edits.

## 4. Execution sequence

### E1 — Verify entry

- verify the preparation checkpoint changed coordinating documents only;
- verify installed runtime/source correspondence and clean resources;
- reuse or rerun the direct and affected refactor-entry baselines only if
  identity remains valid;
- dynamically validate runner targets before executing them.

Any contrary baseline signal is diagnosed and returned before mutation.

### E2 — Establish the architecture detector

Create the root architecture proof that detects:

- final physical files and retired-path absence;
- one passive Evidence Tool assembly selected once;
- no dynamic Evidence discovery;
- Artifact Public dependency and no cross-Private/Browser dependency;
- stable entrypoint delegation;
- `BrowserAccess.status` retained and both Evidence placeholders absent;
- current guidance names only the final owner.

This structural proof may be RED solely because the repository still has the
old topology. Do not invent a behavioral RED for preserved semantics.

### E3 — Perform one coherent source cutover

Without a public test inside the intermediate state:

- create/move the final owner;
- wire composition and stable entrypoint;
- delete old owners;
- remove the host placeholders;
- update current architecture.

Private formatting and exact private type annotations are executor-owned.
Behavior, dependency direction, and public contracts are not.

After the last `src/buddyswitch/**` mutation, reprovision/install/activate and
run `runtime_activation verify` before any `./buddyswitch-test` command.

### E4 — Prove the coherent candidate

Through the public runner, dynamically select the smallest complete groups
covering:

1. direct Evidence Tool and stable CLI behavior;
2. schemas, semantics, authority, success/rejection correspondence and no
   product persistence;
3. Context/host decision surfaces and Native MCP projection;
4. application composition, dynamic-package absence, source ownership, and
   installed package correspondence;
5. resource cleanup.

Known preflight targets are review input from the snapshot, not a frozen
command transcript. Mechanically equivalent target construction is
executor-owned under D-051.

Diagnose and repair an ordinary defect only before FINAL and only inside the
classified scope. Reprovision again before proof whenever package source
changes.

### E5 — Freeze and return

When all direct and affected evidence is clean:

- freeze exact source/diff/runtime identity;
- run `./buddyswitch-test full` exactly once;
- after FINAL, make no executable/test/package mutation and do not rerun;
- prove residue absence and global cleanup;
- return the complete result packet and stop.

FINAL failure is evidence returned to the hub, not a local repair cycle.

## 5. Stop conditions

Stop once, return evidence, and do not enter repeated blocked turns if:

- Evidence needs a Public API, Browser port, new host/assembly field, or
  persisted token store;
- Artifact Public meaning or durable data must change;
- another component's Private code or lane must change;
- a protected result/authority/protocol changes;
- compatibility, fallback, or dual discovery appears necessary;
- source/runtime correspondence or cleanup is invalid;
- a required write is not classified;
- FINAL fails.

## 6. Required return

Return packet identity, starting/final source and diff, every changed/created/
deleted file, runtime activation identity, direct/affected/FINAL commands and
run IDs, every failure/timeout/flake/residue signal and owning disposition,
consumer-observed results, residue/cleanup proof, omitted checks, remaining
risk, and proposed `ACCEPTED` or `REJECTED`. The hub alone accepts and commits.
