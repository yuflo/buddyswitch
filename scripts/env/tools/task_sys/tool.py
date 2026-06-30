#!/usr/bin/env python3
"""Black-box protocol entrypoint for env.tools.task_sys."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, TASK_REQUIREMENT_FREE, ToolDefinition, validate_definition
from env.tool_runtime.definition import MUTATES_RUNTIME_OBJECTS


def _build_definition() -> ToolDefinition:
    task_id_schema = {
        "type": "string",
        "description": "Task Sys task id from the active task_sys.side_frame, task_sys.parent_frame, or task_sys.checkpoint.",
    }
    return ToolDefinition(
        id="task_sys",
        title="Task Sys",
        description="Task Sys actions update the active Task Sys frame: close side/parent tasks, request parent handoff from side, or update checkpoints.",
        scope="Task Sys frame-state updates for the active actor.",
        capability_boundary=(
            "Task Sys actions update task sys task state. task_sys.close completes side or parent frames; task_sys.need_parent may submit "
            "or interrupt+submit the parent only through a Task Sys runtime instruction. These actions do not send messages, mutate tracks, "
            "or write actor private files."
        ),
        object_model="Task Sys tasks are durable task records with source refs, actor targets, close results, side handoff results, and optional parent handoff params.",
        use_when=(
            "You are processing a task_sys.side_frame, task_sys.parent_frame, or task_sys.checkpoint and need to record the legal Task Sys operation for that frame.",
        ),
        do_not_use_when=(
            "You need to act directly on IM, Track, artifact, browser, or parent-thread runtime state.",
        ),
        actions=(
            ActionDefinition(
                name="close",
                title="task_sys.close",
                description="Close a Task Sys task after the active side or parent frame has completed the required source-bound work.",
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
                result_content_level="task id and state transition",
                success_effect="Marks the task closed, records close metadata, and clears active processing.",
                failure_state_guarantee="Rejected close requests do not mutate task sys state.",
                reads=("task sys task record",),
                writes=("task sys task record",),
                does_not_write=("parent turns", "side turns", "messages", "tracks", "artifacts"),
                preconditions=(
                    "env.tool role-action policy allows this action for the active role",
                    "task_id exists",
                    "task is in side_processing, parent_processing, or already closed status",
                ),
                returns=(
                    "task_id",
                    "outcome",
                    "task_status",
                    "state_changed",
                    "processor",
                    "side_thread_id",
                    "side_cleanup",
                    "close_result",
                ),
                use_when=("The active side or parent frame completed the source-bound work and the task should be closed.",),
                do_not_use_when=(
                    "A side frame needs parent work; use task_sys.need_parent instead.",
                    "You are processing a checkpoint frame; use task_sys.checkpoint_update instead.",
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
                                "relation": {
                                    "type": "string",
                                    "description": "How this parent request relates to the current task.",
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
                result_content_level="task id, parent handoff params, and parent runtime result",
                success_effect="Records normalized handoff params and executes the Task Sys parent runtime instruction.",
                failure_state_guarantee="Rejected parent-handoff requests do not mutate task sys state.",
                reads=("task sys task record",),
                writes=("task sys task record", "parent turn through Task Sys runtime instruction"),
                does_not_write=("side turns", "messages", "tracks", "artifacts"),
                preconditions=(
                    "env.tool role-action policy allows this action for the active role",
                    "task_id exists",
                    "task is in side_processing status",
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
                    "side_result",
                    "parent_handoff_params",
                    "parent_instruction",
                    "parent_runtime",
                ),
                use_when=("The side processor determines parent-thread handoff work is required, with interrupt set only as a handoff param.",),
                do_not_use_when=("The task was handled without parent involvement; use task_sys.close instead.",),
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
                name="checkpoint_update",
                title="task_sys.checkpoint_update",
                description="Update one Task Sys checkpoint frame with the actor's chosen checkpoint outcome.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task_id", "outcome"],
                    "properties": {
                        "task_id": task_id_schema,
                        "outcome": {
                            "type": "string",
                            "description": "Checkpoint update outcome.",
                            "enum": ["close", "continue"],
                        },
                        "summary": {
                            "type": "string",
                            "description": "Optional concise checkpoint update summary.",
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates=MUTATES_RUNTIME_OBJECTS,
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission="task_sys.checkpoint_update",
                authority="task_sys.checkpoint",
                visibility="Task Sys checkpoint mutation",
                durability="durable",
                result_content_level="task id, checkpoint update, and next checkpoint frame",
                success_effect="Records the checkpoint update and returns the next Task Sys checkpoint frame.",
                failure_state_guarantee="Rejected checkpoint updates do not mutate task sys state.",
                reads=("task sys task record",),
                writes=("task sys task record",),
                does_not_write=("parent turns", "side turns", "messages", "tracks", "artifacts"),
                preconditions=(
                    "env.tool role-action policy allows this action for the active role",
                    "task_id exists",
                    "task is in checkpoint status",
                    "outcome is close or continue",
                ),
                returns=("task_id", "outcome", "frame"),
                use_when=("You are processing a task_sys.checkpoint frame and need to record the chosen checkpoint outcome update.",),
                do_not_use_when=("You are processing a task_sys.side_frame; use task_sys.close or task_sys.need_parent instead.",),
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
