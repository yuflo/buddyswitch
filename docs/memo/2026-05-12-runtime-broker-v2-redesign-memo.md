# Runtime Broker V2 Redesign Memo

Date: 2026-05-12
Scope: BuddySwitch product-mode runtime broker, broker client, runtime locking, launcher lifecycle, and product-mode state mutation safety.

## Core Question

The current runtime broker failed during ordinary product-mode work. The visible symptoms were:

- `track get` and `prepare` returned `E_RUNTIME_BROKER_UNAVAILABLE`.
- The first failure was a Unix socket timeout.
- Later failures became `No such file or directory` for the broker socket.
- The agent could not persist design output back to the track.
- A later `ps` diagnostic triggered a Codex sandbox permission prompt.

The question is not "which one-line patch stops this exact crash?"

The better question is:

How should BuddySwitch structure the local runtime broker so product-mode state access stays controlled, recoverable, observable, and simple enough to maintain?

## Short Answer

Keep the local Unix socket broker. Replace the current fragile synchronous loop with a small local RPC gateway:

- explicit request/response protocol;
- request ids and structured errors;
- bounded per-request isolation;
- consistent client/server deadlines;
- explicit read/write coordination;
- lifecycle health checks and stale-state cleanup;
- idempotent retry semantics for side-effecting writes.

Do not move to gRPC, HTTP services, external queues, systemd dependency, or a database-backed platform layer for this problem. The current bottleneck is not protocol power. It is request isolation, timeout alignment, lifecycle recovery, and write idempotency.

## Current Failure Chain

The likely chain behind the observed incident is:

1. The client calls the broker through a Unix socket with a 3 second timeout.
2. The broker is handling a request or waiting on runtime state coordination long enough to exceed that timeout.
3. The client times out and closes the socket.
4. The broker later tries to write the response back with `sendall()`.
5. `sendall()` hits `BrokenPipeError`.
6. That exception is not isolated to the request, so the broker process exits.
7. The broker process cleanup removes the real socket.
8. The pid and socket marker state can remain stale enough for later clients to keep using a dead socket path.
9. Later calls report `No such file or directory`, which looks like "broker unavailable" rather than the original crash.

The `ps` prompt was a separate Codex sandbox diagnostic issue. It was not a BuddySwitch business permission denial and not evidence that the design buddy lacked write permissions.

## Code Evidence

The current broker serve loop is synchronous and single-process:

```text
scripts/runtime_kernel/broker.py:313
```

It accepts one connection, reads until EOF, dispatches the request, and then writes the response. While it is processing a request, it is not accepting another one.

The current broker also wraps dispatch in an additional process-local lock:

```text
scripts/runtime_kernel/broker.py:320
scripts/runtime_kernel/broker.py:342
```

The broker sends responses without isolating client disconnects:

```text
scripts/runtime_kernel/broker.py:348
```

The client uses one 3 second timeout for connect, send, processing wait, and response read:

```text
scripts/runtime_kernel/client.py:102
```

The runtime state lock can wait up to 30 seconds by default:

```text
scripts/turn_runtime.py:69
scripts/turn_runtime.py:308
scripts/turn_runtime.py:323
```

All product-mode `prepare` and `persist` calls are required to route through the broker unless the broker itself is running in server mode:

```text
scripts/turn_runtime.py:2172
scripts/turn_runtime.py:2283
```

The launcher ensures the broker during instance start/open, but there is no in-session recovery path when the broker dies later:

```text
tools/launcher/runtime_broker.sh:44
buddyswitch-codex:193
buddyswitch-codex:305
```

## Design Principle

The broker should be a controlled local runtime gateway, not a workflow engine.

It should centralize these responsibilities:

- product-mode state access;
- active instance and active buddy boundary checks;
- request coordination around runtime state;
- broker-issued evidence and controlled env tools;
- structured runtime feedback;
- safe lifecycle management.

