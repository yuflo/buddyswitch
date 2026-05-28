#!/usr/bin/env python3
"""Task checkout handler for daemon notifications."""

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
import submit_turn as launcher_submit_turn  # noqa: E402
from env.domain import task_management, task_tui  # noqa: E402


def _string_field(payload: dict[str, Any], *names: str) -> str:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value:
            return value
    return ""


def completed_turn_for_checkout(notification: dict[str, Any], state: Any) -> dict[str, str] | None:
    if notification.get("method") != "turn/completed":
        return None
    params = notification.get("params")
    if not isinstance(params, dict):
        return None
    turn = params.get("turn")
    if not isinstance(turn, dict):
        return None

    thread_id = _string_field(params, "threadId")
    turn_id = _string_field(turn, "id")
    status = _string_field(turn, "status")
    if not thread_id or not turn_id:
        return None
    if thread_id != state.payload.get("main_thread_id"):
        return None
    if status != "completed":
        return None
    if state.is_daemon_origin_turn(turn_id):
        return None
    return {"thread_id": thread_id, "turn_id": turn_id, "status": status}


def send_checkout_prompt(
    context: Any,
    state: Any,
    actions: Any,
    previous_turn: dict[str, str],
) -> daemon_core.HandlerResult:
    origin_turn_id = previous_turn["turn_id"]
    try:
        snapshot = task_management.current_snapshot(
            active_buddy=context.buddy,
            instance_json=context.instance_json,
            instance_payload=context.instance_payload,
        )
        prompt = task_tui.render_stop_task_tui(snapshot, previous_turn)
        actions.submit_turn(prompt, handler_name="task_checkout", origin_turn_id=origin_turn_id)
        return daemon_core.HandlerResult.handled()
    except launcher_submit_turn.SubmitTurnError as exc:
        return daemon_core.HandlerResult.failed(str(exc))


class TaskCheckoutHandler:
    name = "task_checkout"

    def handle_notification(
        self,
        context: Any,
        state: Any,
        actions: Any,
        notification: dict[str, Any],
    ) -> daemon_core.HandlerResult:
        previous_turn = completed_turn_for_checkout(notification, state)
        if previous_turn is None:
            return daemon_core.HandlerResult.ignored()
        return send_checkout_prompt(context, state, actions, previous_turn)
