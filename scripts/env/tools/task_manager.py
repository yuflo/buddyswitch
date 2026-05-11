#!/usr/bin/env python3
"""Task tool dispatcher for env.tool broker envelope requests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env.services import tasks as task_service

_ACTION_MAP = {
    "create": task_service.create_task_for_active_buddy,
    "list": task_service.list_tasks_for_active_buddy,
    "get": task_service.get_task_for_active_buddy,
    "get_current": task_service.get_current_task,
    "set_current": task_service.set_current_task,
    "update": task_service.update_task_for_active_buddy,
    "archive": task_service.archive_task_for_active_buddy,
}


def _payload_error(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "task",
        "action": action,
        "error": {
            "code": "E_TASK_PAYLOAD",
            "message": message,
        },
        "permission_boundary": "request-payload",
        "active_buddy": active_buddy,
        "allowed_next_actions": [
            'Send env.tool payload as {"tool":"task","action":"<action>","args":{...}}.',
            "Use one supported action: create, list, get, get_current, set_current, update, archive.",
        ],
    }


def _unknown_action_error(*, action: str, active_buddy: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "task",
        "action": action,
        "error": {
            "code": "E_TASK_ACTION",
            "message": f"unsupported task action: {action}",
        },
        "permission_boundary": "request-payload",
        "active_buddy": active_buddy,
        "allowed_next_actions": [
            "Use one supported action: create, list, get, get_current, set_current, update, archive.",
            "Check prepare.runtime_context.env_tools.task_manager for command and payload hints.",
        ],
    }


def dispatch_task_manager_request(
    *,
    payload: dict[str, Any],
    active_buddy: str,
    instance_id: str,
    instance_json: Path,
    instance_payload: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    raw_action = payload.get("action")
    if not isinstance(raw_action, str) or not raw_action.strip():
        return _payload_error(
            action="task.unknown",
            active_buddy=active_buddy,
            message="env.tool payload.action must be a non-empty string",
        )
    action_name = raw_action.strip().replace("-", "_")
    action = f"task.{action_name}"

    args = payload.get("args", {})
    if not isinstance(args, dict):
        return _payload_error(
            action=action,
            active_buddy=active_buddy,
            message="env.tool payload.args must be an object",
        )

    handler = _ACTION_MAP.get(action_name)
    if handler is None:
        return _unknown_action_error(action=action, active_buddy=active_buddy)

    context: task_service.TaskServiceContext = {
        "active_buddy": active_buddy,
        "instance_id": instance_id,
        "instance_json": instance_json,
        "instance_payload": instance_payload,
        "manifest": manifest,
    }
    response = handler(args=args, context=context)
    if isinstance(response, dict):
        response.setdefault("tool", "task")
    return response
