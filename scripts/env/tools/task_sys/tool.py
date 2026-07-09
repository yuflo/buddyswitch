#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.task_sys."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, TASK_REQUIREMENT_FREE, ToolDefinition, validate_definition
from env.tool_runtime.definition import MUTATES_NONE, MUTATES_RUNTIME_OBJECTS


def _task_id_schema() -> dict[str, str]:
    return {
        "type": "string",
        "description": "Task Sys task id from an actor-owned task_sys.side_frame or task_sys.parent_frame.",
    }


def _task_relation_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "description": "Structured relation option selected during Task Sys relation analysis.",
        "additionalProperties": False,
        "required": ["kind"],
        "properties": {
            "kind": {
                "type": "string",
                "description": "Relation option for this task.",
                "enum": ["independent", "after", "before"],
            },
            "target_task_id": {
                "type": ["string", "null"],
                "description": "Target actor-owned Task Sys task id for after/before; null for independent.",
            },
        },
    }


def _build_definition() -> ToolDefinition:
    task_id_schema = _task_id_schema()
    return ToolDefinition(
        id="task_sys",
        title="Task Sys",
        description="Task Sys actions read actor-owned task state and advance active side or parent frames.",
        scope="Task Sys task reads and frame-state updates for the active actor.",
        capability_boundary=(
            "Task Sys read actions inspect actor-owned task sys task state. task_sys.close completes side or parent "
            "frames; task_sys.need_parent may submit or interrupt+submit the parent only through a Task Sys runtime "
            "instruction. These actions do not send messages, mutate tracks, or write actor private files."
        ),
        object_model=(
            "Task Sys tasks are durable task records with source refs, actor targets, lifecycle status, task_desc, "
            "structured task_relation, execution facts, and lifecycle events."
        ),
        use_when=(
            "You need to inspect ongoing actor-owned Task Sys tasks or record a legal operation for the active Task Sys side or parent frame.",
        ),
        do_not_use_when=(
            "You need to act directly on IM, Track, artifact, browser, or parent-thread runtime state.",
        ),
        actions=(
            ActionDefinition(
                name="list",
                title="task_sys.list",
                description="List active, recoverable, or all actor-owned Task Sys tasks with relation-analysis context.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": [],
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "Task set to list.",
                            "enum": ["active", "recoverable", "all"],
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of tasks to return.",
                            "minimum": 1,
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="read",
                mutates=MUTATES_NONE,
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission="task_sys.list",
                authority="task_sys.actor_owned_read",
                visibility="Actor-owned ongoing Task Sys task summaries",
                durability="none",
                result_content_level="task summaries with lifecycle status, task_desc, task_relation, execution, and active/recoverable counts",
                success_effect="Returns actor-owned Task Sys task summaries for relation analysis without changing runtime state.",
                failure_state_guarantee="Rejected list requests do not mutate task sys state.",
                reads=("task sys task record",),
                writes=(),
                does_not_write=("parent turns", "side turns", "messages", "tracks", "artifacts", "task sys task record"),
                preconditions=(
                    "env.tool role-action policy allows this action for the active role",
                    "status is active, recoverable, or all when provided",
                    "limit is a positive integer when provided",
                ),
                returns=("tasks", "active_count", "recoverable_count"),
                use_when=("You need actor-owned Task Sys task summaries, descriptions, relations, or execution state before choosing the next frame action.",),
                do_not_use_when=("You already know the exact task_id and need full detail; use task_sys.get instead.",),
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
                title="task_sys.get",
                description="Get one actor-owned Task Sys task detail, including lifecycle events.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task_id"],
                    "properties": {
                        "task_id": task_id_schema,
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="read",
                mutates=MUTATES_NONE,
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission="task_sys.get",
                authority="task_sys.actor_owned_read",
                visibility="Actor-owned Task Sys task detail",
                durability="none",
                result_content_level="task detail, relation-analysis fields, execution, and lifecycle events",
                success_effect="Returns one actor-owned Task Sys task detail without changing runtime state.",
                failure_state_guarantee="Rejected get requests do not mutate task sys state.",
                reads=("task sys task record",),
                writes=(),
                does_not_write=("parent turns", "side turns", "messages", "tracks", "artifacts", "task sys task record"),
                preconditions=(
                    "env.tool role-action policy allows this action for the active role",
                    "task_id exists",
                    "task belongs to the active actor",
                ),
                returns=("task_id", "task", "events"),
                use_when=("You need task_id detail, current lifecycle status, desc, relation, source refs, execution, or events for an actor-owned Task Sys task.",),
                do_not_use_when=("You need only a compact set of active ongoing tasks; use task_sys.list instead.",),
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
                name="update_task_analysis",
                title="task_sys.update_task_analysis",
                description="Write the short task description and structured relation selected during Task Sys relation analysis.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task_id", "task_desc", "task_relation"],
                    "properties": {
                        "task_id": task_id_schema,
                        "task_desc": {
                            "type": "string",
                            "description": "Short task description generated from inbound info before side gate; must be under 50 characters.",
                        },
                        "task_relation": _task_relation_schema(),
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates=MUTATES_RUNTIME_OBJECTS,
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission="task_sys.update_task_analysis",
                authority="task_sys.task_analysis_update",
                visibility="Task Sys task relation-analysis mutation",
                durability="durable",
                result_content_level="task id, lifecycle status, task_desc, task_relation, and execution",
                success_effect="Durably updates one actor-owned Task Sys task with task_desc and structured task_relation.",
                failure_state_guarantee="Rejected task-analysis updates do not mutate task sys state.",
                reads=("task sys task record",),
                writes=("task sys task record",),
                does_not_write=("parent turns", "side turns", "messages", "tracks", "artifacts"),
                preconditions=(
                    "env.tool role-action policy allows this action for the active role",
                    "task_id exists",
                    "task belongs to the active actor",
                    "task_desc is non-empty and shorter than 50 characters",
                    "task_relation.kind is independent, after, or before",
                    "after/before target_task_id exists, belongs to the same actor, and is not the current task",
                ),
                returns=("task_id", "task_status", "task_desc", "task_relation", "execution", "state_changed"),
                use_when=("A side or parent frame has generated relation analysis and must persist the selected task_desc and task_relation before deciding the final frame action.",),
                do_not_use_when=(
                    "You only need to inspect relation context; use task_sys.list or task_sys.get.",
                    "You need to close or hand off the task; use task_sys.close or task_sys.need_parent after analysis is recorded.",
                ),
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
                name="close",
                title="task_sys.close",
                description="Close a Task Sys task after the active side or parent frame has completed the required frame work.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task_id"],
                    "properties": {
                        "task_id": task_id_schema,
                        "summary": {
                            "type": "string",
                            "description": "Optional concise summary of how the active frame completed the task.",
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates=MUTATES_RUNTIME_OBJECTS,
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission="task_sys.close",
                authority="task_sys.task_close",
                visibility="Task Sys close mutation",
                durability="durable",
                result_content_level="task id, lifecycle status, and execution completion result",
                success_effect="Marks the task completed, records execution completion metadata, and clears active processing.",
                failure_state_guarantee="Rejected close requests do not mutate task sys state.",
                reads=("task sys task record",),
                writes=("task sys task record",),
                does_not_write=("parent turns", "side turns", "messages", "tracks", "artifacts"),
                preconditions=(
                    "env.tool role-action policy allows this action for the active role",
                    "task_id exists",
                    "task lifecycle status is in_progress with execution.processor side or parent, or already completed",
                ),
                returns=(
                    "task_id",
                    "outcome",
                    "task_status",
                    "state_changed",
                    "processor",
                    "side_thread_id",
                    "side_cleanup",
                    "execution_result",
                ),
                use_when=("The active side or parent frame completed the required frame work and the task should be closed.",),
                do_not_use_when=(
                    "A side frame needs parent work; use task_sys.need_parent instead.",
                    "You only need to inspect current task state; use task_sys.list or task_sys.get.",
                ),
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
                name="need_parent",
                title="task_sys.need_parent",
                description="Record that side processing needs parent-thread work, with interrupt as a handoff parameter.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task_id", "params"],
                    "properties": {
                        "task_id": task_id_schema,
                        "params": {
                            "type": "object",
                            "description": "Parent handoff parameters. Shape: object.",
                            "additionalProperties": False,
                            "required": [],
                            "properties": {
                                "parent_frame_context": {
                                    "type": "object",
                                    "description": "Task context needed by the parent frame. Shape: object.",
                                    "additionalProperties": False,
                                    "required": [],
                                    "properties": {},
                                },
                                "interrupt": {
                                    "type": "boolean",
                                    "description": "Whether Task Sys should request interrupt before parent submit.",
                                },
                                "ordering": {
                                    "type": "object",
                                    "description": "Simple ordering or priority metadata. Shape: object.",
                                    "additionalProperties": False,
                                    "required": [],
                                    "properties": {},
                                },
                            },
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates=MUTATES_RUNTIME_OBJECTS,
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission="task_sys.need_parent",
                authority="task_sys.side_need_parent",
                visibility="Task Sys parent handoff mutation",
                durability="durable",
                result_content_level="task id, execution handoff, and parent runtime result",
                success_effect="Records normalized execution handoff and executes the Task Sys parent runtime instruction.",
                failure_state_guarantee="Rejected parent-handoff requests do not mutate task sys state.",
                reads=("task sys task record",),
                writes=("task sys task record", "parent turn through Task Sys runtime instruction"),
                does_not_write=("side turns", "messages", "tracks", "artifacts"),
                preconditions=(
                    "env.tool role-action policy allows this action for the active role",
                    "task_id exists",
                    "task lifecycle status is in_progress with execution.processor side",
                    "params.interrupt is a boolean when provided",
                ),
                returns=(
                    "task_id",
                    "outcome",
                    "task_status",
                    "state_changed",
                    "processor",
                    "side_thread_id",
                    "side_cleanup",
                    "execution_handoff",
                    "parent_instruction",
                    "parent_runtime",
                ),
                use_when=("The side processor determines parent-thread handoff work is required, with interrupt set only as a handoff param.",),
                do_not_use_when=(
                    "The task was handled without parent involvement; use task_sys.close instead.",
                    "You only need to inspect current task state; use task_sys.list or task_sys.get.",
                ),
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


def invoke(*, action: str, args: dict[str, Any], context: "ToolContext") -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
