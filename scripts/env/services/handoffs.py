#!/usr/bin/env python3
"""Runless handoff services."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.services import source_refs as source_ref_service
from env.tools import responses as tool_responses


class HandoffServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


_LIST_FIELDS = {"track_id", "target_buddy", "status", "limit"}
_VALIDATE_FIELDS = {
    "track_id",
    "source_task_id",
    "target_buddy",
    "artifact_ids",
    "source_refs",
    "reason",
    "context",
    "status",
    "read_claim",
}
_CREATE_FIELDS = set(_VALIDATE_FIELDS) | {"handoff_id"}
_LEGACY_SOURCE_RUN = "source" + "_run_id"


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="handoff",
        action=action,
        active_buddy=active_buddy,
        code="E_HANDOFF_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Handoff payload is invalid.",
        why_blocked=message,
        impact="No handoff or product object state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix handoff payload fields and retry.",
        allowed_next_actions=[
            "Use context.summarize to inspect candidate ids.",
            "Use handoff.validate before handoff.create.",
        ],
    )


def _reject_scope(*, action: str, active_buddy: str, boundary: str, message: str, code: str = "E_HANDOFF_SCOPE") -> dict[str, Any]:
    return tool_responses.rejection(
        tool="handoff",
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=boundary,
        human_summary="Handoff scope check failed.",
        why_blocked=message,
        impact="No handoff or product object state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Use owned source objects and valid target buddy ids.",
        allowed_next_actions=[
            "Use task.list/artifact.list/context.summarize to inspect owned source ids.",
            "Use handoff.validate with corrected refs.",
        ],
    )


def _manifest_buddies(manifest: dict[str, Any]) -> set[str]:
    buddies: set[str] = set()
    for row in manifest.get("buddies", []):
        if isinstance(row, dict):
            buddy_id = row.get("id")
            if isinstance(buddy_id, str) and buddy_id:
                buddies.add(buddy_id)
    return buddies


def _require_allowed_fields(action: str, args: dict[str, Any], active_buddy: str) -> dict[str, Any] | None:
    allowed = _LIST_FIELDS if action == "handoff.list" else _VALIDATE_FIELDS if action == "handoff.validate" else _CREATE_FIELDS
    unknown = sorted(key for key in args if key not in allowed)
    if unknown:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"unsupported payload fields: {', '.join(unknown)}")
    if _LEGACY_SOURCE_RUN in args:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="legacy handoff run lineage field is retired; use product object refs",
        )
    return None


def _normalize_ids(value: Any, *, label: str) -> tuple[list[str] | None, str | None]:
    if value is None:
        return [], None
    if not isinstance(value, list):
        return None, f"{label} must be a list"
    rows: list[str] = []
    for raw in value:
        if not isinstance(raw, str) or not raw.strip():
            return None, f"{label} must contain non-empty strings"
        try:
            rows.append(env_store.require_id(raw.strip(), f"{label}[]"))
        except ValueError as exc:
            return None, str(exc)
    return list(dict.fromkeys(rows)), None


def _validate_payload(*, args: dict[str, Any], context: HandoffServiceContext, action: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    active_buddy = context["active_buddy"]
    track_id = args.get("track_id")
    if not isinstance(track_id, str) or not track_id.strip():
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="track_id is required")
    track_id = track_id.strip()

    track = env_store.get_track(track_id)
    if track is None:
        return None, _reject_payload(action=action, active_buddy=active_buddy, message=f"track not found: {track_id}")

    target_buddy = args.get("target_buddy")
    if not isinstance(target_buddy, str) or not target_buddy.strip():
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="target_buddy is required")
    target_buddy = target_buddy.strip()
    buddies = _manifest_buddies(context["manifest"])
    if target_buddy not in buddies:
        return None, _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary="handoff.target_buddy",
            code="E_HANDOFF_TARGET_BUDDY",
            message=f"target_buddy '{target_buddy}' is not in manifest buddies",
        )

    source_task_id = args.get("source_task_id")
    if source_task_id is not None:
        if not isinstance(source_task_id, str) or not source_task_id.strip():
            return None, _reject_payload(action=action, active_buddy=active_buddy, message="source_task_id must be a non-empty string")
        source_task_id = source_task_id.strip()
        task = env_store.get_task(source_task_id)
        if task is None:
            return None, _reject_payload(action=action, active_buddy=active_buddy, message=f"source_task_id not found: {source_task_id}")
        if task.get("buddy") != active_buddy:
            return None, _reject_scope(
                action=action,
                active_buddy=active_buddy,
                boundary="task.buddy_scope",
                message=f"source_task_id '{source_task_id}' is owned by buddy '{task.get('buddy')}'",
            )

    artifact_ids, artifact_err = _normalize_ids(args.get("artifact_ids"), label="artifact_ids")
    if artifact_err:
        return None, _reject_payload(action=action, active_buddy=active_buddy, message=artifact_err)
    assert artifact_ids is not None
    for artifact_id in artifact_ids:
        artifact = env_store.get_artifact(artifact_id)
        if artifact is None:
            return None, _reject_payload(action=action, active_buddy=active_buddy, message=f"artifact not found: {artifact_id}")
        if artifact.get("buddy") != active_buddy:
            return None, _reject_scope(
                action=action,
                active_buddy=active_buddy,
                boundary="artifact.buddy_scope",
                message=f"artifact '{artifact_id}' is owned by buddy '{artifact.get('buddy')}'",
            )

    reason = args.get("reason")
    context_text = args.get("context")
    if not isinstance(reason, str) or not reason.strip():
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="reason is required")
    if not isinstance(context_text, str) or not context_text.strip():
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="context is required")

    status = args.get("status")
    if status is None:
        status = "active"
    if status not in env_store.VALID_HANDOFF_STATUS:
        return None, _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"status must be one of {', '.join(env_store.VALID_HANDOFF_STATUS)}",
        )

    read_claim = args.get("read_claim")
    if read_claim is not None and not isinstance(read_claim, str):
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="read_claim must be a string")

    try:
        source_refs, scope_error = source_ref_service.normalize_source_refs(
            args.get("source_refs"),
            active_buddy=active_buddy,
            read_claim=read_claim if isinstance(read_claim, str) else None,
            allow_buddybox=False,
        )
    except ValueError as exc:
        return None, _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary="source_refs.required_fields",
            message=str(exc),
            code="E_SOURCE_REFS",
        )
    if isinstance(scope_error, dict):
        return None, _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary=str(scope_error.get("permission_boundary", "source_refs.read_scope")),
            message=str(scope_error.get("why_blocked", "source_refs read scope denied")),
            code="E_SOURCE_REFS_READ_SCOPE",
        )

    normalized = {
        "track_id": track_id,
        "source_task_id": source_task_id,
        "target_buddy": target_buddy,
        "artifact_ids": artifact_ids,
        "source_refs": source_refs,
        "reason": reason.strip(),
        "context": context_text.strip(),
        "status": status,
    }
    return normalized, None


def _handoff_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "source_buddy": row.get("source_buddy"),
        "target_buddy": row.get("target_buddy"),
        "track_id": row.get("track_id"),
        "source_task_id": row.get("source_task_id"),
        "artifact_ids": list(row.get("artifact_ids", [])),
        "source_refs": row.get("source_refs"),
        "reason": row.get("reason"),
        "context": row.get("context"),
        "status": row.get("status"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def list_handoffs_for_active_buddy(*, args: dict[str, Any], context: HandoffServiceContext) -> dict[str, Any]:
    action = "handoff.list"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    rows = []
    for row in env_store.list_handoffs():
        if row.get("source_buddy") != active_buddy and row.get("target_buddy") != active_buddy and active_buddy != "pm":
            continue
        rows.append(row)

    track_id = args.get("track_id")
    if isinstance(track_id, str) and track_id.strip():
        rows = [row for row in rows if row.get("track_id") == track_id.strip()]

    target_buddy = args.get("target_buddy")
    if isinstance(target_buddy, str) and target_buddy.strip():
        rows = [row for row in rows if row.get("target_buddy") == target_buddy.strip()]

    status = args.get("status")
    if isinstance(status, str) and status.strip():
        rows = [row for row in rows if row.get("status") == status.strip()]

    limit = args.get("limit")
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]

    payload_rows = [_handoff_row(row) for row in rows]
    return tool_responses.success(
        tool="handoff",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Listed {len(payload_rows)} readable handoff record(s).",
        state_changed=False,
        durability="none",
        read_scope="explicit handoff object records",
        allowed_next_actions=["Use handoff.validate before creating new handoff records."],
        extra={"handoffs": payload_rows},
    )


def validate_handoff(*, args: dict[str, Any], context: HandoffServiceContext) -> dict[str, Any]:
    action = "handoff.validate"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    normalized, error = _validate_payload(args=args, context=context, action=action)
    if error is not None:
        return error
    assert isinstance(normalized, dict)

    return tool_responses.success(
        tool="handoff",
        action=action,
        active_buddy=active_buddy,
        effect_summary="Handoff payload validated with explicit product object refs.",
        state_changed=False,
        durability="none",
        validation_only=True,
        read_scope="request payload validation",
        allowed_next_actions=["Use handoff.create with the same validated payload."],
        extra={
            "handoff": normalized,
            "track_alignment": {
                "track_id": normalized["track_id"],
                "target_buddy": normalized["target_buddy"],
                "source_buddy": active_buddy,
            },
        },
    )


def create_handoff_for_active_buddy(*, args: dict[str, Any], context: HandoffServiceContext) -> dict[str, Any]:
    action = "handoff.create"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    normalized, error = _validate_payload(args=args, context=context, action=action)
    if error is not None:
        return error
    assert isinstance(normalized, dict)

    handoff_id = args.get("handoff_id")
    if handoff_id is None:
        handoff_id = f"handoff-{active_buddy}-{normalized['target_buddy']}-{uuid.uuid4().hex[:8]}"
    if not isinstance(handoff_id, str) or not handoff_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="handoff_id must be a non-empty string")

    try:
        created = env_store.create_handoff(
            handoff_id=handoff_id.strip(),
            track_id=normalized["track_id"],
            source_buddy=active_buddy,
            target_buddy=normalized["target_buddy"],
            source_task_id=normalized["source_task_id"],
            artifact_ids=normalized["artifact_ids"],
            source_refs=normalized["source_refs"],
            reason=normalized["reason"],
            context=normalized["context"],
            status=normalized["status"],
        )
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    row = _handoff_row(created)
    return tool_responses.success(
        tool="handoff",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Created handoff '{created['id']}' from '{active_buddy}' to '{created['target_buddy']}'.",
        state_changed=True,
        durability="durable",
        created_ids=[created["id"]],
        allowed_next_actions=[
            "Use handoff.list to review readable handoff timeline.",
            "Notify target buddy to consume referenced readable artifacts.",
        ],
        extra={"handoff": row},
    )
