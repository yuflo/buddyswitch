"""Artifact-owned read policy and projections."""

from __future__ import annotations

from typing import Any

from buddyswitch.modules.artifact.private.state import artifacts as artifact_repo
from buddyswitch.modules.track import public as track_public


def _current_identity_id(current_identity: dict[str, Any]) -> str | None:
    if not isinstance(current_identity, dict):
        return None
    identity_id = current_identity.get("id")
    return identity_id if isinstance(identity_id, str) and identity_id else None


def _actor_payload_identity_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    actor_id = value.get("actor_id")
    return actor_id if isinstance(actor_id, str) and actor_id else None


def _artifact_creator_identity_id(artifact: dict[str, Any]) -> str | None:
    identity_id = artifact.get("created_by_identity_id")
    if isinstance(identity_id, str) and identity_id:
        return identity_id
    return _actor_payload_identity_id(artifact.get("created_by_identity"))


def _artifact_author_identity_ids(artifact: dict[str, Any]) -> list[str]:
    raw = artifact.get("author_identity_ids")
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, str) and row]
    legacy = artifact.get("author_identities")
    if not isinstance(legacy, list):
        return []
    rows: list[str] = []
    for actor in legacy:
        identity_id = _actor_payload_identity_id(actor)
        if identity_id and identity_id not in rows:
            rows.append(identity_id)
    return rows


def _track_relation_ref(
    artifact_id: str,
    track_id: str,
):
    history_ref = None
    for row in track_public.read_artifact_usage(artifact_id).relations:
        if row.track_id != track_id:
            continue
        if history_ref is None:
            history_ref = row
        if row.current:
            return row
    return history_ref


def assert_supersedes_target_for_revision(
    *,
    supersedes_artifact_id: str,
    current_identity: dict[str, Any],
) -> dict[str, Any]:
    artifact = artifact_repo.get_artifact(supersedes_artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {supersedes_artifact_id}")
    if not bool(artifact.get("is_current")):
        raise ValueError(f"artifact '{supersedes_artifact_id}' is not current and cannot be superseded")
    decision = artifact_read_decision(artifact, current_identity)
    if not bool(decision.get("allowed")):
        raise ValueError("supersedes_artifact_id must reference a current readable artifact")
    return artifact


def artifact_read_decision(artifact: dict[str, Any], current_identity: dict[str, Any]) -> dict[str, Any]:
    artifact_id = artifact.get("id") if isinstance(artifact.get("id"), str) else None
    owner_identity_id = _artifact_creator_identity_id(artifact)
    current_identity_id = _current_identity_id(current_identity)

    if isinstance(owner_identity_id, str) and owner_identity_id == current_identity_id:
        return {
            "allowed": True,
            "artifact_id": artifact_id,
            "track_id": None,
            "track_ids": [],
            "relation": "owner",
            "permission_boundary": "none",
            "why": "active actor owns artifact content",
        }

    relation_track_ids: list[str] = []
    archived_relation_track_id: str | None = None
    history_decision: dict[str, Any] | None = None
    usage = track_public.read_artifact_usage(str(artifact_id or ""))
    for ref in usage.relations:
        track_id = ref.track_id
        if ref.track_archived_at is not None:
            if archived_relation_track_id is None:
                archived_relation_track_id = track_id
            continue
        relation_track_ids.append(track_id)
        role = ref.role
        relation = "track_proof" if role == "proof" else "track_material" if role == "material" else "track_history"
        decision = {
            "allowed": True,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "track_ids": relation_track_ids,
            "relation": relation if ref.current else "track_history",
            "permission_boundary": "none",
            "why": "artifact is referenced by a readable track relation",
        }
        if ref.current:
            return decision
        if history_decision is None:
            history_decision = decision

    if history_decision is not None:
        history_decision["track_ids"] = relation_track_ids
        return history_decision

    if archived_relation_track_id is not None:
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": archived_relation_track_id,
            "track_ids": [],
            "relation": "none",
            "permission_boundary": "track.lifecycle_status",
            "why": "artifact is related only through archived tracks",
        }

    return {
        "allowed": False,
        "artifact_id": artifact_id,
        "track_id": None,
        "track_ids": [],
        "relation": "none",
        "permission_boundary": "artifact.relation_scope",
        "why": "artifact is readable only by owner or through a non-archived track relation",
    }


