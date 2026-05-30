#!/usr/bin/env python3
"""Daemon mailbox handler for message.available events."""

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
from env.tool_runtime.actor_profile import RuntimeActorAddress  # noqa: E402


def _context_actor_address(context: Any) -> RuntimeActorAddress:
    value = getattr(context, "actor_address", None)
    if isinstance(value, RuntimeActorAddress):
        return value
    return daemon_core.actor_address_for_context(context)


class MessageAvailableHandler:
    name = "message_available"

    def handle_mailbox_event(
        self,
        context: Any,
        state: Any,
        actions: Any,
        event: dict[str, Any],
    ) -> daemon_core.HandlerResult:
        if not isinstance(event, dict) or event.get("type") != "message.available":
            return daemon_core.HandlerResult.ignored()
        try:
            normalized = daemon_mailbox.validate_mailbox_event(event)
            local_actor = _context_actor_address(context)
            target_actor = RuntimeActorAddress.from_payload(normalized["to_actor_address"])
            if target_actor != local_actor:
                return daemon_core.HandlerResult.failed("wrong target actor for message.available event")
            prompt = (
                "[MESSAGE AVAILABLE]\n"
                f"message_id: {normalized['message_id']}\n"
                "Use message.list to read the message when ready."
            )
            actions.submit_turn(
                prompt,
                handler_name=self.name,
                origin_turn_id=normalized["message_id"],
            )
            return daemon_core.HandlerResult.handled()
        except Exception as exc:
            return daemon_core.HandlerResult.failed(str(exc))
