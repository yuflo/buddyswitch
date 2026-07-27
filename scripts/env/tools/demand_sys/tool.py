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


def _nullable_text(description: str) -> dict[str, Any]:
    return {"type": ["string", "null"], "description": description}


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
        authority=(
            "demand_sys.bound_inbound_side_capability"
            if name == "resolve_inbound"
            else "demand_sys.parent_actor_completion"
            if name == "complete"
            else "demand_sys.actor_owned_aggregate"
        ),
        visibility=(
            "Isolated Demand-triage side bound to one inbound receipt"
            if name == "resolve_inbound"
            else "Parent/Main Actor thread"
            if name == "complete"
            else "Demand state owned by the active actor identity and role"
        ),
        durability="none" if read_only else "durable",
        result_content_level=result_content_level,
        success_effect=success_effect,
        failure_state_guarantee=(
            "Rejected Demand actions do not mutate Demand, Task, daemon, or inbound state."
        ),
        reads=("active actor Demand aggregate",),
        writes=(
            ()
            if read_only
            else (
                "active actor Demand aggregate",
                "bound inbound receipt",
                "bound source reply when decision is handled",
            )
            if name == "resolve_inbound"
            else ("active actor Demand aggregate",)
        ),
        does_not_write=("Task Sys records", "daemon registrations"),
        preconditions=(
            "env.tool role-action policy allows this action for the active role",
            "all referenced Demands belong to the active actor aggregate",
            *(
                (
                    "actual invocation Thread and one-shot capability match the bound side lease",
                )
                if name == "resolve_inbound"
                else (
                    "evidence includes a completed same-Actor Task bound to this Demand",
                    "evidence includes durable delivery proof beyond Task or Goal status",
                )
                if name == "complete"
                else ()
            ),
        ),
        returns=("actor-level Demand response without storage or concurrency fields",),
        use_when=(use_when,),
        do_not_use_when=(do_not_use_when,),
        risk_hints={
            "read_only": read_only,
            "destructive": name in {"resolve_inbound", "complete"},
            "idempotent": read_only or name in {"resolve_inbound", "complete"},
            "open_world": False,
            "requires_human_approval": False,
            "external_effect": name == "resolve_inbound",
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
            "Inspect canonical Demands, resolve one bound inbound on an isolated side, "
            "or complete one satisfied Demand from Parent/Main."
        ),
        capability_boundary=(
            "Demand Sys exposes four actions. Inbound triage is the only create, merge, "
            "revise, or cancel path; Parent/Main can only read and complete. Source "
            "authority, idempotency, concurrency, storage, and Task/Goal coordination "
            "remain host-owned."
        ),
        object_model=(
            "A Demand is one durable Actor-owned unmet need whose canonical text states "
            "what must become true and how satisfaction can be evidenced. It is live "
            "until explicitly completed or canceled. It is not a Task, execution plan, "
            "progress message, or native Goal."
        ),
        use_when=("You need to inspect or reconcile the active Actor's canonical unmet needs.",),
        do_not_use_when=(
            "You need to execute Task work or control a native Goal.",
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
                name="resolve_inbound",
                description=(
                    "Consume the isolated Demand-triage side's one-shot authority and "
                    "commit exactly one resolution for its bound inbound fact. This "
                    "action never creates Task work or controls a native Goal."
                ),
                schema=_schema(
                    {
                        "decision": {
                            "type": "string",
                            "description": (
                                "One final effect for the bound inbound fact: settle without "
                                "action, handle with a reply, create an independent Demand, "
                                "merge compatible intake, revise meaning, or cancel a live Demand."
                            ),
                            "enum": [
                                "no_action_needed",
                                "handled",
                                "create",
                                "merge_intake",
                                "revise",
                                "cancel",
                            ],
                        },
                        "reason": _text(
                            "Grounded explanation of the inbound's relationship to the "
                            "canonical Demand context and why this effect is correct."
                        ),
                        "demand_ref": _nullable_text(
                            "Current opaque live Demand reference for merge_intake, revise, "
                            "or cancel; otherwise null."
                        ),
                        "description": _nullable_text(
                            "Complete post-resolution canonical unmet need for create, "
                            "merge_intake, or revise; otherwise null."
                        ),
                        "detail": _nullable_text(
                            "Complete post-resolution satisfaction contract for create, "
                            "merge_intake, or revise; otherwise null."
                        ),
                        "reply_content": _nullable_text(
                            "Complete bound-source reply for handled; otherwise null."
                        ),
                    },
                    [
                        "decision",
                        "reason",
                        "demand_ref",
                        "description",
                        "detail",
                        "reply_content",
                    ],
                ),
                read_only=False,
                result_content_level="bound receipt resolution and any resulting Demand or reply identity",
                success_effect=(
                    "Atomically settles the bound receipt and applies at most one canonical "
                    "Demand effect; handled also verifies one durable source reply."
                ),
                use_when="This isolated triage side has completed semantic judgment for its bound inbound.",
                do_not_use_when="The caller is Parent/Main, Goal work, or an unbound side thread.",
            ),
            _action(
                name="complete",
                description=(
                    "Terminalize one live Demand as satisfied with a concrete summary "
                    "and durable evidence references, including one completed "
                    "same-Demand Task and delivery proof beyond Task status. This "
                    "action does not change Task or Goal state."
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
        ),
    )


DEFINITION = _build_definition()
validate_definition(DEFINITION)


def invoke(*, action: str, args: dict[str, Any], context: "ToolContext") -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
