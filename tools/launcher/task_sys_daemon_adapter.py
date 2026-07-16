"""Task Sys-owned adapter between generic daemon commands and Task runtime."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Mapping


HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import daemon_contracts  # noqa: E402
import task_sys_runtime  # noqa: E402
from env.domain import task_sys  # noqa: E402
from env.repos import runtime_files  # noqa: E402
from env.tool_runtime import task_sys_runtime_protocol as task_protocol  # noqa: E402


def execute_instruction(
    context: daemon_contracts.DaemonContext,
    instruction: Mapping[str, object],
) -> dict[str, Any]:
    if not isinstance(instruction, Mapping):
        raise ValueError("instruction must be an object")
    result = task_sys_runtime.execute_instruction(context, dict(instruction))
    if not isinstance(result, dict):
        raise RuntimeError("Task Sys runtime returned a non-object result")
    return result


def cleanup_side_lease(
    context: daemon_contracts.DaemonContext,
    task_id: str,
) -> dict[str, Any]:
    normalized_task_id = runtime_files.require_id(task_id, "task_id")
    result = task_sys_runtime.cleanup_side_lease(context, normalized_task_id)
    if not isinstance(result, dict):
        raise RuntimeError("Task Sys cleanup returned a non-object result")
    return result


def command_handlers(
    context: daemon_contracts.DaemonContext,
) -> Mapping[str, daemon_contracts.ApplicationCommand]:
    def execute(params: Mapping[str, object]) -> Mapping[str, object]:
        instruction = params.get("instruction")
        if not isinstance(instruction, Mapping):
            raise ValueError("instruction must be an object")
        return execute_instruction(context, instruction)

    def cleanup(params: Mapping[str, object]) -> Mapping[str, object]:
        task_id = params.get("task_id")
        return cleanup_side_lease(context, task_id if isinstance(task_id, str) else "")

    return {
        task_protocol.EXECUTE_INSTRUCTION: execute,
        task_protocol.CLEANUP_SIDE_LEASE: cleanup,
    }


def _completed_main_turn(context: Any, trigger: Any) -> dict[str, str] | None:
    if getattr(trigger, "type", None) != "app_server.turn_completed":
        return None
    source_context = getattr(trigger, "source_context", None)
    if not isinstance(source_context, dict):
        return None
    thread_id = source_context.get("thread_id")
    turn_id = source_context.get("turn_id")
    status = source_context.get("turn_status")
    if not all(isinstance(value, str) and value for value in (thread_id, turn_id, status)):
        return None
    if thread_id != getattr(context, "main_thread_id", None) or status != "completed":
        return None
    return {"thread_id": thread_id, "turn_id": turn_id, "status": status}


def _current_parent_task(context: Any) -> dict[str, Any] | None:
    actor_target = {
        "actor_id": runtime_files.require_id(getattr(context, "actor_id", ""), "context.actor_id"),
        "role_id": runtime_files.require_id(getattr(context, "role", ""), "context.role"),
    }
    tasks = task_sys.list_tasks(
        actor_target=actor_target,
        statuses=(task_sys.PARENT_PROCESSING,),
    )
    if not tasks:
        return None
    return max(tasks, key=lambda row: (str(row.get("updated_at") or ""), str(row.get("id") or "")))


class TaskSysProgressCheckHandler:
    name = "task_sys_progress_check"

    def __init__(self) -> None:
        self._submitted_turn_id: str | None = None

    def handles(self, trigger: Any) -> bool:
        return getattr(trigger, "type", None) == "app_server.turn_completed"

    def handle(
        self,
        context: Any,
        state: Any,
        runtime: Any,
        trigger: Any,
    ) -> daemon_contracts.HandlerResult:
        del state, runtime
        previous_turn = _completed_main_turn(context, trigger)
        if previous_turn is None:
            return daemon_contracts.HandlerResult.ignored()
        if previous_turn["turn_id"] == self._submitted_turn_id:
            self._submitted_turn_id = None
            return daemon_contracts.HandlerResult.ignored()
        try:
            task = _current_parent_task(context)
            if task is None:
                return daemon_contracts.HandlerResult.ignored()
            result = task_sys_runtime.submit_parent_progress_check(context, task, previous_turn)
            turn_id = result.get("turn_id") if isinstance(result, Mapping) else None
            if not isinstance(turn_id, str) or not turn_id:
                raise ValueError("parent Progress Check submit did not return a turn id")
            self._submitted_turn_id = turn_id
            return daemon_contracts.HandlerResult.handled()
        except Exception as exc:
            return daemon_contracts.HandlerResult.failed(str(exc))
