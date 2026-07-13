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

import daemon_contracts  # noqa: E402
import task_sys_ingress  # noqa: E402
import task_sys_daemon_adapter  # noqa: E402
from env.repos import runtime_files  # noqa: E402


IM_MESSAGE_CREATED_EVENT_TYPE = "im.message.created"


def _context_identity_route(context: Any) -> dict[str, str]:
    return {
        "identity_id": runtime_files.require_id(getattr(context, "actor_id", ""), "context.actor_id"),
        "role_id": runtime_files.require_id(getattr(context, "role", ""), "context.role"),
    }


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
        del state, runtime
        if not self.handles(trigger):
            return daemon_contracts.HandlerResult.ignored()
        try:
            local_route = _context_identity_route(context)
            target_route = {
                "identity_id": runtime_files.require_id(getattr(trigger, "target_identity_id", ""), "trigger.target_identity_id"),
                "role_id": runtime_files.require_id(getattr(trigger, "target_role_id", ""), "trigger.target_role_id"),
            }
            if target_route != local_route:
                raise PermissionError("wrong target identity for IM wake")
            message_id = _payload_id(trigger, "message_id")
            conversation_id = _payload_id(trigger, "conversation_id")
            event_id = _payload_id(trigger, "event_id")
            result = task_sys_ingress.ingest_im_message(
                actor_id=target_route["identity_id"],
                role_id=target_route["role_id"],
                message_id=message_id,
                conversation_id=conversation_id,
                event_id=event_id,
            )
            task_sys_daemon_adapter.execute_instruction(context, result["instruction"])
            return daemon_contracts.HandlerResult.handled()
        except Exception as exc:
            return daemon_contracts.HandlerResult.failed(str(exc))


if __name__ == "__main__":
    raise SystemExit("im_wake_handler is not a standalone command")
