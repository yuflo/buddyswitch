#!/usr/bin/env python3
"""Active-buddy scoped artifact env tool service for broker-routed env.tool operations."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, TypedDict

import env_store
from env_manifest import buddy_permissions, get_buddy
from env.services import track_relations

_ARTIFACT_PUBLIC_FIELDS = (
    "id",
    "title",
    "task_id",
    "buddy",
    "kind",
    "revision",
    "supersedes_artifact_id",
    "is_current",
    "source_run_id",
    "summary",
    "updated_at",
)
_READ_PERMISSION = "artifact.read"
_CREATE_PERMISSION = "artifact.create"
_UPDATE_PERMISSION = "artifact.update"
_IDENTITY_FIELDS = {"active_buddy", "buddy", "instance_id"}
_LIST_FIELDS: set[str] = {"track_id"}
_GET_FIELDS = {"artifact_id"}
_GET_CURRENT_FIELDS = {"kind"}
_TRACK_ID_FIELDS = {"track_id"}
_CREATE_FIELDS = {
    "artifact_id",
    "task_id",
    "kind",
    "title",
    "summary",
    "content",
    "source_run_id",
} | _IDENTITY_FIELDS
_UPDATE_METADATA_FIELDS = {"artifact_id", "title", "summary", "source_run_id"} | _IDENTITY_FIELDS


class ArtifactServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _error_payload(
    *,
    action: str,
    active_buddy: str,
    code: str,
    message: str,
    permission_boundary: str,
    allowed_next_actions: list[str],
    artifact_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "tool": "artifact",
        "action": action,
        "error": {
            "code": code,
            "message": message,
        },
        "permission_boundary": permission_boundary,
        "active_buddy": active_buddy,
        "allowed_next_actions": allowed_next_actions,
    }
    if isinstance(artifact_id, str) and artifact_id.strip():
        payload["artifact_id"] = artifact_id.strip()
    if isinstance(task_id, str) and task_id.strip():
        payload["task_id"] = task_id.strip()
    return payload


def _permission_error(*, action: str, active_buddy: str, permission: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_ARTIFACT_PERMISSION",
        message=f"active buddy '{active_buddy}' is missing required permission '{permission}'",
        permission_boundary="manifest.permission",
        allowed_next_actions=[
            "Use only artifact actions allowed by the active buddy manifest permissions.",
            "Switch to a buddy that owns this artifact action before retrying.",
        ],
    )


def _payload_error(
    *,
    action: str,
    active_buddy: str,
    message: str,
    artifact_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_ARTIFACT_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        artifact_id=artifact_id,
        task_id=task_id,
        allowed_next_actions=[
            'Fix the env.tool envelope fields (`tool`, `action`, `args`) and retry.',
            "Use track.list then artifact.list --track-id to inspect readable artifact ids.",
        ],
    )


def _task_scope_error(*, action: str, active_buddy: str, task_id: str, task_buddy: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TASK_BUDDY_SCOPE",
        message=f"task belongs to buddy '{task_buddy}', not active buddy '{active_buddy}'",
        permission_boundary="task.buddy_scope",
        task_id=task_id,
        allowed_next_actions=[
            "Choose a task owned by the active buddy.",
            "Use the active buddy current task before creating artifact revisions.",
        ],
    )


def _artifact_scope_error(
    *,
    action: str,
    active_buddy: str,
    artifact_id: str,
    task_id: str | None,
) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_ARTIFACT_BUDDY_SCOPE",
        message=f"artifact '{artifact_id}' does not belong to active buddy '{active_buddy}'",
        permission_boundary="artifact.buddy_scope",
        artifact_id=artifact_id,
        task_id=task_id,
        allowed_next_actions=[
            "Choose an artifact produced for the active buddy task.",
            "Cross-buddy artifacts are read-only sources; use artifact.get for reads and keep writes on owned artifacts.",
        ],
    )


def _artifact_lookup_error(*, action: str, active_buddy: str, artifact_id: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_ARTIFACT_NOT_FOUND",
        message=f"artifact not found: {artifact_id}",
        permission_boundary="artifact.lookup",
        artifact_id=artifact_id,
        allowed_next_actions=[
            "Use artifact.list --track-id <track-id> to inspect readable artifact ids.",
            "Use task.get --task-id <task-id> to inspect task artifact summaries.",
        ],
    ) | {
        "why": "artifact id is unknown",
        "relation": "none",
        "missing_preconditions": ["artifact_id must reference an existing artifact"],
        "next_actions": [
            {"tool": "track", "action": "list"},
            {"tool": "artifact", "action": "list"},
        ],
        "command_hint": track_relations.command_hint("track", "list"),
        "no_content_leak": True,
    }


def _task_lookup_error(*, action: str, active_buddy: str, task_id: str) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_TASK_NOT_FOUND",
        message=f"task not found: {task_id}",
        permission_boundary="task.lookup",
        task_id=task_id,
        allowed_next_actions=[
            "Use task.get_current to inspect the active task binding.",
            "Create or bind an active-buddy task before creating artifact revisions.",
        ],
    )


def _kind_error(*, action: str, context: ArtifactServiceContext, kind: str, task_id: str) -> dict[str, Any]:
    buddy = get_buddy(context["manifest"], context["active_buddy"])
    allowed_kinds = buddy.get("artifact_kinds", []) if isinstance(buddy, dict) else []
    return _error_payload(
        action=action,
        active_buddy=context["active_buddy"],
        code="E_ARTIFACT_KIND",
        message=f"artifact kind '{kind}' is not allowed for active buddy '{context['active_buddy']}'",
        permission_boundary="manifest.artifact_kinds",
        task_id=task_id,
        allowed_next_actions=[
            f"Use one allowed artifact kind for buddy '{context['active_buddy']}'.",
            "Hand off work to the buddy that owns the requested artifact kind.",
        ],
    ) | {"allowed_artifact_kinds": list(allowed_kinds)}


def _source_run_error(
    *,
    action: str,
    active_buddy: str,
    message: str,
    task_id: str,
    artifact_id: str | None = None,
) -> dict[str, Any]:
    return _error_payload(
        action=action,
        active_buddy=active_buddy,
        code="E_ARTIFACT_SOURCE_RUN",
        message=message,
        permission_boundary="artifact.source_run",
        artifact_id=artifact_id,
        task_id=task_id,
        allowed_next_actions=[
            "Use the reserved run_id from the active prepare context.",
            "When prepare was taskless, use task.create and task.set_current before artifact.create_revision.",
            "Run prepare again when the source run reservation is missing or stale.",
        ],
    )


def _require_permission(context: ArtifactServiceContext, permission: str, action: str) -> dict[str, Any] | None:
    permissions = buddy_permissions(context["manifest"], context["active_buddy"])
    if permission in permissions:
        return None
    return _permission_error(action=action, active_buddy=context["active_buddy"], permission=permission)


def _current_binding(context: ArtifactServiceContext) -> dict[str, Any]:
    payload = context["instance_payload"]
    return {
        "instance_id": context["instance_id"],
        "current_task_id": payload.get("current_task_id"),
        "current_track_id": payload.get("current_track_id"),
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


def _normalize_id(value: Any, *, label: str) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, None
    candidate = value.strip()
    try:
        env_store.require_id(candidate, label)
    except ValueError as exc:
        return None, str(exc)
    return candidate, None


def _required_artifact_id(
    *,
    action: str,
    active_buddy: str,
    args: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    artifact_id, parse_error = _normalize_id(args.get("artifact_id"), label="artifact id")
    if parse_error is not None:
        return None, _payload_error(action=action, active_buddy=active_buddy, message=parse_error)
    if artifact_id is None:
        return None, _payload_error(action=action, active_buddy=active_buddy, message="artifact_id is required")
    return artifact_id, None


def _resolve_task_id(
    *,
    action: str,
    context: ArtifactServiceContext,
    args: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    raw_task_id = args.get("task_id")
    if raw_task_id is None:
        raw_task_id = context["instance_payload"].get("current_task_id")
    task_id, parse_error = _normalize_id(raw_task_id, label="task id")
    if parse_error is not None:
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message=parse_error)
    if task_id is None:
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message="task_id is required")
    return task_id, None


def _owned_task(
    *,
    context: ArtifactServiceContext,
    action: str,
    args: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    task_id, error = _resolve_task_id(action=action, context=context, args=args)
    if error is not None:
        return None, error
    assert task_id is not None
    task = env_store.get_task(task_id)
    if task is None:
        return None, _task_lookup_error(action=action, active_buddy=context["active_buddy"], task_id=task_id)
    task_buddy = task.get("buddy")
    if not isinstance(task_buddy, str) or task_buddy != context["active_buddy"]:
        return None, _task_scope_error(
            action=action,
            active_buddy=context["active_buddy"],
            task_id=task_id,
            task_buddy=str(task_buddy or ""),
        )
    return task, None


def _owned_artifact_for_write(
    *,
    context: ArtifactServiceContext,
    action: str,
    args: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    artifact_id, error = _required_artifact_id(action=action, active_buddy=context["active_buddy"], args=args)
    if error is not None:
        return None, error
    assert artifact_id is not None
    artifact = env_store.get_artifact(artifact_id)
    if artifact is None:
        return None, _artifact_lookup_error(action=action, active_buddy=context["active_buddy"], artifact_id=artifact_id)
    task_id = artifact.get("task_id")
    task = env_store.get_task(task_id) if isinstance(task_id, str) else None
    task_buddy = task.get("buddy") if isinstance(task, dict) else None
    if not isinstance(task_buddy, str) or task_buddy != context["active_buddy"]:
        return None, _artifact_scope_error(
            action=action,
            active_buddy=context["active_buddy"],
            artifact_id=artifact_id,
            task_id=task_id if isinstance(task_id, str) else None,
        )
    return artifact, None


def _artifact_read_rejection(
    *,
    context: ArtifactServiceContext,
    artifact_id: str,
    decision: dict[str, Any],
) -> dict[str, Any]:
    track_id = decision.get("track_id")
    command = (
        track_relations.command_hint("track", "join", {"track_id": track_id})
        if isinstance(track_id, str) and track_id
        else track_relations.command_hint("track", "list")
    )
    next_actions: list[dict[str, Any]] = []
    if isinstance(track_id, str) and track_id:
        next_actions.append({"tool": "track", "action": "join", "args": {"track_id": track_id}})
        next_actions.append({"tool": "artifact", "action": "list", "args": {"track_id": track_id}})
    else:
        next_actions.append({"tool": "track", "action": "list"})
    next_actions.append({"tool": "handoff", "action": "list", "args": {"track_id": track_id}})
    payload = _error_payload(
        action="artifact.get",
        active_buddy=context["active_buddy"],
        code="E_ARTIFACT_READ_SCOPE",
        message=str(decision.get("why") or "artifact read is blocked"),
        permission_boundary=str(decision.get("permission_boundary") or "artifact.track_relation"),
        artifact_id=artifact_id,
        task_id=decision.get("source_task_id") if isinstance(decision.get("source_task_id"), str) else None,
        allowed_next_actions=[
            "Use track.get to inspect relation and artifact summaries.",
            "Use track.join to establish active-buddy participation before retrying artifact.get.",
            "Use handoff.list to inspect explicit handoff authorization context.",
        ],
    )
    payload.update(
        {
            "why": str(decision.get("why") or "artifact read is blocked"),
            "relation": str(decision.get("relation") or "none"),
            "missing_preconditions": list(decision.get("missing_preconditions") or []),
            "next_actions": next_actions,
            "command_hint": command,
            "no_content_leak": True,
        }
    )
    return payload


def _artifact_summary(artifact: dict[str, Any], *, include_content: bool) -> dict[str, Any]:
    source_buddy = artifact.get("buddy")
    source_run = artifact.get("source_run_id")
    is_current = bool(artifact.get("is_current"))
    payload = {field: artifact.get(field) for field in _ARTIFACT_PUBLIC_FIELDS}
    payload["source_buddy"] = source_buddy
    payload["source_run"] = source_run
    payload["is_current"] = is_current
    payload["currentness"] = "current" if is_current else "superseded"
    if include_content:
        payload["content"] = artifact.get("content", {})
    return payload


def _artifact_rows_for_task(task: dict[str, Any], *, include_content: bool) -> list[dict[str, Any]]:
    artifact_map = {artifact["id"]: artifact for artifact in env_store.list_artifacts()}
    rows = [
        _artifact_summary(artifact_map[artifact_id], include_content=include_content)
        for artifact_id in task.get("artifact_ids", [])
        if artifact_id in artifact_map
    ]
    rows.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("id") or "")), reverse=True)
    return rows


def _allowed_artifact_kinds(context: ArtifactServiceContext) -> list[str]:
    buddy = get_buddy(context["manifest"], context["active_buddy"])
    kinds = buddy.get("artifact_kinds", []) if isinstance(buddy, dict) else []
    return [item for item in kinds if isinstance(item, str)]


def _validate_kind(
    *,
    action: str,
    context: ArtifactServiceContext,
    raw_kind: Any,
    task_id: str,
) -> tuple[str | None, dict[str, Any] | None]:
    if not isinstance(raw_kind, str) or not raw_kind.strip():
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message="kind is required")
    kind = raw_kind.strip()
    try:
        env_store.require_id(kind, "artifact.kind")
    except ValueError as exc:
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message=str(exc))
    if kind not in set(_allowed_artifact_kinds(context)):
        return None, _kind_error(action=action, context=context, kind=kind, task_id=task_id)
    return kind, None


def _validate_source_run(
    *,
    action: str,
    context: ArtifactServiceContext,
    raw_source_run_id: Any,
    task_id: str,
    artifact_id: str | None = None,
) -> tuple[str | None, dict[str, Any] | None]:
    source_run_id, parse_error = _normalize_id(raw_source_run_id, label="artifact.source_run_id")
    if parse_error is not None:
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message=parse_error)
    if source_run_id is None:
        return None, _source_run_error(
            action=action,
            active_buddy=context["active_buddy"],
            message="source_run_id is required",
            task_id=task_id,
            artifact_id=artifact_id,
        )

    reservation_path = env_store.CONTENT_ROOT / "runs" / "reserved" / f"{source_run_id}.json"
    if not reservation_path.exists():
        return None, _source_run_error(
            action=action,
            active_buddy=context["active_buddy"],
            message=f"run reservation not found: {source_run_id}",
            task_id=task_id,
            artifact_id=artifact_id,
        )
    try:
        reservation = json.loads(reservation_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return None, _source_run_error(
            action=action,
            active_buddy=context["active_buddy"],
            message=f"run reservation is invalid: {source_run_id}: {exc}",
            task_id=task_id,
            artifact_id=artifact_id,
        )
    if not isinstance(reservation, dict) or reservation.get("status") != "reserved":
        return None, _source_run_error(
            action=action,
            active_buddy=context["active_buddy"],
            message=f"run reservation is not active: {source_run_id}",
            task_id=task_id,
            artifact_id=artifact_id,
        )
    if reservation.get("run_id") != source_run_id:
        return None, _source_run_error(
            action=action,
            active_buddy=context["active_buddy"],
            message=f"run reservation id mismatch: {source_run_id}",
            task_id=task_id,
            artifact_id=artifact_id,
        )
    reserved_task_id = reservation.get("task_id")
    if isinstance(reserved_task_id, str) and reserved_task_id and reserved_task_id != task_id:
        return None, _source_run_error(
            action=action,
            active_buddy=context["active_buddy"],
            message=f"run reservation task mismatch: {source_run_id}",
            task_id=task_id,
            artifact_id=artifact_id,
        )
    reservation_instance = reservation.get("instance_id")
    if isinstance(reservation_instance, str) and reservation_instance and reservation_instance != context["instance_id"]:
        return None, _source_run_error(
            action=action,
            active_buddy=context["active_buddy"],
            message=f"run reservation instance mismatch: {source_run_id}",
            task_id=task_id,
            artifact_id=artifact_id,
        )
    turn_identity = reservation.get("turn_identity")
    reserved_buddy = turn_identity.get("active_buddy") if isinstance(turn_identity, dict) else None
    if isinstance(reserved_buddy, str) and reserved_buddy and reserved_buddy != context["active_buddy"]:
        return None, _source_run_error(
            action=action,
            active_buddy=context["active_buddy"],
            message=f"run reservation buddy mismatch: {source_run_id}",
            task_id=task_id,
            artifact_id=artifact_id,
        )
    return source_run_id, None


def _next_artifact_id(*, task_id: str, kind: str) -> str:
    while True:
        candidate = f"art-{task_id}-{kind}-{uuid.uuid4().hex[:8]}"
        if env_store.get_artifact(candidate) is None:
            return candidate


def _normalized_create_payload(
    *,
    action: str,
    context: ArtifactServiceContext,
    args: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    task, error = _owned_task(context=context, action=action, args=args)
    if error is not None:
        return None, error
    assert task is not None
    task_id = str(task["id"])

    kind, error = _validate_kind(action=action, context=context, raw_kind=args.get("kind"), task_id=task_id)
    if error is not None:
        return None, error
    assert kind is not None

    title = args.get("title")
    if not isinstance(title, str) or not title.strip():
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message="title is required")
    summary = args.get("summary", "")
    if summary is None:
        summary = ""
    if not isinstance(summary, str):
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message="summary must be a string")
    content = args.get("content")
    if not isinstance(content, dict):
        return None, _payload_error(action=action, active_buddy=context["active_buddy"], message="content must be an object")

    raw_artifact_id = args.get("artifact_id")
    if raw_artifact_id is None:
        artifact_id = _next_artifact_id(task_id=task_id, kind=kind)
    else:
        artifact_id, parse_error = _normalize_id(raw_artifact_id, label="artifact id")
        if parse_error is not None:
            return None, _payload_error(action=action, active_buddy=context["active_buddy"], message=parse_error)
        if artifact_id is None:
            return None, _payload_error(
                action=action,
                active_buddy=context["active_buddy"],
                message="artifact_id must be a non-empty string when provided",
            )
        if env_store.get_artifact(artifact_id) is not None:
            return None, _payload_error(
                action=action,
                active_buddy=context["active_buddy"],
                message=f"artifact already exists: {artifact_id}",
                artifact_id=artifact_id,
                task_id=task_id,
            )

    source_run_id, error = _validate_source_run(
        action=action,
        context=context,
        raw_source_run_id=args.get("source_run_id"),
        task_id=task_id,
        artifact_id=artifact_id,
    )
    if error is not None:
        return None, error
    assert source_run_id is not None

    return {
        "artifact_id": artifact_id,
        "task_id": task_id,
        "buddy": context["active_buddy"],
        "kind": kind,
        "title": title.strip(),
        "summary": summary,
        "content": content,
        "source_run_id": source_run_id,
    }, None


def list_artifacts_for_track(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.list"
    permission_error = _require_permission(context, _READ_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_LIST_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    track_id_raw = args.get("track_id")
    if not isinstance(track_id_raw, str) or not track_id_raw.strip():
        return _payload_error(action=action, active_buddy=context["active_buddy"], message="track_id is required")
    try:
        track_id = env_store.require_id(track_id_raw.strip(), "track id")
    except ValueError as exc:
        return _payload_error(action=action, active_buddy=context["active_buddy"], message=str(exc))
    track = env_store.get_track(track_id)
    if track is None:
        payload = _error_payload(
            action=action,
            active_buddy=context["active_buddy"],
            code="E_TRACK_NOT_FOUND",
            message=f"track not found: {track_id}",
            permission_boundary="track.lookup",
            allowed_next_actions=[
                "Use track.list to inspect available track ids.",
                "Retry artifact.list with a valid track id.",
            ],
        )
        payload.update(
            {
                "track_id": track_id,
                "relation": "none",
                "missing_preconditions": ["track_id must reference an existing track"],
                "next_actions": [{"tool": "track", "action": "list"}],
                "command_hint": track_relations.command_hint("track", "list"),
                "no_content_leak": True,
            }
        )
        return payload
    relation = track_relations.track_relation_for_buddy(track, context["active_buddy"])
    rows = track_relations.current_artifact_rows_for_track(track_id, context["active_buddy"])
    return {
        "ok": True,
        "tool": "artifact",
        "action": action,
        "active_buddy": context["active_buddy"],
        "track_id": track_id,
        "relation": relation.get("relation"),
        "artifacts": rows,
        "current_binding": _current_binding(context),
        "next_actions": [
            {"tool": "track", "action": "get", "args": {"track_id": track_id}},
            {"tool": "artifact", "action": "get", "args": {"artifact_id": "<artifact-id>"}},
            {"tool": "track", "action": "join", "args": {"track_id": track_id}},
        ],
        "command_hint": track_relations.command_hint("track", "get", {"track_id": track_id}),
        "allowed_next_actions": [
            "Use artifact.get --artifact-id <artifact-id> for full-body reads.",
            "Use track.join --track-id <track-id> when readable_by_current_buddy is false.",
        ],
    }


def get_artifact_for_active_buddy(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.get"
    permission_error = _require_permission(context, _READ_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_GET_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    artifact_id, parse_error = _required_artifact_id(action=action, active_buddy=context["active_buddy"], args=args)
    if parse_error is not None:
        parse_error["no_content_leak"] = True
        parse_error["relation"] = "none"
        parse_error["missing_preconditions"] = ["artifact_id must be a valid id"]
        parse_error["why"] = parse_error.get("error", {}).get("message", "invalid artifact id")
        parse_error["next_actions"] = [{"tool": "track", "action": "list"}]
        parse_error["command_hint"] = track_relations.command_hint("track", "list")
        return parse_error
    assert isinstance(artifact_id, str)
    artifact = env_store.get_artifact(artifact_id)
    if artifact is None:
        return _artifact_lookup_error(action=action, active_buddy=context["active_buddy"], artifact_id=artifact_id)
    decision = track_relations.artifact_read_decision(artifact, context["active_buddy"])
    if not bool(decision.get("allowed")):
        return _artifact_read_rejection(context=context, artifact_id=artifact_id, decision=decision)
    relation = str(decision.get("relation") or "none")
    track_id = decision.get("track_id") if isinstance(decision.get("track_id"), str) else None
    if relation == "owner":
        next_actions = [
            {"tool": "artifact", "action": "create_revision", "args": {"task_id": artifact.get("task_id")}},
            {"tool": "artifact", "action": "update_metadata", "args": {"artifact_id": artifact.get("id")}},
        ]
        command_hint = track_relations.command_hint("artifact", "create_revision")
        allowed_next_actions = [
            "Use artifact.create_revision instead of overwriting artifact content in place.",
            "Use artifact.update_metadata for title or summary changes only.",
        ]
    else:
        next_actions = []
        if isinstance(track_id, str) and track_id:
            next_actions.append({"tool": "track", "action": "get", "args": {"track_id": track_id}})
            next_actions.append({"tool": "artifact", "action": "list", "args": {"track_id": track_id}})
            next_actions.append({"tool": "handoff", "action": "list", "args": {"track_id": track_id}})
            command_hint = track_relations.command_hint("track", "get", {"track_id": track_id})
        else:
            next_actions.append({"tool": "track", "action": "list"})
            command_hint = track_relations.command_hint("track", "list")
        allowed_next_actions = [
            "Use track.get to inspect track context and buddy relation for this foreign artifact.",
            "Use artifact.list with the source track to inspect readable current artifacts only.",
            "Use handoff.list to inspect explicit cross-buddy handoff authorization context.",
        ]
    return {
        "ok": True,
        "tool": "artifact",
        "action": action,
        "active_buddy": context["active_buddy"],
        "artifact_id": artifact["id"],
        "task_id": artifact["task_id"],
        "artifact": _artifact_summary(artifact, include_content=True),
        "relation": relation,
        "readable_by_current_buddy": True,
        "current_binding": _current_binding(context),
        "next_actions": next_actions,
        "command_hint": command_hint,
        "allowed_next_actions": allowed_next_actions,
    }


def get_current_artifacts_for_active_task(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.get_current"
    permission_error = _require_permission(context, _READ_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_GET_CURRENT_FIELDS,
    )
    if fields_error is not None:
        return fields_error

    current_task_id = context["instance_payload"].get("current_task_id")
    if not isinstance(current_task_id, str) or not current_task_id.strip():
        return {
            "ok": True,
            "tool": "artifact",
            "action": action,
            "active_buddy": context["active_buddy"],
            "task_id": None,
            "artifacts": [],
            "current_binding": _current_binding(context),
            "allowed_next_actions": ["Use task.set_current before reading current artifact revisions."],
        }
    task, error = _owned_task(context=context, action=action, args={"task_id": current_task_id})
    if error is not None:
        return error
    assert task is not None

    kind_filter = args.get("kind")
    if kind_filter is not None and (not isinstance(kind_filter, str) or not kind_filter.strip()):
        return _payload_error(action=action, active_buddy=context["active_buddy"], message="kind must be a non-empty string")
    normalized_kind = kind_filter.strip() if isinstance(kind_filter, str) else None
    artifact_slots = task.get("artifact_slots", {})
    artifact_ids: list[str] = []
    if isinstance(artifact_slots, dict):
        for kind, row in artifact_slots.items():
            if normalized_kind is not None and kind != normalized_kind:
                continue
            if isinstance(row, dict) and isinstance(row.get("current_artifact_id"), str):
                artifact_ids.append(row["current_artifact_id"])

    artifact_map = {artifact["id"]: artifact for artifact in env_store.list_artifacts()}
    rows = [
        _artifact_summary(artifact_map[artifact_id], include_content=True)
        for artifact_id in artifact_ids
        if artifact_id in artifact_map
    ]
    rows.sort(key=lambda row: (str(row.get("kind") or ""), str(row.get("id") or "")))
    return {
        "ok": True,
        "tool": "artifact",
        "action": action,
        "active_buddy": context["active_buddy"],
        "task_id": task["id"],
        "artifacts": rows,
        "current_binding": _current_binding(context),
        "allowed_next_actions": [
            "Use artifact.get for a specific full artifact record.",
            "Use artifact.create_revision to replace the current revision for a kind.",
        ],
    }


def validate_artifact_payload(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.validate_payload"
    permission_error = _require_permission(context, _CREATE_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_CREATE_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    normalized, error = _normalized_create_payload(action=action, context=context, args=args)
    if error is not None:
        return error
    assert normalized is not None
    return {
        "ok": True,
        "tool": "artifact",
        "action": action,
        "active_buddy": context["active_buddy"],
        "task_id": normalized["task_id"],
        "artifact_id": normalized["artifact_id"],
        "normalized": {key: value for key, value in normalized.items() if key != "content"},
        "current_binding": _current_binding(context),
        "allowed_next_actions": ["Use artifact.create_revision with the validated payload when ready to write."],
    }


def create_artifact_revision(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.create_revision"
    permission_error = _require_permission(context, _CREATE_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_CREATE_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    normalized, error = _normalized_create_payload(action=action, context=context, args=args)
    if error is not None:
        return error
    assert normalized is not None
    artifact = env_store.create_artifact(
        artifact_id=normalized["artifact_id"],
        title=normalized["title"],
        buddy=normalized["buddy"],
        kind=normalized["kind"],
        task_id=normalized["task_id"],
        source_run_id=normalized["source_run_id"],
        summary=normalized["summary"],
        content=normalized["content"],
    )
    return {
        "ok": True,
        "tool": "artifact",
        "action": action,
        "active_buddy": context["active_buddy"],
        "task_id": artifact["task_id"],
        "artifact_id": artifact["id"],
        "artifact": _artifact_summary(artifact, include_content=True),
        "current_binding": _current_binding(context),
        "allowed_next_actions": [
            "Use artifact.get_current to confirm the promoted current revision.",
            "Include the artifact in the run result/audit path before completing the turn.",
        ],
    }


def update_artifact_metadata(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.update_metadata"
    permission_error = _require_permission(context, _UPDATE_PERMISSION, action)
    if permission_error is not None:
        return permission_error
    fields_error = _ensure_allowed_fields(
        action=action,
        active_buddy=context["active_buddy"],
        args=args,
        allowed_fields=_UPDATE_METADATA_FIELDS,
    )
    if fields_error is not None:
        return fields_error
    artifact, error = _owned_artifact_for_write(context=context, action=action, args=args)
    if error is not None:
        return error
    assert artifact is not None
    source_run_id, error = _validate_source_run(
        action=action,
        context=context,
        raw_source_run_id=args.get("source_run_id"),
        task_id=str(artifact["task_id"]),
        artifact_id=str(artifact["id"]),
    )
    if error is not None:
        return error
    assert source_run_id is not None

    patch: dict[str, Any] = {"source_run_id": source_run_id}
    title = args.get("title")
    if title is not None:
        if not isinstance(title, str) or not title.strip():
            return _payload_error(action=action, active_buddy=context["active_buddy"], message="title must be a non-empty string")
        patch["title"] = title.strip()
    summary = args.get("summary")
    if summary is not None:
        if not isinstance(summary, str):
            return _payload_error(action=action, active_buddy=context["active_buddy"], message="summary must be a string")
        patch["summary"] = summary
    if set(patch) == {"source_run_id"}:
        return _payload_error(
            action=action,
            active_buddy=context["active_buddy"],
            message="update_metadata requires title or summary",
            artifact_id=str(artifact["id"]),
            task_id=str(artifact["task_id"]),
        )

    updated = env_store.update_artifact(str(artifact["id"]), patch)
    return {
        "ok": True,
        "tool": "artifact",
        "action": action,
        "active_buddy": context["active_buddy"],
        "task_id": updated["task_id"],
        "artifact_id": updated["id"],
        "artifact": _artifact_summary(updated, include_content=True),
        "current_binding": _current_binding(context),
        "allowed_next_actions": ["Use artifact.get to confirm metadata changes."],
    }
