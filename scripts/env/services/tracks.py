#!/usr/bin/env python3
"""Runless track services for broker-routed env.tool operations."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.services import track_relations
from env.tools import responses as tool_responses


class TrackServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


_LIST_FIELDS = {"status", "buddy", "limit"}
_GET_FIELDS = {"track_id"}
_JOIN_FIELDS = {"track_id", "task_id", "title", "summary"}
_CREATE_FIELDS = {"track_id", "title", "status", "current_buddy", "next_buddy", "summary"}
_UPDATE_FIELDS = {"track_id", "title", "status", "current_buddy", "next_buddy", "summary"}
_ADVANCE_FIELDS = {"track_id", "status", "current_buddy", "next_buddy", "summary"}
_ARCHIVE_FIELDS = {"track_id"}
_ATTACH_FIELDS = {"track_id", "task_id"}


def _allowed(action: str) -> set[str]:
    if action == "track.list":
        return _LIST_FIELDS
    if action == "track.get":
        return _GET_FIELDS
    if action == "track.join":
        return _JOIN_FIELDS
    if action == "track.create":
        return _CREATE_FIELDS
    if action == "track.update":
        return _UPDATE_FIELDS
    if action == "track.advance":
        return _ADVANCE_FIELDS
    if action == "track.archive":
        return _ARCHIVE_FIELDS
    if action in {"track.attach_task", "track.detach_task"}:
        return _ATTACH_FIELDS
    return set()


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        code="E_TRACK_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Track request payload is invalid.",
        why_blocked=message,
        impact="No track, task, or artifact state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix track payload fields and retry.",
        allowed_next_actions=[
            "Use track.list to inspect available track ids.",
            "Retry with only documented track payload fields.",
        ],
    )


def _reject_authority(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        code="E_TRACK_AUTHORITY",
        message=message,
        permission_boundary="track.lifecycle_authority",
        human_summary="Track lifecycle change is PM-owned.",
        why_blocked=message,
        impact="No track lifecycle state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Use buddy 'pm' for track lifecycle updates.",
        allowed_next_actions=[
            "Use track.list to inspect current lifecycle state.",
            "Hand off to PM when lifecycle mutation is required.",
        ],
    )


def _normalize_track_summary(track: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": track.get("id"),
        "title": track.get("title"),
        "summary": track.get("summary", ""),
        "status": track.get("status"),
        "current_buddy": track.get("current_buddy"),
        "next_buddy": track.get("next_buddy"),
        "task_ids": list(track.get("task_ids", [])),
        "updated_at": track.get("updated_at"),
    }


def _track_context(track: dict[str, Any], active_buddy: str) -> dict[str, Any]:
    task_ids = [task_id for task_id in track.get("task_ids", []) if isinstance(task_id, str)]
    tasks: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    for task_id in task_ids:
        task = env_store.get_task(task_id)
        if task is None:
            continue
        tasks.append(
            {
                "id": task.get("id"),
                "buddy": task.get("buddy"),
                "title": task.get("title"),
                "summary": task.get("summary", ""),
                "status": task.get("status"),
                "artifact_ids": list(task.get("artifact_ids", [])),
                "artifact_slots": dict(task.get("artifact_slots", {})),
                "updated_at": task.get("updated_at"),
            }
        )
        for artifact in track_relations.artifacts_for_task(task_id):
            artifacts.append(track_relations.artifact_summary_row(artifact, active_buddy, track=track, task=task))

    return {
        "track": _normalize_track_summary(track),
        "tasks": tasks,
        "artifacts": artifacts,
    }


def _require_fields(action: str, args: dict[str, Any], active_buddy: str) -> dict[str, Any] | None:
    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"unsupported payload fields: {', '.join(unknown)}")
    return None


def _is_pm(active_buddy: str) -> bool:
    return active_buddy == "pm"


def list_tracks_for_active_buddy(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.list"
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    rows = env_store.list_tracks()
    status = args.get("status")
    if isinstance(status, str) and status:
        rows = [row for row in rows if row.get("status") == status]

    buddy = args.get("buddy")
    if isinstance(buddy, str) and buddy:
        rows = [
            row
            for row in rows
            if row.get("current_buddy") == buddy or row.get("next_buddy") == buddy or buddy in _task_buddies(row)
        ]

    limit = args.get("limit")
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]

    summaries = [_normalize_track_summary(row) for row in rows]
    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Listed {len(summaries)} track(s).",
        state_changed=False,
        durability="none",
        read_scope="readable track summaries",
        allowed_next_actions=[
            "Use track.get for one track context.",
            "Use track.join to create/reuse your task relation on a track.",
        ],
        extra={"tracks": summaries, "discovery_summary": {"count": len(summaries)}},
    )


def _task_buddies(track: dict[str, Any]) -> set[str]:
    buddies: set[str] = set()
    for task_id in track.get("task_ids", []):
        if not isinstance(task_id, str):
            continue
        task = env_store.get_task(task_id)
        if isinstance(task, dict) and isinstance(task.get("buddy"), str):
            buddies.add(task["buddy"])
    return buddies


def get_track_for_active_buddy(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.get"
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    track_id = args.get("track_id")
    if not isinstance(track_id, str) or not track_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="track_id is required")
    track_id = track_id.strip()

    track = env_store.get_track(track_id)
    if track is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"track not found: {track_id}")

    context_payload = _track_context(track, active_buddy)
    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Read track '{track_id}' with related tasks and artifacts.",
        state_changed=False,
        durability="none",
        read_scope="track + related tasks/artifacts",
        allowed_next_actions=[
            "Use track.join to create/reuse your task relation.",
            "Use artifact.get for full artifact body intake.",
        ],
        extra={"track_id": track_id, "track": context_payload["track"], "track_context_summary": context_payload},
    )


def join_track_for_active_buddy(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.join"
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    track_id = args.get("track_id")
    if not isinstance(track_id, str) or not track_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="track_id is required")
    track_id = track_id.strip()

    track = env_store.get_track(track_id)
    if track is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"track not found: {track_id}")

    task_id = args.get("task_id")
    if task_id is not None and (not isinstance(task_id, str) or not task_id.strip()):
        return _reject_payload(action=action, active_buddy=active_buddy, message="task_id must be a non-empty string")

    task = None
    if isinstance(task_id, str) and task_id.strip():
        task = env_store.get_task(task_id.strip())
        if task is None:
            return _reject_payload(action=action, active_buddy=active_buddy, message=f"task not found: {task_id}")
        if task.get("buddy") != active_buddy:
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message=f"task '{task_id}' is owned by buddy '{task.get('buddy')}'",
            )
    else:
        for candidate_id in track.get("task_ids", []):
            candidate = env_store.get_task(candidate_id)
            if isinstance(candidate, dict) and candidate.get("buddy") == active_buddy:
                task = candidate
                break

    state_changes: list[dict[str, Any]] = []
    if task is None:
        requested_title = args.get("title")
        title = requested_title.strip() if isinstance(requested_title, str) and requested_title.strip() else f"{track.get('title', 'Track')} Task"
        summary = args.get("summary")
        if summary is None:
            summary = ""
        if not isinstance(summary, str):
            return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")
        generated_task_id = f"task-{active_buddy}-{env_store.slugify(title)}-{uuid.uuid4().hex[:8]}"
        task = env_store.create_task(
            generated_task_id,
            title,
            buddy=active_buddy,
            track_id=track_id,
            status="active",
            summary=summary,
            initial_run_id=None,
        )
        state_changes.append({"change": "task_created", "task_id": task["id"]})
    elif task.get("track_id") != track_id:
        task = env_store.register_task_to_track(track_id, task["id"])
        state_changes.append({"change": "task_attached", "task_id": task["id"]})
    else:
        env_store.register_task_to_track(track_id, task["id"])

    updated_track = env_store.get_track(track_id)
    if updated_track is not None and task["id"] in updated_track.get("task_ids", []):
        if not state_changes:
            state_changes.append({"change": "relation_reused", "task_id": task["id"]})

    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Joined track '{track_id}' using task '{task['id']}' without instance binding mutation.",
        state_changed=bool(state_changes and state_changes[0]["change"] != "relation_reused"),
        durability="durable" if state_changes and state_changes[0]["change"] != "relation_reused" else "none",
        allowed_next_actions=[
            "Use artifact.create_revision with returned task_id.",
            "Use track.get for updated track context.",
        ],
        state_changes=state_changes,
        extra={
            "track_id": track_id,
            "task_id": task["id"],
            "task": {
                "id": task["id"],
                "buddy": task.get("buddy"),
                "title": task.get("title"),
                "summary": task.get("summary", ""),
                "status": task.get("status"),
                "track_id": task.get("track_id"),
            },
            "relation": "participant",
        },
    )


def _pm_write(
    *,
    action: str,
    args: dict[str, Any],
    context: TrackServiceContext,
    default_status: str | None = None,
) -> dict[str, Any]:
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error
    if not _is_pm(active_buddy):
        return _reject_authority(action=action, active_buddy=active_buddy, message="only pm may mutate track lifecycle")

    track_id = args.get("track_id")
    if not isinstance(track_id, str) or not track_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="track_id is required")
    track_id = track_id.strip()

    title = args.get("title")
    summary = args.get("summary")
    status = args.get("status")
    current_buddy = args.get("current_buddy")
    next_buddy = args.get("next_buddy")

    if action == "track.create":
        if not isinstance(title, str) or not title.strip():
            return _reject_payload(action=action, active_buddy=active_buddy, message="title is required")
        if summary is None:
            summary = ""
        if not isinstance(summary, str):
            return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")
        if status is None:
            status = default_status or "active"
        if status not in env_store.VALID_TRACK_STATUS:
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message=f"status must be one of {', '.join(env_store.VALID_TRACK_STATUS)}",
            )
        if current_buddy is None:
            current_buddy = active_buddy
        if not isinstance(current_buddy, str) or not current_buddy.strip():
            return _reject_payload(action=action, active_buddy=active_buddy, message="current_buddy must be a non-empty string")
        if next_buddy is not None and (not isinstance(next_buddy, str) or not next_buddy.strip()):
            return _reject_payload(action=action, active_buddy=active_buddy, message="next_buddy must be a non-empty string")
        try:
            created = env_store.create_track(
                track_id,
                title.strip(),
                status=status,
                current_buddy=current_buddy.strip(),
                next_buddy=next_buddy.strip() if isinstance(next_buddy, str) and next_buddy.strip() else None,
                summary=summary,
            )
        except ValueError as exc:
            return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))
        return tool_responses.success(
            tool="track",
            action=action,
            active_buddy=active_buddy,
            effect_summary=f"Created track '{track_id}'.",
            state_changed=True,
            durability="durable",
            created_ids=[track_id],
            allowed_next_actions=["Use track.get to inspect the new track context."],
            extra={"track_id": track_id, "track": _normalize_track_summary(created)},
        )

    track = env_store.get_track(track_id)
    if track is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"track not found: {track_id}")

    patch: dict[str, Any] = {}
    for field in ("title", "summary", "status", "current_buddy", "next_buddy"):
        if field in args:
            patch[field] = args[field]

    if action == "track.archive":
        patch["status"] = "archived"

    if not patch:
        return _reject_payload(action=action, active_buddy=active_buddy, message="at least one patch field is required")

    if "title" in patch and (not isinstance(patch["title"], str) or not patch["title"].strip()):
        return _reject_payload(action=action, active_buddy=active_buddy, message="title must be a non-empty string")
    if "summary" in patch and not isinstance(patch["summary"], str):
        return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")
    if "status" in patch and patch["status"] not in env_store.VALID_TRACK_STATUS:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"status must be one of {', '.join(env_store.VALID_TRACK_STATUS)}",
        )
    if "current_buddy" in patch and (not isinstance(patch["current_buddy"], str) or not patch["current_buddy"].strip()):
        return _reject_payload(action=action, active_buddy=active_buddy, message="current_buddy must be a non-empty string")
    if "next_buddy" in patch and patch["next_buddy"] is not None:
        if not isinstance(patch["next_buddy"], str) or not patch["next_buddy"].strip():
            return _reject_payload(action=action, active_buddy=active_buddy, message="next_buddy must be a non-empty string")

    try:
        updated = env_store.update_track(track_id, patch)
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Updated lifecycle for track '{track_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[track_id],
        allowed_next_actions=["Use track.get to inspect updated lifecycle state."],
        extra={"track_id": track_id, "track": _normalize_track_summary(updated)},
    )


def create_track_for_pm(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    return _pm_write(action="track.create", args=args, context=context, default_status="active")


def update_track_for_pm(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    return _pm_write(action="track.update", args=args, context=context)


def advance_track_for_pm(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    return _pm_write(action="track.advance", args=args, context=context)


def archive_track_for_pm(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    return _pm_write(action="track.archive", args=args, context=context)


def attach_task_to_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.attach_task"
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error
    track_id = args.get("track_id")
    task_id = args.get("task_id")
    if not isinstance(track_id, str) or not track_id.strip() or not isinstance(task_id, str) or not task_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="track_id and task_id are required")

    task = env_store.get_task(task_id.strip())
    if task is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"task not found: {task_id}")
    if task.get("buddy") != active_buddy:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"task '{task_id}' is owned by buddy '{task.get('buddy')}'",
        )

    try:
        updated_task = env_store.register_task_to_track(track_id.strip(), task_id.strip())
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    track = env_store.get_track(track_id.strip())
    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Attached task '{task_id}' to track '{track_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[task_id.strip(), track_id.strip()],
        allowed_next_actions=["Use track.get to inspect updated relationship."],
        extra={
            "track_id": track_id.strip(),
            "task_id": task_id.strip(),
            "track": _normalize_track_summary(track) if isinstance(track, dict) else None,
            "task": {
                "id": updated_task.get("id"),
                "buddy": updated_task.get("buddy"),
                "track_id": updated_task.get("track_id"),
            },
        },
    )


def detach_task_from_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.detach_task"
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    track_id = args.get("track_id")
    task_id = args.get("task_id")
    if not isinstance(track_id, str) or not track_id.strip() or not isinstance(task_id, str) or not task_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="track_id and task_id are required")

    task = env_store.get_task(task_id.strip())
    if task is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"task not found: {task_id}")
    if task.get("buddy") != active_buddy:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"task '{task_id}' is owned by buddy '{task.get('buddy')}'",
        )

    if task.get("track_id") == track_id.strip():
        env_store.update_task(task_id.strip(), {"track_id": None})
    track = env_store.get_track(track_id.strip())
    if isinstance(track, dict):
        task_ids = [item for item in track.get("task_ids", []) if item != task_id.strip()]
        env_store.update_track(track_id.strip(), {"task_ids": task_ids})

    updated_track = env_store.get_track(track_id.strip())
    updated_task = env_store.get_task(task_id.strip())
    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Detached task '{task_id}' from track '{track_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[task_id.strip(), track_id.strip()],
        allowed_next_actions=["Use track.get to inspect updated relationship."],
        extra={
            "track_id": track_id.strip(),
            "task_id": task_id.strip(),
            "track": _normalize_track_summary(updated_track) if isinstance(updated_track, dict) else None,
            "task": {
                "id": updated_task.get("id") if isinstance(updated_task, dict) else task_id.strip(),
                "buddy": updated_task.get("buddy") if isinstance(updated_task, dict) else active_buddy,
                "track_id": updated_task.get("track_id") if isinstance(updated_task, dict) else None,
            },
        },
    )
