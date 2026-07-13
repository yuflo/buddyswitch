"""Runtime broker v2 client for product-mode env.tool and health methods."""

from __future__ import annotations

import hashlib
import json
import os
import errno
from dataclasses import dataclass
from pathlib import Path
import socket
from typing import Any
import uuid

from env.tool_runtime import registry as tool_registry

from runtime_kernel import protocol

PROTOCOL = protocol.PROTOCOL


class RuntimeBrokerError(RuntimeError):
    """Raised when the runtime broker is unavailable or request handling fails."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        response: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.response = response
        self.details = details or {}


@dataclass(frozen=True)
class RuntimeBrokerTimeouts:
    connect_timeout_seconds: float = 0.75
    request_deadline_ms: int = 35000
    response_margin_ms: int = 1000


@dataclass(frozen=True)
class BrokerRetryDecision:
    should_retry: bool
    reason: str


def broker_unavailable_feedback(*, socket_path: Path | None = None) -> dict[str, Any]:
    raw_actor_id = os.environ.get("BUDDYSWITCH_ACTOR_ID")
    actor_id = raw_actor_id.strip() if isinstance(raw_actor_id, str) and raw_actor_id.strip() else "<actor-id>"
    feedback: dict[str, Any] = {
        "permission_boundary": "product-mode-runtime-broker",
        "stop_condition": "stop_and_report_do_not_bypass_broker",
        "allowed_next_actions": [
            "Report that the launcher-managed runtime broker is unavailable.",
            "Do not write raw BuddySwitch state directly.",
            "Do not bypass product-mode runtime safeguards via debug APIs.",
        ],
        "command_hint": f"./buddyswitch-codex instance attach {actor_id}",
    }
    if socket_path is not None:
        feedback["socket_path"] = str(socket_path)
    return feedback


def runtime_broker_socket_from_env() -> Path:
    raw = os.environ.get("BUDDYSWITCH_RUNTIME_BROKER_SOCKET")
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "BUDDYSWITCH_RUNTIME_BROKER_SOCKET is required in product mode.",
            details=broker_unavailable_feedback(),
        )
    return Path(raw.strip())


def canonical_result_hash(result: dict[str, Any]) -> str:
    if not isinstance(result, dict):
        raise ValueError("result must be an object to compute canonical_result_hash")
    body = json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _response_timeout_seconds(request_deadline_ms: int, response_margin_ms: int) -> float:
    return max(0.1, (request_deadline_ms + max(0, response_margin_ms)) / 1000.0)


def _normalize_broker_error(
    response: dict[str, Any],
    *,
    request_id: str,
) -> RuntimeBrokerError:
    error = response.get("error") if isinstance(response.get("error"), dict) else {}
    code = error.get("code") if isinstance(error.get("code"), str) else "E_RUNTIME_BROKER_PROTOCOL"
    message = error.get("message") if isinstance(error.get("message"), str) else "runtime broker request failed"
    details: dict[str, Any] = dict(error)
    details["request_id"] = request_id
    for key, value in response.items():
        if key not in {"protocol", "request_id", "ok", "error"}:
            details[key] = value
    return RuntimeBrokerError(code, message, response=response, details=details)


def _is_read_only_env_tool(method: str, params: dict[str, Any]) -> bool:
    if method != "env.tool":
        return False
    tool = params.get("tool")
    action_raw = params.get("action")
    if not isinstance(tool, str) or not tool.strip() or not isinstance(action_raw, str) or not action_raw.strip():
        return False
    action = action_raw.strip().replace("-", "_")
    mutates = tool_registry.action_mutates(tool.strip(), action)
    if not isinstance(mutates, str):
        return False
    return mutates == "none"


def _retry_decision(
    *,
    error: RuntimeBrokerError,
    method: str,
    params: dict[str, Any],
    idempotency_key: str | None,
) -> BrokerRetryDecision:
    del idempotency_key
    code = error.code
    retriable = bool(error.details.get("retriable", False))

    retriable_codes = {
        "E_RUNTIME_BROKER_UNAVAILABLE",
        "E_RUNTIME_BROKER_STALE_SOCKET",
        "E_RUNTIME_BROKER_BUSY",
        "E_RUNTIME_BROKER_DEADLINE_EXCEEDED",
        "E_RUNTIME_BROKER_CLIENT_DISCONNECTED",
    }
    if code not in retriable_codes and not retriable:
        return BrokerRetryDecision(False, "non-retriable error")

    if method in {"ping", "status"}:
        return BrokerRetryDecision(True, "read health request")

    if _is_read_only_env_tool(method, params):
        return BrokerRetryDecision(True, "read-only env.tool request")

    return BrokerRetryDecision(False, "write operation does not auto-retry")


def _request_once(
    *,
    socket_path: Path,
    request: dict[str, Any],
    connect_timeout_seconds: float,
    response_timeout_seconds: float,
) -> dict[str, Any]:
    request_id = str(request.get("request_id"))
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(connect_timeout_seconds)
            sock.connect(str(socket_path))
            sock.settimeout(response_timeout_seconds)
            protocol.write_message(sock, request)
            response = protocol.read_message(sock)
    except socket.timeout as exc:
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_DEADLINE_EXCEEDED",
            f"runtime broker request timed out at {socket_path}: {exc}",
            details={
                **broker_unavailable_feedback(socket_path=socket_path),
                "request_id": request_id,
                "retriable": True,
            },
        ) from exc
    except protocol.BrokerProtocolError as exc:
        code = "E_RUNTIME_BROKER_CLIENT_DISCONNECTED"
        message = exc.message
        retriable = True
        if "invalid JSON" in exc.message or "header exceeds limit" in exc.message or "invalid broker header line" in exc.message:
            code = "E_RUNTIME_BROKER_PROTOCOL"
            retriable = False
        raise RuntimeBrokerError(
            code,
            f"runtime broker response protocol error: {message}",
            details={
                "request_id": request_id,
                "retriable": retriable,
                "permission_boundary": "broker-protocol",
            },
        ) from exc
    except ConnectionResetError as exc:
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_CLIENT_DISCONNECTED",
            f"runtime broker reset connection at {socket_path}",
            details={
                **broker_unavailable_feedback(socket_path=socket_path),
                "request_id": request_id,
                "retriable": True,
            },
        ) from exc
    except FileNotFoundError as exc:
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            f"runtime broker socket not found: {socket_path}",
            details={
                **broker_unavailable_feedback(socket_path=socket_path),
                "request_id": request_id,
                "retriable": True,
            },
        ) from exc
    except OSError as exc:
        if exc.errno in {errno.ENOENT, errno.ECONNREFUSED}:
            raise RuntimeBrokerError(
                "E_RUNTIME_BROKER_UNAVAILABLE",
                f"runtime broker unavailable at {socket_path}: {exc}",
                details={
                    **broker_unavailable_feedback(socket_path=socket_path),
                    "request_id": request_id,
                    "retriable": True,
                },
            ) from exc
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_PROTOCOL",
            f"runtime broker transport error at {socket_path}: {exc}",
            details={
                "request_id": request_id,
                "retriable": False,
                "permission_boundary": "broker-transport",
            },
        ) from exc

    if response.get("protocol") != PROTOCOL:
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_PROTOCOL",
            f"runtime broker protocol mismatch: {response.get('protocol')!r}",
            response=response if isinstance(response, dict) else None,
            details={"request_id": request_id, "retriable": False},
        )

    returned_request_id = response.get("request_id")
    if returned_request_id != request_id:
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_PROTOCOL",
            f"runtime broker request_id mismatch: expected {request_id!r}, got {returned_request_id!r}",
            response=response,
            details={"request_id": request_id, "retriable": False},
        )

    if response.get("ok") is not True:
        raise _normalize_broker_error(response, request_id=request_id)

    result = response.get("result")
    if not isinstance(result, dict):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_PROTOCOL",
            "runtime broker success response missing object result",
            response=response,
            details={"request_id": request_id, "retriable": False},
        )
    return result


def request_runtime_broker(
    method: str,
    params: dict[str, Any],
    *,
    idempotency_key: str | None = None,
    result_hash: str | None = None,
    socket_path: Path | None = None,
    timeouts: RuntimeBrokerTimeouts = RuntimeBrokerTimeouts(),
) -> dict[str, Any]:
    del result_hash
    if not isinstance(method, str) or not method.strip():
        raise ValueError("method must be a non-empty string")
    if not isinstance(params, dict):
        raise ValueError("params must be an object")

    chosen_socket = runtime_broker_socket_from_env() if socket_path is None else socket_path
    method_name = method.strip()
    deadline_ms = max(1, int(timeouts.request_deadline_ms))
    request_params = dict(params)
    response_timeout_seconds = _response_timeout_seconds(
        request_deadline_ms=max(1, int(timeouts.request_deadline_ms)),
        response_margin_ms=max(0, int(timeouts.response_margin_ms)),
    )

    attempts = 0
    last_error: RuntimeBrokerError | None = None
    while attempts < 2:
        attempts += 1
        request = protocol.make_request(
            request_id=f"req-{uuid.uuid4()}",
            method=method_name,
            params=request_params,
            deadline_ms=deadline_ms,
            idempotency_key=idempotency_key,
        )
        try:
            return _request_once(
                socket_path=chosen_socket,
                request=request,
                connect_timeout_seconds=float(timeouts.connect_timeout_seconds),
                response_timeout_seconds=response_timeout_seconds,
            )
        except RuntimeBrokerError as exc:
            last_error = exc
            decision = _retry_decision(error=exc, method=method_name, params=params, idempotency_key=idempotency_key)
            if attempts >= 2 or not decision.should_retry:
                raise
    if last_error is not None:
        raise last_error
    raise RuntimeBrokerError("E_RUNTIME_BROKER_PROTOCOL", "runtime broker request failed without response")
