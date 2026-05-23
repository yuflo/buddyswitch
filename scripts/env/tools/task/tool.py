#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.task."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition, validate_definition

_TASK_STATUS = ["active", "blocked", "done", "archived"]
_TASK_PRIORITY = ["high", "normal", "low"]
_TASK_REF_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["type"],
    "properties": {
        "type": {
            "type": "string",
            "description": "Reference type.",
        },
        "id": {
            "type": "string",
            "description": "Referenced runtime object id when the ref points at track/artifact/message/comment/request.",
        },
        "logical_name": {
            "type": "string",
            "description": "Referenced buddybox logical name when the ref points at a private buddybox file.",
        },
        "label": {
            "type": "string",
            "description": "Optional short label for the reference.",
        },
    },
}


def _build_definition() -> ToolDefinition:
    return ToolDefinition(
        id="task",
        title="Task Management",
        description="Manage active-buddy private tasks inside the instance-local taskbox.",
        cli_resource="task",
        command="python3 scripts/env/client.py task <action> --payload '<json-object>'",
        scope="instance-local active-buddy private taskbox",
        capability_boundary="Only the active buddy's taskbox inside the active instance is readable and writable.",
        object_model=(
            "Tasks live in the active instance taskbox under taskbox/<buddy>. They are private work items, not shared runtime objects, and may reference tracks, artifacts, messages, comments, requests, or buddybox files without publishing or sharing them."
        ),
        use_when=(
            "You need to create, list, inspect, update, archive, or review history for active-buddy private tasks.",
        ),
        do_not_use_when=(
            "You need to change shared track/artifact/message/comment/request state rather than the private taskbox.",
        ),
        actions=(
            ActionDefinition(
                name="create",
                title="task.create",
                description="Create one instance-local private task in the active buddy taskbox.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task_id", "title"],
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "Task id to create in the active taskbox.",
                        },
                        "title": {
                            "type": "string",
                            "description": "Task title.",
                        },
                        "summary": {
                            "type": "string",
                            "description": "Optional task summary.",
                        },
                        "status": {
                            "type": "string",
                            "description": "Optional initial task status.",
                            "enum": _TASK_STATUS,
                        },
                        "priority": {
                            "type": "string",
                            "description": "Optional initial task priority.",
                            "enum": _TASK_PRIORITY,
                        },
                        "track_id": {
                            "type": "string",
                            "description": "Optional linked track id for context only.",
                        },
                        "refs": {
                            "type": "array",
                            "description": "Optional private structured references for this task.",
                            "items": _TASK_REF_SCHEMA,
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates="runtime_files",
                required_permission="task.create",
                authority="task.buddy_scope",
                visibility="active-buddy private",
                durability="durable",
                result_content_level="task row",
                success_effect="Creates one private taskbox task for the active buddy and appends task history.",
                failure_state_guarantee="Rejected writes do not mutate taskbox files or shared runtime objects.",
                reads=("optional track existence",),
                writes=("instance-local active-buddy taskbox task", "instance-local taskbox history"),
                does_not_write=(
                    "shared runtime task objects",
                    "track state",
                    "artifact state",
                    "message state",
                    "comment state",
                    "request state",
                    "buddybox file contents",
                ),
                preconditions=("task_id is unique inside the active taskbox",),
                returns=("task_id", "task"),
                use_when=("You need to capture a new private task for the active buddy instance.",),
                do_not_use_when=("You need to mutate an existing task; use task.update or task.archive.",),
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
                name="list",
                title="task.list",
                description="List active-buddy private tasks from the instance-local taskbox.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": [],
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "Optional status filter.",
                            "enum": _TASK_STATUS,
                        },
                        "priority": {
                            "type": "string",
                            "description": "Optional priority filter.",
                            "enum": _TASK_PRIORITY,
                        },
                        "track_id": {
                            "type": "string",
                            "description": "Optional linked track id filter.",
                        },
                        "include_archived": {
                            "type": "boolean",
                            "description": "Whether archived tasks should be included.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Optional maximum number of rows to return.",
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
                result_content_level="summary rows",
                success_effect="Returns filtered taskbox task rows ordered by priority, updated_at, and id.",
                failure_state_guarantee="Rejected reads do not mutate taskbox files or shared runtime objects.",
                reads=("instance-local active-buddy taskbox summaries",),
                writes=(),
                does_not_write=(
                    "task state",
                    "track state",
                    "artifact state",
                    "message state",
                    "comment state",
                    "request state",
                    "buddybox file contents",
                ),
                preconditions=("active buddy owns task.read permission",),
                returns=("tasks",),
                use_when=("You need queue triage across private taskbox tasks.",),
                do_not_use_when=("You need one specific task or you need to mutate task state.",),
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
                name="get",
                title="task.get",
                description="Read one active-buddy private task from the instance-local taskbox.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task_id"],
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "Task id to read from the active taskbox.",
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
                result_content_level="task row",
                success_effect="Returns one private taskbox task row by id.",
                failure_state_guarantee="Rejected reads do not mutate taskbox files or shared runtime objects.",
                reads=("one instance-local active-buddy taskbox task",),
                writes=(),
                does_not_write=(
                    "task state",
                    "track state",
                    "artifact state",
                    "message state",
                    "comment state",
                    "request state",
                    "buddybox file contents",
                ),
                preconditions=("task_id references an active-buddy taskbox task",),
                returns=("task",),
                use_when=("You need one specific private task row by id.",),
                do_not_use_when=("You need multi-row filtering or mutation.",),
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
                name="update",
                title="task.update",
                description="Update one active-buddy private task in the instance-local taskbox.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task_id"],
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "Task id to update.",
                        },
                        "title": {
                            "type": "string",
                            "description": "Optional replacement title.",
                        },
                        "summary": {
                            "type": "string",
                            "description": "Optional replacement summary.",
                        },
                        "status": {
                            "type": "string",
                            "description": "Optional replacement status.",
                            "enum": _TASK_STATUS,
                        },
                        "priority": {
                            "type": "string",
                            "description": "Optional replacement priority.",
                            "enum": _TASK_PRIORITY,
                        },
                        "track_id": {
                            "type": "string",
                            "description": "Optional replacement linked track id.",
                        },
                        "refs": {
                            "type": "array",
                            "description": "Optional replacement structured refs.",
                            "items": _TASK_REF_SCHEMA,
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates="runtime_files",
                required_permission="task.update",
                authority="task.buddy_scope",
                visibility="active-buddy private",
                durability="durable",
                result_content_level="task row",
                success_effect="Updates one private taskbox task, maintains lifecycle fields, and appends one history event for a real change.",
                failure_state_guarantee="Rejected writes do not mutate taskbox files or shared runtime objects.",
                reads=("one instance-local active-buddy taskbox task", "optional track existence"),
                writes=("instance-local active-buddy taskbox task", "instance-local taskbox history"),
                does_not_write=(
                    "shared runtime task objects",
                    "track state",
                    "artifact state",
                    "message state",
                    "comment state",
                    "request state",
                    "buddybox file contents",
                ),
                preconditions=("task_id references an active-buddy taskbox task",),
                returns=("task",),
                use_when=("You need to patch task content, priority, refs, or lifecycle state.",),
                do_not_use_when=("You need to create a new task or inspect history without mutation.",),
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
                name="archive",
                title="task.archive",
                description="Archive one active-buddy private task in the instance-local taskbox.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task_id"],
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "Task id to archive.",
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates="runtime_files",
                required_permission="task.archive",
                authority="task.buddy_scope",
                visibility="active-buddy private",
                durability="durable",
                result_content_level="task row",
                success_effect="Archives one private taskbox task and appends history exactly once for the archive lifecycle change.",
                failure_state_guarantee="Rejected writes do not mutate taskbox files or shared runtime objects.",
                reads=("one instance-local active-buddy taskbox task",),
                writes=("instance-local active-buddy taskbox task", "instance-local taskbox history"),
                does_not_write=(
                    "shared runtime task objects",
                    "track state",
                    "artifact state",
                    "message state",
                    "comment state",
                    "request state",
                    "buddybox file contents",
                ),
                preconditions=("task_id references an active-buddy taskbox task",),
                returns=("task",),
                use_when=("You need to remove a task from default taskbox views while preserving history.",),
                do_not_use_when=("You only need a non-archival status change; use task.update.",),
                risk_hints={
                    "read_only": False,
                    "destructive": True,
                    "idempotent": False,
                    "open_world": False,
                    "requires_human_approval": False,
                    "external_effect": False,
                },
            ),
            ActionDefinition(
                name="history",
                title="task.history",
                description="Read recent lifecycle history lines from the active buddy taskbox.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": [],
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Optional maximum number of history entries to return.",
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
                result_content_level="history rows",
                success_effect="Returns recent taskbox history lines for the active buddy instance.",
                failure_state_guarantee="Rejected reads do not mutate taskbox files or shared runtime objects.",
                reads=("instance-local taskbox history",),
                writes=(),
                does_not_write=(
                    "task state",
                    "track state",
                    "artifact state",
                    "message state",
                    "comment state",
                    "request state",
                    "buddybox file contents",
                ),
                preconditions=("active buddy owns task.read permission",),
                returns=("entries",),
                use_when=("You need recent lifecycle history for the active instance taskbox.",),
                do_not_use_when=("You need current task rows rather than lifecycle history.",),
                risk_hints={
                    "read_only": True,
                    "destructive": False,
                    "idempotent": True,
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
