#!/usr/bin/env python3
"""Daemon trigger handler for Track comment attention."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import daemon_core  # noqa: E402
from env.domain import track_comments as track_comment_rules  # noqa: E402
from env.repos import runtime_files  # noqa: E402
from env.repos import track_comments as track_comment_repo  # noqa: E402
from env.repos import tracks as track_repo  # noqa: E402
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402


def _context_actor_address(context: Any) -> ActorAddress:
    value = getattr(context, "actor_address", None)
    if isinstance(value, ActorAddress):
        return value
    return daemon_core.actor_address_for_context(context)


class TrackCommentAddedHandler:
    name = "track_comment_added"

    def handles(self, trigger: Any) -> bool:
        return getattr(trigger, "type", None) == "track.comment.added"

    def handle(
        self,
        context: Any,
        state: Any,
        runtime: Any,
        trigger: Any,
    ) -> Any:
        del state
        if getattr(trigger, "type", None) != "track.comment.added":
            return daemon_core.HandlerResult.ignored()
        return self._handle_track_comment_added(context, runtime, trigger)

    def _payload(self, trigger: Any) -> dict[str, str]:
        payload = getattr(trigger, "payload", None)
        if not isinstance(payload, dict):
            raise ValueError("track comment trigger payload must be an object")
        return {
            "track_id": runtime_files.require_id(payload.get("track_id"), "track_id"),
            "comment_id": runtime_files.require_id(payload.get("comment_id"), "comment_id"),
            "thread_id": runtime_files.require_id(payload.get("thread_id"), "thread_id"),
        }

    def _ensure_target_actor(self, context: Any, trigger: Any) -> ActorAddress:
        local_actor = _context_actor_address(context)
        target_actor = ActorAddress.from_payload(getattr(trigger, "target_actor_address", None))
        if target_actor != local_actor:
            raise PermissionError("wrong target actor for Track comment trigger")
        return target_actor

    def _source_actor_address(self, trigger: Any) -> ActorAddress:
        source_context = getattr(trigger, "source_context", None)
        if not isinstance(source_context, dict):
            raise ValueError("track comment trigger source_context must be an object")
        return ActorAddress.from_payload(source_context.get("source_actor_address"))

    def _comment(self, *, track_id: str, comment_id: str, thread_id: str) -> dict[str, Any]:
        comment = track_comment_repo.get_track_comment(track_id, comment_id)
        if comment is None:
            raise ValueError(f"comment not found for track '{track_id}': {comment_id}")
        if comment.get("track_id") != track_id:
            raise ValueError("Track comment row track_id does not match trigger payload")
        if comment.get("thread_id") != thread_id:
            raise ValueError("Track comment row thread_id does not match trigger payload")
        return comment

    def _reply_to_comment(self, comment: dict[str, Any]) -> dict[str, Any] | None:
        reply_to = comment.get("reply_to")
        if reply_to is None:
            return None
        parent = track_comment_repo.get_track_comment(str(comment["track_id"]), str(reply_to))
        if parent is None:
            raise ValueError(f"reply_to comment not found: {reply_to}")
        return parent

    def _ensure_track_readable(self, track_id: str) -> None:
        track = track_repo.get_track(track_id)
        if track is None:
            raise ValueError(f"track not found: {track_id}")
        if track.get("archived_at") is not None:
            raise PermissionError(f"track '{track_id}' is archived and cannot receive Track comment attention")

    def _handle_track_comment_added(self, context: Any, runtime: Any, trigger: Any) -> daemon_core.HandlerResult:
        try:
            target_actor = self._ensure_target_actor(context, trigger)
            source_actor = self._source_actor_address(trigger)
            payload = self._payload(trigger)
            comment = self._comment(**payload)
            reply_to_comment = self._reply_to_comment(comment)
            if not track_comment_rules.target_is_intended_recipient(
                target_actor,
                comment,
                reply_to_comment=reply_to_comment,
            ):
                raise PermissionError("target actor is not an intended recipient for this Track comment")
            self._ensure_track_readable(payload["track_id"])

            activity = runtime.parent_activity()
            status = activity.get("status") if isinstance(activity, dict) else None
            prompt_args = {
                "track_id": payload["track_id"],
                "comment_id": payload["comment_id"],
                "thread_id": payload["thread_id"],
                "source_actor_address": source_actor,
                "target_actor_address": target_actor,
            }
            if status == "idle":
                runtime.submit_parent_prompt(
                    track_comment_rules.render_parent_track_comment_prompt(**prompt_args),
                    handler_name=self.name,
                    origin_id=payload["comment_id"],
                    interrupt_policy="none",
                )
                return daemon_core.HandlerResult.handled()
            if status == "running":
                runtime.submit_side_triage_prompt(
                    track_comment_rules.render_side_track_comment_prompt(**prompt_args),
                    handler_name=self.name,
                    origin_id=payload["comment_id"],
                )
                return daemon_core.HandlerResult.handled()
            error = activity.get("error") if isinstance(activity, dict) else None
            return daemon_core.HandlerResult.failed(str(error or "parent thread activity is unavailable"))
        except Exception as exc:
            return daemon_core.HandlerResult.failed(str(exc))


if __name__ == "__main__":
    raise SystemExit("track_comment_added_handler is not a standalone command")
