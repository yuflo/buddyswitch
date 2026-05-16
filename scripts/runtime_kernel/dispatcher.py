#!/usr/bin/env python3
"""Runtime broker request dispatcher for runless env.tool flows."""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import env_store
from env.tools import responses as tool_responses
from env.tools.router import dispatch_env_tool_request
from env_manifest import ManifestError, load_manifest


@dataclass(frozen=True)
class RuntimeBrokerSession:
    instance_json_path: Path
    manifest_path: Path
    socket_path: Path | None = None
    pid_file: Path | None = None


def _error(
    code: str,
    message: str,
    *,
    retriable: bool = False,
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
        payload["error"]["retry_after_ms"] = int(retry_after_ms)
    if extra:
        payload.update(extra)
    if "allowed_next_actions" in payload and "allowed_next_action_options" not in payload:
        payload["allowed_next_action_options"] = [
            tool_responses.next_action_option(
                tool="context",
                action="summarize",
                option_id="summarize_current_context_before_retry",
                reason="Summarize current context before retrying runtime operations.",
            ),
            tool_responses.next_action_option(
                tool="context",
                action="get",
                option_id="inspect_context_before_retry",
                reason="Inspect full current context before retrying runtime operations.",
            ),
        ]
    return payload


def _allowed(*actions: str) -> list[str]:
    return list(actions)


def _boundary_error(
    code: str,
    message: str,
    *,
    boundary: str,
    actions: list[str],
    retriable: bool = False,
    retry_after_ms: int | None = None,
) -> dict[str, Any]:
    return _error(
        code,
        message,
        retriable=retriable,
        retry_after_ms=retry_after_ms,
        extra={
            "permission_boundary": boundary,
            "allowed_next_actions": actions,
        },
    )


def _load_instance_record(instance_json_path: Path) -> dict[str, Any]:
    payload = json.loads(instance_json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"instance record must be an object: {instance_json_path}")
    instance_id = payload.get("instance_id")
    buddy = payload.get("buddy")
    if not isinstance(instance_id, str) or not instance_id.strip():
        raise ValueError(f"instance record missing instance_id: {instance_json_path}")
    if not isinstance(buddy, str) or not buddy.strip():
        raise ValueError(f"instance record missing buddy: {instance_json_path}")
    return payload


def _instance_shared_root(instance_json_path: Path) -> Path:
    instance_root = instance_json_path.parent
    if instance_root.parent.name == "instances":
        return instance_root.parent.parent
    return instance_root


@contextlib.contextmanager
def _runtime_server_env(
    *,
    instance_id: str,
    buddy_id: str,
    instance_json_path: Path,
    instance_record: dict[str, Any],
) -> Iterator[None]:
    shared_root = _instance_shared_root(instance_json_path)
    updates = {
        "BUDDYSWITCH_RUNTIME_BROKER_MODE": "server",
        "BUDDYSWITCH_INSTANCE_ID": instance_id,
        "BUDDYSWITCH_ACTIVE_BUDDY": buddy_id,
        "BUDDYSWITCH_INSTANCE_JSON": str(instance_json_path),
        "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
        "BUDDYSWITCH_STATE_ROOT": str(shared_root / "state"),
    }
    workspace_dir = instance_record.get("workspace_dir")
    if isinstance(workspace_dir, str) and workspace_dir.strip():
        updates["BUDDYSWITCH_WORKSPACE_DIR"] = str(
            Path(workspace_dir.strip()).expanduser().resolve(strict=False)
        )
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _env_tool_dispatch(
    *,
    params: dict[str, Any],
    manifest_path: Path,
    instance_json_path: Path,
    instance_record: dict[str, Any],
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    instance_id = str(instance_record["instance_id"]).strip()
    active_buddy = str(instance_record["buddy"]).strip()
    payload = dict(params)
    return dispatch_env_tool_request(
        payload=payload,
        active_buddy=active_buddy,
        instance_id=instance_id,
        instance_json=instance_json_path,
        instance_payload=dict(instance_record),
        manifest=manifest,
        manifest_path=manifest_path,
    )


def _ping_dispatch(*, session: RuntimeBrokerSession, instance_record: dict[str, Any]) -> dict[str, Any]:
    instance_id = str(instance_record["instance_id"]).strip()
    active_buddy = str(instance_record["buddy"]).strip()
    runtime_root = Path.cwd().resolve(strict=False)
    env_store_root = env_store.ROOT.resolve(strict=False)
    return {
        "ok": True,
        "protocol": "buddyswitch-runtime-broker/v2",
        "instance_id": instance_id,
        "active_buddy": active_buddy,
        "pid": os.getpid(),
        "socket_path": str(session.socket_path) if session.socket_path is not None else None,
        "runtime_root": str(runtime_root),
        "cwd": str(runtime_root),
        "env_store_root": str(env_store_root),
        "runtime_workspace": env_store.is_runtime_workspace(env_store.ROOT),
        "runtime_mode": "runless",
    }


def _status_dispatch(*, session: RuntimeBrokerSession, instance_record: dict[str, Any]) -> dict[str, Any]:
    ping = _ping_dispatch(session=session, instance_record=instance_record)
    ping["marker_path"] = None
    ping["healthy"] = True
    if session.pid_file is not None:
        ping["pid_file"] = str(session.pid_file)
    return ping


def dispatch_runtime_request(request: dict[str, Any], session: RuntimeBrokerSession) -> dict[str, Any]:
    try:
        method_raw = request.get("method")
        if not isinstance(method_raw, str) or not method_raw.strip():
            raise ValueError("request.method must be a non-empty string")
        method = method_raw.strip()

        params = request.get("params")
        if not isinstance(params, dict):
            return _boundary_error(
                "E_RUNTIME_BROKER_PERMISSION",
                "request.params must be an object",
                boundary="request-payload",
                actions=_allowed("Send a broker request with an object params."),
            )

        instance_record = _load_instance_record(session.instance_json_path)
        instance_id = str(instance_record["instance_id"]).strip()
        active_buddy = str(instance_record["buddy"]).strip()

        request_instance_id = params.get("instance_id")
        request_buddy = params.get("active_buddy")

        if request_instance_id is not None and request_instance_id != instance_id:
            return _boundary_error(
                "E_RUNTIME_BROKER_PERMISSION",
                f"instance_id mismatch: expected '{instance_id}', got '{request_instance_id}'",
                boundary="active-instance",
                actions=_allowed("Use the active launcher-managed instance id."),
            )
        if request_buddy is not None and request_buddy != active_buddy:
            return _boundary_error(
                "E_RUNTIME_BROKER_PERMISSION",
                f"active_buddy mismatch: expected '{active_buddy}', got '{request_buddy}'",
                boundary="active-buddy",
                actions=_allowed("Use the active buddy locked by the launcher."),
            )

        if method not in {"ping", "status"}:
            status = instance_record.get("status")
            if status != "active":
                return _boundary_error(
                    "E_RUNTIME_BROKER_PERMISSION",
                    f"instance is not active: {status!r}",
                    boundary="active-instance-status",
                    actions=_allowed("Open an active launcher-managed instance before calling runtime tools."),
                )

        with _runtime_server_env(
            instance_id=instance_id,
            buddy_id=active_buddy,
            instance_json_path=session.instance_json_path,
            instance_record=instance_record,
        ):
            if method == "env.tool":
                return _env_tool_dispatch(
                    params=params,
                    manifest_path=session.manifest_path,
                    instance_json_path=session.instance_json_path,
                    instance_record=instance_record,
                )
            if method == "ping":
                return _ping_dispatch(session=session, instance_record=instance_record)
            if method == "status":
                return _status_dispatch(session=session, instance_record=instance_record)

        return _boundary_error(
            "E_RUNTIME_BROKER_PROTOCOL",
            f"unsupported method: {method}",
            boundary="broker-protocol",
            actions=_allowed("Use supported runtime methods: env.tool, ping, status."),
        )
    except (ValueError, OSError, json.JSONDecodeError, ManifestError) as exc:
        return _error("E_RUNTIME_BROKER_PERMISSION", str(exc))
