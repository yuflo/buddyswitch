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


def _track_comment_header(
    title: str,
    *,
    track_id: str,
    comment_id: str,
    thread_id: str,
    source_actor_address: ActorAddress | dict[str, Any],
    target_actor_address: ActorAddress | dict[str, Any],
) -> str:
    return (
        f"[{title}]\n\n"
        f"Track id: {track_id}\n"
        f"Comment id: {comment_id}\n"
        f"Thread id: {thread_id}\n"
        f"From: {_format_actor(source_actor_address)}\n"
        f"To: {_format_actor(target_actor_address)}"
    )


def _track_comment_runtime_context(*, side: bool = False) -> str:
    if side:
        return (
            "Runtime context:\n"
            "Side triage is for quick Track-thread handling only.\n"
            "A Track comment may still contain a concrete work demand, but side triage should not treat a lightweight acknowledgement as completed work."
        )
    return (
        "Runtime context:\n"
        "A Track comment may be discussion, FYI, review feedback, blocker information, or a concrete work demand.\n"
        "Track tools remain the source of truth for reading and replying to the comment thread.\n"
        "Task tools are only for this actor's private work tracking when the comment assigns durable work."
    )


def _track_comment_parent_work_demand_tips() -> str:
    return (
        "Work-demand guidance:\n"
        "If the exact comment assigns concrete work to this actor, acknowledgement alone is usually not completion.\n"
        "For durable actor work, consider task.current and task.capture/task.select.\n"
        "If the requested work is small enough to complete now, do the smallest substantive work and reply with the result in the Track thread.\n"
        "If the comment is only lightweight discussion, reply through Track tools when useful."
    )


def _track_comment_side_work_demand_tips() -> str:
    return (
        "Work-demand guidance:\n"
        "If the comment is lightweight, handle it through Track tools.\n"
        "If the comment clearly assigns durable work that cannot be completed quickly in side triage, do not present it as done.\n"
        "Leave substantive work for the parent/main path; use a concise Track reply only if it is useful for coordination."
    )


def _track_comment_parent_steps(*, track_id: str, comment_id: str, thread_id: str) -> str:
    return (
        "Steps:\n"
        f"1. Call track.open(track_id=\"{track_id}\") to inspect the Track page.\n"
        f"2. Call track.list_comments(track_id=\"{track_id}\", status=\"all\") and find comment \"{comment_id}\" in thread \"{thread_id}\".\n"
        "3. If the comment contains concrete work that should be tracked, consider task.current and task.capture/task.select.\n"
        "4. If a reply is useful, call track.add_comment with:\n"
        f"   - track_id = \"{track_id}\"\n"
        "   - content = your reply\n"
        f"   - reply_to = \"{comment_id}\"\n"
        "5. Only if the active actor is the exact Track owner and durable closure is appropriate, call track.resolve_comment_thread with:\n"
        f"   - track_id = \"{track_id}\"\n"
        f"   - comment_id = \"{comment_id}\"\n"
        "   - resolution_summary = the closure summary"
    )


def _track_comment_side_steps(*, track_id: str, comment_id: str, thread_id: str) -> str:
    return (
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


def _track_comment_finish(*, side: bool = False) -> str:
    if side:
        return "Finish:\nFinish after quick Track-thread triage is handled."
    return "Finish:\nFinish after the Track comment has been handled through Track tools, and any needed actor task capture has been completed."


def render_parent_track_comment_prompt(
    *,
    track_id: str,
    comment_id: str,
    thread_id: str,
    source_actor_address: ActorAddress | dict[str, Any],
    target_actor_address: ActorAddress | dict[str, Any],
) -> str:
    return "\n\n".join(
        (
            _track_comment_header(
                "TRACK COMMENT ATTENTION",
                track_id=track_id,
                comment_id=comment_id,
                thread_id=thread_id,
                source_actor_address=source_actor_address,
                target_actor_address=target_actor_address,
            ),
            "One exact Track comment needs this actor's attention.",
            "Required action:\nProcess this exact Track comment from Track source truth. Do not assume a reply or thread resolution is required.",
            _track_comment_runtime_context(),
            _track_comment_parent_work_demand_tips(),
            _track_comment_parent_steps(track_id=track_id, comment_id=comment_id, thread_id=thread_id),
            _track_comment_finish(),
        )
    )


def render_side_track_comment_prompt(
    *,
    track_id: str,
    comment_id: str,
    thread_id: str,
    source_actor_address: ActorAddress | dict[str, Any],
    target_actor_address: ActorAddress | dict[str, Any],
) -> str:
    return "\n\n".join(
        (
            _track_comment_header(
                "TRACK COMMENT TRIAGE",
                track_id=track_id,
                comment_id=comment_id,
                thread_id=thread_id,
                source_actor_address=source_actor_address,
                target_actor_address=target_actor_address,
            ),
            "A Track comment arrived while the main work is busy.",
            "Required action:\nTriage this exact comment from Track source truth.",
            _track_comment_runtime_context(side=True),
            _track_comment_side_work_demand_tips(),
            _track_comment_side_steps(track_id=track_id, comment_id=comment_id, thread_id=thread_id),
            _track_comment_finish(side=True),
        )
    )
