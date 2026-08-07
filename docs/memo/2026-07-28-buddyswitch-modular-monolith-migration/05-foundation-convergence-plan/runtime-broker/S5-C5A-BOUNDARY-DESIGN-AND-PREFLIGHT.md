# S5 C5A Boundary Design and Preflight

## 1. Decision

C5 is refined at its two existing semantic owners:

```text
C5A Runtime Broker                    C5B Daemon
protocol/dispatch/coordination        contracts/trigger/mailbox/state
client/server/lifecycle               central + instance host lifecycle
             |                                      |
             +---- process-runtime JSON framing ----+
```

They have separate service lifecycles, consumers and proof loops. Combining
them would not make an atomic replacement safer; it would merely enlarge the
dirty candidate and obscure failure ownership. C5A completes first because
Daemon currently consumes framing mixed into Broker protocol. C5B then starts
from the clean C5A checkpoint.

## 2. Target physical boundary

- `foundation/runtime_broker/**`: the existing Broker protocol, coordination,
  dispatch, client/server and lifecycle owner;
- `foundation/process_runtime/<direct framing module>`: the existing generic
  Content-Length JSON socket framing shared by Broker and Daemon;
- `runtime_support/turn_runtime.py`: current diagnostics/status only after the
  Broker-private advisory lock moves to Broker coordination.

`foundation/runtime_broker/**` is an earned owner, not speculative topology:
the current service is more than 2,200 lines, has its own installed entrypoint,
Unix socket lifecycle, client API, protocol, dispatch and four-tier proof
surface. It is neither ToolHost, Browser runtime, Daemon nor a generic process
primitive.

File splits and private symbol organization are executor choices. The design
does not require copying current modules one-for-one.

## 3. Dependency boundary

Allowed:

```text
application entrypoint -> Runtime Broker owner
ToolHost/Browser/Evidence adapters -> Runtime Broker client
Runtime Broker -> process identity/framing + state + ToolHost + Browser owner
Runtime Broker -> current explicit manifest loader until S6
Daemon transport -> process-runtime framing
```

Forbidden:

- Runtime Broker importing a concrete product module or Role;
- Daemon importing Runtime Broker merely to read/write framed JSON;
- ToolHost or Browser absorbing Broker service lifecycle;
- Runtime Broker becoming a service locator, plugin host or generic bus;
- package-root re-exports, aliases, fallback imports or a retained
  `runtime_kernel` namespace;
- C5A changing Daemon contracts, trigger/order/handler execution or service
  lifecycle.

## 4. C5A / C5B / C6 cut line

C5A may edit current Daemon files only to replace the shared framing import.
All Daemon contracts, central/instance service code, trigger routing, mailbox
semantics, state and host runtime remain C5B-owned.

Actor/App/Web/CLI hosts remain C6-owned. Launcher or runtime-support files may
be direct C5A consumers, but moving their unrelated host ownership is not
authorized.

## 5. Preflight result

Preflight `S5C5AP-20260807-02` parsed the complete current package with the
verified Python 3.13 runtime, simulated the seven Broker owner moves and
rewired the three current Daemon framing consumers to the generic primitive.

```text
candidate Broker moves:                7
generic framing owner:                 foundation.process_runtime
candidate strongly connected groups:  10 (unchanged current topology)
Broker -> product/Role imports:         0
retired runtime_kernel import edges:   0
result:                                PASS
```

The candidate introduces no product/Role dependency and leaves no import edge
to the retired root. Existing unrelated later-host cycles are not C5A scope.

## 6. Acceptance matrix

| Proof class | Required C5A claim |
|---|---|
| Product | Tool, Browser, Evidence and launcher consumers observe the same Broker terminal results |
| Contract | v2 envelopes, framing, identity validation, locking, retry and errors remain exact |
| Architecture | one earned Broker owner and one generic framing primitive; no product/Role/Daemon semantic dependency |
| Replacement | `runtime_kernel/**`, imports, literals, patch targets and installed modules are absent without aliases |
| Operations | local socket capacity, readiness, PID identity, marker/log, stop and cleanup remain exact |
| Correspondence | installed distribution and activated runtime contain final owners only and match frozen source |

Architecture proof should assert stable paths/import directions and a few
direct service invariants. It must not implement lexical/data-flow analysis or
maintain a hand-written catalog of every private symbol.

## 7. Stop conditions

Return `REPLANNING REQUIRED` only if current facts require product/Role
semantics, Daemon handler/lifecycle redesign, a protected protocol change,
compatibility, a new generalized framework or C5B/C6 implementation to make
C5A runnable. Mechanical consumer discovery, equivalent private layout,
current test-target correction and owner-correct in-scope repair are executor
responsibilities.
