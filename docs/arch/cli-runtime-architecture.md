# CLI Runtime Architecture

## Owner

`src/buddyswitch/foundation/cli_runtime/` is the single product-neutral owner
for public CLI parsing, help, machine envelopes and exit mapping, Host Control
and Actor Session projection, Web launch, Codex config mechanics, and the
cooperating environment, cleanup and Browser shell adapters. Its direct files
are `src/buddyswitch/foundation/cli_runtime/runtime.py`,
`src/buddyswitch/foundation/cli_runtime/config.py`,
`src/buddyswitch/foundation/cli_runtime/contracts.py`, and
`src/buddyswitch/foundation/cli_runtime/shell/`.

The package root is inert. Consumers import the concrete modules directly;
the shell adapters are packaged only from their owner-local directory.

## Application input and dependency direction

```text
Application executable + current RoleHost facts
  -> one frozen CliRuntimeApplicationInput
  -> Foundation CLI Runtime / config / shell adapters
  -> Host Control / Actor Session / Web / Browser / cleanup owners
  -> exact public JSON, exit, filesystem and resource effect
```

`src/buddyswitch/application/cli_runtime.py` selects the concrete Web,
Actor-build, Browser Runtime, environment MCP, Browser proxy, cleanup and
diagnostics modules, the current RoleRuntime resolver,
and the parent Tool projection. The public CLI and Host-start entrypoints each
assemble that same required input. Foundation validates it and projects only
the supplied facts into its owner-local shell environment; it has no default,
fallback, discovery, provider, registry, locator or second executable path.

The cleanup and diagnostics entrypoints remain stable Application process
interfaces. Generic cleanup execution is owned by
`src/buddyswitch/foundation/state/cleanup.py`; runless status and Tool-catalog
projection are owned by
`src/buddyswitch/foundation/cli_runtime/diagnostics.py`. Application supplies
their required current Role facts directly.

Foundation CLI Runtime imports or embeds no Application, Launcher, component,
retired central Role support or concrete Role implementation. Application
supplies one `RoleRuntime` resolver from RoleHost; CLI Runtime uses only its
source-access and Browser facts. No Launcher package root or executable owner
remains.

## Preserved public contract

The direct owner preserves all current commands and help bytes, success and
failure envelopes, exit codes, destructive confirmation, shared lifecycle
locking, Host Control and Actor Session calls, Web startup and teardown,
Codex config idempotence and filesystem safety, environment MCP reconciliation,
Browser status/ensure/release and MCP registration, cleanup planning/effects,
Host-start phase ordering, shell quoting and attributable resource cleanup.
