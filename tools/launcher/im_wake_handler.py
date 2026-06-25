#!/usr/bin/env python3
"""Daemon trigger handler for Central IM runtime wake."""

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
from env.repos import runtime_files  # noqa: E402
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402


IM_MESSAGE_CREATED_EVENT_TYPE = "im.message.created"


def _context_actor_address(context: Any) -> ActorAddress:
    value = getattr(context, "actor_address", None)
    if isinstance(value, ActorAddress):
        return value
    return daemon_core.actor_address_for_context(context)


def _payload_id(trigger: Any, field: str) -> str:
    payload = getattr(trigger, "payload", None)
    if not isinstance(payload, dict):
        raise ValueError("IM wake payload must be an object")
    return runtime_files.require_id(payload.get(field), field)


def _parent_prompt(message_id: str, conversation_id: str, event_id: str) -> str:
    return "\n\n".join(
        (
            "[IM MESSAGE CREATED]",
            f"Message id: {message_id}",
            f"Conversation id: {conversation_id}",
            f"Event id: {event_id}",
            "Required action:\nProcess this exact IM message. Do not assume a reply is required.",
            "Steps:\n"
            f'1. Call message__get with message_id="{message_id}".\n'
            "2. If prior context is needed, call message__conversation for the sender from the message.\n"
            f'3. If a reply is needed, call message__send(content=..., reply_to="{message_id}").\n'
            "4. If no reply is needed, call message__mark with disposition=\"absorbed\".",
            'Finish:\nFinish after the message is marked "absorbed" or "replied".',
        )
    )


def _side_prompt(message_id: str, conversation_id: str, event_id: str) -> str:
    return "\n\n".join(
        (
            "[IM MESSAGE TRIAGE]",
            f"Message id: {message_id}",
            f"Conversation id: {conversation_id}",
            f"Event id: {event_id}",
            "Required action:\nTriage this exact IM message without interrupting the parent unless parent involvement is necessary.",
            "Steps:\n"
            f'1. Call message__get with message_id="{message_id}".\n'
            "2. If prior context is needed, call message__conversation for the sender from the message.\n"
            f'3. Use message__send(content=..., reply_to="{message_id}") when a reply is enough.\n'
            "4. Use message__mark with disposition=\"needs_parent\" only when parent work is required.\n"
            "5. Otherwise use message__mark with disposition=\"absorbed\".",
            "Finish:\nFinish after exactly one disposition path succeeds.",
        )
    )


class ImMessageCreatedHandler:
    name = "im_message_created"

    def handles(self, trigger: Any) -> bool:
        return getattr(trigger, "type", None) == IM_MESSAGE_CREATED_EVENT_TYPE

    def handle(
        self,
        context: Any,
        state: Any,
        runtime: Any,
        trigger: Any,
    ) -> Any:
        del state
        if not self.handles(trigger):
            return daemon_core.HandlerResult.ignored()
        try:
            local_actor = _context_actor_address(context)
            target_actor = ActorAddress.from_payload(getattr(trigger, "target_actor_address", None))
            if target_actor != local_actor:
                raise PermissionError("wrong target actor for IM wake")
            message_id = _payload_id(trigger, "message_id")
            conversation_id = _payload_id(trigger, "conversation_id")
            event_id = _payload_id(trigger, "event_id")
            activity = runtime.parent_activity()
            status = activity.get("status") if isinstance(activity, dict) else None
            if status == "idle":
                runtime.submit_parent_prompt(
                    _parent_prompt(message_id, conversation_id, event_id),
                    handler_name=self.name,
                    origin_id=message_id,
                    interrupt_policy="none",
                )
                return daemon_core.HandlerResult.handled()
            if status == "running":
                runtime.submit_side_triage_prompt(
                    _side_prompt(message_id, conversation_id, event_id),
                    handler_name=self.name,
                    origin_id=message_id,
                )
                return daemon_core.HandlerResult.handled()
            error = activity.get("error") if isinstance(activity, dict) else None
            return daemon_core.HandlerResult.failed(str(error or "parent thread activity is unavailable"))
        except Exception as exc:
            return daemon_core.HandlerResult.failed(str(exc))


if __name__ == "__main__":
    raise SystemExit("im_wake_handler is not a standalone command")
