"""Derived artifact relation/backlink helpers built from existing runtime objects."""

from __future__ import annotations

from typing import Any

from env.domain import artifact_visibility as artifact_visibility_domain
from env.repos import artifacts as artifact_repo
from env.repos import tracks as track_repo


def _artifact_ref_matches(refs: Any, artifact_id: str) -> bool:
    if not isinstance(refs, list):
        return False
    for row in refs:
        if not isinstance(row, dict):
            continue
        if row.get("type") != "artifact":
            continue
        if row.get("id") == artifact_id:
            return True
    return False


def _source_ref_backlinks(*, artifact_id: str, active_role: str, current_identity_address: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in artifact_repo.list_artifacts():
        if not isinstance(candidate, dict):
            continue
        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not candidate_id:
            continue
        decision = artifact_visibility_domain.artifact_read_decision(candidate, current_identity_address)
        if not bool(decision.get("allowed")):
            continue
        if not _artifact_ref_matches(candidate.get("source_refs"), artifact_id):
            continue
        rows.append(
            {
                "artifact_id": candidate_id,
                "title": candidate.get("title"),
                "created_by_identity": candidate.get("created_by_identity"),
                "_sort_updated_at": str(candidate.get("updated_at") or ""),
            }
        )
    rows.sort(key=lambda row: (str(row.get("_sort_updated_at") or ""), str(row.get("artifact_id") or "")), reverse=True)
    for row in rows:
        row.pop("_sort_updated_at", None)
    return rows


def _track_update_backlinks(*, artifact_id: str, active_role: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track in track_repo.list_tracks():
        track_id = track.get("id")
        if not isinstance(track_id, str) or not track_id:
            continue
        if track.get("archived_at") is not None:
            continue
        readable = artifact_visibility_domain.assert_track_readable(
            track_id,
            active_role=active_role,
            action="artifact.get",
        )
        if not bool(readable.get("ok")):
            continue
        for update in track.get("updates", []):
            if not isinstance(update, dict):
                continue
            if not _artifact_ref_matches(update.get("refs"), artifact_id):
                continue
            update_id = update.get("id")
            if not isinstance(update_id, str) or not update_id:
                continue
            rows.append(
                {
                    "track_id": track_id,
                    "update_id": update_id,
                    "kind": update.get("kind"),
                    "summary": update.get("summary"),
                    "by_identity": update.get("by_identity"),
                    "created_at": update.get("created_at"),
                    "_sort_created_at": str(update.get("created_at") or ""),
                }
            )
    rows.sort(key=lambda row: (str(row.get("_sort_created_at") or ""), str(row.get("update_id") or "")), reverse=True)
    for row in rows:
        row.pop("_sort_created_at", None)
    return rows


def _visible_superseded_by_ids(*, artifact_id: str, active_role: str, current_identity_address: dict[str, Any]) -> list[str]:
    rows: list[tuple[str, str]] = []
    for candidate in artifact_repo.list_artifacts():
        if not isinstance(candidate, dict):
            continue
        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not candidate_id:
            continue
        if candidate.get("supersedes_artifact_id") != artifact_id:
            continue
        decision = artifact_visibility_domain.artifact_read_decision(candidate, current_identity_address)
        if not bool(decision.get("allowed")):
            continue
        rows.append((str(candidate.get("updated_at") or ""), candidate_id))
    rows.sort(reverse=True)
    return [artifact_id_value for _, artifact_id_value in rows]


def comment_counts_for_artifact(artifact_id: str) -> dict[str, int]:
    del artifact_id
    return {
        "open_comment_count": 0,
        "resolved_comment_count": 0,
    }


def relation_summary_for_artifact(
    *,
    artifact: dict[str, Any],
    active_role: str,
    current_identity_address: dict[str, Any],
) -> dict[str, Any]:
    artifact_id = artifact.get("id")
    if not isinstance(artifact_id, str) or not artifact_id:
        return {
            "track_relations": [],
            "lineage": {
                "supersedes_artifact_id": artifact.get("supersedes_artifact_id"),
                "superseded_by_artifact_ids": [],
            },
            "incoming_refs": {
                "source_ref_by_artifacts": [],
                "track_update_refs": [],
            },
        }

    track_relations: list[dict[str, Any]] = []
    for track in track_repo.list_tracks():
        track_id = track.get("id")
        if not isinstance(track_id, str) or not track_id:
            continue
        if track.get("archived_at") is not None:
            continue
        for row in track.get("artifact_relations", []):
            if not isinstance(row, dict):
                continue
            if row.get("type") != "artifact" or row.get("artifact_id") != artifact_id:
                continue
            role = row.get("role")
            row_relation = "track_proof" if role == "proof" else "track_material" if role == "material" else "track_history"
            if not bool(row.get("current")):
                row_relation = "track_history"
            row_currentness = "proof" if row_relation == "track_proof" else "current" if row_relation == "track_material" else "superseded"
            track_relations.append(
                {
                    "track_id": track_id,
                    "relation_id": row.get("relation_id"),
                    "role": role,
                    "relation": row_relation,
                    "currentness": row_currentness,
                    "label": row.get("label"),
                    "summary": row.get("summary", ""),
                    "current": bool(row.get("current")),
                    "created_at": row.get("created_at"),
                }
            )

    return {
        "track_relations": track_relations,
        "lineage": {
            "supersedes_artifact_id": artifact.get("supersedes_artifact_id"),
            "superseded_by_artifact_ids": _visible_superseded_by_ids(
                artifact_id=artifact_id,
                active_role=active_role,
                current_identity_address=current_identity_address,
            ),
        },
        "incoming_refs": {
            "source_ref_by_artifacts": _source_ref_backlinks(
                artifact_id=artifact_id,
                active_role=active_role,
                current_identity_address=current_identity_address,
            ),
            "track_update_refs": _track_update_backlinks(artifact_id=artifact_id, active_role=active_role),
        },
    }


def relation_counts_for_artifact(*, artifact_id: str, active_role: str, current_identity_address: dict[str, Any]) -> dict[str, int]:
    artifact = artifact_repo.get_artifact(artifact_id)
    if not isinstance(artifact, dict):
        return {
            "incoming_source_ref_count": 0,
            "track_update_ref_count": 0,
        }
    decision = artifact_visibility_domain.artifact_read_decision(artifact, current_identity_address)
    if not bool(decision.get("allowed")):
        return {
            "incoming_source_ref_count": 0,
            "track_update_ref_count": 0,
        }
    summary = relation_summary_for_artifact(
        artifact=artifact,
        active_role=active_role,
        current_identity_address=current_identity_address,
    )
    incoming = summary.get("incoming_refs", {})
    if not isinstance(incoming, dict):
        incoming = {}
    return {
        "incoming_source_ref_count": len(incoming.get("source_ref_by_artifacts", []))
        if isinstance(incoming.get("source_ref_by_artifacts"), list)
        else 0,
        "track_update_ref_count": len(incoming.get("track_update_refs", []))
        if isinstance(incoming.get("track_update_refs"), list)
        else 0,
    }
