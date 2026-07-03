#!/usr/bin/env python3
"""Track comment attention and prompt rules."""

from __future__ import annotations

from typing import Any

from env.domain.identity import IdentityRef
from env.repos import runtime_files


def _route_payload(value: dict[str, Any], field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an identity route payload")
    identity_id = runtime_files.require_id(str(value.get("identity_id") or ""), f"{field}.identity_id")
    role_id = runtime_files.require_id(str(value.get("role_id") or ""), f"{field}.role_id")
    return {"identity_id": identity_id, "role_id": role_id}


def _same_identity_route(left: dict[str, str], right: dict[str, str]) -> bool:
    return left.get("identity_id") == right.get("identity_id") and left.get("role_id") == right.get("role_id")


def _identity_id(value: Any, field: str) -> str:
    if isinstance(value, str) and value.strip():
        return runtime_files.require_id(value.strip(), field)
    if isinstance(value, dict):
        if isinstance(value.get("identity"), dict):
            return IdentityRef.from_payload(value["identity"]).id
        if isinstance(value.get("id"), str) and isinstance(value.get("type"), str):
            return IdentityRef.from_payload(value).id
    raise ValueError(f"{field} must be an identity id or identity payload")


def track_comment_added_payload(comment: dict[str, Any]) -> dict[str, str]:
    return {
        "track_id": runtime_files.require_id(comment.get("track_id"), "comment.track_id"),
        "comment_id": runtime_files.require_id(comment.get("id"), "comment.id"),
        "thread_id": runtime_files.require_id(comment.get("thread_id"), "comment.thread_id"),
    }


def track_comment_targets(
    comment: dict[str, Any],
    *,
    reply_to_comment: dict[str, Any] | None = None,
    identity_routes: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    author_identity_id = _identity_id(
        comment.get("by_identity_id"),
        "comment.by_identity_id",
    )
    targets: list[dict[str, str]] = []
    seen: set[str] = set()

    def add_target(value: Any, field: str) -> None:
        identity_id = _identity_id(value, field)
        if identity_id == author_identity_id:
            return
        if identity_id in seen:
            return
        seen.add(identity_id)
        route = identity_routes.get(identity_id) if isinstance(identity_routes, dict) else None
        if isinstance(route, dict):
            targets.append(dict(route))

    mentions = comment.get("mentioned_identity_ids") or []
    if not isinstance(mentions, list):
        raise ValueError("comment.mentioned_identity_ids must be a list")
    for index, row in enumerate(mentions):
        add_target(row, f"comment.mentioned_identity_ids[{index}]")

    if isinstance(reply_to_comment, dict):
        add_target(
            reply_to_comment.get("by_identity_id"),
            "reply_to_comment.by_identity_id",
        )

    return targets


def target_is_intended_recipient(
    target_identity_route: dict[str, Any],
    comment: dict[str, Any],
    *,
    reply_to_comment: dict[str, Any] | None = None,
    identity_routes: dict[str, dict[str, str]] | None = None,
) -> bool:
    target = _route_payload(target_identity_route, "target_identity_route")
    return any(
        _same_identity_route(target, row)
        for row in track_comment_targets(
            comment,
            reply_to_comment=reply_to_comment,
            identity_routes=identity_routes,
        )
    )
