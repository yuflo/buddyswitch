#!/usr/bin/env python3
"""Direct track-publication visibility helpers."""

from __future__ import annotations

from typing import Any

import env_store


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
        if row.get("artifact_id") == artifact_id:
            return row
    return None


def artifact_read_decision(artifact: dict[str, Any], active_buddy: str) -> dict[str, Any]:
    artifact_id = artifact.get("id") if isinstance(artifact.get("id"), str) else None
    owner = artifact.get("created_by")
    published_track_id = artifact.get("published_to_track")

    if published_track_id is None:
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

    track = env_store.get_track(published_track_id)
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
    is_current = bool(artifact.get("is_current"))
    relation = decision.get("relation")
    if relation not in {"owner", "track_material", "track_proof"}:
        relation = "none"
    return {
        "id": artifact.get("id"),
        "artifact_id": artifact.get("id"),
        "track_id": artifact.get("published_to_track"),
        "relation": relation,
        "kind": artifact.get("kind"),
        "title": artifact.get("title"),
        "summary": artifact.get("summary", ""),
        "from_buddy": artifact.get("created_by"),
        "created_by": artifact.get("created_by"),
        "source_refs": artifact.get("source_refs"),
        "revision": artifact.get("revision"),
        "currentness": "current" if is_current else "superseded",
        "readable_by_active_buddy": bool(decision.get("allowed")),
        "supersedes_artifact_id": artifact.get("supersedes_artifact_id"),
        "publication_role": artifact.get("publication_role"),
        "published_to_track": artifact.get("published_to_track"),
        "content": artifact.get("content"),
        "updated_at": artifact.get("updated_at"),
        "created_at": artifact.get("created_at"),
    }


def current_material_rows_for_track(track_id: str, active_buddy: str) -> list[dict[str, Any]]:
    track = env_store.get_track(track_id)
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
        artifact = env_store.get_artifact(artifact_id)
        decision = artifact_read_decision(artifact, active_buddy) if isinstance(artifact, dict) else {
            "allowed": False
        }
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
    track = env_store.get_track(track_id)
    if not isinstance(track, dict) or track.get("archived_at") is not None:
        return []

    rows: list[dict[str, Any]] = []
    for ref in track.get("close_proof", []):
        if not isinstance(ref, dict):
            continue
        if ref.get("type") != "artifact":
            continue
        artifact_id = ref.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            continue
        artifact = env_store.get_artifact(artifact_id)
        decision = artifact_read_decision(artifact, active_buddy) if isinstance(artifact, dict) else {
            "allowed": False
        }
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


def assert_track_readable(track_id: str, *, active_buddy: str, action: str) -> dict[str, Any]:
    track = env_store.get_track(track_id)
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
