#!/usr/bin/env python3
"""Track tool dispatcher for env.tool broker envelope requests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env.services import tracks as track_service
from env.tools import contracts as tool_contracts

_ACTION_MAP = {
    "list": track_service.list_tracks_for_active_buddy,
    "get": track_service.get_track_for_active_buddy,
    "get_current": track_service.get_current_track,
    "create": track_service.create_track_for_pm,
    "update": track_service.update_track_for_pm,
    "advance": track_service.advance_track_for_pm,
    "archive": track_service.archive_track_for_pm,
    "attach_task": track_service.attach_task_to_track,
    "detach_task": track_service.detach_task_from_track,
}


def _supported_actions_text() -> str:
    return ", ".join(sorted(tool_contracts.supported_actions("track")))


def _payload_error(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "track",
        "action": action,
        "error": {
            "code": "E_TRACK_PAYLOAD",
            "message": message,
        },
        "permission_boundary": "request-payload",
        "active_buddy": active_buddy,
        "allowed_next_actions": [
            'Send env.tool payload as {"tool":"track","action":"<action>","args":{...}}.',
            f"Use one supported action: {_supported_actions_text()}.",
        ],
    }


def _router_contract_error(*, action: str, active_buddy: str, action_name: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "track",
        "action": action,
        "error": {
            "code": "E_ENV_TOOL_ROUTER",
            "message": f"router dispatched unsupported track action: {action_name}",
        },
        "permission_boundary": "env.tool.router_contract",
        "active_buddy": active_buddy,
        "allowed_next_actions": [
            "Retry through env.tools.router with a registry-declared action.",
            "Report registry/manager drift if this persists.",
        ],
    }


def dispatch_track_manager_request(
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
            action="track.unknown",
            active_buddy=active_buddy,
            message="env.tool payload.action must be a non-empty string",
        )
    action_name = raw_action.strip().replace("-", "_")
    action = f"track.{action_name}"

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

    context: track_service.TrackServiceContext = {
        "active_buddy": active_buddy,
        "instance_id": instance_id,
        "instance_json": instance_json,
        "instance_payload": instance_payload,
        "manifest": manifest,
    }
    response = handler(args=args, context=context)
    if isinstance(response, dict):
        response.setdefault("tool", "track")
    return response
