# S5 C5A Source and Consumer Snapshot

## 1. Entry identity

```text
branch:                       fea-tool
executable base HEAD:         e33698ec53b681fa323808283a906f3e49a29da6
worktree/index/untracked:     clean before preparation
Broker owner manifest SHA:    50817395316529a36dbab0817b41cf43d47813960dd1fdded7bfeebda17eea2e
representation path-set SHA:  5e1f27d69eef797d71895f217ba72544dbf9583e5838ee161bc4e737be6327cf
runtime source digest:        ad12cb31082f05b17062421ef427f416688fe03d6e9a9fc86fa347109614535f
runtime distribution digest:  e7b80ee5b9773393914bacf71b8dea86d42bc08ad5d3238ccf13ac1e96d2b75e
runtime.verify:               ok=true
source-equivalent FINAL:      e306abb4f43d42ce8b9517f08e3a5450; exit 0
```

C4 acceptance and this preparation change only memo/design truth. The
executable and test trees remain source-equivalent to the accepted C4 FINAL.

The direct C5A preservation baseline is run
`fed0d4f446be48fa83891c8bd65637b2`:

```text
64 passed, 12 subtests passed in 4.28s
cleanup: clean
```

It covers Broker framing/envelopes, coordination, dispatch, client/server,
identity checks, retries, live behavior and lifecycle. A separately executed
Daemon boundary baseline `35589e1bc45b45d79e7f1b4661ac8f6c` passed 195
tests and 66 subtests. The two independent GREEN loops confirm that C5A and
C5B do not need one shared dirty candidate.

## 2. Current Runtime Broker owner

| Current file | LOC | Current responsibility | SHA-256 prefix |
|---|---:|---|---|
| `runtime_kernel/broker.py` | 295 | CLI, request/session wiring and envelopes | `cd212336fb17` |
| `runtime_kernel/client.py` | 315 | local client, retry and observable feedback | `d24c0a0c57fc` |
| `runtime_kernel/coordinator.py` | 144 | deadline and runtime-lock coordination | `20a0a45edeb3` |
| `runtime_kernel/dispatcher.py` | 430 | Tool/Browser dispatch and identity validation | `f8544c94c530` |
| `runtime_kernel/lifecycle.py` | 688 | paths, health, start/ensure/status/stop and logs | `a859083996ab` |
| `runtime_kernel/protocol.py` | 194 | Broker envelope plus shared socket framing | `04062457c2f9` |
| `runtime_kernel/server.py` | 225 | bounded Unix socket server | `3e06fdd5b11d` |

`runtime_kernel/__init__.py` contains no behavior. The root has no remaining
non-Broker primitive after C4 moved exact process identity. C5A can therefore
delete the complete root rather than retain a namespace shell.

## 3. Two responsibilities currently mixed in protocol

`runtime_kernel/protocol.py` contains:

- Broker-specific protocol version, request validation and success/error
  envelopes;
- generic Content-Length framed JSON socket read/write used by Runtime Broker,
  central Daemon, instance mailbox and Browser test harnesses.

The framing already has multiple real service consumers. Its final owner is a
small direct process-runtime primitive. Broker-specific validation remains in
Runtime Broker. This is not a transport framework: it is the current one
framing algorithm with the same limits and effects.

## 4. Broker-adjacent owner fact

`runtime_support/turn_runtime.py` still owns the advisory runtime-lock
implementation, but its only production caller is Broker coordinator through
private `_hold_product_runtime_lock`. C5A places this lock behavior with
Broker coordination rather than leaving a new Foundation owner dependent on a
historical private runtime-support function. The remaining status/diagnostic
entrypoint stays current and is not redesigned.

`runtime_support/env_manifest.py` remains the current S6-owned manifest/Role
projection input. Broker may continue consuming its current explicit manifest
loader; C5A does not acquire Role policy.

## 5. Representation-complete consumer classes

The source/test/current-doc search found 50 path-bearing representations. The
write boundary is classified by semantic role rather than frozen filenames:

| Class | Current representations | C5A disposition |
|---|---|---|
| application | Runtime Broker installed entrypoint | import the new direct Broker owner |
| Foundation | Tool client/MCP, Browser cockpit and Daemon client | Broker clients move; Daemon client consumes only generic framing |
| modules | Evidence Browser CLI adapter and one Track integration import | update direct Broker imports; no product behavior change |
| Daemon C5B files | central service and instance mailbox framing imports | import generic framing only; no Daemon movement/redesign |
| Runtime support | Broker-private lock implementation and diagnostics | Broker owns its lock; keep current diagnostics behavior |
| tests/support | direct imports, patches, literal paths, subprocess entrypoints, package and resource assertions | follow final owners; tests do not earn aliases |
| current docs | Browser architecture and new Broker current architecture | state only implemented final paths after cutover |

Discovery must include direct and `from package import member` imports,
patch/mock strings, literal source/package paths, installed-distribution
expectations and subprocess entrypoints. Newly discovered representations in
these classes are executor-owned scope and must be reported, not treated as a
coordinator omission requiring a new packet.

## 6. Protected behavior

- protocol identifier `buddyswitch-runtime-broker/v2` and request/response
  envelope fields;
- Content-Length framing, limits and malformed-message failure effects;
- local Unix socket boundary, bounded request isolation and capacity behavior;
- Actor/Role/active-instance validation and current method set;
- `env.tool`, Browser acquire/status/release, ping and status results;
- read/write lock selection, deadlines and structured failures;
- client retry/idempotency rules and broker-unavailable feedback;
- socket/PID/identity/marker/log ownership, readiness, start/ensure/status/stop
  and cleanup effects;
- installed-runtime-only entrypoint and exact process attribution.

No public product operation, Role policy, state schema/path or Daemon
handler/order/lifecycle behavior changes in C5A.
