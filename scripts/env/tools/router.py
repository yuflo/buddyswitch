#!/usr/bin/env python3
"""Unified env.tool envelope router for broker-routed env tool operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env.tools import contracts as tool_contracts
from env.tools.dispatch import dispatch_registered_env_tool

_TOOL_ACTIONS = {
    tool: tool_contracts.supported_actions(tool)
    for tool in sorted(tool_contracts.supported_tools())
}
_TOOL_HINTS = {tool: tool for tool in _TOOL_ACTIONS}


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
    human_summary: str,
    why_blocked: str,
    impact: str,
    retryable: bool,
    retry_guidance: str,
    state_changed: bool = False,
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
        "human_summary": human_summary,
        "why_blocked": why_blocked,
        "impact": impact,
        "state_changed": state_changed,
        "retryable": retryable,
        "retry_guidance": retry_guidance,
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
            human_summary="The request is missing a valid env tool id.",
            why_blocked="payload.tool must be a non-empty string for env.tool routing.",
            impact="No env action ran and runtime state was unchanged.",
            retryable=True,
            retry_guidance="Fix payload.tool, payload.action, and payload.args, then retry the request.",
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
            human_summary=f"Tool '{tool}' is not registered for env.tool.",
            why_blocked="payload.tool is not in the runtime supported env tool set.",
            impact="No env action ran and runtime state was unchanged.",
            retryable=True,
            retry_guidance="Pick a tool id from prepare.runtime_context.env_tools and retry.",
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
            human_summary="The request is missing a valid env action id.",
            why_blocked="payload.action must be a non-empty string for the selected tool.",
            impact="No env action ran and runtime state was unchanged.",
            retryable=True,
            retry_guidance="Set payload.action to a supported action id and retry.",
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
            human_summary=f"Action '{action}' is not supported for tool '{tool}'.",
            why_blocked="payload.action is not registered under the selected tool.",
            impact="No env action ran and runtime state was unchanged.",
            retryable=True,
            retry_guidance="Choose an action from prepare.runtime_context.env_tools and retry.",
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
            human_summary="The request args payload has the wrong shape.",
            why_blocked="payload.args must be a JSON object for env.tool handlers.",
            impact="No env action ran and runtime state was unchanged.",
            retryable=True,
            retry_guidance="Set payload.args to an object and include only supported fields.",
            tool=tool,
            action=semantic_action,
            allowed_next_actions=[
                "Set payload.args to an object and retry.",
                f"Use prepare.runtime_context.env_tools.{_TOOL_HINTS[tool]}.payload_fields to shape args.",
            ],
        )

    response = dispatch_registered_env_tool(
        tool=tool,
        action=action,
        args=args,
        active_buddy=active_buddy,
        instance_id=instance_id,
        instance_json=instance_json,
        instance_payload=instance_payload,
        manifest=manifest,
        manifest_path=manifest_path,
    )
    if isinstance(response, dict):
        response.setdefault("tool", tool)
    return response