It should not own product workflow policy, hidden routing, generic orchestration, or broad future-proof abstractions.

## Research Basis

The useful external references support a small set of principles:

- Python `socketserver` documents the difference between synchronous serving and threaded request handling, including per-handler exception isolation.
- Python socket timeout behavior confirms that socket timeouts surface as `TimeoutError` / `OSError` and must be treated as normal transport failure.
- JSON-RPC 2.0 gives a simple model for request ids, result-or-error responses, and structured error objects.
- The Language Server Protocol uses `Content-Length` framing over streams with JSON payloads, which avoids ambiguous "read until EOF" message framing.
- AWS Builders Library notes that timeout or failure does not prove side effects did not happen, so retried writes need idempotency.
- Google SRE guidance warns against retry amplification and recommends clear retriable vs non-retriable errors and retry budgets.

References:

- https://docs.python.org/3.9/library/socketserver.html
- https://docs.python.org/3/library/socket.html
- https://www.jsonrpc.org/specification
- https://github.com/microsoft/language-server-protocol/blob/gh-pages/_specifications/lsp/3.18/specification.md
- https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/
- https://sre.google/sre-book/addressing-cascading-failures/

## Options Considered

Option 1: Patch the existing broker loop.

This would catch `BrokenPipeError`, raise the client timeout, and maybe clean stale pid files. It is fast, but it preserves the same structural problems: one synchronous loop, unclear protocol framing, inconsistent timeouts, no lifecycle recovery, and no idempotent write semantics.

Use this only as an emergency stabilization patch. It is not the target design.

Option 2: Replace the current broker with Runtime Broker V2.

This keeps the Unix socket and product-mode broker boundary, but rewrites the broker as a small local RPC gateway with explicit transport, protocol, coordinator, dispatcher, and lifecycle boundaries.

This is the recommended direction. It directly solves the observed failure mode while improving the broker's architecture without turning BuddySwitch into a distributed platform.

Option 3: Remove the long-lived broker and run every operation as a CLI command under the runtime lock.

This reduces daemon lifecycle complexity, but weakens the current runtime shape. BuddySwitch already depends on broker-issued evidence, controlled env tools, active instance boundaries, and centralized state feedback. Removing the broker now would move complexity into many command paths.

This is not recommended.

## Recommended Architecture

Runtime Broker V2 should be a near-monolith with clear module boundaries:

```text
scripts/runtime_kernel/protocol.py
scripts/runtime_kernel/server.py
scripts/runtime_kernel/dispatcher.py
scripts/runtime_kernel/coordinator.py
scripts/runtime_kernel/lifecycle.py
scripts/runtime_kernel/client.py
scripts/runtime_kernel/broker.py
```

`protocol.py`

Own message framing and envelope validation. Use `Content-Length` framing with UTF-8 JSON payloads. Every request has `protocol`, `request_id`, `method`, `params`, and `deadline_ms`. Write methods also carry an `idempotency_key`.

`server.py`

Own Unix socket accept/read/write and bounded request execution. Use a bounded thread pool or `socketserver.ThreadingMixIn` style request isolation. Default `max_workers` should be small, such as 4. A client disconnect or malformed request must not terminate the broker process.

`dispatcher.py`

Own method dispatch and existing product-mode checks. Keep `prepare`, `persist`, and `env.tool` as the main methods. Preserve active instance, active buddy, and instance status validation.

`coordinator.py`

Own runtime coordination. `prepare` and `persist` are write operations. `env.tool` declares read or write mode by action. Unknown env tool actions default to write mode. The first implementation can still use the existing file lock, but the lock policy must be explicit at this layer.

`lifecycle.py`

Own `ping`, `status`, `ensure`, stale pid cleanup, stale socket cleanup, and broker startup readiness. Shell launcher code should stop reimplementing broker health logic ad hoc.

`client.py`

