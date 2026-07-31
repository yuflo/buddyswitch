"""Artifact Public operations over Artifact-owned state and policy."""

from __future__ import annotations

from typing import Any

from buddyswitch.modules.artifact.private.domain import (
    artifact_relations,
    artifact_visibility,
)
from buddyswitch.modules.artifact.private.state import artifacts
from buddyswitch.modules.artifact.public.contracts import (
    ArtifactNotFound,
    ArtifactNotPublishable,
    ArtifactOwnershipDenied,
    ArtifactReferenceMetadata,
    AttachmentSummary,
    EvidenceTarget,
    PublicationCandidate,
)


def _artifact_or_raise(artifact_id: str) -> dict[str, Any]:
    artifact = artifacts.get_artifact(artifact_id)
    if artifact is None:
        raise ArtifactNotFound(f"artifact not found: {artifact_id}")
    return artifact


def _attachment_summaries(
    artifact: dict[str, Any],
) -> tuple[AttachmentSummary, ...]:
    rows: list[AttachmentSummary] = []
    for row in artifact_visibility.attachment_summary_rows(artifact):
        try:
            rows.append(
                AttachmentSummary(
                    attachment_id=str(row["attachment_id"]),
                    filename=str(row["filename"]),
                    content_type=str(row["content_type"]),
                    size_bytes=int(row["size_bytes"]),
                    sha256=str(row["sha256"]),
                    created_by_identity_id=str(
                        row["created_by_identity_id"]
                    ),
                    created_at=str(row["created_at"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(rows)


def resolve_publication_candidate(
    artifact_id: str,
    owner_identity_id: str,
) -> PublicationCandidate:
    artifact = _artifact_or_raise(artifact_id)
    if artifact.get("created_by_identity_id") != owner_identity_id:
        raise ArtifactOwnershipDenied(
            f"artifact '{artifact_id}' is owned by another identity"
        )
    template = artifact.get("template")
    if not isinstance(template, str) or not template:
        raise ArtifactNotPublishable(
            "artifact.template is required for track artifact relation"
        )
    return PublicationCandidate(
        artifact_id=str(artifact["id"]),
        template=template,
    )


def read_reference_metadata(
    artifact_id: str,
) -> ArtifactReferenceMetadata:
    artifact = _artifact_or_raise(artifact_id)
    template = artifact.get("template")
    if not isinstance(template, str) or not template:
        raise ArtifactNotPublishable(
            "artifact.template is required for track artifact relation"
        )
    return ArtifactReferenceMetadata(
        artifact_id=str(artifact["id"]),
        template=template,
        attachments=_attachment_summaries(artifact),
    )


def list_readable_summaries(
    *,
    current_identity: dict[str, Any],
    track_id: str | None = None,
    limit: int = 20,
    active_role: str = "",
) -> list[dict[str, object]]:
    normalized_track_id = (
        track_id.strip()
        if isinstance(track_id, str) and track_id.strip()
        else None
    )
    rows: list[dict[str, object]] = []
    for artifact in artifacts.list_artifacts():
        decision = artifact_visibility.artifact_read_decision(
            artifact,
            current_identity,
        )
        if not bool(decision.get("allowed")):
            continue
        relation = decision.get("relation")
        if normalized_track_id is not None:
            if (
                decision.get("track_id") != normalized_track_id
                or relation not in {"track_material", "track_proof"}
            ):
                continue
        elif relation not in {"owner", "track_material", "track_proof"}:
            continue
        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, str) or not artifact_id:
            continue
        rows.append(
            artifact_visibility.artifact_list_row(
                artifact,
                current_identity,
                comment_counts=artifact_relations.comment_counts_for_artifact(
                    artifact_id
                ),
                relation_counts=artifact_relations.relation_counts_for_artifact(
                    artifact_id=artifact_id,
                    active_role=active_role,
                    current_identity_address=current_identity,
                ),
            )
        )
    rows.sort(
        key=lambda row: (
            str(row.get("updated_at") or ""),
            str(row.get("artifact_id") or ""),
        ),
        reverse=True,
    )
    return rows[:limit]


def resolve_evidence_target(
    artifact_id: str,
    author_identity_id: str,
) -> EvidenceTarget:
    artifact = _artifact_or_raise(artifact_id)
    raw_authors = artifact.get("author_identity_ids")
    authors = tuple(
        row
        for row in raw_authors
        if isinstance(row, str) and row
    ) if isinstance(raw_authors, list) else ()
    if author_identity_id not in authors:
        raise ArtifactOwnershipDenied(
            f"artifact '{artifact_id}' is not authored by the active actor"
        )
    return EvidenceTarget(
        artifact_id=str(artifact["id"]),
        author_identity_ids=authors,
    )
