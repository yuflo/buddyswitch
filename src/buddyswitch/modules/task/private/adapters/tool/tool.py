"""Actor-facing Task tool: select work, inspect it, or explicitly cancel it."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from buddyswitch.env.tool_runtime.context import ToolContext

from buddyswitch.env.tool_runtime.definition import (
    ActionDefinition,
    MUTATES_NONE,
    MUTATES_RUNTIME_OBJECTS,
    TASK_REQUIREMENT_FREE,
    ToolDefinition,
    validate_definition,
)
from buddyswitch.modules.task.public.contracts import DemandSelectionResolver


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
        description=(
            "Task Sys owns the Actor's single Demand-bound execution slot and its "
            "binding to one native Codex Goal."
        ),
        scope=(
            "Inspect the current Task slot, create one Demand-bound Task, or "
            "explicitly cancel one active Task."
        ),
        capability_boundary=(
            "Task Sys owns Task records and native Goal binding/reconciliation. "
            "Creating a Task requests idempotent Goal reconciliation through the "
            "instance runtime. Native Goal completion owns successful Task completion. "
            "Task Sys never mutates a Demand."
        ),
        object_model=(
            "A Task records one Demand snapshot reference that was current when "
            "selected, one self-contained Goal objective, one grounded selection "
            "reason, at most one native Goal binding, and an active/completed/canceled "
            "lifecycle."
        ),
        use_when=(
            "You need to inspect the Actor's single Task slot, create its selected "
            "execution commitment, or cancel the active Task.",
        ),
        do_not_use_when=(
            "You need to resolve inbound Demand meaning or complete a satisfied "
            "Demand; use the permitted Demand Sys action for the current thread.",
            "You need to declare native Goal completion; use the Codex Goal lifecycle.",
        ),
        actions=(
            _action(
                name="list",
                description=(
                    "Return Actor-owned Task summaries for the selected lifecycle set "
                    "without changing state."
                ),
                schema=_object_schema(
                    required=[],
                    properties={
                        "status": {
                            "type": "string",
                            "description": (
                                "Task lifecycle set to enumerate: active, terminal, or "
                                "all; defaults to active."
                            ),
                            "enum": ["active", "terminal", "all"],
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Positive maximum number of summaries to return.",
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
                use_when=(
                    "You need to inspect the current Task slot or prior terminal Tasks.",
                ),
                do_not_use_when=(
                    "You need complete content for one known Task; use task_sys.get.",
                ),
            ),
            _action(
                name="get",
                description=(
                    "Return one complete current Actor-owned Task without changing state."
                ),
                schema=_object_schema(
                    required=["task_id"],
                    properties={
                        "task_id": _string(
                            "Exact Actor-owned Task id returned by task_sys.list, "
                            "task_sys.create, or orchestration attention."
                        )
                    },
                ),
                kind="read",
                mutates=MUTATES_NONE,
                authority="task_sys.actor_owned_read",
                reads=("Task record",),
                writes=(),
                success_effect="Returns one Actor-owned Task without changing state.",
                failure_state_guarantee="A rejected read changes no state.",
                returns=("task_id", "task"),
                use_when=(
                    "You need the exact objective, Demand snapshot reference, selection reason, "
                    "Goal binding, status, or terminal result for one Task.",
                ),
                do_not_use_when=(
                    "You only need to inspect the Task slot; use task_sys.list.",
                ),
            ),
            _action(
                name="create",
                description=(
                    "Create or idempotently replay one Task for one current Demand "
                    "reference and request native Goal reconciliation. This action does "
                    "not mutate, satisfy, or reprioritize a Demand."
                ),
                schema=_object_schema(
                    required=["demand_ref", "objective", "selection_reason"],
                    properties={
                        "demand_ref": _string(
                            "Current opaque Demand reference returned by demand_sys.get "
                            "for the selected live Demand; never construct or decode it."
                        ),
                        "objective": _string(
                            "Self-contained execution contract for one native Goal: "
                            "required observable result, exact durable deliverables, "
                            "material boundaries and constraints, completion checks, "
                            "user-facing delivery, and evidence to retain. Exclude Demand "
                            "lifecycle reconciliation and later-work selection."
                        ),
                        "selection_reason": _string(
                            "Grounded decision record explaining why this Demand should "
                            "occupy the single Task slot now after comparison with the "
                            "current live pool. State the decisive facts and timing; do "
                            "not use an unsupported generic priority claim."
                        ),
                    },
                ),
                kind="write",
                mutates=MUTATES_RUNTIME_OBJECTS,
                authority="task_sys.actor_create",
                reads=("current Demand reference", "Actor Task slot"),
                writes=("Task record", "native Goal reconciliation request"),
                success_effect=(
                    "Creates at most one Demand-bound Task, persists its objective and "
                    "selection reason, and reconciles its native Goal without changing "
                    "its Demand; returned Task status and Goal reconciliation are "
                    "authoritative."
                ),
                failure_state_guarantee=(
                    "Invalid Demand, source conflicts, or an occupied Task slot write nothing. A runtime reconciliation "
                    "failure leaves the durable active Task unbound and explicitly recoverable by reconciliation."
                ),
                returns=("outcome", "task_id", "task_status", "demand_ref", "goal_reconciliation", "state_changed"),
                use_when=(
                    "Parent Demand orchestration selected one current Demand for execution and "
                    "the Actor's Task slot is empty.",
                ),
                do_not_use_when=(
                    "A Task is active.",
                    "The selected Demand is not current/live or the execution commitment remains ambiguous.",
                ),
            ),
            _action(
                name="cancel",
                description=(
                    "Terminalize one active Task as canceled and request idempotent native "
                    "Goal cleanup. This action does not cancel, complete, or revise its "
                    "Demand."
                ),
                schema=_object_schema(
                    required=["task_id", "reason"],
                    properties={
                        "task_id": _string("Exact active Actor-owned Task id to stop."),
                        "reason": _string(
                            "Concrete execution-level reason the Task must stop without "
                            "successful Goal completion, such as an invalid objective, "
                            "explicit stop decision, or unrecoverable execution condition."
                        ),
                    },
                ),
                kind="write",
                mutates=MUTATES_RUNTIME_OBJECTS,
                authority="task_sys.actor_cancel",
                reads=("Task record",),
                writes=("Task terminal result", "native Goal reconciliation request"),
                success_effect=(
                    "Terminalizes the active Task as canceled and requests idempotent "
                    "native Goal cleanup without changing its Demand."
                ),
                failure_state_guarantee="A rejected cancellation changes neither Task nor Goal state.",
                returns=("outcome", "task_id", "task_status", "goal_reconciliation", "state_changed"),
                use_when=(
                    "The Actor explicitly decides the active Task must terminate "
                    "without successful Goal completion.",
                ),
                do_not_use_when=(
                    "Work completed successfully, the Demand itself should be canceled, "
                    "or execution is only blocked, paused, usage-limited, or budget-limited.",
                ),
            ),
        ),
    )
    validate_definition(definition)
    return definition


DEFINITION = _build_definition()


def build_invoke(demand_selection_resolver: DemandSelectionResolver):
    if not callable(demand_selection_resolver):
        raise ValueError("Demand selection resolver must be callable")

    def invoke(
        *,
        action: str,
        args: dict[str, Any],
        context: "ToolContext",
    ) -> dict[str, Any]:
        from ._impl import invoke as _invoke

        return _invoke(
            action=action,
            args=args,
            context=context,
            demand_selection_resolver=demand_selection_resolver,
        )

    return invoke
