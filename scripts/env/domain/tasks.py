#!/usr/bin/env python3
"""Task-domain validation and active-buddy ownership helpers."""

from __future__ import annotations

from typing import Any, Mapping

from env.repos import runtime_files
from env.repos import tasks as task_repo
from env.repos import tracks as track_repo

PUBLICATION_STYLE_FIELDS = {
    "artifact_id",
    "artifact_ids",
    "close_proof",
    "current_artifacts",
    "publish",
    "published_to_track",
    "shared_materials",
    "source_refs",
    "supersedes_artifact_id",
    "target_buddy",
    "template",
    "updates",
    "visibility",
}
VALID_TASK_PRIORITY = task_repo.valid_task_priorities()
ALLOWED_TASK_REF_ID_TYPES = {"track", "artifact", "message", "comment", "request"}
ALLOWED_TASK_REF_TYPES = set(ALLOWED_TASK_REF_ID_TYPES)
_STATUS_VALUES = task_repo.valid_task_statuses()


class TaskPayloadError(ValueError):
    """Raised when task payload fields are invalid."""


class TaskScopeError(PermissionError):
    """Raised when task ownership does not match active buddy scope."""


def publication_style_fields(args: Mapping[str, Any]) -> list[str]:
    return sorted(field for field in args if field in PUBLICATION_STYLE_FIELDS)


def require_task_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TaskPayloadError("task_id is required")
    try:
        return runtime_files.require_id(value.strip(), "task_id")
    except ValueError as exc:
        raise TaskPayloadError(str(exc)) from exc


def require_title(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TaskPayloadError("title is required")
    return value.strip()


def require_summary(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TaskPayloadError("summary must be a string")
    return value


def validate_status(value: Any) -> str:
    if value not in _STATUS_VALUES:
        raise TaskPayloadError(f"status must be one of {', '.join(_STATUS_VALUES)}")
    return str(value)


def optional_status(value: Any) -> str:
    if value is None:
        return "active"
    return validate_status(value)


def normalize_priority(value: Any) -> str:
    if value is None:
        return "normal"
    if not isinstance(value, str) or value not in VALID_TASK_PRIORITY:
        raise TaskPayloadError(f"priority must be one of {', '.join(VALID_TASK_PRIORITY)}")
    return value


def _normalize_ref_label(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TaskPayloadError("ref label must be a string")
    return value


def normalize_refs(value: Any) -> list[dict[str, object]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TaskPayloadError("refs must be a list")
    refs: list[dict[str, object]] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise TaskPayloadError("each ref must be an object")
        ref_type = raw.get("type")
        if ref_type not in ALLOWED_TASK_REF_TYPES:
            raise TaskPayloadError("ref type is not supported")
        normalized: dict[str, object] = {"type": str(ref_type)}
        label = _normalize_ref_label(raw.get("label"))
        if label is not None:
            normalized["label"] = label
        ref_id = raw.get("id")
        if not isinstance(ref_id, str) or not ref_id.strip():
            raise TaskPayloadError("refs require id")
        try:
            normalized["id"] = runtime_files.require_id(ref_id.strip(), "ref.id")
        except ValueError as exc:
            raise TaskPayloadError(str(exc)) from exc
        refs.append(normalized)
    return refs


def optional_track_context(track_id: Any) -> str | None:
    if track_id is None:
        return None
    if not isinstance(track_id, str) or not track_id.strip():
        raise TaskPayloadError("track_id must be a non-empty string or null")
    normalized = track_id.strip()
    try:
        runtime_files.require_id(normalized, "track_id")
    except ValueError as exc:
        raise TaskPayloadError(str(exc)) from exc
    if track_repo.get_track(normalized) is None:
        raise TaskPayloadError(f"track not found: {normalized}")
    return normalized


def optional_track_filter(track_id: Any) -> str | None:
    if track_id is None:
        return None
    if not isinstance(track_id, str) or not track_id.strip():
        raise TaskPayloadError("track_id must be a non-empty string")
    try:
        return runtime_files.require_id(track_id.strip(), "track_id")
    except ValueError as exc:
        raise TaskPayloadError(str(exc)) from exc


def optional_status_filter(value: Any) -> str | None:
    if value is None:
        return None
    return validate_status(value)


def optional_priority_filter(value: Any) -> str | None:
    if value is None:
        return None
    return normalize_priority(value)


def include_archived_flag(value: Any) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise TaskPayloadError("include_archived must be a boolean")
    return value


def normalize_limit(value: Any, *, default: int = 100, maximum: int = 200) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or value < 1:
        raise TaskPayloadError("limit must be a positive integer")
    return min(value, maximum)


def ensure_active_buddy_ownership(*, task: Mapping[str, Any], task_id: str, active_buddy: str) -> None:
    owner = task.get("owner_buddy")
    if owner != active_buddy:
        raise TaskScopeError(f"task '{task_id}' is owned by buddy '{owner}'")


def create_payload(args: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_id": require_task_id(args.get("task_id")),
        "title": require_title(args.get("title")),
        "summary": require_summary(args.get("summary")),
        "status": optional_status(args.get("status")),
        "priority": normalize_priority(args.get("priority")),
        "track_id": optional_track_context(args.get("track_id")),
        "refs": normalize_refs(args.get("refs")),
    }


def update_patch(args: Mapping[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "title" in args:
        patch["title"] = require_title(args.get("title"))
    if "summary" in args:
        patch["summary"] = require_summary(args.get("summary"))
    if "status" in args:
        patch["status"] = validate_status(args.get("status"))
    if "priority" in args:
        patch["priority"] = normalize_priority(args.get("priority"))
    if "track_id" in args:
        patch["track_id"] = optional_track_context(args.get("track_id"))
    if "refs" in args:
        patch["refs"] = normalize_refs(args.get("refs"))
    if not patch:
        raise TaskPayloadError("at least one patch field is required")
    return patch


def history_limit(args: Mapping[str, Any]) -> int:
    return normalize_limit(args.get("limit"), default=50, maximum=200)
