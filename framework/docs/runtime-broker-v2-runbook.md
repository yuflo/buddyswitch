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
   - consistent `pid` and `socket_path`
   - root facts: `runtime_root`, `cwd`, `env_store_root`, `runtime_workspace`.
5. Root boundary checks pass:
   - `runtime_workspace == true`
   - `env_store_root` resolves to the instance runtime workspace (or a subpath inside it)
   - `runtime_root` and `cwd` resolve to the same runtime workspace boundary.

Do not treat `pid` or socket existence alone as healthy.

## Ensure Flow

`python3 scripts/runtime_kernel/broker.py ensure ...` performs:

1. Full lifecycle status check.
2. Stale state cleanup (`pid`, marker, socket) when unhealthy.
3. Broker process start via `serve`.
4. Readiness wait until `ping` passes.
5. JSON output containing `ok`, `socket_path`, and status/error details.
6. On startup failure/timeout, returns structured error with `log_file`, `socket_path`, `pid_file`, and removes stale marker/socket artifacts.

Launcher shell wrappers (`tools/launcher/runtime_broker.sh`) must delegate lifecycle logic to `status|ensure|stop`, not re-implement `kill -0` style health checks.
Launcher-owned ensure is the only lifecycle repair path in product flows (`instance start/open` before Codex launch).
Lifecycle script path and cwd must come from the runtime workspace (`BUDDYSWITCH_WORKSPACE_DIR`), not source checkout root.

## Retry Policy

Client retries are conservative and bounded:

- One controlled retry max.
- `ping`, `status`, read-only `env.tool`: retry once on retriable transport/lifecycle errors.
- `prepare`: no blind retry.
- `persist`: retry only with `idempotency_key`.
- Non-idempotent write `env.tool`: no automatic retry.
- Product client does not run `broker.py ensure`, does not write broker pid/socket/marker/log files, and does not mutate lifecycle state.
- Stale/missing broker returns structured feedback with `permission_boundary=product-mode-runtime-broker` and launcher reopen hint `./buddyswitch-codex instance open <instance-id>`.

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

When broker lifecycle is unavailable in product mode, include:

- `permission_boundary: product-mode-runtime-broker`
- `stop_condition: stop_and_report_do_not_bypass_broker`
- `command_hint: ./buddyswitch-codex instance open <instance-id>`.

## Focused Verification Commands

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py -q
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -k runtime_broker -q
```
