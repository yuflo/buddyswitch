#!/usr/bin/env python3
"""Task-domain validation and active-buddy ownership helpers."""

from __future__ import annotations

from typing import Any, Mapping

from env.repos import tasks as task_repo

_PUBLICATION_STYLE_FIELDS = {
    "artifact_id",
    "artifact_ids",
    "current_artifacts",
    "published_to_track",
    "shared_materials",
    "close_proof",
    "updates",
    "source_refs",
    "body",
    "template",
    "supersedes_artifact_id",
}

_STATUS_VALUES = task_repo.valid_task_statuses()


class TaskPayloadError(ValueError):
    """Raised when task payload fields are invalid."""


class TaskScopeError(PermissionError):
    """Raised when task ownership does not match active buddy scope."""


def publication_style_fields(args: Mapping[str, Any]) -> list[str]:
    return sorted(field for field in args if field in _PUBLICATION_STYLE_FIELDS)


def require_task_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TaskPayloadError("task_id is required")
    return value.strip()


def optional_task_id(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise TaskPayloadError("task_id must be a non-empty string")
    return value.strip()


def require_title(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TaskPayloadError("title is required")
    return value.strip()


def optional_title_patch(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TaskPayloadError("title must be a non-empty string")
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
    return value


def optional_status(value: Any) -> str:
    if value is None:
        return "active"
    return validate_status(value)


def optional_track_context(track_id: Any) -> str | None:
    if track_id is None:
        return None
    if not isinstance(track_id, str):
        raise TaskPayloadError("track_id must be a string or null")
    normalized = track_id.strip()
    if not normalized:
        raise TaskPayloadError("track_id must be a string or null")
    if not task_repo.track_exists(normalized):
        raise TaskPayloadError(f"track not found: {normalized}")
    return normalized


def ensure_active_buddy_ownership(*, task: Mapping[str, Any], task_id: str, active_buddy: str) -> None:
    owner = task.get("buddy")
    if owner != active_buddy:
        raise TaskScopeError(f"task '{task_id}' is owned by buddy '{owner}'")


def update_patch(args: Mapping[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "title" in args:
        patch["title"] = optional_title_patch(args.get("title"))
    if "summary" in args:
        patch["summary"] = require_summary(args.get("summary"))
    if "status" in args:
        patch["status"] = validate_status(args.get("status"))
    if "track_id" in args:
        patch["track_id"] = optional_track_context(args.get("track_id"))
    if not patch:
        raise TaskPayloadError("at least one patch field is required")
    return patch
