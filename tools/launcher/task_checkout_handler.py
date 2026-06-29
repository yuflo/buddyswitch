#!/usr/bin/env python3
"""Task checkout handler for daemon triggers."""

from __future__ import annotations

import sys
from pathlib import Path
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


def _string_field(payload: dict[str, Any], *names: str) -> str:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value:
            return value
    return ""


def completed_turn_for_checkout(trigger: Any, state: Any) -> dict[str, str] | None:
    if getattr(trigger, "type", None) != "app_server.turn_completed":
        return None
    source_context = getattr(trigger, "source_context", None)
    if not isinstance(source_context, dict):
        return None

    thread_id = _string_field(source_context, "thread_id")
    turn_id = _string_field(source_context, "turn_id")
    status = _string_field(source_context, "turn_status")
    if not thread_id or not turn_id or not status:
        return None
    if thread_id != state.payload.get("main_thread_id"):
        return None
    if status != "completed":
        return None
    if state.is_daemon_origin_turn_from(turn_id, "task_checkout"):
        return None
    return {"thread_id": thread_id, "turn_id": turn_id, "status": status}


def record_completed_turn(
    context: Any,
    state: Any,
    runtime: Any,
    previous_turn: dict[str, str],
) -> daemon_core.HandlerResult:
    del runtime
    try:
        result = task_sys_ingress.ingest_turn_completed(
            actor_id=context.actor_id,
            role_id=context.role,
            thread_id=previous_turn["thread_id"],
            turn_id=previous_turn["turn_id"],
            status=previous_turn["status"],
        )
        runtime_result = task_sys_runtime.execute_instruction(context, result["instruction"])
        turn_id = runtime_result.get("turn_id") if isinstance(runtime_result, dict) else None
        if isinstance(turn_id, str) and turn_id:
            state.record_daemon_origin_turn(
                turn_id,
                handler_name="task_checkout",
                origin_turn_id=previous_turn["turn_id"],
            )
        return daemon_core.HandlerResult.handled()
    except Exception as exc:
        return daemon_core.HandlerResult.failed(str(exc))


class TaskCheckoutHandler:
    name = "task_checkout"

    def handles(self, trigger: Any) -> bool:
        return getattr(trigger, "type", None) == "app_server.turn_completed"

    def handle(
        self,
        context: Any,
        state: Any,
        runtime: Any,
        trigger: Any,
    ) -> daemon_core.HandlerResult:
        previous_turn = completed_turn_for_checkout(trigger, state)
        if previous_turn is None:
            return daemon_core.HandlerResult.ignored()
        return record_completed_turn(context, state, runtime, previous_turn)
