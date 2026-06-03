#!/usr/bin/env python3
"""Daemon trigger handler for message routing."""

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
from env.domain import messages as message_rules  # noqa: E402
from env.repos import runtime_files  # noqa: E402
from env.tool_runtime.actor_profile import ActorAddress  # noqa: E402


def _context_actor_address(context: Any) -> ActorAddress:
    value = getattr(context, "actor_address", None)
    if isinstance(value, ActorAddress):
        return value
    return daemon_core.actor_address_for_context(context)


class MessageAvailableHandler:
    name = "message_available"

    def handles(self, trigger: Any) -> bool:
        return getattr(trigger, "type", None) == "message.available"

    def handle(
        self,
        context: Any,
        state: Any,
        runtime: Any,
        trigger: Any,
    ) -> Any:
        del state
        trigger_type = getattr(trigger, "type", None)
        if trigger_type == "message.available":
            return self._handle_message_available(context, runtime, trigger)
        return daemon_core.HandlerResult.ignored()

    def _message_id(self, trigger: Any) -> str:
        payload = getattr(trigger, "payload", None)
        if not isinstance(payload, dict):
            raise ValueError("message trigger payload must be an object")
        return runtime_files.require_id(payload.get("message_id"), "message_id")

    def _ensure_target_actor(self, context: Any, trigger: Any) -> None:
        local_actor = _context_actor_address(context)
        target_actor = ActorAddress.from_payload(getattr(trigger, "target_actor_address", None))
        if target_actor != local_actor:
            raise PermissionError("wrong target actor for message trigger")

    def _source_actor_address(self, trigger: Any) -> ActorAddress:
        source_context = getattr(trigger, "source_context", None)
        if not isinstance(source_context, dict):
            raise ValueError("message trigger source_context must be an object")
        return ActorAddress.from_payload(source_context.get("source_actor_address"))

    def _handle_message_available(self, context: Any, runtime: Any, trigger: Any) -> daemon_core.HandlerResult:
        try:
            self._ensure_target_actor(context, trigger)
            message_id = self._message_id(trigger)
            source_actor = self._source_actor_address(trigger)
            target_actor = _context_actor_address(context)
            activity = runtime.parent_activity()
            status = activity.get("status") if isinstance(activity, dict) else None
            if status == "idle":
                runtime.submit_parent_prompt(
                    message_rules.render_parent_message_prompt(message_id, source_actor, target_actor),
                    handler_name=self.name,
                    origin_id=message_id,
                    interrupt_policy="none",
                )
                return daemon_core.HandlerResult.handled()
            if status == "running":
                runtime.submit_side_triage_prompt(
                    message_rules.render_side_triage_prompt(message_id, source_actor, target_actor),
                    handler_name=self.name,
                    origin_id=message_id,
                )
                return daemon_core.HandlerResult.handled()
            error = activity.get("error") if isinstance(activity, dict) else None
            return daemon_core.HandlerResult.failed(str(error or "parent thread activity is unavailable"))
        except Exception as exc:
            return daemon_core.HandlerResult.failed(str(exc))


if __name__ == "__main__":
    raise SystemExit("message_available_handler is not a standalone command")
