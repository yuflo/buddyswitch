#!/usr/bin/env python3
"""Daemon signal handler for message.available."""

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
import daemon_mailbox  # noqa: E402
from env.repos import runtime_files  # noqa: E402
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402


def _context_actor_address(context: Any) -> ActorAddress:
    value = getattr(context, "actor_address", None)
    if isinstance(value, ActorAddress):
        return value
    return daemon_core.actor_address_for_context(context)


class MessageAvailableHandler:
    name = "message_available"

    def handles(self, signal: dict[str, Any]) -> bool:
        return isinstance(signal, dict) and signal.get("type") == "message.available"

    def parent_prompt(self) -> str:
        return (
            "[MESSAGE AVAILABLE]\n"
            "A direct message is available for this actor.\n"
            "Use native `message__list` to read the inbox.\n"
            "Use native `message__conversation` when bidirectional context is needed."
        )

    def side_triage_prompt(self) -> str:
        return (
            "[MESSAGE TRIAGE]\n"
            "A direct message is available for this actor while the parent thread is running.\n"
            "Use native `message__list` to read the inbox.\n"
            "Use native `message__conversation` when bidirectional context is needed.\n"
            "When the message can be handled independently, send the direct reply with native `message__send`.\n"
            "When parent is required because the message conflicts with, interrupts, corrects, or materially affects "
            "the parent work, send the typed parent-required request to the local daemon."
        )

    def handle_signal(
        self,
        context: Any,
        state: Any,
        actions: Any,
        signal: dict[str, Any],
    ) -> daemon_core.HandlerResult:
        if not self.handles(signal):
            return daemon_core.HandlerResult.ignored()
        try:
            normalized = daemon_mailbox.validate_daemon_signal(signal)
            local_actor = _context_actor_address(context)
            target_actor = ActorAddress.from_payload(normalized["target_actor_address"])
            if target_actor != local_actor:
                return daemon_core.HandlerResult.failed("wrong target actor for message.available signal")
            payload = normalized["payload"]
            if not isinstance(payload, dict):
                return daemon_core.HandlerResult.failed("message.available payload must be an object")
            message_id = runtime_files.require_id(payload.get("message_id"), "message_id")
            activity = actions.parent_activity()
            status = activity.get("status") if isinstance(activity, dict) else None
            if status == "idle":
                actions.submit_parent_prompt(
                    self.parent_prompt(),
                    handler_name=self.name,
                    origin_id=message_id,
                )
                return daemon_core.HandlerResult.handled()
            if status == "running":
                actions.start_or_reuse_side_triage(
                    self.side_triage_prompt(),
                    handler_name=self.name,
                    origin_id=message_id,
                )
                return daemon_core.HandlerResult.handled()
            error = activity.get("error") if isinstance(activity, dict) else None
            return daemon_core.HandlerResult.failed(str(error or "parent thread activity is unavailable"))
        except Exception as exc:
            return daemon_core.HandlerResult.failed(str(exc))

    def handle_parent_required(
        self,
        context: Any,
        state: Any,
        actions: Any,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        del context, state
        try:
            if not isinstance(request, dict):
                raise ValueError("parent-required request must be an object")
            message_id = runtime_files.require_id(request.get("message_id"), "message_id")
            side_thread_id = runtime_files.require_id(request.get("side_thread_id"), "side_thread_id")
            actions.require_side_thread(side_thread_id)
            result = actions.interrupt_and_submit_parent_prompt(
                self.parent_prompt(),
                handler_name=self.name,
                origin_id=message_id,
            )
            payload = {
                "status": "handled",
                "side_thread_id": side_thread_id,
            }
            if isinstance(result, dict):
                interrupted_turn_id = result.get("interrupted_turn_id")
                turn_id = result.get("turn_id")
                if isinstance(interrupted_turn_id, str) and interrupted_turn_id:
                    payload["interrupted_turn_id"] = interrupted_turn_id
                if isinstance(turn_id, str) and turn_id:
                    payload["turn_id"] = turn_id
            return payload
        except Exception as exc:
            return {"status": "failed", "message": str(exc)}
