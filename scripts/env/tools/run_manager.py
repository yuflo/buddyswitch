#!/usr/bin/env python3
"""Run tool dispatcher for env.tool broker envelope requests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from env.services import runs as run_service

_ACTION_MAP = {
    "commit": run_service.commit_for_active_instance,
    "get_receipt": run_service.get_receipt_for_active_instance,
    "get_raw": run_service.get_raw_for_active_instance,
    "validate_result": run_service.validate_result_for_active_instance,
}


def _payload_error(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "run",
        "action": action,
        "error": {
            "code": "E_RUN_PAYLOAD",
            "message": message,
        },
        "permission_boundary": "request-payload",
        "active_buddy": active_buddy,
        "allowed_next_actions": [
            'Send env.tool payload as {"tool":"run","action":"<action>","args":{...}}.',
            "Use one supported action: commit, get_receipt, get_raw, validate_result.",
        ],
    }


def _unknown_action_error(*, action: str, active_buddy: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "run",
        "action": action,
        "error": {
            "code": "E_RUN_ACTION",
            "message": f"unsupported run action: {action}",
        },
        "permission_boundary": "request-payload",
        "active_buddy": active_buddy,
        "allowed_next_actions": [
            "Use one supported action: commit, get_receipt, get_raw, validate_result.",
            "Check prepare.runtime_context.env_tools.run_manager for command and payload hints.",
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
    return {
        "ok": False,
        "tool": "run",
        "action": action,
        "error": {
            "code": code,
            "message": message,
        },
        "active_buddy": active_buddy,
        **details,
    }


def dispatch_run_manager_request(
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
            action="run.unknown",
            active_buddy=active_buddy,
            message="env.tool payload.action must be a non-empty string",
        )
    action_name = raw_action.strip().replace("-", "_")
    action = f"run.{action_name}"

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

    context: run_service.RunServiceContext = {
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
            code="E_RUNTIME_PERSIST",
            message=str(exc),
            details={
                "permission_boundary": "run.service",
                "allowed_next_actions": [
                    "Use prepare.runtime_context.env_tools.run_manager payload hints and retry.",
                    "Rerun prepare if the context or reserved run is stale.",
                ],
            },
        )
    if isinstance(response, dict):
        response.setdefault("tool", "run")
    return response
