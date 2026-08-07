# Browser Runtime Architecture

## Purpose

Browser is one Actor-scoped Foundation capability. Its physical owner is
`src/buddyswitch/foundation/browser_runtime/`, which contains strict TTL
configuration, CDP target transport, page lifecycle state and schedules,
Browser process acquisition and release, Daemon handlers and registrations,
the Chrome DevTools cockpit proxy, and the proxy's private tool-contract asset.

Browser preserves one current consumer flow:

```text
public shell/application entrypoint -> Browser owner -> JSON/exit/resource effect
MCP client -> cockpit proxy -> Broker + Browser lifecycle/target -> page result
Runtime Broker -> Browser runtime operation -> protocol result
Instance Daemon -> Browser inbound registration -> cleanup/schedule effect
```

## Owned operations

`config.py` owns the canonical shared Browser config path, schema, defaults,
validation, and creation. `target.py` owns list, get, create, and close CDP
target transport. `lifecycle.py` owns page-idle state, the active target,
refresh, expiry comparison, forgetting, and Browser-owned schedules.

`runtime.py` owns Actor profile, Chrome port, PID/start identity, readiness,
usable-page acquisition, ownership classification, stop, release, schedule
cancellation, and terminal cleanup. `page_handlers.py`, `release_handler.py`,
and `inbound.py` own the three exact Browser Daemon event registrations and
their effects. `cockpit_proxy.py` owns MCP framing, focus protection, page and
search behavior, lifecycle metadata, upstream process identity, and cleanup.

The package `__init__.py` is side-effect free and exports no facade. Browser
submodules call named operations directly; no Browser submodule reaches
another Browser submodule's leading-underscore implementation details.

## Host boundaries

The verified application bridges remain
`src/buddyswitch/application/entrypoints/browser_runtime.py` and
`src/buddyswitch/application/entrypoints/browser_cockpit_proxy.py`. Shell
commands call those entrypoints and do not import Browser implementation.

`src/buddyswitch/foundation/runtime_broker/dispatcher.py` owns the Broker-side
request parsing, identity validation, and error/result translation for Browser
acquire, status, and release. Browser consumers call
`src/buddyswitch/foundation/runtime_broker/client.py` directly.
`src/buddyswitch/launcher/instance_daemon.py`
retains generic handler ordering, duplicate validation, and execution. It
combines the exact registrations from
`src/buddyswitch/foundation/browser_runtime/inbound.py` without defining
Browser event meaning.

Browser may consume the current generic Daemon, notification, process-identity,
Broker-client, and state-cancellation contracts. Those hosts and primitives do
not import Browser semantics except at the explicit Broker and Instance Daemon
composition points above.

## State, process, and cleanup contracts

Browser state stays Actor-scoped under the existing instance paths. The owner
preserves the current profile, port, PID/start-identity, page-idle fields,
schedule keys, retry counts, and event payloads. Release stops only processes
whose recorded start identity and Browser profile ownership still match,
verifies the real process group is gone, then removes attributable PID, page,
lock, port, and Browser-owned schedule state.

The cockpit proxy records the real upstream process identity before use and
stops it before deleting its markers. Failed page opens either close the exact
new target or schedule the existing bounded cleanup operation.

## Dependency rules

Allowed:

```text
application Browser entrypoint -> Browser Foundation submodule
Runtime Broker dispatcher -> Browser runtime operations
Instance Daemon -> Browser inbound registrations
Browser owner -> generic Daemon/process/Broker/notification contracts
```

Forbidden:

- Browser implementation in a generic host or product module;
- host calls to Browser private implementation details;
- package-root operation re-exports, service facades, discovery, fallback
  imports, dual assets, or a second registration system;
- Browser ownership of generic Broker, Daemon, Identity, State, Process,
  Actor, App, Web, CLI, or RoleHost lifecycle.
