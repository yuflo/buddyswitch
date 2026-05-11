#!/usr/bin/env python3
"""Launcher instance binding service for broker-routed env.tool operations."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypedDict

import env_store

_IDENTITY_FIELDS = {"active_buddy", "buddy", "instance_id"}
_SET_TASK_FIELDS = {"task_id"} | _IDENTITY_FIELDS
_SET_TRACK_FIELDS = {"track_id"} | _IDENTITY_FIELDS


class BindingServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _write_runtime_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=True, indent=2) + os.linesep
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        handle.write(serialized)
        temp_name = handle.name
    os.replace(temp_name, path)


def _normalize_optional_id(value: Any, *, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return env_store.require_id(value.strip(), label)


def _error_payload(
    *,
    action: str,
    active_buddy: str,
    code: str,
    message: str,
    permission_boundary: str,
    allowed_next_actions: list[str],
    task_id: str | None = None,
    track_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "tool": "binding",
        "action": action,
        "error": {
            "code": code,
            "message": message,
        },
        "permission_boundary": permission_boundary,
        "active_buddy": active_buddy,
        "allowed_next_actions": allowed_next_actions,
    }
    if isinstance(task_id, str) and task_id.strip():
        payload["task_id"] = task_id.strip()
    if isinstance(track_id, str) and track_id.strip():
        payload["track_id"] = track_id.strip()
    return payload


def _payload_error(
    *,
    action: str,
    active_buddy: str,
    message: str,
    task_id: str | None = None,
    track_id: str | None = None,
) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_BINDING_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        task_id=task_id,
        track_id=track_id,
        allowed_next_actions=[
            'Fix the env.tool envelope fields (`tool`, `action`, `args`) and retry.',
            "Use binding.get to inspect the active instance binding before retrying.",
        ],
    )


def _task_lookup_error(*, action: str, active_buddy: str, task_id: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TASK_NOT_FOUND",
        message=f"task not found: {task_id}",
        permission_boundary="task.lookup",
        task_id=task_id,
        allowed_next_actions=[
            "Use task.list to inspect active-buddy task ids.",
            "Create the active-buddy task before binding it.",
        ],
    )


def _task_scope_error(*, action: str, active_buddy: str, task_id: str, task_buddy: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TASK_BUDDY_SCOPE",
        message=f"task belongs to buddy '{task_buddy}', not active buddy '{active_buddy}'",
        permission_boundary="task.buddy_scope",
        task_id=task_id,
        allowed_next_actions=[
            "Choose a task owned by the active buddy.",
            "Use handoff or track context instead of cross-buddy task mutation.",
        ],
    )


def _track_lookup_error(*, action: str, active_buddy: str, track_id: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TRACK_NOT_FOUND",
        message=f"track not found: {track_id}",
        permission_boundary="track.lookup",
        track_id=track_id,
        allowed_next_actions=[
            "Use track.list to inspect available track ids.",
            "Ask PM to create the track before binding it.",
        ],
    )


def _track_authority_error(*, action: str, active_buddy: str, track_id: str | None = None) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TRACK_LIFECYCLE_AUTHORITY",
        message=f"active buddy '{active_buddy}' cannot bind an arbitrary track",
        permission_boundary="track.lifecycle_authority",
        track_id=track_id,
        allowed_next_actions=[
            "Use PM to bind a standalone track.",
            "Bind an active-buddy-owned task when a non-PM buddy needs derived track context.",
        ],
    )


def _ensure_allowed_fields(
    *,
    action: str,
    active_buddy: str,
    args: dict[str, Any],
    allowed_fields: set[str],
) -> dict[str, Any] | None:
    unknown = sorted(key for key in args.keys() if key not in allowed_fields)
    if not unknown:
        return None
    return _payload_error(
        action=action,
        active_buddy=active_buddy,
        message=f"unsupported payload fields: {', '.join(unknown)}",
    )


def current_binding(context: BindingServiceContext) -> dict[str, Any]:
    payload = context["instance_payload"]
    return {
        "instance_id": context["instance_id"],
        "active_buddy": context["active_buddy"],
        "current_task_id": payload.get("current_task_id"),
        "current_track_id": payload.get("current_track_id"),
    }


def write_instance_binding(
    *,
    context: BindingServiceContext,
    task_id: str | None,
    track_id: str | None,
) -> dict[str, Any]:
    normalized_task_id = _normalize_optional_id(task_id, label="task id")
    normalized_track_id = _normalize_optional_id(track_id, label="track id")
    updated = dict(context["instance_payload"])
    updated["current_task_id"] = normalized_task_id
    updated["current_track_id"] = normalized_track_id
    updated["updated_at"] = env_store.now_iso()
    _write_runtime_json(context["instance_json"], updated)
    context["instance_payload"] = updated
    return current_binding(context)


def write_product_session_binding(
    product_session: dict[str, Any],
    *,
    task_id: str | None,
    track_id: str | None,
) -> None:
    instance_json = product_session.get("instance_json")
    payload = product_session.get("payload")
    if not isinstance(instance_json, Path):
        raise ValueError("product session instance_json is required")
    if not isinstance(payload, dict):
        raise ValueError("product session payload is required")
    context: BindingServiceContext = {
        "active_buddy": str(product_session.get("active_buddy") or payload.get("buddy") or ""),
        "instance_id": str(product_session.get("instance_id") or payload.get("instance_id") or ""),
        "instance_json": instance_json,
        "instance_payload": payload,
        "manifest": {},
    }
    write_instance_binding(context=context, task_id=task_id, track_id=track_id)
    product_session["payload"] = context["instance_payload"]


def resolve_binding_from_payload(payload: dict[str, Any]) -> tuple[str, str | None]:
    task_id = payload.get("current_task_id")
    track_id = payload.get("current_track_id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("prepare payload current_task_id is required for product session binding")
    env_store.require_id(task_id.strip(), "task id")
    if not isinstance(track_id, str) or not track_id.strip():
        track_id = None
    else:
        track_id = env_store.require_id(track_id.strip(), "track id")
    return task_id.strip(), track_id


def _receipt_has_binding_update_warning(receipt: dict[str, Any]) -> bool:
    warnings = receipt.get("warnings")
    if not isinstance(warnings, list):
        return False
    return any(
        isinstance(item, dict) and item.get("code") == "W_INSTANCE_BINDING_UPDATE_FAILED"
        for item in warnings
    )


def persist_binding_from_payload(payload: dict[str, Any]) -> tuple[str, str | None] | None:
    refreshed_context = payload.get("refreshed_context")
    if isinstance(refreshed_context, dict) and refreshed_context.get("ok") is True:
        return resolve_binding_from_payload(refreshed_context)

    receipt = payload.get("receipt")
    if not isinstance(receipt, dict):
        return None
    refreshed_error = refreshed_context.get("error") if isinstance(refreshed_context, dict) else None
    if (
        isinstance(refreshed_error, dict)
        and refreshed_error.get("code") == "E_RUNTIME_REFRESH_CONTEXT"
        and not _receipt_has_binding_update_warning(receipt)
    ):
        next_state = receipt.get("next_state")
        if isinstance(next_state, dict):
            task_id = next_state.get("task_id")
            track_id = next_state.get("track_id")
        else:
            task_id = receipt.get("task_id")
            track_id = receipt.get("track_id")
        if not isinstance(task_id, str) or not task_id.strip():
            return None
        env_store.require_id(task_id.strip(), "task id")
        if not isinstance(track_id, str) or not track_id.strip():
            track_id = None
        else:
            track_id = env_store.require_id(track_id.strip(), "track id")
        return task_id.strip(), track_id
    return None


def get_binding(*, args: dict[str, Any], context: BindingServiceContext) -> dict[str, Any]:
    action = "binding.get"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_IDENTITY_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    return {
        "ok": True,
        "tool": "binding",
        "action": action,
        "active_buddy": context["active_buddy"],
        "current_binding": current_binding(context),
        "allowed_next_actions": [
            "Use binding.set_task to bind an active-buddy-owned task.",
            "Use context.get to inspect the current binding context.",
        ],
    }


def set_task_binding(*, args: dict[str, Any], context: BindingServiceContext) -> dict[str, Any]:
    action = "binding.set_task"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_SET_TASK_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    raw_task_id = args.get("task_id")
    if not isinstance(raw_task_id, str) or not raw_task_id.strip():
        return _payload_error(action=action, active_buddy=context["active_buddy"], message="task_id is required")
    try:
        task_id = env_store.require_id(raw_task_id.strip(), "task id")
    except ValueError as exc:
        return _payload_error(action=action, active_buddy=context["active_buddy"], message=str(exc))

    task = env_store.get_task(task_id)
    if task is None:
        return _task_lookup_error(action=action, active_buddy=context["active_buddy"], task_id=task_id)
    task_buddy = task.get("buddy")
    if task_buddy != context["active_buddy"]:
        return _task_scope_error(
            action=action,
            active_buddy=context["active_buddy"],
            task_id=task_id,
            task_buddy=str(task_buddy or ""),
        )

    track_id = task.get("track_id")
    normalized_track_id = track_id if isinstance(track_id, str) and track_id.strip() else None
    binding = write_instance_binding(context=context, task_id=task_id, track_id=normalized_track_id)
    return {
        "ok": True,
        "tool": "binding",
        "action": action,
        "active_buddy": context["active_buddy"],
        "task_id": task_id,
        "track_id": normalized_track_id,
        "current_binding": binding,
        "allowed_next_actions": [
            "Use binding.get to confirm active instance binding.",
            "Use context.get to inspect refreshed task and track context.",
        ],
    }


def set_track_binding(*, args: dict[str, Any], context: BindingServiceContext) -> dict[str, Any]:
    action = "binding.set_track"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_SET_TRACK_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    raw_track_id = args.get("track_id")
    if not isinstance(raw_track_id, str) or not raw_track_id.strip():
        return _payload_error(action=action, active_buddy=context["active_buddy"], message="track_id is required")
    try:
        track_id = env_store.require_id(raw_track_id.strip(), "track id")
    except ValueError as exc:
        return _payload_error(action=action, active_buddy=context["active_buddy"], message=str(exc))

    track = env_store.get_track(track_id)
    if track is None:
        return _track_lookup_error(action=action, active_buddy=context["active_buddy"], track_id=track_id)
    if context["active_buddy"] != "pm":
        return _track_authority_error(action=action, active_buddy=context["active_buddy"], track_id=track_id)

    binding = write_instance_binding(context=context, task_id=None, track_id=track_id)
    return {
        "ok": True,
        "tool": "binding",
        "action": action,
        "active_buddy": context["active_buddy"],
        "track_id": track_id,
        "current_binding": binding,
        "allowed_next_actions": [
            "Use binding.get to confirm active instance binding.",
            "Use context.get to inspect refreshed track context.",
        ],
    }


def clear_binding(*, args: dict[str, Any], context: BindingServiceContext) -> dict[str, Any]:
    action = "binding.clear"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_IDENTITY_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    binding = write_instance_binding(context=context, task_id=None, track_id=None)
    return {
        "ok": True,
        "tool": "binding",
        "action": action,
        "active_buddy": context["active_buddy"],
        "current_binding": binding,
        "allowed_next_actions": [
            "Use task.list to inspect active-buddy tasks.",
            "Use binding.set_task to bind the next task.",
        ],
    }
