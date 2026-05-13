#!/usr/bin/env python3
"""Runtime broker v2 client for product-mode turn tools."""

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

from env.tools import contracts as tool_contracts

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
    raw_instance_id = os.environ.get("BUDDYSWITCH_INSTANCE_ID")
    instance_id = raw_instance_id.strip() if isinstance(raw_instance_id, str) and raw_instance_id.strip() else "<instance-id>"
    feedback: dict[str, Any] = {
        "permission_boundary": "product-mode-runtime-broker",
        "stop_condition": "stop_and_report_do_not_bypass_broker",
        "allowed_next_actions": [
            "Report that the launcher-managed runtime broker is unavailable.",
            "Do not write raw BuddySwitch state directly.",
            "Do not bypass product-mode runtime safeguards via debug APIs.",
        ],
        "command_hint": f"./buddyswitch-codex instance open {instance_id}",
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


def _require_env(name: str) -> str:
    raw = os.environ.get(name)
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            f"{name} is required in product mode.",
            details=broker_unavailable_feedback(),
        )
    return raw.strip()


def canonical_result_hash(result: dict[str, Any]) -> str:
    if not isinstance(result, dict):
        raise ValueError("result must be an object to compute canonical_result_hash")
    body = json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _extract_run_id(context: dict[str, Any]) -> str:
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    run_envelope = context.get("run_envelope")
    if isinstance(run_envelope, dict):
        turn_identity = run_envelope.get("turn_identity")
        if isinstance(turn_identity, dict):
            run_id = turn_identity.get("run_id")
            if isinstance(run_id, str) and run_id.strip():
                return run_id.strip()
        run_id = run_envelope.get("run_id")
        if isinstance(run_id, str) and run_id.strip():
            return run_id.strip()
    raise ValueError("context.run_envelope.turn_identity.run_id is required for persist idempotency")


def make_persist_idempotency_key(context: dict[str, Any], result: dict[str, Any]) -> str:
    run_id = _extract_run_id(context)
    result_hash = canonical_result_hash(result)
    return f"persist:{run_id}:{result_hash}"


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
    spec = tool_contracts.get_action_spec(tool.strip(), action)
    if not isinstance(spec, dict):
        return False
    return spec.get("mutates") == "none"


def _retry_decision(
    *,
    error: RuntimeBrokerError,
    method: str,
    params: dict[str, Any],
    idempotency_key: str | None,
) -> BrokerRetryDecision:
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

    if method == "prepare":
        return BrokerRetryDecision(False, "prepare does not auto-retry")

    if method == "persist":
        if isinstance(idempotency_key, str) and idempotency_key.strip():
            return BrokerRetryDecision(True, "persist with idempotency key")
        return BrokerRetryDecision(False, "persist missing idempotency key")

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
        # EOF while reading a response is usually a disconnect/reset after request send.
        is_disconnect = "unexpected EOF" in exc.message
        code = "E_RUNTIME_BROKER_CLIENT_DISCONNECTED" if is_disconnect else "E_RUNTIME_BROKER_PROTOCOL"
        raise RuntimeBrokerError(
            code,
            f"runtime broker protocol failure at {socket_path}: {exc.message}",
            details={
                **broker_unavailable_feedback(socket_path=socket_path),
                "request_id": request_id,
                "retriable": is_disconnect,
            },
        ) from exc
    except OSError as exc:
        err = getattr(exc, "errno", None)
        is_stale_socket = err in {errno.ENOENT, errno.ECONNREFUSED, errno.ENOTSOCK}
        code = "E_RUNTIME_BROKER_STALE_SOCKET" if is_stale_socket else "E_RUNTIME_BROKER_CLIENT_DISCONNECTED"
        raise RuntimeBrokerError(
            code,
            f"runtime broker unavailable at {socket_path}: {exc}",
            details={
                **broker_unavailable_feedback(socket_path=socket_path),
                "request_id": request_id,
                "retriable": True,
            },
        ) from exc

    if not isinstance(response, dict):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_PROTOCOL",
            "runtime broker response must be a JSON object.",
            response={"raw_response": response},
            details={"request_id": request_id, "retriable": False},
        )

    if response.get("protocol") != PROTOCOL:
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_PROTOCOL",
            "runtime broker response protocol mismatch.",
            response=response,
            details={"request_id": request_id, "retriable": False},
        )

    response_request_id = response.get("request_id")
    if response_request_id != request_id:
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_PROTOCOL",
            "runtime broker response request_id mismatch.",
            response=response,
            details={"request_id": request_id, "retriable": False},
        )

    if not isinstance(response.get("ok"), bool):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_PROTOCOL",
            "runtime broker response must contain boolean 'ok'.",
            response=response,
            details={"request_id": request_id, "retriable": False},
        )

    if response["ok"] is True:
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeBrokerError(
                "E_RUNTIME_BROKER_PROTOCOL",
                "runtime broker success response must contain object result.",
                response=response,
                details={"request_id": request_id, "retriable": False},
            )
        return result

    raise _normalize_broker_error(response, request_id=request_id)


def request_runtime_broker(
    method: str,
    params: dict[str, Any],
    *,
    deadline_ms: int | None = None,
    idempotency_key: str | None = None,
    result_hash: str | None = None,
    timeouts: RuntimeBrokerTimeouts | None = None,
) -> dict[str, Any]:
    if not isinstance(method, str) or not method.strip():
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker method is required.",
            details=broker_unavailable_feedback(),
        )
    if not isinstance(params, dict):
        raise RuntimeBrokerError(
            "E_RUNTIME_BROKER_UNAVAILABLE",
            "runtime broker params must be an object.",
            details=broker_unavailable_feedback(),
        )

    socket_path = runtime_broker_socket_from_env()
    _require_env("BUDDYSWITCH_INSTANCE_ID")
    _require_env("BUDDYSWITCH_ACTIVE_BUDDY")

    cfg = timeouts or RuntimeBrokerTimeouts()
    request_deadline_ms = int(deadline_ms if isinstance(deadline_ms, int) and deadline_ms > 0 else cfg.request_deadline_ms)
    response_timeout_seconds = _response_timeout_seconds(request_deadline_ms, cfg.response_margin_ms)

    max_attempts = 2
    attempt = 0
    while attempt < max_attempts:
        request_id = f"req-{uuid.uuid4()}"
        request = protocol.make_request(
            request_id=request_id,
            method=method.strip(),
            params=params,
            deadline_ms=request_deadline_ms,
            idempotency_key=idempotency_key,
        )
        if isinstance(result_hash, str) and result_hash.strip():
            request["result_hash"] = result_hash.strip()

        try:
            return _request_once(
                socket_path=socket_path,
                request=request,
                connect_timeout_seconds=cfg.connect_timeout_seconds,
                response_timeout_seconds=response_timeout_seconds,
            )
        except RuntimeBrokerError as exc:
            if attempt >= max_attempts - 1:
                raise
            decision = _retry_decision(
                error=exc,
                method=method.strip(),
                params=params,
                idempotency_key=idempotency_key,
            )
            if not decision.should_retry:
                raise
            attempt += 1
            continue

    raise RuntimeBrokerError(
        "E_RUNTIME_BROKER_UNAVAILABLE",
        "runtime broker request exhausted retry budget.",
        details=broker_unavailable_feedback(socket_path=socket_path),
    )
