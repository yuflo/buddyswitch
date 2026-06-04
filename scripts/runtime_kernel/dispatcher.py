#!/usr/bin/env python3
"""Runtime broker request dispatcher for runless env.tool flows."""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from env.repos import runtime_files
from env.tool_runtime import results as tool_results
from env.tool_runtime.registry import dispatch_env_tool_request
from env_manifest import ManifestError, load_manifest


@dataclass(frozen=True)
class RuntimeBrokerSession:
    instance_json_path: Path
    manifest_path: Path
    repo_root_path: Path | None = None
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
            tool_results.next_action_option(
                tool="context",
                action="summarize",
                option_id="summarize_current_context_before_retry",
                reason="Summarize current context before retrying runtime operations.",
            ),
            tool_results.next_action_option(
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
    actor_id = payload.get("actor_id")
    role = payload.get("role")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ValueError(f"instance record missing actor_id: {instance_json_path}")
    if not isinstance(role, str) or not role.strip():
        raise ValueError(f"instance record missing role: {instance_json_path}")
    return payload


def _instance_shared_root(instance_json_path: Path) -> Path:
    instance_root = instance_json_path.parent
    if instance_root.parent.name == "instances":
        return instance_root.parent.parent
    return instance_root


def _runtime_source_repo_root(*, manifest_path: Path, repo_root_path: Path | None) -> Path:
    if repo_root_path is not None:
        return repo_root_path.expanduser().resolve(strict=False)
    return manifest_path.expanduser().resolve(strict=False).parents[1]


@contextlib.contextmanager
def _runtime_server_env(
    *,
    actor_id: str,
    role_id: str,
    instance_json_path: Path,
    instance_record: dict[str, Any],
    manifest_path: Path,
    repo_root_path: Path | None,
) -> Iterator[None]:
    shared_root = _instance_shared_root(instance_json_path)
    repo_root = _runtime_source_repo_root(manifest_path=manifest_path, repo_root_path=repo_root_path)
    updates = {
        "BUDDYSWITCH_RUNTIME_BROKER_MODE": "server",
        "BUDDYSWITCH_ACTOR_ID": actor_id,
        "BUDDYSWITCH_ROLE_ID": role_id,
        "BUDDYSWITCH_INSTANCE_JSON": str(instance_json_path),
        "BUDDYSWITCH_REPO_ROOT": str(repo_root),
        "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
        "BUDDYSWITCH_STATE_ROOT": str(shared_root / "state"),
    }
    instance_root = instance_record.get("instance_root")
    if isinstance(instance_root, str) and instance_root.strip():
        resolved_instance_root = Path(instance_root.strip()).expanduser().resolve(strict=False)
    else:
        resolved_instance_root = instance_json_path.parent.resolve(strict=False)
    updates["BUDDYSWITCH_INSTANCE_ROOT"] = str(resolved_instance_root)
    updates["BUDDYSWITCH_INSTANCE_TMP"] = str(resolved_instance_root / "tmp")
    workspace_dir = instance_record.get("workspace_dir")
    if isinstance(workspace_dir, str) and workspace_dir.strip():
        updates["BUDDYSWITCH_WORKSPACE_DIR"] = str(
            Path(workspace_dir.strip()).expanduser().resolve(strict=False)
        )
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    runtime_files.refresh_runtime_roots_from_env()
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        runtime_files.refresh_runtime_roots_from_env()


def _env_tool_dispatch(
    *,
    params: dict[str, Any],
    manifest_path: Path,
    instance_json_path: Path,
    instance_record: dict[str, Any],
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    actor_id = str(instance_record["actor_id"]).strip()
    active_role = str(instance_record["role"]).strip()
    payload = dict(params)
    return dispatch_env_tool_request(
        payload=payload,
        active_role=active_role,
        actor_id=actor_id,
        instance_json=instance_json_path,
        instance_payload=dict(instance_record),
        manifest=manifest,
        manifest_path=manifest_path,
    )


def _ping_dispatch(*, session: RuntimeBrokerSession, instance_record: dict[str, Any]) -> dict[str, Any]:
    actor_id = str(instance_record["actor_id"]).strip()
    active_role = str(instance_record["role"]).strip()
    runtime_workspace_root = runtime_files.runtime_workspace_root(instance_record).resolve(strict=False)
    runtime_state_root = runtime_files.STATE_ROOT.resolve(strict=False)
    return {
        "ok": True,
        "protocol": "buddyswitch-runtime-broker/v2",
        "actor_id": actor_id,
        "active_role": active_role,
        "pid": os.getpid(),
        "socket_path": str(session.socket_path) if session.socket_path is not None else None,
        "runtime_root": str(runtime_workspace_root),
        "runtime_workspace_root": str(runtime_workspace_root),
        "runtime_state_root": str(runtime_state_root),
        "cwd": str(runtime_workspace_root),
        "env_store_root": str(runtime_state_root),
        "runtime_workspace": runtime_files.is_runtime_workspace(runtime_workspace_root),
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
        actor_id = str(instance_record["actor_id"]).strip()
        active_role = str(instance_record["role"]).strip()

        request_actor_id = params.get("actor_id")
        request_role = params.get("active_role")

        if request_actor_id is not None and request_actor_id != actor_id:
            return _boundary_error(
                "E_RUNTIME_BROKER_PERMISSION",
                f"actor_id mismatch: expected '{actor_id}', got '{request_actor_id}'",
                boundary="active-instance",
                actions=_allowed("Use the active launcher-managed actor id."),
            )
        if request_role is not None and request_role != active_role:
            return _boundary_error(
                "E_RUNTIME_BROKER_PERMISSION",
                f"active_role mismatch: expected '{active_role}', got '{request_role}'",
                boundary="active-role",
                actions=_allowed("Use the active role locked by the launcher."),
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
            actor_id=actor_id,
            role_id=active_role,
            instance_json_path=session.instance_json_path,
            instance_record=instance_record,
            manifest_path=session.manifest_path,
            repo_root_path=session.repo_root_path,
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
