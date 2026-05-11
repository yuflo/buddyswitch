#!/usr/bin/env python3
"""Unified env.tool envelope router for broker-routed env tool operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from env.tools.artifact_manager import dispatch_artifact_manager_request
from env.tools.binding_manager import dispatch_binding_manager_request
from env.tools.context_manager import dispatch_context_manager_request
from env.tools.evidence_manager import dispatch_evidence_manager_request
from env.tools.handoff_manager import dispatch_handoff_manager_request
from env.tools.run_manager import dispatch_run_manager_request
from env.tools.task_manager import dispatch_task_manager_request
from env.tools.track_manager import dispatch_track_manager_request

_ARTIFACT_ACTIONS = {
    "list",
    "get",
    "get_current",
    "validate_payload",
    "create_revision",
    "update_metadata",
}
_BINDING_ACTIONS = {
    "get",
    "set_task",
    "set_track",
    "clear",
}
_CONTEXT_ACTIONS = {
    "get",
    "summarize",
    "list_sources",
}
_EVIDENCE_ACTIONS = {
    "issue_browser",
    "approve_downgrade",
}
_HANDOFF_ACTIONS = {
    "validate",
}
_RUN_ACTIONS = {
    "commit",
    "get_receipt",
    "get_raw",
    "validate_result",
}
_TASK_ACTIONS = {
    "create",
    "list",
    "get",
    "get_current",
    "set_current",
    "update",
    "archive",
}
_TRACK_ACTIONS = {
    "list",
    "get",
    "get_current",
    "create",
    "update",
    "advance",
    "archive",
    "attach_task",
    "detach_task",
}
_TOOL_ACTIONS = {
    "artifact": _ARTIFACT_ACTIONS,
    "binding": _BINDING_ACTIONS,
    "context": _CONTEXT_ACTIONS,
    "evidence": _EVIDENCE_ACTIONS,
    "handoff": _HANDOFF_ACTIONS,
    "run": _RUN_ACTIONS,
    "task": _TASK_ACTIONS,
    "track": _TRACK_ACTIONS,
}
_TOOL_DISPATCHERS: dict[str, Callable[..., dict[str, Any]]] = {
    "artifact": dispatch_artifact_manager_request,
    "binding": dispatch_binding_manager_request,
    "context": dispatch_context_manager_request,
    "evidence": dispatch_evidence_manager_request,
    "handoff": dispatch_handoff_manager_request,
    "run": dispatch_run_manager_request,
    "task": dispatch_task_manager_request,
    "track": dispatch_track_manager_request,
}
_TOOL_HINTS = {
    "artifact": "artifact_manager",
    "binding": "binding_manager",
    "context": "context_manager",
    "evidence": "evidence_manager",
    "handoff": "handoff_manager",
    "run": "run_manager",
    "task": "task_manager",
    "track": "track_manager",
}


def _supported_tools_text() -> str:
    return ", ".join(sorted(_TOOL_ACTIONS))


def _supported_actions_text(tool: str) -> str:
    return ", ".join(sorted(_TOOL_ACTIONS[tool]))


def _semantic_action(*, tool: str, action: str | None) -> str | None:
    if not isinstance(action, str) or not action.strip():
        return f"{tool}.unknown"
    return f"{tool}.{action.strip().replace('-', '_')}"


def _reject(
    *,
    code: str,
    message: str,
    active_buddy: str,
    permission_boundary: str,
    allowed_next_actions: list[str],
    tool: str | None = None,
    action: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
        },
        "permission_boundary": permission_boundary,
        "active_buddy": active_buddy,
        "allowed_next_actions": allowed_next_actions,
    }
    if isinstance(tool, str) and tool.strip():
        payload["tool"] = tool.strip()
    if isinstance(action, str) and action.strip():
        payload["action"] = action.strip()
    return payload


def dispatch_env_tool_request(
    *,
    payload: dict[str, Any],
    active_buddy: str,
    instance_id: str,
    instance_json: Path,
    instance_payload: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    raw_tool = payload.get("tool")
    if not isinstance(raw_tool, str) or not raw_tool.strip():
        return _reject(
            code="E_ENV_TOOL",
            message="env.tool payload.tool must be a non-empty string",
            active_buddy=active_buddy,
            permission_boundary="env.tool",
            allowed_next_actions=[
                "Send env.tool payload as {tool, action, args}.",
                f"Use one supported tool: {_supported_tools_text()}.",
            ],
        )
    tool = raw_tool.strip().lower()
    if tool not in _TOOL_ACTIONS:
        return _reject(
            code="E_ENV_TOOL",
            message=f"unsupported env.tool payload.tool: {tool}",
            active_buddy=active_buddy,
            permission_boundary="env.tool",
            tool=tool,
            allowed_next_actions=[
                f"Use one supported tool: {_supported_tools_text()}.",
                "Check prepare.runtime_context.env_tools for active tool ids and payload hints.",
            ],
        )

    raw_action = payload.get("action")
    semantic_action = _semantic_action(tool=tool, action=raw_action if isinstance(raw_action, str) else None)
    if not isinstance(raw_action, str) or not raw_action.strip():
        return _reject(
            code="E_ENV_TOOL",
            message="env.tool payload.action must be a non-empty string",
            active_buddy=active_buddy,
            permission_boundary="env.tool",
            tool=tool,
            action=semantic_action,
            allowed_next_actions=[
                f"Set payload.action to one supported {tool} action.",
                f"Use one supported action: {_supported_actions_text(tool)}.",
            ],
        )
    action = raw_action.strip().replace("-", "_")
    semantic_action = _semantic_action(tool=tool, action=action)
    if action not in _TOOL_ACTIONS[tool]:
        return _reject(
            code="E_ENV_TOOL",
            message=f"unsupported env.tool payload.action for {tool}: {action}",
            active_buddy=active_buddy,
            permission_boundary="env.tool",
            tool=tool,
            action=semantic_action,
            allowed_next_actions=[
                f"Use one supported action: {_supported_actions_text(tool)}.",
                f"Check prepare.runtime_context.env_tools.{_TOOL_HINTS[tool]} for action and payload field hints.",
            ],
        )

    args = payload.get("args", {})
    if not isinstance(args, dict):
        return _reject(
            code="E_ENV_TOOL_PAYLOAD",
            message="env.tool payload.args must be an object",
            active_buddy=active_buddy,
            permission_boundary="request-payload",
            tool=tool,
            action=semantic_action,
            allowed_next_actions=[
                "Set payload.args to an object and retry.",
                f"Use prepare.runtime_context.env_tools.{_TOOL_HINTS[tool]}.payload_fields to shape args.",
            ],
        )

    dispatch = _TOOL_DISPATCHERS[tool]
    dispatch_kwargs = {
        "payload": {"action": action, "args": args},
        "active_buddy": active_buddy,
        "instance_id": instance_id,
        "instance_json": instance_json,
        "instance_payload": instance_payload,
        "manifest": manifest,
    }
    if tool in {"run", "evidence"}:
        dispatch_kwargs["manifest_path"] = manifest_path
    response = dispatch(**dispatch_kwargs)
    if isinstance(response, dict):
        response.setdefault("tool", tool)
    return response
