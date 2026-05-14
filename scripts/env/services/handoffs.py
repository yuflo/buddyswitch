#!/usr/bin/env python3
"""Handoff service for broker-routed env.tool operations."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.services import context as context_service
from env.services import track_relations
from env.tools import responses as tool_responses

_IDENTITY_FIELDS = {"active_buddy", "buddy", "instance_id"}
_VALIDATE_FIELDS = {
    "track_id",
    "source_task_id",
    "source_run_id",
    "target_buddy",
    "next_buddy",
    "artifact_ids",
    "historical_artifact_ids",
    "reason",
    "context",
} | _IDENTITY_FIELDS
_FORBIDDEN_MUTATION_FIELDS = {"status", "current_buddy", "next_buddy_override", "track_status", "state_effects"}


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


def _current_binding(context: HandoffServiceContext) -> dict[str, Any]:
    payload = context["instance_payload"]
    return {
        "instance_id": context["instance_id"],
        "current_task_id": payload.get("current_task_id"),
        "current_track_id": payload.get("current_track_id"),
    }


def _error_payload(
    *,
    action: str,
    active_buddy: str,
    code: str,
    message: str,
    permission_boundary: str,
    allowed_next_actions: list[str],
    human_summary: str | None = None,
    why_blocked: str | None = None,
    impact: str = "No handoff, track, task, or run state was changed.",
    retryable: bool = True,
    retry_guidance: str | None = None,
    allowed_next_action_options: list[dict[str, Any]] | None = None,
    track_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = tool_responses.rejection(
        tool="handoff",
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=permission_boundary,
        human_summary=human_summary or message,
        why_blocked=why_blocked or message,
        impact=impact,
        state_changed=False,
        retryable=retryable,
        retry_guidance=retry_guidance or "Fix handoff payload/context preconditions and retry.",
        allowed_next_actions=allowed_next_actions,
        allowed_next_action_options=allowed_next_action_options,
    )
    if isinstance(track_id, str) and track_id.strip():
        payload["track_id"] = track_id.strip()
    if isinstance(extra, dict):
        payload.update(extra)
    return payload


def _payload_error(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    payload = _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_HANDOFF_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Handoff payload is invalid.",
        why_blocked=message,
        retryable=True,
        retry_guidance="Provide required handoff fields and retry.",
        allowed_next_actions=[
            "Provide track_id, source_task_id, target_buddy, artifact_ids, reason, and context.",
            "Use handoff.list and track.get to inspect current handoff state before retrying.",
        ],
        allowed_next_action_options=[
            tool_responses.next_action_option(
                tool="track",
                action="get",
                option_id="inspect_track_before_handoff",
                reason="Inspect one track before validating or creating a handoff.",
            ),
            tool_responses.next_action_option(
                tool="handoff",
                action="list",
                option_id="inspect_recent_handoffs",
                reason="Inspect recent handoffs before creating a new one.",
            ),
        ],
    )
    payload.update(
        {
            "next_actions": [
                {"tool": "track", "action": "list"},
                {"tool": "handoff", "action": "list"},
            ],
            "command_hint": track_relations.command_hint("track", "list"),
            "relation": "none",
            "missing_preconditions": ["handoff payload must include required fields"],
            "no_content_leak": True,
        }
    )
    return payload


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


def _normalize_target_buddy(args: dict[str, Any]) -> tuple[str | None, str | None]:
    target = args.get("target_buddy")
    next_buddy = args.get("next_buddy")
    if isinstance(target, str) and target.strip():
        return target.strip(), next_buddy.strip() if isinstance(next_buddy, str) and next_buddy.strip() else target.strip()
    if isinstance(next_buddy, str) and next_buddy.strip():
        return next_buddy.strip(), next_buddy.strip()
    return None, None


def _normalize_id(value: Any, label: str) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, None
    try:
        return env_store.require_id(value.strip(), label), None
    except ValueError as exc:
        return None, str(exc)


def _normalize_string_list(value: Any, label: str) -> tuple[list[str] | None, str | None]:
    if value is None:
        return [], None
    if not isinstance(value, list):
        return None, f"{label} must be a list"
    rows: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return None, f"{label} must contain non-empty strings"
        try:
            rows.append(env_store.require_id(item.strip(), label))
        except ValueError as exc:
            return None, str(exc)
    return list(dict.fromkeys(rows)), None


def _track_id_from_payload_or_binding(args: dict[str, Any], context: HandoffServiceContext) -> tuple[str | None, str | None]:
    raw_track_id = args.get("track_id")
    if raw_track_id is None:
        raw_track_id = context["instance_payload"].get("current_track_id")
    return _normalize_id(raw_track_id, "track id")


def _validate_handoff_payload(
    *,
    args: dict[str, Any],
    context: HandoffServiceContext,
    action: str,
    mutate: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    forbidden = sorted(key for key in args.keys() if key in _FORBIDDEN_MUTATION_FIELDS)
    if forbidden:
        return None, _error_payload(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_HANDOFF_LIFECYCLE_BOUNDARY",
            message=f"forbidden handoff mutation fields: {', '.join(forbidden)}",
            permission_boundary="handoff.lifecycle_boundary",
            allowed_next_actions=[
                "Remove lifecycle mutation fields from handoff payload.",
                "Use explicit track/task env tools for lifecycle or state changes.",
            ],
        )

    track_id, track_error = _track_id_from_payload_or_binding(args, context)
    if track_error is not None:
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message=track_error)
    if track_id is None:
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message="track_id is required")
    track = env_store.get_track(track_id)
    if track is None:
        return None, _error_payload(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_TRACK_NOT_FOUND",
            message=f"track not found: {track_id}",
            permission_boundary="track.lookup",
            track_id=track_id,
            allowed_next_actions=[
                "Use track.list to inspect valid track ids.",
                "Retry handoff with an existing track id.",
            ],
        )

    source_task_id, task_error = _normalize_id(args.get("source_task_id"), "task id")
    if task_error is not None:
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message=task_error)
    if source_task_id is None:
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message="source_task_id is required")
    source_task = env_store.get_task(source_task_id)
    if source_task is None:
        return None, _error_payload(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_TASK_NOT_FOUND",
            message=f"source task not found: {source_task_id}",
            permission_boundary="task.lookup",
            track_id=track_id,
            allowed_next_actions=[
                "Use task.list to inspect active-buddy tasks.",
                "Retry with a valid source_task_id owned by the active buddy.",
            ],
        )
    if source_task.get("buddy") != context["active_buddy"]:
        return None, _error_payload(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_TASK_BUDDY_SCOPE",
            message=f"source task belongs to '{source_task.get('buddy')}', not active buddy '{context['active_buddy']}'",
            permission_boundary="task.buddy_scope",
            track_id=track_id,
            allowed_next_actions=[
                "Use a source task owned by the active buddy.",
                "Use handoff.list to inspect handoffs from other buddies.",
            ],
        )

    source_task_track_id = source_task.get("track_id")
    if isinstance(source_task_track_id, str) and source_task_track_id and source_task_track_id != track_id:
        return None, _error_payload(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_TRACK_TASK_LINKAGE",
            message=f"source task '{source_task_id}' is bound to another track '{source_task_track_id}'",
            permission_boundary="track.task_linkage",
            track_id=track_id,
            allowed_next_actions=[
                "Use a source task already linked to the requested track.",
                "Use track.join to create a task on the target track first.",
            ],
        )
    if source_task_track_id is None:
        return None, _error_payload(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_TRACK_TASK_LINKAGE",
            message=f"source task '{source_task_id}' is not linked to track '{track_id}'",
            permission_boundary="track.task_linkage",
            track_id=track_id,
            allowed_next_actions=[
                "Link source task to the track before validate/create/commit handoff payload.",
                "Use track.join to create or select active-buddy tracked work first.",
            ],
        )

    source_run_id, run_error = _normalize_id(args.get("source_run_id"), "run id")
    if run_error is not None:
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message=run_error)
    if source_run_id is None:
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message="source_run_id is required")

    target_buddy, next_buddy = _normalize_target_buddy(args)
    if not isinstance(target_buddy, str):
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message="target_buddy is required")
    if target_buddy not in _known_buddy_ids(context["manifest"]):
        return None, _error_payload(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_HANDOFF_TARGET",
            message=f"target_buddy must reference a manifest buddy id; got '{target_buddy}'",
            permission_boundary="manifest.buddies",
            track_id=track_id,
            allowed_next_actions=[
                "Use one of the manifest buddy ids as target_buddy.",
                "Retry handoff after selecting a valid buddy target.",
            ],
            extra={"handoff_targets": sorted(_known_buddy_ids(context["manifest"]))},
        )

    reason = args.get("reason")
    handoff_context = args.get("context")
    if not isinstance(reason, str) or not reason.strip():
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message="reason must be a non-empty string")
    if not isinstance(handoff_context, str) or not handoff_context.strip():
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message="context must be a non-empty string")

    artifact_ids, artifact_error = _normalize_string_list(args.get("artifact_ids"), "artifact_ids")
    if artifact_error is not None:
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message=artifact_error)
    if artifact_ids is None or not artifact_ids:
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message="artifact_ids is required")

    historical_artifact_ids, historical_error = _normalize_string_list(
        args.get("historical_artifact_ids"),
        "historical_artifact_ids",
    )
    if historical_error is not None:
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message=historical_error)
    assert isinstance(historical_artifact_ids, list)

    for artifact_id in artifact_ids:
        artifact = env_store.get_artifact(artifact_id)
        if artifact is None:
            return None, _error_payload(
                action=action,
                active_buddy=context["active_buddy"],
                code="E_ARTIFACT_NOT_FOUND",
                message=f"artifact not found: {artifact_id}",
                permission_boundary="artifact.lookup",
                track_id=track_id,
                allowed_next_actions=[
                    "Use artifact.list --track-id <track-id> to inspect valid ids.",
                    "Retry with existing source artifact ids only.",
                ],
            )
        if artifact.get("task_id") != source_task_id:
            return None, _error_payload(
                action=action,
                active_buddy=context["active_buddy"],
                code="E_HANDOFF_SOURCE_ARTIFACT_SCOPE",
                message=f"artifact '{artifact_id}' is not owned by source task '{source_task_id}'",
                permission_boundary="handoff.source_artifact_scope",
                track_id=track_id,
                allowed_next_actions=[
                    "Use artifacts owned by the source task only.",
                    "Use artifact.create_revision on the source task before handoff.",
                ],
            )
        if artifact.get("buddy") != context["active_buddy"]:
            return None, _error_payload(
                action=action,
                active_buddy=context["active_buddy"],
                code="E_ARTIFACT_BUDDY_SCOPE",
                message=f"artifact '{artifact_id}' is not owned by active buddy '{context['active_buddy']}'",
                permission_boundary="artifact.buddy_scope",
                track_id=track_id,
                allowed_next_actions=[
                    "Use source artifacts owned by the active buddy only.",
                    "Use handoff.list to inspect foreign handoff records instead of reusing foreign artifacts.",
                ],
            )
        if not bool(artifact.get("is_current")) and artifact_id not in set(historical_artifact_ids):
            return None, _error_payload(
                action=action,
                active_buddy=context["active_buddy"],
                code="E_HANDOFF_HISTORICAL_MARKER",
                message=f"artifact '{artifact_id}' is historical and must be listed in historical_artifact_ids",
                permission_boundary="handoff.historical_marker",
                track_id=track_id,
                allowed_next_actions=[
                    "Add historical artifact ids explicitly when handing off superseded artifacts.",
                    "Prefer current artifacts for normal handoff payloads.",
                ],
            )

    return {
        "track_id": track_id,
        "source_task_id": source_task_id,
        "source_run_id": source_run_id,
        "target_buddy": target_buddy,
        "next_buddy": next_buddy,
        "artifact_ids": artifact_ids,
        "historical_artifact_ids": historical_artifact_ids,
        "reason": reason.strip(),
        "context": handoff_context.strip(),
    }, None


def _discoverability() -> dict[str, Any]:
    return {
        "will_be_discoverable_by_next_buddy": True,
        "discovery_basis": "handoff_record + run_audit",
        "available_after": "handoff.create or run.commit",
        "discovery_surfaces": ["track.list", "track.get", "handoff.list"],
    }


def list_handoffs_for_active_buddy(*, args: dict[str, Any], context: HandoffServiceContext) -> dict[str, Any]:
    action = "handoff.list"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields={"track_id"} | _IDENTITY_FIELDS,
    )
    if fields_error is not None:
        return fields_error

    track_id: str | None = None
    if "track_id" in args:
        track_id, parse_error = _normalize_id(args.get("track_id"), "track id")
        if parse_error is not None:
            return _payload_error(action=action, active_buddy=context["active_buddy"], message=parse_error)

    rows: list[dict[str, Any]] = []
    for record in env_store.list_handoffs():
        if track_id is not None and record.get("track_id") != track_id:
            continue
        target_buddy = record.get("target_buddy")
        rows.append(
            {
                "source_type": "handoff_record",
                "handoff_id": record.get("id"),
                "track_id": record.get("track_id"),
                "source_buddy": record.get("source_buddy"),
                "target_buddy": target_buddy,
                "source_task_id": record.get("source_task_id"),
                "source_run_id": record.get("source_run_id"),
                "artifact_ids": record.get("artifact_ids", []),
                "status": record.get("status"),
                "read_authorizes_active_buddy": target_buddy == context["active_buddy"],
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
            }
        )

    if isinstance(track_id, str):
        for handoff in context_service.scan_track_recent_handoffs(track_id, limit=20):
            if not isinstance(handoff, dict):
                continue
            target_buddy = handoff.get("next_buddy")
            rows.append(
                {
                    "source_type": "run_audit",
                    "handoff_id": None,
                    "track_id": track_id,
                    "source_buddy": handoff.get("buddy_id"),
                    "target_buddy": target_buddy,
                    "source_task_id": handoff.get("task_id"),
                    "source_run_id": handoff.get("run_id"),
                    "artifact_ids": [],
                    "status": "active",
                    "read_authorizes_active_buddy": target_buddy == context["active_buddy"],
                    "created_at": handoff.get("timestamp"),
                    "updated_at": handoff.get("timestamp"),
                }
            )

    rows.sort(
        key=lambda row: (
            str(row.get("updated_at") or row.get("created_at") or ""),
            str(row.get("handoff_id") or row.get("source_run_id") or ""),
        ),
        reverse=True,
    )

    payload: dict[str, Any] = {
        "track_id": track_id,
        "handoffs": rows,
        "current_binding": _current_binding(context),
        "next_actions": [
            {"tool": "handoff", "action": "validate"},
            {"tool": "handoff", "action": "create"},
        ],
        "command_hint": track_relations.command_hint("handoff", "create"),
    }
    return tool_responses.success(
        tool="handoff",
        action=action,
        active_buddy=context["active_buddy"],
        effect_summary=f"Listed {len(rows)} handoff rows for track '{track_id}' without mutating state.",
        state_changed=False,
        durability="none",
        read_scope="Explicit handoff records plus recent run-audit handoff summaries.",
        allowed_next_actions=[
            "Use handoff.validate before creating a new explicit handoff record.",
            "Use track.get and artifact.get to inspect referenced source artifacts.",
        ],
        extra=payload,
    )


def validate_handoff(*, args: dict[str, Any], context: HandoffServiceContext) -> dict[str, Any]:
    action = "handoff.validate"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_VALIDATE_FIELDS | _FORBIDDEN_MUTATION_FIELDS,
    )
    if fields_error is not None:
        return fields_error

    normalized, error = _validate_handoff_payload(args=args, context=context, action=action, mutate=False)
    if error is not None:
        return error
    assert isinstance(normalized, dict)
    track = env_store.get_track(str(normalized["track_id"]))
    track_next_buddy = track.get("next_buddy") if isinstance(track, dict) else None
    return tool_responses.success(
        tool="handoff",
        action=action,
        active_buddy=context["active_buddy"],
        effect_summary="Validated handoff payload and discoverability alignment without writing state.",
        state_changed=False,
        durability="none",
        validation_only=True,
        follow_up_affordances=[
            tool_responses.follow_up_affordance(
                tool="handoff",
                action="create",
                reason="Create explicit handoff record from validated payload.",
            )
        ],
        allowed_next_actions=[
            "Use handoff.create with the validated payload when ready.",
            "Use run.validate_result before run.commit when handoff payload is included in result.",
        ],
        extra={
            "track_id": normalized["track_id"],
            "handoff": normalized,
            "track_alignment": {
                "track_id": normalized["track_id"],
                "requested_next_buddy": normalized["target_buddy"],
                "track_next_buddy": track_next_buddy,
                "target_matches_track_next_buddy": track_next_buddy in {None, normalized["target_buddy"]},
            },
            "discoverability": _discoverability(),
            "current_binding": _current_binding(context),
            "next_actions": [
                {"tool": "handoff", "action": "create"},
                {"tool": "run", "action": "validate_result"},
            ],
            "command_hint": track_relations.command_hint("handoff", "create"),
        },
    )


def create_handoff_for_active_buddy(*, args: dict[str, Any], context: HandoffServiceContext) -> dict[str, Any]:
    action = "handoff.create"
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_VALIDATE_FIELDS | _FORBIDDEN_MUTATION_FIELDS,
    )
    if fields_error is not None:
        return fields_error

    normalized, error = _validate_handoff_payload(args=args, context=context, action=action, mutate=True)
    if error is not None:
        return error
    assert isinstance(normalized, dict)

    handoff_id = f"handoff-{normalized['track_id']}-{context['active_buddy']}-to-{normalized['target_buddy']}-{uuid.uuid4().hex[:8]}"
    record = env_store.create_handoff(
        handoff_id=handoff_id,
        track_id=str(normalized["track_id"]),
        source_buddy=context["active_buddy"],
        target_buddy=str(normalized["target_buddy"]),
        source_task_id=str(normalized["source_task_id"]),
        source_run_id=str(normalized["source_run_id"]),
        artifact_ids=list(normalized["artifact_ids"]),
        historical_artifact_ids=list(normalized["historical_artifact_ids"]),
        reason=str(normalized["reason"]),
        context=str(normalized["context"]),
        status="active",
    )

    return tool_responses.success(
        tool="handoff",
        action=action,
        active_buddy=context["active_buddy"],
        effect_summary=f"Created explicit handoff record '{record['id']}' without mutating track lifecycle fields.",
        state_changed=True,
        durability="runtime_object",
        state_changes=[{"object_type": "handoff", "object_id": record["id"], "change": "created"}],
        created_ids=[str(record["id"])],
        allowed_next_actions=[
            "Use run.validate_result or run.commit to include this handoff in run audit when needed.",
            "Use handoff.list to verify recipient-facing handoff visibility.",
        ],
        extra={
            "track_id": normalized["track_id"],
            "handoff": record,
            "current_binding": _current_binding(context),
            "next_actions": [
                {"tool": "run", "action": "validate_result"},
                {"tool": "handoff", "action": "list", "args": {"track_id": normalized["track_id"]}},
            ],
            "command_hint": track_relations.command_hint(
                "handoff",
                "list",
                {"track_id": normalized["track_id"]},
            ),
        },
    )


__all__ = [
    "validate_handoff",
    "list_handoffs_for_active_buddy",
    "create_handoff_for_active_buddy",
    "_validate_handoff_payload",
]
