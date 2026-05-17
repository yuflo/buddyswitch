#!/usr/bin/env python3
"""Artifact services aligned to direct track publication model."""

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


_GET_FIELDS = {"artifact_id"}
_CREATE_FIELDS = {"artifact_id", "kind", "title", "summary", "content", "source_refs", "read_claim", "task_id"}
_UPDATE_FIELDS = {"artifact_id", "title", "summary", "source_refs", "read_claim"}
_LEGACY_SOURCE_RUN = "source" + "_run_id"


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    correctable_fields: list[str] | None = None
    if "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            correctable_fields = [row.strip() for row in suffix.split(",") if row.strip()]
    else:
        for field in ("artifact_id", "kind", "title", "summary", "content", "source_refs", "task_id"):
            if field in message:
                correctable_fields = [field]
                break
    return tool_responses.rejection(
        tool="artifact",
        action=action,
        active_buddy=active_buddy,
        code="E_ARTIFACT_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Artifact payload is invalid.",
        why_blocked=message,
        impact="No artifact state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix artifact payload fields and retry.",
        allowed_next_actions=[
            "Use track.open to discover current shared artifact ids.",
            "Retry with supported payload fields only.",
        ],
        correctable_fields=correctable_fields,
    )


def _reject_scope(*, action: str, active_buddy: str, boundary: str, message: str, code: str = "E_ARTIFACT_SCOPE") -> dict[str, Any]:
    return tool_responses.rejection(
        tool="artifact",
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=boundary,
        human_summary="Artifact scope check failed.",
        why_blocked=message,
        impact="No artifact state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Use readable or active-buddy-owned artifact ids.",
        allowed_next_actions=[
            "Use track.open for shared artifact refs.",
            "Use artifact.create_revision for a private draft owned by the active buddy.",
        ],
        correctable_fields=["artifact_id"],
    )


def _require_allowed_fields(action: str, args: dict[str, Any], active_buddy: str) -> dict[str, Any] | None:
    allowed = _GET_FIELDS if action == "artifact.get" else _CREATE_FIELDS if action == "artifact.create_revision" else _UPDATE_FIELDS
    unknown = sorted(key for key in args if key not in allowed)
    if unknown:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"unsupported payload fields: {', '.join(unknown)}")
    if _LEGACY_SOURCE_RUN in args:
        return _reject_payload(action=action, active_buddy=active_buddy, message="legacy artifact run lineage field is retired; use source_refs")
    return None


def _artifact_response_row(artifact: dict[str, Any], active_buddy: str) -> dict[str, Any]:
    return artifact_visibility.artifact_summary_row(artifact, active_buddy)


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
        effect_summary=f"Read one readable artifact '{artifact_id}' including full content.",
        state_changed=False,
        durability="none",
        read_scope="one readable artifact",
        allowed_next_actions=[
            "Use artifact.update_metadata to revise title/summary/source_refs.",
            "Use track.open to inspect current shared materials.",
        ],
        extra={"artifact_id": artifact_id, "artifact": row},
    )


def create_artifact_revision(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.create_revision"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    if "task_id" in args:
        return _reject_payload(action=action, active_buddy=active_buddy, message="task_id is retired for artifact.create_revision")

    kind = args.get("kind")
    title = args.get("title")
    summary = args.get("summary", "")
    content = args.get("content")
    if not isinstance(kind, str) or not kind.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="kind is required")
    if not isinstance(title, str) or not title.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="title is required")
    if not isinstance(summary, str):
        return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")
    if not isinstance(content, dict):
        return _reject_payload(action=action, active_buddy=active_buddy, message="content must be a JSON object")

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

    artifact_id = args.get("artifact_id")
    if artifact_id is not None and (not isinstance(artifact_id, str) or not artifact_id.strip()):
        return _reject_payload(action=action, active_buddy=active_buddy, message="artifact_id must be a non-empty string")

    try:
        artifact = env_store.create_artifact(
            artifact_id=artifact_id.strip() if isinstance(artifact_id, str) and artifact_id.strip() else None,
            title=title.strip(),
            kind=kind.strip(),
            created_by=active_buddy,
            summary=summary,
            content=content,
            source_refs=normalized_refs,
            published_to_track=None,
            publication_role=None,
        )
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    row = _artifact_response_row(artifact, active_buddy)
    return tool_responses.success(
        tool="artifact",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Created one private draft artifact '{artifact['id']}' without task relation.",
        state_changed=True,
        durability="durable",
        created_ids=[artifact["id"]],
        state_changes=[{"object_type": "artifact", "change": "created", "artifact_id": artifact["id"]}],
        allowed_next_actions=[
            "Use track.add_material or track.add_proof to publish this artifact.",
            "Use artifact.update_metadata to refine metadata.",
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
    if artifact.get("created_by") != active_buddy:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary="artifact.buddy_scope",
            message=f"artifact '{artifact_id}' is owned by buddy '{artifact.get('created_by')}'",
            code="E_ARTIFACT_SCOPE",
        )

    patch: dict[str, Any] = {}
    for field in ("title", "summary"):
        if field in args:
            patch[field] = args[field]
    if "title" in patch and (not isinstance(patch["title"], str) or not patch["title"].strip()):
        return _reject_payload(action=action, active_buddy=active_buddy, message="title must be a non-empty string")
    if "summary" in patch and not isinstance(patch["summary"], str):
        return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")

    if "source_refs" in args or "read_claim" in args:
        read_claim = args.get("read_claim")
        if read_claim is not None and not isinstance(read_claim, str):
            return _reject_payload(action=action, active_buddy=active_buddy, message="read_claim must be a string")
        try:
            refs, scope_error = source_ref_service.normalize_source_refs(
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
        patch["source_refs"] = refs

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
        effect_summary=f"Updated metadata for artifact '{artifact_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[artifact_id],
        state_changes=[{"object_type": "artifact", "change": "metadata_updated", "artifact_id": artifact_id}],
        allowed_next_actions=["Use artifact.get to verify updated metadata."],
        extra={"artifact_id": artifact_id, "artifact": row},
    )