Own deadline configuration, request ids, retry budget, and one controlled ensure-and-retry path for missing or stale brokers. It must not let agents bypass product-mode state safeguards.

`broker.py`

Remain a thin CLI entry point: parse args, call lifecycle/server, return process status.

## Protocol Contract

Request shape:

```json
{
  "protocol": "buddyswitch-runtime-broker/v2",
  "request_id": "req-...",
  "method": "persist",
  "params": {},
  "deadline_ms": 35000,
  "idempotency_key": "persist:<run-id>:<result-hash>"
}
```

Success response:

```json
{
  "protocol": "buddyswitch-runtime-broker/v2",
  "request_id": "req-...",
  "ok": true,
  "result": {}
}
```

Error response:

```json
{
  "protocol": "buddyswitch-runtime-broker/v2",
  "request_id": "req-...",
  "ok": false,
  "error": {
    "code": "E_RUNTIME_BROKER_BUSY",
    "message": "runtime broker is at request capacity",
    "retriable": true,
    "retry_after_ms": 250,
    "permission_boundary": "product-mode-runtime-broker"
  }
}
```

Compatibility note:

Keep the existing product-mode response payloads under `result` initially. Do not run long-lived v1 and v2 stacks side by side. Instead, change the broker and client together in one focused change set, with tests covering the public CLI behavior.

## Timeout Policy

The current client timeout and runtime lock timeout conflict.

Runtime Broker V2 should use separate timeout concepts:

- `connect_timeout`: 0.5 to 1 second by default.
- `request_deadline`: passed in the request, default 35 seconds.
- `runtime_lock_timeout`: no greater than the request deadline minus response margin.
- `response_timeout`: aligned with request deadline, not a hard 3 second all-purpose timeout.

If a request deadline expires before the lock is acquired, the broker returns a structured busy/timeout response. If the client disconnects first, the broker records the disconnect and continues serving other requests.

## Retry Policy

Retries must be conservative:

- `ping`, `status`, and read-only env tool requests may be retried once automatically.
- `prepare` should generally not be retried blindly because it can reserve run context.
- `persist` may be retried only when an idempotency key is present.
- malformed requests, active buddy mismatch, active instance mismatch, and permission boundary errors are not retriable.
- broker busy, stale socket, and transport reset may be retried under a small local retry budget.

The client should try one controlled `ensure` when the socket is missing or stale. It should not keep looping, and it should not ask the agent to run process diagnostics as part of the normal path.

## Idempotency Policy

The most important side-effecting operation is `persist`.

Runtime Broker V2 should make `persist` idempotent around the prepared run identity and result content:

- key: `persist:<run_id>:<result_hash>`;
- same key and same payload: return the original receipt;
- same run id and different result hash: return conflict and do not write;
- missing key on retryable transport recovery: return a non-retriable error before writing.

This handles the hard case where the client timed out but the broker actually committed the write.

## Locking Policy

Keep the existing file lock as the first V2 coordination primitive. Do not introduce SQLite, external queues, or a generic transaction engine just to solve this broker issue.

Change the policy boundary:

- `prepare`: write lock;
- `persist`: write lock;
- `env.tool`: action declares read or write;
- unknown env tool action: write lock;
- lifecycle `ping/status`: no runtime state write lock;
- lifecycle `ensure/stop`: launcher-level lifecycle control, not a normal env tool operation.

If read/write distinction becomes risky during implementation, default more actions to write lock. The architecture should make the choice explicit even if the first version is conservative.

## Lifecycle Policy

Broker health is not "pid file exists" and not "socket path exists".

Runtime Broker V2 health requires:

- pid belongs to a live process;
- socket exists and is a Unix socket;
- `ping` succeeds with the expected protocol, instance id, and active buddy;
- pid file, socket marker, and actual socket path agree.

`ensure` should:

1. Check health with `ping`.
2. If healthy, return the socket path.
3. If stale, clean pid file, marker file, and socket path.
4. Start the broker.
5. Wait for `ping`, not just socket existence.
6. Return structured failure with the broker log path if startup fails.

