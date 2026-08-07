"""Runtime Broker v2 request validation and envelope utilities."""

from __future__ import annotations

from typing import Any

PROTOCOL = "buddyswitch-runtime-broker/v2"


class BrokerProtocolError(ValueError):
    """Raised when a broker wire message violates protocol constraints."""

    def __init__(self, code: str, message: str, *, request_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id


def make_request(
    *,
    request_id: str,
    method: str,
    params: dict[str, Any],
    deadline_ms: int,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "method": method,
        "params": params,
        "deadline_ms": deadline_ms,
    }
    if isinstance(idempotency_key, str) and idempotency_key.strip():
        request["idempotency_key"] = idempotency_key.strip()
    return request


def _raise_protocol(message: str, *, request_id: str | None = None) -> None:
    raise BrokerProtocolError("E_RUNTIME_BROKER_PROTOCOL", message, request_id=request_id)


def validate_request(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        _raise_protocol("request must be an object")

    protocol = request.get("protocol")
    if protocol != PROTOCOL:
        _raise_protocol(f"unsupported protocol: {protocol!r}")

    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        _raise_protocol("request_id must be a non-empty string")

    method = request.get("method")
    if not isinstance(method, str) or not method.strip():
        _raise_protocol("method must be a non-empty string", request_id=request_id)

    params = request.get("params")
    if not isinstance(params, dict):
        _raise_protocol("params must be an object", request_id=request_id)

    deadline_ms = request.get("deadline_ms")
    if not isinstance(deadline_ms, int) or deadline_ms <= 0:
        _raise_protocol("deadline_ms must be a positive integer", request_id=request_id)

    return request


def success_response(request_id: str | None, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "ok": True,
        "result": result,
    }


def error_response(
    request_id: str | None,
    error: dict[str, Any] | None = None,
    *,
    code: str | None = None,
    message: str | None = None,
    retriable: bool | None = None,
    **extra: Any,
) -> dict[str, Any]:
    if error is not None:
        if code is None:
            code = str(error.get("code", "E_RUNTIME_BROKER_PROTOCOL"))
        if message is None:
            message = str(error.get("message", "runtime broker error"))
        if retriable is None:
            retriable = bool(error.get("retriable", False))
        for key, value in error.items():
            if key not in {"code", "message", "retriable"} and key not in extra:
                extra[key] = value
    if code is None:
        code = "E_RUNTIME_BROKER_PROTOCOL"
    if message is None:
        message = "runtime broker error"
    if retriable is None:
        retriable = False

    error_payload: dict[str, Any] = {
        "code": code,
        "message": message,
        "retriable": retriable,
    }
    for key, value in extra.items():
        if value is not None:
            error_payload[key] = value
    return {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "ok": False,
        "error": error_payload,
    }
