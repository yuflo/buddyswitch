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

import daemon_contracts  # noqa: E402
import task_sys_ingress  # noqa: E402
import task_sys_daemon_adapter  # noqa: E402
from env.domain import track_comments as track_comment_rules  # noqa: E402
from env.repos import runtime_files  # noqa: E402
from env.repos import track_comments as track_comment_repo  # noqa: E402
from env.repos import tracks as track_repo  # noqa: E402


def _context_identity_route(context: Any) -> dict[str, str]:
    return {
        "identity_id": runtime_files.require_id(getattr(context, "actor_id", ""), "context.actor_id"),
        "role_id": runtime_files.require_id(getattr(context, "role", ""), "context.role"),
    }


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
            return daemon_contracts.HandlerResult.ignored()
        del runtime
        return self._handle_track_comment_added(context, trigger)

    def _payload(self, trigger: Any) -> dict[str, str]:
        payload = getattr(trigger, "payload", None)
        if not isinstance(payload, dict):
            raise ValueError("track comment trigger payload must be an object")
        return {
            "track_id": runtime_files.require_id(payload.get("track_id"), "track_id"),
            "comment_id": runtime_files.require_id(payload.get("comment_id"), "comment_id"),
            "thread_id": runtime_files.require_id(payload.get("thread_id"), "thread_id"),
        }

    def _ensure_target_identity(self, context: Any, trigger: Any) -> dict[str, str]:
        local_route = _context_identity_route(context)
        target_route = {
            "identity_id": runtime_files.require_id(getattr(trigger, "target_identity_id", ""), "trigger.target_identity_id"),
            "role_id": runtime_files.require_id(getattr(trigger, "target_role_id", ""), "trigger.target_role_id"),
        }
        if target_route != local_route:
            raise PermissionError("wrong target identity for Track comment trigger")
        return target_route

    def _source_identity_route(self, trigger: Any) -> dict[str, str]:
        source_context = getattr(trigger, "source_context", None)
        if not isinstance(source_context, dict):
            raise ValueError("track comment trigger source_context must be an object")
        return {
            "identity_id": runtime_files.require_id(source_context.get("source_identity_id"), "source_context.source_identity_id"),
            "role_id": runtime_files.require_id(source_context.get("source_role_id"), "source_context.source_role_id"),
        }

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

    def _handle_track_comment_added(self, context: Any, trigger: Any) -> daemon_contracts.HandlerResult:
        try:
            target_identity = self._ensure_target_identity(context, trigger)
            source_identity = self._source_identity_route(trigger)
            payload = self._payload(trigger)
            comment = self._comment(**payload)
            reply_to_comment = self._reply_to_comment(comment)
            if not track_comment_rules.target_is_intended_recipient(
                target_identity,
                comment,
                reply_to_comment=reply_to_comment,
                identity_routes={target_identity["identity_id"]: target_identity},
            ):
                raise PermissionError("target identity is not an intended recipient for this Track comment")
            self._ensure_track_readable(payload["track_id"])

            result = task_sys_ingress.ingest_track_comment(
                actor_id=target_identity["identity_id"],
                role_id=target_identity["role_id"],
                track_id=payload["track_id"],
                comment_id=payload["comment_id"],
                thread_id=payload["thread_id"],
                source_identity_id=source_identity["identity_id"],
                source_role_id=source_identity["role_id"],
            )
            task_sys_daemon_adapter.execute_instruction(context, result["instruction"])
            return daemon_contracts.HandlerResult.handled()
        except Exception as exc:
            return daemon_contracts.HandlerResult.failed(str(exc))


if __name__ == "__main__":
    raise SystemExit("track_comment_added_handler is not a standalone command")
