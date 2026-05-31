#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.task."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition

_TASK_PRIORITY = ["high", "normal", "low"]
_TASK_REF_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["type", "id"],
    "properties": {
        "type": {
            "type": "string",
            "description": "Reference type.",
            "enum": ["track", "artifact", "message", "comment", "request"],
        },
        "id": {
            "type": "string",
            "description": "Referenced runtime object id.",
        },
        "label": {
            "type": "string",
            "description": "Optional short label for the reference.",
        },
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
        "priority": {
            "type": "string",
            "description": "Task priority.",
            "enum": _TASK_PRIORITY,
        },
        "track_id": {
            "type": ["string", "null"],
            "description": "Optional linked track id for context only.",
        },
        "refs": {
            "type": "array",
            "description": "Optional private references.",
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
        "mode": {
            "type": "string",
            "description": "Switch target mode.",
            "enum": ["existing", "new"],
        },
        "task_id": {
            "type": "string",
            "description": "Existing target task id for mode=existing.",
        },
        "task": {
            **_TASK_PAYLOAD_SCHEMA,
            "description": "New target task body for mode=new.",
        },
    },
}


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id="task",
        title="Task Management",
        description="Read, propose, and confirm active-buddy private task state inside the instance-local taskbox.",
        scope="instance-local active-buddy private taskbox",
        capability_boundary="Only the active buddy's taskbox inside the active instance is readable and writable.",
        object_model=(
            "Tasks live in the active instance taskbox under taskbox/<buddy>. "
            "Each task is a private work item for the active buddy, not shared product state. "
            "task.current reads the canonical TaskSnapshot. task.propose and task.confirm are the only public taskbox mutation actions. "
            "Task refs and track_id are private context links; they do not publish or share those objects."
        ),
        use_when=(
            "You need to understand, start, switch, finish, block, or confirm active-buddy private task state.",
        ),
        do_not_use_when=(
            "You need to change shared track/artifact/message/comment/request state rather than the private taskbox.",
        ),
        actions=(
            ActionDefinition(
                name="current",
                title="task.current",
                description="Read the canonical active-buddy TaskSnapshot from taskbox history and task docs.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": [],
                    "properties": {
                        "history_limit": {
                            "type": "integer",
                            "minimum": 1,
                            "default": 8,
                            "description": "Maximum recent task history lines to return.",
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="read",
                mutates="none",
                required_permission="task.read",
                authority="task.buddy_scope",
                visibility="active-buddy private",
                durability="none",
                result_content_level="TaskSnapshot",
                success_effect="Returns the canonical current task snapshot without mutating taskbox state.",
                failure_state_guarantee="Rejected reads do not mutate taskbox files or shared runtime objects.",
                reads=("instance-local taskbox history", "current active-buddy taskbox task"),
                writes=(),
                does_not_write=(
                    "taskbox task docs",
                    "taskbox history",
                    "shared runtime task objects",
                    "track state",
                    "artifact state",
                    "message state",
                    "comment state",
                    "request state",
                    "buddybox file contents",
                ),
                preconditions=("env.tool role-action policy allows this action for the active role",),
                returns=("snapshot",),
                use_when=("You need the current TaskSnapshot with current task id, status, pending switch confirmation, and recent task history.",),
                do_not_use_when=("You need to mutate task state; use task.propose or task.confirm.",),
                risk_hints={
                    "read_only": True,
                    "destructive": False,
                    "idempotent": True,
                    "open_world": False,
                    "requires_human_approval": False,
                    "external_effect": False,
                },
            ),
            ActionDefinition(
                name="propose",
                title="task.propose",
                description="Propose a task start, switch, finish, or block transition in the active-buddy taskbox.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["type", "reason", "evidence"],
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Task state proposal type.",
                            "enum": ["start", "switch", "finish", "block"],
                        },
                        "task_id": {
                            "type": "string",
                            "description": "Current task id for finish/block.",
                        },
                        "task": {
                            **_TASK_PAYLOAD_SCHEMA,
                            "description": "Task body for type=start.",
                        },
                        "target": _TARGET_SCHEMA,
                        "reason": {
                            "type": "string",
                            "description": "Why this task state change is appropriate.",
                        },
                        "evidence": {
                            "type": "string",
                            "description": "User-visible evidence for the proposal.",
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates="runtime_files",
                required_permission="task.propose",
                authority="task.buddy_scope",
                visibility="active-buddy private",
                durability="durable",
                result_content_level="TaskSnapshot plus changed task or confirmation",
                success_effect="Writes only active-buddy taskbox task docs and history for accepted task proposals.",
                failure_state_guarantee="Rejected proposals do not mutate taskbox files, history, or shared runtime objects.",
                reads=("canonical TaskSnapshot", "instance-local taskbox task docs"),
                writes=("instance-local active-buddy taskbox task", "instance-local taskbox history"),
                does_not_write=(
                    "shared runtime task objects",
                    "track state",
                    "artifact state",
                    "artifact visibility",
                    "message state",
                    "comment state",
                    "request state",
                    "buddybox file contents",
                ),
                preconditions=("env.tool role-action policy allows this action for the active role",),
                returns=("snapshot", "task", "pending_confirmation"),
                use_when=("You need to start a task, request a switch, finish current task work, or mark it blocked.",),
                do_not_use_when=("You only need to inspect task state; use task.current. You need to answer a pending switch; use task.confirm.",),
                risk_hints={
                    "read_only": False,
                    "destructive": False,
                    "idempotent": False,
                    "open_world": False,
                    "requires_human_approval": False,
                    "external_effect": False,
                },
            ),
            ActionDefinition(
                name="confirm",
                title="task.confirm",
                description="Accept or reject the one pending active-buddy task switch confirmation.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["confirmation_id", "decision"],
                    "properties": {
                        "confirmation_id": {
                            "type": "string",
                            "description": "Pending task switch confirmation id.",
                        },
                        "decision": {
                            "type": "string",
                            "description": "Whether to accept or reject the pending switch.",
                            "enum": ["accept", "reject"],
                        },
                        "reason": {
                            "type": "string",
                            "description": "Optional reason for the decision.",
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates="runtime_files",
                required_permission="task.confirm",
                authority="task.buddy_scope",
                visibility="active-buddy private",
                durability="durable",
                result_content_level="TaskSnapshot plus confirmation outcome",
                success_effect="Accepts or rejects a pending task switch and appends taskbox history.",
                failure_state_guarantee="Rejected confirmations do not mutate taskbox files, history, or shared runtime objects.",
                reads=("canonical TaskSnapshot", "instance-local taskbox task docs"),
                writes=("instance-local active-buddy taskbox task", "instance-local taskbox history"),
                does_not_write=(
                    "shared runtime task objects",
                    "track state",
                    "artifact state",
                    "artifact visibility",
                    "message state",
                    "comment state",
                    "request state",
                    "buddybox file contents",
                ),
                preconditions=("env.tool role-action policy allows this action for the active role", "one pending task switch confirmation exists"),
                returns=("snapshot", "task"),
                use_when=("You need to accept or reject the pending task switch confirmation shown by task.current or the task input context.",),
                do_not_use_when=("You need to request a new switch; use task.propose with type=switch.",),
                risk_hints={
                    "read_only": False,
                    "destructive": False,
                    "idempotent": False,
                    "open_world": False,
                    "requires_human_approval": False,
                    "external_effect": False,
                },
            ),
        ),
    )


DEFINITION = _build_definition()
validate_definition(DEFINITION)


def invoke(*, action: str, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
