#!/usr/bin/env python3
"""Run tool dispatcher for env.tool broker envelope requests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from env.services import runs as run_service
from env.tools import contracts as tool_contracts
from env.tools import responses as tool_responses

_ACTION_MAP = {
    "commit": run_service.commit_for_active_instance,
    "get_receipt": run_service.get_receipt_for_active_instance,
    "get_raw": run_service.get_raw_for_active_instance,
    "validate_result": run_service.validate_result_for_active_instance,
}


def _supported_actions_text() -> str:
    return ", ".join(sorted(tool_contracts.supported_actions("run")))


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
            f"Use one supported action: {_supported_actions_text()}.",
        ],
    }


def _router_contract_error(*, action: str, active_buddy: str, action_name: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "run",
        "action": action,
        "error": {
            "code": "E_ENV_TOOL_ROUTER",
            "message": f"router dispatched unsupported run action: {action_name}",
        },
        "permission_boundary": "env.tool.router_contract",
        "active_buddy": active_buddy,
        "allowed_next_actions": [
            "Retry through env.tools.router with a registry-declared action.",
            "Report registry/manager drift if this persists.",
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
    payload: dict[str, Any] = {
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
    if "allowed_next_actions" in payload and "allowed_next_action_options" not in payload:
        payload["allowed_next_action_options"] = [
            tool_responses.next_action_option(
                tool="context",
                action="summarize",
                option_id="summarize_context_before_run_retry",
                reason="Summarize active context before retrying run action.",
            )
        ]
    return payload


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
        return _router_contract_error(action=action, active_buddy=active_buddy, action_name=action_name)

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
