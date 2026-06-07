#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.task."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, TASK_REQUIREMENT_FREE, ToolDefinition, validate_definition
from env.tool_runtime.definition import MUTATES_NONE, MUTATES_RUNTIME_FILES

_TASK_PRIORITY = ["high", "normal", "low"]
_TASK_REF_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["type", "id"],
    "properties": {
        "type": {
            "type": "string",
            "description": "Private task reference type.",
            "enum": ["track", "artifact", "message", "comment", "request"],
        },
        "id": {"type": "string", "description": "Referenced runtime object id."},
        "label": {"type": "string", "description": "Optional short label for the private reference."},
    },
}
_TASK_ORIGIN_SCHEMA = {
    "type": "object",
    "description": "Private origin context for where the task came from.",
    "additionalProperties": False,
    "required": ["type"],
    "properties": {
        "type": {
            "type": "string",
            "description": "Origin category for the captured work demand.",
            "enum": ["manual", "user_input", "track", "artifact", "message", "comment", "request"],
        },
        "id": {"type": "string", "description": "Optional origin object or turn id."},
        "label": {"type": "string", "description": "Optional origin label."},
    },
}
_TASK_PAYLOAD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "body"],
    "properties": {
        "title": {"type": "string", "description": "Task title."},
        "summary": {"type": "string", "description": "Short task summary."},
        "body": {"type": "string", "description": "Detailed task body."},
        "priority": {"type": "string", "description": "Task priority.", "enum": _TASK_PRIORITY},
        "origin": _TASK_ORIGIN_SCHEMA,
        "track_id": {"type": ["string", "null"], "description": "Optional private track context link."},
        "refs": {
            "type": "array",
            "description": "Private context refs; task operations do not mutate referenced objects.",
            "items": _TASK_REF_SCHEMA,
        },
    },
}
_TARGET_SCHEMA = {
    "type": "object",
    "description": "Task switch target.",
    "additionalProperties": False,
    "required": ["mode"],
    "properties": {
        "mode": {"type": "string", "description": "Switch target mode.", "enum": ["existing", "new"]},
        "task_id": {"type": "string", "description": "Existing captured or blocked target task id for mode=existing."},
        "task": {**_TASK_PAYLOAD_SCHEMA, "description": "New target task body for mode=new."},
    },
}
_NO_SIBLING_WRITES = (
    "track state",
    "artifact state",
    "artifact visibility",
    "message state",
    "comment state",
    "request state",
    "actor_private file contents",
)
_TASK_WRITES = ("instance-local active actor taskbox task docs", "instance-local taskbox history")


def _read_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [],
        "properties": {
            "history_limit": {
                "type": "integer",
                "minimum": 1,
                "default": 8,
                "description": "Maximum recent task events to include in the TaskViewModel.",
            },
        },
    }


