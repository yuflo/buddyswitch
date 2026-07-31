"""Track Public operations over Track-owned state."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from buddyswitch.modules.track.private import read_model
from buddyswitch.modules.track.private.state import track_comments, tracks
from buddyswitch.modules.track.public.contracts import (
    ArtifactRelationFact,
    ArtifactUsage,
    TrackContextSnapshot,
    TrackScope,
    TrackUpdateReferenceFact,
)


def read_track_scope(track_id: str) -> TrackScope | None:
    track = tracks.get_track(track_id)
    if track is None:
        return None
    owner_identity_id = track.get("owner_identity_id")
    if not isinstance(owner_identity_id, str) or not owner_identity_id:
        return None
    archived_at = track.get("archived_at")
    return TrackScope(
        track_id=str(track["id"]),
        owner_identity_id=owner_identity_id,
        archived_at=archived_at if isinstance(archived_at, str) else None,
    )


def read_artifact_usage(artifact_id: str) -> ArtifactUsage:
    relations: list[ArtifactRelationFact] = []
    update_references: list[TrackUpdateReferenceFact] = []
    for track in tracks.list_tracks():
        track_id = track.get("id")
        if not isinstance(track_id, str) or not track_id:
            continue
        archived = track.get("archived_at")
        archived_at = archived if isinstance(archived, str) else None
        for relation in track.get("artifact_relations", []):
            if (
                not isinstance(relation, dict)
                or relation.get("type") != "artifact"
                or relation.get("artifact_id") != artifact_id
            ):
                continue
            relations.append(
                ArtifactRelationFact(
                    track_id=track_id,
                    track_archived_at=archived_at,
                    relation_id=relation.get("relation_id")
                    if isinstance(relation.get("relation_id"), str)
                    else None,
                    artifact_id=artifact_id,
                    role=relation.get("role")
                    if isinstance(relation.get("role"), str)
                    else None,
                    label=relation.get("label")
                    if isinstance(relation.get("label"), str)
                    else None,
                    template=relation.get("template")
                    if isinstance(relation.get("template"), str)
                    else None,
                    from_identity_id=relation.get("from_identity_id")
                    if isinstance(relation.get("from_identity_id"), str)
                    else None,
                    summary=str(relation.get("summary") or ""),
                    current=bool(relation.get("current")),
                    created_at=relation.get("created_at")
                    if isinstance(relation.get("created_at"), str)
                    else None,
                )
            )
        for update in track.get("updates", []):
            if not isinstance(update, dict):
                continue
            refs = update.get("refs")
            if not isinstance(refs, list) or not any(
                isinstance(ref, dict)
                and ref.get("type") == "artifact"
                and ref.get("id") == artifact_id
                for ref in refs
            ):
                continue
            update_id = update.get("id")
            if not isinstance(update_id, str) or not update_id:
                continue
            update_references.append(
                TrackUpdateReferenceFact(
                    track_id=track_id,
                    track_archived_at=archived_at,
                    update_id=update_id,
                    kind=update.get("kind")
                    if isinstance(update.get("kind"), str)
                    else None,
                    summary=update.get("summary")
                    if isinstance(update.get("summary"), str)
                    else None,
                    by_identity_id=update.get("by_identity_id")
                    if isinstance(update.get("by_identity_id"), str)
                    else None,
                    created_at=update.get("created_at")
                    if isinstance(update.get("created_at"), str)
                    else None,
                )
            )
    return ArtifactUsage(
        artifact_id=artifact_id,
        relations=tuple(relations),
        update_references=tuple(update_references),
    )


def list_external_tracks(
    *,
    owner_identity: Mapping[str, Any] | str | None = None,
) -> list[dict[str, Any]]:
    return read_model.list_external_tracks(owner_identity=owner_identity)


def get_external_track(
    track_id: str,
    *,
    current_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    return read_model.get_external_track(
        track_id,
        current_identity=current_identity,
    )


def _candidate_track_row(
    *,
    track: dict[str, Any],
    current_identity: dict[str, Any],
) -> dict[str, Any]:
    identity_id = current_identity.get("id")
    relation = (
        "owner"
        if isinstance(identity_id, str)
        and track.get("owner_identity_id") == identity_id
        else "collaborator"
    )
    return {
        "track_id": track.get("id"),
        "title": track.get("title"),
        "outcome": track.get("outcome", ""),
        "owner_identity_id": track.get("owner_identity_id"),
        "state": track.get("state"),
        "now": track.get("now"),
        "acceptance_criteria": track.get("acceptance_criteria"),
        "non_goals": track.get("non_goals"),
        "current_identity_relation": relation,
        "active_role_relation": relation,
        "updated_at": track.get("updated_at"),
    }


def _open_comment_threads(
    *,
    visible_track_ids: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for comment in track_comments.list_track_comments():
        track_id = comment.get("track_id")
        if not isinstance(track_id, str) or track_id not in visible_track_ids:
            continue
        thread_id = comment.get("thread_id")
        if isinstance(thread_id, str) and thread_id:
            grouped.setdefault(thread_id, []).append(comment)
    rows: list[dict[str, Any]] = []
    for thread_id, comments in grouped.items():
        comments.sort(
            key=lambda row: (
                str(row.get("created_at") or ""),
                str(row.get("id") or ""),
            )
        )
        open_count = sum(1 for row in comments if row.get("status") == "open")
        if open_count == 0:
            continue
        latest = comments[-1]
        rows.append(
            {
                "thread_id": thread_id,
                "track_id": latest.get("track_id"),
                "latest_comment_id": latest.get("id"),
                "latest_by_identity_id": latest.get("by_identity_id"),
                "open_comment_count": open_count,
                "updated_at": latest.get("created_at"),
            }
        )
    rows.sort(
        key=lambda row: (
            str(row.get("updated_at") or ""),
            str(row.get("thread_id") or ""),
        ),
        reverse=True,
    )
    return rows[:limit]


def _recent_updates(
    *,
    visible_tracks: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track in visible_tracks:
        track_id = track.get("id")
        if not isinstance(track_id, str) or not track_id:
            continue
        for update in track.get("updates", []):
            if not isinstance(update, dict):
                continue
            refs = update.get("refs")
            ref_count = len(refs) if isinstance(refs, list) else 0
            rows.append(
                {
                    "track_id": track_id,
                    "update_id": update.get("id"),
                    "kind": update.get("kind"),
                    "summary": update.get("summary"),
                    "by_identity_id": update.get("by_identity_id"),
                    "ref_count": ref_count,
                    "created_at": update.get("created_at"),
                }
            )
    rows.sort(
        key=lambda row: (
            str(row.get("created_at") or ""),
            str(row.get("update_id") or ""),
        ),
        reverse=True,
    )
    return rows[:limit]


def context_snapshot(
    *,
    current_identity: dict[str, Any],
    track_filter: str | None = None,
    limit: int = 20,
) -> TrackContextSnapshot:
    visible_tracks = [
        row
        for row in tracks.list_tracks()
        if row.get("archived_at") is None
    ]
    if isinstance(track_filter, str) and track_filter.strip():
        visible_tracks = [
            row
            for row in visible_tracks
            if row.get("id") == track_filter.strip()
        ]
    visible_tracks = visible_tracks[:limit]
    visible_ids = {
        str(row["id"])
        for row in visible_tracks
        if isinstance(row.get("id"), str)
    }
    return TrackContextSnapshot(
        tracks=tuple(deepcopy(visible_tracks)),
        candidate_tracks=tuple(
            _candidate_track_row(
                track=row,
                current_identity=current_identity,
            )
            for row in visible_tracks
        ),
        open_comment_threads=tuple(
            _open_comment_threads(
                visible_track_ids=visible_ids,
                limit=limit,
            )
        ),
        recent_updates=tuple(
            _recent_updates(
                visible_tracks=visible_tracks,
                limit=limit,
            )
        ),
    )
