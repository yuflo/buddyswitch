#!/usr/bin/env python3
"""Runless request services for broker-routed env.tool operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from .tool import DEFINITION
from env.tool_runtime import results as tool_results


_ACTION_DEFINITION_MAP = {
    "actions": [
        {
            "name": row.name,
            "payload_fields": [
                field
                for field in (row.input_schema.get("properties") or {})
                if isinstance(field, str)
            ],
        }
        for row in DEFINITION.actions
    ]
}


class RequestServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
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
    active_buddy: str,
    message: str,
    correctable_fields: list[str] | None = None,
    field_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="request",
        action=action,
        active_buddy=active_buddy,
        code="E_REQUEST_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Request payload is invalid.",
        why_blocked=message,
        impact="No request object changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix payload fields and retry.",
        allowed_next_actions=[
            "Use context.get.tool_catalog['request'] for request payload fields and semantics.",
            "Use request.list to inspect visible request ids before mutation actions.",
        ],
        correctable_fields=correctable_fields,
        field_errors=field_errors,
    )


def _reject_scope(
    *,
    action: str,
    active_buddy: str,
    code: str,
    boundary: str,
    message: str,
    human_summary: str,
    why_blocked: str,
    retryable: bool = False,
    correctable_fields: list[str] | None = None,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="request",
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=boundary,
        human_summary=human_summary,
        why_blocked=why_blocked,
        impact="No request object changed.",
        state_changed=False,
        retryable=retryable,
        retry_guidance="Fix scope boundary and retry." if retryable else "This action cannot run as requested.",
        allowed_next_actions=[
            "Use request.get with a visible request_id to inspect current lifecycle fields.",
            "Use request.list to discover requests you can read.",
        ],
        correctable_fields=correctable_fields,
    )


def _reject_state(
    *,
    action: str,
    active_buddy: str,
    message: str,
    correctable_fields: list[str] | None = None,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="request",
        action=action,
        active_buddy=active_buddy,
        code="E_REQUEST_STATE",
        message=message,
        permission_boundary="request.state",
        human_summary="Request lifecycle state does not allow this mutation.",
        why_blocked=message,
        impact="No request object changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Inspect request status and use an allowed state transition.",
        allowed_next_actions=[
            "Use request.get to inspect current status before retrying.",
        ],
        correctable_fields=correctable_fields,
    )


def _assert_track_readable(*, track_id: str, action: str, active_buddy: str, context: RequestServiceContext) -> dict[str, Any]:
    try:
        return context.rules.comment_target.assert_target_readable(
            target_type="track",
            target_id=track_id,
            active_buddy=active_buddy,
            action=action,
        )
    except context.rules.comment_target.CommentTargetPayloadError as exc:
        raise context.rules.request.RequestPayloadError(
            str(exc),
            correctable_fields=exc.correctable_fields,
        ) from exc
    except context.rules.comment_target.CommentTargetScopeError as exc:
        raise context.rules.request.RequestScopeError(
            message=str(exc),
            permission_boundary=exc.permission_boundary,
            human_summary="Request track scope denied.",
            why_blocked=str(exc),
            retryable=exc.retryable,
            correctable_fields=exc.correctable_fields,
            code=exc.code,
        ) from exc


def _assert_ref_readable_in_track_context(
    *,
    ref: dict[str, str],
    track_id: str,
    action: str,
    active_buddy: str,
    context: RequestServiceContext,
) -> None:
    ref_type = ref["type"]
    ref_id = ref["id"]
    if ref_type == "track":
        if ref_id != track_id:
            raise context.rules.request.RequestPayloadError(
                "track ref id must match track_id",
                correctable_fields=["target_refs", "track_id"],
            )
        _assert_track_readable(
            track_id=track_id,
            action=action,
            active_buddy=active_buddy,
            context=context,
        )
        return

    if ref_type == "artifact":
        artifact = context.repos.artifact.get_artifact(ref_id)
        if artifact is None:
            raise context.rules.request.RequestPayloadError(
                f"artifact ref not found: {ref_id}",
                correctable_fields=["target_refs"],
            )
        try:
            context.rules.comment_target.assert_target_readable(
                target_type="artifact",
                target_id=ref_id,
                active_buddy=active_buddy,
                action=action,
            )
        except context.rules.comment_target.CommentTargetPayloadError as exc:
            raise context.rules.request.RequestPayloadError(
                str(exc),
                correctable_fields=exc.correctable_fields,
            ) from exc
        except context.rules.comment_target.CommentTargetScopeError as exc:
            raise context.rules.request.RequestScopeError(
                message=str(exc),
                permission_boundary=exc.permission_boundary,
                human_summary="Artifact reference scope denied.",
                why_blocked=str(exc),
                retryable=exc.retryable,
                correctable_fields=exc.correctable_fields,
                code=exc.code,
            ) from exc
        if artifact.get("published_to_track") != track_id:
            raise context.rules.request.RequestScopeError(
                message=f"artifact ref '{ref_id}' is not published on track '{track_id}'",
                permission_boundary="request.track_context",
                human_summary="Request refs must stay inside request track context.",
                why_blocked="artifact ref is outside the request track context",
                retryable=False,
                correctable_fields=["target_refs"],
            )
        return

    comment = context.repos.comment.get_comment(ref_id)
    if comment is None:
        raise context.rules.request.RequestPayloadError(
            f"comment ref not found: {ref_id}",
            correctable_fields=["target_refs"],
        )
    target_type = comment.get("target_type")
    target_id = comment.get("target_id")
    if not isinstance(target_type, str) or not isinstance(target_id, str):
        raise context.rules.request.RequestScopeError(
            message=f"comment ref '{ref_id}' has invalid target linkage",
            permission_boundary="request.track_context",
            human_summary="Comment reference shape is invalid.",
            why_blocked="comment target linkage is missing or malformed",
            retryable=False,
            correctable_fields=["target_refs"],
        )
    if target_type == "track":
        if target_id != track_id:
            raise context.rules.request.RequestScopeError(
                message=f"comment ref '{ref_id}' is on track '{target_id}', not '{track_id}'",
                permission_boundary="request.track_context",
                human_summary="Comment refs must stay inside request track context.",
                why_blocked="comment track target does not match request track",
                retryable=False,
                correctable_fields=["target_refs"],
            )
    elif target_type in {"artifact", "artifact_section"}:
        artifact = context.repos.artifact.get_artifact(target_id)
        if artifact is None:
            raise context.rules.request.RequestPayloadError(
                f"comment target artifact not found: {target_id}",
                correctable_fields=["target_refs"],
            )
        if artifact.get("published_to_track") != track_id:
            raise context.rules.request.RequestScopeError(
                message=f"comment ref '{ref_id}' target artifact is outside track '{track_id}'",
                permission_boundary="request.track_context",
                human_summary="Comment refs must stay inside request track context.",
                why_blocked="comment artifact target is outside the request track",
                retryable=False,
                correctable_fields=["target_refs"],
            )
    else:
        raise context.rules.request.RequestScopeError(
            message=f"comment ref '{ref_id}' has unsupported target type '{target_type}'",
            permission_boundary="request.track_context",
            human_summary="Comment refs must target track or artifact contexts only.",
            why_blocked="comment target type is outside request reference scope",
            retryable=False,
            correctable_fields=["target_refs"],
        )
    try:
        context.rules.comment_target.assert_target_readable(
            target_type=target_type,
            target_id=target_id,
            active_buddy=active_buddy,
            action=action,
        )
    except context.rules.comment_target.CommentTargetPayloadError as exc:
        raise context.rules.request.RequestPayloadError(
            str(exc),
            correctable_fields=exc.correctable_fields,
        ) from exc
    except context.rules.comment_target.CommentTargetScopeError as exc:
        raise context.rules.request.RequestScopeError(
            message=str(exc),
            permission_boundary=exc.permission_boundary,
            human_summary="Comment target scope denied.",
            why_blocked=str(exc),
            retryable=exc.retryable,
            correctable_fields=exc.correctable_fields,
            code=exc.code,
        ) from exc


def _reject_from_scope_exc(
    *,
    action: str,
    active_buddy: str,
    exc: Exception,
) -> dict[str, Any]:
    return _reject_scope(
        action=action,
        active_buddy=active_buddy,
        code=getattr(exc, "code", "E_REQUEST_SCOPE"),
        boundary=getattr(exc, "permission_boundary", "request.scope"),
        message=str(exc),
        human_summary=getattr(exc, "human_summary", "Request scope denied."),
        why_blocked=getattr(exc, "why_blocked", str(exc)),
        retryable=bool(getattr(exc, "retryable", False)),
        correctable_fields=getattr(exc, "correctable_fields", None),
    )


def create_request(*, args: dict[str, Any], context: RequestServiceContext) -> dict[str, Any]:
    action = "request.create"
    active_buddy = context["active_buddy"]
    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"unsupported payload fields: {', '.join(unknown)}",
            correctable_fields=unknown,
        )
    raw_track_id = args.get("track_id")
    if not isinstance(raw_track_id, str) or not raw_track_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="track_id is required", correctable_fields=["track_id"])
    track_id = raw_track_id.strip()
    track = context.repos.track.get_track(track_id)
    if track is None:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"track not found: {track_id}",
            correctable_fields=["track_id"],
        )
    try:
        _assert_track_readable(
            track_id=track_id,
            action=action,
            active_buddy=active_buddy,
            context=context,
        )
        normalized = context.rules.request.normalize_create_args(
            args=args,
            active_buddy=active_buddy,
            manifest=context["manifest"],
            track=track,
            readable_ref_checker=lambda ref, bound_track_id: _assert_ref_readable_in_track_context(
                ref=ref,
                track_id=bound_track_id,
                action=action,
                active_buddy=active_buddy,
                context=context,
            ),
            allowed_fields=_allowed(action),
        )
    except context.rules.request.RequestPayloadError as exc:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
            field_errors=exc.field_errors,
        )
    except context.rules.request.RequestScopeError as exc:
        return _reject_from_scope_exc(action=action, active_buddy=active_buddy, exc=exc)

    try:
        request = context.repos.request.create_request(
            track_id=normalized["track_id"],
            from_buddy=normalized["from_buddy"],
            to_buddy=normalized["to_buddy"],
            title=normalized["title"],
            summary=normalized["summary"],
            target_refs=normalized["target_refs"],
            status="open",
            blocker=None,
            result_refs=[],
            accepted_at=None,
            blocked_at=None,
            completed_at=None,
            canceled_at=None,
        )
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_results.success(
        tool="request",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Created one durable request '{request['id']}' from '{request['from_buddy']}' to '{request['to_buddy']}'.",
        state_changed=True,
        durability="durable",
        created_ids=[request["id"]],
        state_changes=[{"object_type": "request", "change": "created", "request_id": request["id"]}],
        allowed_next_actions=[
            "Use request.get to inspect the created request lifecycle fields.",
            "Use request.list with box filters to scan inbox/outbox work requests.",
        ],
        extra={"request_id": request["id"], "request": request},
    )


def list_requests(*, args: dict[str, Any], context: RequestServiceContext) -> dict[str, Any]:
    action = "request.list"
    active_buddy = context["active_buddy"]
    try:
        normalized = context.rules.request.normalize_list_args(
            args=args,
            manifest=context["manifest"],
            allowed_fields=_allowed(action),
        )
    except context.rules.request.RequestPayloadError as exc:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
            field_errors=exc.field_errors,
        )

    visible_rows: list[dict[str, Any]] = []
    for row in context.repos.request.list_requests():
        track_id = row.get("track_id")
        if not isinstance(track_id, str):
            continue
        try:
            _assert_track_readable(
                track_id=track_id,
                action=action,
                active_buddy=active_buddy,
                context=context,
            )
            context.rules.request.ensure_visible(row, active_buddy)
        except context.rules.request.RequestScopeError:
            continue
        visible_rows.append(row)

    if normalized["box"] == "inbox":
        visible_rows = [row for row in visible_rows if row.get("to_buddy") == active_buddy]
    elif normalized["box"] == "outbox":
        visible_rows = [row for row in visible_rows if row.get("from_buddy") == active_buddy]

    if normalized["status"] is not None:
        visible_rows = [row for row in visible_rows if row.get("status") == normalized["status"]]
    if normalized["track_id"] is not None:
        visible_rows = [row for row in visible_rows if row.get("track_id") == normalized["track_id"]]
    if normalized["buddy"] is not None:
        visible_rows = [
            row for row in visible_rows if row.get("from_buddy") == normalized["buddy"] or row.get("to_buddy") == normalized["buddy"]
        ]

    return tool_results.success(
        tool="request",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Returned {len(visible_rows)} visible request row(s).",
        state_changed=False,
        durability="none",
        read_scope="visible cross-buddy request rows",
        allowed_next_actions=[
            "Use request.get with request_id for one request row.",
            "Use request.accept/block/complete/cancel when authority and state allow.",
        ],
        extra={
            "requests": visible_rows,
            "filters": normalized,
        },
    )


def get_request(*, args: dict[str, Any], context: RequestServiceContext) -> dict[str, Any]:
    action = "request.get"
    active_buddy = context["active_buddy"]
    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"unsupported payload fields: {', '.join(unknown)}",
            correctable_fields=unknown,
        )
    try:
        request_id = context.rules.request.require_request_id(args)
    except context.rules.request.RequestPayloadError as exc:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
            field_errors=exc.field_errors,
        )
    request = context.repos.request.get_request(request_id)
    if request is None:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"request not found: {request_id}",
            correctable_fields=["request_id"],
        )
    try:
        _assert_track_readable(
            track_id=str(request.get("track_id")),
            action=action,
            active_buddy=active_buddy,
            context=context,
        )
        context.rules.request.ensure_visible(request, active_buddy)
    except context.rules.request.RequestScopeError as exc:
        return _reject_from_scope_exc(action=action, active_buddy=active_buddy, exc=exc)
    return tool_results.success(
        tool="request",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Read one request row '{request_id}'.",
        state_changed=False,
        durability="none",
        read_scope="single visible request row",
        allowed_next_actions=[
            "Use request.accept/block/complete/cancel according to request authority and status.",
        ],
        extra={"request_id": request_id, "request": request},
    )


def _load_request_for_mutation(
    *,
    action: str,
    args: dict[str, Any],
    active_buddy: str,
    context: RequestServiceContext,
) -> tuple[str, dict[str, Any]] | dict[str, Any]:
    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"unsupported payload fields: {', '.join(unknown)}",
            correctable_fields=unknown,
        )
    try:
        request_id = context.rules.request.require_request_id(args)
    except context.rules.request.RequestPayloadError as exc:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
            field_errors=exc.field_errors,
        )
    request = context.repos.request.get_request(request_id)
    if request is None:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"request not found: {request_id}",
            correctable_fields=["request_id"],
        )
    try:
        _assert_track_readable(
            track_id=str(request.get("track_id")),
            action=action,
            active_buddy=active_buddy,
            context=context,
        )
    except context.rules.request.RequestPayloadError as exc:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
            field_errors=exc.field_errors,
        )
    except context.rules.request.RequestScopeError as exc:
        return _reject_from_scope_exc(action=action, active_buddy=active_buddy, exc=exc)
    return request_id, request


def _mutate_request(
    *,
    action: str,
    args: dict[str, Any],
    context: RequestServiceContext,
    patch_builder: Any,
) -> dict[str, Any]:
    active_buddy = context["active_buddy"]
    loaded = _load_request_for_mutation(action=action, args=args, active_buddy=active_buddy, context=context)
    if isinstance(loaded, dict):
        return loaded
    request_id, request = loaded
    try:
        patch = patch_builder(request)
    except context.rules.request.RequestPayloadError as exc:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
            field_errors=exc.field_errors,
        )
    except context.rules.request.RequestScopeError as exc:
        return _reject_from_scope_exc(action=action, active_buddy=active_buddy, exc=exc)
    except context.rules.request.RequestStateError as exc:
        return _reject_state(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
            correctable_fields=exc.correctable_fields,
        )

    try:
        updated = context.repos.request.update_request(request_id, patch)
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    change_name = str(updated.get("status") or "updated")
    return tool_results.success(
        tool="request",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Updated request '{request_id}' status to '{updated.get('status')}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[request_id],
        state_changes=[{"object_type": "request", "change": change_name, "request_id": request_id}],
        allowed_next_actions=[
            "Use request.get to verify lifecycle fields after mutation.",
            "Use request.list to scan remaining open/blocked work requests.",
        ],
        extra={"request_id": request_id, "request": updated},
    )


def accept_request(*, args: dict[str, Any], context: RequestServiceContext) -> dict[str, Any]:
    action = "request.accept"
    active_buddy = context["active_buddy"]
    return _mutate_request(
        action=action,
        args=args,
        context=context,
        patch_builder=lambda request: context.rules.request.accept_patch(
            request,
            active_buddy,
            context.now(),
        ),
    )


def block_request(*, args: dict[str, Any], context: RequestServiceContext) -> dict[str, Any]:
    action = "request.block"
    active_buddy = context["active_buddy"]
    blocker = args.get("blocker")
    return _mutate_request(
        action=action,
        args=args,
        context=context,
        patch_builder=lambda request: context.rules.request.block_patch(
            request,
            active_buddy,
            blocker if isinstance(blocker, str) else "",
            context.now(),
        ),
    )


def complete_request(*, args: dict[str, Any], context: RequestServiceContext) -> dict[str, Any]:
    action = "request.complete"
    active_buddy = context["active_buddy"]

    def _builder(request: dict[str, Any]) -> dict[str, Any]:
        result_refs = context.rules.request.normalize_ref_items(args.get("result_refs"), "result_refs")
        for ref in result_refs:
            if ref["type"] == "track" and ref["id"] != str(request.get("track_id")):
                raise context.rules.request.RequestPayloadError(
                    "track result_refs must match request track_id",
                    correctable_fields=["result_refs", "request_id"],
                )
            _assert_ref_readable_in_track_context(
                ref=ref,
                track_id=str(request.get("track_id")),
                action=action,
                active_buddy=active_buddy,
                context=context,
            )
        return context.rules.request.complete_patch(request, active_buddy, result_refs, context.now())

    return _mutate_request(
        action=action,
        args=args,
        context=context,
        patch_builder=_builder,
    )


def cancel_request(*, args: dict[str, Any], context: RequestServiceContext) -> dict[str, Any]:
    action = "request.cancel"
    active_buddy = context["active_buddy"]
    return _mutate_request(
        action=action,
        args=args,
        context=context,
        patch_builder=lambda request: context.rules.request.cancel_patch(request, active_buddy, context.now()),
    )


_ACTION_HANDLERS = {
    "create": create_request,
    "list": list_requests,
    "get": get_request,
    "accept": accept_request,
    "block": block_request,
    "complete": complete_request,
    "cancel": cancel_request,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    return handler(args=args, context=context)
