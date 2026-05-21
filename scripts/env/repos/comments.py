#!/usr/bin/env python3
"""Comment repository helpers backed by runtime object files."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from . import runtime_files

_TARGET_TYPES = {"track", "artifact", "artifact_section"}
_COMMENT_STATUSES = {"open", "resolved"}
_FORBIDDEN_COMMENT_FIELDS = {"resolved", "task_id", "edit_history", "attachment"}


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _comment_file(comment_id: str) -> Path:
    return runtime_files.COMMENTS_DIR / f"{runtime_files.require_id(comment_id, 'comment id')}.json"


def _validate_comment(comment: dict[str, Any]) -> dict[str, Any]:
    forbidden = sorted(key for key in comment if key in _FORBIDDEN_COMMENT_FIELDS)
    if forbidden:
        raise ValueError(f"unsupported comment fields: {', '.join(forbidden)}")

    comment_id = runtime_files.require_id(comment.get("id", ""), "comment.id")
    target_type = comment.get("target_type")
    if target_type not in _TARGET_TYPES:
        raise ValueError("comment.target_type must be one of 'track'|'artifact'|'artifact_section'")
    target_id = runtime_files.require_id(comment.get("target_id"), "comment.target_id")
    by_buddy = _require_non_empty_text(comment.get("by_buddy"), "comment.by_buddy")
    content = _require_non_empty_text(comment.get("content"), "comment.content")

    thread_id_raw = comment.get("thread_id")
    if thread_id_raw is None:
        thread_id = comment_id
    else:
        thread_id = runtime_files.require_id(_require_non_empty_text(thread_id_raw, "comment.thread_id"), "comment.thread_id")

    status = _require_non_empty_text(comment.get("status", "open"), "comment.status")
    if status not in _COMMENT_STATUSES:
        raise ValueError("comment.status must be one of open|resolved")

    resolved_by = comment.get("resolved_by")
    resolved_at = comment.get("resolved_at")
    resolution_summary = comment.get("resolution_summary")
    if status == "resolved":
        resolved_by = _require_non_empty_text(resolved_by, "comment.resolved_by")
        resolved_at = _require_non_empty_text(resolved_at, "comment.resolved_at")
        resolution_summary = _require_non_empty_text(resolution_summary, "comment.resolution_summary")
    else:
        resolved_by = None
        resolved_at = None
        resolution_summary = None

    mentions_raw = comment.get("mentions", [])
    if mentions_raw is None:
        mentions: list[str] = []
    else:
        if not isinstance(mentions_raw, list):
            raise ValueError("comment.mentions must be a list when provided")
        mentions = []
        seen: set[str] = set()
        for idx, row in enumerate(mentions_raw):
            buddy = _require_non_empty_text(row, f"comment.mentions[{idx}]")
            if buddy in seen:
                continue
            seen.add(buddy)
            mentions.append(buddy)

    anchor = comment.get("anchor")
    if anchor is not None:
        anchor = _require_non_empty_text(anchor, "comment.anchor")

    artifact_revision_id = comment.get("artifact_revision_id")
    if artifact_revision_id is not None:
        artifact_revision_id = runtime_files.require_id(
            _require_non_empty_text(artifact_revision_id, "comment.artifact_revision_id"),
            "comment.artifact_revision_id",
        )

    reply_to = comment.get("reply_to")
    if reply_to is not None:
        reply_to = runtime_files.require_id(reply_to, "comment.reply_to")

    created_at = _require_non_empty_text(comment.get("created_at"), "comment.created_at")

    return {
        "id": comment_id,
        "target_type": target_type,
        "target_id": target_id,
        "by_buddy": by_buddy,
        "content": content,
        "thread_id": thread_id,
        "status": status,
        "mentions": mentions,
        "anchor": anchor,
        "artifact_revision_id": artifact_revision_id,
        "reply_to": reply_to,
        "created_at": created_at,
        "resolved_by": resolved_by,
        "resolved_at": resolved_at,
        "resolution_summary": resolution_summary,
    }


def list_comments() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if runtime_files.COMMENTS_DIR.is_dir():
        for path in runtime_files.COMMENTS_DIR.glob("*.json"):
            rows.append(_validate_comment(runtime_files.read_json_object(path)))
    rows.sort(key=lambda row: (row.get("created_at", ""), row["id"]))
    return rows


def get_comment(comment_id: str) -> dict[str, Any] | None:
    path = _comment_file(comment_id)
    if not path.exists():
        return None
    return _validate_comment(runtime_files.read_json_object(path))


def save_comment(comment: dict[str, Any]) -> dict[str, Any]:
    normalized = _validate_comment(comment)
    runtime_files.require_runtime_workspace_write_root()
    runtime_files.COMMENTS_DIR.mkdir(parents=True, exist_ok=True)
    runtime_files.write_json_object(_comment_file(normalized["id"]), normalized)
    return normalized


def create_comment(
    *,
    target_type: str,
    target_id: str,
    by_buddy: str,
    content: str,
    reply_to: str | None = None,
    mentions: list[str] | None = None,
    thread_id: str | None = None,
    status: str = "open",
    anchor: str | None = None,
    artifact_revision_id: str | None = None,
) -> dict[str, Any]:
    if target_type not in _TARGET_TYPES:
        raise ValueError("target_type must be one of 'track'|'artifact'|'artifact_section'")
    runtime_files.require_id(target_id, "target_id")
    author = _require_non_empty_text(by_buddy, "by_buddy")
    content_text = _require_non_empty_text(content, "content")
    if reply_to is not None:
        runtime_files.require_id(reply_to, "reply_to")
    if thread_id is not None:
        runtime_files.require_id(thread_id, "thread_id")
    if status not in _COMMENT_STATUSES:
        raise ValueError("status must be one of open|resolved")
    if anchor is not None and (not isinstance(anchor, str) or not anchor.strip()):
        raise ValueError("anchor must be a non-empty string when provided")
    if artifact_revision_id is not None:
        runtime_files.require_id(artifact_revision_id, "artifact_revision_id")
    normalized_mentions: list[str] = []
    if mentions is not None:
        if not isinstance(mentions, list):
            raise ValueError("mentions must be a list when provided")
        seen_mentions: set[str] = set()
        for idx, row in enumerate(mentions):
            buddy = _require_non_empty_text(row, f"mentions[{idx}]")
            if buddy in seen_mentions:
                continue
            seen_mentions.add(buddy)
            normalized_mentions.append(buddy)

    comment_id = f"comment-{uuid.uuid4().hex[:12]}"
    runtime_files.require_id(comment_id, "comment id")
    return save_comment(
        {
            "id": comment_id,
            "target_type": target_type,
            "target_id": target_id,
            "by_buddy": author,
            "content": content_text,
            "thread_id": thread_id or comment_id,
            "status": status,
            "mentions": normalized_mentions,
            "anchor": anchor.strip() if isinstance(anchor, str) else None,
            "artifact_revision_id": artifact_revision_id,
            "reply_to": reply_to,
            "created_at": runtime_files.now_iso(),
            "resolved_by": None,
            "resolved_at": None,
            "resolution_summary": None,
        }
    )


def comments_for_target(target_type: str, target_id: str) -> list[dict[str, Any]]:
    if target_type not in _TARGET_TYPES:
        raise ValueError("target_type must be one of 'track'|'artifact'|'artifact_section'")
    runtime_files.require_id(target_id, "target_id")

    matched: list[dict[str, Any]] = []
    for row in list_comments():
        row_type = row.get("target_type")
        row_target_id = row.get("target_id")
        if row_target_id != target_id:
            continue
        if row_type == target_type:
            matched.append(row)
            continue
        if target_type == "artifact" and row_type == "artifact_section":
            matched.append(row)
    matched.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))
    return matched


def resolve_thread(*, comment_id: str, resolved_by: str, resolution_summary: str) -> list[dict[str, Any]]:
    normalized_comment_id = runtime_files.require_id(comment_id, "comment_id")
    normalized_resolved_by = _require_non_empty_text(resolved_by, "resolved_by")
    normalized_summary = _require_non_empty_text(resolution_summary, "resolution_summary")

    seed = get_comment(normalized_comment_id)
    if seed is None:
        raise ValueError(f"comment not found: {normalized_comment_id}")
    thread_id = _require_non_empty_text(seed.get("thread_id"), "comment.thread_id")

    thread_rows = [row for row in list_comments() if row.get("thread_id") == thread_id]
    if not thread_rows:
        raise ValueError(f"comment thread not found: {thread_id}")
    if all(row.get("status") == "resolved" for row in thread_rows):
        raise ValueError(f"comment thread '{thread_id}' is already resolved")

    now = runtime_files.now_iso()
    normalized_updates: list[dict[str, Any]] = []
    for row in thread_rows:
        updated_row = dict(row)
        updated_row["status"] = "resolved"
        updated_row["resolved_by"] = normalized_resolved_by
        updated_row["resolved_at"] = now
        updated_row["resolution_summary"] = normalized_summary
        normalized_updates.append(_validate_comment(updated_row))

    runtime_files.require_runtime_workspace_write_root()
    runtime_files.COMMENTS_DIR.mkdir(parents=True, exist_ok=True)
    for row in normalized_updates:
        runtime_files.write_json_object(_comment_file(str(row["id"])), row)
    normalized_updates.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))
    return normalized_updates
