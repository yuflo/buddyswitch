#!/usr/bin/env python3
"""Track env tool service for broker-routed env.tool operations."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.services import bindings as binding_service
from env.services import context as context_service
from env.services import track_relations
from env_manifest import buddy_permissions, get_buddy
from env.tools import responses as tool_responses

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
_TASK_CREATE_PERMISSION = "task.create"
_TASK_UPDATE_PERMISSION = "task.update"
_IDENTITY_FIELDS = {"active_buddy", "buddy", "instance_id"}
_TRACK_ID_FIELDS = {"track_id"}
_LINK_FIELDS = {"track_id", "task_id"} | _IDENTITY_FIELDS
_JOIN_FIELDS = {"track_id", "task_id"} | _IDENTITY_FIELDS
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
    human_summary: str | None = None,
    why_blocked: str | None = None,
    impact: str = "No track, task, or instance binding state was changed.",
    retryable: bool = True,
    retry_guidance: str | None = None,
    track_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    payload = tool_responses.rejection(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=permission_boundary,
        human_summary=human_summary or message,
        why_blocked=why_blocked or message,
        impact=impact,
        state_changed=False,
        retryable=retryable,
        retry_guidance=retry_guidance or "Fix payload or track/task preconditions, then retry.",
        allowed_next_actions=allowed_next_actions,
    )
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
        human_summary="Active buddy cannot use this track action.",
        why_blocked=f"Missing required permission '{permission}'.",
        retryable=False,
        retry_guidance="Switch to a buddy that owns this permission, or choose an action allowed for the current buddy.",
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
        human_summary="Track lifecycle mutations are PM-only.",
        why_blocked="The active buddy is not the PM lifecycle authority for track state transitions.",
        retryable=False,
        retry_guidance="Use PM for track lifecycle mutations, or continue with non-lifecycle task/artifact collaboration actions.",
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
        human_summary="Track request payload is invalid.",
        why_blocked=message,
        retryable=True,
        retry_guidance="Fix the action payload fields and retry.",
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
        human_summary="Requested track id was not found.",
        why_blocked=f"track_id '{track_id}' does not reference an existing track.",
        retryable=True,
        retry_guidance="List available tracks or ask PM to create one, then retry with a valid track_id.",
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
        human_summary="Requested task id was not found.",
        why_blocked=f"task_id '{task_id}' does not reference an existing task.",
        retryable=True,
        retry_guidance="Use task.list to inspect task ids, then retry with a valid task_id.",
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
        human_summary="Task belongs to another buddy.",
        why_blocked="Only active-buddy owned tasks can be attached, detached, or selected in this action path.",
        retryable=False,
        retry_guidance="Choose a task owned by the active buddy, or use handoff/track collaboration instead of direct mutation.",
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
        human_summary="Task-to-track linkage is invalid for this operation.",
        why_blocked=message,
        retryable=True,
        retry_guidance="Inspect current task/track linkage and retry with a compatible task-track pair.",
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


def _artifact_decision_summary(artifact: dict[str, Any], *, active_buddy: str) -> dict[str, Any]:
    return track_relations.artifact_summary_row(artifact, active_buddy)


def _task_current_artifact_rows(task: dict[str, Any], *, active_buddy: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    artifact_slots = task.get("artifact_slots")
    if not isinstance(artifact_slots, dict):
        return rows
    for kind in sorted(artifact_slots.keys()):
        row = artifact_slots.get(kind)
        if not isinstance(row, dict):
            continue
        artifact_id = row.get("current_artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            continue
        artifact = env_store.get_artifact(artifact_id)
        if not isinstance(artifact, dict):
            continue
        rows.append(_artifact_decision_summary(artifact, active_buddy=active_buddy))
    rows.sort(key=lambda item: (str(item.get("kind") or ""), str(item.get("artifact_id") or "")))
    return rows


def _track_context_summary(track: dict[str, Any], *, active_buddy: str) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    for task_id in sorted(track.get("task_ids", [])):
        if not isinstance(task_id, str) or not task_id:
            continue
        task = env_store.get_task(task_id)
        if not isinstance(task, dict):
            continue
        tasks.append(
            {
                "id": task.get("id"),
                "buddy": task.get("buddy"),
                "status": task.get("status"),
                "summary": task.get("summary", ""),
                "current_artifacts": _task_current_artifact_rows(task, active_buddy=active_buddy),
            }
        )

    recent_handoffs = context_service.scan_track_recent_handoffs(str(track.get("id") or ""), limit=3)
    compact_handoffs: list[dict[str, Any]] = []
    for row in recent_handoffs:
        if not isinstance(row, dict):
            continue
        compact_handoffs.append(
            {
                "run_id": row.get("run_id"),
                "task_id": row.get("task_id"),
                "buddy_id": row.get("buddy_id"),
                "next_buddy": row.get("next_buddy"),
                "reason": row.get("reason"),
                "context": row.get("context"),
                "timestamp": row.get("timestamp"),
            }
        )
    track_id = str(track.get("id") or "")
    return {
        "track_id": track_id,
        "tasks": tasks,
        "current_artifacts": track_relations.current_artifact_rows_for_track(track_id, active_buddy),
        "recent_handoffs": compact_handoffs,
    }


def _latest_handoff_summary_row(track_id: str) -> dict[str, Any] | None:
    rows: list[tuple[str, str, dict[str, Any]]] = []

    for row in env_store.list_handoffs():
        if row.get("track_id") != track_id:
            continue
        if row.get("status") != "active":
            continue
        target_buddy = row.get("target_buddy")
        if not isinstance(target_buddy, str) or not target_buddy.strip():
            continue
        timestamp = str(row.get("updated_at") or row.get("created_at") or "")
        rows.append(
            (
                timestamp,
                f"handoff:{row.get('id')}",
                {
                    "source_type": "handoff_record",
                    "source_buddy": row.get("source_buddy"),
                    "target_buddy": target_buddy.strip(),
                    "source_task_id": row.get("source_task_id"),
                    "source_run_id": row.get("source_run_id"),
                    "reason": row.get("reason"),
                    "timestamp": timestamp,
                },
            )
        )

    for handoff in context_service.scan_track_recent_handoffs(track_id, limit=20):
        if not isinstance(handoff, dict):
            continue
        target_buddy = handoff.get("next_buddy")
        if not isinstance(target_buddy, str) or not target_buddy.strip():
            continue
        timestamp = str(handoff.get("timestamp") or "")
        rows.append(
            (
                timestamp,
                f"run:{handoff.get('run_id')}",
                {
                    "source_type": "run_audit",
                    "source_buddy": handoff.get("buddy_id"),
                    "target_buddy": target_buddy.strip(),
                    "source_task_id": handoff.get("task_id"),
                    "source_run_id": handoff.get("run_id"),
                    "reason": handoff.get("reason"),
                    "timestamp": timestamp,
                },
            )
        )

    if not rows:
        return None
    rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return rows[0][2]


def _track_discovery(
    *,
    track: dict[str, Any],
    active_buddy: str,
) -> tuple[dict[str, Any], int | None]:
    reasons: list[str] = []
    track_id = track.get("id")
    next_buddy = track.get("next_buddy")
    current_buddy = track.get("current_buddy")
    is_next_buddy = isinstance(next_buddy, str) and next_buddy == active_buddy
    is_current_buddy = isinstance(current_buddy, str) and current_buddy == active_buddy
    participates = False
    for task_id in track.get("task_ids", []):
        if not isinstance(task_id, str) or not task_id:
            continue
        task = env_store.get_task(task_id)
        if isinstance(task, dict) and task.get("buddy") == active_buddy:
            participates = True
            break

    recent_to_active = False
    latest_handoff = _latest_handoff_summary_row(track_id) if isinstance(track_id, str) and track_id else None
    if isinstance(latest_handoff, dict) and latest_handoff.get("target_buddy") == active_buddy:
        recent_to_active = True
        if latest_handoff.get("source_type") == "run_audit":
            reasons.append("recent_handoff.next_buddy == active_buddy")
        else:
            reasons.append("recent_handoff.target_buddy == active_buddy")

    if is_next_buddy:
        reasons.append("track.next_buddy == active_buddy")
    if participates:
        reasons.append("track has active_buddy participant task")
    if is_current_buddy:
        reasons.append("track.current_buddy == active_buddy")

    if is_next_buddy:
        active_role = "next_buddy"
    elif is_current_buddy:
        active_role = "current_buddy"
    elif participates:
        active_role = "participant"
    else:
        active_role = "observer"

    priority: int | None = None
    if recent_to_active and is_next_buddy:
        priority = 0
    elif recent_to_active:
        priority = 1
    elif is_next_buddy:
        priority = 2
    elif participates:
        priority = 3

    return {
        "active_buddy_role": active_role,
        "latest_handoff_to_active_buddy": recent_to_active,
        "relevance_reasons": reasons,
    }, priority


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
    effect_summary: str,
    state_changed: bool,
    durability: str,
    read_scope: str | None = None,
    state_changes: list[dict[str, Any]] | None = None,
    created_ids: list[str] | None = None,
    updated_ids: list[str] | None = None,
    binding_changed: bool | None = None,
    validation_only: bool | None = None,
    follow_up_affordances: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
    track: dict[str, Any] | None = None,
    task: dict[str, Any] | None = None,
    tracks: list[dict[str, Any]] | None = None,
    allowed_next_actions: list[str],
) -> dict[str, Any]:
    payload = tool_responses.success(
        tool="track",
        action=action,
        active_buddy=context["active_buddy"],
        effect_summary=effect_summary,
        state_changed=state_changed,
        durability=durability,
        state_changes=state_changes,
        created_ids=created_ids,
        updated_ids=updated_ids,
        binding_changed=binding_changed,
        read_scope=read_scope,
        validation_only=validation_only,
        follow_up_affordances=follow_up_affordances,
        allowed_next_actions=allowed_next_actions,
        extra={
            "current_binding": _current_binding(context),
            **(extra or {}),
        },
    )
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
    tracks: list[dict[str, Any]] = []
    candidate_rows: list[tuple[int, str, dict[str, Any]]] = []
    for track in env_store.list_tracks():
        row = _track_summary(track)
        discovery, priority = _track_discovery(track=track, active_buddy=context["active_buddy"])
        row["discovery"] = discovery
        relation = track_relations.track_relation_for_buddy(track, context["active_buddy"])
        row["active_buddy_relation"] = relation.get("relation")
        latest_handoff = _latest_handoff_summary_row(str(track.get("id") or ""))
        if isinstance(latest_handoff, dict):
            row["latest_handoff_summary"] = latest_handoff
        row["command_hint"] = track_relations.command_hint(
            "track",
            "get",
            {"track_id": str(track.get("id") or "<track-id>")},
        )
        tracks.append(row)
        if priority is not None:
            track_id = str(track.get("id") or "")
            candidate_rows.append((priority, track_id, row))

    candidate_rows.sort(key=lambda item: (item[0], item[1]))
    candidate_ids = [row.get("id") for _, _, row in candidate_rows if isinstance(row.get("id"), str)]

    prioritized_ids = {track_id for _, track_id, _ in candidate_rows}
    tracks.sort(
        key=lambda row: (
            0 if str(row.get("id") or "") in prioritized_ids else 1,
            next(
                (priority for priority, track_id, _ in candidate_rows if track_id == str(row.get("id") or "")),
                99,
            ),
            str(row.get("id") or ""),
        )
    )

    payload = _success_payload(
        action=action,
        context=context,
        effect_summary=f"Listed {len(tracks)} readable tracks for active buddy orientation.",
        state_changed=False,
        durability="none",
        read_scope="Track summaries, discovery hints, and relation metadata; no artifact full-body content.",
        tracks=tracks,
        allowed_next_actions=[
            "Use track.get with a returned track_id to inspect one track.",
            "Use track.join when active-buddy relation is missing for source intake.",
        ],
    )
    payload["next_actions"] = [
        {"tool": "track", "action": "get", "args": {"track_id": "<track-id>"}},
        {"tool": "track", "action": "join", "args": {"track_id": "<track-id>"}},
    ]
    payload["command_hint"] = track_relations.command_hint("track", "get", {"track_id": "<track-id>"})
    payload["discovery_summary"] = {
        "active_buddy": context["active_buddy"],
        "candidate_track_ids": candidate_ids,
    }
    return payload


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
    payload = _success_payload(
        action=action,
        context=context,
        effect_summary=f"Read track '{track['id']}' context summary and relation orientation.",
        state_changed=False,
        durability="none",
        read_scope="Track summary, current artifact summaries, and recent handoff rows.",
        track=track,
        allowed_next_actions=[
            "Use artifact.get with artifact ids from track_context_summary.current_artifacts.",
            "Use track.join when relation or active task linkage is missing.",
        ],
    )
    relation = track_relations.track_relation_for_buddy(track, context["active_buddy"])
    summary = _track_context_summary(track, active_buddy=context["active_buddy"])
    payload["relation"] = relation.get("relation")
    payload["current_artifacts"] = summary.get("current_artifacts", [])
    payload["recent_handoffs"] = summary.get("recent_handoffs", [])
    payload["track_context_summary"] = summary
    payload["next_actions"] = [
        {"tool": "artifact", "action": "get", "args": {"artifact_id": "<artifact-id>"}},
        {"tool": "track", "action": "join", "args": {"track_id": track.get("id")}},
    ]
    payload["command_hint"] = track_relations.command_hint(
        "artifact",
        "get",
        {"artifact_id": "<artifact-id>"},
    )
    return payload


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
        payload = _success_payload(
            action=action,
            context=context,
            effect_summary="No current track binding exists for the active instance.",
            state_changed=False,
            durability="none",
            read_scope="Instance binding state only; no bound track was read.",
            track=None,
            allowed_next_actions=[
                "Use track.list to inspect available tracks.",
                "Use track.get with a selected track_id when details are needed.",
            ],
        )
        payload["track"] = None
        payload["track_id"] = None
        payload["allowed_next_action_options"] = [
            tool_responses.next_action_option(
                tool="track",
                action="list",
                option_id="inspect_candidate_tracks",
                reason="Inspect readable tracks when no current track binding exists.",
            ),
            tool_responses.next_action_option(
                tool="track",
                action="get",
                option_id="inspect_track_details_after_list",
                reason="Inspect one selected track after listing candidates.",
            ),
        ]
        return payload
    track = env_store.get_track(track_id.strip())
    if track is None:
        return _track_lookup_error(action=action, active_buddy=context["active_buddy"], track_id=track_id.strip())
    return _success_payload(
        action=action,
        context=context,
        effect_summary=f"Read current bound track '{track['id']}' from instance binding.",
        state_changed=False,
        durability="none",
        read_scope="Current instance track binding and track summary.",
        track=track,
        allowed_next_actions=[
            "Use track.get to refresh this track context.",
            "Continue work using the current track binding.",
        ],
    )


def _active_buddy_tasks_for_track(track_id: str, active_buddy: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    track = env_store.get_track(track_id)
    if not isinstance(track, dict):
        return rows
    for task_id in track.get("task_ids", []):
        if not isinstance(task_id, str) or not task_id:
            continue
        task = env_store.get_task(task_id)
        if not isinstance(task, dict):
            continue
        if task.get("buddy") != active_buddy:
            continue
        if task.get("status") == "archived":
            continue
        rows.append(task)
    rows.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
    return rows


def _next_join_task_id(active_buddy: str, track_id: str) -> str:
    track = env_store.get_track(track_id)
    seed = env_store.slugify(str(track.get("title") or track_id)) if isinstance(track, dict) else track_id
    while True:
        candidate = f"task-{active_buddy}-join-{seed}-{uuid.uuid4().hex[:8]}"
        if env_store.get_task(candidate) is None:
            return candidate


def join_track_for_active_buddy(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.join"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_JOIN_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    for permission in (_READ_PERMISSION, _TASK_CREATE_PERMISSION, _TASK_UPDATE_PERMISSION):
        permission_error = _require_permission(context, permission, action)
        if permission_error is not None:
            return permission_error

    track, error = _get_track(context=context, action=action, args=args)
    if error is not None:
        return error
    assert track is not None
    track_id = str(track.get("id"))
    if track.get("status") == "archived":
        return _error_payload(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_TRACK_LIFECYCLE_STATUS",
            message=f"track '{track_id}' is archived",
            permission_boundary="track.lifecycle_status",
            track_id=track_id,
            allowed_next_actions=[
                "Choose a non-archived track.",
                "Ask PM to create a new active track for continued work.",
            ],
        )

    selected_task: dict[str, Any] | None = None
    created_task = False
    task_relation_changed = False
    requested_task_id = args.get("task_id")
    if requested_task_id is not None:
        task, task_error = _get_owned_task(context=context, action=action, args={"task_id": requested_task_id})
        if task_error is not None:
            return task_error
        assert task is not None
        if task.get("status") == "archived":
            return _error_payload(
                action=action,
                active_buddy=context["active_buddy"],
                code="E_TASK_STATUS",
                message=f"task '{task['id']}' is archived and cannot be selected by track.join",
                permission_boundary="task.status",
                track_id=track_id,
                task_id=str(task["id"]),
                allowed_next_actions=[
                    "Select a non-archived active-buddy task.",
                    "Use track.join without --task-id to create a fresh task when no active candidate exists.",
                ],
            )
        existing_track = task.get("track_id")
        if isinstance(existing_track, str) and existing_track and existing_track != track_id:
            return _linkage_error(
                action=action,
                active_buddy=context["active_buddy"],
                track_id=track_id,
                task_id=str(task["id"]),
                message=f"task '{task['id']}' is already bound to track '{existing_track}'",
            )
        if existing_track != track_id:
            task = env_store.register_task_to_track(track_id, str(task["id"]))
            task_relation_changed = True
        selected_task = task
    else:
        active_tasks = _active_buddy_tasks_for_track(track_id, context["active_buddy"])
        if len(active_tasks) == 0:
            new_task_id = _next_join_task_id(context["active_buddy"], track_id)
            selected_task = env_store.create_task(
                new_task_id,
                f"Join {track.get('title')}",
                buddy=context["active_buddy"],
                track_id=track_id,
                status="active",
                summary=f"Joined track {track_id} for {context['active_buddy']} work.",
                initial_run_id=None,
            )
            created_task = True
        elif len(active_tasks) == 1:
            selected_task = active_tasks[0]
        else:
            candidates = [str(task.get("id")) for task in active_tasks if isinstance(task.get("id"), str)]
            return _error_payload(
                action=action,
                active_buddy=context["active_buddy"],
                code="E_TRACK_JOIN_AMBIGUITY",
                message="multiple active-buddy tasks are already attached to this track; choose one explicitly",
                permission_boundary="track.join_ambiguity",
                track_id=track_id,
                allowed_next_actions=[
                    "Retry track.join with --task-id <task-id> using one returned candidate.",
                    "Archive or detach stale tasks before retrying automatic join selection.",
                ],
            ) | {
                "candidate_task_ids": candidates,
                "next_actions": [
                    {"tool": "track", "action": "join", "args": {"track_id": track_id, "task_id": "<task-id>"}},
                ],
                "command_hint": track_relations.command_hint(
                    "track",
                    "join",
                    {"track_id": track_id, "task_id": "<task-id>"},
                ),
                "relation": "participant",
            }

    assert isinstance(selected_task, dict)
    binding = binding_service.write_instance_binding(
        context=context,
        task_id=str(selected_task["id"]),
        track_id=track_id,
    )
    track_after = env_store.get_track(track_id) or track
    relation = track_relations.track_relation_for_buddy(track_after, context["active_buddy"])
    readable_artifacts = track_relations.current_artifact_rows_for_track(track_id, context["active_buddy"])
    join_state_changes: list[dict[str, Any]] = [
        {
            "object_type": "instance_binding",
            "object_id": context["instance_id"],
            "change": "current_task_id/current_track_id updated",
        }
    ]
    if created_task:
        join_state_changes.append(
            {
                "object_type": "task",
                "object_id": selected_task["id"],
                "change": "created and attached to track",
            }
        )
    elif task_relation_changed:
        join_state_changes.append(
            {
                "object_type": "task",
                "object_id": selected_task["id"],
                "change": "reused/attached for active-buddy participation",
            }
        )
    durability = "runtime_object+instance_binding" if (created_task or task_relation_changed) else "instance_binding"
    return _success_payload(
        action=action,
        context=context,
        effect_summary=(
            f"Joined track '{track_id}' with task '{selected_task['id']}', updating active instance binding without "
            "changing PM lifecycle fields."
        ),
        state_changed=True,
        durability=durability,
        state_changes=join_state_changes,
        created_ids=[str(selected_task["id"])] if created_task else [],
        updated_ids=[str(selected_task["id"])] if task_relation_changed else [],
        binding_changed=True,
        allowed_next_actions=[
            "Use track.get to inspect current artifact ids after join.",
            "Use artifact.get with returned artifact ids for full body reads.",
        ],
        extra={
            "track_id": track_id,
            "task_id": selected_task["id"],
            "task": _task_summary(selected_task),
            "created_task": created_task,
            "current_task_selected": True,
            "relation": relation.get("relation"),
            "readable_artifact_count": len([row for row in readable_artifacts if row.get("readable_by_current_buddy")]),
            "current_binding": binding,
            "next_actions": [
                {"tool": "artifact", "action": "get", "args": {"artifact_id": "<artifact-id>"}},
                {"tool": "track", "action": "get", "args": {"track_id": track_id}},
            ],
            "command_hint": track_relations.command_hint("artifact", "get", {"artifact_id": "<artifact-id>"}),
        },
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
        effect_summary=f"Created track '{track['id']}' with PM lifecycle ownership.",
        state_changed=True,
        durability="runtime_object",
        state_changes=[{"object_type": "track", "object_id": track["id"], "change": "created"}],
        created_ids=[str(track["id"])],
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
        effect_summary=f"Updated lifecycle fields on track '{updated['id']}'.",
        state_changed=True,
        durability="runtime_object",
        state_changes=[{"object_type": "track", "object_id": updated["id"], "change": "updated"}],
        updated_ids=[str(updated["id"])],
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
        effect_summary=f"Advanced track '{updated['id']}' lifecycle fields.",
        state_changed=True,
        durability="runtime_object",
        state_changes=[{"object_type": "track", "object_id": updated["id"], "change": "advanced"}],
        updated_ids=[str(updated["id"])],
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
        effect_summary=f"Archived track '{archived['id']}' by status update; track record was not deleted.",
        state_changed=True,
        durability="runtime_object",
        state_changes=[{"object_type": "track", "object_id": archived["id"], "change": "status set to archived"}],
        updated_ids=[str(archived["id"])],
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
        effect_summary=f"Attached task '{linked_task['id']}' to track '{linked_track['id']}'.",
        state_changed=True,
        durability="runtime_object",
        state_changes=[
            {"object_type": "task", "object_id": linked_task["id"], "change": "track_id linked"},
            {"object_type": "track", "object_id": linked_track["id"], "change": "task membership updated"},
        ],
        updated_ids=[str(linked_task["id"]), str(linked_track["id"])],
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
        effect_summary=f"Detached task '{task['id']}' from track '{detached_track['id']}'.",
        state_changed=True,
        durability="runtime_object",
        state_changes=[
            {"object_type": "task", "object_id": task["id"], "change": "track_id cleared or membership removed"},
            {"object_type": "track", "object_id": detached_track["id"], "change": "task membership updated"},
        ],
        updated_ids=[str(task["id"]), str(detached_track["id"])],
        track=detached_track,
        task=task,
        allowed_next_actions=[
            "Use track.attach_task to relink the task if needed.",
            "Use task.list to continue with active-buddy tasks.",
        ],
    )
