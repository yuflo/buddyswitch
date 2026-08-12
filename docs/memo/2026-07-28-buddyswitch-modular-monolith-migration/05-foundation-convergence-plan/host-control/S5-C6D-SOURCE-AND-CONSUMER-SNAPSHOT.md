# S5 C6D Source and Consumer Snapshot

> Source HEAD: `d3dc9fa14b50e4d5f2030149eda2e62d5edf93af`
> Worktree/index/untracked state: clean
> Representation manifest: `2fad8eb5f26f5827242e843d9167e65ff0287ce523476e13ed8e45e0e6c20874`

## Current owner knot

The private Host Control path is not one Python file. Its live behavior is
distributed across:

- `launcher/host_control.py`: public-private facade, validation, payload/error
  interpretation, runtime selection and direct Role catalog imports;
- `launcher/runtime_lock.py`: product-neutral cross-process lock and child
  signal ownership;
- `launcher/shell/host_control.sh`: the actual start/list/status/clear/resume/
  stop/delete/interrupt/compact lifecycle orchestration;
- `launcher/shell/env.sh`: shared environment and instance-record mutations,
  but also current Role/profile, config, Browser and reset policy;
- Foundation App Server, Actor Runtime, Browser Runtime, Daemon and Runtime
  Broker owners already accepted in C3/C5/C6A–C6C;
- Application entrypoints, generic CLI/Web consumers, package projections,
  process/system tests and current architecture guidance.

Moving `host_control.py` alone would not move the lifecycle owner. Moving the
shell unchanged would make Foundation depend on Launcher and central Role
policy. Moving all remaining Launcher code would mix Host Control, Web, CLI,
cleanup, assets and RoleHost failure boundaries.

## Current consumer path

```text
public CLI or Web action
  -> Launcher CLI/Web adapter
  -> launcher.host_control.HostControl
  -> private host_control.sh under one runtime lock
  -> Actor Environment + Broker + config/MCP + Browser + App Server + Daemon
  -> instance record and exact success/failure envelope
```

CLI and Web instantiate Host Control themselves. This hides application
composition and forces both generic hosts to import the concrete current
owner. Host Control itself imports the central Role manifest.

## Required behavior preservation

- exact operations and public CLI/Web observable envelopes/status mapping;
- Role list and unknown-Role rejection before shared-root mutation;
- one owner-allocated Actor ID used at every start boundary;
- one selected Codex runtime for start and recorded-runtime validation on
  resume/status-sensitive paths;
- ordered start phases, one cleanup owner and truthful recorded failure;
- list/status malformed-record behavior and optional Role filtering;
- clear/resume/stop/delete/interrupt/compact effects and lifecycle blocks;
- capability get/set behavior;
- destructive path/symlink safety and active Browser/App Server guards;
- shared runtime lock timeout, ownership, signal forwarding and cleanup;
- no contradictory success/error output and no attributable process, socket,
  lock or temporary-root residue.

## Representation classes

The refreshed scan classifies direct imports, constructor defaults, shell
source paths and function names, embedded application entrypoints, package
assets, test fixtures/fakes, subprocess launchers, error literals, current
architecture text, old-path absence assertions and installed-distribution
expectations. The executor owns newly discovered mechanical representations
within these classes.

## Baseline evidence

```text
Command:
./buddyswitch-test focused \
  tests/process/cli/test_host_control.py \
  tests/process/launcher/test_instance_commands.py \
  tests/integration/web/test_management_actions.py \
  tests/unit/architecture/test_external_control.py \
  tests/unit/launcher/test_cli_contract.py

Run:    2a202fd6bf464799a6cb02b212730597
Result: 89 passed, 203 subtests; cleanup clean
```

C6C's source-equivalent frozen FINAL
`c9211e36639740738eca7fe0cbda96ca` passed every tier. Runtime verification is
`ok=true` at source digest
`0f24fd6ce3ccb995d84213ca5b678a547963b706701c3152d04f88c628007e54`
and distribution digest
`b5deaa423e359f5358ba771ae3f94abb11e4bed8b59ad519fe693fc296430a0b`.
