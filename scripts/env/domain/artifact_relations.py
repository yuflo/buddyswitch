#!/usr/bin/env python3
"""Derived artifact relation/backlink helpers built from existing runtime objects."""

from __future__ import annotations

from typing import Any

from env.domain import artifact_visibility as artifact_visibility_domain
from env.domain import requests as request_domain
from env.repos import artifacts as artifact_repo
from env.repos import comments as comment_repo
from env.repos import requests as request_repo
from env.repos import tracks as track_repo


def _relation_and_currentness(*, artifact: dict[str, Any], decision: dict[str, Any]) -> tuple[str, str]:
    relation = str(decision.get("relation") or "none")
    if relation not in {"owner", "track_material", "track_proof", "track_history"}:
        relation = "none"
    status = artifact.get("status")
    if status == "draft":
        currentness = "draft"
    elif relation == "track_material":
        currentness = "current"
    elif relation == "track_proof":
        currentness = "proof"
    else:
        currentness = "superseded"
    return relation, currentness


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


def _request_is_visible(*, request: dict[str, Any], active_role: str, active_actor_address: dict[str, Any]) -> bool:
    try:
        request_domain.ensure_visible(request, active_role, active_actor_address)
    except request_domain.RequestScopeError:
        return False
    track_id = request.get("track_id")
    if not isinstance(track_id, str) or not track_id:
        return False
    track_readable = artifact_visibility_domain.assert_track_readable(
        track_id,
        active_role=active_role,
        action="artifact.get",
    )
    return bool(track_readable.get("ok"))


def _source_ref_backlinks(*, artifact_id: str, active_role: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in artifact_repo.list_artifacts():
        if not isinstance(candidate, dict):
            continue
        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not candidate_id:
            continue
        decision = artifact_visibility_domain.artifact_read_decision(candidate, active_role)
        if not bool(decision.get("allowed")):
            continue
        if not _artifact_ref_matches(candidate.get("source_refs"), artifact_id):
            continue
        rows.append(
            {
                "artifact_id": candidate_id,
                "title": candidate.get("title"),
                "created_by_actor": candidate.get("created_by_actor"),
                "_sort_updated_at": str(candidate.get("updated_at") or ""),
            }
        )
    rows.sort(key=lambda row: (str(row.get("_sort_updated_at") or ""), str(row.get("artifact_id") or "")), reverse=True)
    for row in rows:
        row.pop("_sort_updated_at", None)
    return rows


def _request_backlinks(
    *,
    artifact_id: str,
    active_role: str,
    active_actor_address: dict[str, Any],
    ref_field: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request in request_repo.list_requests():
        if not isinstance(request, dict):
            continue
        if not _request_is_visible(request=request, active_role=active_role, active_actor_address=active_actor_address):
            continue
        if not _artifact_ref_matches(request.get(ref_field), artifact_id):
            continue
        request_id = request.get("id")
        if not isinstance(request_id, str) or not request_id:
            continue
        rows.append(
            {
                "request_id": request_id,
                "track_id": request.get("track_id"),
                "from_actor": request.get("from_actor"),
                "to_role": request.get("to_role"),
                "status": request.get("status"),
                "title": request.get("title"),
                "_sort_updated_at": str(request.get("updated_at") or ""),
            }
        )
    rows.sort(key=lambda row: (str(row.get("_sort_updated_at") or ""), str(row.get("request_id") or "")), reverse=True)
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
                    "by_actor": update.get("by_actor"),
                    "created_at": update.get("created_at"),
                    "_sort_created_at": str(update.get("created_at") or ""),
                }
            )
    rows.sort(key=lambda row: (str(row.get("_sort_created_at") or ""), str(row.get("update_id") or "")), reverse=True)
    for row in rows:
        row.pop("_sort_created_at", None)
    return rows


def _visible_superseded_by_ids(*, artifact_id: str, active_role: str) -> list[str]:
    rows: list[tuple[str, str]] = []
    for candidate in artifact_repo.list_artifacts():
        if not isinstance(candidate, dict):
            continue
        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not candidate_id:
            continue
        if candidate.get("supersedes_artifact_id") != artifact_id:
            continue
        decision = artifact_visibility_domain.artifact_read_decision(candidate, active_role)
        if not bool(decision.get("allowed")):
            continue
        rows.append((str(candidate.get("updated_at") or ""), candidate_id))
    rows.sort(reverse=True)
    return [artifact_id_value for _, artifact_id_value in rows]


