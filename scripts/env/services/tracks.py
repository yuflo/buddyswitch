#!/usr/bin/env python3
"""Runless track services for broker-routed env.tool operations."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.services import artifact_visibility
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
_CREATE_FIELDS = {"track_id", "title", "status", "summary"}
_UPDATE_FIELDS = {"track_id", "title", "status", "summary"}
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
    if action == "track.archive":
        return _ARCHIVE_FIELDS
    if action in {"track.attach_task", "track.detach_task"}:
        return _ATTACH_FIELDS
    return set()


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    correctable_fields: list[str] | None = None
    if "track_id" in message:
        correctable_fields = ["track_id"]
    elif "task_id" in message:
        correctable_fields = ["task_id"]
    elif "title" in message:
        correctable_fields = ["title"]
    elif "status" in message:
        correctable_fields = ["status"]
    elif "owner_buddy" in message:
        correctable_fields = ["owner_buddy"]
    elif "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            correctable_fields = [row.strip() for row in suffix.split(",") if row.strip()]
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
        correctable_fields=correctable_fields,
    )


def _reject_archived(*, action: str, active_buddy: str, track_id: str) -> dict[str, Any]:
    message = f"track '{track_id}' is archived and cannot be read via {action}"
    return tool_responses.rejection(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        code="E_TRACK_ARCHIVED",
        message=message,
        permission_boundary="track.lifecycle_status",
        human_summary="Archived tracks are explicit read boundaries.",
        why_blocked=message,
        impact="No track, task, or artifact state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Use track.list without archived rows or choose an active track id.",
        allowed_next_actions=["Use track.list for active track discovery."],
        correctable_fields=["track_id"],
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
        ],
        correctable_fields=["active_buddy"],
    )


def _reject_task_scope(
    *,
    action: str,
    active_buddy: str,
    task_id: str,
    owner_buddy: str | None,
) -> dict[str, Any]:
    owner = owner_buddy or "unknown"
    message = f"task '{task_id}' is owned by buddy '{owner}'"
    return tool_responses.rejection(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        code="E_TRACK_TASK_SCOPE",
        message=message,
        permission_boundary="task.buddy_scope",
        human_summary="Track relation mutation requires an active-buddy-owned task.",
        why_blocked=message,
        impact="No track, task, or artifact state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Use a task_id owned by the active buddy.",
        allowed_next_actions=[
            "Use task.list to find active-buddy task ids.",
            "Use track.get to inspect current track context.",
        ],
        correctable_fields=["task_id"],
    )


def _normalize_track_summary(track: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": track.get("id"),
        "title": track.get("title"),
        "summary": track.get("summary", ""),
        "status": track.get("status"),
        "owner_buddy": track.get("owner_buddy"),
        "task_ids": list(track.get("task_ids", [])),
        "updated_at": track.get("updated_at"),
    }


def _track_context(track: dict[str, Any], active_buddy: str) -> dict[str, Any]:
    task_ids = [task_id for task_id in track.get("task_ids", []) if isinstance(task_id, str)]
    tasks: list[dict[str, Any]] = []
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

    artifacts = artifact_visibility.current_artifact_rows_for_track(str(track.get("id") or ""), active_buddy)
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


def _task_buddies(track: dict[str, Any]) -> set[str]:
    buddies: set[str] = set()
    for task_id in track.get("task_ids", []):
        if not isinstance(task_id, str):
            continue
        task = env_store.get_task(task_id)
        if isinstance(task, dict) and isinstance(task.get("buddy"), str):
            buddies.add(task["buddy"])
    return buddies


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
    else:
        rows = [row for row in rows if row.get("status") != "archived"]

    buddy = args.get("buddy")
    if isinstance(buddy, str) and buddy:
        rows = [
            row
            for row in rows
            if row.get("owner_buddy") == buddy or buddy in _task_buddies(row)
        ]

    limit = args.get("limit")
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]

    summaries = [_normalize_track_summary(row) for row in rows]
    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Returned {len(summaries)} track summary row(s) for first-pass collaboration context.",
        state_changed=False,
        durability="none",
        read_scope="readable track summaries",
        allowed_next_actions=[
            "Use track.get for one track context.",
            "Use track.join to create/reuse your task relation on a track.",
        ],
        extra={"tracks": summaries, "discovery_summary": {"count": len(summaries)}},
    )


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
    if track.get("status") == "archived":
        return _reject_archived(action=action, active_buddy=active_buddy, track_id=track_id)

    context_payload = _track_context(track, active_buddy)
    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Read one track context '{track_id}' with track metadata plus related task and artifact summaries (no full artifact bodies).",
        state_changed=False,
        durability="none",
        read_scope="one track metadata record plus related task/artifact summaries",
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
    if track.get("status") == "archived":
        return _reject_archived(action=action, active_buddy=active_buddy, track_id=track_id)

    task_id = args.get("task_id")
    if task_id is not None and (not isinstance(task_id, str) or not task_id.strip()):
        return _reject_payload(action=action, active_buddy=active_buddy, message="task_id must be a non-empty string")

    task: dict[str, Any] | None = None
    if isinstance(task_id, str) and task_id.strip():
        task = env_store.get_task(task_id.strip())
        if task is None:
            return _reject_payload(action=action, active_buddy=active_buddy, message=f"task not found: {task_id}")
        if task.get("buddy") != active_buddy:
            return _reject_task_scope(
                action=action,
                active_buddy=active_buddy,
                task_id=task_id,
                owner_buddy=str(task.get("buddy")),
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
        state_changes.append({"object_type": "task_relation", "change": "task_created", "task_id": task["id"], "track_id": track_id})
    elif task.get("track_id") != track_id:
        task = env_store.register_task_to_track(track_id, task["id"])
        state_changes.append({"object_type": "task_relation", "change": "task_attached", "task_id": task["id"], "track_id": track_id})
    else:
        env_store.register_task_to_track(track_id, task["id"])

    updated_track = env_store.get_track(track_id)
    if updated_track is not None and task["id"] in updated_track.get("task_ids", []):
        if not state_changes:
            state_changes.append({"object_type": "task_relation", "change": "relation_reused", "task_id": task["id"], "track_id": track_id})

    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Updated explicit task-track relation for track '{track_id}' using task '{task['id']}' (created, attached, or reused relation).",
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
            "relation": "track_task",
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
        try:
            created = env_store.create_track(
                track_id,
                title.strip(),
                status=status,
                owner_buddy=active_buddy,
                summary=summary,
            )
        except ValueError as exc:
            return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))
        return tool_responses.success(
            tool="track",
            action=action,
            active_buddy=active_buddy,
            effect_summary=f"Created one durable track lifecycle object '{track_id}'.",
            state_changed=True,
            durability="durable",
            created_ids=[track_id],
            state_changes=[{"object_type": "track", "change": "created", "track_id": track_id}],
            allowed_next_actions=["Use track.get to inspect the new track context."],
            extra={"track_id": track_id, "track": _normalize_track_summary(created)},
        )

    track = env_store.get_track(track_id)
    if track is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"track not found: {track_id}")

    patch: dict[str, Any] = {}
    for field in ("title", "summary", "status"):
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

    try:
        updated = env_store.update_track(track_id, patch)
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    lifecycle_change = {
        "track.update": "updated",
        "track.archive": "archived",
    }.get(action, "updated")
    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Persisted durable lifecycle change '{lifecycle_change}' for track '{track_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[track_id],
        state_changes=[{"object_type": "track", "change": lifecycle_change, "track_id": track_id}],
        allowed_next_actions=["Use track.get to inspect updated lifecycle state."],
        extra={"track_id": track_id, "track": _normalize_track_summary(updated)},
    )


def create_track_for_pm(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    return _pm_write(action="track.create", args=args, context=context, default_status="active")


def update_track_for_pm(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    return _pm_write(action="track.update", args=args, context=context)


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

    track = env_store.get_track(track_id.strip())
    if track is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"track not found: {track_id}")
    if track.get("status") == "archived":
        return _reject_archived(action=action, active_buddy=active_buddy, track_id=track_id.strip())

    task = env_store.get_task(task_id.strip())
    if task is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"task not found: {task_id}")
    if task.get("buddy") != active_buddy:
        return _reject_task_scope(
            action=action,
            active_buddy=active_buddy,
            task_id=task_id.strip(),
            owner_buddy=str(task.get("buddy")),
        )

    try:
        updated_task = env_store.register_task_to_track(track_id.strip(), task_id.strip())
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    updated_track = env_store.get_track(track_id.strip())
    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Attached task '{task_id}' to track '{track_id}' in durable task-track relation state.",
        state_changed=True,
        durability="durable",
        updated_ids=[task_id.strip(), track_id.strip()],
        state_changes=[{"object_type": "task_track_relation", "change": "attached", "task_id": task_id.strip(), "track_id": track_id.strip()}],
        allowed_next_actions=["Use track.get to inspect updated relationship."],
        extra={
            "track_id": track_id.strip(),
            "task_id": task_id.strip(),
            "track": _normalize_track_summary(updated_track) if isinstance(updated_track, dict) else None,
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
        return _reject_task_scope(
            action=action,
            active_buddy=active_buddy,
            task_id=task_id.strip(),
            owner_buddy=str(task.get("buddy")),
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
        effect_summary=f"Detached task '{task_id}' from track '{track_id}' in durable task-track relation state.",
        state_changed=True,
        durability="durable",
        updated_ids=[task_id.strip(), track_id.strip()],
        state_changes=[{"object_type": "task_track_relation", "change": "detached", "task_id": task_id.strip(), "track_id": track_id.strip()}],
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
