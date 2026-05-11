#!/usr/bin/env python3
"""Evidence tool dispatcher for env.tool broker envelope requests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from env.services import evidence as evidence_service

_ACTION_MAP = {
    "issue_browser": evidence_service.issue_browser_for_active_instance,
    "approve_downgrade": evidence_service.approve_downgrade_for_active_instance,
}


def _payload_error(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "evidence",
        "action": action,
        "error": {
            "code": "E_EVIDENCE_PAYLOAD",
            "message": message,
        },
        "permission_boundary": "request-payload",
        "active_buddy": active_buddy,
        "allowed_next_actions": [
            'Send env.tool payload as {"tool":"evidence","action":"<action>","args":{...}}.',
            "Use one supported action: issue_browser, approve_downgrade.",
        ],
    }


def _unknown_action_error(*, action: str, active_buddy: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "evidence",
        "action": action,
        "error": {
            "code": "E_EVIDENCE_ACTION",
            "message": f"unsupported evidence action: {action}",
        },
        "permission_boundary": "request-payload",
        "active_buddy": active_buddy,
        "allowed_next_actions": [
            "Use one supported action: issue_browser, approve_downgrade.",
            "Check prepare.runtime_context.env_tools.evidence_manager for command and payload hints.",
        ],
    }


def _runtime_feedback_error(
    *,
    action: str,
    active_buddy: str,
    code: str,
    message: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    error = {
        "code": code,
        "message": message,
    }
    error.update(details)
    return {
        "ok": False,
        "tool": "evidence",
        "action": action,
        "error": error,
        "active_buddy": active_buddy,
        **details,
    }


def dispatch_evidence_manager_request(
    *,
    payload: dict[str, Any],
    active_buddy: str,
    instance_id: str,
    instance_json: Path,
    instance_payload: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    raw_action = payload.get("action")
    if not isinstance(raw_action, str) or not raw_action.strip():
        return _payload_error(
            action="evidence.unknown",
            active_buddy=active_buddy,
            message="env.tool payload.action must be a non-empty string",
        )
    action_name = raw_action.strip().replace("-", "_")
    action = f"evidence.{action_name}"

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

    context: evidence_service.EvidenceServiceContext = {
        "active_buddy": active_buddy,
        "instance_id": instance_id,
        "instance_json": instance_json,
        "instance_payload": instance_payload,
        "manifest": manifest,
        "manifest_path": manifest_path,
    }
    import turn_runtime

    try:
        response = handler(args=args, context=context)
    except turn_runtime.RuntimeFeedbackError as exc:
        return _runtime_feedback_error(
            action=action,
            active_buddy=active_buddy,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return _runtime_feedback_error(
            action=action,
            active_buddy=active_buddy,
            code="E_RUNTIME_BROKER",
            message=str(exc),
            details={
                "permission_boundary": "market.browser_evidence",
                "allowed_next_actions": [
                    "Use prepare.runtime_context.env_tools.evidence_manager payload hints and retry.",
                    "Rerun prepare if the context or browser cockpit readiness is stale.",
                ],
            },
        )
    if isinstance(response, dict):
        response.setdefault("tool", "evidence")
    return response
