#!/usr/bin/env python3
"""Runless comment services for broker-routed env.tool operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.services import artifact_visibility
from env.tools import responses as tool_responses


class CommentServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


_ADD_FIELDS = {"target_type", "target_id", "content", "reply_to"}
_LIST_FIELDS = {"target_type", "target_id"}
_TARGET_TYPES = {"track", "artifact"}


def _allowed(action: str) -> set[str]:
    if action == "comment.add":
        return _ADD_FIELDS
    if action == "comment.list":
        return _LIST_FIELDS
    return set()


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    correctable_fields: list[str] | None = None
    if "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            correctable_fields = [row.strip() for row in suffix.split(",") if row.strip()]
    elif "target_type" in message:
        correctable_fields = ["target_type"]
    elif "target_id" in message:
        correctable_fields = ["target_id"]
    elif "content" in message:
        correctable_fields = ["content"]
    elif "reply_to" in message:
        correctable_fields = ["reply_to"]
    return tool_responses.rejection(
        tool="comment",
        action=action,
        active_buddy=active_buddy,
        code="E_COMMENT_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Comment request payload is invalid.",
        why_blocked=message,
        impact="No comments were created or changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix the comment payload fields and retry.",
        allowed_next_actions=[
            "Use comment.list to view existing comments on the target.",
            "Retry with only documented comment payload fields.",
        ],
        correctable_fields=correctable_fields,
    )


def _reject_target_scope(
    *,
    action: str,
    active_buddy: str,
    code: str,
    message: str,
    permission_boundary: str,
    human_summary: str,
    why_blocked: str,
    retryable: bool = True,
    correctable_fields: list[str] | None = None,
) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="comment",
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=permission_boundary,
        human_summary=human_summary,
        why_blocked=why_blocked,
        impact="No comments were created or changed.",
        state_changed=False,
        retryable=retryable,
        retry_guidance="Fix the target scope issue and retry." if retryable else "This action cannot be retried as-is.",
        allowed_next_actions=[
            "Use context.summarize to inspect available tracks and artifacts.",
            "Use track.get or artifact.get to verify the target is readable.",
        ],
        correctable_fields=correctable_fields,
    )


def _reject_reply_scope(
    *,
    action: str,
    active_buddy: str,
    code: str,
    message: str,
    permission_boundary: str,
    human_summary: str,
    why_blocked: str,
) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="comment",
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=permission_boundary,
        human_summary=human_summary,
        why_blocked=why_blocked,
        impact="No comments were created or changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix the reply_to reference and retry.",
        allowed_next_actions=[
            "Use comment.list to view existing comments on the target and pick a valid reply_to id.",
        ],
        correctable_fields=["reply_to"],
    )


def _normalize_target(
    args: dict[str, Any], active_buddy: str, action: str
) -> tuple[str, str] | dict[str, Any]:
    target_type = args.get("target_type")
    if not isinstance(target_type, str) or not target_type.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="target_type is required")
    target_type = target_type.strip()
    if target_type not in _TARGET_TYPES:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"unsupported target_type: {target_type}; must be 'track' or 'artifact'",
        )

    target_id = args.get("target_id")
    if not isinstance(target_id, str) or not target_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="target_id is required")
    target_id = target_id.strip()

    return (target_type, target_id)


def _readable_target(
    target_type: str, target_id: str, active_buddy: str, action: str
) -> dict[str, Any] | dict[str, Any]:
    """Returns the target dict on success or a rejection dict on failure."""
    if target_type == "track":
        result = artifact_visibility.assert_track_readable(
            target_id, active_buddy=active_buddy, action=action
        )
        if not result.get("ok"):
            return _reject_target_scope(
                action=action,
                active_buddy=active_buddy,
                code=result.get("code", "E_COMMENT_TARGET_SCOPE"),
                message=result.get("message", f"track '{target_id}' is not readable"),
                permission_boundary=result.get("permission_boundary", "track.lifecycle_status"),
                human_summary="Target track is not readable.",
                why_blocked=result.get("message", "Track is not readable."),
                retryable=False if result.get("permission_boundary") == "track.lifecycle_status" else True,
                correctable_fields=["target_id"],
            )
        return result["track"]

    if target_type == "artifact":
        artifact = env_store.get_artifact(target_id)
        if artifact is None:
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message=f"artifact not found: {target_id}",
            )
        decision = artifact_visibility.artifact_read_decision(artifact, active_buddy)
        if not decision.get("allowed"):
            return _reject_target_scope(
                action=action,
                active_buddy=active_buddy,
                code="E_COMMENT_TARGET_SCOPE",
                message=decision.get("why", "artifact is not readable"),
                permission_boundary=decision.get("permission_boundary", "artifact.track_relation"),
                human_summary="Target artifact is not readable by the active buddy.",
                why_blocked=decision.get("why", "Artifact read boundary denied access."),
                retryable=False,
                correctable_fields=["target_id"],
            )
        return artifact

    return _reject_payload(
        action=action,
        active_buddy=active_buddy,
        message=f"unsupported target_type: {target_type}",
    )


def _validate_reply_to(
    reply_to: Any,
    target_type: str,
    target_id: str,
    active_buddy: str,
    action: str,
) -> str | None | dict[str, Any]:
    """Returns the reply_to id (or None) on success, or a rejection dict on failure."""
    if reply_to is None:
        return None

    if not isinstance(reply_to, str) or not reply_to.strip():
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="reply_to must be a non-empty string when provided",
        )

    reply_id = reply_to.strip()
    referenced = env_store.get_comment(reply_id)
    if referenced is None:
        return _reject_reply_scope(
            action=action,
            active_buddy=active_buddy,
            code="E_COMMENT_REPLY_SCOPE",
            message=f"reply_to references a comment that does not exist: {reply_id}",
            permission_boundary="comment.reply_to_scope",
            human_summary="The referenced comment was not found.",
            why_blocked="reply_to must reference an existing comment on the same target.",
        )

    if referenced.get("target_type") != target_type or referenced.get("target_id") != target_id:
        return _reject_reply_scope(
            action=action,
            active_buddy=active_buddy,
            code="E_COMMENT_REPLY_SCOPE",
            message=f"reply_to comment '{reply_id}' is attached to a different target",
            permission_boundary="comment.reply_to_scope",
            human_summary="Reply must stay on the same target discussion.",
            why_blocked="reply_to must reference a comment on the same target_type and target_id.",
        )

    return reply_id


def add_comment(*, args: dict[str, Any], context: CommentServiceContext) -> dict[str, Any]:
    action = "comment.add"
    active_buddy = context["active_buddy"]

    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"unsupported payload fields: {', '.join(unknown)}",
        )

    target = _normalize_target(args, active_buddy, action)
    if isinstance(target, dict):
        return target
    target_type, target_id = target

    readable = _readable_target(target_type, target_id, active_buddy, action)
    if isinstance(readable, dict) and readable.get("ok") is False:
        return readable

    content_value = args.get("content")
    if not isinstance(content_value, str) or not content_value.strip():
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="content must be a non-empty string after trimming",
        )

    reply_result = _validate_reply_to(
        args.get("reply_to"), target_type, target_id, active_buddy, action
    )
    if isinstance(reply_result, dict):
        return reply_result

    try:
        comment = env_store.create_comment(
            target_type=target_type,
            target_id=target_id,
            author_buddy=active_buddy,
            content=content_value.strip(),
            reply_to=reply_result,
        )
    except (ValueError, OSError) as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_responses.success(
        tool="comment",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Added one durable comment to {target_type} '{target_id}'.",
        state_changed=True,
        durability="durable",
        created_ids=[comment["id"]],
        state_changes=[
            {
                "object_type": "comment",
                "change": "added",
                "comment_id": comment["id"],
                "target_type": target_type,
                "target_id": target_id,
            },
        ],
        allowed_next_actions=[
            "Use comment.list to view all comments on this target.",
        ],
        extra={
            "comment_id": comment["id"],
            "comment": comment,
            "target_type": target_type,
            "target_id": target_id,
        },
    )


def list_comments(*, args: dict[str, Any], context: CommentServiceContext) -> dict[str, Any]:
    action = "comment.list"
    active_buddy = context["active_buddy"]

    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"unsupported payload fields: {', '.join(unknown)}",
        )

    target = _normalize_target(args, active_buddy, action)
    if isinstance(target, dict):
        return target
    target_type, target_id = target

    readable = _readable_target(target_type, target_id, active_buddy, action)
    if isinstance(readable, dict) and readable.get("ok") is False:
        return readable

    all_comments = env_store.list_comments()
    # Only return comments whose stored target_type and target_id match
    matched = [
        cmt
        for cmt in all_comments
        if cmt.get("target_type") == target_type and cmt.get("target_id") == target_id
    ]

    read_scope = (
        "target comments for readable track"
        if target_type == "track"
        else "target comments for readable artifact"
    )

    return tool_responses.success(
        tool="comment",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Returned {len(matched)} comment(s) for {target_type} '{target_id}'.",
        state_changed=False,
        durability="none",
        read_scope=read_scope,
        allowed_next_actions=[
            "Use comment.add to add a new comment to this target.",
        ],
        extra={
            "comments": matched,
            "target_type": target_type,
            "target_id": target_id,
            "discovery_summary": {"count": len(matched)},
        },
    )
