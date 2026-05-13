# Runtime Broker V2 Runbook

## Scope

Runtime broker v2 is a local Unix socket RPC gateway for product-mode `prepare`, `persist`, and `env.tool`.
It is not a workflow orchestrator, queue system, or generic orchestration layer.

## Health Criteria

A broker is healthy only when all checks pass:

1. `runtime-broker.pid` exists and points to a live process.
2. Socket path exists and is a Unix socket.
3. Socket marker file exists and matches the socket path.
4. `python3 scripts/runtime_kernel/broker.py ping ...` succeeds with:
   - `protocol == buddyswitch-runtime-broker/v2`
   - expected `instance_id`
   - expected `active_buddy`
   - consistent `pid` and `socket_path`.

Do not treat `pid` or socket existence alone as healthy.

## Ensure Flow

`python3 scripts/runtime_kernel/broker.py ensure ...` performs:

1. Full lifecycle status check.
2. Stale state cleanup (`pid`, marker, socket) when unhealthy.
3. Broker process start via `serve`.
4. Readiness wait until `ping` passes.
5. JSON output containing `ok`, `socket_path`, and status/error details.

Launcher shell wrappers (`tools/launcher/runtime_broker.sh`) must delegate lifecycle logic to `status|ensure|stop`, not re-implement `kill -0` style health checks.

## Retry Policy

Client retries are conservative and bounded:

- One controlled retry max.
- `ping`, `status`, read-only `env.tool`: retry once on retriable transport/lifecycle errors.
- `prepare`: no blind retry.
- `persist`: retry only with `idempotency_key`.
- Non-idempotent write `env.tool`: no automatic retry.
- Missing/stale broker path uses one controlled `ensure` before retry.

## Error Codes

Important runtime broker codes:

- `E_RUNTIME_BROKER_BUSY`: bounded worker capacity is exhausted.
- `E_RUNTIME_BROKER_DEADLINE_EXCEEDED`: request deadline/lock window expired.
- `E_RUNTIME_BROKER_CLIENT_DISCONNECTED`: peer disconnected during broker transport.
- `E_RUNTIME_BROKER_STALE_SOCKET`: lifecycle inconsistency (pid/socket/marker/ping mismatch).
- `E_RUNTIME_BROKER_PROTOCOL`: malformed frame or invalid envelope.
- `E_RUNTIME_BROKER_PERMISSION`: active instance/buddy/status or boundary rejection.
- `E_RUNTIME_PERSIST_CONFLICT`: same run id persisted with conflicting result payload.
- `E_RUNTIME_IDEMPOTENCY_REQUIRED`: write request (`persist`) missing required idempotency key.

## Focused Verification Commands

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py -q
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -k runtime_broker -q
```
