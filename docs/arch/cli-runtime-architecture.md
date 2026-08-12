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
Application executable + manifest + current Role-profile facts
  -> one frozen CliRuntimeApplicationInput
  -> Foundation CLI Runtime / config / shell adapters
  -> Host Control / Actor Session / Web / Browser / cleanup owners
  -> exact public JSON, exit, filesystem and resource effect
```

`src/buddyswitch/application/cli_runtime.py` selects the concrete Web,
Actor-build, Browser Runtime, environment MCP, Browser proxy, cleanup and
diagnostics modules, the current manifest, the current Role-profile resolver,
and the parent Tool projection. The public CLI and Host-start entrypoints each
assemble that same required input. Foundation validates it and projects only
the supplied facts into its owner-local shell environment; it has no default,
fallback, discovery, provider, registry, locator or second executable path.

Foundation CLI Runtime imports or embeds no Application, Launcher, component,
runtime-support or concrete Role implementation. Current Role assets remain
unchanged under `src/buddyswitch/launcher/assets/roles/` as an Application/S6
input. The Launcher package root remains inert and contains no executable
owner.

## Preserved public contract

The direct owner preserves all current commands and help bytes, success and
failure envelopes, exit codes, destructive confirmation, shared lifecycle
locking, Host Control and Actor Session calls, Web startup and teardown,
Codex config idempotence and filesystem safety, environment MCP reconciliation,
Browser status/ensure/release and MCP registration, cleanup planning/effects,
Host-start phase ordering, shell quoting and attributable resource cleanup.
