# S1.3 Process and Entrypoint Cutover

## Outcome

> CLI, Web, central/instance Daemon, Runtime Broker, Env MCP, App supervision
> and Browser runtime launch only package module entrypoints and report one
> runtime identity.

## Public wrappers

Modify:

- `buddyswitch-codex`;
- `buddyswitch-test`.

Both resolve the approved Python/runtime and delegate. Neither sources
implementation shell libraries, sets source `PYTHONPATH` or reproduces
product command semantics.

`buddyswitch-codex` executes only
`python -m buddyswitch.application.entrypoints.cli`. Every BuddySwitch child
process follows the package-entrypoint allowlist below and never executes a
checkout `.py` path.

`buddyswitch-test` is the one test-only exception: root `tests/**` remains the
current cross-component proof owner under D-020, so the wrapper executes root
`tests/runner.py` with the activated interpreter. The runner is package-aware,
clears source `PYTHONPATH`, invokes the installed activation verifier, and
proves during preflight that
`buddyswitch.__file__` resolves below the activated installation rather than
the checkout. This exception does not authorize a production process to load
checkout implementation.

Resolution is exact:

1. resolve the checkout-local `.buddyswitch-runtime`, or one explicit absolute
   `BUDDYSWITCH_RUNTIME_DIR`;
2. require both `activation.json` and executable `venv/bin/python`;
3. execute that deterministic runtime interpreter without parsing JSON in
   shell;
4. let the installed package parse the activation record and validate
   source/distribution/interpreter identity before any lifecycle mutation;
5. fail with `RUNTIME_UNAVAILABLE` or `RUNTIME_MISMATCH`; never fall back to
   `PATH` Python or checkout source.

The wrapper never interprets activation JSON, imports product code or owns a
second interpreter field. The activation record must name the same normalized
`venv/bin/python`; mismatch fails inside the package verifier.

Runtime provisioning is deliberately outside these wrappers. Before first
use, the operator performs the explicit build/venv/install/activate sequence
owned by S1.1. Launch and Actor start never self-install.

## Package entrypoints

Create the following exact thin module entrypoints:

| Current call surface | S1 module entrypoint |
|---|---|
| root CLI | `buddyswitch.application.entrypoints.cli` |
| runtime activation/install verification | `buddyswitch.application.entrypoints.runtime_activation` |
| Web management server | `buddyswitch.application.entrypoints.web` |
| central Daemon | `buddyswitch.application.entrypoints.central_daemon` |
| instance Daemon | `buddyswitch.application.entrypoints.instance_daemon` |
| Runtime Broker | `buddyswitch.application.entrypoints.runtime_broker` |
| Env MCP | `buddyswitch.application.entrypoints.env_mcp` |
| App Server lifecycle/RPC | `buddyswitch.application.entrypoints.app_server` |
| Actor workspace build | `buddyswitch.application.entrypoints.actor_build` |
| Browser runtime manager | `buddyswitch.application.entrypoints.browser_runtime` |
| Chrome DevTools cockpit proxy | `buddyswitch.application.entrypoints.browser_cockpit_proxy` |
| cleanup | `buddyswitch.application.entrypoints.cleanup` |
| runtime diagnostics | `buddyswitch.application.entrypoints.diagnostics` |
| Browser evidence command | `buddyswitch.application.entrypoints.browser_evidence` |
| Artifact selection command | `buddyswitch.application.entrypoints.artifact_selection` |

Manifest/profile/Skill operations become imported package APIs called by
their owner. They do not remain separate source-file processes.

Each calls one current package owner. No entrypoint imports source files
dynamically.

Current shell orchestration may remain temporarily under
`buddyswitch.launcher.shell` during S1, but only as installed package data
invoked from a package owner. Root wrappers never source it, and no shell
helper resolves checkout paths. S2–S5 remove product/foundation semantics from
that technical package as their owners move.

## Child-process replacement

Trace and replace every `subprocess`/shell launch in current:

```text
HostControl
App Server manager
Daemon manager
Runtime Broker manager
Browser manager/proxy
Web management
central Daemon
test fakes/support
```

Target form:

```text
<installed-runtime-python> -m <package-entrypoint> ...
```

The exact process-to-entrypoint table above is the allowlist. A new executable
surface discovered during source refresh stops the stage and extends this
table through review before code work.

Packaged internal shell helpers, while still current, are resolved from the
installed distribution and never from repository roots.

## Runtime identity

Add one immutable value object sourced from installed package metadata:

```text
package version
source identity
distribution digest
Python executable
package root
```

Pass or load it consistently. Include it in:

- component process startup logs;
- Broker, App, central Daemon, instance Daemon and Browser status;
- instance record attribution;
- diagnostic status.

Do not build a multi-version runtime manager.

## Direct proof

- start every BuddySwitch child with source checkout removed from import path;
- assert command lines contain package modules, not `.py` paths;
- assert runtime identities agree;
- assert Broker no longer accepts/uses `--repo-root`;
- assert dispatcher has no dynamic file loading;
- stale PID/process identity safety remains exact;
- process-group and failure cleanup tests pass.
