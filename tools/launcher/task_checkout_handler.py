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

import app_server  # noqa: E402
from env.domain import task_management, task_tui  # noqa: E402


def _string_field(payload: dict[str, Any], *names: str) -> str:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value:
            return value
    return ""


def _turn_id_from_start_result(result: dict[str, Any]) -> str:
    turn = result.get("turn")
    if isinstance(turn, dict):
        turn_id = turn.get("id")
        if isinstance(turn_id, str) and turn_id:
            return turn_id
    return _string_field(result, "turn_id", "turnId")


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
    client: Any,
    previous_turn: dict[str, str],
) -> bool:
    origin_turn_id = previous_turn["turn_id"]
    try:
        snapshot = task_management.current_snapshot(
            active_buddy=context.buddy,
            instance_json=context.instance_json,
            instance_payload=context.instance_payload,
        )
        prompt = task_tui.render_stop_task_tui(snapshot, previous_turn)
        result = client.request(
            "turn/start",
            {
                "threadId": context.main_thread_id,
                "input": app_server.text_input_payload(prompt),
                "permissions": context.permissions,
            },
        )
        turn_id = _turn_id_from_start_result(result)
        if not turn_id:
            raise app_server.AppServerProtocolError("turn/start did not return a turn id")
        state.record_daemon_origin_turn(turn_id)
        state.update_handler_state(
            "task_checkout",
            {
                "last_origin_turn_id": origin_turn_id,
                "last_checkout_turn_id": turn_id,
                "last_error": None,
            },
        )
        return True
    except app_server.AppServerError as exc:
        state.record_error(origin_turn_id=origin_turn_id, message=str(exc), handler="task_checkout")
        state.record_handler_error("task_checkout", origin_turn_id=origin_turn_id, message=str(exc))
        return False


class TaskCheckoutHandler:
    name = "task_checkout"

    def handle_notification(
        self,
        context: Any,
        state: Any,
        client: Any,
        notification: dict[str, Any],
    ) -> bool:
        previous_turn = completed_turn_for_checkout(notification, state)
        if previous_turn is None:
            return False
        return send_checkout_prompt(context, state, client, previous_turn)
