# S1 Single Package and Runtime Cutover Charter

> State: IN_PROGRESS — C1–C5 ACCEPTED, C6 PENDING
> Authorized packet: none
> Merge unit: one complete package/runtime/lifecycle replacement
> Plan pack: `01-single-package-runtime-cutover-plan/README.md`

## Acceptance sentence

> Every current BuddySwitch capability executes from one installed package
> built from `src/buddyswitch/**`; every BuddySwitch process reports one
> runtime identity; Actor workspaces contain only selected projections; old
> executable roots, copied implementation and path-surgery bootstraps are
> absent.

## Why this is one merge unit

Package provenance participates in start, status, input, interrupt, compact,
clear, resume, stop, delete, Web retry, Tool calls, Daemon recovery and Browser
lifecycle. Merging a partial cutover would create two runtime sources.

Internal checkpoints are required, but none is independently mergeable.

## Entry gate

- S0 accepted;
- exact source/diff identity recorded;
- dirty scope partitioned;
- package build/install strategy demonstrated in a throwaway proof;
- current source/assets/process/lifecycle inventory refreshed;
- S1 plan names every move, consumer, delete and test;
- canonical data paths/protected contracts classified;
- test environment can exercise installed package;
- no other branch changes runtime/launcher roots.

Current gate status: accepted for the atomic C2–C5 packet. F-033 is repaired
and accepted. The isolated
E2 preflight proves the selected exact source/installed manifest mechanism is
feasible, including explicit runtime assets, pre-activation drift and
package-source symlink rejection. E2 passed its executable RED/GREEN, complete
C1 milestone and C2 preservation gates and is accepted in
`01-single-package-runtime-cutover-plan/S1-E2-ACCEPTANCE.md`; F-034 and
R-PKG-019 are closed and C1 is accepted. Its packet is consumed.
`01-single-package-runtime-cutover-plan/S1-C2-READY-PREFLIGHT.md` proves the
old standalone C2 boundary would break live process and Actor consumers before
C3/C4 replace them. D-038 and
`01-single-package-runtime-cutover-plan/S1-C2-C5-READY-REVIEW.md` close F-035
by authorizing one source-bound C2–C5 replacement packet. That packet returned
with one installed runtime path, complete affected-tier proof and clean
operations. The coordinating hub accepted C2–C5 in
`01-single-package-runtime-cutover-plan/S1-C2-C5-ACCEPTANCE.md`; the packet is
consumed. C6 remains unauthorized until its own source-bound READY review.

## Owned scope

- `pyproject.toml` and package content;
- `.buddyswitch-runtime` installation/activation contract and `.gitignore`;
- package entrypoints;
- all current executable source/assets moving below `src/buddyswitch`;
- explicit runtime/shared/instance locators;
- Actor workspace materializer;
- CLI, Web, central/instance Daemon, Broker, MCP, App and Browser launch paths;
- runtime identity/status/logging;
- root launcher delegation;
- package/Actor content tests;
- all topology-sensitive tests and active guidance;
- deletion of old executable/runtime source roots.

## Preserved behavior

- public CLI commands/results;
- complete Actor lifecycle effects;
- Tool IDs/schemas/authority/results;
- Daemon scheduling/recovery effects;
- Web/IM/Browser behavior;
- Role list/start/bootstrap/Skills/authority;
- canonical persisted data;
- shared project seed-once/projection;
- cleanup and destructive path safety.

## Deliberate intermediate truth

After S1, product code may still be grouped technically inside the package and
fine-grained composition may remain. It is current packaged code, not a
compatibility layer. Component aggregation begins in S2.

No code remains at its prior executable path.

## Required checkpoints

1. RED for clean build/install, distribution allowlist and no-import source.
2. Package entrypoints and explicit locator contracts.
3. Direct source/asset movement with imports updated.
4. One runtime identity across every child process.
5. Actor projection without implementation copies.
6. Full lifecycle/error/cleanup preservation.
7. Old-root, path-bootstrap, dynamic-source-load and guidance deletion.
8. Frozen S1 candidate acceptance.

## Required proof

- clean checkout build/install;
- non-editable install plus fail-closed activation/source-drift checks;
- runtime distribution allowlist, explicit package-asset inclusion and
  co-located test/cache exclusion;
- the production root launcher and every BuddySwitch child work without
  repository `PYTHONPATH` or checkout `.py` execution; the root test launcher
  uses the activated interpreter for the root-owned test runner only;
- all Actor lifecycle matrix rows;
- Web retry and iMessage worker lifecycle;
- representative Tool request from MCP to Broker to owner;
- Daemon restart/recovery;
- Browser acquire/release/delete safety;
- Actor workspace exact allowlist;
- one runtime identity in status/logs;
- old paths/imports/fallbacks/dynamic loads absent;
- process/socket/lock/temp cleanup clean.

## Forbidden

- editable/check-out fallback in the accepted runtime;
- copying `src/buddyswitch` into Actor workspaces;
- import aliases for `scripts` or `tools.launcher`;
- two package/build declarations;
- product behavior redesign;
- implicit user-data relocation;
- RoleHost/component framework work beyond what runtime packaging requires;
- independently merging an internal checkpoint.

## Stop conditions

- any child still requires checkout code;
- any lifecycle operation requires copied implementation;
- package data cannot represent a required current asset;
- runtime identities diverge;
- a canonical data migration is discovered but not protected/planned;
- scope reveals duplicated semantic owners rather than a physical move.

## Exit record

Publish exact distribution manifest, final repository/Actor/runtime trees,
lifecycle results, runtime identity evidence, deletion scan, cleanup evidence,
omitted checks and residual risk.
