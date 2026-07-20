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


def _build_definition() -> ToolDefinition:
    task_id_schema = _task_id_schema()
    return ToolDefinition(
        id="task_sys",
        title="Task Sys",
        description="Task Sys actions create, read, and advance actor-owned Task lifecycle state.",
        scope="Actor-owned Task creation, reads, and frame-state updates.",
        capability_boundary=(
            "task_sys.create establishes one Demand-sourced Task through the canonical side lifecycle. Task Sys read "
            "actions inspect actor-owned task state. task_sys.close and task_sys.cancel make legal "
            "terminal transitions; either terminal action may submit Task outcome attention and task_sys.need_parent may "
            "submit or interrupt+submit the parent only through a Task Sys runtime instruction. These actions do not "
            "mutate Demands, send messages, mutate tracks, or write actor private files."
        ),
        object_model=(
            "Task Sys tasks are durable task records with source refs, actor targets, one canonical lifecycle status, "
            "execution facts, and lifecycle events."
        ),
        use_when=(
            "You need to inspect ongoing actor-owned Task Sys tasks or record a legal operation for the active Task Sys side or parent frame.",
        ),
        do_not_use_when=(
            "You need to act directly on IM, Track, artifact, browser, or parent-thread runtime state.",
        ),
        actions=(
            ActionDefinition(
                name="create",
                title="task_sys.create",
                description="Create or replay one Task from one exact Demand revision through the canonical side lifecycle.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["demand_ref", "execution_brief"],
                    "properties": {
                        "demand_ref": {
                            "type": "object",
                            "description": "Opaque Demand snapshot identity selected by the actor.",
                            "additionalProperties": False,
                            "required": ["demand_id", "basis_revision"],
                            "properties": {
                                "demand_id": {
                                    "type": "string",
                                    "description": "Exact actor-owned Demand id selected for execution.",
                                },
                                "basis_revision": {
                                    "type": "integer",
                                    "description": "Exact Demand revision observed when selecting the work.",
                                    "minimum": 1,
                                },
                            },
                        },
                        "execution_brief": {
                            "type": "object",
                            "description": "Self-contained work brief for the Task side frame.",
                            "additionalProperties": False,
                            "required": ["description", "detail"],
                            "properties": {
                                "description": {
                                    "type": "string",
                                    "description": "Concise description of the work to perform.",
                                },
                                "detail": {
                                    "type": "string",
                                    "description": "Concrete detail sufficient to execute the selected Demand snapshot.",
                                },
                            },
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates=MUTATES_RUNTIME_OBJECTS,
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission="task_sys.create",
                authority="task_sys.actor_create",
                visibility="Actor-owned Demand-sourced Task lifecycle",
                durability="durable",
                result_content_level="create/replay outcome, Task lifecycle state, opaque DemandRef, execution facts, and runtime result",
                success_effect="Creates at most one actor Task for the exact Demand snapshot and starts its side frame only when newly created.",
                failure_state_guarantee="Payload, source, active-Task, and authority rejections create no Task and execute no runtime instruction.",
                reads=("task sys task record",),
                writes=("task sys task record", "side turn through Task Sys runtime instruction"),
                does_not_write=("Demands", "parent turns", "messages", "tracks", "artifacts", "actor private files"),
                preconditions=(
                    "env.tool role-action policy allows this action for the active role",
                    "demand_ref identifies one exact observed Demand revision",
                    "the actor has no different active Task",
                ),
                returns=("outcome", "task_id", "task_status", "demand_ref", "execution", "runtime", "state_changed"),
                use_when=("The actor selected one live Demand revision for execution and no different Task is active.",),
                do_not_use_when=(
                    "A Task is already active; continue or finish that Task first.",
                    "You need to organize or terminalize a Demand; use Demand Sys.",
                ),
                risk_hints={
                    "read_only": False,
                    "destructive": False,
                    "idempotent": True,
                    "open_world": False,
                    "requires_human_approval": False,
                    "external_effect": False,
                },
            ),
            ActionDefinition(
                name="list",
                title="task_sys.list",
                description="List active, recoverable, or all actor-owned Task Sys tasks.",
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
                result_content_level="task summaries with canonical lifecycle status, execution, and active/recoverable counts",
                success_effect="Returns actor-owned Task Sys task summaries without changing runtime state.",
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
                use_when=("You need actor-owned Task Sys task summaries, canonical status, or execution state before choosing the next frame action.",),
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
                result_content_level="task detail, canonical lifecycle status, execution, and lifecycle events",
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
                use_when=("You need task_id detail, current lifecycle status, source refs, execution, or events for an actor-owned Task Sys task.",),
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
                success_effect=(
                    "Marks the Task completed, records execution completion metadata, clears active processing, and "
                    "submits outcome attention to the parent for a Demand-sourced Task."
                ),
                failure_state_guarantee=(
                    "Rejected close requests do not mutate Task state. If outcome-attention submission fails after "
                    "the terminal write, the completed Task remains durable and the failure is returned explicitly."
                ),
                reads=("task sys task record",),
                writes=(
                    "task sys task record",
                    "side runtime cleanup when closing from side",
                    "parent turn through Task Sys outcome runtime instruction for Demand-sourced Tasks",
                ),
                does_not_write=("Demands", "messages", "tracks", "artifacts", "actor private files"),
                preconditions=(
                    "env.tool role-action policy allows this action for the active role",
                    "task_id exists",
                    "task status is in_progress.side_processing or in_progress.parent_processing, or already completed",
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
                    "outcome_attention",
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
                name="cancel",
                title="task_sys.cancel",
                description="Cancel an actor-owned Task Sys task from any active canonical lifecycle status.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["task_id"],
                    "properties": {
                        "task_id": task_id_schema,
                        "reason": {
                            "type": "string",
                            "description": "Optional concise reason for cancellation.",
                        },
                    },
                },
                output_schema={"$ref": "ToolResult"},
                kind="write",
                mutates=MUTATES_RUNTIME_OBJECTS,
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission="task_sys.cancel",
                authority="task_sys.task_cancel",
                visibility="Task Sys cancel mutation",
                durability="durable",
                result_content_level="task id, canceled lifecycle status, and execution cancellation result",
                success_effect=(
                    "Marks the Task canceled, records cancellation metadata, clears active processing, and submits "
                    "outcome attention to the parent for a Demand-sourced Task."
                ),
                failure_state_guarantee=(
                    "Rejected cancel requests do not mutate Task state. If outcome-attention submission fails after "
                    "the terminal write, the canceled Task remains durable and the failure is returned explicitly."
                ),
                reads=("task sys task record",),
                writes=(
                    "task sys task record",
                    "side runtime cleanup when canceling from side",
                    "parent turn through Task Sys outcome runtime instruction for Demand-sourced Tasks",
                ),
                does_not_write=("Demands", "messages", "tracks", "artifacts", "actor private files"),
                preconditions=(
                    "env.tool role-action policy allows this action for the active role",
                    "task_id exists",
                    "task status is one of the three canonical in_progress statuses, or already canceled",
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
                    "outcome_attention",
                ),
                use_when=("The actor decides to cancel an active Task Sys task so it stops without completion.",),
                do_not_use_when=(
                    "The task completed successfully; use task_sys.close instead.",
                    "A side frame needs parent work; use task_sys.need_parent instead.",
                ),
                risk_hints={
                    "read_only": False,
                    "destructive": True,
                    "idempotent": True,
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
                    "task status is in_progress.side_processing",
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
