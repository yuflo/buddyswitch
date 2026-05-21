#!/usr/bin/env python3
"""Artifact services aligned to draft-first publication model."""

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

class ArtifactServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


_LEGACY_SOURCE_RUN = "source" + "_run_id"


def _template_field_error(allowed_values: tuple[str, ...]) -> dict[str, Any]:
    return {
        "path": "template",
        "message": f"template must be one of {', '.join(allowed_values)}",
        "allowed_values": list(allowed_values),
        "example": "brief",
    }


def _source_refs_field_error() -> dict[str, Any]:
    return {
        "path": "source_refs",
        "message": "source_refs must be a list of supported source_ref objects",
        "expected": [
            {"type": "artifact", "id": "art-..."},
            {"type": "track", "id": "track-..."},
            {"type": "task", "id": "task-..."},
            {"type": "buddybox", "logical_name": "notes/source.txt"},
            {"type": "external", "label": "Product page", "url": "https://example.com"},
            {"type": "note", "label": "Source note"},
        ],
        "example": [{"type": "note", "label": "Source note"}],
    }


def _reject_payload(
    *,
    action: str,
    active_buddy: str,
    message: str,
    field_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
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
    return tool_results.rejection(
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
        field_errors=field_errors,
    )


def _reject_publication_path(
    *,
    active_buddy: str,
    field: str,
    why_blocked: str,
) -> dict[str, Any]:
    return tool_results.rejection(
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


def _reject_scope(
    *,
    action: str,
    active_buddy: str,
    boundary: str,
    message: str,
    code: str = "E_ARTIFACT_SCOPE",
    correctable_fields: list[str] | None = None,
    field_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return tool_results.rejection(
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
        correctable_fields=correctable_fields or ["artifact_id"],
        field_errors=field_errors,
    )


def _reject_revision_scope(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return tool_results.rejection(
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
    for row in _ACTION_DEFINITION_MAP.get("actions", []):
        if isinstance(row, dict) and row.get("name") == action_name:
            allowed = {field for field in row.get("payload_fields", []) if isinstance(field, str)}
            break
    unknown = sorted(key for key in args if key not in allowed)
    if unknown:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"unsupported payload fields: {', '.join(unknown)}")
    if _LEGACY_SOURCE_RUN in args:
        return _reject_payload(action=action, active_buddy=active_buddy, message="legacy artifact run lineage field is retired; use source_refs")
    return None


def _artifact_response_row(artifact: dict[str, Any], active_buddy: str, context: ArtifactServiceContext) -> dict[str, Any]:
    return context.rules.artifact_visibility.artifact_summary_row(artifact, active_buddy)


def _normalize_list_filters(
    args: dict[str, Any],
    active_buddy: str,
    context: ArtifactServiceContext,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    action = "artifact.list"
    track_id: str | None = None
    if "track_id" in args:
        raw_track_id = args.get("track_id")
        if not isinstance(raw_track_id, str) or not raw_track_id.strip():
            return None, _reject_payload(action=action, active_buddy=active_buddy, message="track_id must be a non-empty string")
        normalized_track_id = raw_track_id.strip()
        readable = context.rules.artifact_visibility.assert_track_readable(
            normalized_track_id,
            active_buddy=active_buddy,
            action=action,
        )
        if not bool(readable.get("ok")):
            boundary = str(readable.get("permission_boundary", "artifact.read_scope"))
            message = str(readable.get("message", f"track not found: {normalized_track_id}"))
            if boundary == "request-payload":
                return None, _reject_payload(action=action, active_buddy=active_buddy, message=message)
            return None, _reject_scope(
                action=action,
                active_buddy=active_buddy,
                boundary=boundary,
                message=message,
                code=str(readable.get("code", "E_ARTIFACT_SCOPE")),
                correctable_fields=["track_id"],
            )
        track_id = normalized_track_id

    created_by: str | None = None
    if "created_by" in args:
        raw_created_by = args.get("created_by")
        if not isinstance(raw_created_by, str) or not raw_created_by.strip():
            return None, _reject_payload(action=action, active_buddy=active_buddy, message="created_by must be a non-empty string")
        normalized_created_by = raw_created_by.strip()
        manifest_ids = context.rules.message.manifest_buddy_ids(context["manifest"])
        if normalized_created_by not in manifest_ids:
            return None, _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message="created_by must be one of manifest buddies",
            )
        created_by = normalized_created_by

    template: str | None = None
    if "template" in args:
        raw_template = args.get("template")
        if not isinstance(raw_template, str) or raw_template not in context.repos.artifact.VALID_ARTIFACT_TEMPLATES:
            return None, _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message=f"template must be one of {', '.join(context.repos.artifact.VALID_ARTIFACT_TEMPLATES)}",
                field_errors=[_template_field_error(context.repos.artifact.VALID_ARTIFACT_TEMPLATES)],
            )
        template = raw_template

    status: str | None = None
    if "status" in args:
        raw_status = args.get("status")
        if not isinstance(raw_status, str) or raw_status not in context.repos.artifact.VALID_ARTIFACT_STATUS:
            return None, _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message=f"status must be one of {', '.join(context.repos.artifact.VALID_ARTIFACT_STATUS)}",
            )
        status = raw_status

    q: str | None = None
    if "q" in args:
        raw_q = args.get("q")
        if not isinstance(raw_q, str):
            return None, _reject_payload(action=action, active_buddy=active_buddy, message="q must be a string")
        q = raw_q.strip().lower() or None

    limit = args.get("limit", 20)
    if not isinstance(limit, int) or limit <= 0:
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="limit must be a positive integer")

    return (
        {
            "track_id": track_id,
            "created_by": created_by,
            "template": template,
            "status": status,
            "q": q,
            "limit": limit,
        },
        None,
    )


def list_artifacts_for_active_buddy(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.list"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    filters, filter_error = _normalize_list_filters(args, active_buddy, context)
    if filter_error is not None:
        return filter_error
    assert isinstance(filters, dict)

    rows: list[dict[str, Any]] = []
    for artifact in context.repos.artifact.list_artifacts():
        decision = context.rules.artifact_visibility.artifact_read_decision(artifact, active_buddy)
        if not bool(decision.get("allowed")):
            continue
        if isinstance(filters.get("track_id"), str) and decision.get("track_id") != filters.get("track_id"):
            continue
        if isinstance(filters.get("created_by"), str) and artifact.get("created_by") != filters.get("created_by"):
            continue
        if isinstance(filters.get("template"), str) and artifact.get("template") != filters.get("template"):
            continue
        if isinstance(filters.get("status"), str) and artifact.get("status") != filters.get("status"):
            continue
        query = filters.get("q")
        if isinstance(query, str) and query:
            title = str(artifact.get("title") or "").lower()
            summary = str(artifact.get("summary") or "").lower()
            if query not in title and query not in summary:
                continue

        artifact_id = str(artifact.get("id") or "")
        comment_counts = context.rules.artifact_relations.comment_counts_for_artifact(artifact_id) if artifact_id else {}
        relation_counts = (
            context.rules.artifact_relations.relation_counts_for_artifact(artifact_id=artifact_id, active_buddy=active_buddy)
            if artifact_id
            else {}
        )
        rows.append(
            context.rules.artifact_visibility.artifact_list_row(
                artifact,
                active_buddy,
                comment_counts=comment_counts,
                relation_counts=relation_counts,
            )
        )

    rows.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("artifact_id") or "")), reverse=True)
    limited_rows = rows[: int(filters.get("limit", 20))]
    return tool_results.success(
        tool="artifact",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Returned {len(limited_rows)} readable artifact summary row(s).",
        state_changed=False,
        durability="none",
        read_scope="readable artifact summaries only",
        allowed_next_actions=[
            "Use artifact.get with artifact_id to read full markdown body content.",
            "Use track.open to inspect shared track publication state.",
        ],
        extra={"artifacts": limited_rows, "count": len(limited_rows), "filters": filters},
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

    artifact = context.repos.artifact.get_artifact(artifact_id)
    if artifact is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"artifact not found: {artifact_id}")

    decision = context.rules.artifact_visibility.artifact_read_decision(artifact, active_buddy)
    if not bool(decision.get("allowed")):
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary=str(decision.get("permission_boundary", "artifact.read_scope")),
            message=str(decision.get("why", "artifact read denied")),
            code="E_ARTIFACT_READ_SCOPE",
        )

    row = _artifact_response_row(artifact, active_buddy, context)
    row["relation_summary"] = context.rules.artifact_relations.relation_summary_for_artifact(
        artifact=artifact,
        active_buddy=active_buddy,
    )
    return tool_results.success(
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
    if not isinstance(template, str) or template not in context.repos.artifact.VALID_ARTIFACT_TEMPLATES:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"template must be one of {', '.join(context.repos.artifact.VALID_ARTIFACT_TEMPLATES)}",
            field_errors=[_template_field_error(context.repos.artifact.VALID_ARTIFACT_TEMPLATES)],
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
        normalized_refs, scope_error = context.rules.source_refs.normalize_source_refs(
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
            field_errors=[_source_refs_field_error()],
        )
    if isinstance(scope_error, dict):
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary=str(scope_error.get("permission_boundary", "source_refs.read_scope")),
            message=str(scope_error.get("why_blocked", "source_refs read scope denied")),
            code="E_SOURCE_REFS_READ_SCOPE",
            field_errors=[_source_refs_field_error()],
        )

    artifact_id = args.get("artifact_id")
    if artifact_id is not None and (not isinstance(artifact_id, str) or not artifact_id.strip()):
        return _reject_payload(action=action, active_buddy=active_buddy, message="artifact_id must be a non-empty string")

    if normalized_supersedes_artifact_id is not None:
        try:
            context.rules.artifact_visibility.assert_supersedes_target_for_revision(
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
        artifact = context.repos.artifact.create_artifact_revision(
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

    row = _artifact_response_row(artifact, active_buddy, context)
    return tool_results.success(
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

    artifact = context.repos.artifact.get_artifact(artifact_id)
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
    if "template" in patch and (not isinstance(patch["template"], str) or patch["template"] not in context.repos.artifact.VALID_ARTIFACT_TEMPLATES):
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"template must be one of {', '.join(context.repos.artifact.VALID_ARTIFACT_TEMPLATES)}",
            field_errors=[_template_field_error(context.repos.artifact.VALID_ARTIFACT_TEMPLATES)],
        )
    if "body" in patch and (not isinstance(patch["body"], str) or not patch["body"].strip()):
        return _reject_payload(action=action, active_buddy=active_buddy, message="body must be a non-empty string")

    if "source_refs" in args or "read_claim" in args:
        read_claim = args.get("read_claim")
        if read_claim is not None and not isinstance(read_claim, str):
            return _reject_payload(action=action, active_buddy=active_buddy, message="read_claim must be a string")
        try:
            refs, scope_error = context.rules.source_refs.normalize_source_refs(
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
                field_errors=[_source_refs_field_error()],
            )
        if isinstance(scope_error, dict):
            return _reject_scope(
                action=action,
                active_buddy=active_buddy,
                boundary=str(scope_error.get("permission_boundary", "source_refs.read_scope")),
                message=str(scope_error.get("why_blocked", "source_refs read scope denied")),
                code="E_SOURCE_REFS_READ_SCOPE",
                field_errors=[_source_refs_field_error()],
            )
        patch["source_refs"] = refs

    if not patch:
        return _reject_payload(action=action, active_buddy=active_buddy, message="at least one metadata field is required")

    try:
        updated = context.repos.artifact.update_artifact(artifact_id, patch)
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    row = _artifact_response_row(updated, active_buddy, context)
    return tool_results.success(
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


_ACTION_HANDLERS = {
    'create_revision': create_artifact_revision,
    'get': get_artifact_for_active_buddy,
    'list': list_artifacts_for_active_buddy,
    'update_metadata': update_artifact_metadata,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    return handler(args=args, context=context)
