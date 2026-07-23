"""Actor-facing Demand Sys intents."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from env.tool_runtime.context import ToolContext

from env.tool_runtime.definition import ActionDefinition
from env.tool_runtime.definition import MUTATES_NONE
from env.tool_runtime.definition import MUTATES_RUNTIME_OBJECTS
from env.tool_runtime.definition import TASK_REQUIREMENT_FREE
from env.tool_runtime.definition import ToolDefinition
from env.tool_runtime.definition import validate_definition


def _text(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def _evidence_refs() -> dict[str, Any]:
    return {
        "type": "array",
        "description": "Evidence proving that the need itself is satisfied.",
        "items": {
            "type": "object",
            "description": "One evidence reference owned by its source product.",
            "additionalProperties": False,
            "required": ["type", "ref"],
            "properties": {
                "type": _text("Evidence source kind."),
                "ref": {
                    "type": "object",
                    "description": "Evidence identity; Task evidence may name an exact task_id.",
                    "additionalProperties": False,
                    "required": [],
                    "properties": {
                        "key": _text("Stable evidence key when supplied by the source."),
                        "id": _text("Stable evidence id when supplied by the source."),
                        "task_id": _text(
                            "Exact Task Sys task id when type is task_sys.task."
                        ),
                    },
                },
            },
        },
    }


def _action(
    *,
    name: str,
    description: str,
    schema: dict[str, Any],
    read_only: bool,
    result_content_level: str,
    success_effect: str,
    use_when: str,
    do_not_use_when: str,
) -> ActionDefinition:
    return ActionDefinition(
        name=name,
        title=f"demand_sys.{name}",
        description=description,
        input_schema=schema,
        output_schema={"$ref": "ToolResult"},
        kind="read" if read_only else "write",
        mutates=MUTATES_NONE if read_only else MUTATES_RUNTIME_OBJECTS,
        task_requirement=TASK_REQUIREMENT_FREE,
        required_permission=f"demand_sys.{name}",
        authority="demand_sys.actor_owned_aggregate",
        visibility="Demand state owned by the active actor identity and role",
        durability="none" if read_only else "durable",
        result_content_level=result_content_level,
        success_effect=success_effect,
        failure_state_guarantee=(
            "Rejected Demand actions do not mutate Demand, Task, daemon, or inbound state."
        ),
        reads=("active actor Demand aggregate",),
        writes=() if read_only else ("active actor Demand aggregate",),
        does_not_write=("Task Sys records", "daemon registrations", "inbound state"),
        preconditions=(
            "env.tool role-action policy allows this action for the active role",
            "all referenced Demands belong to the active actor aggregate",
        ),
        returns=("actor-level Demand response without storage or concurrency fields",),
        use_when=(use_when,),
        do_not_use_when=(do_not_use_when,),
        risk_hints={
            "read_only": read_only,
            "destructive": name in {"complete", "cancel"},
            "idempotent": read_only or name in {"create", "complete", "cancel"},
            "open_world": False,
            "requires_human_approval": False,
            "external_effect": False,
        },
    )


def _build_definition() -> ToolDefinition:
    demand_id = _text("Actor-owned Demand id returned by demand_sys.list.")
    demand_ref = _text(
        "Opaque current Demand reference returned only by demand_sys.get."
    )
    return ToolDefinition(
        id="demand_sys",
        title="Demand Sys",
        description=(
            "Demand Sys owns the active actor's canonical needs independently of "
            "Task execution."
        ),
        scope="Actor intent to inspect, declare, revise, satisfy, or cancel a Demand.",
        capability_boundary=(
            "Demand Sys exposes six actor intents. Ingress triage, source provenance, "
            "idempotency, concurrency, storage, and Task coordination remain host-owned."
        ),
        object_model=(
            "A Demand is one canonical actor-owned need that is live, completed, or canceled."
        ),
        use_when=("You need to inspect or change the active actor's canonical needs.",),
        do_not_use_when=(
            "You need to triage raw inbound information or execute Task work.",
        ),
        actions=(
            _action(
                name="list",
                description="List compact actor-owned Demand summaries.",
                schema=_schema(
                    {
                        "state": {
                            "type": "string",
                            "enum": ["live", "terminal", "all"],
                            "description": "Lifecycle set to list; defaults to live.",
                        }
                    },
                    [],
                ),
                read_only=True,
                result_content_level="compact Demand summaries",
                success_effect="Returns the selected Demand summaries without changing state.",
                use_when="You need to compare the actor's canonical Demand pool.",
                do_not_use_when="You need full detail or a mutation reference; use demand_sys.get.",
            ),
            _action(
                name="get",
                description="Read one complete actor-owned Demand.",
                schema=_schema({"demand_id": demand_id}, ["demand_id"]),
                read_only=True,
                result_content_level="complete Demand plus opaque demand_ref",
                success_effect="Returns one current Demand and its opaque mutation reference.",
                use_when="You selected a Demand id and need full current content.",
                do_not_use_when="You only need to compare compact summaries; use demand_sys.list.",
            ),
            _action(
                name="create",
                description="Declare one independent new actor-owned Demand.",
                schema=_schema(
                    {
                        "description": _text("Compact statement of the need."),
                        "detail": _text("Full goal, boundary, and constraints."),
                    },
                    ["description", "detail"],
                ),
                read_only=False,
                result_content_level="creation receipt and opaque demand_ref",
                success_effect=(
                    "Creates one Demand, with host-derived provenance and idempotency."
                ),
                use_when="You intentionally identify a new need independent of live Demands.",
                do_not_use_when="Raw inbound information still needs demand-triage judgment.",
            ),
            _action(
                name="revise",
                description="Change the goal, boundary, or constraints of one live Demand.",
                schema=_schema(
                    {
                        "demand_ref": demand_ref,
                        "description": _text("Replacement compact statement."),
                        "detail": _text("Replacement full goal, boundary, and constraints."),
                        "reason": _text("Why this canonical Demand meaning changed."),
                    },
                    ["demand_ref", "description", "detail", "reason"],
                ),
                read_only=False,
                result_content_level="revision receipt with refreshed opaque demand_ref",
                success_effect="Replaces Demand meaning while preserving host-owned provenance.",
                use_when="The canonical need itself changed after rereading it.",
                do_not_use_when="A related inbound fact only supplements the same need; triage owns that merge.",
            ),
            _action(
                name="complete",
                description="Declare that one Demand is satisfied.",
                schema=_schema(
                    {
                        "demand_ref": demand_ref,
                        "summary": _text("How the need itself was satisfied."),
                        "evidence_refs": _evidence_refs(),
                    },
                    ["demand_ref", "summary", "evidence_refs"],
                ),
                read_only=False,
                result_content_level="completion receipt with refreshed opaque demand_ref",
                success_effect="Terminalizes the Demand as completed with exact evidence.",
                use_when="The need itself is satisfied, not merely one related Task.",
                do_not_use_when="The Demand remains unmet after a Task completes.",
            ),
            _action(
                name="cancel",
                description="Declare that one Demand is withdrawn or no longer required.",
                schema=_schema(
                    {
                        "demand_ref": demand_ref,
                        "summary": _text("Why the need no longer requires satisfaction."),
                    },
                    ["demand_ref", "summary"],
                ),
                read_only=False,
                result_content_level="cancellation receipt with refreshed opaque demand_ref",
                success_effect="Terminalizes the Demand as canceled.",
                use_when="The need was withdrawn or deliberately abandoned.",
                do_not_use_when="The need was satisfied; use demand_sys.complete.",
            ),
        ),
    )


DEFINITION = _build_definition()
validate_definition(DEFINITION)


def invoke(*, action: str, args: dict[str, Any], context: "ToolContext") -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
