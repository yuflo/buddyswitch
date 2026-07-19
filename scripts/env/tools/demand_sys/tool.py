"""Black-box protocol entrypoint for env.tools.demand_sys."""

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


def _revision(description: str = "Expected current Demand revision.") -> dict[str, Any]:
    return {"type": "integer", "minimum": 1, "description": description}


def _source_refs(description: str) -> dict[str, Any]:
    return {
        "type": "array",
        "description": description,
        "items": {
            "type": "object",
            "description": "One source reference owned by this Demand.",
            "additionalProperties": False,
            "required": ["type", "ref"],
            "properties": {
                "type": _text("Source kind."),
                "ref": {
                    "type": "object",
                    "description": "Source identity data used by Phase 1 actor and artifact sources.",
                    "additionalProperties": False,
                    "required": [],
                    "properties": {
                        "key": _text("Stable source key when the source is actor-originated."),
                        "id": _text("Stable source id when the source is an existing runtime object."),
                    },
                },
            },
        },
    }


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def _action(
    *,
    name: str,
    description: str,
    input_schema: dict[str, Any],
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
        input_schema=input_schema,
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
        failure_state_guarantee="Rejected Demand actions do not mutate Demand state or any other runtime product state.",
        reads=("active actor Demand aggregate",),
        writes=() if read_only else ("active actor Demand aggregate",),
        does_not_write=("Task Sys records", "daemon registrations", "inbound state"),
        preconditions=(
            "env.tool role-action policy allows this action for the active role",
            "all referenced Demands belong to the active actor aggregate",
        ),
        returns=("canonical Demand action response",),
        use_when=(use_when,),
        do_not_use_when=(do_not_use_when,),
        risk_hints={
            "read_only": read_only,
            "destructive": name in {"absorb_into", "mark_duplicate", "supersede", "complete", "cancel"},
            "idempotent": read_only or name in {"create", "complete_check"},
            "open_world": False,
            "requires_human_approval": False,
            "external_effect": False,
        },
    )


