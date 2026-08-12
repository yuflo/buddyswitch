# S5 C7 Source and Residue Snapshot

> Source/upstream: `74e93676e083b6ca755974b92ed487ac172d57ac`
> Worktree/index/untracked at refresh: clean / empty / none
> Runtime: source `f94b873f95fb8b119fa7455b7772b0107fa6b3ecebf88c71cd392787ea5f8da3`, distribution `1ee40273808d4aa5b6d3dc2b88d8fe0d2fd0183c458d5bea5d985ba7b4658335`, `ok=true`
> Captured: 2026-08-12

## Bottleneck

C1–C6F established direct Foundation owners, but the remaining
`runtime_support` root still mixes two change reasons:

```text
generic S5 execution/contracts          current S6 Role/Skill truth
----------------------------------      ---------------------------
env_cleanup.py                          env_manifest.py
skill_contracts.py                      env_profiles.py
turn_runtime.py                         role_auth.py
                                        runtime_skills.py
```

The inert package root is not a semantic owner. The eight-file source manifest
has SHA-256:

```text
f3ff933e078f9edeb9107af73a7eff306a620787c09c03ebcaffd255f79965b8
```

The generic files cannot remain as an S5-compatible technical seam:

- C2 explicitly deferred physical cleanup-host movement to later S5 work;
- component `SkillExport` and cleanup contributions are application-composition
  contracts, not RoleHost implementation;
- runless diagnostics is a generic CLI/runtime projection;
- Foundation Runtime Broker still imports the current Role manifest loader
  directly.

Deferring these facts to S6 would make RoleHost absorb generic cleanup,
diagnostics and Broker ownership and would falsely accept the S5 boundary.

## Current upward edges

Current Python AST inspection found exactly three Foundation imports into the
historical root:

```text
foundation.composition
  -> runtime_support.env_cleanup
  -> runtime_support.skill_contracts

foundation.runtime_broker.dispatcher
  -> runtime_support.env_manifest
```

Nineteen current source/test representations directly name the three generic
owners. Their sorted path-list SHA-256 is:

```text
01c5f01f355d8f92b763409662d06f0709b62c0bc3c3f1062f5f442c3eff510d
```

This inventory is a source-refresh fact, not an executor path ceiling. Current
imports, embedded module/path strings, package projections, tests and current
guidance must be rediscovered mechanically after implementation.

## Required final ownership

The final S5 responsibilities are:

- passive `SkillExport`, `CleanupContribution`, `CleanupIndexProjection` and
  `OwnedStatePath` values live with Foundation composition contracts;
- generic cleanup planning, path-safety execution and result projection live
  with Foundation state/lifecycle execution;
- runless diagnostics lives with Foundation CLI/runtime execution;
- Runtime Broker and cleanup receive current Role-source facts from
  Application and never import Role implementation;
- Application remains the sole current composition point for the S6-owned Role
  manifest/profile/authority/materialization implementation.

Exact file splits and callable signatures are executor choices. No alias,
fallback, provider family, service locator or transitional re-export is earned.

## S6-owned input preserved

C7 must leave current Role behavior untouched:

```text
runtime_support/env_manifest.py
runtime_support/env_profiles.py
runtime_support/role_auth.py
runtime_support/runtime_skills.py
catalog/manifest.toml
launcher/assets/roles/**
```

These are the current inputs S6 replaces atomically. Product modules that
currently consume Role profile/authority policy remain S6 consumers. C7 may
mechanically update `env_manifest.py` to import the relocated passive
`SkillExport` contract, but it may not redesign Role semantics or discovery.

## Protected current interfaces

Stable Application process entrypoints invoked by accepted Foundation
lifecycle owners are current interfaces, not retired compatibility. C7 does
not reopen App Server, Daemon, Broker lifecycle, Tool client or CLI process
architecture merely because those owners invoke an Application entrypoint.
The forbidden edge is a Foundation dependency on concrete component, Launcher,
historical generic runtime-support or Role implementation.
