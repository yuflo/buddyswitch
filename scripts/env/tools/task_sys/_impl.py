#!/usr/bin/env python3
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
            "Use task_sys.list, task_sys.get, task_sys.close, or task_sys.need_parent with documented payload fields.",
        ],
        correctable_fields=unknown,
    )


def _task_events(task: Mapping[str, Any]) -> list[dict[str, Any]]:
    events = task.get("events")
    if not isinstance(events, list):
        return []
    return [dict(row) for row in events if isinstance(row, Mapping)]


def _task_summary(task: Mapping[str, Any]) -> dict[str, Any]:
    task_id = task.get("id")
    row = {
        "task_id": task_id,
        "id": task_id,
        "source_type": task.get("source_type"),
        "source_ref": task.get("source_ref"),
        "status": task.get("status"),
        "active_processor": task.get("active_processor"),
        "updated_at": task.get("updated_at"),
        "event_types": [str(event.get("type")) for event in _task_events(task) if event.get("type")],
    }
    parent_handoff = task.get("parent_handoff_params")
    if isinstance(parent_handoff, Mapping):
        row["parent_handoff_params"] = dict(parent_handoff)
    failure_result = task.get("failure_result")
    if isinstance(failure_result, Mapping):
        row["failure_result"] = dict(failure_result)
    return row


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
            "Use task_sys.close when the active frame completed the source-bound task.",
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
    extra: dict[str, Any] = {
        "task_id": result.get("task_id"),
        "outcome": result.get("outcome"),
        "task_status": task.get("status"),
    }
    parent_handoff = task.get("parent_handoff_params")
    if isinstance(parent_handoff, dict):
        extra["parent_handoff_params"] = parent_handoff
    close_result = task.get("close_result")
    if isinstance(close_result, dict):
        extra["close_result"] = close_result
        processor = close_result.get("processor")
        if isinstance(processor, str) and processor.strip():
            extra["processor"] = processor.strip()
        side_thread_id = close_result.get("side_thread_id")
        if isinstance(side_thread_id, str) and side_thread_id.strip():
            extra["side_thread_id"] = side_thread_id.strip()
        cleanup = close_result.get("cleanup")
        if isinstance(cleanup, dict):
            extra["side_cleanup"] = cleanup
    side_result = task.get("side_result")
    if isinstance(side_result, dict):
        extra["side_result"] = side_result
        extra["processor"] = "side"
        side_thread_id = side_result.get("side_thread_id")
        if isinstance(side_thread_id, str) and side_thread_id.strip():
            extra["side_thread_id"] = side_thread_id.strip()
        cleanup = side_result.get("cleanup")
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
        allowed_next_actions=["Use the returned task_status, processor, and cleanup fields to decide the next frame action."],
        extra=extra,
    )


def _execute_parent_instruction(context: Any, instruction: dict[str, Any]) -> dict[str, Any]:
    daemon = context.get("daemon") if isinstance(context, dict) else None
    if daemon is None:
        daemon = getattr(context, "daemon", None)
    execute = getattr(daemon, "execute_task_sys_instruction", None)
    if not callable(execute):
        raise RuntimeError("Task Sys parent runtime execution is unavailable")
    result = execute(instruction)
    if not isinstance(result, dict):
        raise RuntimeError("Task Sys parent runtime execution returned a non-object result")
    return result


def _cleanup_task_sys_side_lease(context: Any, task_id: str) -> dict[str, Any]:
    daemon = context.get("daemon") if isinstance(context, dict) else None
    if daemon is None:
        daemon = getattr(context, "daemon", None)
    cleanup = getattr(daemon, "cleanup_task_sys_side_lease", None)
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
    cleanup = _cleanup_task_sys_side_lease(context, task_id)
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
    actor_target = _actor_target(context)
    status = args.get("status") or "active"
    if status not in {"active", "recoverable", "all"}:
        raise ValueError("status must be active, recoverable, or all")

    active = task_sys.active_tasks_for_actor(actor_target)
    recoverable = task_sys.recoverable_tasks_for_actor(actor_target)
    if status == "active":
        rows = active
    elif status == "recoverable":
        rows = recoverable
    else:
        rows = task_sys.list_tasks(actor_target=actor_target)

    limited = rows[: _limit(args)]
    return _read_success(
        "list",
        context,
        effect_summary="Listed actor-owned Task Sys tasks.",
        extra={
            "tasks": [_task_summary(row) for row in limited if isinstance(row, Mapping)],
            "active_count": len(active),
            "recoverable_count": len(recoverable),
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


def close(*, args: dict[str, Any], context: Any) -> dict[str, Any]:
    task_sys = _task_sys_domain(context)
    result = task_sys.record_task_close(
        str(args.get("task_id") or ""),
        {"summary": args.get("summary")},
    )
    task = result.get("task") if isinstance(result.get("task"), dict) else {}
    close_result = task.get("close_result") if isinstance(task, dict) else None
    if isinstance(close_result, dict) and close_result.get("processor") == "side" and "cleanup" not in close_result:
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
