#!/usr/bin/env python3
"""Track manager service for broker-routed env.tool operations."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, TypedDict

import env_store
from env_manifest import buddy_permissions, get_buddy

_TRACK_PUBLIC_FIELDS = (
    "id",
    "title",
    "summary",
    "status",
    "current_buddy",
    "next_buddy",
    "task_ids",
    "updated_at",
)
_TASK_PUBLIC_FIELDS = (
    "id",
    "buddy",
    "title",
    "summary",
    "status",
    "track_id",
    "latest_run_id",
    "updated_at",
)
_TRACK_STATUSES = set(env_store.VALID_TRACK_STATUS)
_READ_PERMISSION = "track.read"
_CREATE_PERMISSION = "track.create"
_UPDATE_PERMISSION = "track.update"
_ADVANCE_PERMISSION = "track.advance"
_ARCHIVE_PERMISSION = "track.archive"
_TASK_UPDATE_PERMISSION = "task.update"
_IDENTITY_FIELDS = {"active_buddy", "buddy", "instance_id"}
_TRACK_ID_FIELDS = {"track_id"}
_LINK_FIELDS = {"track_id", "task_id"} | _IDENTITY_FIELDS
_CREATE_FIELDS = {"track_id", "title", "status", "current_buddy", "next_buddy", "summary"} | _IDENTITY_FIELDS
_UPDATE_FIELDS = {"track_id", "title", "status", "current_buddy", "next_buddy", "summary"} | _IDENTITY_FIELDS
_ADVANCE_FIELDS = {"track_id", "status", "current_buddy", "next_buddy", "summary"} | _IDENTITY_FIELDS


class TrackServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _error_payload(
    *,
    action: str,
    active_buddy: str,
    code: str,
    message: str,
    permission_boundary: str,
    allowed_next_actions: list[str],
    track_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "tool": "track",
        "action": action,
        "error": {
            "code": code,
            "message": message,
        },
        "permission_boundary": permission_boundary,
        "active_buddy": active_buddy,
        "allowed_next_actions": allowed_next_actions,
    }
    if isinstance(track_id, str) and track_id.strip():
        payload["track_id"] = track_id.strip()
    if isinstance(task_id, str) and task_id.strip():
        payload["task_id"] = task_id.strip()
    return payload


def _permission_error(*, action: str, active_buddy: str, permission: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TRACK_PERMISSION",
        message=f"active buddy '{active_buddy}' is missing required permission '{permission}'",
        permission_boundary="manifest.permission",
        allowed_next_actions=[
            "Use only track actions allowed by the active buddy manifest permissions.",
            "Switch to a buddy that owns this track action before retrying.",
        ],
    )


def _lifecycle_authority_error(*, action: str, active_buddy: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TRACK_LIFECYCLE_AUTHORITY",
        message=f"active buddy '{active_buddy}' cannot mutate track lifecycle state",
        permission_boundary="track.lifecycle_authority",
        allowed_next_actions=[
            "Use PM for track lifecycle mutations.",
            "Non-PM buddies may read track context or attach their own task work to an existing track.",
        ],
    )


def _payload_error(
    *,
    action: str,
    active_buddy: str,
    message: str,
    track_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TRACK_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        track_id=track_id,
        task_id=task_id,
        allowed_next_actions=[
            'Fix the env.tool envelope fields (`tool`, `action`, `args`) and retry.',
            "Use track.list to inspect candidate track ids before retrying.",
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
            "Ask PM to create a track when no existing track matches.",
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
            "Create the task before linking it to a track.",
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


def _linkage_error(
    *,
    action: str,
    active_buddy: str,
    track_id: str,
    task_id: str,
    message: str,
) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TRACK_TASK_LINKAGE",
        message=message,
        permission_boundary="track.task_linkage",
        track_id=track_id,
        task_id=task_id,
        allowed_next_actions=[
            "Inspect the task and track before retrying.",
            "Detach the task from its current track before attaching it elsewhere.",
        ],
    )


def _require_permission(context: TrackServiceContext, permission: str, action: str) -> dict[str, Any] | None:
    permissions = buddy_permissions(context["manifest"], context["active_buddy"])
    if permission in permissions:
        return None
    return _permission_error(action=action, active_buddy=context["active_buddy"], permission=permission)


def _require_lifecycle_authority(
    context: TrackServiceContext,
    *,
    permission: str,
    action: str,
) -> dict[str, Any] | None:
    if context["active_buddy"] != "pm":
        return _lifecycle_authority_error(action=action, active_buddy=context["active_buddy"])
    return _require_permission(context, permission, action)


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


def _normalize_id(value: Any, *, label: str) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, None
    candidate = value.strip()
    try:
        env_store.require_id(candidate, label)
    except ValueError as exc:
        return None, str(exc)
    return candidate, None


def _required_track_id(
    *,
    action: str,
    active_buddy: str,
    args: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    track_id, parse_error = _normalize_id(args.get("track_id"), label="track id")
    if parse_error is not None:
        return None, _payload_error(action=action, active_buddy=active_buddy, message=parse_error)
    if track_id is None:
        return None, _payload_error(action=action, active_buddy=active_buddy, message="track_id is required")
    return track_id, None


def _required_task_id(
    *,
    action: str,
    active_buddy: str,
    args: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    task_id, parse_error = _normalize_id(args.get("task_id"), label="task id")
    if parse_error is not None:
        return None, _payload_error(action=action, active_buddy=active_buddy, message=parse_error)
    if task_id is None:
        return None, _payload_error(action=action, active_buddy=active_buddy, message="task_id is required")
    return task_id, None


def _track_summary(track: dict[str, Any]) -> dict[str, Any]:
    return {field: track.get(field) for field in _TRACK_PUBLIC_FIELDS}


def _task_summary(task: dict[str, Any]) -> dict[str, Any]:
    return {field: task.get(field) for field in _TASK_PUBLIC_FIELDS}


def _current_binding(context: TrackServiceContext) -> dict[str, Any]:
    payload = context["instance_payload"]
    return {
        "instance_id": context["instance_id"],
        "current_task_id": payload.get("current_task_id"),
        "current_track_id": payload.get("current_track_id"),
    }


def _validate_buddy_ref(
    *,
    context: TrackServiceContext,
    action: str,
    field: str,
    value: Any,
    required: bool,
    track_id: str | None = None,
) -> tuple[str | None, dict[str, Any] | None]:
    if value is None:
        if required:
            return None, _payload_error(
                action=action,
                active_buddy=context["active_buddy"],
                message=f"{field} is required",
                track_id=track_id,
            )
        return None, None
    if not isinstance(value, str) or not value.strip():
        return None, _payload_error(
            action=action,
            active_buddy=context["active_buddy"],
            message=f"{field} must be a non-empty string or null",
            track_id=track_id,
        )
    buddy_id = value.strip()
    if get_buddy(context["manifest"], buddy_id) is None:
        return None, _payload_error(
            action=action,
            active_buddy=context["active_buddy"],
            message=f"{field} must reference a known buddy",
            track_id=track_id,
        )
    return buddy_id, None


def _validate_status(
    *,
    action: str,
    active_buddy: str,
    value: Any,
    track_id: str | None = None,
) -> tuple[str | None, dict[str, Any] | None]:
    if not isinstance(value, str) or value not in _TRACK_STATUSES:
        return None, _payload_error(
            action=action,
            active_buddy=active_buddy,
            message=f"status must be one of {', '.join(sorted(_TRACK_STATUSES))}",
            track_id=track_id,
        )
    return value, None


def _get_track(
    *,
    context: TrackServiceContext,
    action: str,
    args: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    track_id, error = _required_track_id(action=action, active_buddy=context["active_buddy"], args=args)
    if error is not None:
        return None, error
    assert track_id is not None
    track = env_store.get_track(track_id)
    if track is None:
        return None, _track_lookup_error(action=action, active_buddy=context["active_buddy"], track_id=track_id)
    return track, None


def _get_owned_task(
    *,
    context: TrackServiceContext,
    action: str,
    args: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    task_id, error = _required_task_id(action=action, active_buddy=context["active_buddy"], args=args)
    if error is not None:
        return None, error
    assert task_id is not None
    task = env_store.get_task(task_id)
    if task is None:
        return None, _task_lookup_error(action=action, active_buddy=context["active_buddy"], task_id=task_id)
    task_buddy = task.get("buddy")
    if not isinstance(task_buddy, str) or task_buddy != context["active_buddy"]:
        return None, _task_scope_error(
            action=action,
            active_buddy=context["active_buddy"],
            task_id=task_id,
            task_buddy=str(task_buddy or ""),
        )
    return task, None


def _next_track_id(title: str) -> str:
    seed = env_store.slugify(title)
    while True:
        candidate = f"track-{seed}-{uuid.uuid4().hex[:8]}"
        if env_store.get_track(candidate) is None:
            return candidate


def _success_payload(
    *,
    action: str,
    context: TrackServiceContext,
    track: dict[str, Any] | None = None,
    task: dict[str, Any] | None = None,
    tracks: list[dict[str, Any]] | None = None,
    allowed_next_actions: list[str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "tool": "track",
        "action": action,
        "active_buddy": context["active_buddy"],
        "current_binding": _current_binding(context),
        "allowed_next_actions": allowed_next_actions,
    }
    if track is not None:
        payload["track_id"] = track["id"]
        payload["track"] = _track_summary(track)
    if task is not None:
        payload["task_id"] = task["id"]
        payload["task"] = _task_summary(task)
    if tracks is not None:
        payload["tracks"] = tracks
    return payload


def list_tracks_for_active_buddy(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.list"
    permission_error = _require_permission(context, _READ_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    if args:
        fields_error = _ensure_allowed_fields(
            action=action,
            active_buddy=context["active_buddy"],
            args=args,
            allowed_fields=_IDENTITY_FIELDS,
        )
        if fields_error is not None:
            return fields_error
    return _success_payload(
        action=action,
        context=context,
        tracks=[_track_summary(track) for track in env_store.list_tracks()],
        allowed_next_actions=[
            "Use track.get with a returned track_id to inspect one track.",
            "Ask PM to create or advance lifecycle state when needed.",
        ],
    )


def get_track_for_active_buddy(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.get"
    permission_error = _require_permission(context, _READ_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_TRACK_ID_FIELDS | _IDENTITY_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    track, error = _get_track(context=context, action=action, args=args)
    if error is not None:
        return error
    assert track is not None
    return _success_payload(
        action=action,
        context=context,
        track=track,
        allowed_next_actions=[
            "Use track.attach_task to link active-buddy task work to this track.",
            "Ask PM to update or advance track lifecycle state.",
        ],
    )


def get_current_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.get_current"
    permission_error = _require_permission(context, _READ_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    if args:
        fields_error = _ensure_allowed_fields(
            action=action,
            active_buddy=context["active_buddy"],
            args=args,
            allowed_fields=_IDENTITY_FIELDS,
        )
        if fields_error is not None:
            return fields_error
    binding = _current_binding(context)
    track_id = binding.get("current_track_id")
    if not isinstance(track_id, str) or not track_id.strip():
        return {
            "ok": True,
            "tool": "track",
            "action": action,
            "active_buddy": context["active_buddy"],
            "track": None,
            "current_binding": binding,
            "allowed_next_actions": [
                "Use track.list to inspect available tracks.",
                "Set a current task that is linked to a track when track binding is needed.",
            ],
        }
    track = env_store.get_track(track_id.strip())
    if track is None:
        return _track_lookup_error(action=action, active_buddy=context["active_buddy"], track_id=track_id.strip())
    return _success_payload(
        action=action,
        context=context,
        track=track,
        allowed_next_actions=[
            "Use track.get to refresh this track context.",
            "Continue work using the current track binding.",
        ],
    )


def create_track_for_pm(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.create"
    authority_error = _require_lifecycle_authority(context, permission=_CREATE_PERMISSION, action=action)
    if authority_error is not None:
        return authority_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_CREATE_FIELDS,
    )
    if fields_error is not None:
        return fields_error

    title = args.get("title")
    if not isinstance(title, str) or not title.strip():
        return _payload_error(action=action, active_buddy=context["active_buddy"], message="title is required")
    clean_title = title.strip()
    summary = args.get("summary", "")
    if summary is None:
        summary = ""
    if not isinstance(summary, str):
        return _payload_error(action=action, active_buddy=context["active_buddy"], message="summary must be a string")
    status = args.get("status", "active")
    normalized_status, status_error = _validate_status(
        action=action,
        active_buddy=context["active_buddy"],
        value=status,
    )
    if status_error is not None:
        return status_error

    current_buddy, current_error = _validate_buddy_ref(
        context=context,
        action=action,
        field="current_buddy",
        value=args.get("current_buddy", "pm"),
        required=True,
    )
    if current_error is not None:
        return current_error
    next_buddy, next_error = _validate_buddy_ref(
        context=context,
        action=action,
        field="next_buddy",
        value=args.get("next_buddy"),
        required=False,
    )
    if next_error is not None:
        return next_error

    explicit_track_id = args.get("track_id")
    if explicit_track_id is None:
        track_id = _next_track_id(clean_title)
    else:
        track_id, parse_error = _normalize_id(explicit_track_id, label="track id")
        if parse_error is not None:
            return _payload_error(action=action, active_buddy=context["active_buddy"], message=parse_error)
        if track_id is None:
            return _payload_error(
                action=action,
                active_buddy=context["active_buddy"],
                message="track_id must be a non-empty string when provided",
            )
        if env_store.get_track(track_id) is not None:
            return _payload_error(
                action=action,
                active_buddy=context["active_buddy"],
                message=f"track already exists: {track_id}",
                track_id=track_id,
            )

    assert isinstance(normalized_status, str)
    assert isinstance(current_buddy, str)
    track = env_store.create_track(
        track_id,
        clean_title,
        status=normalized_status,
        current_buddy=current_buddy,
        next_buddy=next_buddy,
        summary=summary,
    )
    return _success_payload(
        action=action,
        context=context,
        track=track,
        allowed_next_actions=[
            "Use track.update to adjust metadata.",
            "Use track.advance when another buddy should own the next lifecycle step.",
        ],
    )


def _track_patch_from_args(
    *,
    context: TrackServiceContext,
    action: str,
    track_id: str,
    args: dict[str, Any],
    allowed_patch_fields: set[str],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    patch: dict[str, Any] = {}
    if "title" in allowed_patch_fields and "title" in args:
        title = args.get("title")
        if not isinstance(title, str) or not title.strip():
            return None, _payload_error(
                action=action,
                active_buddy=context["active_buddy"],
                message="title must be a non-empty string when provided",
                track_id=track_id,
            )
        patch["title"] = title.strip()
    if "summary" in allowed_patch_fields and "summary" in args:
        summary = args.get("summary")
        if summary is None:
            summary = ""
        if not isinstance(summary, str):
            return None, _payload_error(
                action=action,
                active_buddy=context["active_buddy"],
                message="summary must be a string when provided",
                track_id=track_id,
            )
        patch["summary"] = summary
    if "status" in allowed_patch_fields and "status" in args:
        status, status_error = _validate_status(
            action=action,
            active_buddy=context["active_buddy"],
            value=args.get("status"),
            track_id=track_id,
        )
        if status_error is not None:
            return None, status_error
        patch["status"] = status
    if "current_buddy" in allowed_patch_fields and "current_buddy" in args:
        current_buddy, current_error = _validate_buddy_ref(
            context=context,
            action=action,
            field="current_buddy",
            value=args.get("current_buddy"),
            required=True,
            track_id=track_id,
        )
        if current_error is not None:
            return None, current_error
        patch["current_buddy"] = current_buddy
    if "next_buddy" in allowed_patch_fields and "next_buddy" in args:
        next_buddy, next_error = _validate_buddy_ref(
            context=context,
            action=action,
            field="next_buddy",
            value=args.get("next_buddy"),
            required=False,
            track_id=track_id,
        )
        if next_error is not None:
            return None, next_error
        patch["next_buddy"] = next_buddy
    if not patch:
        return None, _payload_error(
            action=action,
            active_buddy=context["active_buddy"],
            message=f"{action.split('.', 1)[1]} requires at least one field to change",
            track_id=track_id,
        )
    return patch, None


def update_track_for_pm(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.update"
    authority_error = _require_lifecycle_authority(context, permission=_UPDATE_PERMISSION, action=action)
    if authority_error is not None:
        return authority_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_UPDATE_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    track, error = _get_track(context=context, action=action, args=args)
    if error is not None:
        return error
    assert track is not None
    patch, patch_error = _track_patch_from_args(
        context=context,
        action=action,
        track_id=track["id"],
        args=args,
        allowed_patch_fields={"title", "status", "current_buddy", "next_buddy", "summary"},
    )
    if patch_error is not None:
        return patch_error
    assert patch is not None
    updated = env_store.update_track(track["id"], patch)
    return _success_payload(
        action=action,
        context=context,
        track=updated,
        allowed_next_actions=[
            "Use track.get to confirm the persisted track fields.",
            "Use track.advance when lifecycle ownership should move.",
        ],
    )


def advance_track_for_pm(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.advance"
    authority_error = _require_lifecycle_authority(context, permission=_ADVANCE_PERMISSION, action=action)
    if authority_error is not None:
        return authority_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_ADVANCE_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    track, error = _get_track(context=context, action=action, args=args)
    if error is not None:
        return error
    assert track is not None
    patch, patch_error = _track_patch_from_args(
        context=context,
        action=action,
        track_id=track["id"],
        args=args,
        allowed_patch_fields={"status", "current_buddy", "next_buddy", "summary"},
    )
    if patch_error is not None:
        return patch_error
    assert patch is not None
    updated = env_store.update_track(track["id"], patch)
    return _success_payload(
        action=action,
        context=context,
        track=updated,
        allowed_next_actions=[
            "Use track.get to confirm the lifecycle change.",
            "Use handoff when another buddy should continue work.",
        ],
    )


def archive_track_for_pm(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.archive"
    authority_error = _require_lifecycle_authority(context, permission=_ARCHIVE_PERMISSION, action=action)
    if authority_error is not None:
        return authority_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_TRACK_ID_FIELDS | _IDENTITY_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    track, error = _get_track(context=context, action=action, args=args)
    if error is not None:
        return error
    assert track is not None
    archived = env_store.update_track(track["id"], {"status": "archived"})
    return _success_payload(
        action=action,
        context=context,
        track=archived,
        allowed_next_actions=[
            "Use track.list to continue with another track.",
            "Create a new track when a fresh coordination thread is needed.",
        ],
    )


def attach_task_to_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.attach_task"
    permission_error = _require_permission(context, _READ_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    permission_error = _require_permission(context, _TASK_UPDATE_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_LINK_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    track, error = _get_track(context=context, action=action, args=args)
    if error is not None:
        return error
    task, error = _get_owned_task(context=context, action=action, args=args)
    if error is not None:
        return error
    assert track is not None
    assert task is not None
    current_track_id = task.get("track_id")
    if isinstance(current_track_id, str) and current_track_id and current_track_id != track["id"]:
        return _linkage_error(
            action=action,
            active_buddy=context["active_buddy"],
            track_id=track["id"],
            task_id=task["id"],
            message=f"task is already bound to track '{current_track_id}'",
        )
    linked_task = env_store.register_task_to_track(track["id"], task["id"])
    linked_track = env_store.get_track(track["id"])
    assert linked_track is not None
    return _success_payload(
        action=action,
        context=context,
        track=linked_track,
        task=linked_task,
        allowed_next_actions=[
            "Use task.set_current to bind the active instance to this tracked task.",
            "Use track.detach_task when this task should leave the track.",
        ],
    )


def detach_task_from_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.detach_task"
    permission_error = _require_permission(context, _READ_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    permission_error = _require_permission(context, _TASK_UPDATE_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_LINK_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    track, error = _get_track(context=context, action=action, args=args)
    if error is not None:
        return error
    task, error = _get_owned_task(context=context, action=action, args=args)
    if error is not None:
        return error
    assert track is not None
    assert task is not None
    current_track_id = task.get("track_id")
    if isinstance(current_track_id, str) and current_track_id and current_track_id != track["id"]:
        return _linkage_error(
            action=action,
            active_buddy=context["active_buddy"],
            track_id=track["id"],
            task_id=task["id"],
            message=f"task is bound to track '{current_track_id}', not '{track['id']}'",
        )
    if current_track_id == track["id"]:
        task = env_store.update_task(task["id"], {"track_id": None})
    elif task["id"] in track.get("task_ids", []):
        task_ids = [item for item in track.get("task_ids", []) if item != task["id"]]
        env_store.update_track(track["id"], {"task_ids": task_ids})
    detached_track = env_store.get_track(track["id"])
    assert detached_track is not None
    return _success_payload(
        action=action,
        context=context,
        track=detached_track,
        task=task,
        allowed_next_actions=[
            "Use track.attach_task to relink the task if needed.",
            "Use task.list to continue with active-buddy tasks.",
        ],
    )
