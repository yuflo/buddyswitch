"""Thin client for the instance daemon's Task-to-native-Goal reconciliation command."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Mapping


from buddyswitch.env.tool_runtime import daemon_client  # noqa: E402
from buddyswitch.env.tool_runtime import task_goal_runtime_protocol as protocol  # noqa: E402

TASK_GOAL_RESPONSE_TIMEOUT_SECONDS = 65.0


class TaskGoalRuntimeClientError(RuntimeError):
    def __init__(self, code: str, message: str, *, response: Mapping[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.response = dict(response) if response is not None else None


def reconcile_task(
    *,
    instance_root: Path,
    task_id: str,
    socket_path: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("task_id must be a non-empty string")
    root = Path(instance_root)
    envelope = daemon_client.request_mailbox(
        protocol.RECONCILE_TASK,
        {"task_id": task_id.strip()},
        socket_path=(
            Path(socket_path)
            if socket_path is not None
            else daemon_client.mailbox_socket_path_for_instance_root(root)
        ),
        response_timeout_seconds=TASK_GOAL_RESPONSE_TIMEOUT_SECONDS,
    )
    if envelope.get("ok") is not True:
        error = envelope.get("error")
        payload = error if isinstance(error, Mapping) else {}
        code = payload.get("code")
        message = payload.get("message")
        raise TaskGoalRuntimeClientError(
            code if isinstance(code, str) and code else "task_goal_reconcile_error",
            message if isinstance(message, str) and message else "Task Goal reconciliation failed",
            response=envelope,
        )
    result = envelope.get("result")
    if not isinstance(result, Mapping):
        raise TaskGoalRuntimeClientError(
            "task_goal_runtime_protocol_error",
            "Task Goal reconciliation success is missing a result object",
            response=envelope,
        )
    return dict(result)
