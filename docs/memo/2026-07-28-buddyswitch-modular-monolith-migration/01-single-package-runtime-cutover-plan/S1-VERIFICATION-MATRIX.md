# S1 Verification Matrix

> State: FROZEN FOR READY REVIEW
> Public runner: `./buddyswitch-test` only

This matrix assigns proof to the nearest meaningful checkpoint. Exact node IDs
may be added for new RED tests, but no target group may be removed without
coordinating-hub replanning.

## C1 — package, installation and activation

Create and prove:

```text
tests/unit/architecture/test_package_contract.py
tests/process/package/test_distribution_install.py
tests/process/package/test_runtime_activation.py
```

Also run:

```bash
./buddyswitch-test focused tests/unit/architecture/test_unit_runtime_policy.py tests/unit/architecture/test_repo_contracts.py tests/unit/support/test_runner.py tests/process/launcher/test_bootstrap_config.py tests/process/launcher/test_public_cli.py
```

Direct claims:

- one `pyproject.toml` and one `src` package declaration;
- exact distribution allowlist/exclusions;
- non-editable clean install;
- source/distribution/interpreter binding and drift rejection;
- missing/mismatched runtime fails closed;
- dynamic proof owns process tier and cleans all build/runtime outputs.

## C2 — source and resource cutover

Run:

```bash
./buddyswitch-test focused tests/unit/architecture tests/unit/env_tool tests/unit/daemon tests/unit/actor tests/unit/launcher tests/unit/runtime_protocol
./buddyswitch-test focused tests/integration/env_tool tests/integration/runtime tests/integration/runtime_broker tests/integration/daemon tests/integration/app_server
```

Direct claims:

- every moved import uses `buddyswitch...`;
- current manifests, profiles, contracts, schemas, Skills, Web/static assets and
  shell assets load from the installed distribution;
- tests import installed package code, not old roots;
- no `sys.path`, source `PYTHONPATH`, dynamic source-file load or package-parent
  state inference remains.

## C3 — public and child process cutover

Run the complete process tier because S1 changes every production executable
surface:

```bash
./buddyswitch-test focused tests/process
```

Direct claims:

- root CLI enters the package module;
- root test wrapper uses the activated interpreter and root test runner only;
- every BuddySwitch child command uses the exact package-entrypoint allowlist;
- Broker, App, Daemon and Browser lifecycle/status report one runtime identity;
- stale PID, process-group, socket and failure cleanup remain exact.

## C4 — Actor projection and lifecycle

Run:

```bash
./buddyswitch-test focused tests/unit/actor tests/unit/launcher/test_actor_environment.py tests/integration/actor tests/integration/runtime tests/process/launcher/test_capabilities.py tests/process/launcher/test_instance_commands.py
./buddyswitch-test focused tests/system/instance_lifecycle
```

Direct claims:

- exact Actor allowlist and no implementation copy;
- selected Role/Skill/profile/authority equivalence for every current Role;
- start/input/interrupt/compact/clear/resume/stop/delete behavior and terminal
  state agreement;
- shared project seed-once and deletion safety;
- failure cleanup leaves attributable state and no unowned resources.

## C5 — all consumers after replacement

Run:

```bash
./buddyswitch-test focused tests/integration
./buddyswitch-test focused tests/system
```

This is the broad pre-FINAL milestone because the physical source/runtime
cutover affects every product consumer even though product semantics do not
change.

Additionally execute one real temporary Actor lifecycle through the public
CLI:

```text
roles
start
status
representative Tool request
input
clear
resume
stop
delete
```

Capture Actor/runtime/process identities, exact terminal results and cleanup.
Use isolated test state; never mutate canonical user data for this proof.

## C6 — frozen S1 FINAL

Only after implementation, old-path deletion, current-guidance replacement,
residue scans and C1–C5 are green:

```bash
./buddyswitch-test full
```

Then run:

```text
git diff --check
distribution content manifest/digest
tracked old-root absence scan
active source/test/current-guidance residue classification
process/PID/socket/lock/temp cleanup scan
```

`full` is authorized exactly once for the frozen candidate and again only if
that candidate changes afterward. A failing FINAL reopens the nearest owning
checkpoint; it is never suppressed or converted to a compatibility path.
