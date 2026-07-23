"""Implementation for the minimal native-Goal Task tool."""

from __future__ import annotations

import importlib
from typing import Any, Mapping

from env.tool_runtime import results as tool_results
from .tool import DEFINITION

_ACTION_ALLOWED_FIELDS = {
    action.name: set(action.input_schema.get("properties") or {})
    for action in DEFINITION.actions
}


def _current_identity(context: Any) -> dict[str, Any]:
    value = context.get("current_identity") if hasattr(context, "get") else getattr(context, "current_identity", None)
    if isinstance(value, dict):
        return value
    to_payload = getattr(value, "to_payload", None)
    if callable(to_payload):
        payload = to_payload()
        if isinstance(payload, dict):
            return payload
    return {}


def _active_role(context: Any) -> str:
    value = context.get("active_role") if hasattr(context, "get") else getattr(context, "role_id", None)
    if isinstance(value, str):
        return value
    role_id = getattr(value, "role_id", None)
    return role_id if isinstance(role_id, str) else ""


def _actor_target(context: Any) -> dict[str, str]:
    identity = _current_identity(context)
    actor_id = identity.get("id")
    role_id = _active_role(context)
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ValueError("active actor_id is required")
    if not isinstance(role_id, str) or not role_id.strip():
        raise ValueError("active role_id is required")
    return {"actor_id": actor_id.strip(), "role_id": role_id.strip()}


def _task_domain(context: Any) -> Any:
    rules = context.get("rules") if isinstance(context, dict) else getattr(context, "rules", None)
    domain = getattr(rules, "task_sys", None)
    return domain if domain is not None else importlib.import_module("env.domain.task_sys")


def _reject_unknown_fields(*, action: str, args: dict[str, Any], context: Any) -> dict[str, Any] | None:
    unknown = sorted(set(args) - _ACTION_ALLOWED_FIELDS.get(action, set()))
    if not unknown:
        return None
    message = f"unsupported payload fields: {', '.join(unknown)}"
    return tool_results.rejection(
        tool="task_sys",
        action=f"task_sys.{action}",
        current_identity=_current_identity(context),
        active_role=_active_role(context),
        code="E_TASK_SYS_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Task Sys request payload is invalid.",
        why_blocked=message,
        impact="No Task, Demand, or native Goal state was changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Retry with only the documented Task Sys fields.",
        allowed_next_actions=["Inspect the current task_sys action contract before retrying."],
        correctable_fields=unknown,
    )


def _domain_rejection(*, action: str, context: Any, exc: Exception) -> dict[str, Any]:
    code = str(getattr(exc, "code", "E_TASK_SYS_PAYLOAD"))
    extra: dict[str, Any] = {}
    task_id = getattr(exc, "task_id", None)
    if isinstance(task_id, str):
        key = "active_task_id" if code == "E_TASK_SYS_ACTIVE_CONFLICT" else "conflicting_task_id"
        extra[key] = task_id
    task_status = getattr(exc, "task_status", None)
    if isinstance(task_status, str):
        extra["active_task_status"] = task_status
    return tool_results.rejection(
        tool="task_sys",
        action=f"task_sys.{action}",
        current_identity=_current_identity(context),
        active_role=_active_role(context),
        code=code,
        message=str(exc),
        permission_boundary="task_sys.actor_owned_task",
        human_summary="Task Sys rejected the requested action.",
        why_blocked=str(exc),
        impact="No Task, Demand, or native Goal state was changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Read the active Task and current Demand before retrying.",
        allowed_next_actions=["Use task_sys.list or task_sys.get to inspect current Task state."],
        extra=extra,
    )


def _limit(args: dict[str, Any]) -> int:
    value = args.get("limit", 50)
    if type(value) is not int or value < 1:
        raise ValueError("limit must be a positive integer")
    return value


def _actor_owned_task(domain: Any, context: Any, task_id: str) -> dict[str, Any]:
    task = domain.get_task(task_id)
    if task.get("actor_target") != _actor_target(context):
        raise PermissionError("task does not belong to the active actor")
    return task


def _reconcile(context: Any, task_id: str) -> dict[str, Any]:
    access = context.get("task_goal_runtime") if isinstance(context, dict) else getattr(context, "task_goal_runtime", None)
    reconcile = getattr(access, "reconcile_task", None)
    if not callable(reconcile):
        return {
            "status": "pending",
            "task_id": task_id,
            "error_code": "task_goal_runtime_unavailable",
            "error": "Task Goal runtime reconciliation is unavailable",
        }
    try:
        result = reconcile(task_id)
    except Exception as exc:
        return {
            "status": "pending",
            "task_id": task_id,
            "error_code": str(getattr(exc, "code", "task_goal_reconcile_error")),
            "error": str(exc),
        }
    if not isinstance(result, Mapping):
        return {
            "status": "pending",
            "task_id": task_id,
            "error_code": "task_goal_runtime_protocol_error",
            "error": "Task Goal runtime returned a non-object result",
        }
    return {"status": "reconciled", "task_id": task_id, "result": dict(result)}


