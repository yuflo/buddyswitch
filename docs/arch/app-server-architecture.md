# App Server Architecture

## Owner

`src/buddyswitch/foundation/app_server/runtime.py` is the single BuddySwitch
owner for the Codex App Server WebSocket/JSON-RPC client, typed failures,
thread and turn operations, native Goal operations, socket resolution, and
process lifecycle. Its shell projection is co-located at
`src/buddyswitch/foundation/app_server/shell/app_server.sh` and retains the
current shell function and environment contract.

The `foundation/app_server` package root is inert. Consumers import the runtime
module directly; there is no package re-export or Launcher compatibility path.

## Dependency direction

```text
application / module / Actor host -> foundation App Server runtime
Launcher CLI and host shell ------> Foundation App Server shell projection
Foundation shell projection ------> stable application entrypoint
stable application entrypoint ----> Foundation App Server runtime main
Foundation Python runtime --------> foundation process runtime
```

The Foundation App Server Python runtime/import graph depends only on the
standard library and direct `foundation.process_runtime` primitives. Its shell
projection intentionally invokes the stable application entrypoint, which
activates application composition before calling the Foundation runtime main.
Concrete Actor, Daemon, CLI, Web, Role, and product policy remain in their
existing owners.

## Runtime contract

The direct owner preserves the current protocol envelopes and typed failures,
thread/turn/Goal/input/interrupt/compact operations, permissions and timeout
behavior, environment propagation, Unix socket fallback, process identity,
readiness, status, logging, termination, and cleanup semantics. The stable
application entrypoint remains
`buddyswitch.application.entrypoints.app_server`.
