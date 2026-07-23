"""Actor-facing Task tool: select work, inspect it, or explicitly cancel it."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext

from env.tool_runtime.definition import (
    ActionDefinition,
    MUTATES_NONE,
    MUTATES_RUNTIME_OBJECTS,
    TASK_REQUIREMENT_FREE,
    ToolDefinition,
    validate_definition,
)


def _object_schema(
    *,
    required: list[str],
    properties: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def _string(description: str) -> dict[str, str]:
    return {"type": "string", "description": description}


def _action(
    *,
    name: str,
    description: str,
    schema: dict[str, Any],
    kind: str,
    mutates: str,
    authority: str,
    reads: tuple[str, ...],
    writes: tuple[str, ...],
    success_effect: str,
    failure_state_guarantee: str,
    returns: tuple[str, ...],
    use_when: tuple[str, ...],
    do_not_use_when: tuple[str, ...],
) -> ActionDefinition:
    return ActionDefinition(
        name=name,
        title=f"task_sys.{name}",
        description=description,
        input_schema=schema,
        output_schema={"$ref": "ToolResult"},
        kind=kind,
        mutates=mutates,
        task_requirement=TASK_REQUIREMENT_FREE,
        required_permission=f"task_sys.{name}",
        authority=authority,
        visibility="Actor-owned Demand-bound Task state",
        durability="durable" if kind == "write" else "none",
        result_content_level="Task identity, Demand reference, objective, native Goal binding, status, and terminal result",
        success_effect=success_effect,
        failure_state_guarantee=failure_state_guarantee,
        reads=reads,
        writes=writes,
        does_not_write=("Demands", "messages", "tracks", "artifacts", "actor private files"),
        preconditions=("The Task belongs to the active Actor.",),
        returns=returns,
        use_when=use_when,
        do_not_use_when=do_not_use_when,
        risk_hints={
            "read_only": kind == "read",
            "destructive": name == "cancel",
            "idempotent": True,
            "open_world": False,
            "requires_human_approval": False,
            "external_effect": False,
        },
    )


def _build_definition() -> ToolDefinition:
    definition = ToolDefinition(
        id="task_sys",
        title="Task Sys",
        description="Expose the minimal Actor intent surface for one Demand-bound Task executed by a native Codex Goal.",
        scope="Actor-owned Task selection, reads, and explicit cancellation.",
        capability_boundary=(
            "Task Sys owns Task records and their binding to one native Goal. Creating a Task requests idempotent "
            "Goal reconciliation through the instance runtime. Native Goal completion, not an Actor close call, "
            "completes the Task. Task Sys never mutates a Demand."
        ),
        object_model=(
            "A Task contains one Demand snapshot reference, one objective, the recorded selection reason, at most "
            "one native Goal binding, and an active/completed/canceled status."
        ),
        use_when=("You need to select one live Demand for execution or inspect/cancel the Actor's Task.",),
        do_not_use_when=(
            "You need to create, revise, complete, or cancel a Demand; use Demand Sys.",
            "You need to declare native Goal completion; use the Codex Goal lifecycle.",
        ),
        actions=(
            _action(
                name="list",
                description="List active, terminal, or all Task records owned by the active Actor.",
                schema=_object_schema(
                    required=[],
                    properties={
                        "status": {
                            "type": "string",
                            "description": "Task set to list.",
                            "enum": ["active", "terminal", "all"],
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of Task summaries to return.",
                            "minimum": 1,
                        },
                    },
                ),
                kind="read",
                mutates=MUTATES_NONE,
                authority="task_sys.actor_owned_read",
                reads=("Task records",),
                writes=(),
                success_effect="Returns Actor-owned Task summaries without changing state.",
                failure_state_guarantee="A rejected read changes no state.",
                returns=("tasks", "active_count", "terminal_count"),
                use_when=("You need to see the current Task slot or prior terminal Tasks.",),
                do_not_use_when=("You know a task_id and require its detail; use task_sys.get.",),
            ),
            _action(
                name="get",
                description="Get one Task record owned by the active Actor.",
                schema=_object_schema(
                    required=["task_id"],
                    properties={"task_id": _string("Task id returned by task_sys.list or task_sys.create.")},
                ),
                kind="read",
                mutates=MUTATES_NONE,
                authority="task_sys.actor_owned_read",
                reads=("Task record",),
                writes=(),
                success_effect="Returns one Actor-owned Task without changing state.",
                failure_state_guarantee="A rejected read changes no state.",
                returns=("task_id", "task"),
                use_when=("You need the exact objective, Goal binding, status, or result for one Task.",),
                do_not_use_when=("You need to scan the Task slot; use task_sys.list.",),
            ),
            _action(
                name="create",
                description="Create or replay one Task for one current opaque Demand reference and request native Goal reconciliation.",
                schema=_object_schema(
                    required=["demand_ref", "objective", "selection_reason"],
                    properties={
                        "demand_ref": _string("Opaque current Demand reference returned by demand_sys.get."),
                        "objective": _string("Self-contained objective the native Codex Goal must complete."),
                        "selection_reason": _string("Why this Demand was selected over the other live Demands now."),
                    },
                ),
                kind="write",
                mutates=MUTATES_RUNTIME_OBJECTS,
                authority="task_sys.actor_create",
                reads=("current Demand reference", "Actor Task slot"),
                writes=("Task record", "native Goal reconciliation request"),
                success_effect="Creates at most one active Task and requests idempotent native Goal reconciliation.",
                failure_state_guarantee=(
                    "Invalid Demand, source conflicts, or an occupied Task slot write nothing. A runtime reconciliation "
                    "failure leaves the durable active Task unbound and explicitly recoverable by reconciliation."
                ),
                returns=("outcome", "task_id", "task_status", "demand_ref", "goal_reconciliation", "state_changed"),
                use_when=("Demand orchestration selected one current Demand and the Task slot is empty.",),
                do_not_use_when=("A different Task is active.", "The Demand objective still needs clarification."),
            ),
            _action(
                name="cancel",
                description="Record the Actor's explicit decision to stop one active Task and request Goal cleanup.",
                schema=_object_schema(
                    required=["task_id", "reason"],
                    properties={
                        "task_id": _string("Active Actor-owned Task id."),
                        "reason": _string("Concrete reason this Task must stop without Goal completion."),
                    },
                ),
                kind="write",
                mutates=MUTATES_RUNTIME_OBJECTS,
                authority="task_sys.actor_cancel",
                reads=("Task record",),
                writes=("Task terminal result", "native Goal reconciliation request"),
                success_effect="Marks the active Task canceled and requests idempotent native Goal cleanup.",
                failure_state_guarantee="A rejected cancellation changes neither Task nor Goal state.",
                returns=("outcome", "task_id", "task_status", "goal_reconciliation", "state_changed"),
                use_when=("The Actor explicitly decides the active Task must stop without completion.",),
                do_not_use_when=("The work is complete; native Goal completion owns successful Task completion.",),
            ),
        ),
    )
    validate_definition(definition)
    return definition


DEFINITION = _build_definition()


def invoke(*, action: str, args: dict[str, Any], context: "ToolContext") -> dict[str, Any]:
    from ._impl import invoke as _invoke

    return _invoke(action=action, args=args, context=context)
