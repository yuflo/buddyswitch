#!/usr/bin/env python3
"""Runtime broker coordination policy and runtime lock integration."""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

import turn_runtime
from env.tools import contracts as tool_contracts


class LockMode(str, Enum):
    NONE = "none"
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class RequestDeadline:
    request_id: str
    started_monotonic: float
    deadline_ms: int
    response_margin_ms: int

    def remaining_seconds(self) -> float:
        elapsed = time.monotonic() - self.started_monotonic
        return max(0.0, (self.deadline_ms / 1000.0) - elapsed)

    def lock_timeout_seconds(self) -> float:
        return max(0.0, self.remaining_seconds() - (self.response_margin_ms / 1000.0))

    def expired(self) -> bool:
        return self.remaining_seconds() <= 0.0


def _error(
    code: str,
    message: str,
    *,
    retriable: bool,
    retry_after_ms: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "retriable": retriable,
        },
    }
    if retry_after_ms is not None:
        payload["error"]["retry_after_ms"] = retry_after_ms
    if extra:
        payload.update(extra)
    return payload


def lock_mode_for_request(method: str, params: dict[str, Any]) -> LockMode:
    if method in {"prepare", "persist"}:
        return LockMode.WRITE
    if method in {"ping", "status"}:
        return LockMode.NONE
    if method != "env.tool":
        return LockMode.WRITE

    tool = params.get("tool")
    action_raw = params.get("action")
    if not isinstance(tool, str) or not tool.strip() or not isinstance(action_raw, str) or not action_raw.strip():
        return LockMode.WRITE

    action = action_raw.strip().replace("-", "_")
    spec = tool_contracts.get_action_spec(tool.strip(), action)
    if not isinstance(spec, dict):
        return LockMode.WRITE
    if spec.get("mutates") == "none":
        return LockMode.READ
    return LockMode.WRITE


def _lock_context(*, session: dict[str, Any], mode: LockMode, timeout_seconds: float):
    lock_mode = "read" if mode == LockMode.READ else "write"
    return turn_runtime._hold_product_runtime_lock(session, mode=lock_mode, timeout_seconds=timeout_seconds)


def dispatch_with_coordination(
    request: dict[str, Any],
    session: dict[str, Any],
    dispatch_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    *,
    response_margin_ms: int = 1000,
) -> dict[str, Any]:
    method = str(request.get("method", "")).strip()
    params = request.get("params")
    if not isinstance(params, dict):
        params = {}
    request_id = str(request.get("request_id", "<unknown>"))
    deadline_ms_raw = request.get("deadline_ms")
    deadline_ms = int(deadline_ms_raw) if isinstance(deadline_ms_raw, int) else 35000

    deadline = RequestDeadline(
        request_id=request_id,
        started_monotonic=time.monotonic(),
        deadline_ms=deadline_ms,
        response_margin_ms=response_margin_ms,
    )
    if deadline.expired():
        return _error(
            "E_RUNTIME_BROKER_DEADLINE_EXCEEDED",
            "runtime broker request deadline exceeded before dispatch",
            retriable=True,
            retry_after_ms=250,
        )

    mode = lock_mode_for_request(method, params)
    if mode == LockMode.NONE:
        return dispatch_fn(request, session)

    timeout_seconds = deadline.lock_timeout_seconds()
    if timeout_seconds <= 0.0:
        return _error(
            "E_RUNTIME_BROKER_DEADLINE_EXCEEDED",
            "runtime broker request deadline exceeded before lock acquisition",
            retriable=True,
            retry_after_ms=250,
        )

    try:
        with _lock_context(session=session, mode=mode, timeout_seconds=timeout_seconds):
            return dispatch_fn(request, session)
    except TimeoutError as exc:
        return _error(
            "E_RUNTIME_BROKER_DEADLINE_EXCEEDED",
            str(exc),
            retriable=True,
            retry_after_ms=250,
        )
    except turn_runtime.RuntimeFeedbackError as exc:
        return _error(
            exc.code,
            exc.message,
            retriable=False,
            extra=exc.details,
        )
