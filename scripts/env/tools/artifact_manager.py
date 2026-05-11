#!/usr/bin/env python3
"""Artifact tool dispatcher for env.tool broker envelope requests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from env.services import artifacts as artifact_service

_ACTION_MAP = {
    "list": artifact_service.list_artifacts_for_current_task,
    "get": artifact_service.get_artifact_for_active_buddy,
    "get_current": artifact_service.get_current_artifacts_for_active_task,
    "validate_payload": artifact_service.validate_artifact_payload,
    "create_revision": artifact_service.create_artifact_revision,
    "update_metadata": artifact_service.update_artifact_metadata,
}


def _payload_error(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "artifact",
        "action": action,
        "error": {
            "code": "E_ARTIFACT_PAYLOAD",
            "message": message,
        },
        "permission_boundary": "request-payload",
        "active_buddy": active_buddy,
        "allowed_next_actions": [
            'Send env.tool payload as {"tool":"artifact","action":"<action>","args":{...}}.',
            "Use one supported action: list, get, get_current, validate_payload, create_revision, update_metadata.",
        ],
    }


def _unknown_action_error(*, action: str, active_buddy: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "artifact",
        "action": action,
        "error": {
            "code": "E_ARTIFACT_ACTION",
            "message": f"unsupported artifact action: {action}",
        },
        "permission_boundary": "request-payload",
        "active_buddy": active_buddy,
        "allowed_next_actions": [
            "Use one supported action: list, get, get_current, validate_payload, create_revision, update_metadata.",
            "Check prepare.runtime_context.env_tools.artifact_manager for command and payload hints.",
        ],
    }


def dispatch_artifact_manager_request(
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
            action="artifact.unknown",
            active_buddy=active_buddy,
            message="env.tool payload.action must be a non-empty string",
        )
    action_name = raw_action.strip().replace("-", "_")
    action = f"artifact.{action_name}"

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

    context: artifact_service.ArtifactServiceContext = {
        "active_buddy": active_buddy,
        "instance_id": instance_id,
        "instance_json": instance_json,
        "instance_payload": instance_payload,
        "manifest": manifest,
    }
    response = handler(args=args, context=context)
    if isinstance(response, dict):
        response.setdefault("tool", "artifact")
    return response
