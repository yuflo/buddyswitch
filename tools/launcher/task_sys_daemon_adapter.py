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
import side_thread_registry  # noqa: E402
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


def _completed_turn(trigger: Any) -> dict[str, str] | None:
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
    if status != "completed":
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


def _idle_side_thread(context: Any, trigger: Any) -> dict[str, str] | None:
    if getattr(trigger, "type", None) != "app_server.thread_status_changed":
        return None
    source_context = getattr(trigger, "source_context", None)
    if not isinstance(source_context, Mapping):
        return None
    thread_id = source_context.get("thread_id")
    status = source_context.get("thread_status")
    if not isinstance(thread_id, str) or not thread_id or status != "idle":
        return None
    if thread_id == getattr(context, "main_thread_id", None):
        return None
    return {"thread_id": thread_id, "status": "idle"}


def _current_side_task(
    context: Any,
    side_signal: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, str]] | None:
    actor_id = runtime_files.require_id(getattr(context, "actor_id", ""), "context.actor_id")
    role_id = runtime_files.require_id(getattr(context, "role", ""), "context.role")
    parent_thread_id = runtime_files.require_id(
        getattr(context, "main_thread_id", ""),
        "context.main_thread_id",
    )
    thread_id = runtime_files.require_id(side_signal.get("thread_id"), "side_signal.thread_id")
    instance_json = getattr(context, "instance_json", None)
    if not isinstance(instance_json, (str, Path)):
        raise ValueError("context.instance_json is required for side Progress Check")
    try:
        row = side_thread_registry.require_side_thread(
            Path(instance_json),
            actor_id=actor_id,
            parent_thread_id=parent_thread_id,
            side_thread_id=thread_id,
        )
    except side_thread_registry.SideThreadRegistryError as exc:
        if str(exc).startswith("Side thread is not registered for this instance:"):
            return None
        raise
    if row.get("purpose") != "task_sys.side_frame":
        return None
    if row.get("turn_kind") != "work":
        return None
    turn_id = row.get("turn_id")
    if not isinstance(turn_id, str) or not turn_id:
        return None
    task_id = row.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        return None
    task = task_sys.get_task(task_id)
    if task.get("actor_target") != {"actor_id": actor_id, "role_id": role_id}:
        return None
    if task.get("status") != task_sys.SIDE_PROCESSING:
        return None
    return task, {"thread_id": thread_id, "turn_id": turn_id, "status": "idle"}


class TaskSysProgressCheckHandler:
    name = "task_sys_progress_check"

    def _parent_checkpoint(self, state: Any) -> Mapping[str, Any]:
        get_state = getattr(state, "handler_state", None)
        if not callable(get_state):
            raise ValueError("daemon state does not expose handler_state")
        handler_state = get_state(self.name)
        if not isinstance(handler_state, Mapping):
            raise ValueError("Task Progress Check daemon state must be an object")
        checkpoint = handler_state.get("checkpoint")
        return checkpoint if isinstance(checkpoint, Mapping) else {}

    def _record_parent_checkpoint(
        self,
        state: Any,
        *,
        task_id: str,
        previous_turn: Mapping[str, str],
        status: str,
        submitted_turn_id: str | None = None,
    ) -> None:
        update = getattr(state, "update_handler_state", None)
        if not callable(update):
            raise ValueError("daemon state does not expose update_handler_state")
        checkpoint = {
            "processor": "parent",
            "task_id": task_id,
            "thread_id": previous_turn["thread_id"],
            "source_turn_id": previous_turn["turn_id"],
            "status": status,
        }
        if submitted_turn_id is not None:
            checkpoint["submitted_turn_id"] = submitted_turn_id
        update(self.name, {"checkpoint": checkpoint})

    def handles(self, trigger: Any) -> bool:
        return getattr(trigger, "type", None) in {
            "app_server.turn_completed",
            "app_server.thread_status_changed",
        }

    def handle(
        self,
        context: Any,
        state: Any,
        runtime: Any,
        trigger: Any,
    ) -> daemon_contracts.HandlerResult:
        del runtime
        try:
            previous_turn = _completed_turn(trigger)
            if previous_turn is not None and previous_turn["thread_id"] == getattr(context, "main_thread_id", None):
                processor = "parent"
                side_thread_id = None
                task = _current_parent_task(context)
                checkpoint = self._parent_checkpoint(state)
                same_checkpoint = (
                    checkpoint.get("processor") == "parent"
                    and checkpoint.get("thread_id") == previous_turn["thread_id"]
                    and isinstance(task, Mapping)
                    and checkpoint.get("task_id") == task.get("id")
                )
                if same_checkpoint and checkpoint.get("status") == "submitting":
                    return daemon_contracts.HandlerResult.ignored()
                if same_checkpoint and (
                    previous_turn["turn_id"]
                    in {checkpoint.get("source_turn_id"), checkpoint.get("submitted_turn_id")}
                ):
                    return daemon_contracts.HandlerResult.ignored()
            else:
                side_signal = _idle_side_thread(context, trigger)
                if side_signal is None:
                    return daemon_contracts.HandlerResult.ignored()
                processor = "side"
                side_thread_id = side_signal["thread_id"]
                resolved = _current_side_task(context, side_signal)
                if resolved is None:
                    return daemon_contracts.HandlerResult.ignored()
                task, previous_turn = resolved
            if task is None:
                return daemon_contracts.HandlerResult.ignored()
            if processor == "parent":
                self._record_parent_checkpoint(
                    state,
                    task_id=str(task["id"]),
                    previous_turn=previous_turn,
                    status="submitting",
                )
            result = task_sys_runtime.submit_task_progress_check(
                context,
                task,
                previous_turn,
                processor=processor,
                side_thread_id=side_thread_id,
            )
            if result.get("status") == "already_claimed":
                return daemon_contracts.HandlerResult.ignored()
            turn_id = result.get("turn_id") if isinstance(result, Mapping) else None
            if not isinstance(turn_id, str) or not turn_id:
                raise ValueError("Task Progress Check submit did not return a turn id")
            if processor == "parent":
                self._record_parent_checkpoint(
                    state,
                    task_id=str(task["id"]),
                    previous_turn=previous_turn,
                    status="submitted",
                    submitted_turn_id=turn_id,
                )
            return daemon_contracts.HandlerResult.handled()
        except Exception as exc:
            return daemon_contracts.HandlerResult.failed(str(exc))
