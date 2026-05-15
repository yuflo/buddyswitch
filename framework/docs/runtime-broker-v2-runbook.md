# Runtime Broker V2 Runbook (Runless)

Runtime broker v2 is a local Unix socket RPC gateway for product-mode runtime calls.

## Supported Methods

- `env.tool`
- `ping`
- `status`

Unsupported methods (including legacy `prepare`/`persist`) are rejected with broker-protocol errors.

## Request Envelope

- `protocol`: `buddyswitch-runtime-broker/v2`
- `request_id`: unique id per request
- `method`: one of supported methods
- `params`: JSON object payload
- `deadline_ms`: positive integer

## Coordination

- Lock mode is derived from env.tool mutability metadata.
- Read-only actions use shared lock.
- Mutating actions use exclusive lock.

## Retry Policy

- `ping`/`status` may retry on transient transport errors.
- Read-only env.tool requests may retry on transient broker errors.
- Mutating env.tool requests do not auto-retry without explicit operation-id semantics.

## Structured Error Signals

Typical broker error codes:

- `E_RUNTIME_BROKER_UNAVAILABLE`
- `E_RUNTIME_BROKER_PERMISSION`
- `E_RUNTIME_BROKER_PROTOCOL`
- `E_RUNTIME_BROKER_DEADLINE_EXCEEDED`
- `E_RUNTIME_BROKER_CLIENT_DISCONNECTED`

Services may return domain-specific `permission_boundary`, `why_blocked`, `impact`, and `retry_guidance` fields inside tool responses.
