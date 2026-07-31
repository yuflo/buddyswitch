"""Track-owned Artifact relation mutations."""

from __future__ import annotations

import uuid
from typing import Any, TypedDict

from buddyswitch.env.domain.identity import IdentityRef
from buddyswitch.modules.track.private.state import tracks as track_repo
from buddyswitch.modules.track.public.contracts import (
    PublicationCandidatePort,
    ResolvePublicationCandidate,
)


class MaterialRelationResult(TypedDict):
    track: dict[str, Any]
    artifact: PublicationCandidatePort
    superseded_artifact_id: str | None


class ProofRelationResult(TypedDict):
    track: dict[str, Any]
    artifact: PublicationCandidatePort
    superseded_artifact_id: str | None


def _identity_id(value: Any, field: str) -> str:
    if isinstance(value, str) and value.strip():
        return track_repo.runtime_files.require_id(value.strip(), field)
    if isinstance(value, dict):
        if isinstance(value.get("identity"), dict):
            return IdentityRef.from_payload(value["identity"]).id
        if isinstance(value.get("id"), str) and isinstance(value.get("type"), str):
            return IdentityRef.from_payload(value).id
    raise ValueError(f"{field} must be an identity id or identity payload")


def _relation_identity_id(row: dict[str, Any]) -> str | None:
    identity_id = row.get("from_identity_id")
    if isinstance(identity_id, str) and identity_id:
        return identity_id
    return None


def _load_track(track_id: str) -> dict[str, Any]:
    track = track_repo.get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    if track.get("archived_at") is not None:
        raise ValueError(f"track '{track_id}' is archived and cannot accept artifact relations")
    return track


def _same_relation_slot(*, row: dict[str, Any], role: str, label: str, template: str, identity_id: str) -> bool:
    return (
        row.get("role") == role
        and row.get("label") == label
        and row.get("template") == template
        and _relation_identity_id(row) == identity_id
    )


def _relation_row(
    *,
    artifact_id: str,
    role: str,
    label: str,
    template: str,
    from_identity: dict[str, Any] | str,
    summary: str,
) -> dict[str, Any]:
    return {
        "relation_id": f"rel-{uuid.uuid4().hex[:10]}",
        "type": "artifact",
        "artifact_id": artifact_id,
        "role": role,
        "label": label,
        "template": template,
        "from_identity_id": _identity_id(from_identity, "from_identity"),
        "summary": summary,
        "current": True,
        "created_at": track_repo.now_iso(),
    }


def _next_relation_rows(
    *,
    track: dict[str, Any],
    artifact: PublicationCandidatePort,
    role: str,
    label: str,
    identity_id: str,
    summary: str,
) -> tuple[list[dict[str, Any]], str | None]:
    template = artifact.template
    superseded_artifact_id: str | None = None
    rows: list[dict[str, Any]] = []
    for row in track.get("artifact_relations", []):
        if not isinstance(row, dict):
            continue
        next_row = dict(row)
        if _same_relation_slot(row=row, role=role, label=label, template=template, identity_id=identity_id):
            if bool(row.get("current")):
                existing_artifact_id = row.get("artifact_id")
                if existing_artifact_id == artifact.artifact_id:
                    raise ValueError(f"artifact '{artifact.artifact_id}' is already current {role} on track '{track.get('id')}'")
                if isinstance(existing_artifact_id, str) and existing_artifact_id:
                    superseded_artifact_id = existing_artifact_id
            next_row["current"] = False
        rows.append(next_row)

    rows.append(
        _relation_row(
            artifact_id=artifact.artifact_id,
            role=role,
            label=label,
            template=template,
            from_identity=identity_id,
            summary=summary,
        )
    )
    return rows, superseded_artifact_id


def add_material_relation(
    *,
    track_id: str,
    artifact_id: str,
    label: str,
    from_identity: dict[str, Any] | str,
    summary: str,
    resolve_publication_candidate: ResolvePublicationCandidate,
) -> MaterialRelationResult:
    track = _load_track(track_id)
    identity_id = _identity_id(from_identity, "from_identity")
    artifact = resolve_publication_candidate(artifact_id, identity_id)
    rows, superseded_artifact_id = _next_relation_rows(
        track=track,
        artifact=artifact,
        role="material",
        label=label,
        identity_id=identity_id,
        summary=summary,
    )

    track_after = dict(track)
    track_after["artifact_relations"] = rows
    track_after["updated_at"] = track_repo.now_iso()
    saved_track = track_repo.save_track(track_after)
    return {
        "track": saved_track,
        "artifact": artifact,
        "superseded_artifact_id": superseded_artifact_id,
    }


def add_proof_relation(
    *,
    track_id: str,
    artifact_id: str,
    label: str,
    from_identity: dict[str, Any] | str,
    summary: str,
    resolve_publication_candidate: ResolvePublicationCandidate,
) -> ProofRelationResult:
    track = _load_track(track_id)
    identity_id = _identity_id(from_identity, "from_identity")
    artifact = resolve_publication_candidate(artifact_id, identity_id)
    rows, superseded_artifact_id = _next_relation_rows(
        track=track,
        artifact=artifact,
        role="proof",
        label=label,
        identity_id=identity_id,
        summary=summary,
    )

    track_after = dict(track)
    track_after["artifact_relations"] = rows
    track_after["updated_at"] = track_repo.now_iso()
    saved_track = track_repo.save_track(track_after)
    return {
        "track": saved_track,
        "artifact": artifact,
        "superseded_artifact_id": superseded_artifact_id,
    }
