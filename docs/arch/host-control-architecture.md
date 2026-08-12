# Host Control Architecture

## Owner

`src/buddyswitch/foundation/host_control/` is the single product-neutral owner
for private instance lifecycle coordination, Actor and Role ID validation,
host facts, recorded runtime validation, instance-record transitions,
start/list/status/clear/resume/stop/delete/interrupt/compact sequencing,
capability operations, terminal errors, destructive safety, and attributable
cleanup. Its owner-local shell projection is packaged at
`foundation/host_control/shell/host_control.sh`; it sources only owner-local or
direct Foundation shell projections.

The shared global lifecycle lock is owned by
`foundation/process_runtime/runtime_lock.py`. Runtime Broker's workspace-local
advisory lock is a separate current Broker-private concern.

## Assembly and dependency direction

```text
application Role catalog + exact start program
  -> one HostControlApplicationInput
  -> Foundation Host Control
  -> Actor Runtime / App Server / Browser / Daemon / Runtime Broker

application CLI entrypoint -> assembled Host Control -> generic CLI
application Web entrypoint -> assembled Host Control -> generic Web
```

Application owns current Role discovery and application-specific Actor build,
Codex configuration, environment MCP, Browser registration, and the concrete
Daemon and Runtime Broker executable modules. It supplies those facts as one
explicit immutable input; Foundation owns their lifecycle phases and arguments
but does not import or embed Launcher, application, modules, runtime-support,
or a concrete Role in either Python or owner-local shell. CLI and Web require
the assembled capability and never construct a concrete lifecycle owner.

There is no Launcher alias, fallback, re-export, old shell, alternate runtime
lock, provider registry, container, or dual lifecycle execution path.

## Preserved runtime contract

The owner preserves Role rows, allocated Actor IDs, selected and recorded Codex
runtime identity, start phase ordering and failure recording, canonical
instance paths and state, lifecycle payloads and error codes, capability
config, active-resource deletion guards, lock timeout and signal behavior, and
cleanup of Browser, App Server, Daemon, Runtime Broker, sockets, processes and
temporary start files.
