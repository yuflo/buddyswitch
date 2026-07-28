"""Read-only Track projections shared by Web and runtime tools."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from buddyswitch.env.domain.identity import IdentityRef
from buddyswitch.env.repos import track_comments as track_comment_repo
from buddyswitch.env.repos import tracks as track_repo


COMMENT_KEYS = (
    "id",
    "track_id",
    "thread_id",
    "by_identity_id",
    "content",
    "reply_to",
    "mentioned_identity_ids",
    "status",
    "created_at",
    "resolved_by_identity_id",
    "resolved_at",
    "resolution_summary",
)
ARTIFACT_RELATION_KEYS = (
    "type",
    "relation_id",
    "artifact_id",
    "role",
    "label",
    "template",
    "from_identity_id",
    "summary",
    "current",
    "created_at",
)
UPDATE_KEYS = ("id", "by_identity_id", "summary", "kind", "refs", "created_at")
UPDATE_REF_KEYS = ("type", "id")


def _preview(value: Any, *, limit: int = 160) -> str:
    if not isinstance(value, str):
        return ""
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _identity_id(value: Mapping[str, Any] | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, Mapping):
        if isinstance(value.get("identity"), Mapping):
            return IdentityRef.from_payload(value["identity"]).id
        if isinstance(value.get("id"), str) and isinstance(value.get("type"), str):
            return IdentityRef.from_payload(value).id
    return None


def _comment_author_identity_id(comment: Mapping[str, Any]) -> str | None:
    identity_id = comment.get("by_identity_id")
    if isinstance(identity_id, str) and identity_id:
        return identity_id
    return None


def _allowlisted_mapping(row: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: deepcopy(row.get(key)) for key in keys}


def _comment_row(comment: Mapping[str, Any]) -> dict[str, Any]:
    return _allowlisted_mapping(comment, COMMENT_KEYS)


def _track_now(track: Mapping[str, Any]) -> dict[str, Any]:
    now = track.get("now")
    if not isinstance(now, Mapping):
        return {"next": None, "blocker": None}
    return {"next": deepcopy(now.get("next")), "blocker": deepcopy(now.get("blocker"))}


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in deepcopy(value) if isinstance(item, str)]


def _artifact_relation_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return _allowlisted_mapping(row, ARTIFACT_RELATION_KEYS)


def _update_row(row: Mapping[str, Any]) -> dict[str, Any]:
    update = _allowlisted_mapping(row, UPDATE_KEYS)
    refs = row.get("refs")
    if isinstance(refs, list):
        update["refs"] = [
            _allowlisted_mapping(ref, UPDATE_REF_KEYS)
            for ref in refs
            if isinstance(ref, Mapping)
        ]
    else:
        update["refs"] = []
    return update


def comment_threads(
    comments: Iterable[Mapping[str, Any]],
    *,
    current_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in comments:
        row = _comment_row(raw)
        thread_id = row.get("thread_id")
        comment_id = row.get("id")
        if not isinstance(thread_id, str) or not thread_id:
            if not isinstance(comment_id, str) or not comment_id:
                continue
            thread_id = comment_id
        grouped.setdefault(thread_id, []).append(row)

    rows: list[dict[str, Any]] = []
    active_identity_id = _identity_id(current_identity)
    for thread_id, thread_comments in grouped.items():
        thread_comments.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))
        latest = thread_comments[-1] if thread_comments else {}
        thread_status = "resolved" if thread_comments and all(row.get("status") == "resolved" for row in thread_comments) else "open"
        rows.append(
            {
                "thread_id": thread_id,
                "status": thread_status,
                "comment_count": len(thread_comments),
                "latest_comment_id": latest.get("id"),
                "latest_comment_preview": _preview(latest.get("content")),
                "latest_by_identity_id": latest.get("by_identity_id"),
                "mentions_me": any(
                    active_identity_id in comment.get("mentioned_identity_ids", [])
                    for comment in thread_comments
                    if isinstance(comment.get("mentioned_identity_ids"), list)
                ),
                "replies_to_me": any(_comment_author_identity_id(comment) == active_identity_id for comment in thread_comments if comment.get("reply_to")),
                "comments": thread_comments,
            }
        )

    rows.sort(key=lambda row: (str(row["comments"][-1].get("created_at") if row["comments"] else ""), str(row.get("thread_id") or "")), reverse=True)
    open_count = sum(1 for row in rows if row.get("status") == "open")
    resolved_count = sum(1 for row in rows if row.get("status") == "resolved")
    return {
        "threads": rows,
        "summary": {
            "open_thread_count": open_count,
            "resolved_thread_count": resolved_count,
            "comment_count": sum(int(row.get("comment_count") or 0) for row in rows),
        },
    }


def track_summary(
    track: Mapping[str, Any],
    *,
    comments: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    comment_projection = comment_threads(comments or [])
    return {
        "id": track.get("id"),
        "title": track.get("title"),
        "outcome": track.get("outcome"),
        "owner_identity_id": track.get("owner_identity_id"),
        "state": track.get("state"),
        "now": _track_now(track),
        "acceptance_criteria": _text_list(track.get("acceptance_criteria")),
        "non_goals": _text_list(track.get("non_goals")),
        "updated_at": track.get("updated_at"),
        "comment_summary": comment_projection["summary"],
    }


def track_detail(
    track: Mapping[str, Any],
    *,
    comments: Iterable[Mapping[str, Any]] | None = None,
    current_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    page = track_summary(track, comments=comments)
    relations = [
        _artifact_relation_row(row)
        for row in track.get("artifact_relations", [])
        if isinstance(row, Mapping)
    ]
    thread_projection = comment_threads(comments or [], current_identity=current_identity)
    page.update(
        {
            "materials": [row for row in relations if row.get("role") == "material"],
            "proofs": [row for row in relations if row.get("role") == "proof"],
            "updates": [_update_row(row) for row in track.get("updates", []) if isinstance(row, Mapping)],
            "comment_threads": thread_projection["threads"],
            "comment_summary": thread_projection["summary"],
        }
    )
    return page


def _sort_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("updated_at") or ""), str(row.get("id") or ""))


def list_external_tracks(*, owner_identity: Mapping[str, Any] | str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    owner_identity_id = _identity_id(owner_identity)
    for track in track_repo.list_tracks():
        if track.get("archived_at") is not None:
            continue
        if owner_identity is not None and track.get("owner_identity_id") != owner_identity_id:
            continue
        track_id = track.get("id")
        comments = track_comment_repo.comments_for_track(track_id) if isinstance(track_id, str) else []
        rows.append(track_summary(track, comments=comments))
    rows.sort(key=_sort_key, reverse=True)
    return rows


def get_external_track(track_id: str, *, current_identity: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    track = track_repo.get_track(track_id)
    if track is None or track.get("archived_at") is not None:
        return None
    comments = track_comment_repo.comments_for_track(track_id)
    return track_detail(track, comments=comments, current_identity=current_identity)


def list_track_summaries(*, owner_identity: Mapping[str, Any] | str | None = None) -> list[dict[str, Any]]:
    return list_external_tracks(owner_identity=owner_identity)


def get_track_detail(track_id: str, *, current_identity: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    return get_external_track(track_id, current_identity=current_identity)
