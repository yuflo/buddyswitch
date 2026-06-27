#!/usr/bin/env python3
"""Read-only Track projections shared by Web and runtime tools."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from env.repos import track_comments as track_comment_repo
from env.repos import tracks as track_repo


def _preview(value: Any, *, limit: int = 160) -> str:
    if not isinstance(value, str):
        return ""
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _same_actor(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> bool:
    if left is None or right is None:
        return False
    return left.get("actor_id") == right.get("actor_id") and left.get("role_id") == right.get("role_id")


def comment_threads(
    comments: Iterable[Mapping[str, Any]],
    *,
    active_actor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in comments:
        row = dict(raw)
        thread_id = row.get("thread_id")
        comment_id = row.get("id")
        if not isinstance(thread_id, str) or not thread_id:
            if not isinstance(comment_id, str) or not comment_id:
                continue
            thread_id = comment_id
        grouped.setdefault(thread_id, []).append(row)

    rows: list[dict[str, Any]] = []
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
                "latest_by_actor": latest.get("by_actor"),
                "mentions_me": any(_same_actor(active_actor, row) for comment in thread_comments for row in comment.get("mentioned_actors", [])),
                "replies_to_me": any(_same_actor(active_actor, comment.get("by_actor")) for comment in thread_comments if comment.get("reply_to")),
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
        "owner_actor": track.get("owner_actor"),
        "state": track.get("state"),
        "now": track.get("now"),
        "acceptance_criteria": track.get("acceptance_criteria"),
        "non_goals": track.get("non_goals"),
        "updated_at": track.get("updated_at"),
        "comment_summary": comment_projection["summary"],
    }


def track_detail(
    track: Mapping[str, Any],
    *,
    comments: Iterable[Mapping[str, Any]] | None = None,
    active_actor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    page = track_summary(track, comments=comments)
    relations = [dict(row) for row in track.get("artifact_relations", []) if isinstance(row, Mapping)]
    thread_projection = comment_threads(comments or [], active_actor=active_actor)
    page.update(
        {
            "materials": [row for row in relations if row.get("role") == "material"],
            "proofs": [row for row in relations if row.get("role") == "proof"],
            "updates": [dict(row) for row in track.get("updates", []) if isinstance(row, Mapping)],
            "comment_threads": thread_projection["threads"],
            "comment_summary": thread_projection["summary"],
        }
    )
    return page


def list_track_summaries(*, owner_actor: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track in track_repo.list_tracks():
        if track.get("archived_at") is not None:
            continue
        if owner_actor is not None and not _same_actor(track.get("owner_actor"), owner_actor):
            continue
        track_id = track.get("id")
        comments = track_comment_repo.comments_for_track(track_id) if isinstance(track_id, str) else []
        rows.append(track_summary(track, comments=comments))
    return rows


def get_track_detail(track_id: str, *, active_actor: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    track = track_repo.get_track(track_id)
    if track is None or track.get("archived_at") is not None:
        return None
    comments = track_comment_repo.comments_for_track(track_id)
    return track_detail(track, comments=comments, active_actor=active_actor)
