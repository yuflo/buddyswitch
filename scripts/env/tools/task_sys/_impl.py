"""Implementation for the Task Sys env tool."""

from __future__ import annotations

import importlib
from typing import Any, Mapping

from env.tool_runtime import results as tool_results
from .tool import DEFINITION


_ACTION_ALLOWED_FIELDS = {
    row.name: {
        field
        for field in (row.input_schema.get("properties") or {})
        if isinstance(field, str)
    }
    for row in DEFINITION.actions
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
    active_actor = context.get("active_actor") if hasattr(context, "get") else getattr(context, "active_actor", None)
    if isinstance(active_actor, dict):
        actor_id = active_actor.get("actor_id")
        if isinstance(actor_id, str) and actor_id.strip():
            return {"id": actor_id.strip(), "type": "actor"}
        identity_id = active_actor.get("id")
        identity_type = active_actor.get("type")
        if isinstance(identity_id, str) and identity_id.strip() and isinstance(identity_type, str) and identity_type.strip():
            return {"id": identity_id.strip(), "type": identity_type.strip()}
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


def _task_sys_domain(context: Any) -> Any:
    rules = context.get("rules") if isinstance(context, dict) else getattr(context, "rules", None)
    domain = getattr(rules, "task_sys", None)
    if domain is not None:
        return domain
    return importlib.import_module("env.domain.task_sys")


def _reject_unknown_payload_fields(*, action: str, args: dict[str, Any], context: Any) -> dict[str, Any] | None:
    allowed = _ACTION_ALLOWED_FIELDS.get(action, set())
    unknown = sorted(field for field in args if field not in allowed)
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
        impact="No task sys state was changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Retry with only documented task_sys payload fields.",
        allowed_next_actions=[
            "Use task_sys.list, task_sys.get, task_sys.update_task_analysis, task_sys.close, or task_sys.need_parent with documented payload fields.",
        ],
        correctable_fields=unknown,
    )


def _task_events(task: Mapping[str, Any]) -> list[dict[str, Any]]:
    events = task.get("events")
    if not isinstance(events, list):
        return []
    return [dict(row) for row in events if isinstance(row, Mapping)]


def _read_success(action: str, context: Any, *, effect_summary: str, extra: dict[str, Any]) -> dict[str, Any]:
    return tool_results.success(
        tool="task_sys",
        action=f"task_sys.{action}",
        current_identity=_current_identity(context),
        active_role=_active_role(context),
        effect_summary=effect_summary,
        state_changed=False,
        durability="none",
        read_scope="actor-owned task sys task records",
        allowed_next_actions=[
            "Use task_sys.get for full task detail.",
            "Use task_sys.update_task_analysis to record task_desc and task_relation before a side final action.",
            "Use task_sys.close when the active frame completed the required task work.",
            "Use task_sys.need_parent when side processing requires parent work.",
        ],
        extra=extra,
    )


