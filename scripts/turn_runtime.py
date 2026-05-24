#!/usr/bin/env python3
"""Runless BuddySwitch runtime primitives.

This module no longer owns prepare/persist run lifecycle. Runtime broker entrypoints
route only ``env.tool`` plus health methods, and services mutate durable product
objects directly.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
import time
from pathlib import Path
from typing import Any, Iterator

from env_manifest import DEFAULT_MANIFEST
from env.repos import runtime_files
from env.tool_runtime import registry as tool_registry

ROOT = runtime_files.ROOT
REPO_ROOT = Path(__file__).resolve().parents[1]

_RUNTIME_LOCK_TIMEOUT_ENV = "BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS"
_RUNTIME_LOCK_DEFAULT_TIMEOUT_SECONDS = 30.0
_RUNTIME_LOCK_POLL_SECONDS = 0.05


class RuntimeFeedbackError(ValueError):
    """Structured runtime feedback for broker and CLI responses."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


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

    return ROOT


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
    """Acquire a broker-scoped advisory lock for runtime requests."""

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


def _build_env_tools_desc() -> dict[str, Any]:
    """Expose canonical env tool contract and semantics map for runtime consumers."""

    return tool_registry.env_tools_description(exclude_tools={"buddybox"})


def _runtime_status_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "runtime_mode": "runless",
        "manifest_path": str(DEFAULT_MANIFEST),
        "env_tools": _build_env_tools_desc(),
    }


def _cmd_status(_args: argparse.Namespace) -> int:
    print(json.dumps(_runtime_status_payload(), ensure_ascii=True))
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runless BuddySwitch runtime entrypoints.")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Show runless runtime status and env tool catalog.")
    status.set_defaults(func=_cmd_status)

    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        return args.func(args)
    except RuntimeFeedbackError as exc:
        payload: dict[str, Any] = {
            "ok": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retriable": False,
            },
        }
        if exc.details:
            payload.update(exc.details)
        print(json.dumps(payload, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
