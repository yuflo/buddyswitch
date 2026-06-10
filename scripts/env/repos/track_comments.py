#!/usr/bin/env python3
"""Track comment repository helpers backed by runtime object files."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from env.tool_runtime.actor_profile import ActorAddress
from . import runtime_files

_COMMENT_STATUSES = {"open", "resolved"}
_FORBIDDEN_TRACK_COMMENT_FIELDS = {
    "target_type",
    "target_id",
    "anchor",
    "artifact_revision_id",
    "resolved",
    "task_id",
    "edit_history",
    "attachment",
}


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _normalize_actor(value: Any, field: str) -> dict[str, str]:
    try:
        return ActorAddress.from_payload(value).to_payload()
    except ValueError as exc:
        raise ValueError(f"{field} must be an ActorAddress payload: {exc}") from exc


def track_comment_file(track_id: str, comment_id: str) -> Path:
    return (
        runtime_files.TRACK_COMMENTS_DIR
        / runtime_files.require_id(track_id, "track id")
        / f"{runtime_files.require_id(comment_id, 'comment id')}.json"
    )


def _track_comment_dir(track_id: str) -> Path:
    return runtime_files.TRACK_COMMENTS_DIR / runtime_files.require_id(track_id, "track id")


def validate_track_comment(comment: dict[str, Any]) -> dict[str, Any]:
    forbidden = sorted(key for key in comment if key in _FORBIDDEN_TRACK_COMMENT_FIELDS)
    if forbidden:
        raise ValueError(f"unsupported track comment fields: {', '.join(forbidden)}")

    comment_id = runtime_files.require_id(comment.get("id", ""), "comment.id")
    track_id = runtime_files.require_id(comment.get("track_id"), "comment.track_id")
    by_actor = _normalize_actor(comment.get("by_actor"), "comment.by_actor")
    content = _require_non_empty_text(comment.get("content"), "comment.content")

    thread_id_raw = comment.get("thread_id")
    if thread_id_raw is None:
        thread_id = comment_id
    else:
        thread_id = runtime_files.require_id(
            _require_non_empty_text(thread_id_raw, "comment.thread_id"),
            "comment.thread_id",
        )

    reply_to = comment.get("reply_to")
    if reply_to is not None:
        reply_to = runtime_files.require_id(reply_to, "comment.reply_to")

    status = _require_non_empty_text(comment.get("status", "open"), "comment.status")
    if status not in _COMMENT_STATUSES:
        raise ValueError("comment.status must be one of open|resolved")

    resolved_by_actor = comment.get("resolved_by_actor")
    resolved_at = comment.get("resolved_at")
    resolution_summary = comment.get("resolution_summary")
    if status == "resolved":
        resolved_by_actor = _normalize_actor(resolved_by_actor, "comment.resolved_by_actor")
        resolved_at = _require_non_empty_text(resolved_at, "comment.resolved_at")
        resolution_summary = _require_non_empty_text(resolution_summary, "comment.resolution_summary")
    else:
        resolved_by_actor = None
        resolved_at = None
        resolution_summary = None

    mentioned_raw = comment.get("mentioned_actors", [])
    if mentioned_raw is None:
        mentioned_actors: list[dict[str, str]] = []
    else:
        if not isinstance(mentioned_raw, list):
            raise ValueError("comment.mentioned_actors must be a list when provided")
        mentioned_actors = []
        seen: set[str] = set()
        for idx, row in enumerate(mentioned_raw):
            actor = _normalize_actor(row, f"comment.mentioned_actors[{idx}]")
            actor_id = actor["actor_id"]
            if actor_id in seen:
                continue
            seen.add(actor_id)
            mentioned_actors.append(actor)

    created_at = _require_non_empty_text(comment.get("created_at"), "comment.created_at")

    return {
        "id": comment_id,
        "track_id": track_id,
        "thread_id": thread_id,
        "by_actor": by_actor,
        "content": content,
        "reply_to": reply_to,
        "mentioned_actors": mentioned_actors,
        "status": status,
        "created_at": created_at,
        "resolved_by_actor": resolved_by_actor,
        "resolved_at": resolved_at,
        "resolution_summary": resolution_summary,
    }


def _read_comment_file(path: Path) -> dict[str, Any]:
    return validate_track_comment(runtime_files.read_json_object(path))


def list_track_comments() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if runtime_files.TRACK_COMMENTS_DIR.is_dir():
        for path in runtime_files.TRACK_COMMENTS_DIR.glob("*/*.json"):
            rows.append(_read_comment_file(path))
    rows.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))
    return rows


def comments_for_track(track_id: str) -> list[dict[str, Any]]:
    runtime_files.require_id(track_id, "track_id")
    rows: list[dict[str, Any]] = []
    track_dir = _track_comment_dir(track_id)
    if track_dir.is_dir():
        for path in track_dir.glob("*.json"):
            rows.append(_read_comment_file(path))
    rows.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))
    return rows


def comments_for_track_thread(track_id: str, thread_id: str) -> list[dict[str, Any]]:
    normalized_thread_id = runtime_files.require_id(thread_id, "thread_id")
    rows = [row for row in comments_for_track(track_id) if row.get("thread_id") == normalized_thread_id]
    rows.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))
    return rows


def get_track_comment(track_id: str, comment_id: str) -> dict[str, Any] | None:
    path = track_comment_file(track_id, comment_id)
    if not path.exists():
        return None
    return _read_comment_file(path)


def _find_track_comment(comment_id: str) -> dict[str, Any] | None:
    normalized_comment_id = runtime_files.require_id(comment_id, "comment_id")
    for row in list_track_comments():
        if row.get("id") == normalized_comment_id:
            return row
    return None


def save_track_comment(comment: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_track_comment(comment)
    runtime_files.require_runtime_workspace_write_root()
    runtime_files.write_json_object(
        track_comment_file(str(normalized["track_id"]), str(normalized["id"])),
        normalized,
    )
    return normalized


def _normalize_mentioned_actors(mentioned_actors: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    if mentioned_actors is None:
        return []
    if not isinstance(mentioned_actors, list):
        raise ValueError("mentioned_actors must be a list when provided")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for idx, row in enumerate(mentioned_actors):
        actor = _normalize_actor(row, f"mentioned_actors[{idx}]")
        actor_id = actor["actor_id"]
        if actor_id in seen:
            continue
        seen.add(actor_id)
        normalized.append(actor)
    return normalized


def create_track_comment(
    *,
    track_id: str,
    by_actor: dict[str, Any],
    content: str,
    reply_to: str | None = None,
    mentioned_actors: list[dict[str, Any]] | None = None,
    thread_id: str | None = None,
    status: str = "open",
) -> dict[str, Any]:
    normalized_track_id = runtime_files.require_id(track_id, "track_id")
    author = _normalize_actor(by_actor, "by_actor")
    content_text = _require_non_empty_text(content, "content")
    if reply_to is not None:
        runtime_files.require_id(reply_to, "reply_to")
    if thread_id is not None:
        runtime_files.require_id(thread_id, "thread_id")
    if status not in _COMMENT_STATUSES:
        raise ValueError("status must be one of open|resolved")

    comment_id = f"comment-{uuid.uuid4().hex[:12]}"
    runtime_files.require_id(comment_id, "comment id")
    return save_track_comment(
        {
            "id": comment_id,
            "track_id": normalized_track_id,
            "thread_id": thread_id or comment_id,
            "by_actor": author,
            "content": content_text,
            "reply_to": reply_to,
            "mentioned_actors": _normalize_mentioned_actors(mentioned_actors),
            "status": status,
            "created_at": runtime_files.now_iso(),
            "resolved_by_actor": None,
            "resolved_at": None,
            "resolution_summary": None,
        }
    )


def reply_to_track_comment(
    *,
    track_id: str,
    reply_to: str,
    by_actor: dict[str, Any],
    content: str,
    mentioned_actors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_track_id = runtime_files.require_id(track_id, "track_id")
    normalized_reply_to = runtime_files.require_id(reply_to, "reply_to")
    parent = _find_track_comment(normalized_reply_to)
    if parent is None:
        raise ValueError(f"reply_to comment not found: {normalized_reply_to}")
    if parent.get("track_id") != normalized_track_id:
        raise ValueError(f"reply_to comment '{normalized_reply_to}' belongs to a different track")
    parent_thread_id = _require_non_empty_text(parent.get("thread_id"), "comment.thread_id")
    return create_track_comment(
        track_id=normalized_track_id,
        by_actor=by_actor,
        content=content,
        reply_to=normalized_reply_to,
        mentioned_actors=mentioned_actors,
        thread_id=parent_thread_id,
    )


def resolve_track_comment_thread(
    *,
    track_id: str,
    comment_id: str,
    resolved_by_actor: dict[str, Any],
    resolution_summary: str,
) -> list[dict[str, Any]]:
    normalized_track_id = runtime_files.require_id(track_id, "track_id")
    normalized_comment_id = runtime_files.require_id(comment_id, "comment_id")
    normalized_resolved_by_actor = _normalize_actor(resolved_by_actor, "resolved_by_actor")
    normalized_summary = _require_non_empty_text(resolution_summary, "resolution_summary")

    seed = get_track_comment(normalized_track_id, normalized_comment_id)
    if seed is None:
        other = _find_track_comment(normalized_comment_id)
        if other is not None:
            raise ValueError(f"comment '{normalized_comment_id}' belongs to a different track")
        raise ValueError(f"comment not found: {normalized_comment_id}")
    thread_id = _require_non_empty_text(seed.get("thread_id"), "comment.thread_id")
    thread_rows = comments_for_track_thread(normalized_track_id, thread_id)
    if not thread_rows:
        raise ValueError(f"comment thread not found: {thread_id}")
    if all(row.get("status") == "resolved" for row in thread_rows):
        raise ValueError(f"comment thread '{thread_id}' is already resolved")

    now = runtime_files.now_iso()
    normalized_updates: list[dict[str, Any]] = []
    for row in thread_rows:
        updated = dict(row)
        updated["status"] = "resolved"
        updated["resolved_by_actor"] = normalized_resolved_by_actor
        updated["resolved_at"] = now
        updated["resolution_summary"] = normalized_summary
        normalized_updates.append(validate_track_comment(updated))

    runtime_files.require_runtime_workspace_write_root()
    for row in normalized_updates:
        runtime_files.write_json_object(
            track_comment_file(str(row["track_id"]), str(row["id"])),
            row,
        )
    normalized_updates.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))
    return normalized_updates
