#!/usr/bin/env python3
"""Registry-backed env.tool action dispatch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from env.services import artifacts as artifact_service
from env.services import bindings as binding_service
from env.services import context as context_service
from env.services import evidence as evidence_service
from env.services import handoffs as handoff_service
from env.services import runs as run_service
from env.services import search as search_service
from env.services import tasks as task_service
from env.services import tracks as track_service
from env.tools import responses as tool_responses

HANDLERS_BY_TOOL = {
    "task": {
        "create": task_service.create_task_for_active_buddy,
        "list": task_service.list_tasks_for_active_buddy,
        "get": task_service.get_task_for_active_buddy,
        "get_current": task_service.get_current_task,
        "set_current": task_service.set_current_task,
        "update": task_service.update_task_for_active_buddy,
        "archive": task_service.archive_task_for_active_buddy,
    },
    "track": {
        "list": track_service.list_tracks_for_active_buddy,
        "get": track_service.get_track_for_active_buddy,
        "join": track_service.join_track_for_active_buddy,
        "get_current": track_service.get_current_track,
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
        "get_current": artifact_service.get_current_artifacts_for_active_task,
        "validate_payload": artifact_service.validate_artifact_payload,
        "create_revision": artifact_service.create_artifact_revision,
        "update_metadata": artifact_service.update_artifact_metadata,
    },
    "context": {
        "get": context_service.get_context,
        "summarize": context_service.summarize_context,
        "list_sources": context_service.list_sources,
    },
    "binding": {
        "get": binding_service.get_binding,
        "set_task": binding_service.set_task_binding,
        "set_track": binding_service.set_track_binding,
        "clear": binding_service.clear_binding,
    },
    "handoff": {
        "list": handoff_service.list_handoffs_for_active_buddy,
        "validate": handoff_service.validate_handoff,
        "create": handoff_service.create_handoff_for_active_buddy,
    },
    "run": {
        "commit": run_service.commit_for_active_instance,
        "get_receipt": run_service.get_receipt_for_active_instance,
        "get_raw": run_service.get_raw_for_active_instance,
        "validate_result": run_service.validate_result_for_active_instance,
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
    missing = object()

    def _extract_bool_field(*, key: str, default: bool, invalid_default: bool) -> bool:
        raw = extra.pop(key, missing)
        if raw is missing:
            return default
        if isinstance(raw, bool):
            return raw
        return invalid_default

    extra = dict(details)
    permission_boundary = str(extra.pop("permission_boundary", "runtime.feedback"))
    allowed_next_actions_raw = extra.pop("allowed_next_actions", [])
    allowed_next_actions = (
        list(allowed_next_actions_raw)
        if isinstance(allowed_next_actions_raw, list)
        else ["Retry after fixing runtime preconditions."]
    )
    options = extra.pop("allowed_next_action_options", None)
    if not isinstance(options, list) and allowed_next_actions:
        if tool == "run":
            options = [
                tool_responses.next_action_option(
                    tool="context",
                    action="summarize",
                    option_id="summarize_context_before_run_retry",
                    reason="Summarize active context before retrying run action.",
                )
            ]
        elif tool == "evidence":
            options = [
                tool_responses.next_action_option(
                    tool="evidence",
                    action="issue_browser",
                    option_id="issue_browser_token",
                    reason="Issue browser evidence for the prepared run before retrying.",
                )
            ]
    state_changed = _extract_bool_field(key="state_changed", default=False, invalid_default=False)
    retryable = _extract_bool_field(key="retryable", default=True, invalid_default=False)
    retry_guidance = str(extra.pop("retry_guidance", "Fix runtime preconditions and retry safely."))
    human_summary = str(extra.pop("human_summary", message))
    why_blocked = str(extra.pop("why_blocked", message))
    impact = str(extra.pop("impact", "No runtime state changed before this rejection."))
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
        allowed_next_actions=allowed_next_actions,
        allowed_next_action_options=options if isinstance(options, list) else None,
        extra=extra if extra else None,
    )


def _service_context(
    *,
    tool: str,
    active_buddy: str,
    instance_id: str,
    instance_json: Path,
    instance_payload: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path | None,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "active_buddy": active_buddy,
        "instance_id": instance_id,
        "instance_json": instance_json,
        "instance_payload": instance_payload,
        "manifest": manifest,
    }
    if tool in {"run", "evidence", "search"}:
        context["manifest_path"] = manifest_path
    return context


def _runtime_feedback_from_exception(
    *,
    tool: str,
    action: str,
    active_buddy: str,
    error: Exception,
) -> dict[str, Any]:
    if tool == "run":
        return _runtime_feedback_error(
            tool=tool,
            action=action,
            active_buddy=active_buddy,
            code="E_RUNTIME_PERSIST",
            message=str(error),
            details={
                "permission_boundary": "run.service",
                "human_summary": "Run service rejected the request before commit.",
                "why_blocked": str(error),
                "impact": "No run commit or runtime object mutation occurred.",
                "state_changed": False,
                "retryable": True,
                "retry_guidance": "Fix run payload or refresh context, then retry run.validate_result or run.commit.",
                "allowed_next_actions": [
                    "Use prepare.runtime_context.env_tools.run payload hints and retry.",
                    "Rerun prepare if the context or reserved run is stale.",
                ],
            },
        )
    return _runtime_feedback_error(
        tool=tool,
        action=action,
        active_buddy=active_buddy,
        code="E_RUNTIME_BROKER",
        message=str(error),
        details={
            "permission_boundary": "market.browser_evidence",
            "human_summary": "Evidence service rejected the request before token issuance.",
            "why_blocked": str(error),
            "impact": "No evidence token was issued and no runtime objects were changed.",
            "state_changed": False,
            "retryable": True,
            "retry_guidance": "Fix evidence payload or browser readiness, then retry evidence action.",
            "allowed_next_actions": [
                "Use prepare.runtime_context.env_tools.evidence payload hints and retry.",
                "Rerun prepare if the context or browser cockpit readiness is stale.",
            ],
        },
    )


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
        tool=tool,
        active_buddy=active_buddy,
        instance_id=instance_id,
        instance_json=instance_json,
        instance_payload=instance_payload,
        manifest=manifest,
        manifest_path=manifest_path,
    )
    semantic_action = f"{tool}.{action}"

    if tool in {"run", "evidence"}:
        import turn_runtime

        try:
            response = handler(args=args, context=context)
        except turn_runtime.RuntimeFeedbackError as exc:
            return _runtime_feedback_error(
                tool=tool,
                action=semantic_action,
                active_buddy=active_buddy,
                code=exc.code,
                message=exc.message,
                details=exc.details,
            )
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            return _runtime_feedback_from_exception(
                tool=tool,
                action=semantic_action,
                active_buddy=active_buddy,
                error=exc,
            )
    else:
        response = handler(args=args, context=context)

    if isinstance(response, dict):
        response.setdefault("tool", tool)
    return response
