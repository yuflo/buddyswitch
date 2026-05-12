#!/usr/bin/env python3
"""Handoff validation service for broker-routed env.tool operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.tools import responses as tool_responses

_IDENTITY_FIELDS = {"active_buddy", "buddy", "instance_id"}
_VALIDATE_FIELDS = {"next_buddy", "reason", "context", "track_id"} | _IDENTITY_FIELDS


class HandoffServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _known_buddy_ids(manifest: dict[str, Any]) -> set[str]:
    return {
        buddy.get("id")
        for buddy in manifest.get("buddies", [])
        if isinstance(buddy, dict) and isinstance(buddy.get("id"), str)
    }


def _error_payload(
    *,
    action: str,
    active_buddy: str,
    code: str,
    message: str,
    permission_boundary: str,
    allowed_next_actions: list[str],
    allowed_next_action_options: list[dict[str, Any]] | None = None,
    track_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "tool": "handoff",
        "action": action,
        "error": {
            "code": code,
            "message": message,
        },
        "permission_boundary": permission_boundary,
        "active_buddy": active_buddy,
        "allowed_next_actions": allowed_next_actions,
    }
    if isinstance(allowed_next_action_options, list):
        payload["allowed_next_action_options"] = allowed_next_action_options
    if isinstance(track_id, str) and track_id.strip():
        payload["track_id"] = track_id.strip()
    if isinstance(extra, dict):
        payload.update(extra)
    return payload


def _payload_error(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_HANDOFF_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        allowed_next_actions=[
            "Provide next_buddy, reason, and context as non-empty strings.",
            "Remove handoff when no cross-buddy continuation is needed.",
        ],
        allowed_next_action_options=[
            tool_responses.next_action_option(
                tool="context",
                action="summarize",
                option_id="summarize_context_before_handoff",
                reason="Summarize context before validating handoff payload.",
            ),
            tool_responses.next_action_option(
                tool="track",
                action="list",
                option_id="inspect_tracks_before_handoff",
                reason="Inspect track context before selecting handoff target.",
            ),
        ],
    )


def _discoverability() -> dict[str, Any]:
    return {
        "will_be_discoverable_by_next_buddy": True,
        "discovery_basis": "persisted_run_audit_handoff",
        "available_after": "run.commit",
        "discovery_surfaces": ["track.list", "track.get", "context.summarize"],
    }


def _ensure_allowed_fields(
    *,
    action: str,
    active_buddy: str,
    args: dict[str, Any],
    allowed_fields: set[str],
) -> dict[str, Any] | None:
    unknown = sorted(key for key in args.keys() if key not in allowed_fields)
    if not unknown:
        return None
    return _payload_error(
        action=action,
        active_buddy=active_buddy,
        message=f"unsupported payload fields: {', '.join(unknown)}",
    )


def _normalize_handoff_args(
    *,
    action: str,
    args: dict[str, Any],
    context: HandoffServiceContext,
) -> tuple[dict[str, str] | None, dict[str, Any] | None]:
    next_buddy = args.get("next_buddy")
    reason = args.get("reason")
    handoff_context = args.get("context")
    if not isinstance(next_buddy, str) or not next_buddy.strip():
        return None, _payload_error(
            action=action,
            active_buddy=context["active_buddy"],
            message="next_buddy must be a non-empty string",
        )
    if not isinstance(reason, str) or not reason.strip():
        return None, _payload_error(
            action=action,
            active_buddy=context["active_buddy"],
            message="reason must be a non-empty string",
        )
    if not isinstance(handoff_context, str) or not handoff_context.strip():
        return None, _payload_error(
            action=action,
            active_buddy=context["active_buddy"],
            message="context must be a non-empty string",
        )

    normalized = {
        "next_buddy": next_buddy.strip(),
        "reason": reason.strip(),
        "context": handoff_context.strip(),
    }
    known_buddies = _known_buddy_ids(context["manifest"])
    if normalized["next_buddy"] not in known_buddies:
        return None, _error_payload(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_HANDOFF_TARGET",
            message=f"handoff.next_buddy must reference a manifest buddy id; got '{normalized['next_buddy']}'",
            permission_boundary="manifest.buddies",
            allowed_next_actions=[
                "Use one of the manifest buddy ids as next_buddy.",
                "Remove handoff if no valid target exists.",
            ],
            allowed_next_action_options=[
                tool_responses.next_action_option(
                    tool="context",
                    action="summarize",
                    option_id="summarize_context_before_target_retry",
                    reason="Summarize context before retrying handoff target selection.",
                ),
            ],
            extra={"handoff_targets": sorted(known_buddies)},
        )
    return normalized, None


def _track_id_from_args_or_binding(args: dict[str, Any], context: HandoffServiceContext) -> tuple[str | None, str | None]:
    raw_track_id = args.get("track_id")
    if raw_track_id is None:
        raw_track_id = context["instance_payload"].get("current_track_id")
    if raw_track_id is None:
        return None, None
    if not isinstance(raw_track_id, str) or not raw_track_id.strip():
        return None, "track_id must be a non-empty string when provided"
    try:
        return env_store.require_id(raw_track_id.strip(), "track id"), None
    except ValueError as exc:
        return None, str(exc)


def validate_handoff(*, args: dict[str, Any], context: HandoffServiceContext) -> dict[str, Any]:
    action = "handoff.validate"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_VALIDATE_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    handoff, error = _normalize_handoff_args(action=action, args=args, context=context)
    if error is not None:
        return error
    assert handoff is not None

    track_id, track_parse_error = _track_id_from_args_or_binding(args, context)
    if track_parse_error is not None:
        return _payload_error(action=action, active_buddy=context["active_buddy"], message=track_parse_error)
    track_alignment: dict[str, Any] = {
        "track_id": track_id,
        "requested_next_buddy": handoff["next_buddy"],
        "track_next_buddy": None,
        "target_matches_track_next_buddy": True,
    }
    discoverability = _discoverability()
    if track_id is not None:
        track = env_store.get_track(track_id)
        if track is None:
            return _error_payload(
                action=action,
                active_buddy=context["active_buddy"],
                code="E_TRACK_NOT_FOUND",
                message=f"track not found: {track_id}",
                permission_boundary="track.lookup",
                track_id=track_id,
                allowed_next_actions=[
                    "Use track.list to inspect available track ids.",
                    "Validate handoff without track_id when no track is bound.",
                ],
                allowed_next_action_options=[
                    tool_responses.next_action_option(
                        tool="track",
                        action="list",
                        option_id="list_tracks_for_handoff_validation",
                        reason="Inspect available tracks before validating handoff target.",
                    ),
                ],
            )
        next_buddy = track.get("next_buddy")
        normalized_track_next = next_buddy.strip() if isinstance(next_buddy, str) and next_buddy.strip() else None
        track_alignment["track_next_buddy"] = normalized_track_next
        if isinstance(next_buddy, str) and next_buddy.strip() and next_buddy.strip() != handoff["next_buddy"]:
            track_alignment["target_matches_track_next_buddy"] = False
            track_alignment["suggested_next_buddy"] = next_buddy.strip()
            return _error_payload(
                action=action,
                active_buddy=context["active_buddy"],
                code="E_HANDOFF_TRACK_TRANSITION",
                message=(
                    f"handoff target '{handoff['next_buddy']}' conflicts with track next_buddy "
                    f"'{next_buddy.strip()}'"
                ),
                permission_boundary="handoff.track_transition",
                track_id=track_id,
                allowed_next_actions=[
                    "Use the track next_buddy as the handoff target.",
                    "Ask PM to advance the track before handing off to a different buddy.",
                ],
                allowed_next_action_options=[
                    tool_responses.next_action_option(
                        tool="track",
                        action="get",
                        option_id="inspect_track_transition_before_handoff",
                        reason="Inspect track transition state before retrying handoff target.",
                    ),
                    tool_responses.next_action_option(
                        tool="context",
                        action="summarize",
                        option_id="summarize_context_before_handoff_retry",
                        reason="Summarize context before retrying conflicting handoff target.",
                    ),
                ],
                extra={
                    "track_alignment": track_alignment,
                    "discoverability": discoverability,
                },
            )

    return {
        "ok": True,
        "tool": "handoff",
        "action": action,
        "active_buddy": context["active_buddy"],
        "track_id": track_id,
        "handoff": handoff,
        "track_alignment": track_alignment,
        "discoverability": discoverability,
        "allowed_next_actions": [
            "Include this handoff object in the next persist result when a transfer is needed.",
            "Use context.get to inspect current task and track context.",
        ],
        "allowed_next_action_options": [
            tool_responses.next_action_option(
                tool="run",
                action="commit",
                option_id="commit_handoff_to_run_audit",
                reason="Commit this validated handoff to make it discoverable for the next buddy.",
            ),
            tool_responses.next_action_option(
                tool="context",
                action="get",
                option_id="inspect_context_before_handoff_commit",
                reason="Inspect full context before committing handoff.",
            ),
        ],
    }
