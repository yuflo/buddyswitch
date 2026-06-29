#!/usr/bin/env python3
"""Track comment attention and prompt rules."""

from __future__ import annotations

from typing import Any

from env.repos import runtime_files
from env.tool_runtime.actor_profile import ActorAddress


def _actor_payload(value: ActorAddress | dict[str, Any], field: str) -> dict[str, str]:
    try:
        if isinstance(value, ActorAddress):
            return value.to_payload()
        return ActorAddress.from_payload(value).to_payload()
    except Exception as exc:
        raise ValueError(f"{field} must be an ActorAddress payload: {exc}") from exc


def _same_actor(left: dict[str, str], right: dict[str, str]) -> bool:
    return left.get("actor_id") == right.get("actor_id") and left.get("role_id") == right.get("role_id")


def _identity_id(value: Any, field: str) -> str:
    if isinstance(value, str) and value.strip():
        return runtime_files.require_id(value.strip(), field)
    return _actor_payload(value, field)["actor_id"]


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
        comment.get("by_identity_id", comment.get("by_actor")),
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

    mentions = comment.get("mentioned_identity_ids", comment.get("mentioned_actors")) or []
    if not isinstance(mentions, list):
        raise ValueError("comment.mentioned_identity_ids must be a list")
    for index, row in enumerate(mentions):
        add_target(row, f"comment.mentioned_identity_ids[{index}]")

    if isinstance(reply_to_comment, dict):
        add_target(
            reply_to_comment.get("by_identity_id", reply_to_comment.get("by_actor")),
            "reply_to_comment.by_identity_id",
        )

    return targets


def target_is_intended_recipient(
    target_actor_address: ActorAddress | dict[str, Any],
    comment: dict[str, Any],
    *,
    reply_to_comment: dict[str, Any] | None = None,
    identity_routes: dict[str, dict[str, str]] | None = None,
) -> bool:
    target = _actor_payload(target_actor_address, "target_actor_address")
    return any(
        _same_actor(target, row)
        for row in track_comment_targets(
            comment,
            reply_to_comment=reply_to_comment,
            identity_routes=identity_routes,
        )
    )
