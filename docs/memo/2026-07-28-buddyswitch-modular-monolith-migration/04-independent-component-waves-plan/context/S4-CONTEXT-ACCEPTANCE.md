# S4 Context Capability Lane Acceptance

> Decision: `ACCEPTED`
> Product packet: `BS-MM-S4-CONTEXT-R1-20260804-02`
> Authority: coordinating hub
> Acceptance date: 2026-08-04
> Stage effect: S4 accepted; S5 source refresh unblocked

## 1. Accepted outcome

The Context acceptance sentence is true:

> Context is one last-selected, read-only application-projection module that
> composes accepted Public reads, contributes exactly one `context` Tool, and
> leaves no Context-private behavior or retired owner path in shared hosts.

The accepted path is:

```text
application composition
  -> Context ModuleAssembly (selected once and last)
    -> Context Private Tool adapter
      -> Track / Task / Artifact / Communication Public
      -> generic Tool registry / Role authorization / runtime profile
      -> host-provided ToolContext facts
```

Context owns no Public API, durable state, Daemon, Web, CLI, Skill, cleanup,
inbound or module-local cross-component test surface.

## 2. Frozen candidate identity

Before writing this non-executable acceptance record, the coordinating hub
reproduced the executor's frozen candidate:

```text
worktree: /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
branch: fea-tool
HEAD: 1d25cabf43556d25abe77b8ca287105314ce4bbf
HEAD tree: 261f6fa4753e39448bfdeed1defb7e7ae4d25c68
tracked patch SHA-256: a670a3878804526790dfa2e10ee4126e1199edeb085d44a7eb597c4a54d5b276
tracked patch bytes: 55121
index patch SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
non-ignored untracked files: 9
untracked length-framed path/content SHA-256: 21d72bebb029e4e637d311a7b53ede88a8093c100b311be8e81e541f4bacabda
git diff --check: clean
```

The untracked digest hashes sorted paths as 8-byte big-endian path length,
path bytes, 8-byte big-endian content length and content bytes. This record and
the master-truth updates are under `docs/memo/**` and do not mutate that
executable/test/current-architecture candidate.

## 3. Product and contract proof

| Material claim | Consumer path | Evidence | Result |
|---|---|---|---|
| all three Context actions preserve their current outputs and rejection semantics | Actor/Native MCP -> registry -> Context owner | direct `fe22eecc03234f30af665678671a7ea6`; FINAL | PASS |
| Context remains runless, read-only and non-durable | Context action -> Public reads/runtime facts -> ToolResult | direct binding/runless proof; FINAL | PASS |
| Role authority, schemas, visibility, filters and source-workspace facts remain exact | Context request -> generic Role/registry/profile contracts -> consumer result | direct and affected proof; FINAL | PASS |
| installed distribution dispatches one explicit Context registration | application composition -> installed registry -> Context Tool | structure `fec6cceada1d4bd6836bead804046587`; affected; FINAL | PASS |

No Context mutation, transport or resource lifecycle exists. The applicable
failure contract is invalid payload/profile/authority rejection with no state
effect; direct proof preserved those envelopes and consumer-visible codes.

## 4. Architecture and replacement proof

The accepted candidate has:

- one physical owner at `src/buddyswitch/modules/context/**`;
- one passive `CONTEXT` assembly selected exactly once and last;
- exactly one `context` Tool with `get`, `summarize` and `list_sources`;
- Public-only component reads and no cross-component Private import;
- application composition as the only Context-module consumer;
- root-owned behavior/process tests and no false module-local test boundary;
- unchanged Daemon order;
- no old `src/buddyswitch/env/tools/context/**` package;
- no `RuntimeObjectAccess`, `RegistryCatalogAccess`, `ToolContext.objects`,
  `ToolContext.catalog` or `ToolContext.runtime_policy_preview(...)`;
- current README/architecture guidance naming only the module owner.

`R-CONTEXT-001` and `R-DOC-002` are closed. Context portions of
`R-FND-001`, `R-FND-002`, `R-FND-003`, `R-FND-011` and `R-FND-012` are
closed. S5 retains only the Foundation-wide scanner, host/context, lifecycle,
identity and technical-root convergence that was explicitly excluded from the
Context lane.

## 5. Verification evidence

```text
final structure:
  command: ./buddyswitch-test focused tests/unit/architecture/test_context_component_boundaries.py
  run: fec6cceada1d4bd6836bead804046587
  result: 5 passed; exit 0

direct behavior:
  run: fe22eecc03234f30af665678671a7ea6
  result: 34 passed, 23 subtests; exit 0

affected architecture/package/process:
  run: 8895133bfd2d4f74859801a9ed9c3fea
  result: 95 passed, 48 subtests; exit 0

frozen FINAL:
  command: ./buddyswitch-test full
  run: 57bb518bb531437e95038f9ccf91f050
  result:
    Unit Python 478 passed, 1,117 subtests
    Unit JavaScript 147 passed
    Integration 769 passed, 442 subtests
    Process 264 passed, 374 subtests
    System 22 passed
    shell syntax PASS
    git diff --check PASS
    exit 0
  cleanup: run root and attributable resources absent
```

Runtime identity reproduced during hub review:

```text
activated_at: 2026-08-04T06:28:19.349329Z
source_digest: 0f9c35e6a6431bd43974026ec41ea541babce6a63809e49fb78b108b1099af9b
distribution_digest: 15026280b38866b282b6bf9dd73c2d2ee1cdebe49d8ee2fdb964ecb9d95ba2a8
package: buddyswitch 0.1.0
runtime.verify: ok=true
```

The hub performed a read-only review, reproduced tracked/untracked/runtime
identity and reused the frozen FINAL rather than rerunning it.

## 6. Contrary evidence and operations

No test failure, timeout, flake or attributable cleanup residue occurred. The
reported command-shape, shell-variable and rejected pre-process cleanup
diagnostics were corrected before candidate execution or mutation; none
contradicts the accepted product/runtime result. Historical zero-collection
and unsupported-entrypoint probes remain explicit non-evidence.

Final state has no `bs-test-*` root, attributable process, socket, PID or held
test lock. Temporary build output was removed recoverably. No required check
was omitted; manual UI proof is inapplicable to this read-only Tool ownership
refactor.

## 7. Acceptance and next boundary

Product, Contract, Architecture, Replacement and Operations proof pass.
Context and S4 are `ACCEPTED`; both Context preparation packets are consumed
and must never resume.

This acceptance unlocks only:

```text
checkpoint S4
  -> refresh S5 current Foundation hosts, consumers and residue
    -> prove the smallest complete Foundation convergence boundary
      -> issue an S5 packet only after READY review
```

It does not authorize S5 implementation, S6, S7 or a compatibility path.