def comment_counts_for_artifact(artifact_id: str) -> dict[str, int]:
    open_count = 0
    resolved_count = 0
    for comment in comment_repo.comments_for_target("artifact", artifact_id):
        if comment.get("status") == "resolved":
            resolved_count += 1
        else:
            open_count += 1
    return {
        "open_comment_count": open_count,
        "resolved_comment_count": resolved_count,
    }


def relation_summary_for_artifact(
    *,
    artifact: dict[str, Any],
    active_role: str,
    active_actor_address: dict[str, Any],
) -> dict[str, Any]:
    artifact_id = artifact.get("id")
    if not isinstance(artifact_id, str) or not artifact_id:
        return {
            "publication": {
                "track_id": None,
                "relation": "none",
                "currentness": "superseded",
            },
            "lineage": {
                "supersedes_artifact_id": artifact.get("supersedes_artifact_id"),
                "superseded_by_artifact_ids": [],
            },
            "incoming_refs": {
                "source_ref_by_artifacts": [],
                "target_ref_by_requests": [],
                "result_ref_by_requests": [],
                "track_update_refs": [],
                "comment_ids": [],
            },
        }

    decision = artifact_visibility_domain.artifact_read_decision(artifact, active_role)
    relation, currentness = _relation_and_currentness(artifact=artifact, decision=decision)
    comments = comment_repo.comments_for_target("artifact", artifact_id)
    comment_ids = [row.get("id") for row in comments if isinstance(row.get("id"), str)]

    return {
        "publication": {
            "track_id": decision.get("track_id"),
            "relation": relation,
            "currentness": currentness,
        },
        "lineage": {
            "supersedes_artifact_id": artifact.get("supersedes_artifact_id"),
            "superseded_by_artifact_ids": _visible_superseded_by_ids(artifact_id=artifact_id, active_role=active_role),
        },
        "incoming_refs": {
            "source_ref_by_artifacts": _source_ref_backlinks(artifact_id=artifact_id, active_role=active_role),
            "target_ref_by_requests": _request_backlinks(
                artifact_id=artifact_id,
                active_role=active_role,
                active_actor_address=active_actor_address,
                ref_field="target_refs",
            ),
            "result_ref_by_requests": _request_backlinks(
                artifact_id=artifact_id,
                active_role=active_role,
                active_actor_address=active_actor_address,
                ref_field="result_refs",
            ),
            "track_update_refs": _track_update_backlinks(artifact_id=artifact_id, active_role=active_role),
            "comment_ids": comment_ids,
        },
    }


def relation_counts_for_artifact(*, artifact_id: str, active_role: str, active_actor_address: dict[str, Any]) -> dict[str, int]:
    artifact = artifact_repo.get_artifact(artifact_id)
    if not isinstance(artifact, dict):
        return {
            "incoming_source_ref_count": 0,
            "target_request_count": 0,
            "result_request_count": 0,
            "track_update_ref_count": 0,
            "comment_count": 0,
        }
    decision = artifact_visibility_domain.artifact_read_decision(artifact, active_role)
    if not bool(decision.get("allowed")):
        return {
            "incoming_source_ref_count": 0,
            "target_request_count": 0,
            "result_request_count": 0,
            "track_update_ref_count": 0,
            "comment_count": 0,
        }
    summary = relation_summary_for_artifact(
        artifact=artifact,
        active_role=active_role,
        active_actor_address=active_actor_address,
    )
    incoming = summary.get("incoming_refs", {})
    if not isinstance(incoming, dict):
        incoming = {}
    return {
        "incoming_source_ref_count": len(incoming.get("source_ref_by_artifacts", []))
        if isinstance(incoming.get("source_ref_by_artifacts"), list)
        else 0,
        "target_request_count": len(incoming.get("target_ref_by_requests", []))
        if isinstance(incoming.get("target_ref_by_requests"), list)
        else 0,
        "result_request_count": len(incoming.get("result_ref_by_requests", []))
        if isinstance(incoming.get("result_ref_by_requests"), list)
        else 0,
        "track_update_ref_count": len(incoming.get("track_update_refs", []))
        if isinstance(incoming.get("track_update_refs"), list)
        else 0,
        "comment_count": len(incoming.get("comment_ids", [])) if isinstance(incoming.get("comment_ids"), list) else 0,
    }
