# S5 C3 Boundary Design and Preflight

## 1. Selected boundary

```text
application Browser entrypoints
  -> Browser Foundation owner
       config
       CDP target transport
       page-idle lifecycle/state
       Actor-scoped runtime acquisition/release
       Daemon handlers and inbound registrations
       MCP cockpit proxy + owned static asset

Runtime Broker -> Browser runtime operations
Instance Daemon -> Browser inbound registrations
```

The only mandatory physical root is:

```text
src/buddyswitch/foundation/browser_runtime/**
```

A reviewed reference layout is:

```text
browser_runtime/
  __init__.py          # side-effect free; no compatibility re-exports
  config.py
  target.py
  lifecycle.py
  runtime.py
  page_handlers.py
  release_handler.py
  inbound.py
  cockpit_proxy.py
  assets/chrome-devtools-mcp-1.1.1-tools.json
```

The executor may merge or rename private files inside this root when the one
owner, import direction, operations and proof remain exact. It may not leave
any Browser implementation in `env/**` or `launcher/**`.

## 2. Ownership rules

Browser Foundation owns Browser meaning and resources. Generic hosts retain
only their own protocol/lifecycle responsibilities:

- Runtime Broker owns request method parsing, response/error mapping and
  session facts; it calls Browser acquire/status/release operations;
- Instance Daemon owns handler ordering, duplicate validation and execution;
  it combines Browser registrations without defining Browser event meaning;
- application entrypoints own installed-runtime verification and argument
  bridging only;
- shell remains a public interface over the application entrypoints;
- C4/C5 owners retain identity/state/process/Daemon/Broker primitives until
  those checkpoints replace their physical roots.

Package-root exports, a `BrowserService` locator, discovery, handler scans,
generic plugin APIs and dependency-injection containers are forbidden.

## 3. Public-internal operations

Public-internal means a named module operation used across files inside the
Browser physical owner or by one current host consumer. It does not mean a new
external API.

Required operation classes:

- runtime: acquire, status, release, stop and ownership state;
- lifecycle: read page-idle state, active target, refresh, expiry, forget and
  schedule operations;
- target: list/get/create/close;
- inbound: exact three registrations.

No production module outside the defining Browser submodule may reach a
leading-underscore lifecycle or resource operation. Focused owner regressions
may still exercise a private terminal invariant directly when that is the
nearest meaningful proof; C3 must not turn every test-touched helper into a
public surface. The package root remains side-effect free and does not mirror
operations.

## 4. Protected behavior

### Product and contract

- `browser.acquire`, `browser.status`, `browser.release` request/result/error
  semantics;
- TTL config schema/defaults/validation and canonical path;
- Actor/profile/port/PID/start-identity ownership and stale/foreign-process
  refusal;
- readiness, one usable page and exact release modes;
- page-idle state fields, active target, due-at comparison and lock behavior;
- event types, payloads, schedule keys, retry counts and exact handler order;
- MCP tool list/schema, focus blocking, upstream framing, page/search behavior,
  page hints and failed-open cleanup;
- application and shell command names, one-line JSON and exit behavior.

### Operations

- parent-known child identity and owner-level terminal reconciliation from S2;
- release and startup failure cleanup;
- no PID/socket/lock/profile/test-root residue;
- installed distribution/source correspondence.

## 5. Atomic replacement

The following changes form one C3 candidate:

1. create the single Browser owner and move its asset;
2. update owner-internal imports and replace cross-module private calls;
3. update Broker, Daemon, application, support and test consumers;
4. update package-data and current Browser/Daemon architecture guidance;
5. delete all eight retired Python modules and the retired Launcher asset;
6. prove old paths/imports absent and current behavior exact.

No old/new aliases, import fallbacks, forwarding modules or dual assets may
exist at any intermediate accepted state. Runtime reprovision occurs after the
coherent source block and before any public-runner proof.

## 6. Representative topology preflight

Read-only preflight `S5C3P-20260806-01` mapped the eight current modules into
the selected Browser root, parsed their real imports and translated internal
Browser edges.

```text
result:                       PASS
mapped implementation files: 8
unique destinations:          8
owner import graph:            acyclic
direct/representation files:   28 identified for executor re-discovery
private lifecycle read calls:  6 production calls to replace
proxy asset destination:       Browser owner
stable shell entrypoints:      preserved
preflight SHA-256:             fdc3ee083c4629695abeb6ffc05f5bdbd731677b0af4b239498fd5fd9c4ed9ad
```

Translated Browser-owner edges are:

```text
config          -> none
target          -> none
lifecycle       -> config
runtime         -> lifecycle, target
page handlers   -> lifecycle, target
release handler -> lifecycle, runtime, target
inbound         -> page handlers, release handler
cockpit proxy   -> lifecycle, target
```

This proves the physical cutover does not require a Browser-internal cycle,
service locator or later checkpoint. It does not replace behavior tests.

## 7. Proof matrix

| Proof class | Required observation |
|---|---|
| Product | public Browser commands and MCP proxy complete the same loops |
| Contract | Broker errors/results, TTL, target, lease and handler effects remain exact |
| Architecture | one Browser root; host imports only owned operations/registrations; no production cross-submodule private calls |
| Replacement | all eight retired modules, old asset, imports and literal executable paths absent |
| Operations | real child/process ownership, startup/release cleanup and source/runtime correspondence pass |
| Packaging | new owner asset ships; retired Launcher asset does not; package manifest remains exact |

## 8. Non-goals and later owners

C3 does not:

- relocate or redesign generic identity, locator, daemon state or process
  identity primitives (C4);
- move Runtime Broker or Instance Daemon hosts (C5);
- move generic Actor/App/Web/CLI/shell hosts (C6);
- change any product module, RoleHost, persisted schema or state path;
- introduce a generalized Foundation plugin mechanism.
