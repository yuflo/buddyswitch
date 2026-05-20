#!/usr/bin/env python3
"""Artifact services aligned to draft-first publication model."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from env.domain import artifact_visibility as artifact_visibility_domain
from env.domain import source_refs as source_ref_domain
from env.repos import artifacts as artifact_repo
from env.tools.artifact import contract as tool_contract
from env.tools import responses as tool_responses


class ArtifactServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


_LEGACY_SOURCE_RUN = "source" + "_run_id"


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    correctable_fields: list[str] | None = None
    if "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            correctable_fields = [row.strip() for row in suffix.split(",") if row.strip()]
    else:
        for field in ("artifact_id", "title", "summary", "template", "body", "supersedes_artifact_id", "source_refs"):
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
        impact="No artifact or track state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix artifact payload fields and retry.",
        allowed_next_actions=[
            "Use track.open to discover current shared artifact ids.",
            "Retry with supported payload fields only.",
        ],
        correctable_fields=correctable_fields,
    )


def _reject_publication_path(
    *,
    active_buddy: str,
    field: str,
    why_blocked: str,
) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="artifact",
        action="artifact.create_revision",
        active_buddy=active_buddy,
        code="E_ARTIFACT_PUBLICATION_PATH",
        message=why_blocked,
        permission_boundary="artifact.publication_path",
        human_summary="artifact.create_revision only creates private draft revisions.",
        why_blocked=why_blocked,
        impact="No artifact or track state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Create a draft revision first, then publish through track.add_material or track.add_proof.",
        allowed_next_actions=[
            "Create artifact.create_revision without publication fields.",
            "Use track.add_material with this artifact_id to publish current shared material.",
            "Use track.add_proof with this artifact_id to publish close proof.",
        ],
        correctable_fields=[field],
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
        impact="No artifact or track state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Use readable or active-buddy-owned artifact ids.",
        allowed_next_actions=[
            "Use track.open for shared artifact refs.",
            "Use artifact.create_revision for a private draft owned by the active buddy.",
        ],
        correctable_fields=["artifact_id"],
    )


def _reject_revision_scope(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="artifact",
        action=action,
        active_buddy=active_buddy,
        code="E_ARTIFACT_SCOPE",
        message=message,
        permission_boundary="artifact.revision_scope",
        human_summary="Supersede target is not publishable in the requested draft path.",
        why_blocked=message,
        impact="No artifact or track state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Use a current readable supersedes_artifact_id or omit supersedes_artifact_id.",
        allowed_next_actions=[
            "Use track.open to inspect current shared material/proof ids.",
            "Retry artifact.create_revision with a valid supersedes_artifact_id.",
        ],
        correctable_fields=["supersedes_artifact_id"],
    )


def _require_allowed_fields(action: str, args: dict[str, Any], active_buddy: str) -> dict[str, Any] | None:
    _, action_name = action.split(".", 1)
    allowed = set()
    for row in tool_contract.TOOL_SPEC.get("actions", []):
        if isinstance(row, dict) and row.get("name") == action_name:
            allowed = {field for field in row.get("payload_fields", []) if isinstance(field, str)}
            break
    unknown = sorted(key for key in args if key not in allowed)
    if unknown:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"unsupported payload fields: {', '.join(unknown)}")
    if _LEGACY_SOURCE_RUN in args:
        return _reject_payload(action=action, active_buddy=active_buddy, message="legacy artifact run lineage field is retired; use source_refs")
    return None


def _artifact_response_row(artifact: dict[str, Any], active_buddy: str) -> dict[str, Any]:
    return artifact_visibility_domain.artifact_summary_row(artifact, active_buddy)


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

    artifact = artifact_repo.get_artifact(artifact_id)
    if artifact is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"artifact not found: {artifact_id}")

    decision = artifact_visibility_domain.artifact_read_decision(artifact, active_buddy)
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
        effect_summary=f"Read one readable artifact '{artifact_id}' including full markdown body.",
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
    if "published_to_track" in args:
        return _reject_publication_path(
            active_buddy=active_buddy,
            field="published_to_track",
            why_blocked=(
                "artifact.create_revision creates private drafts; "
                "track.add_material or track.add_proof publishes existing artifacts"
            ),
        )
    if "status" in args:
        return _reject_publication_path(
            active_buddy=active_buddy,
            field="status",
            why_blocked="artifact.create_revision always creates status=draft artifacts",
        )
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    title = args.get("title")
    summary = args.get("summary", "")
    body = args.get("body")
    template = args.get("template")
    supersedes_artifact_id = args.get("supersedes_artifact_id")
    if not isinstance(title, str) or not title.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="title is required")
    if not isinstance(summary, str):
        return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")
    if not isinstance(body, str) or not body.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="body is required")
    if not isinstance(template, str) or template not in artifact_repo.VALID_ARTIFACT_TEMPLATES:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"template must be one of {', '.join(artifact_repo.VALID_ARTIFACT_TEMPLATES)}",
        )
    if supersedes_artifact_id is not None and (not isinstance(supersedes_artifact_id, str) or not supersedes_artifact_id.strip()):
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="supersedes_artifact_id must be a non-empty string",
        )
    normalized_supersedes_artifact_id = (
        supersedes_artifact_id.strip() if isinstance(supersedes_artifact_id, str) and supersedes_artifact_id.strip() else None
    )

    read_claim = args.get("read_claim")
    if read_claim is not None and not isinstance(read_claim, str):
        return _reject_payload(action=action, active_buddy=active_buddy, message="read_claim must be a string")

    try:
        normalized_refs, scope_error = source_ref_domain.normalize_source_refs(
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

    if normalized_supersedes_artifact_id is not None:
        try:
            artifact_visibility_domain.assert_supersedes_target_for_revision(
                supersedes_artifact_id=normalized_supersedes_artifact_id,
                active_buddy=active_buddy,
            )
        except ValueError as exc:
            return _reject_revision_scope(
                action=action,
                active_buddy=active_buddy,
                message=str(exc),
            )

    try:
        artifact = artifact_repo.create_artifact_revision(
            artifact_id=artifact_id.strip() if isinstance(artifact_id, str) and artifact_id.strip() else None,
            title=title.strip(),
            created_by=active_buddy,
            summary=summary,
            body=body,
            template=template,
            source_refs=normalized_refs,
            supersedes_artifact_id=normalized_supersedes_artifact_id,
            authors=[active_buddy],
        )
    except ValueError as exc:
        message = str(exc)
        if "supersedes_artifact_id" in message or "superseded" in message:
            return _reject_revision_scope(
                action=action,
                active_buddy=active_buddy,
                message=message,
            )
        return _reject_payload(action=action, active_buddy=active_buddy, message=message)

    row = _artifact_response_row(artifact, active_buddy)
    return tool_responses.success(
        tool="artifact",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Created one private draft artifact revision '{artifact['id']}' (not shared on track yet).",
        state_changed=True,
        durability="durable",
        created_ids=[artifact["id"]],
        state_changes=[{"object_type": "artifact", "change": "draft_created", "artifact_id": artifact["id"]}],
        allowed_next_actions=[
            "Use track.add_material with this artifact_id when this draft should become current shared material.",
            "Use track.add_proof with this artifact_id when this draft is close proof.",
            "Use artifact.get with this artifact_id to read the full body.",
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

    artifact = artifact_repo.get_artifact(artifact_id)
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
    for field in ("title", "summary", "template", "body"):
        if field in args:
            patch[field] = args[field]
    if "title" in patch and (not isinstance(patch["title"], str) or not patch["title"].strip()):
        return _reject_payload(action=action, active_buddy=active_buddy, message="title must be a non-empty string")
    if "summary" in patch and not isinstance(patch["summary"], str):
        return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")
    if "template" in patch and (not isinstance(patch["template"], str) or patch["template"] not in artifact_repo.VALID_ARTIFACT_TEMPLATES):
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"template must be one of {', '.join(artifact_repo.VALID_ARTIFACT_TEMPLATES)}",
        )
    if "body" in patch and (not isinstance(patch["body"], str) or not patch["body"].strip()):
        return _reject_payload(action=action, active_buddy=active_buddy, message="body must be a non-empty string")

    if "source_refs" in args or "read_claim" in args:
        read_claim = args.get("read_claim")
        if read_claim is not None and not isinstance(read_claim, str):
            return _reject_payload(action=action, active_buddy=active_buddy, message="read_claim must be a string")
        try:
            refs, scope_error = source_ref_domain.normalize_source_refs(
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
        updated = artifact_repo.update_artifact(artifact_id, patch)
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