def _action(
    *,
    name: str,
    title: str,
    description: str,
    input_schema: dict[str, Any],
    kind: str,
    mutates: str,
    required_permission: str,
    durability: str,
    result_content_level: str,
    success_effect: str,
    failure_state_guarantee: str,
    reads: tuple[str, ...],
    writes: tuple[str, ...],
    returns: tuple[str, ...],
    use_when: tuple[str, ...],
    do_not_use_when: tuple[str, ...],
    read_only: bool,
) -> ActionDefinition:
    return ActionDefinition(
        name=name,
        title=title,
        description=description,
        input_schema=input_schema,
        output_schema={"$ref": "ToolResult"},
        kind=kind,
        mutates=mutates,
        task_requirement=TASK_REQUIREMENT_FREE,
        required_permission=required_permission,
        authority="task.role_scope",
        visibility="active actor private",
        durability=durability,
        result_content_level=result_content_level,
        success_effect=success_effect,
        failure_state_guarantee=failure_state_guarantee,
        reads=reads,
        writes=writes,
        does_not_write=(
            *(("taskbox task docs", "taskbox history") if read_only else ()),
            "shared runtime task objects",
            *_NO_SIBLING_WRITES,
        ),
        preconditions=("env.tool role-action policy allows this action for the active role",),
        returns=returns,
        use_when=use_when,
        do_not_use_when=do_not_use_when,
        risk_hints={
            "read_only": read_only,
            "destructive": False,
            "idempotent": read_only,
            "open_world": False,
            "requires_human_approval": False,
            "external_effect": False,
        },
    )


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id="task",
        title="Task Management",
        description="Read and mutate active actor private task state through explicit Task Operations.",
        scope="instance-local active actor private taskbox",
        capability_boundary="Only active actor private taskbox task docs and history inside the active instance are readable or writable.",
        object_model=(
            "Tasks are active actor private work items stored in taskbox. Task Core owns task facts and history; "
            "Task Operations own capture, select, switch, progress, checkout, and review semantics. "
            "Task refs are private context links and do not publish, share, or mutate referenced tracks, artifacts, messages, comments, requests, or actor_private files. "
            "All reads and writes return a TaskViewModel for innerTUI rendering."
        ),
        use_when=("You need current, shelf, switch, progress, checkout, or review state for active actor private work.",),
        do_not_use_when=("You need to change shared track/artifact/message/comment/request state rather than private taskbox state.",),
        actions=(
            _action(
                name="current",
                title="task.current",
                description="Read the current active actor TaskViewModel without mutating taskbox state.",
                input_schema=_read_schema(),
                kind="read",
                mutates=MUTATES_NONE,
                required_permission="task.read",
                durability="none",
                result_content_level="TaskViewModel",
                success_effect="Returns TaskViewModel with current anchor, shelf, pending switch, evidence, checkout cue, warnings, and recent taskbox history.",
                failure_state_guarantee="Rejected reads do not mutate taskbox files or shared runtime objects.",
                reads=("instance-local taskbox history", "instance-local active actor taskbox task docs"),
                writes=(),
                returns=("view",),
                use_when=("You need the current TaskViewModel with current anchor, shelf, pending switch, and recent history.",),
                do_not_use_when=("You need to mutate task state; use capture, select, switch_request, switch_confirm, progress, checkout, or review.",),
                read_only=True,
            ),
            _action(
                name="capture",
                title="task.capture",
                description="Capture a work demand onto the task shelf without changing the current anchor.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task"],
                    "properties": {
                        "task": {**_TASK_PAYLOAD_SCHEMA, "description": "Captured task body."},
                        "reason": {"type": "string", "description": "Why this work should be captured."},
                        "evidence": {"type": "string", "description": "Actor-visible evidence behind the capture."},
                    },
                },
                kind="write",
                mutates=MUTATES_RUNTIME_FILES,
                required_permission="task.capture",
                durability="durable",
                result_content_level="TaskViewModel plus captured task",
                success_effect="Creates a captured shelf task and appends task.captured in taskbox history.",
                failure_state_guarantee="Rejected captures do not mutate taskbox files, taskbox history, or sibling runtime objects.",
                reads=("instance-local taskbox task docs",),
                writes=_TASK_WRITES,
                returns=("view", "task", "task_id"),
                use_when=("You need to capture a new work demand for later on the shelf without replacing current active work.",),
                do_not_use_when=("You need to make captured work current; use task.select when no active anchor exists.",),
                read_only=False,
            ),
            _action(
                name="select",
                title="task.select",
                description="Select one captured or blocked task as the active current anchor when no active anchor exists.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task_id"],
                    "properties": {
                        "task_id": {"type": "string", "description": "Captured or blocked task id to select."},
                        "reason": {"type": "string", "description": "Why this task should become active."},
                    },
                },
                kind="write",
                mutates=MUTATES_RUNTIME_FILES,
                required_permission="task.select",
                durability="durable",
                result_content_level="TaskViewModel plus selected task",
                success_effect="Marks a captured or blocked task active and appends task.selected in taskbox history.",
                failure_state_guarantee="Rejected selects do not mutate taskbox files, taskbox history, or sibling runtime objects.",
                reads=("TaskViewModel", "instance-local taskbox task docs"),
                writes=_TASK_WRITES,
                returns=("view", "task", "task_id"),
                use_when=("You need to select captured shelf work or blocked work as active current work and there is no active current anchor.",),
                do_not_use_when=("There is already active current work; use task.switch_request instead.",),
                read_only=False,
            ),
            _action(
                name="switch_request",
                title="task.switch_request",
                description="Request a pending switch away from the active current anchor without changing current work.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["target", "reason"],
                    "properties": {
                        "target": _TARGET_SCHEMA,
                        "reason": {"type": "string", "description": "Why a switch is being requested."},
                        "evidence": {"type": "string", "description": "Actor-visible evidence behind the switch request."},
                    },
                },
                kind="write",
                mutates=MUTATES_RUNTIME_FILES,
                required_permission="task.switch_request",
                durability="durable",
                result_content_level="TaskViewModel plus pending switch",
                success_effect="Appends task.switch.requested with a pending confirmation while keeping the current anchor unchanged.",
                failure_state_guarantee="Rejected switch requests do not mutate taskbox files, taskbox history, or sibling runtime objects.",
                reads=("TaskViewModel", "instance-local taskbox task docs"),
                writes=("instance-local taskbox history",),
                returns=("view", "pending_switch"),
                use_when=("You need to create a pending switch from current active work to captured, blocked, or new target work.",),
                do_not_use_when=("There is no active current anchor, or you are answering an existing confirmation; use select or switch_confirm.",),
                read_only=False,
            ),
            _action(
                name="switch_confirm",
                title="task.switch_confirm",
                description="Accept or reject one pending task switch confirmation.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["confirmation_id", "decision"],
                    "properties": {
                        "confirmation_id": {"type": "string", "description": "Pending task switch confirmation id."},
                        "decision": {"type": "string", "description": "Whether to accept or reject the pending switch.", "enum": ["accept", "reject"]},
                        "reason": {"type": "string", "description": "Reason for the switch confirmation decision."},
                    },
                },
                kind="write",
                mutates=MUTATES_RUNTIME_FILES,
                required_permission="task.switch_confirm",
                durability="durable",
                result_content_level="TaskViewModel plus switch result",
                success_effect="Accept changes current anchor or reject keeps it; both clear pending switch through taskbox history.",
                failure_state_guarantee="Rejected switch confirmations do not mutate taskbox files, taskbox history, or sibling runtime objects.",
                reads=("TaskViewModel", "instance-local taskbox task docs"),
                writes=_TASK_WRITES,
                returns=("view", "task"),
                use_when=("You need to accept or reject the pending switch confirmation shown in TaskViewModel.",),
                do_not_use_when=("You need to request a new switch; use task.switch_request.",),
                read_only=False,
            ),
            _action(
                name="progress",
                title="task.progress",
                description="Append progress evidence and refs to the active current task.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task_id"],
                    "properties": {
                        "task_id": {"type": "string", "description": "Active current task id."},
                        "summary": {"type": "string", "description": "Updated progress summary."},
                        "evidence": {"type": "string", "description": "Actor-visible evidence of progress."},
                        "refs": {"type": "array", "description": "Private evidence refs to append.", "items": _TASK_REF_SCHEMA},
                    },
                },
                kind="write",
                mutates=MUTATES_RUNTIME_FILES,
                required_permission="task.progress",
                durability="durable",
                result_content_level="TaskViewModel plus updated task",
                success_effect="Updates current task progress summary/refs and appends task.progress.appended with evidence.",
                failure_state_guarantee="Rejected progress updates do not mutate taskbox files, taskbox history, or sibling runtime objects.",
                reads=("TaskViewModel", "instance-local taskbox task docs"),
                writes=_TASK_WRITES,
                returns=("view", "task", "task_id"),
                use_when=("You need to record progress, evidence, or refs for current active work.",),
                do_not_use_when=("You need to end the work block; use task.checkout.",),
                read_only=False,
            ),
            _action(
                name="checkout",
                title="task.checkout",
                description="End a work block as continue, finish, or block for the active current task.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task_id", "next"],
                    "properties": {
                        "task_id": {"type": "string", "description": "Active current task id."},
                        "next": {"type": "string", "description": "Checkout choice.", "enum": ["continue", "finish", "block"]},
                        "summary": {"type": "string", "description": "Progress summary for continued work."},
                        "evidence": {"type": "string", "description": "Evidence required when next=finish."},
                        "reason": {"type": "string", "description": "Reason required when next=block."},
                        "refs": {"type": "array", "description": "Private evidence refs.", "items": _TASK_REF_SCHEMA},
                    },
                },
                kind="write",
                mutates=MUTATES_RUNTIME_FILES,
                required_permission="task.checkout",
                durability="durable",
                result_content_level="TaskViewModel plus checked-out task",
                success_effect="Appends checkout, finished, or blocked taskbox event and updates the current task status when required.",
                failure_state_guarantee="Rejected checkouts do not mutate taskbox files, taskbox history, or sibling runtime objects.",
                reads=("TaskViewModel", "instance-local taskbox task docs"),
                writes=_TASK_WRITES,
                returns=("view", "task", "task_id"),
                use_when=("You need to checkpoint current work as continue, finish it with evidence, or block it with a reason.",),
                do_not_use_when=("You need to switch to another task; use switch_request and switch_confirm.",),
                read_only=False,
            ),
            _action(
                name="review",
                title="task.review",
                description="Review captured, blocked, pending, and stale task cues without changing state by default.",
                input_schema=_read_schema(),
                kind="read",
                mutates=MUTATES_NONE,
                required_permission="task.review",
                durability="none",
                result_content_level="TaskViewModel",
                success_effect="Returns TaskViewModel review cues for captured shelf work, blocked work, pending switch, warnings, and recent history.",
                failure_state_guarantee="Rejected reviews do not mutate taskbox files or shared runtime objects.",
                reads=("instance-local taskbox history", "instance-local active actor taskbox task docs"),
                writes=(),
                returns=("view",),
                use_when=("You need to review captured shelf tasks, blocked tasks, pending switch state, or stale work cues.",),
                do_not_use_when=("You need to mutate task state; use capture, select, switch_request, switch_confirm, progress, or checkout.",),
                read_only=True,
            ),
        ),
    )


DEFINITION = _build_definition()
validate_definition(DEFINITION)


def invoke(*, action: str, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