def artifact_read_decision_for_track(
    artifact: dict[str, Any],
    current_identity: dict[str, Any],
    *,
    track_id: str,
) -> dict[str, Any]:
    del current_identity
    artifact_id = artifact.get("id") if isinstance(artifact.get("id"), str) else None
    track = track_public.read_track_scope(track_id)
    if track is None:
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "track_ids": [],
            "relation": "none",
            "permission_boundary": "request-payload",
            "why": f"track not found: {track_id}",
        }
    if track.archived_at is not None:
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "track_ids": [],
            "relation": "none",
            "permission_boundary": "track.lifecycle_status",
            "why": "archived tracks are hard read boundaries",
        }
    ref = _track_relation_ref(str(artifact_id or ""), track_id)
    if ref is None:
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": track_id,
            "track_ids": [],
            "relation": "none",
            "permission_boundary": "artifact.relation_scope",
            "why": "artifact is not related to the requested track",
        }
    role = ref.role
    relation = "track_proof" if role == "proof" else "track_material" if role == "material" else "track_history"
    return {
        "allowed": True,
        "artifact_id": artifact_id,
        "track_id": track_id,
        "track_ids": [track_id],
        "relation": relation if ref.current else "track_history",
        "permission_boundary": "none",
        "why": "artifact is referenced by the requested track relation",
    }


def artifact_summary_row(
    artifact: dict[str, Any],
    current_identity: dict[str, Any],
) -> dict[str, Any]:
    decision = artifact_read_decision(artifact, current_identity)
    relation, currentness = _relation_and_currentness_for_decision(artifact=artifact, decision=decision)
    return {
        "id": artifact.get("id"),
        "artifact_id": artifact.get("id"),
        "track_id": decision.get("track_id"),
        "track_ids": decision.get("track_ids", []),
        "relation": relation,
        "title": artifact.get("title"),
        "summary": artifact.get("summary", ""),
        "body": artifact.get("body"),
        "template": artifact.get("template"),
        "created_by_identity_id": _artifact_creator_identity_id(artifact),
        "author_identity_ids": _artifact_author_identity_ids(artifact),
        "source_refs": artifact.get("source_refs"),
        "attachments": attachment_summary_rows(artifact),
        "revision": artifact.get("revision"),
        "currentness": currentness,
        "readable_by_current_identity": bool(decision.get("allowed")),
        "supersedes_artifact_id": artifact.get("supersedes_artifact_id"),
        "updated_at": artifact.get("updated_at"),
        "created_at": artifact.get("created_at"),
    }


def _relation_and_currentness_for_decision(
    *,
    artifact: dict[str, Any],
    decision: dict[str, Any],
) -> tuple[str, str]:
    del artifact
    relation = decision.get("relation")
    if relation not in {"owner", "track_material", "track_proof", "track_history"}:
        relation = "none"
    if relation == "owner":
        currentness = "draft"
    elif relation == "track_material":
        currentness = "current"
    elif relation == "track_proof":
        currentness = "proof"
    else:
        currentness = "superseded"
    return str(relation), currentness


def attachment_summary_rows(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in artifact.get("attachments", []):
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "attachment_id": row.get("attachment_id"),
                "filename": row.get("filename"),
                "content_type": row.get("content_type"),
                "size_bytes": row.get("size_bytes"),
                "sha256": row.get("sha256"),
                "created_by_identity_id": row.get("created_by_identity_id") or _actor_payload_identity_id(row.get("created_by_identity")),
                "created_at": row.get("created_at"),
            }
        )
    return rows


