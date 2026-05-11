#!/usr/bin/env python3
"""Track tool dispatcher for env.tool broker envelope requests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env.services import tracks as track_service

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
            "Use one supported action: list, get, get_current, create, update, advance, archive, attach_task, detach_task.",
        ],
    }


def _unknown_action_error(*, action: str, active_buddy: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "track",
        "action": action,
        "error": {
            "code": "E_TRACK_ACTION",
            "message": f"unsupported track action: {action}",
        },
        "permission_boundary": "request-payload",
        "active_buddy": active_buddy,
        "allowed_next_actions": [
            "Use one supported action: list, get, get_current, create, update, advance, archive, attach_task, detach_task.",
            "Check prepare.runtime_context.env_tools.track_manager for command and payload hints.",
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
        return _unknown_action_error(action=action, active_buddy=active_buddy)

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
