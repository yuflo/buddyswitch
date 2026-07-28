# BuddySwitch Modular Monolith Refactor Preparation

> Status: audited preparation index
> Runtime authorization: none
> Evidence baseline: `9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3`

## 1. Purpose

This file is a compact preparation index. It does not duplicate the target or
stage plans and does not authorize implementation.

The original Demand-first preparation was withdrawn after repository review
found that package bootstrap, Actor runtime projection, split source
provenance, complete lifecycle and several owner boundaries were missing.

## 2. Acceptance

Preparation is sufficient only when:

> The S1 executor receives one exact package/runtime/lifecycle task against
> current source and need not invent repository topology, Actor distribution,
> owner classification, stage order, proof or removal scope.

## 3. Evidence dossier

Read the audit pack in order:

1. `2026-07-28-buddyswitch-modular-monolith-readiness-audit.md`;
2. `2026-07-28-buddyswitch-modular-monolith-readiness-audit/01-current-system-topology.md`;
3. `.../02-actor-lifecycle-and-runtime-projection.md`;
4. `.../03-product-foundation-role-boundaries.md`;
5. `.../04-target-repository-and-runtime-topology.md`;
6. `.../05-migration-stage-readiness-review.md`;
7. `.../06-final-readiness-decision.md`.

These reports contain the source evidence formerly scattered through this
preparation memo.

## 4. Accepted target summary

```text
one implementation root: src/buddyswitch/**
one package/build owner: pyproject.toml
one installed runtime identity: all BuddySwitch processes
Actor workspace: selected Role/Skill/config/private/projects only
application: explicit component assemblies
foundation: business-neutral hosts/primitives
Role: narrow fail-closed RoleHost
old runtime roots: deleted, no fallback
```

`projects/app` remains the external product source mount. Root launchers/tests/
docs remain distinct interfaces and proof/guidance, not Python implementation
roots.

## 5. Accepted stage order

```text
S0 audit/admission
  -> S1 package/runtime/lifecycle
    -> S2 Demand
      -> S3 Task/Goal
        -> S4 component waves
          -> S5 foundation
            -> S6 RoleHost
              -> S7 final acceptance
```

The roadmap owns details.

## 6. Why S1 is necessarily large

The same source-layout assumptions are used by:

- root CLI and test launchers;
- Actor builder;
- Runtime Broker and Env MCP;
- App/Daemon/Web/Browser process managers;
- start/clear/resume/stop/delete;
- Role/Skill/config projection;
- tests, fakes, diagnostics and cleanup.

A partial merge would create mixed runtime provenance. S1 therefore has
internal review checkpoints but one merge/acceptance boundary.

## 7. S1 blueprint and source-refresh prerequisites

The audit-reviewed structured S1 blueprint lives at:

```text
2026-07-28-buddyswitch-modular-monolith-migration/
  01-single-package-runtime-cutover-plan/
```

After maintainer admission and before S1 becomes READY, refresh:

- source commit and dirty diff;
- complete executable/assets file inventory;
- import and child-process graph;
- package-data requirements;
- Actor lifecycle tests and direct consumer paths;
- canonical state/data contracts;
- active guidance and old-path references;
- current test runtime/dependency setup;
- all S1 residue rows.

The refreshed handoff expands the frozen directory dispositions into the exact
current file manifest and test node IDs. It may not revisit the accepted build,
runtime, Actor, entrypoint or deletion decisions without moving S1 to
`REPLANNING`.

## 8. S1 proof requirements

At minimum:

- clean build/install and distribution allowlist;
- no package tests/docs/product mount;
- no repository `PYTHONPATH`, `sys.path` or file-path execution;
- one runtime identity across CLI/Web/Daemon/Broker/MCP/Browser;
- code-free Actor workspace allowlist;
- start/status/input/interrupt/compact/clear/resume/stop/delete;
- Web retry, IM worker, Daemon recovery and Browser safety;
- shared project seed/projection semantics;
- no implicit canonical data move;
- old-root/import/help/test/guidance absence;
- clean process/socket/lock/temp state.

## 9. Current non-authorization

Do not yet:

- create `pyproject.toml`;
- create `src/buddyswitch`;
- move files;
- change Actor builder;
- add module assembly;
- add the secondary-market-investor Role;
- alter current `docs/arch`;
- update runtime tests.

Those are S1+ executable changes and require an accepted stage plan.

## 10. Next action

Obtain R4 maintainer acceptance. Then refresh current source into the existing
S1 plan pack and perform its READY review. Do not authorize code changes during
the refresh.
