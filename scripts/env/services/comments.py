#!/usr/bin/env python3
"""Runless comment services for broker-routed env.tool operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from env.domain import comment_targets as comment_target_domain
from env.repos import comments as comment_repo
from env.tools import contracts as tool_contracts
from env.tools import responses as tool_responses


class CommentServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _allowed(action: str) -> set[str]:
    tool, action_name = action.split(".", 1)
    return tool_contracts.payload_fields_for_action(tool, action_name)


def _reject_payload(
    *,
    action: str,
    active_buddy: str,
    message: str,
    correctable_fields: list[str] | None = None,
) -> dict[str, Any]:
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
        retry_guidance="Fix comment payload fields and retry.",
        allowed_next_actions=["Use comment.list to inspect current threads on the target."],
        correctable_fields=correctable_fields,
    )


def _reject_scope(
    *,
    action: str,
    active_buddy: str,
    code: str,
    boundary: str,
    message: str,
    retryable: bool = False,
    correctable_fields: list[str] | None = None,
) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="comment",
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=boundary,
        human_summary="Comment target scope denied.",
        why_blocked=message,
        impact="No comments were created or changed.",
        state_changed=False,
        retryable=retryable,
        retry_guidance="Fix target scope and retry." if retryable else "This action cannot be retried as-is.",
        allowed_next_actions=["Use track.get or artifact.get to verify target readability first."],
        correctable_fields=correctable_fields,
    )


def _manifest_buddies(manifest: dict[str, Any]) -> set[str]:
    buddies = manifest.get("buddies")
    if isinstance(buddies, dict):
        return {key for key in buddies if isinstance(key, str) and key}
    if isinstance(buddies, list):
        ids: set[str] = set()
        for row in buddies:
            if not isinstance(row, dict):
                continue
            buddy_id = row.get("id")
            if isinstance(buddy_id, str) and buddy_id:
                ids.add(buddy_id)
        return ids
    return set()


def _normalize_target(args: dict[str, Any], active_buddy: str, action: str) -> tuple[str, str] | dict[str, Any]:
    try:
        return comment_target_domain.normalize_target(args)
    except comment_target_domain.CommentTargetPayloadError as exc:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )


def _ensure_target_readable(target_type: str, target_id: str, active_buddy: str, action: str) -> dict[str, Any] | None:
    try:
        comment_target_domain.assert_target_readable(
            target_type=target_type,
            target_id=target_id,
            active_buddy=active_buddy,
            action=action,
        )
    except comment_target_domain.CommentTargetPayloadError as exc:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )
    except comment_target_domain.CommentTargetScopeError as exc:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            code=exc.code,
            boundary=exc.permission_boundary,
            message=str(exc),
            retryable=exc.retryable,
            correctable_fields=exc.correctable_fields,
        )
    return None


def _normalize_mentions(
    *,
    mentions: Any,
    active_buddy: str,
    action: str,
    manifest: dict[str, Any],
) -> list[str] | dict[str, Any]:
    if mentions is None:
        return []
    if not isinstance(mentions, list):
        return _reject_payload(action=action, active_buddy=active_buddy, message="mentions must be a list", correctable_fields=["mentions"])
    buddies = _manifest_buddies(manifest)
    normalized: list[str] = []
    for row in mentions:
        if not isinstance(row, str) or not row.strip():
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message="mentions entries must be non-empty strings",
                correctable_fields=["mentions"],
            )
        buddy = row.strip()
        if buddy not in buddies:
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message=f"unknown mention buddy: {buddy}",
                correctable_fields=["mentions"],
            )
        if buddy not in normalized:
            normalized.append(buddy)
    return normalized


def _revision_chain_ids(artifact_id: str) -> set[str]:
    return comment_target_domain.artifact_revision_chain_ids(artifact_id)


def _validate_reply_to(
    *,
    reply_to: Any,
    target_type: str,
    target_id: str,
    active_buddy: str,
    action: str,
) -> str | None | dict[str, Any]:
    if reply_to is None:
        return None
    if not isinstance(reply_to, str) or not reply_to.strip():
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="reply_to must be a non-empty string when provided",
            correctable_fields=["reply_to"],
        )
    reply_id = reply_to.strip()
    parent = comment_repo.get_comment(reply_id)
    if parent is None:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            code="E_COMMENT_REPLY_SCOPE",
            boundary="comment.reply_to_scope",
            message=f"reply_to comment not found: {reply_id}",
            retryable=True,
            correctable_fields=["reply_to"],
        )
    if parent.get("target_type") != target_type or parent.get("target_id") != target_id:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            code="E_COMMENT_REPLY_SCOPE",
            boundary="comment.reply_to_scope",
            message=f"reply_to comment '{reply_id}' belongs to a different target",
            retryable=True,
            correctable_fields=["reply_to"],
        )
    return reply_id


def add_comment(*, args: dict[str, Any], context: CommentServiceContext) -> dict[str, Any]:
    action = "comment.add"
    active_buddy = context["active_buddy"]
    manifest = context["manifest"]

    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"unsupported payload fields: {', '.join(unknown)}",
            correctable_fields=unknown,
        )

    target = _normalize_target(args, active_buddy, action)
    if isinstance(target, dict):
        return target
    target_type, target_id = target

    target_error = _ensure_target_readable(target_type, target_id, active_buddy, action)
    if isinstance(target_error, dict):
        return target_error

    content = args.get("content")
    if not isinstance(content, str) or not content.strip():
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="content must be a non-empty string",
            correctable_fields=["content"],
        )

    anchor = args.get("anchor")
    if target_type == "artifact_section":
        if not isinstance(anchor, str) or not anchor.strip():
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message="anchor is required for target_type='artifact_section'",
                correctable_fields=["anchor"],
            )
        anchor = anchor.strip()
    elif anchor is not None:
        if not isinstance(anchor, str) or not anchor.strip():
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message="anchor must be a non-empty string when provided",
                correctable_fields=["anchor"],
            )
        anchor = anchor.strip()

    mentions = _normalize_mentions(
        mentions=args.get("mentions"),
        active_buddy=active_buddy,
        action=action,
        manifest=manifest,
    )
    if isinstance(mentions, dict):
        return mentions

    artifact_revision_id = args.get("artifact_revision_id")
    if artifact_revision_id is not None:
        if not isinstance(artifact_revision_id, str) or not artifact_revision_id.strip():
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message="artifact_revision_id must be a non-empty string when provided",
                correctable_fields=["artifact_revision_id"],
            )
        artifact_revision_id = artifact_revision_id.strip()
        revision_chain = _revision_chain_ids(artifact_revision_id)
        if not revision_chain:
            return _reject_scope(
                action=action,
                active_buddy=active_buddy,
                code="E_COMMENT_TARGET_SCOPE",
                boundary="comment.artifact_revision_scope",
                message=f"artifact revision not found: {artifact_revision_id}",
                retryable=False,
                correctable_fields=["artifact_revision_id"],
            )
        target_chain = _revision_chain_ids(target_id)
        if not target_chain.intersection(revision_chain):
            return _reject_scope(
                action=action,
                active_buddy=active_buddy,
                code="E_COMMENT_TARGET_SCOPE",
                boundary="comment.artifact_revision_scope",
                message=f"artifact revision '{artifact_revision_id}' is not in the target revision chain",
                retryable=False,
                correctable_fields=["artifact_revision_id"],
            )

    reply_to = _validate_reply_to(
        reply_to=args.get("reply_to"),
        target_type=target_type,
        target_id=target_id,
        active_buddy=active_buddy,
        action=action,
    )
    if isinstance(reply_to, dict):
        return reply_to

    thread_id: str | None = None
    if isinstance(reply_to, str):
        parent = comment_repo.get_comment(reply_to)
        if isinstance(parent, dict):
            parent_thread = parent.get("thread_id")
            if isinstance(parent_thread, str):
                thread_id = parent_thread

    try:
        comment = comment_repo.create_comment(
            target_type=target_type,
            target_id=target_id,
            by_buddy=active_buddy,
            content=content.strip(),
            reply_to=reply_to,
            mentions=mentions,
            anchor=anchor if isinstance(anchor, str) else None,
            artifact_revision_id=artifact_revision_id if isinstance(artifact_revision_id, str) else None,
            thread_id=thread_id,
            status="open",
        )
    except (ValueError, OSError) as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_responses.success(
        tool="comment",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Added one durable comment on {target_type} '{target_id}'.",
        state_changed=True,
        durability="durable",
        created_ids=[comment["id"]],
        state_changes=[{"object_type": "comment", "change": "added", "comment_id": comment["id"]}],
        allowed_next_actions=["Use comment.list for thread view.", "Use comment.add to continue the thread."],
        extra={"comment_id": comment["id"], "comment": comment, "target_type": target_type, "target_id": target_id},
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
            correctable_fields=unknown,
        )

    target = _normalize_target(args, active_buddy, action)
    if isinstance(target, dict):
        return target
    target_type, target_id = target

    target_error = _ensure_target_readable(target_type, target_id, active_buddy, action)
    if isinstance(target_error, dict):
        return target_error

    status_filter = args.get("status", "all")
    if not isinstance(status_filter, str) or status_filter not in {"open", "resolved", "all"}:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="status must be one of open|resolved|all",
            correctable_fields=["status"],
        )

    matched = comment_repo.comments_for_target(target_type, target_id)
    if status_filter != "all":
        matched = [row for row in matched if row.get("status") == status_filter]
    matched.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))

    threads_map: dict[str, list[dict[str, Any]]] = {}
    for row in matched:
        thread_id = row.get("thread_id")
        if not isinstance(thread_id, str) or not thread_id:
            thread_id = str(row.get("id") or "")
        threads_map.setdefault(thread_id, []).append(row)

    threads: list[dict[str, Any]] = []
    open_count = 0
    resolved_count = 0
    for thread_id, rows in threads_map.items():
        rows.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))
        statuses = {row.get("status") for row in rows}
        thread_status = "resolved" if statuses == {"resolved"} else "open"
        if thread_status == "resolved":
            resolved_count += len(rows)
        else:
            open_count += len(rows)
        threads.append(
            {
                "thread_id": thread_id,
                "target_type": target_type,
                "target_id": target_id,
                "status": thread_status,
                "comments": rows,
            }
        )
    threads.sort(key=lambda row: row.get("thread_id") or "")

    return tool_responses.success(
        tool="comment",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Returned {len(matched)} comment(s) for {target_type} '{target_id}'.",
        state_changed=False,
        durability="none",
        read_scope=f"comment threads for {target_type} target",
        allowed_next_actions=["Use comment.add to continue discussion."],
        extra={
            "comments": matched,
            "threads": threads,
            "status_counts": {"open": open_count, "resolved": resolved_count},
            "target_type": target_type,
            "target_id": target_id,
        },
    )
