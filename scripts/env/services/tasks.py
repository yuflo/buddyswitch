#!/usr/bin/env python3
"""Active-buddy scoped task env tool service for broker-routed env.tool operations."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, TypedDict

import env_store
from env_manifest import buddy_permissions
from env.services import bindings as binding_service
from env.services import track_relations
from env.tools import responses as tool_responses

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
_TASK_STATUSES = set(env_store.VALID_TASK_STATUS)
_UPDATE_FIELDS = {"title", "summary", "status"}
_CREATE_ALLOWED_FIELDS = {"title", "summary", "task_id", "buddy", "active_buddy"}
_GET_ALLOWED_FIELDS = {"task_id"}
_SET_CURRENT_ALLOWED_FIELDS = {"task_id"}
_ARCHIVE_ALLOWED_FIELDS = {"task_id"}
_READ_PERMISSION = "task.read"
_CREATE_PERMISSION = "task.create"
_UPDATE_PERMISSION = "task.update"
_ARCHIVE_PERMISSION = "task.archive"


class TaskServiceContext(TypedDict):
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
    impact: str = "No task records or instance binding state were changed.",
    retryable: bool = True,
    retry_guidance: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    payload = tool_responses.rejection(
        tool="task",
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
        retry_guidance=retry_guidance or "Fix payload or state preconditions, then retry the action.",
        allowed_next_actions=allowed_next_actions,
    )
    if isinstance(task_id, str) and task_id.strip():
        payload["task_id"] = task_id.strip()
    return payload


def _success_payload(
    *,
    action: str,
    context: TaskServiceContext,
    effect_summary: str,
    state_changed: bool,
    durability: str,
    allowed_next_actions: list[str],
    state_changes: list[dict[str, Any]] | None = None,
    created_ids: list[str] | None = None,
    updated_ids: list[str] | None = None,
    binding_changed: bool | None = None,
    read_scope: str | None = None,
    validation_only: bool | None = None,
    follow_up_affordances: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return tool_responses.success(
        tool="task",
        action=action,
        active_buddy=context["active_buddy"],
        effect_summary=effect_summary,
        state_changed=state_changed,
        durability=durability,
        allowed_next_actions=allowed_next_actions,
        state_changes=state_changes,
        created_ids=created_ids,
        updated_ids=updated_ids,
        binding_changed=binding_changed,
        read_scope=read_scope,
        validation_only=validation_only,
        follow_up_affordances=follow_up_affordances,
        extra=extra,
    )


def _permission_error(*, action: str, active_buddy: str, permission: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TASK_PERMISSION",
        message=f"active buddy '{active_buddy}' is missing required permission '{permission}'",
        permission_boundary="manifest.permission",
        human_summary="Active buddy cannot use this task action.",
        why_blocked=f"The active buddy is missing required permission '{permission}'.",
        retryable=False,
        retry_guidance="Switch to a buddy that owns this permission, or use an allowed action for the current buddy.",
        allowed_next_actions=[
            "Use only task actions allowed by the active buddy manifest permissions.",
            "Switch to a buddy that owns this task action before retrying.",
        ],
    )


def _payload_error(*, action: str, active_buddy: str, message: str, task_id: str | None = None) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TASK_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Task request payload is invalid.",
        why_blocked=message,
        retryable=True,
        retry_guidance="Fix the payload fields for this action and retry.",
        task_id=task_id,
        allowed_next_actions=[
            'Fix the env.tool envelope fields (`tool`, `action`, `args`) and retry.',
            "Use task.list to inspect candidate task ids before retrying.",
        ],
    )


def _scope_error(*, action: str, active_buddy: str, task_id: str, task_buddy: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TASK_BUDDY_SCOPE",
        message=f"task belongs to buddy '{task_buddy}', not active buddy '{active_buddy}'",
        permission_boundary="task.buddy_scope",
        human_summary="Task belongs to another buddy.",
        why_blocked="Only the owning buddy can mutate or bind this task directly.",
        retryable=False,
        retry_guidance="Choose a task owned by the active buddy or continue through track/handoff collaboration paths.",
        task_id=task_id,
        allowed_next_actions=[
            "Choose a task owned by the active buddy.",
            "List active-buddy tasks before changing the current task.",
            "Use handoff or track context instead of cross-buddy task mutation.",
        ],
    )


def _lookup_error(*, action: str, active_buddy: str, task_id: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TASK_NOT_FOUND",
        message=f"task not found: {task_id}",
        permission_boundary="task.lookup",
        human_summary="Requested task id was not found.",
        why_blocked=f"task_id '{task_id}' does not reference an existing task record.",
        retryable=True,
        retry_guidance="List candidate tasks or create a new task, then retry with a valid task_id.",
        task_id=task_id,
        allowed_next_actions=[
            "Use task.list to get active-buddy task ids.",
            "Create a new task when no active-buddy task matches.",
        ],
    )


def _relation_error(
    *,
    action: str,
    active_buddy: str,
    task_id: str,
    relation: str,
    track_id: str | None,
) -> dict[str, Any]:
    payload = _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TASK_TRACK_RELATION",
        message=f"active buddy '{active_buddy}' cannot read task '{task_id}' without a readable track relation",
        permission_boundary="task.track_relation",
        human_summary="Task read is blocked by missing collaboration relation.",
        why_blocked="The active buddy is neither the owner nor a readable participant on the task track.",
        retryable=True,
        retry_guidance="Inspect track relation and join the track before retrying task read.",
        task_id=task_id,
        allowed_next_actions=[
            "Use track.list and track.get to inspect related tracks first.",
            "Use track.join to establish active-buddy task linkage on the track.",
        ],
    )
    payload.update(
        {
            "relation": relation,
            "track_id": track_id,
            "missing_preconditions": [
                "task must be owned by active buddy or linked to a track readable by active buddy",
            ],
            "next_actions": [
                {"tool": "track", "action": "list"},
                {"tool": "track", "action": "join", "args": {"track_id": track_id}},
            ],
            "command_hint": track_relations.command_hint("track", "list"),
            "no_content_leak": True,
        }
    )
    return payload


def _task_summary(task: dict[str, Any], *, active_buddy: str | None = None) -> dict[str, Any]:
    summary = {field: task.get(field) for field in _TASK_PUBLIC_FIELDS}
    viewer = active_buddy if isinstance(active_buddy, str) and active_buddy else str(task.get("buddy") or "")
    artifact_slots = task.get("artifact_slots")
    current_artifact_ids: list[str] = []
    current_artifacts: list[dict[str, Any]] = []
    if isinstance(artifact_slots, dict):
        for slot in artifact_slots.values():
            if not isinstance(slot, dict):
                continue
            artifact_id = slot.get("current_artifact_id")
            if not isinstance(artifact_id, str) or not artifact_id:
                continue
            current_artifact_ids.append(artifact_id)
            artifact = env_store.get_artifact(artifact_id)
            if isinstance(artifact, dict):
                current_artifacts.append(
                    track_relations.artifact_summary_row(
                        artifact,
                        viewer,
                        task=task,
                    )
                )
    summary["owner_buddy"] = task.get("buddy")
    summary["current_artifact_ids"] = current_artifact_ids
    summary["current_artifacts"] = current_artifacts
    summary["is_current_work"] = bool(task.get("status") == "active")
    return summary


def _task_read_decision(task: dict[str, Any], active_buddy: str) -> dict[str, Any]:
    if task.get("buddy") == active_buddy:
        return {"allowed": True, "relation": "owner", "track_id": task.get("track_id")}
    track_id = task.get("track_id")
    if not isinstance(track_id, str) or not track_id:
        return {"allowed": False, "relation": "none", "track_id": None}
    track = env_store.get_track(track_id)
    if not isinstance(track, dict):
        return {"allowed": False, "relation": "none", "track_id": track_id}
    if track.get("status") == "archived":
        return {"allowed": False, "relation": "archived", "track_id": track_id}
    relation = track_relations.track_relation_for_buddy(track, active_buddy).get("relation")
    if relation == "none":
        return {"allowed": False, "relation": "none", "track_id": track_id}
    return {"allowed": True, "relation": relation, "track_id": track_id}


def _current_binding(context: TaskServiceContext) -> dict[str, Any]:
    return binding_service.current_binding(context)


def _require_permission(context: TaskServiceContext, permission: str, action: str) -> dict[str, Any] | None:
    permissions = buddy_permissions(context["manifest"], context["active_buddy"])
    if permission in permissions:
        return None
    return _permission_error(action=action, active_buddy=context["active_buddy"], permission=permission)


def _normalize_task_id(value: Any) -> tuple[str | None, dict[str, Any] | None]:
    if not isinstance(value, str) or not value.strip():
        return None, None
    candidate = value.strip()
    try:
        env_store.require_id(candidate, "task id")
    except ValueError as exc:
        return None, {"message": str(exc)}
    return candidate, None


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


def _owned_task(
    *,
    context: TaskServiceContext,
    action: str,
    args: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    task_id, parse_error = _normalize_task_id(args.get("task_id"))
    if parse_error is not None:
        return None, _payload_error(
            action=action,
            active_buddy=context["active_buddy"],
            message=parse_error["message"],
        )
    if task_id is None:
        return None, _payload_error(
            action=action,
            active_buddy=context["active_buddy"],
            message="task_id is required",
        )

    task = env_store.get_task(task_id)
    if task is None:
        return None, _lookup_error(action=action, active_buddy=context["active_buddy"], task_id=task_id)
    task_buddy = task.get("buddy")
    if not isinstance(task_buddy, str) or task_buddy != context["active_buddy"]:
        return None, _scope_error(
            action=action,
            active_buddy=context["active_buddy"],
            task_id=task_id,
            task_buddy=str(task_buddy or ""),
        )
    return task, None


def _next_task_id(*, active_buddy: str, title: str) -> str:
    seed = env_store.slugify(title)
    while True:
        candidate = f"task-{active_buddy}-{seed}-{uuid.uuid4().hex[:8]}"
        if env_store.get_task(candidate) is None:
            return candidate


def create_task_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.create"
    permission_error = _require_permission(context, _CREATE_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_CREATE_ALLOWED_FIELDS,
    )
    if fields_error is not None:
        return fields_error

    title = args.get("title")
    if not isinstance(title, str) or not title.strip():
        return _payload_error(action=action, active_buddy=context["active_buddy"], message="title is required")

    summary = args.get("summary", "")
    if summary is None:
        summary = ""
    if not isinstance(summary, str):
        return _payload_error(action=action, active_buddy=context["active_buddy"], message="summary must be a string")

    explicit_task_id = args.get("task_id")
    if explicit_task_id is None:
        task_id = _next_task_id(active_buddy=context["active_buddy"], title=title.strip())
    else:
        task_id, parse_error = _normalize_task_id(explicit_task_id)
        if parse_error is not None:
            return _payload_error(action=action, active_buddy=context["active_buddy"], message=parse_error["message"])
        if not isinstance(task_id, str):
            return _payload_error(
                action=action,
                active_buddy=context["active_buddy"],
                message="task_id must be a non-empty string when provided",
            )
        if env_store.get_task(task_id) is not None:
            return _payload_error(
                action=action,
                active_buddy=context["active_buddy"],
                message=f"task already exists: {task_id}",
                task_id=task_id,
            )

    task = env_store.create_task(
        task_id,
        title.strip(),
        buddy=context["active_buddy"],
        status="active",
        summary=summary,
        initial_run_id=None,
    )
    return _success_payload(
        action=action,
        context=context,
        effect_summary=f"Created task '{task['id']}' for the active buddy.",
        state_changed=True,
        durability="runtime_object",
        state_changes=[{"object_type": "task", "object_id": task["id"], "change": "created"}],
        created_ids=[str(task["id"])],
        allowed_next_actions=[
            "Use task.update to change title, summary, or status.",
            "Use task.set_current to bind this task to the active instance.",
        ],
        extra={
            "task_id": task["id"],
            "task": _task_summary(task),
            "current_binding": _current_binding(context),
        },
    )


def list_tasks_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.list"
    permission_error = _require_permission(context, _READ_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    if args:
        fields_error = _ensure_allowed_fields(
            action=action,
            active_buddy=context["active_buddy"],
            args=args,
            allowed_fields=set(),
        )
        if fields_error is not None:
            return fields_error

    task_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for task in env_store.list_tasks():
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            continue
        decision = _task_read_decision(task, context["active_buddy"])
        if not bool(decision.get("allowed")):
            continue
        if task_id in seen:
            continue
        seen.add(task_id)
        row = _task_summary(task, active_buddy=context["active_buddy"])
        row["relation"] = decision.get("relation")
        task_rows.append(row)
    task_rows.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("id") or "")), reverse=True)
    return _success_payload(
        action=action,
        context=context,
        effect_summary=f"Listed {len(task_rows)} readable task summaries for active buddy '{context['active_buddy']}'.",
        state_changed=False,
        durability="none",
        read_scope="Active-buddy task summaries and relation-readable task rows; no full artifact bodies were read.",
        allowed_next_actions=[
            "Use task.get with a returned task_id to inspect one task.",
            "Use artifact.get with task artifact ids for full content reads.",
        ],
        extra={
            "tasks": task_rows,
            "current_binding": _current_binding(context),
            "next_actions": [
                {"tool": "task", "action": "get", "args": {"task_id": "<task-id>"}},
                {"tool": "artifact", "action": "get", "args": {"artifact_id": "<artifact-id>"}},
            ],
            "command_hint": track_relations.command_hint("task", "get", {"task_id": "<task-id>"}),
        },
    )


def get_task_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.get"
    permission_error = _require_permission(context, _READ_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_GET_ALLOWED_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    task_id, parse_error = _normalize_task_id(args.get("task_id"))
    if parse_error is not None:
        return _payload_error(action=action, active_buddy=context["active_buddy"], message=parse_error["message"])
    if task_id is None:
        return _payload_error(action=action, active_buddy=context["active_buddy"], message="task_id is required")
    task = env_store.get_task(task_id)
    if task is None:
        return _lookup_error(action=action, active_buddy=context["active_buddy"], task_id=task_id)
    decision = _task_read_decision(task, context["active_buddy"])
    if not bool(decision.get("allowed")):
        return _relation_error(
            action=action,
            active_buddy=context["active_buddy"],
            task_id=task_id,
            relation=str(decision.get("relation") or "none"),
            track_id=decision.get("track_id") if isinstance(decision.get("track_id"), str) else None,
        )
    summary = _task_summary(task, active_buddy=context["active_buddy"])
    summary["relation"] = decision.get("relation")
    return _success_payload(
        action=action,
        context=context,
        effect_summary=f"Read task '{task['id']}' summary for active buddy decision use.",
        state_changed=False,
        durability="none",
        read_scope="Task summary plus relation context; full artifact bodies remain behind artifact.get.",
        allowed_next_actions=[
            "Use artifact.get with returned artifact ids for full body reads.",
            "Use task.set_current only when selecting active-buddy owned work.",
        ],
        extra={
            "task_id": task["id"],
            "task": summary,
            "relation": decision.get("relation"),
            "current_binding": _current_binding(context),
            "next_actions": [
                {"tool": "artifact", "action": "get", "args": {"artifact_id": "<artifact-id>"}},
            ],
            "command_hint": track_relations.command_hint("artifact", "get", {"artifact_id": "<artifact-id>"}),
        },
    )


def get_current_task(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.get_current"
    permission_error = _require_permission(context, _READ_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    if args:
        fields_error = _ensure_allowed_fields(
            action=action,
            active_buddy=context["active_buddy"],
            args=args,
            allowed_fields=set(),
        )
        if fields_error is not None:
            return fields_error

    binding = _current_binding(context)
    task_id = binding.get("current_task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        return _success_payload(
            action=action,
            context=context,
            effect_summary="No current task binding exists for the active instance.",
            state_changed=False,
            durability="none",
            read_scope="Instance binding only; no task object was read because current_task_id is empty.",
            allowed_next_actions=[
                "Use task.list to inspect active-buddy tasks.",
                "Use task.set_current with an active-buddy task_id.",
            ],
            extra={
                "task": None,
                "current_binding": binding,
            },
        )

    task = env_store.get_task(task_id.strip())
    if task is None:
        return _lookup_error(action=action, active_buddy=context["active_buddy"], task_id=task_id.strip())
    task_buddy = task.get("buddy")
    if not isinstance(task_buddy, str) or task_buddy != context["active_buddy"]:
        return _scope_error(
            action=action,
            active_buddy=context["active_buddy"],
            task_id=task_id.strip(),
            task_buddy=str(task_buddy or ""),
        )
    return _success_payload(
        action=action,
        context=context,
        effect_summary=f"Read current bound task '{task['id']}' from active instance binding.",
        state_changed=False,
        durability="none",
        read_scope="Current instance task binding and owned task summary.",
        allowed_next_actions=[
            "Use task.update to adjust this task status or summary.",
            "Use task.set_current to switch to another active-buddy task.",
        ],
        extra={
            "task_id": task["id"],
            "task": _task_summary(task),
            "current_binding": binding,
        },
    )


def set_current_task(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.set_current"
    permission_error = _require_permission(context, _UPDATE_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_SET_CURRENT_ALLOWED_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    task, error = _owned_task(context=context, action=action, args=args)
    if error is not None:
        return error
    assert task is not None

    task_id = str(task["id"])
    track_id = task.get("track_id")
    normalized_track_id = track_id if isinstance(track_id, str) and track_id.strip() else None
    binding_service.write_instance_binding(
        context=context,
        task_id=task_id,
        track_id=normalized_track_id,
    )

    return _success_payload(
        action=action,
        context=context,
        effect_summary=f"Set current instance task binding to '{task_id}'.",
        state_changed=True,
        durability="instance_binding",
        state_changes=[
            {
                "object_type": "instance_binding",
                "object_id": context["instance_id"],
                "change": "current_task_id/current_track_id updated",
            }
        ],
        binding_changed=True,
        allowed_next_actions=[
            "Use task.get_current to confirm active instance binding.",
            "Continue task work using the current binding context.",
        ],
        extra={
            "task_id": task_id,
            "task": _task_summary(task),
            "current_binding": _current_binding(context),
        },
    )


def update_task_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.update"
    permission_error = _require_permission(context, _UPDATE_PERMISSION, action)
    if permission_error is not None:
        return permission_error

    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_UPDATE_FIELDS | {"task_id"},
    )
    if fields_error is not None:
        return fields_error
    task, error = _owned_task(context=context, action=action, args=args)
    if error is not None:
        return error
    assert task is not None

    patch: dict[str, Any] = {}
    if "title" in args:
        title = args.get("title")
        if not isinstance(title, str) or not title.strip():
            return _payload_error(
                action=action,
                active_buddy=context["active_buddy"],
                message="title must be a non-empty string when provided",
                task_id=task["id"],
            )
        patch["title"] = title.strip()
    if "summary" in args:
        summary = args.get("summary")
        if summary is None:
            summary = ""
        if not isinstance(summary, str):
            return _payload_error(
                action=action,
                active_buddy=context["active_buddy"],
                message="summary must be a string when provided",
                task_id=task["id"],
            )
        patch["summary"] = summary
    if "status" in args:
        status = args.get("status")
        if not isinstance(status, str) or status not in _TASK_STATUSES:
            return _payload_error(
                action=action,
                active_buddy=context["active_buddy"],
                message=f"status must be one of {', '.join(sorted(_TASK_STATUSES))}",
                task_id=task["id"],
            )
        patch["status"] = status
    if not patch:
        return _payload_error(
            action=action,
            active_buddy=context["active_buddy"],
            message="update requires at least one of title, summary, or status",
            task_id=task["id"],
        )

    updated = env_store.update_task(task["id"], patch)
    return _success_payload(
        action=action,
        context=context,
        effect_summary=f"Updated task '{updated['id']}' fields: {', '.join(sorted(patch.keys()))}.",
        state_changed=True,
        durability="runtime_object",
        state_changes=[{"object_type": "task", "object_id": updated["id"], "change": "updated"}],
        updated_ids=[str(updated["id"])],
        allowed_next_actions=[
            "Use task.get to confirm the persisted task fields.",
            "Use task.archive when this task should be closed without deletion.",
        ],
        extra={
            "task_id": updated["id"],
            "task": _task_summary(updated),
            "current_binding": _current_binding(context),
        },
    )


def archive_task_for_active_buddy(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.archive"
    permission_error = _require_permission(context, _ARCHIVE_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_ARCHIVE_ALLOWED_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    task, error = _owned_task(context=context, action=action, args=args)
    if error is not None:
        return error
    assert task is not None
    archived = env_store.update_task(task["id"], {"status": "archived"})
    return _success_payload(
        action=action,
        context=context,
        effect_summary=f"Archived task '{archived['id']}' by status update; task was not deleted.",
        state_changed=True,
        durability="runtime_object",
        state_changes=[{"object_type": "task", "object_id": archived["id"], "change": "status set to archived"}],
        updated_ids=[str(archived["id"])],
        allowed_next_actions=[
            "Use task.get to inspect archived task context.",
            "Use task.list to continue with another active-buddy task.",
        ],
        extra={
            "task_id": archived["id"],
            "task": _task_summary(archived),
            "current_binding": _current_binding(context),
        },
    )
