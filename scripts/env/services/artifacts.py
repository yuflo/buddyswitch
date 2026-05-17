#!/usr/bin/env python3
"""Runless artifact services."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.services import artifact_visibility
from env.services import source_refs as source_ref_service
from env.tools import responses as tool_responses


class ArtifactServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


_LIST_FIELDS = {"track_id"}
_GET_FIELDS = {"artifact_id"}
_VALIDATE_FIELDS = {"artifact_id", "task_id", "kind", "title", "summary", "content", "source_refs", "read_claim"}
_CREATE_FIELDS = {"artifact_id", "task_id", "kind", "title", "summary", "content", "source_refs", "read_claim"}
_UPDATE_FIELDS = {"artifact_id", "title", "summary", "source_refs", "read_claim"}
_LEGACY_SOURCE_RUN = "source" + "_run_id"


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    correctable_fields: list[str] | None = None
    if "task_id" in message:
        correctable_fields = ["task_id"]
    elif "artifact_id" in message:
        correctable_fields = ["artifact_id"]
    elif "kind" in message:
        correctable_fields = ["kind"]
    elif "title" in message:
        correctable_fields = ["title"]
    elif "content" in message:
        correctable_fields = ["content"]
    elif "source_refs" in message:
        correctable_fields = ["source_refs"]
    elif "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            correctable_fields = [row.strip() for row in suffix.split(",") if row.strip()]
    return tool_responses.rejection(
        tool="artifact",
        action=action,
        active_buddy=active_buddy,
        code="E_ARTIFACT_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Artifact payload is invalid.",
        why_blocked=message,
        impact="No artifact or task state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix artifact payload fields and retry.",
        allowed_next_actions=[
            "Use track.list/track.get to inspect candidate track and task ids.",
            "Retry with explicit task_id and supported fields.",
        ],
        correctable_fields=correctable_fields,
    )


def _reject_scope(*, action: str, active_buddy: str, boundary: str, message: str, code: str = "E_ARTIFACT_SCOPE") -> dict[str, Any]:
    correctable_fields: list[str] = []
    for field in ("task_id", "artifact_id", "source_refs"):
        if field in message:
            correctable_fields.append(field)
    if not correctable_fields:
        correctable_fields = ["artifact_id", "task_id"]
    return tool_responses.rejection(
        tool="artifact",
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=boundary,
        human_summary="Artifact scope check failed.",
        why_blocked=message,
        impact="No artifact or task state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Use readable/owned task and artifact ids.",
        allowed_next_actions=[
            "Use task.list to inspect owned tasks.",
            "Use artifact.list to inspect readable artifacts.",
        ],
        correctable_fields=correctable_fields,
    )


def _require_allowed_fields(action: str, args: dict[str, Any], active_buddy: str) -> dict[str, Any] | None:
    allowed_map = {
        "artifact.list": _LIST_FIELDS,
        "artifact.get": _GET_FIELDS,
        "artifact.validate_payload": _VALIDATE_FIELDS,
        "artifact.create_revision": _CREATE_FIELDS,
        "artifact.update_metadata": _UPDATE_FIELDS,
    }
    allowed = allowed_map[action]
    unknown = sorted(key for key in args if key not in allowed)
    if unknown:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"unsupported payload fields: {', '.join(unknown)}")
    if _LEGACY_SOURCE_RUN in args:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="legacy artifact run lineage field is retired; use source_refs",
        )
    return None


def _normalized_create_payload(*, args: dict[str, Any], active_buddy: str, action: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    task_id = args.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="task_id is required")
    task_id = task_id.strip()

    task = env_store.get_task(task_id)
    if task is None:
        return None, _reject_payload(action=action, active_buddy=active_buddy, message=f"task not found: {task_id}")
    if task.get("buddy") != active_buddy:
        return None, _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary="task.buddy_scope",
            code="E_ARTIFACT_TASK_SCOPE",
            message=f"task '{task_id}' is owned by buddy '{task.get('buddy')}'",
        )

    kind = args.get("kind")
    title = args.get("title")
    content = args.get("content")
    if not isinstance(kind, str) or not kind.strip():
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="kind is required")
    if not isinstance(title, str) or not title.strip():
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="title is required")
    if not isinstance(content, dict):
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="content must be a JSON object")

    summary = args.get("summary")
    if summary is None:
        summary = ""
    if not isinstance(summary, str):
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")

    read_claim = args.get("read_claim")
    if read_claim is not None and not isinstance(read_claim, str):
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="read_claim must be a string")

    try:
        normalized_refs, scope_error = source_ref_service.normalize_source_refs(
            args.get("source_refs"),
            active_buddy=active_buddy,
            read_claim=read_claim if isinstance(read_claim, str) else None,
            allow_buddybox=True,
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

    artifact_id = args.get("artifact_id")
    if artifact_id is not None and (not isinstance(artifact_id, str) or not artifact_id.strip()):
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="artifact_id must be a non-empty string")

    payload = {
        "artifact_id": artifact_id.strip() if isinstance(artifact_id, str) and artifact_id.strip() else None,
        "task_id": task_id,
        "kind": kind.strip(),
        "title": title.strip(),
        "summary": summary,
        "content": content,
        "source_refs": normalized_refs,
    }
    return payload, None


def _artifact_response_row(artifact: dict[str, Any], active_buddy: str) -> dict[str, Any]:
    row = artifact_visibility.artifact_summary_row(artifact, active_buddy)
    row["task_id"] = artifact.get("task_id")
    row["supersedes_artifact_id"] = artifact.get("supersedes_artifact_id")
    row["content"] = artifact.get("content")
    row["updated_at"] = artifact.get("updated_at")
    row["created_at"] = artifact.get("created_at")
    return row


def list_artifacts_for_track(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.list"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    track_id = args.get("track_id")
    if not isinstance(track_id, str) or not track_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="track_id is required")
    track_id = track_id.strip()

    track = env_store.get_track(track_id)
    if track is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"track not found: {track_id}")
    if track.get("status") == "archived":
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary="track.lifecycle_status",
            message=f"track '{track_id}' is archived and cannot be read via artifact.list",
            code="E_TRACK_ARCHIVED",
        )

    rows = artifact_visibility.current_artifact_rows_for_track(track_id, active_buddy)
    return tool_responses.success(
        tool="artifact",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Returned {len(rows)} artifact summary row(s) for track '{track_id}' without full artifact content.",
        state_changed=False,
        durability="none",
        read_scope="track-related readable artifact summaries",
        allowed_next_actions=[
            "Use artifact.get with readable artifact_id for full record.",
            "Use track.join when relation is missing for intended work track.",
        ],
        extra={"track_id": track_id, "relation": "owner-or-track_task", "artifacts": rows},
    )


def get_artifact_for_active_buddy(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.get"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    artifact_id = args.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="artifact_id is required")
    artifact_id = artifact_id.strip()

    artifact = env_store.get_artifact(artifact_id)
    if artifact is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"artifact not found: {artifact_id}")

    decision = artifact_visibility.artifact_read_decision(artifact, active_buddy)
    if not bool(decision.get("allowed")):
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary=str(decision.get("permission_boundary", "artifact.read_scope")),
            message=str(decision.get("why", "artifact read denied")),
            code="E_ARTIFACT_READ_SCOPE",
        )

    row = _artifact_response_row(artifact, active_buddy)
    return tool_responses.success(
        tool="artifact",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Read one readable artifact '{artifact_id}' including full artifact body content.",
        state_changed=False,
        durability="none",
        read_scope="one readable artifact record with full body content",
        allowed_next_actions=[
            "Use artifact.update_metadata to revise title/summary/source_refs.",
            "Use artifact.create_revision with explicit task_id for a new revision.",
        ],
        extra={"artifact_id": artifact_id, "artifact": row},
    )


def validate_artifact_payload(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.validate_payload"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    normalized, error = _normalized_create_payload(args=args, active_buddy=active_buddy, action=action)
    if error is not None:
        return error
    assert isinstance(normalized, dict)

    return tool_responses.success(
        tool="artifact",
        action=action,
        active_buddy=active_buddy,
        effect_summary="Validated and normalized artifact revision payload without writing runtime state.",
        state_changed=False,
        durability="none",
        validation_only=True,
        read_scope="request payload validation",
        allowed_next_actions=["Use artifact.create_revision with the same normalized payload."],
        allowed_next_action_options=[
            tool_responses.next_action_option(
                tool="artifact",
                action="create_revision",
                option_id="artifact_create_when_host_decides_to_write",
                reason="Use when the host decides to write the validated artifact payload.",
            )
        ],
        extra={"normalized": normalized},
    )


def create_artifact_revision(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.create_revision"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    normalized, error = _normalized_create_payload(args=args, active_buddy=active_buddy, action=action)
    if error is not None:
        return error
    assert isinstance(normalized, dict)

    try:
        artifact = env_store.create_artifact(
            artifact_id=normalized["artifact_id"],
            title=normalized["title"],
            buddy=active_buddy,
            kind=normalized["kind"],
            task_id=normalized["task_id"],
            summary=normalized["summary"],
            content=normalized["content"],
            created_by=active_buddy,
            source_refs=normalized.get("source_refs"),
        )
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    row = _artifact_response_row(artifact, active_buddy)
    return tool_responses.success(
        tool="artifact",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Created durable artifact revision '{artifact['id']}' for task '{artifact['task_id']}' and updated task linkage.",
        state_changed=True,
        durability="durable",
        created_ids=[artifact["id"]],
        updated_ids=[artifact["task_id"]],
        state_changes=[
            {"object_type": "artifact", "change": "revision_created", "artifact_id": artifact["id"]},
            {"object_type": "task", "change": "artifact_linkage_updated", "task_id": artifact["task_id"]},
        ],
        allowed_next_actions=[
            "Use artifact.get with artifact_id for full verification.",
        ],
        extra={"artifact_id": artifact["id"], "artifact": row},
    )


def update_artifact_metadata(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.update_metadata"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    artifact_id = args.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="artifact_id is required")
    artifact_id = artifact_id.strip()

    artifact = env_store.get_artifact(artifact_id)
    if artifact is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"artifact not found: {artifact_id}")
    if artifact.get("buddy") != active_buddy:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary="artifact.buddy_scope",
            code="E_ARTIFACT_BUDDY_SCOPE",
            message=f"artifact '{artifact_id}' is owned by buddy '{artifact.get('buddy')}'",
        )

    patch: dict[str, Any] = {}
    if "title" in args:
        title = args["title"]
        if not isinstance(title, str) or not title.strip():
            return _reject_payload(action=action, active_buddy=active_buddy, message="title must be a non-empty string")
        patch["title"] = title.strip()
    if "summary" in args:
        summary = args["summary"]
        if not isinstance(summary, str):
            return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")
        patch["summary"] = summary
    if "source_refs" in args:
        read_claim = args.get("read_claim")
        if read_claim is not None and not isinstance(read_claim, str):
            return _reject_payload(action=action, active_buddy=active_buddy, message="read_claim must be a string")
        try:
            normalized_refs, scope_error = source_ref_service.normalize_source_refs(
                args.get("source_refs"),
                active_buddy=active_buddy,
                read_claim=read_claim if isinstance(read_claim, str) else None,
                allow_buddybox=True,
            )
        except ValueError as exc:
            return _reject_scope(
                action=action,
                active_buddy=active_buddy,
                boundary="source_refs.required_fields",
                message=str(exc),
                code="E_SOURCE_REFS",
            )
        if isinstance(scope_error, dict):
            return _reject_scope(
                action=action,
                active_buddy=active_buddy,
                boundary=str(scope_error.get("permission_boundary", "source_refs.read_scope")),
                message=str(scope_error.get("why_blocked", "source_refs read scope denied")),
                code="E_SOURCE_REFS_READ_SCOPE",
            )
        patch["source_refs"] = normalized_refs

    if not patch:
        return _reject_payload(action=action, active_buddy=active_buddy, message="at least one metadata field is required")

    try:
        updated = env_store.update_artifact(artifact_id, patch)
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    row = _artifact_response_row(updated, active_buddy)
    return tool_responses.success(
        tool="artifact",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Updated metadata fields for artifact '{artifact_id}' without replacing artifact body content.",
        state_changed=True,
        durability="durable",
        updated_ids=[artifact_id],
        state_changes=[{"object_type": "artifact", "change": "metadata_updated", "artifact_id": artifact_id}],
        allowed_next_actions=[
            "Use artifact.get for updated record.",
        ],
        extra={"artifact_id": artifact_id, "artifact": row},
    )
