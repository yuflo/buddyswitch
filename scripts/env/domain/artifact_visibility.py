#!/usr/bin/env python3
"""Read-only artifact visibility decisions backed by repo reads."""

from __future__ import annotations

from typing import Any

from env.repos import artifacts as artifact_repo
from env.repos import tracks as track_repo


def _track_current_material_ref(track: dict[str, Any], artifact_id: str) -> dict[str, Any] | None:
    for row in track.get("shared_materials", []):
        if not isinstance(row, dict):
            continue
        if row.get("type") != "artifact":
            continue
        if row.get("artifact_id") != artifact_id:
            continue
        if not bool(row.get("current")):
            continue
        return row
    return None


def _track_proof_ref(track: dict[str, Any], artifact_id: str) -> dict[str, Any] | None:
    for row in track.get("close_proof", []):
        if not isinstance(row, dict):
            continue
        if row.get("type") != "artifact":
            continue
        if row.get("artifact_id") == artifact_id and bool(row.get("current", True)):
            return row
    return None


def _track_history_ref(track: dict[str, Any], artifact_id: str) -> dict[str, Any] | None:
    for key in ("shared_materials", "close_proof"):
        for row in track.get(key, []):
            if not isinstance(row, dict):
                continue
            if row.get("type") != "artifact":
                continue
            if row.get("artifact_id") != artifact_id:
                continue
            return row
    return None


def assert_supersedes_target_for_revision(
    *,
    supersedes_artifact_id: str,
    active_buddy: str,
) -> dict[str, Any]:
    artifact = artifact_repo.get_artifact(supersedes_artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {supersedes_artifact_id}")
    if not bool(artifact.get("is_current")):
        raise ValueError(f"artifact '{supersedes_artifact_id}' is not current and cannot be superseded")
    if artifact.get("status") == "draft":
        if artifact.get("created_by") != active_buddy:
            raise ValueError("supersedes_artifact_id must reference an active-buddy-owned current draft")
        return artifact
    if artifact.get("status") != "published":
        raise ValueError("supersedes_artifact_id must reference a current draft or published artifact")
    track_id = artifact.get("published_to_track")
    if not isinstance(track_id, str) or not track_id:
        raise ValueError("supersedes published artifact is missing track publication id")
    track = track_repo.get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    if track.get("archived_at") is not None:
        raise ValueError("supersedes published artifact belongs to an archived track")
    in_shared = any(
        isinstance(row, dict)
        and row.get("type") == "artifact"
        and row.get("artifact_id") == supersedes_artifact_id
        and bool(row.get("current"))
        for row in track.get("shared_materials", [])
    )
    in_proof = any(
        isinstance(row, dict)
        and row.get("type") == "artifact"
        and row.get("artifact_id") == supersedes_artifact_id
        and bool(row.get("current", True))
        for row in track.get("close_proof", [])
    )
    if not (in_shared or in_proof):
        raise ValueError("supersedes_artifact_id must reference current published material/proof on a readable track")
    return artifact


def artifact_read_decision(artifact: dict[str, Any], active_buddy: str) -> dict[str, Any]:
    artifact_id = artifact.get("id") if isinstance(artifact.get("id"), str) else None
    owner = artifact.get("created_by")
    published_track_id = artifact.get("published_to_track")
    status = artifact.get("status")

    if status == "draft":
        if owner == active_buddy:
            return {
                "allowed": True,
                "artifact_id": artifact_id,
                "track_id": None,
                "relation": "owner",
                "permission_boundary": "none",
                "why": "active buddy owns private draft artifact",
            }
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": None,
            "relation": "none",
            "permission_boundary": "artifact.status",
            "why": "artifact is private draft and readable by owner only",
        }

    if published_track_id is None:
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": None,
            "relation": "none",
            "permission_boundary": "artifact.publication",
            "why": "artifact is private draft and not published to a readable track",
        }

    if not isinstance(published_track_id, str) or not published_track_id:
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": None,
            "relation": "none",
            "permission_boundary": "artifact.publication",
            "why": "artifact publication track id is invalid",
        }

    track = track_repo.get_track(published_track_id)
    if not isinstance(track, dict):
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": published_track_id,
            "relation": "none",
            "permission_boundary": "artifact.publication",
            "why": "published track cannot be loaded",
        }

    if track.get("archived_at") is not None:
        return {
            "allowed": False,
            "artifact_id": artifact_id,
            "track_id": published_track_id,
            "relation": "none",
            "permission_boundary": "track.lifecycle_status",
            "why": "archived tracks are hard read boundaries",
        }

    current_ref = _track_current_material_ref(track, str(artifact_id or ""))
    if isinstance(current_ref, dict):
        return {
            "allowed": True,
            "artifact_id": artifact_id,
            "track_id": published_track_id,
            "relation": "track_material",
            "permission_boundary": "none",
            "why": "artifact is a current published track material",
        }

    proof_ref = _track_proof_ref(track, str(artifact_id or ""))
    if isinstance(proof_ref, dict):
        return {
            "allowed": True,
            "artifact_id": artifact_id,
            "track_id": published_track_id,
            "relation": "track_proof",
            "permission_boundary": "none",
            "why": "artifact is published as close proof on readable track",
        }

    history_ref = _track_history_ref(track, str(artifact_id or ""))
    if isinstance(history_ref, dict):
        return {
            "allowed": True,
            "artifact_id": artifact_id,
            "track_id": published_track_id,
            "relation": "track_history",
            "permission_boundary": "none",
            "why": "artifact is readable as historical published material/proof on readable track",
        }

    return {
        "allowed": False,
        "artifact_id": artifact_id,
        "track_id": published_track_id,
        "relation": "none",
        "permission_boundary": "artifact.currentness",
        "why": "foreign artifact is not a current material and not listed in close proof",
    }


