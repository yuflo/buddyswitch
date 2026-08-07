"""Runtime Broker coordination policy and advisory runtime lock."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator

import buddyswitch.foundation.state.runtime as state_runtime
from buddyswitch.foundation.tool_runtime import registry as tool_registry


_RUNTIME_LOCK_TIMEOUT_ENV = "BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS"
_RUNTIME_LOCK_DEFAULT_TIMEOUT_SECONDS = 30.0
_RUNTIME_LOCK_POLL_SECONDS = 0.05


def _runtime_lock_timeout_seconds(default: float = _RUNTIME_LOCK_DEFAULT_TIMEOUT_SECONDS) -> float:
    raw = os.environ.get(_RUNTIME_LOCK_TIMEOUT_ENV)
    if raw is None:
        return default
    try:
        parsed = float(raw)
    except ValueError:
        return default
    if parsed <= 0:
        return default
    return parsed


def _runtime_session_root(product_session: dict[str, Any]) -> Path:
    payload = product_session.get("payload")
    if isinstance(payload, dict):
        workspace_dir = payload.get("workspace_dir")
        if isinstance(workspace_dir, str) and workspace_dir.strip():
            return Path(workspace_dir.strip()).expanduser().resolve(strict=False)

    instance_json = product_session.get("instance_json")
    if isinstance(instance_json, Path):
        if instance_json.parent.name == "instances":
            return instance_json.parent.parent
        return instance_json.parent

    return state_runtime.ROOT


def _runtime_lock_path(product_session: dict[str, Any]) -> Path:
    workspace_root = _runtime_session_root(product_session)
    return workspace_root / ".runtime" / "locks" / "runtime.lock"


@contextmanager
def _hold_product_runtime_lock(
    product_session: dict[str, Any],
    *,
    mode: str = "write",
    timeout_seconds: float | None = None,
) -> Iterator[None]:
    """Acquire the Broker-scoped advisory lock for runtime requests."""

    if mode not in {"read", "write"}:
        raise ValueError("mode must be 'read' or 'write'")

    timeout = _runtime_lock_timeout_seconds() if timeout_seconds is None else max(0.0, float(timeout_seconds))
    lock_path = _runtime_lock_path(product_session)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    lock_mode = fcntl.LOCK_SH if mode == "read" else fcntl.LOCK_EX
    deadline = time.monotonic() + timeout

    with lock_path.open("a+", encoding="utf-8") as handle:
        while True:
            try:
                fcntl.flock(handle.fileno(), lock_mode | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"runtime lock acquisition timed out after {timeout:.2f}s")
                time.sleep(_RUNTIME_LOCK_POLL_SECONDS)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class LockMode(str, Enum):
    NONE = "none"
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class RequestDeadline:
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
    return payload


def lock_mode_for_request(method: str, params: dict[str, Any]) -> LockMode:
    if method in {"ping", "status"}:
        return LockMode.NONE
    if method != "env.tool":
        return LockMode.WRITE

    tool = params.get("tool")
    action_raw = params.get("action")
    if not isinstance(tool, str) or not tool.strip() or not isinstance(action_raw, str) or not action_raw.strip():
        return LockMode.WRITE

    action = action_raw.strip().replace("-", "_")
    mutates = tool_registry.action_mutates(tool.strip(), action)
    if not isinstance(mutates, str):
        return LockMode.WRITE
    if mutates == "none":
        return LockMode.READ
    return LockMode.WRITE


def _lock_context(*, session: dict[str, Any], mode: LockMode, timeout_seconds: float):
    lock_mode = "read" if mode == LockMode.READ else "write"
    return _hold_product_runtime_lock(session, mode=lock_mode, timeout_seconds=timeout_seconds)


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
    deadline_ms_raw = request.get("deadline_ms")
    deadline_ms = int(deadline_ms_raw) if isinstance(deadline_ms_raw, int) else 35000

    deadline = RequestDeadline(
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
