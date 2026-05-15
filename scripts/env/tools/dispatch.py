#!/usr/bin/env python3
"""Registry-backed runless env.tool dispatch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env.services import artifacts as artifact_service
from env.services import buddybox as buddybox_service
from env.services import context as context_service
from env.services import evidence as evidence_service
from env.services import handoffs as handoff_service
from env.services import search as search_service
from env.services import tasks as task_service
from env.services import tracks as track_service
from env.tools import responses as tool_responses

HANDLERS_BY_TOOL = {
    "task": {
        "create": task_service.create_task_for_active_buddy,
        "list": task_service.list_tasks_for_active_buddy,
        "get": task_service.get_task_for_active_buddy,
        "update": task_service.update_task_for_active_buddy,
        "archive": task_service.archive_task_for_active_buddy,
    },
    "track": {
        "list": track_service.list_tracks_for_active_buddy,
        "get": track_service.get_track_for_active_buddy,
        "join": track_service.join_track_for_active_buddy,
        "create": track_service.create_track_for_pm,
        "update": track_service.update_track_for_pm,
        "advance": track_service.advance_track_for_pm,
        "archive": track_service.archive_track_for_pm,
        "attach_task": track_service.attach_task_to_track,
        "detach_task": track_service.detach_task_from_track,
    },
    "artifact": {
        "list": artifact_service.list_artifacts_for_track,
        "get": artifact_service.get_artifact_for_active_buddy,
        "validate_payload": artifact_service.validate_artifact_payload,
        "create_revision": artifact_service.create_artifact_revision,
        "update_metadata": artifact_service.update_artifact_metadata,
    },
    "handoff": {
        "list": handoff_service.list_handoffs_for_active_buddy,
        "validate": handoff_service.validate_handoff,
        "create": handoff_service.create_handoff_for_active_buddy,
    },
    "buddybox": {
        "desc": buddybox_service.describe_buddybox_for_active_buddy,
        "list": buddybox_service.list_buddybox_for_active_buddy,
        "read": buddybox_service.read_buddybox_for_active_buddy,
        "write": buddybox_service.write_buddybox_for_active_buddy,
        "delete": buddybox_service.delete_buddybox_for_active_buddy,
    },
    "context": {
        "get": context_service.get_context,
        "summarize": context_service.summarize_context,
        "list_sources": context_service.list_sources,
    },
    "evidence": {
        "issue_browser": evidence_service.issue_browser_for_active_instance,
        "approve_downgrade": evidence_service.approve_downgrade_for_active_instance,
    },
    "search": {
        "status": search_service.status_for_active_instance,
        "request": search_service.request_for_active_instance,
        "open_browser": search_service.open_browser_for_active_instance,
    },
}


def dispatch_handler_actions() -> dict[str, set[str]]:
    return {tool: set(action_map) for tool, action_map in HANDLERS_BY_TOOL.items()}


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
                reason="Summarize current runless context before retrying the action.",
            )
        ]
    extra = {key: value for key, value in details.items() if key not in {
        "permission_boundary", "human_summary", "why_blocked", "impact", "state_changed", "retryable", "retry_guidance", "allowed_next_actions", "allowed_next_action_options"
    }}
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
    handler = HANDLERS_BY_TOOL[tool][action]
    context = _service_context(
        active_buddy=active_buddy,
        instance_id=instance_id,
        instance_json=instance_json,
        instance_payload=instance_payload,
        manifest=manifest,
        manifest_path=manifest_path,
    )
    semantic_action = f"{tool}.{action}"
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