def _build_definition() -> ToolDefinition:
    demand_id = _text("Actor-owned Demand id.")
    source_refs = _source_refs("Provenance references for the Demand description and detail.")
    observed = {
        "type": "array",
        "description": "Unique Demand revisions actually observed during this check.",
        "uniqueItems": True,
        "items": {
            "type": "object",
            "description": "One Demand revision observed by the actor.",
            "additionalProperties": False,
            "required": ["demand_id", "revision"],
            "properties": {
                "demand_id": demand_id,
                "revision": _revision("Demand revision actually observed by the actor."),
            },
        },
    }
    child = {
        "type": "object",
        "description": "One new child Demand created by split.",
        "additionalProperties": False,
        "required": ["intake_key", "description", "detail", "source_refs"],
        "properties": {
            "intake_key": _text("Actor-scoped idempotency key for the child Demand."),
            "description": _text("Compact child Demand description."),
            "detail": _text("Detailed child Demand content."),
            "source_refs": source_refs,
        },
    }
    merged_target = {
        "type": "object",
        "description": "Exact target content after absorbing the source Demand.",
        "additionalProperties": False,
        "required": ["description", "detail", "source_refs"],
        "properties": {
            "description": _text("Merged target Demand description."),
            "detail": _text("Merged target Demand detail."),
            "source_refs": source_refs,
        },
    }
    return ToolDefinition(
        id="demand_sys",
        title="Demand Sys",
        description="Demand Sys captures and organizes actor-owned needs independently of Task Sys execution.",
        scope="Actor-owned Demand capture, inspection, checking, organization, and terminal lineage.",
        capability_boundary=(
            "Demand Sys owns only the active actor's Demand aggregate. It does not create or mutate Task Sys tasks, "
            "register daemon work, consume inbound state, or expose cross-actor discovery."
        ),
        object_model=(
            "A Demand is an actor-owned revisioned need with source refs, optional parent and dependency edges, "
            "check acknowledgement, and one optional terminal lineage record."
        ),
        use_when=("You need to capture, inspect, check, organize, or close an actor-owned Demand.",),
        do_not_use_when=("You need to create, advance, hand off, close, or cancel Task Sys execution.",),
        actions=(
            _action(
                name="create",
                description="Create or idempotently replay one actor-owned Demand intake.",
                input_schema=_schema(
                    {
                        "intake_key": _text("Actor-scoped idempotency key for this intake."),
                        "description": _text("Compact Demand description used by live matching."),
                        "detail": _text("Full Demand detail used by detailed matching and actor judgment."),
                        "source_refs": source_refs,
                    },
                    ["intake_key", "description", "detail", "source_refs"],
                ),
                read_only=False,
                result_content_level="state receipt with created Demand id and revision",
                success_effect="Creates one unchecked live Demand or returns an exact idempotent replay receipt.",
                use_when="A new need must enter the active actor's Demand aggregate.",
                do_not_use_when="The intake key already exists but its content must change; use demand_sys.revise.",
            ),
            _action(
                name="revise",
                description="Replace the descriptive content of one live Demand at an expected revision.",
                input_schema=_schema(
                    {
                        "demand_id": demand_id,
                        "expected_revision": _revision(),
                        "description": _text("Replacement compact Demand description."),
                        "detail": _text("Replacement detailed Demand content."),
                        "source_refs": source_refs,
                    },
                    ["demand_id", "expected_revision", "description", "detail"],
                ),
                read_only=False,
                result_content_level="revision change receipt",
                success_effect="Revises description, detail, and optionally source refs while preserving organization state.",
                use_when="A live Demand's meaning or supporting detail has changed.",
                do_not_use_when="The need is a separate Demand or should be merged through lineage.",
            ),
            _action(
                name="list",
                description="List actor-owned live, terminal, or all Demands.",
                input_schema=_schema(
                    {
                        "state": {
                            "type": "string",
                            "enum": ["live", "terminal", "all"],
                            "description": "Demand lifecycle set to list; defaults to live.",
                        }
                    },
                    [],
                ),
                read_only=True,
                result_content_level="canonical Demand records",
                success_effect="Returns the selected actor-owned Demand records without changing state.",
                use_when="You need a complete actor-owned Demand set filtered by live or terminal state.",
                do_not_use_when="You need attention-first checking; use demand_sys.check.",
            ),
            _action(
                name="get",
                description="Get one actor-owned Demand by id.",
                input_schema=_schema({"demand_id": demand_id}, ["demand_id"]),
                read_only=True,
                result_content_level="one canonical Demand record",
                success_effect="Returns one actor-owned Demand without changing state.",
                use_when="You know the Demand id and need its complete current record.",
                do_not_use_when="You need several exact Demand records for detailed comparison; use demand_sys.get_many.",
            ),
            _action(
                name="get_many",
                description="Get several actor-owned Demands in caller-specified order.",
                input_schema=_schema(
                    {
                        "demand_ids": {
                            "type": "array",
                            "uniqueItems": True,
                            "description": "Unique actor-owned Demand ids to return in this order.",
                            "items": demand_id,
                        }
                    },
                    ["demand_ids"],
                ),
                read_only=True,
                result_content_level="ordered canonical Demand records",
                success_effect="Returns the exact requested actor-owned Demands without changing state.",
                use_when="A coarse live-index match needs detailed comparison of a small candidate set.",
                do_not_use_when="You do not yet know candidate ids; use demand_sys.check or demand_sys.list.",
            ),
            _action(
                name="check",
                description="Read unchecked Demand revisions plus the compact live Demand index.",
                input_schema=_schema({}, []),
                read_only=True,
                result_content_level="attention items, live id-description index, and pending count",
                success_effect="Returns all unchecked revisions and a compact live index without acknowledging them.",
                use_when="The actor must review new Demand changes and first-pass match them against live needs.",
                do_not_use_when="You already observed revisions and need to acknowledge them; use demand_sys.complete_check.",
            ),
            _action(
                name="complete_check",
                description="Acknowledge only the exact Demand revisions the actor actually observed.",
                input_schema=_schema({"observed": observed}, ["observed"]),
                read_only=False,
                result_content_level="acknowledged revisions and still-pending observed rows",
                success_effect="Advances checked revisions up to the observed revisions without hiding newer changes.",
                use_when="The actor has completed a Demand check over exact observed revisions.",
                do_not_use_when="The actor has not yet read the current attention set; use demand_sys.check.",
            ),
            _action(
                name="set_parent",
                description="Set or clear the structural parent of one live Demand.",
                input_schema=_schema(
                    {
                        "demand_id": demand_id,
                        "expected_revision": _revision(),
                        "parent_id": {
                            "type": ["string", "null"],
                            "description": "Live parent Demand id, or null to detach.",
                        },
                    },
                    ["demand_id", "expected_revision", "parent_id"],
                ),
                read_only=False,
                result_content_level="relation revision receipt",
                success_effect="Sets one acyclic parent edge or clears the current parent edge.",
                use_when="One Demand is a distinct structural component of another Demand.",
                do_not_use_when="Two intake rows express one need; use demand_sys.absorb_into or mark_duplicate.",
            ),
            _action(
                name="add_dependency",
                description="Add one prerequisite edge to a live Demand.",
                input_schema=_schema(
                    {
                        "demand_id": demand_id,
                        "expected_revision": _revision(),
                        "dependency_id": _text("Live Demand that must be resolved first."),
                    },
                    ["demand_id", "expected_revision", "dependency_id"],
                ),
                read_only=False,
                result_content_level="dependency revision receipt",
                success_effect="Adds one acyclic dependency edge to the Demand.",
                use_when="A distinct Demand cannot be resolved before another live Demand.",
                do_not_use_when="The related need is a structural child rather than a prerequisite.",
            ),
            _action(
                name="remove_dependency",
                description="Remove one prerequisite edge from a live Demand.",
                input_schema=_schema(
                    {
                        "demand_id": demand_id,
                        "expected_revision": _revision(),
                        "dependency_id": _text("Demand id to remove from prerequisites."),
                    },
                    ["demand_id", "expected_revision", "dependency_id"],
                ),
                read_only=False,
                result_content_level="dependency revision receipt",
                success_effect="Removes the selected dependency edge while preserving all other edges.",
                use_when="A previously recorded prerequisite no longer constrains this Demand.",
                do_not_use_when="The dependency still blocks progress or the relation is a parent edge.",
            ),
            _action(
                name="split",
                description="Revise one live Demand and atomically create at least two child Demands.",
                input_schema=_schema(
                    {
                        "demand_id": demand_id,
                        "expected_revision": _revision(),
                        "description": _text("Replacement parent description after decomposition."),
                        "detail": _text("Replacement parent detail after decomposition."),
                        "children": {
                            "type": "array",
                            "minItems": 2,
                            "description": "At least two new structural child Demands.",
                            "items": child,
                        },
                    },
                    ["demand_id", "expected_revision", "description", "detail", "children"],
                ),
                read_only=False,
                result_content_level="parent revision plus created child receipts",
                success_effect="Atomically revises the parent and creates two or more live child Demands.",
                use_when="One broad Demand must become a parent with multiple independently resolvable parts.",
                do_not_use_when="The input is only a supplemental restatement of the same need.",
            ),
            _action(
                name="absorb_into",
                description="Merge one live source Demand into another and terminalize the source as absorbed.",
                input_schema=_schema(
                    {
                        "source_id": _text("Live supplemental Demand to absorb."),
                        "source_revision": _revision("Expected current source Demand revision."),
                        "target_id": _text("Live Demand that will retain the merged need."),
                        "target_revision": _revision("Expected current target Demand revision."),
                        "merged_target": merged_target,
                        "summary": _text("Why the source is part of the same need as the target."),
                    },
                    ["source_id", "source_revision", "target_id", "target_revision", "merged_target", "summary"],
                ),
                read_only=False,
                result_content_level="source and target revision receipts",
                success_effect="Atomically revises the target and records absorbed lineage on the source.",
                use_when="A new Demand supplements the same underlying need as an existing Demand.",
                do_not_use_when="The source remains a distinct component or prerequisite Demand.",
            ),
            _action(
                name="mark_duplicate",
                description="Terminalize one Demand as a duplicate of another live Demand.",
                input_schema=_schema(
                    {
                        "source_id": _text("Duplicate Demand to terminalize."),
                        "source_revision": _revision("Expected current duplicate Demand revision."),
                        "target_id": _text("Canonical live Demand represented by the duplicate."),
                        "summary": _text("Why both Demands express the same need."),
                    },
                    ["source_id", "source_revision", "target_id", "summary"],
                ),
                read_only=False,
                result_content_level="duplicate lineage revision receipt",
                success_effect="Records duplicate lineage on the source without revising the target.",
                use_when="Two Demands express the same need and the target already contains the required content.",
                do_not_use_when="The source adds content that must be merged; use demand_sys.absorb_into.",
            ),
            _action(
                name="supersede",
                description="Terminalize an old Demand as superseded by a live replacement Demand.",
                input_schema=_schema(
                    {
                        "old_id": _text("Old Demand to terminalize."),
                        "old_revision": _revision("Expected current old Demand revision."),
                        "replacement_id": _text("Live Demand that replaces the old need."),
                        "summary": _text("Why the replacement invalidates the old Demand."),
                    },
                    ["old_id", "old_revision", "replacement_id", "summary"],
                ),
                read_only=False,
                result_content_level="superseded lineage revision receipt",
                success_effect="Records superseded lineage on the old Demand without revising the replacement.",
                use_when="A newer Demand replaces rather than supplements the old need.",
                do_not_use_when="Both Demands still express one current need; use absorb_into or mark_duplicate.",
            ),
            _action(
                name="complete",
                description="Terminalize one live Demand as satisfied with summary and evidence refs.",
                input_schema=_schema(
                    {
                        "demand_id": demand_id,
                        "expected_revision": _revision(),
                        "summary": _text("How the Demand was satisfied."),
                        "evidence_refs": _source_refs("Evidence references supporting Demand completion."),
                    },
                    ["demand_id", "expected_revision", "summary", "evidence_refs"],
                ),
                read_only=False,
                result_content_level="completion revision receipt",
                success_effect="Records completed terminal state with summary and evidence refs.",
                use_when="The actor confirms the need itself is satisfied and can cite evidence.",
                do_not_use_when="Only a related Task finished while the Demand remains unsatisfied.",
            ),
            _action(
                name="cancel",
                description="Terminalize one live Demand as no longer requiring satisfaction.",
                input_schema=_schema(
                    {
                        "demand_id": demand_id,
                        "expected_revision": _revision(),
                        "summary": _text("Why the Demand no longer requires satisfaction."),
                    },
                    ["demand_id", "expected_revision", "summary"],
                ),
                read_only=False,
                result_content_level="cancellation revision receipt",
                success_effect="Records canceled terminal state with the actor's summary.",
                use_when="The need has been withdrawn or deliberately abandoned without satisfaction.",
                do_not_use_when="The Demand was satisfied; use demand_sys.complete.",
            ),
        ),
    )


DEFINITION = _build_definition()
validate_definition(DEFINITION)


def invoke(*, action: str, args: dict[str, Any], context: "ToolContext") -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
