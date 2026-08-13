# Runtime Broker Architecture

## Purpose

The Runtime Broker is the launcher-managed local Unix-socket gateway for one
active Actor instance. Its direct owner is
`src/buddyswitch/foundation/runtime_broker/`, which contains protocol v2,
coordination, Tool/Browser dispatch, client/server behavior, and service
lifecycle. The package `__init__.py` is inert and exports no facade.

The observable flow is unchanged:

```text
Tool/Browser/Evidence consumer -> Runtime Broker client -> local Broker
  -> identity + active-instance validation -> coordinated dispatch
  -> Tool or Browser owner -> v2 terminal result/failure
```

## Owned contracts

`src/buddyswitch/foundation/runtime_broker/protocol.py` owns
`buddyswitch-runtime-broker/v2`, request validation, and the
request/success/error envelope shapes.
`src/buddyswitch/foundation/runtime_broker/coordinator.py` owns deadlines,
read/write selection, and the Broker-private advisory runtime lock.
`src/buddyswitch/foundation/runtime_broker/dispatcher.py` owns the supported
`env.tool`, `ping`, `status`,
`browser.acquire`, `browser.status`, and `browser.release` routes plus Actor,
Role, and active-instance checks.

`src/buddyswitch/foundation/runtime_broker/client.py` owns connection
deadlines, result/error interpretation, retry eligibility, idempotency
behavior, and unavailable feedback.
`src/buddyswitch/foundation/runtime_broker/server.py` owns bounded Unix-socket
capacity and per-connection isolation.
`src/buddyswitch/foundation/runtime_broker/lifecycle.py` owns
socket/PID/start-identity/marker/log paths and start, ensure, health, status,
stop, stale-state cleanup, and failed-start cleanup.
`src/buddyswitch/foundation/runtime_broker/broker.py` is the direct CLI and
request-session composition point.

## Shared socket framing

`src/buddyswitch/foundation/process_runtime/json_framing.py` is the single
owner of the existing Content-Length framed JSON-object read/write algorithm,
header/body limits, and malformed framing failures. Runtime Broker client,
server, and lifecycle code use that primitive directly. Central Daemon,
instance mailbox, and the Daemon client also use it directly; they do not
depend on Runtime Broker protocol policy.

The framing owner contains no Broker version, request validation, envelope,
Tool, Browser, Actor, Role, Daemon, or lifecycle semantics.

## Dependency direction

Allowed:

```text
application runtime_broker entrypoint -> Runtime Broker owner
application RoleHost activation ------> ToolHost RoleRuntime resolver
Tool/Browser/Evidence adapter --------> Runtime Broker client
Runtime Broker -----------------------> process-runtime framing + identity
Runtime Broker -----------------------> state + ToolHost + Browser operations
Daemon socket transports ------------> process-runtime framing
```

Forbidden:

- Runtime Broker imports from a product module or Role implementation;
- Daemon transport imports from Runtime Broker for socket framing;
- package-root re-exports, compatibility aliases, fallback imports, dynamic
  discovery, a service locator, event bus, or generic transport framework;
- ToolHost, Browser, or Daemon ownership of Runtime Broker lifecycle;
- a second write path, protocol version, or retired `runtime_kernel` root.

The Broker process/session contract carries no Role package path. The stable
`src/buddyswitch/application/entrypoints/runtime_broker.py` entrypoint activates
Application once; Tool dispatch resolves the active immutable `RoleRuntime`
through the Application-configured ToolHost capability. Foundation has no
Role fallback, loader, or concrete Role import.

## Terminal and lifecycle invariants

Protocol version and envelopes, method set, identity checks, lock modes,
deadlines, retry/idempotency rules, and terminal success/failure interpretation
remain one end-to-end contract. Unix-socket capacity, PID start identity,
marker/log ownership, readiness, ensure/status/stop behavior, and cleanup stay
attributable to the lifecycle owner. A malformed shared frame becomes the
existing service-specific protocol failure at the consuming boundary; it does
not create cross-service semantic ownership.
