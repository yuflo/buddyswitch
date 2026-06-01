#!/usr/bin/env python3
"""Comment target payload parsing and readability checks."""

from __future__ import annotations

from typing import Any, Mapping

from env.domain import artifact_visibility as artifact_visibility_domain
from env.repos import artifacts as artifact_repo

_TARGET_TYPES = {"track", "artifact", "artifact_section"}


class CommentTargetPayloadError(ValueError):
    def __init__(self, message: str, *, correctable_fields: list[str] | None = None) -> None:
        super().__init__(message)
        self.correctable_fields = correctable_fields


class CommentTargetScopeError(ValueError):
    def __init__(
        self,
        *,
        message: str,
        permission_boundary: str,
        code: str = "E_COMMENT_TARGET_SCOPE",
        retryable: bool = False,
        correctable_fields: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.permission_boundary = permission_boundary
        self.code = code
        self.retryable = retryable
        self.correctable_fields = correctable_fields


def normalize_target(args: Mapping[str, Any]) -> tuple[str, str]:
    target_type = args.get("target_type")
    if not isinstance(target_type, str) or not target_type.strip():
        raise CommentTargetPayloadError("target_type is required", correctable_fields=["target_type"])
    normalized_target_type = target_type.strip()
    if normalized_target_type not in _TARGET_TYPES:
        raise CommentTargetPayloadError(
            f"unsupported target_type: {normalized_target_type}; must be track/artifact/artifact_section",
            correctable_fields=["target_type"],
        )

    target_id = args.get("target_id")
    if not isinstance(target_id, str) or not target_id.strip():
        raise CommentTargetPayloadError("target_id is required", correctable_fields=["target_id"])
    return normalized_target_type, target_id.strip()


def assert_target_readable(
    *,
    target_type: str,
    target_id: str,
    active_role: str,
    active_actor: dict[str, Any],
    action: str,
) -> dict[str, Any]:
    if target_type == "track":
        track_decision = artifact_visibility_domain.assert_track_readable(target_id, active_role=active_role, action=action)
        if not bool(track_decision.get("ok")):
            message = str(track_decision.get("message", f"track not found: {target_id}"))
            boundary = str(track_decision.get("permission_boundary", "track.lifecycle_status"))
            code = str(track_decision.get("code", "E_COMMENT_TARGET_SCOPE"))
            if boundary == "request-payload":
                raise CommentTargetPayloadError(message, correctable_fields=["target_id"])
            raise CommentTargetScopeError(
                message=message,
                permission_boundary=boundary,
                code=code,
                retryable=False,
                correctable_fields=["target_id"],
            )
        return track_decision["track"]

    artifact = artifact_repo.get_artifact(target_id)
    if artifact is None:
        raise CommentTargetPayloadError(f"artifact not found: {target_id}", correctable_fields=["target_id"])

    decision = artifact_visibility_domain.artifact_read_decision(artifact, active_actor)
    if not bool(decision.get("allowed")):
        raise CommentTargetScopeError(
            message=str(decision.get("why", "artifact read denied")),
            permission_boundary=str(decision.get("permission_boundary", "artifact.read_scope")),
            code="E_COMMENT_TARGET_SCOPE",
            retryable=False,
            correctable_fields=["target_id"],
        )

    if artifact.get("status") == "archived":
        raise CommentTargetScopeError(
            message=f"artifact '{target_id}' is archived and does not accept new comments",
            permission_boundary="artifact.status",
            code="E_COMMENT_TARGET_SCOPE",
            retryable=False,
            correctable_fields=["target_id"],
        )

    return artifact


def artifact_revision_chain_ids(artifact_id: str) -> set[str]:
    current = artifact_repo.get_artifact(artifact_id)
    if current is None:
        return set()
    by_id = {
        row.get("id"): row
        for row in artifact_repo.list_artifacts()
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    ids: set[str] = set()
    visited: set[str] = set()
    while isinstance(current, dict):
        current_id = current.get("id")
        if not isinstance(current_id, str) or not current_id or current_id in visited:
            break
        ids.add(current_id)
        visited.add(current_id)
        supersedes_id = current.get("supersedes_artifact_id")
        if not isinstance(supersedes_id, str) or not supersedes_id:
            break
        previous = by_id.get(supersedes_id)
        if not isinstance(previous, dict):
            previous = artifact_repo.get_artifact(supersedes_id)
        if not isinstance(previous, dict):
            break
        current = previous
    return ids