def artifact_summary_row(
    artifact: dict[str, Any],
    active_buddy: str,
) -> dict[str, Any]:
    decision = artifact_read_decision(artifact, active_buddy)
    relation, currentness = _relation_and_currentness_for_decision(artifact=artifact, decision=decision)
    return {
        "id": artifact.get("id"),
        "artifact_id": artifact.get("id"),
        "track_id": artifact.get("published_to_track"),
        "relation": relation,
        "title": artifact.get("title"),
        "summary": artifact.get("summary", ""),
        "body": artifact.get("body"),
        "template": artifact.get("template"),
        "status": artifact.get("status"),
        "from_buddy": artifact.get("created_by"),
        "created_by": artifact.get("created_by"),
        "authors": artifact.get("authors"),
        "source_refs": artifact.get("source_refs"),
        "revision": artifact.get("revision"),
        "currentness": currentness,
        "readable_by_active_buddy": bool(decision.get("allowed")),
        "supersedes_artifact_id": artifact.get("supersedes_artifact_id"),
        "published_to_track": artifact.get("published_to_track"),
        "updated_at": artifact.get("updated_at"),
        "created_at": artifact.get("created_at"),
    }


def _relation_and_currentness_for_decision(
    *,
    artifact: dict[str, Any],
    decision: dict[str, Any],
) -> tuple[str, str]:
    relation = decision.get("relation")
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
    return str(relation), currentness


