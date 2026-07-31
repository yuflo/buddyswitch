"""Artifact-owned services aligned to the draft-first publication model."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from .tool import DEFINITION
from buddyswitch.env.tool_runtime import results as tool_results
from buddyswitch.modules.artifact.private.domain import (
    artifact_relations as artifact_relations_domain,
)
from buddyswitch.modules.artifact.private.domain import (
    artifact_visibility as artifact_visibility_domain,
)
from buddyswitch.modules.artifact.private.domain import (
    source_refs as source_refs_domain,
)
from buddyswitch.modules.artifact.private.state import artifacts as artifact_repo


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
    active_role: str
    current_identity: dict[str, Any]
    actor_id: str
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
            {"type": "external", "label": "Product page", "url": "https://example.com"},
            {"type": "note", "label": "Source note"},
        ],
        "example": [{"type": "note", "label": "Source note"}],
    }


def _attachment_filename_field_error() -> dict[str, Any]:
    return {
        "path": "filename",
        "message": "filename must be a non-empty display name without path separators or traversal",
        "example": "desktop.png",
    }


def _source_path_field_error() -> dict[str, Any]:
    return {
        "path": "source_path",
        "message": "source_path must reference one non-empty file inside the active actor private directory",
        "example": "/path/to/instance/workspace/private/screenshots/desktop.png",
    }


def _attachment_id_field_error() -> dict[str, Any]:
    return {
        "path": "attachment_id",
        "message": "attachment_id must reference one attachment owned by the selected artifact",
        "example": "att-example",
    }


def _allowed_templates_for_active_role(context: ArtifactServiceContext) -> tuple[str, ...]:
    active_role = context["active_role"]
    roles = context.get("manifest", {}).get("roles", [])
    if not isinstance(roles, list):
        return ()
    for role in roles:
        if not isinstance(role, dict) or role.get("id") != active_role:
            continue
        templates = role.get("artifact_templates")
        if not isinstance(templates, list):
            return ()
        return tuple(row for row in templates if isinstance(row, str) and row.strip())
    return ()


def _active_identity_id(current_identity: dict[str, Any]) -> str | None:
    identity_id = current_identity.get("id") if isinstance(current_identity, dict) else None
    return identity_id if isinstance(identity_id, str) and identity_id else None


def _reject_template_permission(
    *,
    action: str,
    current_identity: dict[str, Any],
    active_role: str,
    template: str,
    allowed_templates: tuple[str, ...],
) -> dict[str, Any]:
    allowed = ", ".join(allowed_templates) if allowed_templates else "none"
    return tool_results.rejection(
        tool="artifact",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        code="E_ARTIFACT_TEMPLATE_PERMISSION",
        message=f"template '{template}' is not declared for active role '{active_role}'",
        permission_boundary="artifact.template_permission",
        human_summary="Artifact template is not allowed for the active role.",
        why_blocked=f"Active role '{active_role}' may create or update only these artifact templates: {allowed}.",
        impact="No artifact state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Use one template declared for the active role in manifest artifact_templates.",
        allowed_next_actions=[
            "Use context.get to inspect active role capabilities.",
            "Retry artifact.create_revision or artifact.update_metadata with an allowed template.",
        ],
        correctable_fields=["template"],
        field_errors=[
            {
                "path": "template",
                "message": "template must be declared for the active role",
                "allowed_values": list(allowed_templates),
                "example": allowed_templates[0] if allowed_templates else "brief",
            }
        ],
    )


def _reject_payload(
    *,
    action: str,
    current_identity: dict[str, Any],
    active_role: str,
    message: str,
    correctable_fields: list[str] | None = None,
    field_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if correctable_fields is None:
        if "unsupported payload fields:" in message:
            suffix = message.split("unsupported payload fields:", 1)[1].strip()
            if suffix:
                correctable_fields = [row.strip() for row in suffix.split(",") if row.strip()]
        else:
            for field in (
                "artifact_id",
                "title",
                "summary",
                "template",
                "body",
                "supersedes_artifact_id",
                "source_refs",
                "filename",
                "source_path",
                "attachment_id",
            ):
                if field in message:
                    correctable_fields = [field]
                    break
    return tool_results.rejection(
        tool="artifact",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
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
    current_identity: dict[str, Any],
    active_role: str,
    field: str,
    why_blocked: str,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="artifact",
        action="artifact.create_revision",
        current_identity=current_identity,
        active_role=active_role,
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
    current_identity: dict[str, Any],
    active_role: str,
    boundary: str,
    message: str,
    code: str = "E_ARTIFACT_SCOPE",
    correctable_fields: list[str] | None = None,
    field_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="artifact",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        code=code,
        message=message,
        permission_boundary=boundary,
        human_summary="Artifact scope check failed.",
        why_blocked=message,
        impact="No artifact or track state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Use readable or active-actor-owned artifact ids.",
        allowed_next_actions=[
            "Use track.open for shared artifact refs.",
            "Use artifact.create_revision for a private draft owned by the active actor.",
        ],
        correctable_fields=correctable_fields or ["artifact_id"],
        field_errors=field_errors,
    )


def _reject_revision_scope(*, action: str, current_identity: dict[str, Any], active_role: str, message: str) -> dict[str, Any]:
    return tool_results.rejection(
        tool="artifact",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
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


def _require_allowed_fields(action: str, args: dict[str, Any], current_identity: dict[str, Any], active_role: str) -> dict[str, Any] | None:
    _, action_name = action.split(".", 1)
    allowed = set()
    for row in _ACTION_DEFINITION_MAP.get("actions", []):
        if isinstance(row, dict) and row.get("name") == action_name:
            allowed = {field for field in row.get("payload_fields", []) if isinstance(field, str)}
            break
    unknown = sorted(key for key in args if key not in allowed)
    if unknown:
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message=f"unsupported payload fields: {', '.join(unknown)}",
        )
    if _LEGACY_SOURCE_RUN in args:
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="legacy artifact run lineage field is retired; use source_refs",
        )
    return None


def _artifact_response_row(artifact: dict[str, Any], active_role: str, context: ArtifactServiceContext) -> dict[str, Any]:
    del active_role
    return artifact_visibility_domain.artifact_summary_row(artifact, context["current_identity"])


def _normalize_list_filters(
    args: dict[str, Any],
    active_role: str,
    context: ArtifactServiceContext,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    action = "artifact.list"
    track_id: str | None = None
    if "track_id" in args:
        raw_track_id = args.get("track_id")
        if not isinstance(raw_track_id, str) or not raw_track_id.strip():
            return None, _reject_payload(
                action=action,
                current_identity=context["current_identity"],
                active_role=active_role,
                message="track_id must be a non-empty string",
            )
        normalized_track_id = raw_track_id.strip()
        readable = artifact_visibility_domain.assert_track_readable(
            normalized_track_id,
            active_role=active_role,
            action=action,
        )
        if not bool(readable.get("ok")):
            boundary = str(readable.get("permission_boundary", "artifact.read_scope"))
            message = str(readable.get("message", f"track not found: {normalized_track_id}"))
            if boundary == "request-payload":
                return None, _reject_payload(
                    action=action,
                    current_identity=context["current_identity"],
                    active_role=active_role,
                    message=message,
                )
            return None, _reject_scope(
                action=action,
                current_identity=context["current_identity"],
                active_role=active_role,
                boundary=boundary,
                message=message,
                code=str(readable.get("code", "E_ARTIFACT_SCOPE")),
                correctable_fields=["track_id"],
            )
        track_id = normalized_track_id

    created_by_identity_id: str | None = None
    if "created_by_identity_id" in args:
        raw_created_by = args.get("created_by_identity_id")
        if not isinstance(raw_created_by, str) or not raw_created_by.strip():
            return None, _reject_payload(
                action=action,
                current_identity=context["current_identity"],
                active_role=active_role,
                message="created_by_identity_id must be a non-empty string",
            )
        created_by_identity_id = raw_created_by.strip()

    template: str | None = None
    if "template" in args:
        raw_template = args.get("template")
        if not isinstance(raw_template, str) or raw_template not in artifact_repo.VALID_ARTIFACT_TEMPLATES:
            return None, _reject_payload(
                action=action,
                current_identity=context["current_identity"],
                active_role=active_role,
                message=f"template must be one of {', '.join(artifact_repo.VALID_ARTIFACT_TEMPLATES)}",
                field_errors=[_template_field_error(artifact_repo.VALID_ARTIFACT_TEMPLATES)],
            )
        template = raw_template

    q: str | None = None
    if "q" in args:
        raw_q = args.get("q")
        if not isinstance(raw_q, str):
            return None, _reject_payload(
                action=action,
                current_identity=context["current_identity"],
                active_role=active_role,
                message="q must be a string",
            )
        q = raw_q.strip().lower() or None

    limit = args.get("limit", 20)
    if not isinstance(limit, int) or limit <= 0:
        return None, _reject_payload(
            action=action,
            current_identity=context["current_identity"],
            active_role=active_role,
            message="limit must be a positive integer",
        )

    return (
        {
            "track_id": track_id,
            "created_by_identity_id": created_by_identity_id,
            "template": template,
            "q": q,
            "limit": limit,
        },
        None,
    )


def list_artifacts_for_current_identity(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.list"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_allowed_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    filters, filter_error = _normalize_list_filters(args, active_role, context)
    if filter_error is not None:
        return filter_error
    assert isinstance(filters, dict)

    rows: list[dict[str, Any]] = []
    for artifact in artifact_repo.list_artifacts():
        if isinstance(filters.get("track_id"), str):
            decision = artifact_visibility_domain.artifact_read_decision_for_track(
                artifact,
                current_identity,
                track_id=str(filters["track_id"]),
            )
        else:
            decision = artifact_visibility_domain.artifact_read_decision(artifact, current_identity)
        if not bool(decision.get("allowed")):
            continue
        if isinstance(filters.get("created_by_identity_id"), str) and artifact.get("created_by_identity_id") != filters.get("created_by_identity_id"):
            continue
        if isinstance(filters.get("template"), str) and artifact.get("template") != filters.get("template"):
            continue
        query = filters.get("q")
        if isinstance(query, str) and query:
            title = str(artifact.get("title") or "").lower()
            summary = str(artifact.get("summary") or "").lower()
            if query not in title and query not in summary:
                continue

        artifact_id = str(artifact.get("id") or "")
        comment_counts = artifact_relations_domain.comment_counts_for_artifact(artifact_id) if artifact_id else {}
        relation_counts = (
            artifact_relations_domain.relation_counts_for_artifact(
                artifact_id=artifact_id,
                active_role=active_role,
                current_identity_address=context["current_identity"],
            )
            if artifact_id
            else {}
        )
        row = artifact_visibility_domain.artifact_list_row(
            artifact,
            current_identity,
            comment_counts=comment_counts,
            relation_counts=relation_counts,
        )
        if isinstance(filters.get("track_id"), str):
            relation = str(decision.get("relation") or "none")
            row["relation"] = relation
            row["track_id"] = decision.get("track_id")
            row["track_ids"] = decision.get("track_ids", [])
            if relation == "track_material":
                row["currentness"] = "current"
            elif relation == "track_proof":
                row["currentness"] = "proof"
            elif relation == "track_history":
                row["currentness"] = "superseded"
        rows.append(row)

    rows.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("artifact_id") or "")), reverse=True)
    limited_rows = rows[: int(filters.get("limit", 20))]
    return tool_results.success(
        tool="artifact",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
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


def get_artifact_for_current_identity(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.get"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_allowed_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    artifact_id = args.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="artifact_id is required")
    artifact_id = artifact_id.strip()

    artifact = artifact_repo.get_artifact(artifact_id)
    if artifact is None:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=f"artifact not found: {artifact_id}")

    decision = artifact_visibility_domain.artifact_read_decision(artifact, current_identity)
    if not bool(decision.get("allowed")):
        return _reject_scope(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            boundary=str(decision.get("permission_boundary", "artifact.read_scope")),
            message=str(decision.get("why", "artifact read denied")),
            code="E_ARTIFACT_READ_SCOPE",
        )

    row = _artifact_response_row(artifact, active_role, context)
    row["relation_summary"] = artifact_relations_domain.relation_summary_for_artifact(
        artifact=artifact,
        active_role=active_role,
        current_identity_address=context["current_identity"],
    )
    return tool_results.success(
        tool="artifact",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
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
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    if "published_to_track" in args:
        return _reject_publication_path(
            current_identity=current_identity,
            active_role=active_role,
            field="published_to_track",
            why_blocked=(
                "artifact.create_revision creates private drafts; "
                "track.add_material or track.add_proof publishes existing artifacts"
            ),
        )
    if "status" in args:
        return _reject_publication_path(
            current_identity=current_identity,
            active_role=active_role,
            field="status",
            why_blocked="artifact.create_revision always creates status=draft artifacts",
        )
    payload_error = _require_allowed_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    title = args.get("title")
    summary = args.get("summary", "")
    body = args.get("body")
    template = args.get("template")
    supersedes_artifact_id = args.get("supersedes_artifact_id")
    if not isinstance(title, str) or not title.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="title is required")
    if not isinstance(summary, str):
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="summary must be a string")
    if not isinstance(body, str) or not body.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="body is required")
    if not isinstance(template, str) or template not in artifact_repo.VALID_ARTIFACT_TEMPLATES:
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message=f"template must be one of {', '.join(artifact_repo.VALID_ARTIFACT_TEMPLATES)}",
            field_errors=[_template_field_error(artifact_repo.VALID_ARTIFACT_TEMPLATES)],
        )
    allowed_templates = _allowed_templates_for_active_role(context)
    if template not in allowed_templates:
        return _reject_template_permission(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            template=template,
            allowed_templates=allowed_templates,
        )
    if supersedes_artifact_id is not None and (not isinstance(supersedes_artifact_id, str) or not supersedes_artifact_id.strip()):
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="supersedes_artifact_id must be a non-empty string",
        )
    normalized_supersedes_artifact_id = (
        supersedes_artifact_id.strip() if isinstance(supersedes_artifact_id, str) and supersedes_artifact_id.strip() else None
    )

    read_claim = args.get("read_claim")
    if read_claim is not None and not isinstance(read_claim, str):
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="read_claim must be a string")

    try:
        normalized_refs, scope_error = source_refs_domain.normalize_source_refs(
            args.get("source_refs"),
            active_role=active_role,
            current_identity=current_identity,
            read_claim=read_claim if isinstance(read_claim, str) else None,
        )
    except ValueError as exc:
        return _reject_scope(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            boundary="source_refs.required_fields",
            message=str(exc),
            code="E_SOURCE_REFS",
            field_errors=[_source_refs_field_error()],
        )
    if isinstance(scope_error, dict):
        return _reject_scope(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            boundary=str(scope_error.get("permission_boundary", "source_refs.read_scope")),
            message=str(scope_error.get("why_blocked", "source_refs read scope denied")),
            code="E_SOURCE_REFS_READ_SCOPE",
            field_errors=[_source_refs_field_error()],
        )

    artifact_id = args.get("artifact_id")
    if artifact_id is not None and (not isinstance(artifact_id, str) or not artifact_id.strip()):
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="artifact_id must be a non-empty string")

    if normalized_supersedes_artifact_id is not None:
        try:
            artifact_visibility_domain.assert_supersedes_target_for_revision(
                supersedes_artifact_id=normalized_supersedes_artifact_id,
                current_identity=current_identity,
            )
        except ValueError as exc:
            return _reject_revision_scope(
                action=action,
                current_identity=current_identity,
                active_role=active_role,
                message=str(exc),
            )

    try:
        artifact = artifact_repo.create_artifact_revision(
            artifact_id=artifact_id.strip() if isinstance(artifact_id, str) and artifact_id.strip() else None,
            title=title.strip(),
            created_by_identity=context["current_identity"],
            summary=summary,
            body=body,
            template=template,
            source_refs=normalized_refs,
            supersedes_artifact_id=normalized_supersedes_artifact_id,
            author_identities=[context["current_identity"]],
        )
    except ValueError as exc:
        message = str(exc)
        if "supersedes_artifact_id" in message or "superseded" in message:
            return _reject_revision_scope(
                action=action,
                current_identity=current_identity,
                active_role=active_role,
                message=message,
            )
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=message)

    row = _artifact_response_row(artifact, active_role, context)
    return tool_results.success(
        tool="artifact",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
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
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_allowed_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    artifact_id = args.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="artifact_id is required")
    artifact_id = artifact_id.strip()

    artifact = artifact_repo.get_artifact(artifact_id)
    if artifact is None:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=f"artifact not found: {artifact_id}")
    if artifact.get("created_by_identity_id") != _active_identity_id(current_identity):
        return _reject_scope(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            boundary="artifact.creator_identity_id",
            message=f"artifact '{artifact_id}' is owned by another actor",
            code="E_ARTIFACT_SCOPE",
        )

    patch: dict[str, Any] = {}
    for field in ("title", "summary", "template", "body"):
        if field in args:
            patch[field] = args[field]
    if "title" in patch and (not isinstance(patch["title"], str) or not patch["title"].strip()):
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="title must be a non-empty string")
    if "summary" in patch and not isinstance(patch["summary"], str):
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="summary must be a string")
    if "template" in patch and (not isinstance(patch["template"], str) or patch["template"] not in artifact_repo.VALID_ARTIFACT_TEMPLATES):
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message=f"template must be one of {', '.join(artifact_repo.VALID_ARTIFACT_TEMPLATES)}",
            field_errors=[_template_field_error(artifact_repo.VALID_ARTIFACT_TEMPLATES)],
        )
    if isinstance(patch.get("template"), str):
        allowed_templates = _allowed_templates_for_active_role(context)
        if patch["template"] not in allowed_templates:
            return _reject_template_permission(
                action=action,
                current_identity=current_identity,
                active_role=active_role,
                template=patch["template"],
                allowed_templates=allowed_templates,
            )
    if "body" in patch and (not isinstance(patch["body"], str) or not patch["body"].strip()):
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="body must be a non-empty string")

    if "source_refs" in args or "read_claim" in args:
        read_claim = args.get("read_claim")
        if read_claim is not None and not isinstance(read_claim, str):
            return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="read_claim must be a string")
        try:
            refs, scope_error = source_refs_domain.normalize_source_refs(
                args.get("source_refs"),
                active_role=active_role,
                current_identity=current_identity,
                read_claim=read_claim if isinstance(read_claim, str) else None,
            )
        except ValueError as exc:
            return _reject_scope(
                action=action,
                current_identity=current_identity,
                active_role=active_role,
                boundary="source_refs.required_fields",
                message=str(exc),
                code="E_SOURCE_REFS",
                field_errors=[_source_refs_field_error()],
            )
        if isinstance(scope_error, dict):
            return _reject_scope(
                action=action,
                current_identity=current_identity,
                active_role=active_role,
                boundary=str(scope_error.get("permission_boundary", "source_refs.read_scope")),
                message=str(scope_error.get("why_blocked", "source_refs read scope denied")),
                code="E_SOURCE_REFS_READ_SCOPE",
                field_errors=[_source_refs_field_error()],
            )
        patch["source_refs"] = refs

    if not patch:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="at least one metadata field is required")

    try:
        updated = artifact_repo.update_artifact(artifact_id, patch)
    except ValueError as exc:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=str(exc))

    row = _artifact_response_row(updated, active_role, context)
    return tool_results.success(
        tool="artifact",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        effect_summary=f"Updated metadata for artifact '{artifact_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[artifact_id],
        state_changes=[{"object_type": "artifact", "change": "metadata_updated", "artifact_id": artifact_id}],
        allowed_next_actions=["Use artifact.get to verify updated metadata."],
        extra={"artifact_id": artifact_id, "artifact": row},
    )


def attach_file_to_artifact(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.attach_file"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_allowed_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    artifact_id = args.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="artifact_id is required")
    artifact_id = artifact_id.strip()

    filename = args.get("filename")
    if not isinstance(filename, str) or not filename.strip():
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="filename is required",
            field_errors=[_attachment_filename_field_error()],
        )

    source_path = args.get("source_path")
    if not isinstance(source_path, str) or not source_path.strip():
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="source_path is required",
            field_errors=[_source_path_field_error()],
        )

    artifact = artifact_repo.get_artifact(artifact_id)
    if artifact is None:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=f"artifact not found: {artifact_id}")
    if artifact.get("created_by_identity_id") != _active_identity_id(current_identity):
        return _reject_scope(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            boundary="artifact.creator_identity_id",
            message=f"artifact '{artifact_id}' is owned by another actor",
            code="E_ARTIFACT_SCOPE",
        )
    try:
        updated_artifact, attachment = artifact_repo.adopt_local_attachment(
            artifact_id=artifact_id,
            filename=filename,
            created_by_identity=current_identity,
            source_path=Path(source_path.strip()),
            content_type=args.get("content_type") if isinstance(args.get("content_type"), str) else None,
            context=context,
        )
    except (FileNotFoundError, IsADirectoryError, ValueError) as exc:
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message=str(exc),
            correctable_fields=["source_path"],
            field_errors=[_source_path_field_error()],
        )

    row = _artifact_response_row(updated_artifact, active_role, context)
    return tool_results.success(
        tool="artifact",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        effect_summary=f"Attached one private file to artifact '{artifact_id}' as attachment '{attachment['attachment_id']}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[artifact_id],
        state_changes=[{"object_type": "artifact", "change": "attachment_added", "artifact_id": artifact_id}],
        allowed_next_actions=[
            "Use artifact.list_attachments with this artifact_id to inspect attachment summaries.",
            "Use artifact.get_attachment with artifact_id and attachment_id to fetch exact file content.",
            "Use artifact.get with this artifact_id to inspect the full artifact plus attachment summaries.",
        ],
        extra={"artifact_id": artifact_id, "artifact": row, "attachment": attachment},
    )


def list_artifact_attachments(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.list_attachments"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_allowed_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    artifact_id = args.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="artifact_id is required")
    artifact_id = artifact_id.strip()

    artifact = artifact_repo.get_artifact(artifact_id)
    if artifact is None:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=f"artifact not found: {artifact_id}")

    decision = artifact_visibility_domain.artifact_read_decision(artifact, current_identity)
    if not bool(decision.get("allowed")):
        return _reject_scope(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            boundary=str(decision.get("permission_boundary", "artifact.read_scope")),
            message=str(decision.get("why", "artifact read denied")),
            code="E_ARTIFACT_READ_SCOPE",
        )

    attachments = artifact_repo.attachment_summaries(artifact_id)
    return tool_results.success(
        tool="artifact",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        effect_summary=f"Listed {len(attachments)} attachment summary row(s) for artifact '{artifact_id}'.",
        state_changed=False,
        durability="none",
        read_scope="attachment summaries for one readable artifact",
        allowed_next_actions=[
            "Use artifact.get_attachment with artifact_id and attachment_id to fetch exact content.",
            "Use artifact.get with this artifact_id to inspect the full artifact body.",
        ],
        extra={"artifact_id": artifact_id, "attachments": attachments},
    )


def get_artifact_attachment(*, args: dict[str, Any], context: ArtifactServiceContext) -> dict[str, Any]:
    action = "artifact.get_attachment"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_allowed_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    artifact_id = args.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="artifact_id is required")
    artifact_id = artifact_id.strip()
    attachment_id = args.get("attachment_id")
    if not isinstance(attachment_id, str) or not attachment_id.strip():
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="attachment_id is required",
            field_errors=[_attachment_id_field_error()],
        )
    attachment_id = attachment_id.strip()

    artifact = artifact_repo.get_artifact(artifact_id)
    if artifact is None:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=f"artifact not found: {artifact_id}")

    decision = artifact_visibility_domain.artifact_read_decision(artifact, current_identity)
    if not bool(decision.get("allowed")):
        return _reject_scope(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            boundary=str(decision.get("permission_boundary", "artifact.read_scope")),
            message=str(decision.get("why", "artifact read denied")),
            code="E_ARTIFACT_READ_SCOPE",
        )

    try:
        attachment, raw = artifact_repo.get_attachment_content(artifact_id, attachment_id)
    except FileNotFoundError:
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message=f"attachment not found: {attachment_id}",
            field_errors=[_attachment_id_field_error()],
        )
    except ValueError as exc:
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message=str(exc),
            field_errors=[_attachment_id_field_error()],
        )

    import base64

    return tool_results.success(
        tool="artifact",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        effect_summary=f"Read attachment '{attachment_id}' from artifact '{artifact_id}'.",
        state_changed=False,
        durability="none",
        read_scope="one attachment body for one readable artifact",
        allowed_next_actions=[
            "Use artifact.list_attachments to inspect other attachment summaries on this artifact.",
            "Use artifact.get with this artifact_id to inspect the full artifact body.",
        ],
        extra={
            "artifact_id": artifact_id,
            "attachment": attachment,
            "content_base64": base64.b64encode(raw).decode("ascii"),
        },
    )


_ACTION_HANDLERS = {
    'attach_file': attach_file_to_artifact,
    'create_revision': create_artifact_revision,
    'get': get_artifact_for_current_identity,
    'get_attachment': get_artifact_attachment,
    'list': list_artifacts_for_current_identity,
    'list_attachments': list_artifact_attachments,
    'update_metadata': update_artifact_metadata,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    return handler(args=args, context=context)
