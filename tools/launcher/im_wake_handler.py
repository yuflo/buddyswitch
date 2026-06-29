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
import task_sys_ingress  # noqa: E402
import task_sys_runtime  # noqa: E402
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
            del runtime
            result = task_sys_ingress.ingest_im_message(
                actor_id=target_actor.actor_id,
                role_id=target_actor.role_id,
                message_id=message_id,
                conversation_id=conversation_id,
                event_id=event_id,
            )
            task_sys_runtime.execute_instruction(context, result["instruction"])
            return daemon_core.HandlerResult.handled()
        except Exception as exc:
            return daemon_core.HandlerResult.failed(str(exc))


if __name__ == "__main__":
    raise SystemExit("im_wake_handler is not a standalone command")
