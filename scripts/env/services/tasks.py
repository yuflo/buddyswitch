#!/usr/bin/env python3
"""Runless task services for broker-routed env.tool operations."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.tools import responses as tool_responses


class TaskServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


_CREATE_FIELDS = {"task_id", "title", "summary", "status", "track_id", "buddy", "active_buddy"}
_GET_FIELDS = {"task_id"}
_LIST_FIELDS = {"status", "track_id", "limit"}
_UPDATE_FIELDS = {"task_id", "title", "summary", "status", "track_id"}
_ARCHIVE_FIELDS = {"task_id"}


def _allowed_set(action: str) -> set[str]:
    if action == "task.create":
        return _CREATE_FIELDS
    if action == "task.list":
        return _LIST_FIELDS
    if action == "task.get":
        return _GET_FIELDS
    if action == "task.update":
        return _UPDATE_FIELDS
    if action == "task.archive":
        return _ARCHIVE_FIELDS
    return set()


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    alternative_capabilities = [
        tool_responses.alternative_capability(
            tool="context",
            action="summarize",
            condition="Use when you need candidate ids before retrying a task payload.",
        ),
        tool_responses.alternative_capability(
            tool="context",
            action="get",
            condition="Use when you need full tool catalog and id source details.",
        ),
    ]
    correctable_fields: list[str] | None = None
    if "title" in message:
        correctable_fields = ["title"]
    elif "status" in message:
        correctable_fields = ["status"]
    elif "track_id" in message:
        correctable_fields = ["track_id"]
    elif "task_id" in message:
        correctable_fields = ["task_id"]
    elif "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            correctable_fields = [row.strip() for row in suffix.split(",") if row.strip()]
    return tool_responses.rejection(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        code="E_TASK_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Task request payload is invalid.",
        why_blocked=message,
        impact="No task or track state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix task payload fields and retry.",
        allowed_next_actions=[
            "Use task.list to inspect current task ids.",
            "Retry with only documented task payload fields.",
        ],
        correctable_fields=correctable_fields,
        alternative_capabilities=alternative_capabilities,
    )


def _reject_scope(*, action: str, active_buddy: str, task_id: str, message: str) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        code="E_TASK_BUDDY_SCOPE",
        message=message,
        permission_boundary="task.buddy_scope",
        human_summary="Task belongs to another buddy.",
        why_blocked=message,
        impact="No task or track state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Use a task owned by the active buddy.",
        allowed_next_actions=[
            "Use task.list to find active-buddy task ids.",
            "Use task.create to create an active-buddy task when needed.",
        ],
        correctable_fields=["task_id"],
        alternative_capabilities=[
            tool_responses.alternative_capability(
                tool="task",
                action="list",
                condition="Use when you need owned task ids before retrying with task_id.",
            ),
        ],
        extra={"task_id": task_id},
    )


def _normalize_task_summary(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task.get("id"),
        "buddy": task.get("buddy"),
        "title": task.get("title"),
        "summary": task.get("summary", ""),
        "status": task.get("status"),
        "track_id": task.get("track_id"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
    }


def _require_allowed_fields(*, action: str, args: dict[str, Any], active_buddy: str) -> dict[str, Any] | None:
    allowed = _allowed_set(action)
    unknown = sorted(key for key in args if key not in allowed)
    if unknown:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"unsupported payload fields: {', '.join(unknown)}",
        )
    return None


def create_task_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.create"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action=action, args=args, active_buddy=active_buddy)
    if payload_error is not None:
        return payload_error

    title = args.get("title")
    if not isinstance(title, str) or not title.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="title is required")

    task_id = args.get("task_id")
    if task_id is None:
        slug = env_store.slugify(title)
        task_id = f"task-{active_buddy}-{slug}-{uuid.uuid4().hex[:8]}"
    elif not isinstance(task_id, str) or not task_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="task_id must be a non-empty string")

    summary = args.get("summary")
    if summary is None:
        summary = ""
    if not isinstance(summary, str):
        return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")

    status = args.get("status")
    if status is None:
        status = "active"
    if status not in env_store.VALID_TASK_STATUS:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"status must be one of {', '.join(env_store.VALID_TASK_STATUS)}",
        )

    track_id = args.get("track_id")
    if track_id is not None and not isinstance(track_id, str):
        return _reject_payload(action=action, active_buddy=active_buddy, message="track_id must be a string or null")
    if isinstance(track_id, str) and env_store.get_track(track_id) is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"track not found: {track_id}")

    try:
        task = env_store.create_task(
            task_id.strip(),
            title.strip(),
            buddy=active_buddy,
            track_id=track_id,
            status=status,
            summary=summary,
            initial_run_id=None,
        )
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    created = _normalize_task_summary(task)
    return tool_responses.success(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Created one active-buddy durable task '{task['id']}' with optional track relation support.",
        state_changed=True,
        durability="durable",
        created_ids=[task["id"]],
        state_changes=[{"object_type": "task", "change": "created", "task_id": task["id"]}],
        allowed_next_actions=[
            "Use artifact.create_revision to draft or publish shared artifacts.",
            "Use task.update to refine task status or summary.",
        ],
        extra={"task_id": task["id"], "task": created},
    )


def list_tasks_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.list"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action=action, args=args, active_buddy=active_buddy)
    if payload_error is not None:
        return payload_error

    rows = [task for task in env_store.list_tasks() if task.get("buddy") == active_buddy]

    status = args.get("status")
    if isinstance(status, str) and status:
        rows = [row for row in rows if row.get("status") == status]

    track_id = args.get("track_id")
    if isinstance(track_id, str) and track_id:
        rows = [row for row in rows if row.get("track_id") == track_id]

    limit = args.get("limit")
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]

    payload_rows = [_normalize_task_summary(row) for row in rows]
    return tool_responses.success(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Returned {len(payload_rows)} active-buddy task summary row(s).",
        state_changed=False,
        durability="none",
        read_scope="active-buddy task summaries",
        allowed_next_actions=[
            "Use task.get with task_id for one task detail.",
            "Use artifact.create_revision to draft or publish shared artifacts.",
        ],
        extra={"tasks": payload_rows, "relation": "owner"},
    )


def get_task_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.get"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action=action, args=args, active_buddy=active_buddy)
    if payload_error is not None:
        return payload_error

    task_id = args.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="task_id is required")
    task_id = task_id.strip()

    task = env_store.get_task(task_id)
    if task is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"task not found: {task_id}")
    if task.get("buddy") != active_buddy:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            task_id=task_id,
            message=f"task '{task_id}' is owned by buddy '{task.get('buddy')}'",
        )

    return tool_responses.success(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Read one active-buddy task record '{task_id}'.",
        state_changed=False,
        durability="none",
        read_scope="one active-buddy task record",
        allowed_next_actions=[
            "Use artifact.create_revision to draft or publish shared artifacts.",
            "Use task.update to change title/summary/status.",
        ],
        extra={"task_id": task_id, "task": _normalize_task_summary(task), "relation": "owner"},
    )


def update_task_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.update"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action=action, args=args, active_buddy=active_buddy)
    if payload_error is not None:
        return payload_error

    task_id = args.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="task_id is required")
    task_id = task_id.strip()

    task = env_store.get_task(task_id)
    if task is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"task not found: {task_id}")
    if task.get("buddy") != active_buddy:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            task_id=task_id,
            message=f"task '{task_id}' is owned by buddy '{task.get('buddy')}'",
        )

    patch: dict[str, Any] = {}
    for field in ("title", "summary", "status", "track_id"):
        if field in args:
            patch[field] = args[field]
    if not patch:
        return _reject_payload(action=action, active_buddy=active_buddy, message="at least one patch field is required")

    if "title" in patch and (not isinstance(patch["title"], str) or not patch["title"].strip()):
        return _reject_payload(action=action, active_buddy=active_buddy, message="title must be a non-empty string")
    if "summary" in patch and not isinstance(patch["summary"], str):
        return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")
    if "status" in patch and patch["status"] not in env_store.VALID_TASK_STATUS:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"status must be one of {', '.join(env_store.VALID_TASK_STATUS)}",
        )
    if "track_id" in patch:
        track_id = patch["track_id"]
        if track_id is not None and not isinstance(track_id, str):
            return _reject_payload(action=action, active_buddy=active_buddy, message="track_id must be a string or null")
        if isinstance(track_id, str) and env_store.get_track(track_id) is None:
            return _reject_payload(action=action, active_buddy=active_buddy, message=f"track not found: {track_id}")

    try:
        updated = env_store.update_task(task_id, patch)
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_responses.success(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Updated one active-buddy task '{task_id}' and persisted patched task fields.",
        state_changed=True,
        durability="durable",
        updated_ids=[task_id],
        state_changes=[{"object_type": "task", "change": "updated_fields", "task_id": task_id}],
        allowed_next_actions=[
            "Use task.get to verify updated fields.",
            "Use artifact.create_revision to write task deliverables.",
        ],
        extra={"task_id": task_id, "task": _normalize_task_summary(updated)},
    )


def archive_task_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.archive"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action=action, args=args, active_buddy=active_buddy)
    if payload_error is not None:
        return payload_error

    task_id = args.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="task_id is required")
    task_id = task_id.strip()

    task = env_store.get_task(task_id)
    if task is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"task not found: {task_id}")
    if task.get("buddy") != active_buddy:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            task_id=task_id,
            message=f"task '{task_id}' is owned by buddy '{task.get('buddy')}'",
        )

    if task.get("status") == "archived":
        return tool_responses.success(
            tool="task",
            action=action,
            active_buddy=active_buddy,
            effect_summary=f"Task '{task_id}' is already archived.",
            state_changed=False,
            durability="none",
            state_changes=[{"object_type": "task", "change": "already_archived", "task_id": task_id}],
            allowed_next_actions=["Use task.list to inspect remaining active tasks."],
            extra={"task_id": task_id, "task": _normalize_task_summary(task)},
        )

    updated = env_store.update_task(task_id, {"status": "archived"})
    return tool_responses.success(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Archived one active-buddy task '{task_id}' in durable product state.",
        state_changed=True,
        durability="durable",
        updated_ids=[task_id],
        state_changes=[{"object_type": "task", "change": "archived", "task_id": task_id}],
        allowed_next_actions=["Use task.list to inspect remaining active tasks."],
        extra={"task_id": task_id, "task": _normalize_task_summary(updated)},
    )