def _success(
    action: str,
    result: dict[str, Any],
    context: Any,
    *,
    parent_instruction: dict[str, Any] | None = None,
    parent_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task = result.get("task") if isinstance(result.get("task"), dict) else {}
    execution = task.get("execution") if isinstance(task, dict) else None
    execution_row = dict(execution) if isinstance(execution, dict) else {}
    execution_result = execution_row.get("result")
    execution_handoff = execution_row.get("handoff")
    extra: dict[str, Any] = {
        "task_id": result.get("task_id"),
        "outcome": result.get("outcome"),
        "task_status": task.get("status"),
        "task_desc": task.get("task_desc"),
        "task_relation": dict(task.get("task_relation")) if isinstance(task.get("task_relation"), dict) else None,
        "execution": execution_row,
    }
    if isinstance(execution_handoff, dict):
        extra["execution_handoff"] = execution_handoff
        if action == "need_parent":
            extra["processor"] = "side"
        side_thread_id = execution_handoff.get("side_thread_id")
        if isinstance(side_thread_id, str) and side_thread_id.strip():
            extra["side_thread_id"] = side_thread_id.strip()
        cleanup = execution_handoff.get("cleanup")
        if isinstance(cleanup, dict):
            extra["side_cleanup"] = cleanup
    if isinstance(execution_result, dict):
        extra["execution_result"] = execution_result
        processor = execution_result.get("processor")
        if isinstance(processor, str) and processor.strip():
            extra["processor"] = processor.strip()
        side_thread_id = execution_result.get("side_thread_id")
        if isinstance(side_thread_id, str) and side_thread_id.strip():
            extra["side_thread_id"] = side_thread_id.strip()
        cleanup = execution_result.get("cleanup")
        if isinstance(cleanup, dict):
            extra["side_cleanup"] = cleanup
    if isinstance(parent_instruction, dict):
        extra["parent_instruction"] = parent_instruction
    if isinstance(parent_runtime, dict):
        extra["parent_runtime"] = parent_runtime
    if action == "close":
        effect_summary = "Closed Task Sys task."
    elif action == "need_parent":
        effect_summary = "Recorded Task Sys parent handoff."
    elif action == "update_task_analysis":
        effect_summary = "Updated Task Sys task analysis."
    else:
        effect_summary = f"Recorded Task Sys action: {result.get('outcome')}."
    return tool_results.success(
        tool="task_sys",
        action=f"task_sys.{action}",
        current_identity=_current_identity(context),
        active_role=_active_role(context),
        effect_summary=effect_summary,
        state_changed=bool(result.get("state_changed", True)),
        durability="durable",
        updated_ids=[str(result.get("task_id"))],
        state_changes=[
            {
                "object": "task_sys.task",
                "id": result.get("task_id"),
                "status": task.get("status"),
                "outcome": result.get("outcome"),
            }
        ],
        allowed_next_actions=["Use returned task_status, task_desc, task_relation, execution, processor, and cleanup fields to decide the next frame action."],
        extra=extra,
    )


def _execute_parent_instruction(context: Any, instruction: dict[str, Any]) -> dict[str, Any]:
    runtime_access = context.get("task_sys_runtime") if isinstance(context, dict) else None
    if runtime_access is None:
        runtime_access = getattr(context, "task_sys_runtime", None)
    execute = getattr(runtime_access, "execute_instruction", None)
    if not callable(execute):
        raise RuntimeError("Task Sys parent runtime execution is unavailable")
    result = execute(instruction)
    if not isinstance(result, dict):
        raise RuntimeError("Task Sys parent runtime execution returned a non-object result")
    return result


def _cleanup_side_lease(context: Any, task_id: str) -> dict[str, Any]:
    runtime_access = context.get("task_sys_runtime") if isinstance(context, dict) else None
    if runtime_access is None:
        runtime_access = getattr(context, "task_sys_runtime", None)
    cleanup = getattr(runtime_access, "cleanup_side_lease", None)
    if not callable(cleanup):
        return {
            "side_thread_id": None,
            "turn_interrupt_attempted": False,
            "turn_interrupt_ok": False,
            "turn_interrupt_error": "Task Sys side cleanup is unavailable",
            "lease_unregistered": False,
        }
    result = cleanup(task_id)
    if not isinstance(result, dict):
        return {
            "side_thread_id": None,
            "turn_interrupt_attempted": False,
            "turn_interrupt_ok": False,
            "turn_interrupt_error": "Task Sys side cleanup returned a non-object result",
            "lease_unregistered": False,
        }
    return result


def _record_side_cleanup(task_sys: Any, context: Any, task_id: str) -> dict[str, Any]:
    cleanup = _cleanup_side_lease(context, task_id)
    side_thread_id = cleanup.get("side_thread_id")
    if not isinstance(side_thread_id, str) or not side_thread_id.strip():
        side_thread_id = "unknown-side-thread"
    return task_sys.record_side_cleanup(
        task_id,
        {
            "side_thread_id": side_thread_id,
            "cleanup": cleanup,
        },
    )


def _limit(args: dict[str, Any]) -> int:
    raw = args.get("limit", 50)
    if not isinstance(raw, int) or raw < 1:
        raise ValueError("limit must be a positive integer")
    return raw


def list_tasks(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    task_sys = _task_sys_domain(context)
    status = args.get("status") or "active"
    if status not in {"active", "recoverable", "all"}:
        raise ValueError("status must be active, recoverable, or all")

    projection = task_sys.actor_task_projection(
        actor_profile=context.current_actor_identity_profile,
    )
    if status == "active":
        rows = projection["active_tasks"]
    elif status == "recoverable":
        rows = projection["recoverable_tasks"]
    else:
        rows = projection["tasks"]

    limited = rows[: _limit(args)]
    return _read_success(
        "list",
        context,
        effect_summary="Listed actor-owned Task Sys tasks.",
        extra={
            "tasks": [dict(row) for row in limited if isinstance(row, Mapping)],
            "active_count": projection["active_count"],
            "recoverable_count": projection["recoverable_count"],
        },
    )


def get(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    task_sys = _task_sys_domain(context)
    actor_target = _actor_target(context)
    task_id = str(args.get("task_id") or "")
    task = task_sys.get_task(task_id)
    owner = task.get("actor_target")
    if not isinstance(owner, Mapping) or owner.get("actor_id") != actor_target["actor_id"] or owner.get("role_id") != actor_target["role_id"]:
        raise PermissionError("task does not belong to the active actor")
    events = _task_events(task)
    return _read_success(
        "get",
        context,
        effect_summary="Read actor-owned Task Sys task detail.",
        extra={
            "task_id": task.get("id"),
            "task": dict(task),
            "events": events,
        },
    )


def update_task_analysis(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    task_sys = _task_sys_domain(context)
    actor_target = _actor_target(context)
    task_id = str(args.get("task_id") or "")
    task = task_sys.get_task(task_id)
    owner = task.get("actor_target")
    if not isinstance(owner, Mapping) or owner.get("actor_id") != actor_target["actor_id"] or owner.get("role_id") != actor_target["role_id"]:
        raise PermissionError("task does not belong to the active actor")
    result = task_sys.record_task_analysis_update(
        task_id,
        {
            "task_desc": args.get("task_desc"),
            "task_relation": args.get("task_relation"),
        },
    )
    return _success("update_task_analysis", result, context)


def close(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    task_sys = _task_sys_domain(context)
    result = task_sys.record_task_close(
        str(args.get("task_id") or ""),
        {"summary": args.get("summary")},
    )
    task = result.get("task") if isinstance(result.get("task"), dict) else {}
    execution = task.get("execution") if isinstance(task, dict) else None
    execution_result = execution.get("result") if isinstance(execution, dict) else None
    if isinstance(execution_result, dict) and execution_result.get("processor") == "side" and "cleanup" not in execution_result:
        result = dict(result, task=_record_side_cleanup(task_sys, context, str(result.get("task_id") or ""))["task"])
    return _success("close", result, context)


def need_parent(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    task_sys = _task_sys_domain(context)
    result = task_sys.record_side_need_parent(
        str(args.get("task_id") or ""),
        {
            "params": args.get("params"),
        },
    )
    instruction = task_sys.parent_handoff_instruction(str(result.get("task_id") or ""))
    try:
        parent_runtime = _execute_parent_instruction(context, instruction)
    except Exception:
        _record_side_cleanup(task_sys, context, str(result.get("task_id") or ""))
        raise
    started = task_sys.record_parent_handoff_started(str(result.get("task_id") or ""))
    cleaned = _record_side_cleanup(task_sys, context, str(result.get("task_id") or ""))
    task = cleaned.get("task") if isinstance(cleaned.get("task"), dict) else started.get("task")
    handoff_result = dict(result, task=task)
    return _success(
        "need_parent",
        handoff_result,
        context,
        parent_instruction=instruction,
        parent_runtime=parent_runtime,
    )


_ACTION_HANDLERS = {
    "list": list_tasks,
    "get": get,
    "update_task_analysis": update_task_analysis,
    "close": close,
    "need_parent": need_parent,
}


def invoke(*, action: str, args: dict[str, Any], context: Any) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    rejection = _reject_unknown_payload_fields(action=action, args=args, context=context)
    if rejection is not None:
        return rejection
    return handler(args=args, context=context)
