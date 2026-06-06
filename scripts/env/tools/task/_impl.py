#!/usr/bin/env python3
"""Task services for broker-routed env.tool operations."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Callable, TypedDict

from env.tool_runtime import results as tool_results


class TaskServiceContext(TypedDict):
    active_role: str
    active_actor: dict[str, Any]
    actor_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _repo_context(context: TaskServiceContext) -> dict[str, Any]:
    return {
        "active_role": context["active_role"],
        "active_actor": context["active_actor"],
        "instance_json": context["instance_json"],
        "instance_payload": context["instance_payload"],
    }


def _task_management() -> Any:
    return importlib.import_module("env.domain.task_management")


def _reject_payload(*, action: str, active_actor: dict[str, Any], active_role: str, result: dict[str, Any]) -> dict[str, Any]:
    message = str(result.get("message") or "Task request payload is invalid.")
    correctable_fields = result.get("correctable_fields")
    if not isinstance(correctable_fields, list):
        correctable_fields = None
    return tool_results.rejection(
        tool="task",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        code="E_TASK_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Task request payload is invalid.",
        why_blocked=message,
        impact="No taskbox files, taskbox history, sibling runtime objects, or actor_private files changed.",
        state_changed=False,
        durability="none",
        retryable=True,
        retry_guidance="Fix task payload fields and retry with the documented Task Operation.",
        allowed_next_actions=[
            "Use task.current to inspect the TaskViewModel.",
            "Use context.get to inspect task tool catalog and operation semantics.",
        ],
        correctable_fields=correctable_fields,
        alternative_capabilities=[
            tool_results.alternative_capability(
                tool="context",
                action="get",
                condition="Use when exact task action payload schemas or recovery guidance are needed.",
            ),
        ],
    )


def _success(
    *,
    action: str,
    active_actor: dict[str, Any],
    active_role: str,
    result: dict[str, Any],
    durability: str,
) -> dict[str, Any]:
    extra: dict[str, Any] = {"view": result.get("view")}
    if "task" in result:
        extra["task"] = result.get("task")
        extra["task_id"] = result.get("task_id")
    return tool_results.success(
        tool="task",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=str(result.get("effect_summary") or f"{action} completed."),
        state_changed=bool(result.get("state_changed")),
        durability=durability if bool(result.get("state_changed")) else "none",
        created_ids=result.get("created_ids") if isinstance(result.get("created_ids"), list) else [],
        updated_ids=result.get("updated_ids") if isinstance(result.get("updated_ids"), list) else [],
        state_changes=result.get("state_changes") if isinstance(result.get("state_changes"), list) else [],
        allowed_next_actions=["Use task.current to inspect the latest TaskViewModel."],
        extra=extra,
    )


def _history_limit_or_reject(args: dict[str, Any]) -> int | dict[str, Any]:
    unknown = sorted(key for key in args if key != "history_limit")
    if unknown:
        return {"message": f"unsupported payload fields: {', '.join(unknown)}", "correctable_fields": unknown}
    history_limit = args.get("history_limit", 8)
    if history_limit is None:
        history_limit = 8
    if not isinstance(history_limit, int) or history_limit < 1:
        return {"message": "history_limit must be a positive integer", "correctable_fields": ["history_limit"]}
    return history_limit


def current_for_active_actor(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    action = "task.current"
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    history_limit = _history_limit_or_reject(args)
    if isinstance(history_limit, dict):
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, result=history_limit)
    view = _task_management().current_view(
        **_repo_context(context),
        history_limit=history_limit,
    )
    return tool_results.success(
        tool="task",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary="Read the active actor TaskViewModel.",
        state_changed=False,
        durability="none",
        read_scope="instance-local active actor taskbox TaskViewModel",
        allowed_next_actions=[
            "Use task.capture to shelf a new work demand.",
            "Use task.select when shelf work should become current and no active anchor exists.",
            "Use task.checkout to end a work block for the current anchor.",
        ],
        extra={"view": view},
    )


def _operation_handler(operation: Callable[..., dict[str, Any]], action: str, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    result = operation(
        **_repo_context(context),
        args=args,
    )
    if not result.get("ok"):
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, result=result)
    return _success(action=action, active_actor=active_actor, active_role=active_role, result=result, durability="durable")


def capture_for_active_actor(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    return _operation_handler(_task_management().capture_task, "task.capture", args, context)


def select_for_active_actor(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    return _operation_handler(_task_management().select_task, "task.select", args, context)


def switch_request_for_active_actor(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    return _operation_handler(_task_management().request_task_switch, "task.switch_request", args, context)


def switch_confirm_for_active_actor(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    return _operation_handler(_task_management().confirm_task_switch, "task.switch_confirm", args, context)


def progress_for_active_actor(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    return _operation_handler(_task_management().append_task_progress, "task.progress", args, context)


def checkout_for_active_actor(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    return _operation_handler(_task_management().checkout_task, "task.checkout", args, context)


def review_for_active_actor(*, args: dict[str, Any], context: TaskServiceContext) -> dict[str, Any]:
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    result = _task_management().review_tasks(
        **_repo_context(context),
        args=args,
    )
    if not result.get("ok"):
        return _reject_payload(action="task.review", active_actor=active_actor, active_role=active_role, result=result)
    return _success(action="task.review", active_actor=active_actor, active_role=active_role, result=result, durability="none")


_ACTION_HANDLERS = {
    "current": current_for_active_actor,
    "capture": capture_for_active_actor,
    "select": select_for_active_actor,
    "switch_request": switch_request_for_active_actor,
    "switch_confirm": switch_confirm_for_active_actor,
    "progress": progress_for_active_actor,
    "checkout": checkout_for_active_actor,
    "review": review_for_active_actor,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    return handler(args=args, context=context)