def _read_success(
    action: str,
    context: Any,
    *,
    effect_summary: str,
    extra: dict[str, Any],
) -> dict[str, Any]:
    return tool_results.success(
        tool="task_sys",
        action=f"task_sys.{action}",
        current_identity=_current_identity(context),
        active_role=_active_role(context),
        effect_summary=effect_summary,
        state_changed=False,
        durability="none",
        read_scope="Actor-owned Task records",
        allowed_next_actions=[
            "Use task_sys.create only when Demand orchestration selected work and no Task is active.",
            "Use task_sys.cancel only when the active Task must stop without native Goal completion.",
        ],
        extra=extra,
    )


def _write_success(
    action: str,
    context: Any,
    result: Mapping[str, Any],
    *,
    reconciliation: Mapping[str, Any],
) -> dict[str, Any]:
    task = result.get("task")
    task_row = dict(task) if isinstance(task, Mapping) else {}
    task_id = str(result.get("task_id") or "")
    demand_ref = task_row.get("demand_ref")
    actor_ref = (
        {
            "demand_id": demand_ref.get("demand_id"),
            "demand_ref": demand_ref.get("demand_ref"),
        }
        if isinstance(demand_ref, Mapping)
        else None
    )
    created = action == "create" and result.get("outcome") == "created"
    return tool_results.success(
        tool="task_sys",
        action=f"task_sys.{action}",
        current_identity=_current_identity(context),
        active_role=_active_role(context),
        effect_summary=(
            "Created Demand-bound Task and requested native Goal reconciliation."
            if created
            else "Reconciled the existing Task selection."
            if action == "create"
            else "Canceled Task and requested native Goal cleanup."
        ),
        state_changed=bool(result.get("state_changed")),
        durability="durable",
        created_ids=[task_id] if created else [],
        updated_ids=[task_id] if action == "cancel" else [],
        state_changes=[
            {
                "object": "task_sys.task",
                "id": task_id,
                "status": task_row.get("status"),
                "outcome": result.get("outcome"),
            }
        ],
        allowed_next_actions=[
            "Continue the native Goal when the Task is active.",
            "Use task_sys.get to inspect Goal binding and terminal Task result.",
        ],
        extra={
            "outcome": result.get("outcome"),
            "task_id": task_id,
            "task_status": task_row.get("status"),
            "demand_ref": actor_ref,
            "goal_binding": task_row.get("goal_binding"),
            "goal_reconciliation": dict(reconciliation),
        },
    )


def create(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    domain = _task_domain(context)
    try:
        resolved_ref = context.rules.demand_sys.resolve_demand_ref(
            actor_target=_actor_target(context),
            demand_ref=args.get("demand_ref"),
        )
        result = domain.create(
            actor_target=_actor_target(context),
            demand_ref=resolved_ref,
            objective=args.get("objective"),
            selection_reason=args.get("selection_reason"),
        )
    except (domain.TaskSysError, ValueError) as exc:
        return _domain_rejection(action="create", context=context, exc=exc)
    reconciliation = _reconcile(context, result["task_id"])
    current = domain.get_task(result["task_id"])
    return _write_success(
        "create",
        context,
        dict(result, task=current),
        reconciliation=reconciliation,
    )


def list_tasks(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    status = args.get("status") or "active"
    if status not in {"active", "terminal", "all"}:
        raise ValueError("status must be active, terminal, or all")
    projection = _task_domain(context).actor_task_projection(
        actor_profile=context.current_actor_identity_profile,
    )
    rows = (
        projection["active_tasks"]
        if status == "active"
        else projection["terminal_tasks"]
        if status == "terminal"
        else projection["tasks"]
    )
    return _read_success(
        "list",
        context,
        effect_summary="Listed Actor-owned Task records.",
        extra={
            "tasks": [dict(row) for row in rows[: _limit(args)] if isinstance(row, Mapping)],
            "active_count": projection["active_count"],
            "terminal_count": projection["terminal_count"],
        },
    )


def get(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    domain = _task_domain(context)
    task_id = str(args.get("task_id") or "")
    _actor_owned_task(domain, context, task_id)
    task = domain.actor_task_detail(task_id)
    return _read_success(
        "get",
        context,
        effect_summary="Read Actor-owned Task detail.",
        extra={"task_id": task["id"], "task": task},
    )


def cancel(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    domain = _task_domain(context)
    task_id = str(args.get("task_id") or "")
    try:
        _actor_owned_task(domain, context, task_id)
        result = domain.record_task_cancel(task_id, args.get("reason"))
    except (domain.TaskSysError, ValueError) as exc:
        return _domain_rejection(action="cancel", context=context, exc=exc)
    reconciliation = _reconcile(context, task_id)
    return _write_success("cancel", context, result, reconciliation=reconciliation)


_ACTION_HANDLERS = {
    "create": create,
    "list": list_tasks,
    "get": get,
    "cancel": cancel,
}


def invoke(*, action: str, args: dict[str, Any], context: Any) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    rejection = _reject_unknown_fields(action=action, args=args, context=context)
    if rejection is not None:
        return rejection
    return handler(args=args, context=context)
