"""Execute Task Sys runtime instructions with generic launcher actuators."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import app_server  # noqa: E402
import actor_session  # noqa: E402
import actor_side_thread  # noqa: E402
import side_thread_lifecycle  # noqa: E402
from env.domain import task_sys  # noqa: E402


MAX_START_SIDE_ATTEMPTS = 2


class InstanceTaskSysContext:
    def __init__(
        self,
        *,
        actor_id: str,
        role: str,
        main_thread_id: str,
        socket_path: Path,
        permissions: str,
        instance_json: Path,
        workspace_dir: Path,
        project_workspace_dir: Path,
    ) -> None:
        self.actor_id = actor_id
        self.role = role
        self.main_thread_id = main_thread_id
        self.socket_path = socket_path
        self.permissions = permissions
        self.instance_json = instance_json
        self.workspace_dir = workspace_dir
        self.project_workspace_dir = project_workspace_dir


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _context_field(context: Any, name: str) -> Any:
    if isinstance(context, Mapping):
        return context.get(name)
    return getattr(context, name, None)


def _context_actor_id(context: Any) -> str:
    return _require_text(_context_field(context, "actor_id"), "context.actor_id")


def _context_role(context: Any) -> str:
    value = _context_field(context, "role")
    if value is None:
        value = _context_field(context, "role_id")
    return _require_text(value, "context.role")


def _context_path(context: Any, name: str) -> Path:
    value = _context_field(context, name)
    if isinstance(value, Path):
        return value
    return Path(_require_text(value, f"context.{name}"))


def _validate_actor_target(context: Any, instruction: Mapping[str, Any]) -> None:
    target = _require_mapping(instruction.get("actor_target"), "instruction.actor_target")
    if target.get("actor_id") != _context_actor_id(context) or target.get("role_id") != _context_role(context):
        raise PermissionError("wrong target actor for Task Sys runtime instruction")


def _json_block(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), ensure_ascii=True, indent=2, sort_keys=True)


def _im_message_tool_capability_lines() -> tuple[str, ...]:
    return (
        "- message.contacts(...) to inspect discoverable actor targets when target discovery is needed.",
        "- message.list(...) to inspect active-identity Central IM events when event feed context is needed.",
        "- message.get(message_id=...) to read exact processable inbound messages.",
        "- message.conversation(target_identity_id=..., ...) to inspect visible direct conversation context.",
        "- message.send(reply_to=source_message_id, content=...) to reply to the current source message.",
        "- message.send(target_identity_id=..., content=...) to send required IM communication to an explicit actor or external identity.",
        "- message.mark(message_id=..., disposition=absorbed) when a processable inbound message needs no reply.",
    )


def _render_im_message_task_guidance(*, frame_kind: str) -> tuple[str, str, str]:
    close_line = (
        "- After the required message work succeeds, call task_sys.close(task_id=..., summary=...)."
        if frame_kind == "parent"
        else "- After the task is completed in side, call task_sys.close(task_id=..., summary=...)."
    )
    return (
        "For an IM source message:",
        "\n".join(
            (
                "Use the message tool contract as the authority for message reads, sends, target resolution, and disposition.",
                "Allowed message operations for completing this IM-source task:",
                *_im_message_tool_capability_lines(),
                close_line,
                "- If the actor decides the Task must stop without completion, call task_sys.cancel(task_id=..., reason=...).",
            )
        ),
        "Message task boundary:",
    )


def render_side_frame(frame: Mapping[str, Any]) -> str:
    payload = _require_mapping(frame, "frame")
    task_id = _require_text(payload.get("task_id"), "frame.task_id")
    source = _require_mapping(payload.get("source"), "frame.source")
    source_type = source.get("type")
    if source_type == "im.message.created":
        source_guidance = (
            *_render_im_message_task_guidance(frame_kind="side"),
            "\n".join(
                (
                    "- Keep message work tied to the current IM-source task.",
                    "- Use task_sys.need_parent only when required work needs parent resources outside message tools.",
                )
            ),
        )
    else:
        source_guidance = (
            "Source-specific resources:",
            "No source-specific message capability is added for this source type.",
        )
    return "\n\n".join(
        (
            "task_sys.side_frame",
            "You are processing exactly one Task Sys side frame.",
            (
                "The inherited parent thread history is reference context only. The active task is only the task "
                "described in this frame. Do not continue inherited parent-thread work, plans, tool calls, approvals, "
                "edits, or requests."
            ),
            f"Task id: {task_id}",
            "Task Sys source:",
            _json_block(source),
            "Task Sys context:",
            _json_block(_require_mapping(payload.get("context"), "frame.context")),
            "Core policy: decide by required resources.",
            (
                "A side thread may handle the task only when completion requires this task_sys.side_frame, exact "
                "source objects referenced by this frame, bounded read-only inspection, source-specific message "
                "tools allowed by this frame, and one Task Sys completion operation."
            ),
            (
                "If the task requires parent attention, workspace resources, browser/web/research resources, shared "
                "product-state writes outside the message tools, durable deliverables, or multi-step execution "
                "outside the current message task, do not perform it in side. Call task_sys.need_parent."
            ),
            "Allowed side resources:",
            *source_guidance,
            "\n".join(
                (
                    "1. Frame and exact source reads",
                    "- Read this task frame.",
                    "- Read exact source refs from this frame.",
                    "- Use source-specific product reads only when allowed above.",
                    "- Use track/artifact/context read-only tools only for bounded inspection.",
                    (
                        "- Use local read-only inspection only; do not run tests, builds, app servers, installers, "
                        "formatters, or commands that write files/cache/state."
                    ),
                    "- Use search.status only for capability/status inspection.",
                )
            ),
            "\n".join(
                (
                    "2. Task Sys frame operation",
                    "Finish this frame with one legal completion operation:",
                    "- task_sys.close(task_id=..., summary=...) when the task is completed in side.",
                    "- task_sys.cancel(task_id=..., reason=...) when the task must stop without completion.",
                    (
                        "- task_sys.need_parent(task_id=..., params={parent_frame_context, interrupt, "
                        "ordering}) when parent work is required."
                    ),
                )
            ),
            "Forbidden side resources:",
            "\n".join(
                (
                    "Do not use or mutate:",
                    "- parent turns, parent submit, parent interrupt, or parent steering directly,",
                    "- source files, git, config, dependencies, tests, builds, app runtime, or workspace state,",
                    "- browser session, web search, webpage reading, evidence gathering, or research loops,",
                    "- Track shared state, including comments, status, requirements, materials, proof, resolve, archive,",
                    "- artifacts, evidence, durable deliverables,",
                    "- raw runtime files or buddyswitch/objects direct writes,",
                    "- permission changes, sandbox broadening, or external credentials,",
                    "- outbound communication outside this frame's source-specific message guidance.",
                )
            ),
            "Decision procedure:",
            "\n".join(
                (
                    "1. Identify the resources required to complete the user-visible task.",
                    "2. If all required resources are allowed side resources, complete the task in side.",
                    "3. If any required resource is forbidden or belongs to parent, call task_sys.need_parent.",
                    (
                        "4. Do not call task_sys.need_parent for message work that this frame's source-specific "
                        "message guidance allows."
                    ),
                    (
                        "5. Do call task_sys.need_parent for research, implementation, planning, verification, "
                        "shared product-state writes, Track replies, "
                        "artifact/evidence output, browser/web use, or parent-thread continuity."
                    ),
                )
            ),
            "Frame completion order:",
            "\n".join(
                (
                    "- Perform required message actions before closing the task.",
                    (
                        "- If the message action fails, do not close the task. Retry if clearly safe, otherwise call "
                        "task_sys.need_parent with failure context."
                    ),
                    (
                        "- If the message action succeeded but task_sys.close fails, retry task_sys.close; do "
                        "not send a duplicate reply."
                    ),
                )
            ),
            "Parent handoff rules:",
            "\n".join(
                (
                    "Use task_sys.need_parent when the task needs resources outside side's boundary.",
                    "The parent_frame_context must be minimal and concrete:",
                    "- what the source asked for,",
                    "- what side inspected,",
                    "- why parent resources are required,",
                    "- any exact source ids needed by parent,",
                    "- any failure details if side could not safely close.",
                    (
                        "Set interrupt=true only when delaying parent work would be harmful, stale, or explicitly "
                        "superseded. Otherwise omit interrupt or set it false."
                    ),
                )
            ),
            "Allowed frame completion operations:",
            "- task_sys.close(task_id=..., summary=...) when the task is completed in side.",
            "- task_sys.cancel(task_id=..., reason=...) when the task must stop without completion.",
            "- task_sys.need_parent(task_id=..., params={parent_frame_context, interrupt, ordering})",
            "Do not use any other Task Sys operation from side. Treat interrupt only as a task_sys.need_parent params field.",
        )
    )


def render_parent_frame(frame: Mapping[str, Any]) -> str:
    payload = _require_mapping(frame, "frame")
    task_id = _require_text(payload.get("task_id"), "frame.task_id")
    source = _require_mapping(payload.get("source"), "frame.source")
    source_type = source.get("type")
    if source_type == "im.message.created":
        source_guidance = (
            *_render_im_message_task_guidance(frame_kind="parent"),
            "\n".join(
                (
                    "- Use message tools only for work required by this parent frame and its execution_handoff.",
                    "- Do not rely on parent turn completion to close this Task Sys task.",
                )
            ),
            "Allowed parent frame operations:",
            "\n".join(
                (
                    "- message.contacts(...)",
                    "- message.list(...)",
                    "- message.get(message_id=...)",
                    "- message.conversation(target_identity_id=..., ...)",
                    "- message.send(reply_to=source_message_id, content=...)",
                    "- message.send(target_identity_id=..., content=...)",
                    "- message.mark(message_id=..., disposition=absorbed)",
                    "- task_sys.close(task_id=..., summary=...)",
                    "- task_sys.cancel(task_id=..., reason=...)",
                )
            ),
        )
    else:
        source_guidance = (
            "For this parent source:",
            "\n".join(
                (
                    "- Perform the parent work requested by execution_handoff.",
                    "- After required parent work is complete, call task_sys.close.",
                )
            ),
            "Allowed parent frame operations:",
            "\n".join(
                (
                    "- task_sys.close(task_id=..., summary=...)",
                    "- task_sys.cancel(task_id=..., reason=...)",
                )
            ),
        )
    return "\n\n".join(
        (
            "task_sys.parent_frame",
            f"Task id: {task_id}",
            "Task Sys source:",
            _json_block(source),
            "Inbound context:",
            _json_block(_require_mapping(payload.get("inbound_context"), "frame.inbound_context")),
            "Execution handoff:",
            _json_block(_require_mapping(payload.get("execution_handoff"), "frame.execution_handoff")),
            "Required action:",
            "Process this Task Sys parent frame. Use source refs and task context; do not assume raw inbound outside this frame.",
            "When the source task is complete, call task_sys.close(task_id=..., summary=...).",
            "If the Task must stop without completion, call task_sys.cancel(task_id=..., reason=...).",
            "Do not rely on parent turn completion to close this Task Sys task.",
            *source_guidance,
        )
    )


def render_submit_parent_frame(frame: Mapping[str, Any]) -> str:
    payload = _require_mapping(frame, "frame")
    kind = _require_text(payload.get("kind"), "frame.kind")
    if kind == "task_sys.parent_frame":
        return render_parent_frame(payload)
    raise ValueError(f"unsupported submit_parent frame kind: {kind}")


def render_parent_progress_check(
    task: Mapping[str, Any],
    previous_turn: Mapping[str, Any],
) -> str:
    payload = _require_mapping(task, "task")
    task_id = _require_text(payload.get("id"), "task.id")
    status = _require_text(payload.get("status"), "task.status")
    if status != task_sys.PARENT_PROCESSING:
        raise ValueError("parent Progress Check requires an in_progress.parent_processing task")
    turn = _require_mapping(previous_turn, "previous_turn")
    turn_id = _require_text(turn.get("turn_id"), "previous_turn.turn_id")
    thread_id = _require_text(turn.get("thread_id"), "previous_turn.thread_id")
    turn_status = _require_text(turn.get("status"), "previous_turn.status")
    if turn_status != "completed":
        raise ValueError("parent Progress Check requires a completed previous turn")

    source_ref = payload.get("source_ref")
    source = {
        "type": _require_text(payload.get("source_type"), "task.source_type"),
        "ref": dict(source_ref) if isinstance(source_ref, Mapping) else {},
    }
    events = payload.get("events")
    last_event: dict[str, Any] = {}
    if isinstance(events, list) and events and isinstance(events[-1], Mapping):
        last_event = dict(events[-1])

    return "\n\n".join(
        (
            "[TASK PROGRESS CHECK]",
            "Review the existing parent-owned Task after the previous main-thread turn completed.",
            f"Previous main-thread turn: {turn_id} on {thread_id}",
            f"Existing Task id: {task_id}",
            f"Canonical Task status: {status}",
            "Task source:\n" + _json_block(source),
            "Last lifecycle event:\n" + _json_block(last_event),
            "Actor decision:",
            "\n".join(
                (
                    f"- If the Task is complete, call task_sys.close(task_id=\"{task_id}\", summary=...).",
                    f"- If the Task must stop without completion, call task_sys.cancel(task_id=\"{task_id}\", reason=...).",
                    "- If more parent work is required, continue that work in this turn; do not mutate Task status merely for continuing.",
                    f"- On continue, status remains {task_sys.PARENT_PROCESSING} until the actor explicitly closes or cancels the Task.",
                )
            ),
            "This Progress Check is bound to the existing Task. Do not create another Task or infer completion from turn completion alone.",
        )
    )


def _main_thread_id(context: Any) -> str:
    return _require_text(_context_field(context, "main_thread_id"), "context.main_thread_id")


def _socket_path(context: Any) -> Path:
    return _context_path(context, "socket_path")


def _permissions(context: Any) -> str:
    return _require_text(_context_field(context, "permissions"), "context.permissions")


def _instance_json(context: Any) -> Path:
    return _context_path(context, "instance_json")


def _workspace_dir(context: Any) -> Path:
    return _context_path(context, "workspace_dir")


def _project_workspace_dir(context: Any) -> Path:
    return _context_path(context, "project_workspace_dir")


def submit_parent_progress_check(
    context: Any,
    task: Mapping[str, Any],
    previous_turn: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _require_mapping(task, "task")
    task_id = _require_text(payload.get("id"), "task.id")
    result = actor_session.input_actor_turn(
        socket_path=_socket_path(context),
        instance_json=_instance_json(context),
        thread_id=_main_thread_id(context),
        text=render_parent_progress_check(payload, previous_turn),
        permissions=_permissions(context),
    )
    return {
        "action": "progress_check",
        "task_id": task_id,
        "turn_id": _turn_id_from_submit_result(_require_mapping(result, "submit result")),
    }


def cleanup_side_lease(context: Any, task_id: str) -> dict[str, Any]:
    return side_thread_lifecycle.cleanup_task_side_lease(
        socket_path=_socket_path(context),
        instance_json=_instance_json(context),
        actor_id=_context_actor_id(context),
        parent_thread_id=_main_thread_id(context),
        task_id=_require_text(task_id, "task_id"),
    )


def _start_side_attempt(
    context: Any,
    *,
    task_id: str,
    frame_text: str,
    parent_thread_id: str,
    attempt_number: int,
) -> dict[str, Any]:
    try:
        started = actor_side_thread.start_actor_side_thread(
            socket_path=_socket_path(context),
            instance_json=_instance_json(context),
            actor_id=_context_actor_id(context),
            parent_thread_id=parent_thread_id,
            text=frame_text,
            purpose="task_sys.side_frame",
            workspace_dir=_workspace_dir(context),
            shared_project_workspace_dir=_project_workspace_dir(context),
            permissions=_permissions(context),
            task_id=task_id,
        )
    except Exception as exc:
        attempt: dict[str, Any] = {
            "attempt": attempt_number,
            "stage": "side_lifecycle",
            "error": str(exc),
            "retryable": True,
        }
        return {"ok": False, "attempt": attempt}

    payload = _require_mapping(started, "side lifecycle result")
    side_thread_id = _require_text(payload.get("side_thread_id"), "side_thread_id")
    turn_id = _require_text(payload.get("turn_id"), "turn_id")
    attempt = {
        "attempt": attempt_number,
        "stage": "side_started",
        "side_thread_id": side_thread_id,
        "turn_id": turn_id,
        "retryable": False,
    }
    result = dict(payload)
    result.update(
        {
            "ok": True,
            "action": "start_side",
            "stage": "side_started",
            "task_id": task_id,
            "side_thread_id": side_thread_id,
            "turn_id": turn_id,
            "thread_action": payload.get("thread_action"),
            "attempt": attempt,
        }
    )
    return result


def _execute_start_side(context: Any, instruction: Mapping[str, Any]) -> dict[str, Any]:
    task_id = _require_text(instruction.get("task_id"), "instruction.task_id")
    frame_text = render_side_frame(_require_mapping(instruction.get("frame"), "instruction.frame"))
    parent_thread_id = _main_thread_id(context)
    attempts: list[dict[str, Any]] = []

    for attempt_number in range(1, MAX_START_SIDE_ATTEMPTS + 1):
        result = _start_side_attempt(
            context,
            task_id=task_id,
            frame_text=frame_text,
            parent_thread_id=parent_thread_id,
            attempt_number=attempt_number,
        )
        if result.get("ok") is True:
            attempt = result.pop("attempt")
            if isinstance(attempt, dict):
                attempts.append(attempt)
            result["attempts"] = attempts
            return result
        attempt = result.get("attempt")
        if isinstance(attempt, dict):
            attempts.append(attempt)

    last_attempt = attempts[-1] if attempts else {"stage": "side_fork", "error": "side dispatch failed"}
    failure = {
        "reason": "runtime_failed",
        "status": "runtime_failed",
        "stage": last_attempt.get("stage") or "side_fork",
        "processor": "side",
        "error": str(last_attempt.get("error") or "side dispatch failed"),
        "retryable": True,
        "attempts": len(attempts),
    }
    side_thread_id = last_attempt.get("side_thread_id")
    if isinstance(side_thread_id, str) and side_thread_id:
        failure["last_side_thread_id"] = side_thread_id
    cleanup = last_attempt.get("cleanup")
    if isinstance(cleanup, Mapping):
        failure["cleanup"] = dict(cleanup)
    recorded = task_sys.record_side_runtime_failure(task_id, failure)
    task = recorded.get("task") if isinstance(recorded.get("task"), dict) else {}
    execution = task.get("execution") if isinstance(task.get("execution"), Mapping) else {}
    execution_result = execution.get("result") if isinstance(execution, Mapping) else None
    return {
        "action": "start_side",
        "task_id": task_id,
        "status": "runtime_failed",
        "stage": failure["stage"],
        "attempts": attempts,
        "execution_result": execution_result,
        "state_changed": recorded.get("state_changed"),
    }


def _turn_id_from_submit_result(result: Mapping[str, Any]) -> str:
    value = result.get("turn_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    turn = result.get("turn")
    if isinstance(turn, Mapping):
        turn_id = turn.get("id")
        if isinstance(turn_id, str) and turn_id.strip():
            return turn_id.strip()
    value = result.get("turnId")
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError("submit parent instruction did not return a turn id")


def _is_no_active_turn_interrupt_error(exc: Exception) -> bool:
    message = str(exc)
    return "has no active in-progress turn" in message or "active but no in-progress turn was found" in message


def _execute_submit_parent(context: Any, instruction: Mapping[str, Any], *, interrupt: bool) -> dict[str, Any]:
    task_id = _require_text(instruction.get("task_id"), "instruction.task_id")
    frame_text = render_submit_parent_frame(_require_mapping(instruction.get("frame"), "instruction.frame"))
    interrupted_turn_id: str | None = None
    if interrupt:
        try:
            interrupted = app_server.interrupt_turn(_socket_path(context), _main_thread_id(context))
        except app_server.AppServerUnavailableError as exc:
            if not _is_no_active_turn_interrupt_error(exc):
                raise
        else:
            value = interrupted.get("turn_id") if isinstance(interrupted, Mapping) else None
            if isinstance(value, str) and value.strip():
                interrupted_turn_id = value.strip()
            else:
                raise ValueError("interrupt submit parent instruction did not return an interrupted turn id")
    result = actor_session.input_actor_turn(
        socket_path=_socket_path(context),
        instance_json=_instance_json(context),
        thread_id=_main_thread_id(context),
        text=frame_text,
        permissions=_permissions(context),
    )
    payload: dict[str, Any] = {
        "action": "interrupt_submit_parent" if interrupt else "submit_parent",
        "task_id": task_id,
        "turn_id": _turn_id_from_submit_result(_require_mapping(result, "submit result")),
    }
    if interrupted_turn_id is not None:
        payload["interrupted_turn_id"] = interrupted_turn_id
    return payload


def execute_instruction(context: Any, instruction: Mapping[str, Any]) -> dict[str, Any]:
    payload = _require_mapping(instruction, "instruction")
    _validate_actor_target(context, payload)
    instruction_type = _require_text(payload.get("type"), "instruction.type")
    task_id = _require_text(payload.get("task_id"), "instruction.task_id")
    if instruction_type == "start_side":
        return _execute_start_side(context, payload)
    if instruction_type == "submit_parent":
        return _execute_submit_parent(context, payload, interrupt=False)
    if instruction_type == "interrupt_submit_parent":
        return _execute_submit_parent(context, payload, interrupt=True)
    raise ValueError(f"unsupported Task Sys runtime instruction: {instruction_type}")


def context_from_instance_json(instance_json: Path) -> InstanceTaskSysContext:
    payload = json.loads(instance_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("instance json must contain an object")
    raw_project_workspace = payload.get("project_workspace_dir")
    if not isinstance(raw_project_workspace, str) or not raw_project_workspace.strip():
        raw_project_workspace = os.environ.get("BUDDYSWITCH_PROJECT_WORKSPACE_DIR")
    if not isinstance(raw_project_workspace, str) or not raw_project_workspace.strip():
        raw_project_workspace = str(instance_json.parent.parent.parent / "project" / "workspace")
    return InstanceTaskSysContext(
        actor_id=_require_text(payload.get("actor_id"), "instance.actor_id"),
        role=_require_text(payload.get("role"), "instance.role"),
        main_thread_id=_require_text(payload.get("thread_id"), "instance.thread_id"),
        socket_path=Path(_require_text(payload.get("app_server_socket"), "instance.app_server_socket")),
        permissions="buddyswitch-runtime",
        instance_json=instance_json,
        workspace_dir=Path(_require_text(payload.get("workspace_dir"), "instance.workspace_dir")),
        project_workspace_dir=Path(_require_text(raw_project_workspace, "instance.project_workspace_dir")),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    execute = subparsers.add_parser("execute")
    execute.add_argument("--instance-json", required=True)
    execute.add_argument("--instruction-json", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "execute":
        context = context_from_instance_json(Path(args.instance_json))
        instruction = json.loads(args.instruction_json)
        if not isinstance(instruction, dict):
            raise ValueError("instruction json must contain an object")
        print(json.dumps(execute_instruction(context, instruction), ensure_ascii=True))
        return 0
    raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