def artifact_list_row(
    artifact: dict[str, Any],
    active_buddy: str,
    *,
    comment_counts: dict[str, int] | None = None,
    relation_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    from env.domain import source_refs as source_refs_domain

    decision = artifact_read_decision(artifact, active_buddy)
    relation, currentness = _relation_and_currentness_for_decision(artifact=artifact, decision=decision)
    counts = comment_counts or {}
    backlinks = relation_counts or {}
    return {
        "artifact_id": artifact.get("id"),
        "title": artifact.get("title"),
        "summary": artifact.get("summary", ""),
        "template": artifact.get("template"),
        "status": artifact.get("status"),
        "currentness": currentness,
        "relation": relation,
        "created_by": artifact.get("created_by"),
        "authors": artifact.get("authors"),
        "published_to_track": artifact.get("published_to_track"),
        "revision": artifact.get("revision"),
        "supersedes_artifact_id": artifact.get("supersedes_artifact_id"),
        "source_refs_summary": source_refs_domain.source_ref_summary(artifact.get("source_refs")),
        "open_comment_count": int(counts.get("open_comment_count", 0)),
        "resolved_comment_count": int(counts.get("resolved_comment_count", 0)),
        "incoming_source_ref_count": int(backlinks.get("incoming_source_ref_count", 0)),
        "target_request_count": int(backlinks.get("target_request_count", 0)),
        "result_request_count": int(backlinks.get("result_request_count", 0)),
        "track_update_ref_count": int(backlinks.get("track_update_ref_count", 0)),
        "comment_count": int(backlinks.get("comment_count", 0)),
        "updated_at": artifact.get("updated_at"),
    }


def current_material_rows_for_track(track_id: str, active_buddy: str) -> list[dict[str, Any]]:
    track = track_repo.get_track(track_id)
    if not isinstance(track, dict) or track.get("archived_at") is not None:
        return []

    rows: list[dict[str, Any]] = []
    for ref in track.get("shared_materials", []):
        if not isinstance(ref, dict):
            continue
        if ref.get("type") != "artifact" or not bool(ref.get("current")):
            continue
        artifact_id = ref.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            continue
        artifact = artifact_repo.get_artifact(artifact_id)
        decision = artifact_read_decision(artifact, active_buddy) if isinstance(artifact, dict) else {"allowed": False}
        rows.append(
            {
                "artifact_id": artifact_id,
                "kind": ref.get("kind"),
                "label": ref.get("label"),
                "from_buddy": ref.get("from_buddy"),
                "summary": ref.get("summary", ""),
                "currentness": "current",
                "published_at": ref.get("published_at"),
                "readable_by_active_buddy": bool(decision.get("allowed")),
                "relation": "track_material" if bool(decision.get("allowed")) else "none",
            }
        )

    rows.sort(key=lambda row: (str(row.get("kind") or ""), str(row.get("artifact_id") or "")))
    return rows


def proof_rows_for_track(track_id: str, active_buddy: str) -> list[dict[str, Any]]:
    track = track_repo.get_track(track_id)
    if not isinstance(track, dict) or track.get("archived_at") is not None:
        return []

    rows: list[dict[str, Any]] = []
    for ref in track.get("close_proof", []):
        if not isinstance(ref, dict):
            continue
        if ref.get("type") != "artifact":
            continue
        if not bool(ref.get("current", True)):
            continue
        artifact_id = ref.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            continue
        artifact = artifact_repo.get_artifact(artifact_id)
        decision = artifact_read_decision(artifact, active_buddy) if isinstance(artifact, dict) else {"allowed": False}
        rows.append(
            {
                "artifact_id": artifact_id,
                "kind": ref.get("kind"),
                "label": ref.get("label"),
                "from_buddy": ref.get("from_buddy"),
                "summary": ref.get("summary", ""),
                "currentness": "proof",
                "published_at": ref.get("published_at"),
                "readable_by_active_buddy": bool(decision.get("allowed")),
                "relation": "track_proof" if bool(decision.get("allowed")) else "none",
            }
        )

    rows.sort(key=lambda row: (str(row.get("kind") or ""), str(row.get("artifact_id") or "")))
    return rows


def artifact_ref_decision_for_track_update(
    *,
    artifact_id: str,
    active_buddy: str,
    track_id: str,
) -> dict[str, Any]:
    artifact = artifact_repo.get_artifact(artifact_id)
    if artifact is None:
        return {
            "ok": False,
            "message": f"artifact not found: {artifact_id}",
        }

    decision = artifact_read_decision(artifact, active_buddy)
    if not bool(decision.get("allowed")):
        why = str(decision.get("why") or "artifact is not readable for track updates")
        return {
            "ok": False,
            "message": f"artifact '{artifact_id}' cannot be used in refs: {why}",
        }

    if decision.get("track_id") != track_id:
        return {
            "ok": False,
            "message": (
                f"artifact '{artifact_id}' belongs to track '{decision.get('track_id')}' "
                f"and cannot be referenced from track '{track_id}'"
            ),
        }

    if decision.get("relation") not in {"track_material", "track_proof"}:
        return {
            "ok": False,
            "message": f"artifact '{artifact_id}' is not a current material or close proof on track '{track_id}'",
        }

    return {"ok": True}


def assert_track_readable(track_id: str, *, active_buddy: str, action: str) -> dict[str, Any]:
    track = track_repo.get_track(track_id)
    if not isinstance(track, dict):
        return {
            "ok": False,
            "code": "E_TRACK_PAYLOAD",
            "message": f"track not found: {track_id}",
            "permission_boundary": "request-payload",
        }
    if track.get("archived_at") is not None:
        return {
            "ok": False,
            "code": "E_TRACK_ARCHIVED",
            "message": f"track '{track_id}' is archived and cannot be read via {action}",
            "permission_boundary": "track.lifecycle_status",
        }
    return {
        "ok": True,
        "track": track,
        "active_buddy": active_buddy,
    }