def artifact_list_row(
    artifact: dict[str, Any],
    current_identity: dict[str, Any],
    *,
    comment_counts: dict[str, int] | None = None,
    relation_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    from buddyswitch.modules.artifact.private.domain import (
        source_refs as source_refs_domain,
    )

    decision = artifact_read_decision(artifact, current_identity)
    relation, currentness = _relation_and_currentness_for_decision(artifact=artifact, decision=decision)
    counts = comment_counts or {}
    backlinks = relation_counts or {}
    return {
        "artifact_id": artifact.get("id"),
        "title": artifact.get("title"),
        "summary": artifact.get("summary", ""),
        "template": artifact.get("template"),
        "currentness": currentness,
        "relation": relation,
        "track_id": decision.get("track_id"),
        "track_ids": decision.get("track_ids", []),
        "created_by_identity_id": _artifact_creator_identity_id(artifact),
        "author_identity_ids": _artifact_author_identity_ids(artifact),
        "revision": artifact.get("revision"),
        "supersedes_artifact_id": artifact.get("supersedes_artifact_id"),
        "source_refs_summary": source_refs_domain.source_ref_summary(artifact.get("source_refs")),
        "open_comment_count": int(counts.get("open_comment_count", 0)),
        "resolved_comment_count": int(counts.get("resolved_comment_count", 0)),
        "incoming_source_ref_count": int(backlinks.get("incoming_source_ref_count", 0)),
        "track_update_ref_count": int(backlinks.get("track_update_ref_count", 0)),
        "comment_count": int(backlinks.get("comment_count", 0)),
        "updated_at": artifact.get("updated_at"),
    }


def current_material_rows_for_track(track_id: str, current_identity: dict[str, Any]) -> list[dict[str, Any]]:
    track = track_public.read_track_scope(track_id)
    if track is None or track.archived_at is not None:
        return []

    rows: list[dict[str, Any]] = []
    for artifact in artifact_repo.list_artifacts():
        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, str) or not artifact_id:
            continue
        relation = _track_relation_ref(artifact_id, track_id)
        if relation is None or relation.role != "material" or not relation.current:
            continue
        decision = artifact_read_decision(artifact, current_identity)
        rows.append(
            {
                "artifact_id": artifact_id,
                "template": relation.template,
                "label": relation.label,
                "from_identity_id": relation.from_identity_id,
                "summary": relation.summary,
                "currentness": "current",
                "created_at": relation.created_at,
                "readable_by_current_identity": bool(decision.get("allowed")),
                "relation": "track_material" if bool(decision.get("allowed")) else "none",
            }
        )

    rows.sort(key=lambda row: (str(row.get("template") or ""), str(row.get("artifact_id") or "")))
    return rows


def proof_rows_for_track(track_id: str, current_identity: dict[str, Any]) -> list[dict[str, Any]]:
    track = track_public.read_track_scope(track_id)
    if track is None or track.archived_at is not None:
        return []

    rows: list[dict[str, Any]] = []
    for artifact in artifact_repo.list_artifacts():
        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, str) or not artifact_id:
            continue
        relation = _track_relation_ref(artifact_id, track_id)
        if relation is None or relation.role != "proof" or not relation.current:
            continue
        decision = artifact_read_decision(artifact, current_identity)
        rows.append(
            {
                "artifact_id": artifact_id,
                "template": relation.template,
                "label": relation.label,
                "from_identity_id": relation.from_identity_id,
                "summary": relation.summary,
                "currentness": "proof",
                "created_at": relation.created_at,
                "readable_by_current_identity": bool(decision.get("allowed")),
                "relation": "track_proof" if bool(decision.get("allowed")) else "none",
            }
        )

    rows.sort(key=lambda row: (str(row.get("template") or ""), str(row.get("artifact_id") or "")))
    return rows


def artifact_ref_decision_for_track_update(
    *,
    artifact_id: str,
    current_identity: dict[str, Any],
    track_id: str,
) -> dict[str, Any]:
    artifact = artifact_repo.get_artifact(artifact_id)
    if artifact is None:
        return {
            "ok": False,
            "message": f"artifact not found: {artifact_id}",
        }

    decision = artifact_read_decision(artifact, current_identity)
    if not bool(decision.get("allowed")):
        why = str(decision.get("why") or "artifact is not readable for track updates")
        return {
            "ok": False,
            "message": f"artifact '{artifact_id}' cannot be used in refs: {why}",
        }

    track = track_public.read_track_scope(track_id)
    if track is None or track.archived_at is not None:
        return {
            "ok": False,
            "message": f"track not found or archived: {track_id}",
        }

    relation_ref = _track_relation_ref(artifact_id, track_id)

    if (
        relation_ref is None
        or relation_ref.role not in {"material", "proof"}
        or not relation_ref.current
    ):
        return {
            "ok": False,
            "message": f"artifact '{artifact_id}' is not a current material/proof relation on track '{track_id}'",
        }

    return {"ok": True}


def assert_track_readable(track_id: str, *, active_role: str, action: str) -> dict[str, Any]:
    track = track_public.read_track_scope(track_id)
    if track is None:
        return {
            "ok": False,
            "code": "E_TRACK_PAYLOAD",
            "message": f"track not found: {track_id}",
            "permission_boundary": "request-payload",
        }
    if track.archived_at is not None:
        return {
            "ok": False,
            "code": "E_TRACK_ARCHIVED",
            "message": f"track '{track_id}' is archived and cannot be read via {action}",
            "permission_boundary": "track.lifecycle_status",
        }
    return {
        "ok": True,
        "track": {
            "id": track.track_id,
            "owner_identity_id": track.owner_identity_id,
            "archived_at": track.archived_at,
        },
        "active_role": active_role,
    }
