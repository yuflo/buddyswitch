#!/usr/bin/env python3
"""Generic per-tool env.tool dispatch."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from env.tools import discovery
from env.tools import responses as tool_responses

HandlerSpec = tuple[str, str]


def _handler_specs_for_tool(tool: str) -> dict[str, HandlerSpec]:
    module = discovery.import_tool_module(tool, "handlers")
    specs = getattr(module, "HANDLER_SPECS", None)
    if not isinstance(specs, dict):
        raise TypeError(f"env.tools.{tool}.handlers.HANDLER_SPECS must be an object")
    normalized: dict[str, HandlerSpec] = {}
    for action, row in specs.items():
        if not isinstance(action, str):
            continue
        if not isinstance(row, tuple) or len(row) != 2:
            raise TypeError(f"handler spec for {tool}.{action} must be tuple(module, function)")
        module_name, function_name = row
        if not isinstance(module_name, str) or not isinstance(function_name, str):
            raise TypeError(f"handler spec for {tool}.{action} must be tuple(str, str)")
        normalized[action] = (module_name, function_name)
    return normalized


def dispatch_handler_actions() -> dict[str, set[str]]:
    rows: dict[str, set[str]] = {}
    for tool in discovery.discover_tool_ids():
        try:
            specs = _handler_specs_for_tool(tool)
        except Exception:
            continue
        rows[tool] = set(specs)
    return rows


def _load_handler(*, tool: str, action: str) -> Any:
    specs = _handler_specs_for_tool(tool)
    if action not in specs:
        raise KeyError(f"action '{action}' is not registered in env.tools.{tool}.handlers.HANDLER_SPECS")
    module_name, function_name = specs[action]
    module = importlib.import_module(module_name)
    handler = getattr(module, function_name)
    if not callable(handler):
        raise TypeError(f"handler is not callable: {module_name}.{function_name}")
    return handler


def _runtime_feedback_error(
    *,
    tool: str,
    action: str,
    active_buddy: str,
    code: str,
    message: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    def _coerce_bool(value: Any, *, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
            return default
        if isinstance(value, (int, float)):
            return bool(value)
        return default

    permission_boundary = str(details.get("permission_boundary", "runtime.feedback"))
    human_summary = str(details.get("human_summary", message))
    why_blocked = str(details.get("why_blocked", message))
    impact = str(details.get("impact", "No state changed before runtime rejection."))
    state_changed = _coerce_bool(details.get("state_changed"), default=False)
    retryable = _coerce_bool(details.get("retryable"), default=True)
    retry_guidance = str(details.get("retry_guidance", "Fix runtime preconditions and retry."))
    allowed_next_actions = details.get("allowed_next_actions")
    if not isinstance(allowed_next_actions, list) or not allowed_next_actions:
        allowed_next_actions = ["Inspect payload and retry once prerequisites are satisfied."]
    options = details.get("allowed_next_action_options")
    if not isinstance(options, list):
        options = [
            tool_responses.next_action_option(
                tool="context",
                action="summarize",
                option_id="summarize_context_before_retry",
                reason="Use when you need compact runtime context before retrying the action.",
            )
        ]
    correctable_fields = details.get("correctable_fields")
    if not isinstance(correctable_fields, list):
        correctable_fields = ["args"]
    alternative_capabilities = details.get("alternative_capabilities")
    if not isinstance(alternative_capabilities, list):
        alternative_capabilities = [
            tool_responses.alternative_capability(
                tool="context",
                action="get",
                condition="Use when you need full runtime catalog and semantics before retrying.",
            )
        ]
    extra = {
        key: value
        for key, value in details.items()
        if key
        not in {
            "permission_boundary",
            "human_summary",
            "why_blocked",
            "impact",
            "state_changed",
            "retryable",
            "retry_guidance",
            "allowed_next_actions",
            "allowed_next_action_options",
            "correctable_fields",
            "alternative_capabilities",
        }
    }
    return tool_responses.rejection(
        tool=tool,
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=permission_boundary,
        human_summary=human_summary,
        why_blocked=why_blocked,
        impact=impact,
        state_changed=state_changed,
        retryable=retryable,
        retry_guidance=retry_guidance,
        allowed_next_actions=list(allowed_next_actions),
        allowed_next_action_options=options,
        correctable_fields=correctable_fields,
        alternative_capabilities=alternative_capabilities,
        extra=extra if extra else None,
    )


def _service_context(
    *,
    active_buddy: str,
    instance_id: str,
    instance_json: Path,
    instance_payload: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path | None,
) -> dict[str, Any]:
    return {
        "active_buddy": active_buddy,
        "instance_id": instance_id,
        "instance_json": instance_json,
        "instance_payload": instance_payload,
        "manifest": manifest,
        "manifest_path": manifest_path,
    }


def dispatch_registered_env_tool(
    *,
    tool: str,
    action: str,
    args: dict[str, Any],
    active_buddy: str,
    instance_id: str,
    instance_json: Path,
    instance_payload: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    semantic_action = f"{tool}.{action}"
    try:
        handler = _load_handler(tool=tool, action=action)
    except Exception as exc:
        return _runtime_feedback_error(
            tool=tool,
            action=semantic_action,
            active_buddy=active_buddy,
            code="E_ENV_TOOL_DISPATCH",
            message=f"failed to load env tool handler for {semantic_action}: {exc}",
            details={
                "permission_boundary": "env.tool.dispatch",
                "human_summary": "Selected env tool handler could not be loaded.",
                "why_blocked": str(exc),
                "impact": "No handler ran and no runtime state changed.",
                "state_changed": False,
                "retryable": False,
                "retry_guidance": "Fix the selected tool implementation before retrying this action.",
                "allowed_next_actions": ["Use another registered tool that does not depend on this handler."],
            },
        )

    context = _service_context(
        active_buddy=active_buddy,
        instance_id=instance_id,
        instance_json=instance_json,
        instance_payload=instance_payload,
        manifest=manifest,
        manifest_path=manifest_path,
    )
    try:
        response = handler(args=args, context=context)
    except (ValueError, OSError) as exc:
        response = _runtime_feedback_error(
            tool=tool,
            action=semantic_action,
            active_buddy=active_buddy,
            code="E_RUNTIME_BROKER",
            message=str(exc),
            details={
                "permission_boundary": "runtime.feedback",
                "human_summary": "Runtime service rejected the request before completion.",
                "why_blocked": str(exc),
                "impact": "No durable state was changed by this failed operation.",
                "state_changed": False,
                "retryable": True,
                "retry_guidance": "Fix payload or prerequisites and retry.",
                "allowed_next_actions": ["Use context.summarize to inspect current state before retrying."],
            },
        )

    if isinstance(response, dict):
        response.setdefault("tool", tool)
    return response
