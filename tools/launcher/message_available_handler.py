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
from env.tool_runtime.actor_profile import RuntimeActorAddress  # noqa: E402


def _context_actor_address(context: Any) -> RuntimeActorAddress:
    value = getattr(context, "actor_address", None)
    if isinstance(value, RuntimeActorAddress):
        return value
    return daemon_core.actor_address_for_context(context)


class MessageAvailableHandler:
    name = "message_available"

    def handles(self, signal: dict[str, Any]) -> bool:
        return isinstance(signal, dict) and signal.get("type") == "message.available"

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
            target_actor = RuntimeActorAddress.from_payload(normalized["target_actor_address"])
            if target_actor != local_actor:
                return daemon_core.HandlerResult.failed("wrong target actor for message.available signal")
            payload = normalized["payload"]
            if not isinstance(payload, dict):
                return daemon_core.HandlerResult.failed("message.available payload must be an object")
            message_id = runtime_files.require_id(payload.get("message_id"), "message_id")
            prompt = (
                "[MESSAGE AVAILABLE]\n"
                "A direct message is available for this actor.\n"
                "Use native `message__list` to read the inbox.\n"
                "Use native `message__conversation` when bidirectional context is needed."
            )
            actions.submit_turn(
                prompt,
                handler_name=self.name,
                origin_turn_id=message_id,
            )
            return daemon_core.HandlerResult.handled()
        except Exception as exc:
            return daemon_core.HandlerResult.failed(str(exc))