This moves normal recovery out of ad hoc agent diagnostics and into launcher-owned runtime behavior.

## Error Contract

Errors should be structured enough for the host to act without guessing:

- `code`: stable machine-readable code.
- `message`: short human-readable message.
- `retriable`: boolean.
- `retry_after_ms`: optional.
- `permission_boundary`: optional.
- `allowed_next_actions`: optional.
- `request_id`: always present when known.
- `broker_status`: optional for lifecycle failures.

Important errors:

- `E_RUNTIME_BROKER_BUSY`
- `E_RUNTIME_BROKER_DEADLINE_EXCEEDED`
- `E_RUNTIME_BROKER_CLIENT_DISCONNECTED`
- `E_RUNTIME_BROKER_STALE_SOCKET`
- `E_RUNTIME_BROKER_PROTOCOL`
- `E_RUNTIME_BROKER_PERMISSION`
- `E_RUNTIME_PERSIST_CONFLICT`
- `E_RUNTIME_IDEMPOTENCY_REQUIRED`

Do not collapse all transport and permission failures into `E_RUNTIME_BROKER_UNAVAILABLE`. That hides the next correct action.

## Implementation Order

Stage 1: Protocol and server isolation.

- Add `protocol.py` framing tests.
- Add `server.py` request-isolation tests.
- Prove client disconnect and `BrokenPipeError` do not kill the broker.
- Keep business dispatch behavior unchanged.

Stage 2: Client deadline and lifecycle health.

- Split connect timeout from response deadline.
- Add request ids.
- Add `ping/status`.
- Replace shell pid/socket-only checks with lifecycle health.
- Add one controlled ensure-and-retry path for stale/missing socket.

Stage 3: Coordinator boundary.

- Move runtime lock policy into `coordinator.py`.
- Keep write lock for `prepare/persist`.
- Classify env tool actions as read/write, with unknown actions defaulting to write.

Stage 4: Persist idempotency.

- Add idempotency key generation and validation.
- Make duplicate persist return the original receipt.
- Make same run id with different payload return conflict before writes.

Stage 5: Cleanup and documentation.

- Remove obsolete broker loop code.
- Remove duplicated lifecycle logic from shell where practical.
- Document operational runbook and error meanings.

## Acceptance Tests

The redesign is not done until these behaviors are proven:

- A slow handler exceeding the client response timeout does not terminate the broker.
- A client that disconnects before response does not terminate the broker.
- A second request can receive `ping` after a prior request disconnects.
- Runtime lock contention no longer causes a 3 second false broker-dead report.
- Missing socket plus stale pid is cleaned by `ensure`.
- Healthy broker status is verified by `ping`, not only by pid/socket files.
- Duplicate `persist` with the same idempotency key returns the same receipt.
- Duplicate `persist` with the same run id but different result hash returns conflict without writes.
- Product-mode `prepare` and `persist` still cannot bypass the broker.
- Active buddy and active instance mismatch errors remain structured and non-retriable.

## Non-Goals

Do not add these as part of Runtime Broker V2:

- gRPC;
- HTTP daemon;
- external process supervisor dependency;
- database-backed queue;
- generic workflow engine;
- plugin or rule framework;
- hidden task or handoff routing policy;
- long-lived v1/v2 dual runtime paths;
- agent-facing instructions to bypass the broker when it fails.

## Next Step

The next useful artifact is an implementation plan, not more broad research.

The plan should be written as small verified tasks:

1. Protocol framing tests and implementation.
2. Server isolation tests and implementation.
3. Client timeout/deadline update.
4. Lifecycle health and ensure.
5. Coordinator lock policy.
6. Persist idempotency.
7. End-to-end product-mode broker verification.

Each task should have a focused failing test first and a narrow implementation. Keep the change set centered on the broker reliability bottleneck.
