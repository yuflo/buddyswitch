#!/usr/bin/env python3
"""Runless comment services for broker-routed env.tool operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from .tool import DEFINITION
from env.tool_runtime import results as tool_results


_ACTION_DEFINITION_MAP = {
    'actions': [
        {
            'name': row.name,
            'payload_fields': [
                field
                for field in (row.input_schema.get('properties') or {})
                if isinstance(field, str)
            ],
        }
        for row in DEFINITION.actions
    ]
}

class CommentServiceContext(TypedDict):
    active_role: str
    active_actor: dict[str, Any]
    actor_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _allowed(action: str) -> set[str]:
    _, action_name = action.split(".", 1)
    for row in _ACTION_DEFINITION_MAP.get("actions", []):
        if isinstance(row, dict) and row.get("name") == action_name:
            return {field for field in row.get("payload_fields", []) if isinstance(field, str)}
    return set()


def _reject_payload(
    *,
    action: str,
    active_actor: dict[str, Any],
    active_role: str,
    message: str,
    correctable_fields: list[str] | None = None,
    field_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="comment",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
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
        field_errors=field_errors,
    )


def _reject_scope(
    *,
    action: str,
    active_actor: dict[str, Any],
    active_role: str,
    code: str,
    boundary: str,
    message: str,
    retryable: bool = False,
    correctable_fields: list[str] | None = None,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="comment",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        code=code,
        message=message,
        permission_boundary=boundary,
        human_summary="Comment target scope denied.",
        why_blocked=message,
        impact="No comments were created or changed.",
        state_changed=False,
        retryable=retryable,
        retry_guidance="Fix target scope and retry." if retryable else "This action cannot be retried as-is.",
        allowed_next_actions=["Use track.open or artifact.get to verify target readability first."],
        correctable_fields=correctable_fields,
    )


def _manifest_roles(manifest: dict[str, Any]) -> set[str]:
    roles = manifest.get("roles")
    if isinstance(roles, dict):
        return {key for key in roles if isinstance(key, str) and key}
    if isinstance(roles, list):
        ids: set[str] = set()
        for row in roles:
            if not isinstance(row, dict):
                continue
            role_id = row.get("id")
            if isinstance(role_id, str) and role_id:
                ids.add(role_id)
        return ids
    return set()


def _actor_address_payload(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    unknown = sorted(key for key in value if key not in {"actor_id", "role_id"})
    if unknown:
        raise ValueError(f"{field} contains unsupported fields: {', '.join(unknown)}")
    actor_id = value.get("actor_id")
    role_id = value.get("role_id")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ValueError(f"{field}.actor_id must be a non-empty string")
    if not isinstance(role_id, str) or not role_id.strip():
        raise ValueError(f"{field}.role_id must be a non-empty string")
    return {"actor_id": actor_id.strip(), "role_id": role_id.strip()}


def _normalize_target(
    args: dict[str, Any],
    active_role: str,
    action: str,
    context: CommentServiceContext,
) -> tuple[str, str] | dict[str, Any]:
    try:
        return context.rules.comment_target.normalize_target(args)
    except context.rules.comment_target.CommentTargetPayloadError as exc:
        return _reject_payload(
            action=action,
            active_actor=context["active_actor"],
            active_role=active_role,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )


def _ensure_target_readable(
    target_type: str,
    target_id: str,
    active_role: str,
    action: str,
    context: CommentServiceContext,
) -> dict[str, Any] | None:
    try:
        context.rules.comment_target.assert_target_readable(
            target_type=target_type,
            target_id=target_id,
            active_role=active_role,
            active_actor=context["active_actor"],
            action=action,
        )
    except context.rules.comment_target.CommentTargetPayloadError as exc:
        return _reject_payload(
            action=action,
            active_actor=context["active_actor"],
            active_role=active_role,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )
    except context.rules.comment_target.CommentTargetScopeError as exc:
        return _reject_scope(
            action=action,
            active_actor=context["active_actor"],
            active_role=active_role,
            code=exc.code,
            boundary=exc.permission_boundary,
            message=str(exc),
            retryable=exc.retryable,
            correctable_fields=exc.correctable_fields,
        )
    return None


def _normalize_mentioned_actors(
    *,
    mentioned_actors: Any,
    active_actor: dict[str, Any],
    active_role: str,
    action: str,
    manifest: dict[str, Any],
) -> list[dict[str, str]] | dict[str, Any]:
    if mentioned_actors is None:
        return []
    if not isinstance(mentioned_actors, list):
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="mentioned_actors must be a list",
            correctable_fields=["mentioned_actors"],
            field_errors=[
                {
                    "path": "mentioned_actors",
                    "message": "mentioned_actors must be a list of actor address payloads",
                    "expected": [{"actor_id": "act-pm-example", "role_id": "pm"}],
                    "example": [{"actor_id": "act-pm-example", "role_id": "pm"}],
                }
            ],
        )
    roles = _manifest_roles(manifest)
    normalized: list[dict[str, str]] = []
    seen_actor_ids: set[str] = set()
    for row in mentioned_actors:
        try:
            actor = _actor_address_payload(row, "mentioned_actors entry")
        except ValueError as exc:
            return _reject_payload(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message=f"mentioned_actors entries must be actor address payloads: {exc}",
                correctable_fields=["mentioned_actors"],
                field_errors=[
                    {
                        "path": "mentioned_actors",
                        "message": "mentioned_actors entries must include actor_id and role_id only",
                        "expected": [{"actor_id": "act-pm-example", "role_id": "pm"}],
                        "example": [{"actor_id": "act-pm-example", "role_id": "pm"}],
                    }
                ],
            )
        role = actor["role_id"]
        if role not in roles:
            return _reject_payload(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message=f"unknown mentioned actor role: {role}",
                correctable_fields=["mentioned_actors"],
                field_errors=[
                    {
                        "path": "mentioned_actors",
                        "message": f"unknown mentioned actor role: {role}",
                        "allowed_values": sorted(roles),
                        "example": [{"actor_id": f"act-{sorted(roles)[0]}-example", "role_id": sorted(roles)[0]}],
                    }
                ],
            )
        if actor["actor_id"] not in seen_actor_ids:
            seen_actor_ids.add(actor["actor_id"])
            normalized.append(actor)
    return normalized


def _revision_chain_ids(artifact_id: str, context: CommentServiceContext) -> set[str]:
    return context.rules.comment_target.artifact_revision_chain_ids(artifact_id)


def _validate_reply_to(
    *,
    reply_to: Any,
    target_type: str,
    target_id: str,
    active_role: str,
    active_actor: dict[str, Any],
    action: str,
    context: CommentServiceContext,
) -> str | None | dict[str, Any]:
    if reply_to is None:
        return None
    if not isinstance(reply_to, str) or not reply_to.strip():
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="reply_to must be a non-empty string when provided",
            correctable_fields=["reply_to"],
        )
    reply_id = reply_to.strip()
    parent = context.repos.comment.get_comment(reply_id)
    if parent is None:
        return _reject_scope(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            code="E_COMMENT_REPLY_SCOPE",
            boundary="comment.reply_to_scope",
            message=f"reply_to comment not found: {reply_id}",
            retryable=True,
            correctable_fields=["reply_to"],
        )
    if parent.get("target_type") != target_type or parent.get("target_id") != target_id:
        return _reject_scope(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            code="E_COMMENT_REPLY_SCOPE",
            boundary="comment.reply_to_scope",
            message=f"reply_to comment '{reply_id}' belongs to a different target",
            retryable=True,
            correctable_fields=["reply_to"],
        )
    return reply_id


def add_comment(*, args: dict[str, Any], context: CommentServiceContext) -> dict[str, Any]:
    action = "comment.add"
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    manifest = context["manifest"]

    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=f"unsupported payload fields: {', '.join(unknown)}",
            correctable_fields=unknown,
        )

    target = _normalize_target(args, active_role, action, context)
    if isinstance(target, dict):
        return target
    target_type, target_id = target

    target_error = _ensure_target_readable(target_type, target_id, active_role, action, context)
    if isinstance(target_error, dict):
        return target_error

    content = args.get("content")
    if not isinstance(content, str) or not content.strip():
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="content must be a non-empty string",
            correctable_fields=["content"],
        )

    anchor = args.get("anchor")
    if target_type == "artifact_section":
        if not isinstance(anchor, str) or not anchor.strip():
            return _reject_payload(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message="anchor is required for target_type='artifact_section'",
                correctable_fields=["anchor"],
                field_errors=[
                    {
                        "path": "anchor",
                        "message": "anchor is required when target_type is artifact_section",
                        "expected": "non-empty string anchor id",
                        "example": "section:problem-statement",
                    }
                ],
            )
        anchor = anchor.strip()
    elif anchor is not None:
        if not isinstance(anchor, str) or not anchor.strip():
            return _reject_payload(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message="anchor must be a non-empty string when provided",
                correctable_fields=["anchor"],
            )
        anchor = anchor.strip()

    mentioned_actors = _normalize_mentioned_actors(
        mentioned_actors=args.get("mentioned_actors"),
        active_actor=active_actor,
        active_role=active_role,
        action=action,
        manifest=manifest,
    )
    if isinstance(mentioned_actors, dict):
        return mentioned_actors

    artifact_revision_id = args.get("artifact_revision_id")
    if artifact_revision_id is not None:
        if not isinstance(artifact_revision_id, str) or not artifact_revision_id.strip():
            return _reject_payload(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message="artifact_revision_id must be a non-empty string when provided",
                correctable_fields=["artifact_revision_id"],
            )
        artifact_revision_id = artifact_revision_id.strip()
        revision_chain = _revision_chain_ids(artifact_revision_id, context)
        if not revision_chain:
            return _reject_scope(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                code="E_COMMENT_TARGET_SCOPE",
                boundary="comment.artifact_revision_scope",
                message=f"artifact revision not found: {artifact_revision_id}",
                retryable=False,
                correctable_fields=["artifact_revision_id"],
            )
        target_chain = _revision_chain_ids(target_id, context)
        if not target_chain.intersection(revision_chain):
            return _reject_scope(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
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
        active_role=active_role,
        active_actor=active_actor,
        action=action,
        context=context,
    )
    if isinstance(reply_to, dict):
        return reply_to

    thread_id: str | None = None
    if isinstance(reply_to, str):
        parent = context.repos.comment.get_comment(reply_to)
        if isinstance(parent, dict):
            parent_thread = parent.get("thread_id")
            if isinstance(parent_thread, str):
                thread_id = parent_thread

    try:
        comment = context.repos.comment.create_comment(
            target_type=target_type,
            target_id=target_id,
            by_actor=active_actor,
            content=content.strip(),
            reply_to=reply_to,
            mentioned_actors=mentioned_actors,
            anchor=anchor if isinstance(anchor, str) else None,
            artifact_revision_id=artifact_revision_id if isinstance(artifact_revision_id, str) else None,
            thread_id=thread_id,
            status="open",
        )
    except (ValueError, OSError) as exc:
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message=str(exc))

    return tool_results.success(
        tool="comment",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
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
    active_role = context["active_role"]
    active_actor = context["active_actor"]

    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=f"unsupported payload fields: {', '.join(unknown)}",
            correctable_fields=unknown,
        )

    target = _normalize_target(args, active_role, action, context)
    if isinstance(target, dict):
        return target
    target_type, target_id = target

    target_error = _ensure_target_readable(target_type, target_id, active_role, action, context)
    if isinstance(target_error, dict):
        return target_error

    status_filter = args.get("status", "all")
    if not isinstance(status_filter, str) or status_filter not in {"open", "resolved", "all"}:
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="status must be one of open|resolved|all",
            correctable_fields=["status"],
        )

    matched = context.repos.comment.comments_for_target(target_type, target_id)
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

    return tool_results.success(
        tool="comment",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
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


def resolve_comment(*, args: dict[str, Any], context: CommentServiceContext) -> dict[str, Any]:
    action = "comment.resolve"
    active_role = context["active_role"]
    active_actor = context["active_actor"]

    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=f"unsupported payload fields: {', '.join(unknown)}",
            correctable_fields=unknown,
        )

    if active_role != "pm":
        return tool_results.rejection(
            tool="comment",
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            code="E_COMMENT_SCOPE",
            message="comment.resolve is PM-only",
            permission_boundary="comment.pm_review_authority",
            human_summary="Only PM can resolve comment threads.",
            why_blocked="comment.resolve requires active_role='pm'.",
            impact="No comments were changed.",
            state_changed=False,
            retryable=False,
            retry_guidance="Retry as active role pm.",
            allowed_next_actions=["Use comment.add to contribute evidence without closing the thread."],
            correctable_fields=["active_role"],
        )

    comment_id = args.get("comment_id")
    if not isinstance(comment_id, str) or not comment_id.strip():
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="comment_id must be a non-empty string",
            correctable_fields=["comment_id"],
        )
    comment_id = comment_id.strip()

    resolution_summary = args.get("resolution_summary")
    if not isinstance(resolution_summary, str) or not resolution_summary.strip():
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="resolution_summary must be a non-empty string",
            correctable_fields=["resolution_summary"],
        )
    resolution_summary = resolution_summary.strip()

    seed = context.repos.comment.get_comment(comment_id)
    if seed is None:
        return _reject_scope(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            code="E_COMMENT_THREAD_SCOPE",
            boundary="comment.thread_scope",
            message=f"comment not found: {comment_id}",
            retryable=True,
            correctable_fields=["comment_id"],
        )
    target_type = seed.get("target_type")
    target_id = seed.get("target_id")
    if not isinstance(target_type, str) or not isinstance(target_id, str):
        return _reject_scope(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            code="E_COMMENT_THREAD_SCOPE",
            boundary="comment.thread_scope",
            message=f"comment '{comment_id}' has invalid target linkage",
            retryable=False,
            correctable_fields=["comment_id"],
        )

    target_error = _ensure_target_readable(target_type, target_id, active_role, action, context)
    if isinstance(target_error, dict):
        return target_error

    try:
        resolved_rows = context.repos.comment.resolve_thread(
            comment_id=comment_id,
            resolved_by_actor=active_actor,
            resolution_summary=resolution_summary,
        )
    except ValueError as exc:
        message = str(exc)
        if "already resolved" in message:
            return tool_results.rejection(
                tool="comment",
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                code="E_COMMENT_STATE",
                message=message,
                permission_boundary="comment.state",
                human_summary="Comment thread is already fully resolved.",
                why_blocked=message,
                impact="No comments were changed.",
                state_changed=False,
                retryable=False,
                retry_guidance="Use comment.add to create a new thread if new feedback is needed.",
                allowed_next_actions=["Use comment.list to confirm thread status."],
                correctable_fields=["comment_id"],
            )
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message=message)

    updated_ids = [row.get("id") for row in resolved_rows if isinstance(row.get("id"), str)]
    return tool_results.success(
        tool="comment",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=f"Resolved thread containing comment '{comment_id}' with {len(updated_ids)} durable row update(s).",
        state_changed=True,
        durability="durable",
        updated_ids=updated_ids,
        state_changes=[
            {"object_type": "comment", "change": "resolved", "comment_id": row_id}
            for row_id in updated_ids
        ],
        allowed_next_actions=[
            "Use comment.list with status='resolved' to verify PM closure output.",
            "Use comment.add to open new discussion if unresolved issues remain.",
        ],
        extra={"comments": resolved_rows, "comment_id": comment_id},
    )


_ACTION_HANDLERS = {
    'add': add_comment,
    'list': list_comments,
    'resolve': resolve_comment,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    return handler(args=args, context=context)
