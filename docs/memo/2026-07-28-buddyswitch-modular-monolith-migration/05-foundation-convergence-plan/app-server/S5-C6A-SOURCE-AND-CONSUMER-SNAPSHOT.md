# S5 C6A Source and Consumer Snapshot

## Source identity

```text
HEAD:                         af75566665248fc56c91eab45b64e95c088be41c
tree:                         a83cecda82034a58022d29611316e7267489f27b
owner content digest:         72bf68d0ad54ad62cab32d0c77c2312475a5aae15b3ce69889995d66308db010
representation path digest:   ccfc66d748a9e0057de53ddc9a05f5c27e1e328885c49d443048318afa138b6b
representation content digest:8a48d22e8b215ee780164d68beb4ccc05133d0003317fed7c0c0a12d2db5918a
runtime source:               3d6b5cace4d40afc7058bb72c49188d783248f40114e923399c86c0c35180f2b
runtime distribution:         3fdbec1ebc0169bb198cf3d5f0b03adc0344aff1603a63ddbf10636fc30414c8
runtime.verify:                ok=true
```

The worktree and index were clean at refresh. The active installation is the
non-editable checkout runtime for this source.

## Current physical owner

The current App Server owner is 1,462 lines in two Launcher files:

- `src/buddyswitch/launcher/app_server.py` — JSON-RPC/WebSocket client,
  thread/turn/Goal operations, socket selection, process identity, lifecycle,
  command adapter and failure mapping;
- `src/buddyswitch/launcher/shell/app_server.sh` — shell projection used by
  instance host control and CLI operations.

The Python owner imports only standard-library modules and the accepted
`foundation.process_runtime` event-log/process-identity primitives. It imports
no application, product module, Browser, Role, Broker or other Launcher owner.
The shell adapter forwards current environment facts and invokes the stable
application entrypoint; it does not interpret product meaning.

## Representation-complete refresh

The exact App Server path/import scan classified 27 current files, including:

- six direct production Python consumers in application composition,
  application entrypoint, Actor session/side lifecycle, Demand and Task;
- two packaged shell-path consumers in Launcher CLI and host control;
- direct integration/process/system tests and their process/support harnesses;
- literal Python module, source path and shell asset assertions;
- `pyproject.toml` package-data ownership and installed-distribution proof;
- current Web/Daemon architecture guidance that describes the owner boundary.

This digest is an audit snapshot, not a closed write allowlist. A mechanically
equivalent representation discovered inside the classified C6A
owner/consumer/proof/package/current-doc boundary is in scope and must be
updated rather than escalated as an omitted path.

## Protected observable paths

```text
client call -> exact JSON-RPC/WebSocket envelope -> same result or typed failure
thread input -> idle start or active steer -> same terminal turn behavior
Goal get/set/clear -> Codex App Server -> same native Goal state
ensure/status/stop -> process identity + socket/marker/log -> same lifecycle
long socket path -> deterministic fallback path -> same connectivity
host shell function -> stable application entrypoint -> same JSON and exit effect
```

Environment propagation, Side-thread defaults, timeouts, permissions, process
group termination and cleanup remain exact. Internal Python and packaged asset
paths are not protected contracts.

## Entry preservation evidence

```text
direct behavior run: c81992a70ff147d6a6fe170c8e31fdaf
result:              66 passed, 15 subtests

host/package run:    97b2677406e34820a8ce54d6670f7658
result:              71 passed, 107 subtests

source-equivalent repository FINAL:
                     e91948e42eb0498bbc473714cd48e09d
result:              all tiers passed; exit 0

cleanup:             run roots and attributable processes absent
```

The two focused runs cover App Server protocol/client behavior, early exit,
socket fallback, stale PID protection, process-group cleanup, Actor and Daemon
consumers, host control, instance CLI and installed package projection. The
FINAL is source-equivalent to the executable content at this checkpoint;
subsequent changes before this snapshot were coordinating memo truth only.

## Contrary signal recorded

The unsupported spelling `./buddyswitch-codex runtime verify` returned
`UNKNOWN_COMMAND` and changed no state. The canonical installed invocation,
`.buddyswitch-runtime/venv/bin/python -m
buddyswitch.application.entrypoints.runtime_activation verify`, then returned
the successful identity above. The unsupported spelling is not an executor
instruction.
