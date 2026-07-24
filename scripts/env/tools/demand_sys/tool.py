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
        "description": (
            "One or more exact durable references that together prove the need "
            "and its required delivery are satisfied; exclude placeholders, "
            "inaccessible references, and status-only claims."
        ),
        "items": {
            "type": "object",
            "description": "One durable evidence reference owned by its source product.",
            "additionalProperties": False,
            "required": ["type", "ref"],
            "properties": {
                "type": _text("Owning evidence product or kind."),
                "ref": {
                    "type": "object",
                    "description": (
                        "Exact stable identity or semantic key required by the "
                        "owning evidence product."
                    ),
                    "additionalProperties": False,
                    "required": [],
                    "properties": {
                        "key": _text(
                            "Exact stable semantic key required by the owning evidence product."
                        ),
                        "id": _text(
                            "Exact stable identity required by the owning evidence product."
                        ),
                        "task_id": _text(
                            "Exact terminal Task id when type is task_sys.task."
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
    demand_id = _text(
        "Exact Actor-owned Demand id returned by demand_sys.list or a successful "
        "Demand receipt."
    )
    demand_ref = _text(
        "Current opaque reference returned by demand_sys.get for the exact live "
        "Demand revision; never construct or decode it."
    )
    return ToolDefinition(
        id="demand_sys",
        title="Demand Sys",
        description=(
            "Demand Sys owns the active actor's canonical unmet needs independently "
            "of Task execution."
        ),
        scope=(
            "Inspect or express Actor intent to create, replace, satisfy, or withdraw "
            "one canonical Demand."
        ),
        capability_boundary=(
            "Demand Sys exposes six Actor intents. Raw inbound triage, source-provenance "
            "derivation, idempotency, concurrency, storage, and Task/Goal coordination "
            "remain host-owned."
        ),
        object_model=(
            "A Demand is one durable Actor-owned unmet need whose canonical text states "
            "what must become true and how satisfaction can be evidenced. It is live "
            "until explicitly completed or canceled. It is not a Task, execution plan, "
            "progress message, or native Goal."
        ),
        use_when=("You need to inspect or change the active Actor's canonical unmet needs.",),
        do_not_use_when=(
            "You need to triage raw inbound information, execute Task work, or control a native Goal.",
        ),
        actions=(
            _action(
                name="list",
                description=(
                    "Return compact Actor-owned Demand summaries for the selected "
                    "lifecycle set without changing state."
                ),
                schema=_schema(
                    {
                        "state": {
                            "type": "string",
                            "enum": ["live", "terminal", "all"],
                            "description": (
                                "Lifecycle set to enumerate: live, terminal, or all; "
                                "defaults to live."
                            ),
                        }
                    },
                    [],
                ),
                read_only=True,
                result_content_level="compact Demand summaries",
                success_effect="Returns the selected Demand summaries without changing state.",
                use_when="You need to discover or compare the Actor's canonical Demand pool.",
                do_not_use_when="You need full detail or a mutation reference; use demand_sys.get.",
            ),
            _action(
                name="get",
                description=(
                    "Return one complete current Actor-owned Demand and its opaque "
                    "mutation reference without changing state."
                ),
                schema=_schema({"demand_id": demand_id}, ["demand_id"]),
                read_only=True,
                result_content_level="complete Demand plus opaque demand_ref",
                success_effect="Returns one current Demand and its opaque mutation reference.",
                use_when=(
                    "You need one Demand's full current meaning, provenance, lifecycle, "
                    "or mutation reference."
                ),
                do_not_use_when="You only need to compare compact summaries; use demand_sys.list.",
            ),
            _action(
                name="create",
                description=(
                    "Create one durable independent canonical Demand. This action does "
                    "not create Task work or a native Goal."
                ),
                schema=_schema(
                    {
                        "description": _text(
                            "One durable sentence naming the unmet need and desired "
                            "outcome. It remains meaningful across possible Tasks and "
                            "is not an execution step, acknowledgement, status update, "
                            "or solution plan."
                        ),
                        "detail": _text(
                            "Complete satisfaction contract for the need: desired "
                            "observable outcome, material boundaries, binding constraints, "
                            "required user-facing delivery, and evidence that would justify "
                            "Demand completion. Preserve material source meaning; exclude "
                            "Task selection and Goal-lifecycle instructions."
                        ),
                    },
                    ["description", "detail"],
                ),
                read_only=False,
                result_content_level="creation receipt and opaque demand_ref",
                success_effect=(
                    "Creates one durable live Demand with host-derived provenance and "
                    "idempotency; creates no Task or native Goal."
                ),
                use_when=(
                    "The Actor identifies one independent unmet need not represented "
                    "by a live Demand."
                ),
                do_not_use_when=(
                    "The input is untriaged, duplicates or supplements a live Demand, "
                    "or changes a live Demand's canonical meaning."
                ),
            ),
            _action(
                name="revise",
                description=(
                    "Replace the complete canonical meaning of one live Demand. This "
                    "is a full replacement, not a text patch, and it does not change "
                    "Task or Goal state."
                ),
                schema=_schema(
                    {
                        "demand_ref": demand_ref,
                        "description": _text(
                            "Complete replacement one-sentence unmet need and desired outcome."
                        ),
                        "detail": _text(
                            "Complete replacement satisfaction contract, preserving every "
                            "still-valid prior requirement and incorporating the changed "
                            "outcome, boundary, constraint, delivery, or evidence condition."
                        ),
                        "reason": _text(
                            "Grounded explanation of what canonical meaning changed and why "
                            "replacement is correct. This explains the call; it is not "
                            "promised as persisted Demand history."
                        ),
                    },
                    ["demand_ref", "description", "detail", "reason"],
                ),
                read_only=False,
                result_content_level="revision receipt with refreshed opaque demand_ref",
                success_effect=(
                    "Replaces the live Demand's complete canonical meaning while "
                    "preserving host-owned provenance; changes no Task or Goal."
                ),
                use_when=(
                    "The live Demand's intended outcome, boundary, binding constraint, "
                    "required delivery, or satisfaction meaning changed."
                ),
                do_not_use_when=(
                    "New information changes no canonical meaning, belongs to an "
                    "independent need, or remains raw inbound owned by triage."
                ),
            ),
            _action(
                name="complete",
                description=(
                    "Terminalize one live Demand as satisfied with a concrete summary "
                    "and durable evidence references. This action does not change Task "
                    "or Goal state."
                ),
                schema=_schema(
                    {
                        "demand_ref": demand_ref,
                        "summary": _text(
                            "Concrete account of how the latest desired outcome, "
                            "constraints, delivery, and satisfaction conditions were met. "
                            "Name the delivered result rather than only Task or Goal status."
                        ),
                        "evidence_refs": _evidence_refs(),
                    },
                    ["demand_ref", "summary", "evidence_refs"],
                ),
                read_only=False,
                result_content_level="completion receipt with refreshed opaque demand_ref",
                success_effect=(
                    "Terminalizes the Demand as completed and records the supplied "
                    "evidence references; changes no Task or Goal."
                ),
                use_when=(
                    "The latest complete need and every required delivery condition are "
                    "satisfied by verified durable evidence."
                ),
                do_not_use_when=(
                    "Only Task/Goal execution ended, delivery is missing, evidence is "
                    "unverified, or any part of the Demand remains unmet."
                ),
            ),
            _action(
                name="cancel",
                description=(
                    "Terminalize one live Demand as withdrawn, invalidated, or no longer "
                    "required. This action does not change Task or Goal state."
                ),
                schema=_schema(
                    {
                        "demand_ref": demand_ref,
                        "summary": _text(
                            "Concrete withdrawal or invalidating fact explaining why "
                            "satisfaction is no longer required; do not describe successful "
                            "completion."
                        ),
                    },
                    ["demand_ref", "summary"],
                ),
                read_only=False,
                result_content_level="cancellation receipt with refreshed opaque demand_ref",
                success_effect=(
                    "Terminalizes the Demand as canceled; changes no Task or Goal."
                ),
                use_when="The need was withdrawn or deliberately abandoned.",
                do_not_use_when=(
                    "The need was satisfied, remains valid but blocked or lower priority, "
                    "or only its current Task stopped or failed."
                ),
            ),
        ),
    )


DEFINITION = _build_definition()
validate_definition(DEFINITION)


def invoke(*, action: str, args: dict[str, Any], context: "ToolContext") -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
