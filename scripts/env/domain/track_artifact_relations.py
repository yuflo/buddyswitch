#!/usr/bin/env python3
"""Track-owned Artifact relation mutations."""

from __future__ import annotations

import uuid
from typing import Any, TypedDict

from env.repos import artifacts as artifact_repo
from env.repos import tracks as track_repo
from env.tool_runtime.actor_profile import ActorAddress


class MaterialRelationResult(TypedDict):
    track: dict[str, Any]
    artifact: dict[str, Any]
    superseded_artifact_id: str | None


class ProofRelationResult(TypedDict):
    track: dict[str, Any]
    artifact: dict[str, Any]
    superseded_artifact_id: str | None
    update: dict[str, Any]


def _actor_payload(value: dict[str, Any]) -> dict[str, str]:
    return ActorAddress.from_payload(value).to_payload()


def _actor_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    try:
        return ActorAddress.from_payload(value).actor_id
    except ValueError:
        return None


def _load_track(track_id: str) -> dict[str, Any]:
    track = track_repo.get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    if track.get("archived_at") is not None:
        raise ValueError(f"track '{track_id}' is archived and cannot accept artifact relations")
    return track


def _load_owned_artifact(artifact_id: str, actor: ActorAddress) -> dict[str, Any]:
    artifact = artifact_repo.get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    if artifact.get("created_by_actor") != actor.to_payload():
        raise ValueError(f"artifact '{artifact_id}' is owned by another actor")
    if not isinstance(artifact.get("template"), str) or not artifact.get("template"):
        raise ValueError("artifact.template is required for track artifact relation")
    return artifact


def _same_relation_slot(*, row: dict[str, Any], role: str, label: str, template: str, actor: ActorAddress) -> bool:
    return (
        row.get("role") == role
        and row.get("label") == label
        and row.get("template") == template
        and _actor_id(row.get("from_actor")) == actor.actor_id
    )


def _relation_row(
    *,
    artifact_id: str,
    role: str,
    label: str,
    template: str,
    from_actor: dict[str, str],
    summary: str,
) -> dict[str, Any]:
    return {
        "relation_id": f"rel-{uuid.uuid4().hex[:10]}",
        "type": "artifact",
        "artifact_id": artifact_id,
        "role": role,
        "label": label,
        "template": template,
        "from_actor": from_actor,
        "summary": summary,
        "current": True,
        "created_at": track_repo.now_iso(),
    }


def _next_relation_rows(
    *,
    track: dict[str, Any],
    artifact: dict[str, Any],
    role: str,
    label: str,
    actor: ActorAddress,
    summary: str,
) -> tuple[list[dict[str, Any]], str | None]:
    template = str(artifact.get("template") or "")
    superseded_artifact_id: str | None = None
    rows: list[dict[str, Any]] = []
    for row in track.get("artifact_relations", []):
        if not isinstance(row, dict):
            continue
        next_row = dict(row)
        if _same_relation_slot(row=row, role=role, label=label, template=template, actor=actor):
            if bool(row.get("current")):
                existing_artifact_id = row.get("artifact_id")
                if existing_artifact_id == artifact.get("id"):
                    raise ValueError(f"artifact '{artifact.get('id')}' is already current {role} on track '{track.get('id')}'")
                if isinstance(existing_artifact_id, str) and existing_artifact_id:
                    superseded_artifact_id = existing_artifact_id
            next_row["current"] = False
        rows.append(next_row)

    rows.append(
        _relation_row(
            artifact_id=str(artifact["id"]),
            role=role,
            label=label,
            template=template,
            from_actor=actor.to_payload(),
            summary=summary,
        )
    )
    return rows, superseded_artifact_id


def add_material_relation(
    *,
    track_id: str,
    artifact_id: str,
    label: str,
    from_actor: dict[str, Any],
    summary: str,
) -> MaterialRelationResult:
    track = _load_track(track_id)
    actor = ActorAddress.from_payload(_actor_payload(from_actor))
    artifact = _load_owned_artifact(artifact_id, actor)
    rows, superseded_artifact_id = _next_relation_rows(
        track=track,
        artifact=artifact,
        role="material",
        label=label,
        actor=actor,
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
    from_actor: dict[str, Any],
    summary: str,
    update_summary: str | None = None,
) -> ProofRelationResult:
    track = _load_track(track_id)
    actor = ActorAddress.from_payload(_actor_payload(from_actor))
    artifact = _load_owned_artifact(artifact_id, actor)
    rows, superseded_artifact_id = _next_relation_rows(
        track=track,
        artifact=artifact,
        role="proof",
        label=label,
        actor=actor,
        summary=summary,
    )

    update_row = {
        "id": f"upd-{uuid.uuid4().hex[:8]}",
        "by_actor": actor.to_payload(),
        "summary": update_summary if isinstance(update_summary, str) and update_summary.strip() else f"{actor.role_id} shared proof",
        "kind": "proof",
        "refs": [{"type": "artifact", "id": artifact_id}],
        "created_at": track_repo.now_iso(),
    }
    updates = [row for row in track.get("updates", []) if isinstance(row, dict)]

    track_after = dict(track)
    track_after["artifact_relations"] = rows
    track_after["updates"] = [*updates, update_row]
    track_after["updated_at"] = track_repo.now_iso()
    saved_track = track_repo.save_track(track_after)
    return {
        "track": saved_track,
        "artifact": artifact,
        "superseded_artifact_id": superseded_artifact_id,
        "update": update_row,
    }
