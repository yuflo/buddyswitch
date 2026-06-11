#!/usr/bin/env python3
"""Track comment attention and prompt rules."""

from __future__ import annotations

import json
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
) -> list[dict[str, str]]:
    author = _actor_payload(comment.get("by_actor"), "comment.by_actor")
    targets: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_target(value: Any, field: str) -> None:
        actor = _actor_payload(value, field)
        if _same_actor(actor, author):
            return
        key = (actor["actor_id"], actor["role_id"])
        if key in seen:
            return
        seen.add(key)
        targets.append(actor)

    mentions = comment.get("mentioned_actors") or []
    if not isinstance(mentions, list):
        raise ValueError("comment.mentioned_actors must be a list")
    for index, row in enumerate(mentions):
        add_target(row, f"comment.mentioned_actors[{index}]")

    if isinstance(reply_to_comment, dict):
        add_target(reply_to_comment.get("by_actor"), "reply_to_comment.by_actor")

    return targets


def target_is_intended_recipient(
    target_actor_address: ActorAddress | dict[str, Any],
    comment: dict[str, Any],
    *,
    reply_to_comment: dict[str, Any] | None = None,
) -> bool:
    target = _actor_payload(target_actor_address, "target_actor_address")
    return any(_same_actor(target, row) for row in track_comment_targets(comment, reply_to_comment=reply_to_comment))


def _format_actor(value: ActorAddress | dict[str, Any]) -> str:
    return json.dumps(_actor_payload(value, "actor_address"), ensure_ascii=True, sort_keys=True)


def render_parent_track_comment_prompt(
    *,
    track_id: str,
    comment_id: str,
    thread_id: str,
    source_actor_address: ActorAddress | dict[str, Any],
    target_actor_address: ActorAddress | dict[str, Any],
) -> str:
    return (
        "[TRACK COMMENT ATTENTION]\n\n"
        f"Track id: {track_id}\n"
        f"Comment id: {comment_id}\n"
        f"Thread id: {thread_id}\n"
        f"From: {_format_actor(source_actor_address)}\n"
        f"To: {_format_actor(target_actor_address)}\n\n"
        "One exact Track comment needs this actor's attention.\n\n"
        "Process this exact Track comment from Track source truth. Do not assume a reply or thread resolution is required.\n\n"
        "Steps:\n"
        f"1. Call track.open(track_id=\"{track_id}\") to inspect the Track page.\n"
        f"2. Call track.list_comments(track_id=\"{track_id}\", status=\"all\") and find comment \"{comment_id}\" in thread \"{thread_id}\".\n"
        "3. If a reply is useful, call track.add_comment with:\n"
        f"   - track_id = \"{track_id}\"\n"
        "   - content = your reply\n"
        f"   - reply_to = \"{comment_id}\"\n"
        "4. Only if the active actor is the exact Track owner and durable closure is appropriate, call track.resolve_comment_thread with:\n"
        f"   - track_id = \"{track_id}\"\n"
        f"   - comment_id = \"{comment_id}\"\n"
        "   - resolution_summary = the closure summary\n\n"
        "Finish after the Track comment has been handled through Track tools."
    )


def render_side_track_comment_prompt(
    *,
    track_id: str,
    comment_id: str,
    thread_id: str,
    source_actor_address: ActorAddress | dict[str, Any],
    target_actor_address: ActorAddress | dict[str, Any],
) -> str:
    return (
        "[TRACK COMMENT TRIAGE]\n\n"
        f"Track id: {track_id}\n"
        f"Comment id: {comment_id}\n"
        f"Thread id: {thread_id}\n"
        f"From: {_format_actor(source_actor_address)}\n"
        f"To: {_format_actor(target_actor_address)}\n\n"
        "A Track comment arrived while the main work is busy. Triage this exact comment from Track source truth.\n\n"
        "Steps:\n"
        f"1. Call track.open(track_id=\"{track_id}\") to inspect current Track state.\n"
        f"2. Call track.list_comments(track_id=\"{track_id}\", status=\"all\") and find comment \"{comment_id}\" in thread \"{thread_id}\".\n"
        "3. If quick handling is enough, call track.add_comment with:\n"
        f"   - track_id = \"{track_id}\"\n"
        "   - content = your reply\n"
        f"   - reply_to = \"{comment_id}\"\n"
        "4. Only if the active actor is the exact Track owner and the thread is ready for durable closure, call track.resolve_comment_thread with:\n"
        f"   - track_id = \"{track_id}\"\n"
        f"   - comment_id = \"{comment_id}\"\n"
        "   - resolution_summary = the closure summary\n\n"
        "Use only Track tools for this comment."
    )
