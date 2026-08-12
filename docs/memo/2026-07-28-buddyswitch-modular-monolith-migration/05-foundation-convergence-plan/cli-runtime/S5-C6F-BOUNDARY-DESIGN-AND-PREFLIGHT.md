# S5 C6F Boundary Design and Preflight

> Decision: one atomic CLI Runtime/config/shell owner replacement
> Preflight: `S5C6FP-20260812-01`

## Selected topology

```text
Application CLI assembly
  -> one required immutable CLI Runtime application input
       concrete public Web/Actor-build/Browser/env-MCP/Browser-proxy/
       cleanup/diagnostics executable facts
       current cleanup-manifest fact
       current Role-profile resolution capability
  -> foundation.cli_runtime.runtime
       generic command parsing, help, dispatch, projection and shell execution
  -> foundation.cli_runtime.config
       generic deterministic Codex config mechanics
  -> foundation.cli_runtime.shell/**
       generic environment, cleanup and Browser public shell adapters

Application Host-start adapter
  -> same CLI Runtime application input
  -> resolves the active current Role capability before invoking Foundation

S6-owned current Role truth
  -> Application only
  -X-> Foundation CLI Runtime
```

The existing `foundation/cli_runtime/contracts.py` remains the sole machine
envelope/contribution owner. The exact internal type/function layout is the
executor's choice; the architecture requires one explicit Application input,
not a registry, provider family or container.

## Physical result

The current owner-correct result is:

```text
foundation/cli_runtime/
  __init__.py                 # inert
  contracts.py                # accepted C6E contract owner
  runtime.py                  # generic CLI host
  config.py                   # generic Codex config adapter
  shell/{env,cleanup,browser_cockpit}.sh
```

Application owns the concrete input and current Role resolution. The old
Launcher Python/shell files are deleted after all consumers and package data
move. Launcher Role assets remain untouched for S6.

## Why this is one cutover

1. CLI generates scripts that source all three helpers.
2. Host-start configuration sources environment and Browser helpers directly.
3. Browser and cleanup helpers call environment/config functions.
4. Moving Python alone would leave live Foundation-to-Launcher paths; moving
   shell alone would leave the current CLI host pointing to retired paths.

This is an atomic replacement dependency, not a reason to combine C7 or S6.

## Alternatives rejected

1. **Move only `cli.py` and inject old Launcher shell paths.** Runnable, but
   leaves the S5 shell owner unresolved and introduces a temporary seam whose
   only purpose is another migration.
2. **Create separate environment, cleanup and Browser shell packages now.**
   More physically pure, but no independent consumer/lifecycle currently
   earns three new public packages; it adds speculative boundaries and more
   composition than the product needs.
3. **Move Role assets/profile policy with the host.** Rejected because it
   crosses the explicit S5/S6 boundary and would make C6F an early RoleHost.

## Dependency and topology preflight

The source graph was projected with CLI/config moved to their selected owner,
the three Application consumers rewired and the Role-profile implementation
edge replaced by an Application input:

```text
projected edges:                 733
projected edge SHA-256:          840c4f9566503395f953c2bc668063aea3626e47b83b1ebff2facce44aa30067
new non-trivial SCCs:            none
Foundation CLI upward edges:     none
pre-existing unrelated SCCs:     2, both inside accepted Artifact internals
```

Every hard-coded upward Python/shell/module/path representation was separately
inventoried. Final proof must scan all executable files recursively under the
owner; an AST import graph alone is insufficient.

## Accepted preservation evidence

| Claim | Public command/run | Result |
|---|---|---|
| CLI/contract/architecture/package baseline | focused Unit/Architecture; `b60e6afd68654b609f825a203a6d9a88` | 58 passed, 94 subtests |
| public CLI/config/Browser/env/cleanup/Host/package baseline | focused Process; `baa4660d36b847b4bed6a8fa4d1d4421` | 106 passed, 148 subtests |
| current runtime shell consumer | focused Integration; `e5dcb448c56e4632b87d07ff015384a9` | 8 passed, 6 subtests |
| real reset/Browser/instance/Web loops | focused System; `4874e9a11aa549eaab5835f817fbdd9c` | 7 passed |
| repository-wide source-equivalent acceptance | C6E FINAL `69dd48e9e39e48c5bf232e4a8dd4552d` | every tier passed; cleanup clean |

All focused roots and attributable processes were absent after their owning
runners completed.

## Final invariants

- Foundation CLI Runtime contains no direct or embedded Application, Launcher,
  component, runtime-support or Role implementation root;
- concrete executable/manifest/Profile facts have one Application owner and
  enter through one required input;
- no default, fallback, alias, second invocation path or global discovery
  reconstructs the old dependency;
- all current public bytes/status/errors/state/resource effects remain exact;
- the eight zero-production-consumer helpers are absent unless current-source
  evidence disproves the snapshot;
- Launcher contains no CLI/config/shell executable after replacement; only
  current S6 Role assets and its inert package root may remain.
