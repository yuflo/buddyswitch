#!/usr/bin/env python3
"""Cross-object track/artifact publication mutations with atomic rollback."""

from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any, TypedDict

from env.repos import artifacts as artifact_repo
from env.repos import tracks as track_repo


class MaterialPublicationResult(TypedDict):
    track: dict[str, Any]
    artifact: dict[str, Any]
    superseded_artifact_id: str | None


class ProofPublicationResult(TypedDict):
    track: dict[str, Any]
    artifact: dict[str, Any]
    superseded_artifact_id: str | None
    update: dict[str, Any]


def _commit_atomic_publication(
    *,
    track_before: dict[str, Any],
    track_after: dict[str, Any],
    artifact_before: dict[str, Any],
    artifact_after: dict[str, Any],
    replaced_artifact_before: dict[str, Any] | None,
    replaced_artifact_after: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Commit publication writes and rollback all previously written objects on failure."""

    applied: list[tuple[str, dict[str, Any]]] = []
    try:
        if isinstance(replaced_artifact_after, dict):
            artifact_repo.save_artifact(replaced_artifact_after)
            if isinstance(replaced_artifact_before, dict):
                applied.append(("artifact", deepcopy(replaced_artifact_before)))
        artifact_repo.save_artifact(artifact_after)
        applied.append(("artifact", deepcopy(artifact_before)))
        saved_track = track_repo.save_track(track_after)
        applied.append(("track", deepcopy(track_before)))
        saved_artifact = artifact_repo.get_artifact(str(artifact_after.get("id") or ""))
        if not isinstance(saved_artifact, dict):
            raise ValueError("published artifact could not be reloaded after save")
        return saved_track, saved_artifact
    except Exception as exc:  # pragma: no cover - rollback path validated by integration tests
        rollback_errors: list[str] = []
        for object_type, previous in reversed(applied):
            try:
                if object_type == "track":
                    track_repo.save_track(previous)
                else:
                    artifact_repo.save_artifact(previous)
            except Exception as rollback_exc:
                rollback_errors.append(str(rollback_exc))
        if rollback_errors:
            raise ValueError(f"{exc}; rollback failed: {'; '.join(rollback_errors)}") from exc
        raise ValueError(str(exc)) from exc


def publish_material(
    *,
    track_id: str,
    artifact_id: str,
    label: str,
    from_buddy: str,
    summary: str,
) -> MaterialPublicationResult:
    track = track_repo.get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    if track.get("archived_at") is not None:
        raise ValueError(f"track '{track_id}' is archived and cannot accept material publication")
    artifact = artifact_repo.get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    if artifact.get("created_by") != from_buddy:
        raise ValueError(f"artifact '{artifact_id}' is owned by buddy '{artifact.get('created_by')}'")

    kind = str(artifact.get("template") or "")
    if not kind:
        raise ValueError("artifact.template is required for track publication")

    status = artifact.get("status")
    published_to_track = artifact.get("published_to_track")
    if status != "draft":
        if published_to_track is None:
            raise ValueError(f"artifact '{artifact_id}' is not a publishable draft")
        if published_to_track != track_id:
            raise ValueError(
                f"artifact '{artifact_id}' is already published to track '{published_to_track}' and cannot be republished to '{track_id}'"
            )
        if any(
            isinstance(row, dict)
            and row.get("type") == "artifact"
            and row.get("artifact_id") == artifact_id
            and bool(row.get("current"))
            for row in track.get("shared_materials", [])
        ):
            raise ValueError(f"artifact '{artifact_id}' is already current material on track '{track_id}'")
        if any(
            isinstance(row, dict)
            and row.get("type") == "artifact"
            and row.get("artifact_id") == artifact_id
            and bool(row.get("current", True))
            for row in track.get("close_proof", [])
        ):
            raise ValueError(f"artifact '{artifact_id}' is already bound as close proof on track '{track_id}'")
        raise ValueError(
            f"artifact '{artifact_id}' is already bound to track '{track_id}' but not as current material; create a new revision instead"
        )

    replaced_artifact_id: str | None = None
    next_refs: list[dict[str, Any]] = []
    for row in track.get("shared_materials", []):
        if not isinstance(row, dict):
            continue
        same_slot = row.get("kind") == kind and row.get("label") == label and row.get("from_buddy") == from_buddy
        if same_slot and bool(row.get("current")):
            replaced_artifact_id = str(row.get("artifact_id") or "") or replaced_artifact_id
        next_row = dict(row)
        if same_slot:
            next_row["current"] = False
        next_refs.append(next_row)

    history_ids = {
        str(row.get("artifact_id"))
        for row in track.get("shared_materials", [])
        if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
    }
    history_ids.update(
        str(row.get("artifact_id"))
        for row in track.get("close_proof", [])
        if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
    )

    supersedes: str | None = None
    existing_supersedes = artifact.get("supersedes_artifact_id")
    if isinstance(existing_supersedes, str) and existing_supersedes:
        if replaced_artifact_id is not None and existing_supersedes == replaced_artifact_id:
            supersedes = existing_supersedes
        elif existing_supersedes in history_ids:
            supersedes = existing_supersedes
        else:
            raise ValueError(
                f"artifact '{artifact_id}' supersedes_artifact_id '{existing_supersedes}' does not match readable history on track '{track_id}'"
            )
    else:
        supersedes = replaced_artifact_id

    replaced_before: dict[str, Any] | None = None
    replaced_after: dict[str, Any] | None = None
    if replaced_artifact_id is not None:
        old_artifact = artifact_repo.get_artifact(replaced_artifact_id)
        if isinstance(old_artifact, dict):
            replaced_before = deepcopy(old_artifact)
            replaced_after = dict(old_artifact)
            replaced_after["is_current"] = False
            replaced_after["updated_at"] = track_repo.now_iso()
            replaced_after = artifact_repo.validate_artifact(replaced_after)

    artifact_revision = int(artifact.get("revision", 1))
    if replaced_artifact_id:
        previous = artifact_repo.get_artifact(replaced_artifact_id)
        if previous is not None:
            artifact_revision = max(int(previous.get("revision", 1)) + 1, artifact_revision)

    artifact_before = deepcopy(artifact)
    artifact_after = dict(artifact)
    artifact_after.update(
        {
            "published_to_track": track_id,
            "status": "published",
            "supersedes_artifact_id": supersedes,
            "is_current": True,
            "revision": artifact_revision,
            "updated_at": track_repo.now_iso(),
        }
    )
    artifact_after = artifact_repo.validate_artifact(artifact_after)

    next_refs.append(
        {
            "type": "artifact",
            "artifact_id": artifact_id,
            "label": label,
            "kind": kind,
            "from_buddy": from_buddy,
            "summary": summary,
            "current": True,
            "published_at": track_repo.now_iso(),
        }
    )

    track_before = deepcopy(track)
    track_after = dict(track)
    track_after["shared_materials"] = next_refs
    track_after["updated_at"] = track_repo.now_iso()
    track_after = track_repo.validate_track(track_after)

    saved_track, saved_artifact = _commit_atomic_publication(
        track_before=track_before,
        track_after=track_after,
        artifact_before=artifact_before,
        artifact_after=artifact_after,
        replaced_artifact_before=replaced_before,
        replaced_artifact_after=replaced_after,
    )
    return {
        "track": saved_track,
        "artifact": saved_artifact,
        "superseded_artifact_id": replaced_artifact_id,
    }


def publish_proof(
    *,
    track_id: str,
    artifact_id: str,
    label: str,
    from_buddy: str,
    summary: str,
    update_summary: str | None = None,
) -> ProofPublicationResult:
    track = track_repo.get_track(track_id)
    if track is None:
        raise ValueError(f"track not found: {track_id}")
    if track.get("archived_at") is not None:
        raise ValueError(f"track '{track_id}' is archived and cannot accept proof publication")
    artifact = artifact_repo.get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")
    if artifact.get("created_by") != from_buddy:
        raise ValueError(f"artifact '{artifact_id}' is owned by buddy '{artifact.get('created_by')}'")

    kind = str(artifact.get("template") or "")
    if not kind:
        raise ValueError("artifact.template is required for track proof publication")

    status = artifact.get("status")
    published_to_track = artifact.get("published_to_track")
    if status != "draft":
        if published_to_track is None:
            raise ValueError(f"artifact '{artifact_id}' is not a publishable draft")
        if published_to_track != track_id:
            raise ValueError(
                f"artifact '{artifact_id}' is already published to track '{published_to_track}' and cannot be republished to '{track_id}'"
            )
        if any(
            isinstance(row, dict)
            and row.get("type") == "artifact"
            and row.get("artifact_id") == artifact_id
            and bool(row.get("current", True))
            for row in track.get("close_proof", [])
        ):
            raise ValueError(f"artifact '{artifact_id}' is already current close proof on track '{track_id}'")
        if any(
            isinstance(row, dict)
            and row.get("type") == "artifact"
            and row.get("artifact_id") == artifact_id
            and bool(row.get("current"))
            for row in track.get("shared_materials", [])
        ):
            raise ValueError(f"artifact '{artifact_id}' is already bound as shared material on track '{track_id}'")
        raise ValueError(
            f"artifact '{artifact_id}' is already bound to track '{track_id}' but missing close_proof current ref; create a new proof artifact instead"
        )

    replaced_artifact_id: str | None = None
    next_proof_rows: list[dict[str, Any]] = []
    for row in track.get("close_proof", []):
        if not isinstance(row, dict):
            continue
        same_slot = row.get("kind") == kind and row.get("label") == label and row.get("from_buddy") == from_buddy
        if same_slot and bool(row.get("current", True)):
            replaced_artifact_id = str(row.get("artifact_id") or "") or replaced_artifact_id
        next_row = dict(row)
        if same_slot:
            next_row["current"] = False
        next_proof_rows.append(next_row)

    history_ids = {
        str(row.get("artifact_id"))
        for row in track.get("shared_materials", [])
        if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
    }
    history_ids.update(
        str(row.get("artifact_id"))
        for row in track.get("close_proof", [])
        if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
    )
    supersedes: str | None = replaced_artifact_id
    existing_supersedes = artifact.get("supersedes_artifact_id")
    if isinstance(existing_supersedes, str) and existing_supersedes:
        if replaced_artifact_id is not None and existing_supersedes == replaced_artifact_id:
            supersedes = existing_supersedes
        elif existing_supersedes in history_ids:
            supersedes = existing_supersedes
        else:
            raise ValueError(
                f"artifact '{artifact_id}' supersedes_artifact_id '{existing_supersedes}' does not match readable history on track '{track_id}'"
            )

    replaced_before: dict[str, Any] | None = None
    replaced_after: dict[str, Any] | None = None
    if replaced_artifact_id is not None:
        old_artifact = artifact_repo.get_artifact(replaced_artifact_id)
        if isinstance(old_artifact, dict):
            replaced_before = deepcopy(old_artifact)
            replaced_after = dict(old_artifact)
            replaced_after["is_current"] = False
            replaced_after["updated_at"] = track_repo.now_iso()
            replaced_after = artifact_repo.validate_artifact(replaced_after)

    artifact_before = deepcopy(artifact)
    artifact_after = dict(artifact)
    artifact_after.update(
        {
            "published_to_track": track_id,
            "status": "published",
            "supersedes_artifact_id": supersedes,
            "is_current": True,
            "updated_at": track_repo.now_iso(),
        }
    )
    artifact_after = artifact_repo.validate_artifact(artifact_after)

    next_proof_rows.append(
        {
            "type": "artifact",
            "artifact_id": artifact_id,
            "label": label,
            "kind": kind,
            "from_buddy": from_buddy,
            "summary": summary,
            "current": True,
            "published_at": track_repo.now_iso(),
        }
    )

    update_row = {
        "id": f"upd-{uuid.uuid4().hex[:8]}",
        "by_buddy": from_buddy,
        "summary": update_summary if isinstance(update_summary, str) and update_summary.strip() else f"{from_buddy} published proof",
        "kind": "proof",
        "refs": [{"type": "artifact", "id": artifact_id}],
        "created_at": track_repo.now_iso(),
    }
    existing_updates = [row for row in track.get("updates", []) if isinstance(row, dict)]

    track_before = deepcopy(track)
    track_after = dict(track)
    track_after["close_proof"] = next_proof_rows
    track_after["updates"] = [*existing_updates, update_row]
    track_after["updated_at"] = track_repo.now_iso()
    track_after = track_repo.validate_track(track_after)

    saved_track, saved_artifact = _commit_atomic_publication(
        track_before=track_before,
        track_after=track_after,
        artifact_before=artifact_before,
        artifact_after=artifact_after,
        replaced_artifact_before=replaced_before,
        replaced_artifact_after=replaced_after,
    )
    return {
        "track": saved_track,
        "artifact": saved_artifact,
        "superseded_artifact_id": replaced_artifact_id,
        "update": update_row,
    }
