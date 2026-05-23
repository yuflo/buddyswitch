#!/usr/bin/env python3
"""Runless task services for broker-routed env.tool operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from .tool import DEFINITION
from env.tool_runtime import results as tool_results

_ACTION_DEFINITION_MAP = {
    "actions": [
        {
            "name": row.name,
            "payload_fields": [
                field
                for field in (row.input_schema.get("properties") or {})
                if isinstance(field, str)
            ],
        }
        for row in DEFINITION.actions
    ]
}


class TaskServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _allowed_set(action: str) -> set[str]:
    _, action_name = action.split(".", 1)
    for row in _ACTION_DEFINITION_MAP.get("actions", []):
        if isinstance(row, dict) and row.get("name") == action_name:
            return {field for field in row.get("payload_fields", []) if isinstance(field, str)}
    return set()


def _task_repo_kwargs(context: TaskServiceContext) -> dict[str, Any]:
    return {
        "active_buddy": context["active_buddy"],
        "instance_json": context["instance_json"],
        "instance_payload": context["instance_payload"],
    }


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    alternative_capabilities = [
        tool_results.alternative_capability(
            tool="context",
            action="summarize",
            condition="Use when you need candidate ids before retrying a task payload.",
        ),
        tool_results.alternative_capability(
            tool="context",
            action="get",
            condition="Use when you need full tool catalog and id source details.",
        ),
    ]
    correctable_fields: list[str] | None = None
    for field in ("title", "summary", "status", "priority", "track_id", "task_id", "refs", "include_archived", "limit"):
        if field in message:
            correctable_fields = [field]
            break
    if "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            correctable_fields = [row.strip() for row in suffix.split(",") if row.strip()]
    elif "publication-style payload fields:" in message:
        suffix = message.split("publication-style payload fields:", 1)[1].strip()
        if suffix:
            correctable_fields = [row.strip() for row in suffix.split(",") if row.strip()]
    return tool_results.rejection(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        code="E_TASK_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Task request payload is invalid.",
        why_blocked=message,
        impact="No taskbox, track, or artifact state changed.",
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
    return tool_results.rejection(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        code="E_TASK_BUDDY_SCOPE",
        message=message,
        permission_boundary="task.buddy_scope",
        human_summary="Task belongs to another buddy.",
        why_blocked=message,
        impact="No taskbox state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Use a task owned by the active buddy.",
        allowed_next_actions=[
            "Use task.list to find active-buddy task ids.",
            "Use task.create to create an active-buddy task when needed.",
        ],
        correctable_fields=["task_id"],
        alternative_capabilities=[
            tool_results.alternative_capability(
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
        "owner_buddy": task.get("owner_buddy"),
        "title": task.get("title"),
        "summary": task.get("summary", ""),
        "status": task.get("status"),
        "priority": task.get("priority"),
        "track_id": task.get("track_id"),
        "refs": task.get("refs", []),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "closed_at": task.get("closed_at"),
    }


def _require_allowed_fields(
    *,
    action: str,
    args: dict[str, Any],
    active_buddy: str,
    context: TaskServiceContext,
) -> dict[str, Any] | None:
    publication_fields = context.rules.task.publication_style_fields(args)
    if publication_fields:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"publication-style payload fields: {', '.join(publication_fields)}",
        )
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
    payload_error = _require_allowed_fields(action=action, args=args, active_buddy=active_buddy, context=context)
    if payload_error is not None:
        return payload_error

    try:
        payload = context.rules.task.create_payload(args)
    except context.rules.task.TaskPayloadError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    try:
        task = context.repos.task.create_task(**payload, **_task_repo_kwargs(context))
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_results.success(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Created one instance-local taskbox task '{task['id']}'.",
        state_changed=True,
        durability="durable",
        created_ids=[task["id"]],
        state_changes=[{"object_type": "task", "change": "created", "task_id": task["id"]}],
        allowed_next_actions=[
            "Use task.update to refine task status, priority, or refs.",
            "Use task.history to inspect lifecycle lines.",
        ],
        extra={"task_id": task["id"], "task": _normalize_task_summary(task)},
    )


def list_tasks_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.list"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action=action, args=args, active_buddy=active_buddy, context=context)
    if payload_error is not None:
        return payload_error

    try:
        status = context.rules.task.optional_status_filter(args.get("status"))
        priority = context.rules.task.optional_priority_filter(args.get("priority"))
        track_id = context.rules.task.optional_track_filter(args.get("track_id"))
        include_archived = context.rules.task.include_archived_flag(args.get("include_archived"))
        limit = context.rules.task.normalize_limit(args.get("limit"))
    except context.rules.task.TaskPayloadError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    rows = context.repos.task.list_tasks(
        include_archived=include_archived,
        **_task_repo_kwargs(context),
    )
    if status is not None:
        rows = [row for row in rows if row.get("status") == status]
    if priority is not None:
        rows = [row for row in rows if row.get("priority") == priority]
    if track_id is not None:
        rows = [row for row in rows if row.get("track_id") == track_id]
    payload_rows = [_normalize_task_summary(row) for row in rows[:limit]]

    return tool_results.success(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Returned {len(payload_rows)} active-buddy taskbox row(s).",
        state_changed=False,
        durability="none",
        read_scope="instance-local active-buddy taskbox summaries",
        allowed_next_actions=[
            "Use task.get with task_id for one task detail.",
            "Use task.history for lifecycle history.",
        ],
        extra={"tasks": payload_rows, "relation": "owner"},
    )


def get_task_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.get"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action=action, args=args, active_buddy=active_buddy, context=context)
    if payload_error is not None:
        return payload_error

    try:
        task_id = context.rules.task.require_task_id(args.get("task_id"))
    except context.rules.task.TaskPayloadError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    task = context.repos.task.get_task(task_id, **_task_repo_kwargs(context))
    if task is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"task not found: {task_id}")
    try:
        context.rules.task.ensure_active_buddy_ownership(task=task, task_id=task_id, active_buddy=active_buddy)
    except context.rules.task.TaskScopeError as exc:
        return _reject_scope(action=action, active_buddy=active_buddy, task_id=task_id, message=str(exc))

    return tool_results.success(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Read one instance-local taskbox task '{task_id}'.",
        state_changed=False,
        durability="none",
        read_scope="one instance-local active-buddy taskbox task",
        allowed_next_actions=[
            "Use task.update to change task fields or lifecycle state.",
            "Use task.history to inspect lifecycle lines.",
        ],
        extra={"task_id": task_id, "task": _normalize_task_summary(task), "relation": "owner"},
    )


def update_task_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.update"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action=action, args=args, active_buddy=active_buddy, context=context)
    if payload_error is not None:
        return payload_error

    try:
        task_id = context.rules.task.require_task_id(args.get("task_id"))
        patch = context.rules.task.update_patch(args)
    except context.rules.task.TaskPayloadError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    task = context.repos.task.get_task(task_id, **_task_repo_kwargs(context))
    if task is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"task not found: {task_id}")
    try:
        context.rules.task.ensure_active_buddy_ownership(task=task, task_id=task_id, active_buddy=active_buddy)
    except context.rules.task.TaskScopeError as exc:
        return _reject_scope(action=action, active_buddy=active_buddy, task_id=task_id, message=str(exc))

    try:
        updated, changed, event = context.repos.task.update_task(task_id, patch, **_task_repo_kwargs(context))
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_results.success(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        effect_summary=(
            f"Updated one instance-local taskbox task '{task_id}'."
            if changed
            else f"Task '{task_id}' already matched the requested fields."
        ),
        state_changed=changed,
        durability="durable" if changed else "none",
        updated_ids=[task_id] if changed else [],
        state_changes=[{"object_type": "task", "change": event or "unchanged", "task_id": task_id}],
        allowed_next_actions=[
            "Use task.get to verify current task state.",
            "Use task.history to inspect lifecycle lines.",
        ],
        extra={"task_id": task_id, "task": _normalize_task_summary(updated)},
    )


def archive_task_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.archive"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action=action, args=args, active_buddy=active_buddy, context=context)
    if payload_error is not None:
        return payload_error

    try:
        task_id = context.rules.task.require_task_id(args.get("task_id"))
    except context.rules.task.TaskPayloadError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    task = context.repos.task.get_task(task_id, **_task_repo_kwargs(context))
    if task is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"task not found: {task_id}")
    try:
        context.rules.task.ensure_active_buddy_ownership(task=task, task_id=task_id, active_buddy=active_buddy)
    except context.rules.task.TaskScopeError as exc:
        return _reject_scope(action=action, active_buddy=active_buddy, task_id=task_id, message=str(exc))

    if task.get("status") == "archived":
        return tool_results.success(
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

    updated, changed, _event = context.repos.task.update_task(
        task_id,
        {"status": "archived"},
        **_task_repo_kwargs(context),
    )
    return tool_results.success(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Archived one instance-local taskbox task '{task_id}'.",
        state_changed=changed,
        durability="durable" if changed else "none",
        updated_ids=[task_id] if changed else [],
        state_changes=[{"object_type": "task", "change": "archived", "task_id": task_id}],
        allowed_next_actions=["Use task.list to inspect remaining active tasks."],
        extra={"task_id": task_id, "task": _normalize_task_summary(updated)},
    )


def history_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.history"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action=action, args=args, active_buddy=active_buddy, context=context)
    if payload_error is not None:
        return payload_error

    try:
        limit = context.rules.task.history_limit(args)
    except context.rules.task.TaskPayloadError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    entries = context.repos.task.read_history(limit=limit, **_task_repo_kwargs(context))
    return tool_results.success(
        tool="task",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Returned {len(entries)} taskbox history entrie(s).",
        state_changed=False,
        durability="none",
        read_scope="instance-local taskbox history",
        allowed_next_actions=[
            "Use task.list to inspect current task rows.",
            "Use task.get with task_id for one task detail.",
        ],
        extra={"entries": entries},
    )


_ACTION_HANDLERS = {
    "archive": archive_task_for_active_buddy,
    "create": create_task_for_active_buddy,
    "get": get_task_for_active_buddy,
    "history": history_for_active_buddy,
    "list": list_tasks_for_active_buddy,
    "update": update_task_for_active_buddy,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    return handler(args=args, context=context)
