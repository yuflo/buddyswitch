#!/usr/bin/env python3
"""Handoff tool dispatcher for env.tool broker envelope requests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env.services import handoffs as handoff_service

_ACTION_MAP = {
    "validate": handoff_service.validate_handoff,
}


def _payload_error(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "handoff",
        "action": action,
        "error": {
            "code": "E_HANDOFF_PAYLOAD",
            "message": message,
        },
        "permission_boundary": "request-payload",
        "active_buddy": active_buddy,
        "allowed_next_actions": [
            'Send env.tool payload as {"tool":"handoff","action":"validate","args":{...}}.',
            "Use the validate action with next_buddy, reason, and context.",
        ],
    }


def _unknown_action_error(*, action: str, active_buddy: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "handoff",
        "action": action,
        "error": {
            "code": "E_HANDOFF_ACTION",
            "message": f"unsupported handoff action: {action}",
        },
        "permission_boundary": "request-payload",
        "active_buddy": active_buddy,
        "allowed_next_actions": [
            "Use the supported action: validate.",
            "Check prepare.runtime_context.env_tools.handoff_manager for command and payload hints.",
        ],
    }


def dispatch_handoff_manager_request(
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
            action="handoff.unknown",
            active_buddy=active_buddy,
            message="env.tool payload.action must be a non-empty string",
        )
    action_name = raw_action.strip().replace("-", "_")
    action = f"handoff.{action_name}"

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

    context: handoff_service.HandoffServiceContext = {
        "active_buddy": active_buddy,
        "instance_id": instance_id,
        "instance_json": instance_json,
        "instance_payload": instance_payload,
        "manifest": manifest,
    }
    response = handler(args=args, context=context)
    if isinstance(response, dict):
        response.setdefault("tool", "handoff")
    return response
