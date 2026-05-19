#!/usr/bin/env python3
"""Registry-backed runless env.tool dispatch."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from env.tools import responses as tool_responses

HandlerSpec = tuple[str, str]

HANDLER_SPECS_BY_TOOL: dict[str, dict[str, HandlerSpec]] = {
    "task": {
        "create": ("env.services.tasks", "create_task_for_active_buddy"),
        "list": ("env.services.tasks", "list_tasks_for_active_buddy"),
        "get": ("env.services.tasks", "get_task_for_active_buddy"),
        "update": ("env.services.tasks", "update_task_for_active_buddy"),
        "archive": ("env.services.tasks", "archive_task_for_active_buddy"),
    },
    "track": {
        "create": ("env.services.tracks", "create_track_for_pm"),
        "list": ("env.services.tracks", "list_tracks_for_active_buddy"),
        "open": ("env.services.tracks", "open_track_for_active_buddy"),
        "update_now": ("env.services.tracks", "update_now_for_active_buddy"),
        "add_material": ("env.services.tracks", "add_material_to_track"),
        "add_update": ("env.services.tracks", "add_update_to_track"),
        "add_proof": ("env.services.tracks", "add_proof_to_track"),
        "archive": ("env.services.tracks", "archive_track_for_pm"),
    },
    "artifact": {
        "get": ("env.services.artifacts", "get_artifact_for_active_buddy"),
        "create_revision": ("env.services.artifacts", "create_artifact_revision"),
        "update_metadata": ("env.services.artifacts", "update_artifact_metadata"),
    },
    "buddybox": {
        "desc": ("env.services.buddybox", "describe_buddybox_for_active_buddy"),
        "list": ("env.services.buddybox", "list_buddybox_for_active_buddy"),
        "read": ("env.services.buddybox", "read_buddybox_for_active_buddy"),
        "write": ("env.services.buddybox", "write_buddybox_for_active_buddy"),
        "delete": ("env.services.buddybox", "delete_buddybox_for_active_buddy"),
    },
    "context": {
        "get": ("env.services.context", "get_context"),
        "summarize": ("env.services.context", "summarize_context"),
        "list_sources": ("env.services.context", "list_sources"),
    },
    "evidence": {
        "issue_browser": ("env.services.evidence", "issue_browser_for_active_instance"),
        "approve_downgrade": ("env.services.evidence", "approve_downgrade_for_active_instance"),
    },
    "message": {
        "send": ("env.services.messages", "send_message"),
        "list": ("env.services.messages", "list_messages"),
    },
    "comment": {
        "add": ("env.services.comments", "add_comment"),
        "list": ("env.services.comments", "list_comments"),
    },
    "search": {
        "status": ("env.services.search", "status_for_active_instance"),
        "request": ("env.services.search", "request_for_active_instance"),
        "open_browser": ("env.services.search", "open_browser_for_active_instance"),
    },
}


def dispatch_handler_actions() -> dict[str, set[str]]:
    return {tool: set(action_map) for tool, action_map in HANDLER_SPECS_BY_TOOL.items()}


def _load_handler(*, tool: str, action: str) -> Any:
    module_name, function_name = HANDLER_SPECS_BY_TOOL[tool][action]
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
