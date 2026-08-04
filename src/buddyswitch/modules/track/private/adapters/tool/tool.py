"""Track-owned black-box Tool entrypoint."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from buddyswitch.foundation.tool_runtime.context import ToolContext
from buddyswitch.foundation.tool_runtime.definition import ActionDefinition, TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED, TASK_REQUIREMENT_FREE, ToolDefinition, validate_definition
from buddyswitch.modules.track.public.contracts import (
    ReadReferenceMetadata,
    ResolvePublicationCandidate,
)

_NOW_SCHEMA = {
    "type": "object",
    "description": "Current next step and optional blocker for the Track.",
    "additionalProperties": False,
    "required": ["next"],
    "properties": {
        "next": {"type": "string", "description": "Non-empty next action or current focus."},
        "blocker": {"type": ["string", "null"], "description": "Current blocker text, or null when unblocked."},
    },
    "examples": [{"next": "Ask owner to judge proof.", "blocker": None}],
}

_TEXT_LIST_SCHEMA = {
    "type": "array",
    "description": "List of non-empty text rows.",
    "items": {"type": "string"},
}

_REFS_ITEM_SCHEMA = {
    "type": "object",
    "description": "Artifact reference attached to this update row.",
    "additionalProperties": False,
    "required": ["type", "id"],
    "properties": {
        "type": {"type": "string", "description": "Reference type; Track updates only accept artifact refs.", "enum": ["artifact"]},
        "id": {"type": "string", "description": "Artifact id referenced by this update."},
    },
}

_MENTIONED_IDENTITIES_SCHEMA = {
    "type": "array",
    "description": "Optional list of actor identity ids to mention in the Track comment.",
    "items": {
        "type": "string",
        "description": "Mentioned actor identity id.",
    },
}


def _object_schema(*, required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def _track_id_property(description: str = "Existing non-archived Track id.") -> dict[str, str]:
    return {"type": "string", "description": description}


def _risk(*, read_only: bool = False, destructive: bool = False, idempotent: bool = False) -> dict[str, bool]:
    return {
        "read_only": read_only,
        "destructive": destructive,
        "idempotent": idempotent,
        "open_world": False,
        "requires_human_approval": False,
        "external_effect": False,
    }


def _action(
    *,
    name: str,
    description: str,
    input_schema: dict[str, Any],
    kind: str,
    mutates: str,
    task_requirement: str,
    required_permission: str,
    authority: str,
    visibility: str,
    durability: str,
    result_content_level: str,
    success_effect: str,
    failure_state_guarantee: str,
    reads: tuple[str, ...],
    writes: tuple[str, ...],
    does_not_write: tuple[str, ...],
    preconditions: tuple[str, ...],
    returns: tuple[str, ...],
    use_when: tuple[str, ...],
    do_not_use_when: tuple[str, ...],
    risk_hints: dict[str, bool],
) -> ActionDefinition:
    return ActionDefinition(
        name=name,
        title=f"track.{name}",
        description=description,
        input_schema=input_schema,
        output_schema={"$ref": "ToolResult"},
        kind=kind,
        mutates=mutates,
        task_requirement=task_requirement,
        required_permission=required_permission,
        authority=authority,
        visibility=visibility,
        durability=durability,
        result_content_level=result_content_level,
        success_effect=success_effect,
        failure_state_guarantee=failure_state_guarantee,
        reads=reads,
        writes=writes,
        does_not_write=does_not_write,
        preconditions=preconditions,
        returns=returns,
        use_when=use_when,
        do_not_use_when=do_not_use_when,
        risk_hints=risk_hints,
    )


def _build_definition() -> ToolDefinition:
    read_failure = "Rejected reads do not mutate runtime state and return structured rejection metadata."
    write_failure = "Rejected writes do not mutate runtime objects and response explains the payload, lifecycle, or owner boundary."
    return ToolDefinition(
        id="track",
        title="Track Pages",
        description="Operate shared Track requirement facts, collaboration facts, proof, and comments.",
        scope="shared Track requirement collaboration pages, artifact relations, timeline facts, proof, and comments",
        capability_boundary="Any actor can create and add collaboration facts; only the exact owner identity mutates requirement facts, lifecycle, thread resolution, or archive state.",
        object_model=(
            "A Track is shared requirement facts owned by one exact owner_identity_id plus scattered collaboration facts. "
            "Comments are the only actor-attention mechanism; proof is structured evidence that the owner accepts through status."
        ),
        use_when=("You need to operate shared collaboration on a non-archived Track.",),
        do_not_use_when=("You need full artifact body content by id; use artifact.get.",),
        actions=(
            _action(
                name="create",
                description="Create one active Track owned by the active actor identity.",
                input_schema=_object_schema(
                    required=["track_id", "title", "outcome", "now"],
                    properties={
                        "track_id": _track_id_property("Stable id for the new Track."),
                        "title": {"type": "string", "description": "Human-readable Track title."},
                        "outcome": {"type": "string", "description": "Desired Track outcome."},
                        "now": _NOW_SCHEMA,
                        "acceptance_criteria": _TEXT_LIST_SCHEMA,
                        "non_goals": _TEXT_LIST_SCHEMA,
                    },
                ),
                kind="write",
                mutates="runtime_objects",
                task_requirement=TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED,
                required_permission="track.create",
                authority="track.owner_identity_create",
                visibility="shared to roles with Track read access",
                durability="durable",
                result_content_level="track page",
                success_effect="Creates one active Track with owner_identity_id set to the active actor identity.",
                failure_state_guarantee=write_failure,
                reads=("existing track ids",),
                writes=("shared track page",),
                does_not_write=("artifact body", "task state", "direct message state", "actor_private files"),
                preconditions=("track_id does not already exist",),
                returns=("track",),
                use_when=("You need a canonical shared page for requirement facts and collaboration facts.",),
                do_not_use_when=("You need to mutate an existing Track; use the specific Track write action.",),
                risk_hints=_risk(),
            ),
            _action(
                name="list",
                description="List non-archived Track page summaries.",
                input_schema=_object_schema(
                    required=[],
                    properties={
                        "state": {"type": "string", "description": "Optional state filter for non-archived Tracks.", "enum": ["active", "blocked", "done"]},
                        "limit": {"type": "integer", "description": "Optional max number of rows to return.", "minimum": 1},
                    },
                ),
                kind="read",
                mutates="none",
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission="track.read",
                authority="track.lookup",
                visibility="active-role readable Track summaries",
                durability="none",
                result_content_level="summary rows",
                success_effect="Returns non-archived Track summaries for choosing whether to reuse, split, or open a Track.",
                failure_state_guarantee=read_failure,
                reads=("non-archived Track summaries",),
                writes=(),
                does_not_write=("track state", "artifact state", "task state", "direct message state"),
                preconditions=("env.tool role-action policy allows this action for the active role",),
                returns=("tracks",),
                use_when=("You need a summary index of non-archived Tracks.",),
                do_not_use_when=("You already have track_id and need full page details; use track.open.",),
                risk_hints=_risk(read_only=True, idempotent=True),
            ),
            _action(
                name="open",
                description="Open one non-archived shared Track page.",
                input_schema=_object_schema(required=["track_id"], properties={"track_id": _track_id_property()}),
                kind="read",
                mutates="none",
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission="track.read",
                authority="track.lookup",
                visibility="active-role readable Track page",
                durability="none",
                result_content_level="track page with refs, summaries, and comment cues",
                success_effect="Opens one shared Track page with requirements, materials, proofs, updates, and comment cues.",
                failure_state_guarantee=read_failure,
                reads=("one non-archived Track page", "Track comments for cue summaries"),
                writes=(),
                does_not_write=("track state", "artifact body", "task state", "direct message state"),
                preconditions=("track_id references an existing non-archived Track",),
                returns=("track",),
                use_when=("You need full shared Track page details for one known track_id.",),
                do_not_use_when=("You need to mutate Track facts; use a write Track action.",),
                risk_hints=_risk(read_only=True, idempotent=True),
            ),
            _action(
                name="add_comment",
                description="Add one Track-scoped collaboration comment row.",
                input_schema=_object_schema(
                    required=["track_id", "content"],
                    properties={
                        "track_id": _track_id_property(),
                        "content": {"type": "string", "description": "Track comment body text."},
                        "reply_to": {"type": "string", "description": "Optional parent Track comment id in the same Track."},
                        "mentioned_identity_ids": _MENTIONED_IDENTITIES_SCHEMA,
                    },
                ),
                kind="write",
                mutates="runtime_objects",
                task_requirement=TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED,
                required_permission="track.add_comment",
                authority="track.shared_comment",
                visibility="shared to roles with Track read access",
                durability="durable",
                result_content_level="track comment row and delivery metadata",
                success_effect="Adds one durable Track-scoped comment and emits track.comment.added to mentions or reply target actors.",
                failure_state_guarantee=write_failure,
                reads=("one non-archived Track page", "optional parent Track comment", "manifest role ids"),
                writes=("track comment row", "track.comment.added delivery signal when targets exist"),
                does_not_write=("artifact body", "track timeline", "track lifecycle", "task state", "direct message state"),
                preconditions=("track_id references an existing non-archived Track",),
                returns=("comment_id", "comment", "delivery metadata"),
                use_when=("You need Track-scoped threaded discussion or actor attention through mentions/replies.",),
                do_not_use_when=("You need direct inbox communication; use message.send.",),
                risk_hints=_risk(),
            ),
            _action(
                name="list_comments",
                description="List full Track comment rows for one Track.",
                input_schema=_object_schema(
                    required=["track_id"],
                    properties={
                        "track_id": _track_id_property(),
                        "status": {"type": "string", "description": "Optional Track comment status filter.", "enum": ["open", "resolved", "all"]},
                    },
                ),
                kind="read",
                mutates="none",
                task_requirement=TASK_REQUIREMENT_FREE,
                required_permission="track.list_comments",
                authority="track.lookup",
                visibility="shared to roles with Track read access",
                durability="none",
                result_content_level="full Track comment rows",
                success_effect="Lists Track-scoped comment rows for one Track, optionally filtered by status.",
                failure_state_guarantee=read_failure,
                reads=("one non-archived Track page", "Track comment rows for the Track"),
                writes=(),
                does_not_write=("track comment state", "track lifecycle", "artifact body", "task state"),
                preconditions=("track_id references an existing non-archived Track",),
                returns=("comments", "threads", "status_counts"),
                use_when=("You need full Track collaboration comment history for one Track.",),
                do_not_use_when=("You only need compact Track page cues; use track.open.",),
                risk_hints=_risk(read_only=True, idempotent=True),
            ),
            _action(
                name="resolve_comment_thread",
                description="Owner-only resolution for one Track-local comment thread.",
                input_schema=_object_schema(
                    required=["track_id", "comment_id", "resolution_summary"],
                    properties={
                        "track_id": _track_id_property(),
                        "comment_id": {"type": "string", "description": "Track comment id inside the thread."},
                        "resolution_summary": {"type": "string", "description": "Owner closure summary."},
                    },
                ),
                kind="write",
                mutates="runtime_objects",
                task_requirement=TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED,
                required_permission="track.resolve_comment_thread",
                authority="track.owner_thread_resolution",
                visibility="shared to roles with Track read access",
                durability="durable",
                result_content_level="resolved Track comment rows",
                success_effect="Owner marks all open rows in one Track-local comment thread as resolved.",
                failure_state_guarantee=write_failure,
                reads=("one non-archived Track page", "one Track-local comment thread"),
                writes=("track comment thread status",),
                does_not_write=("track timeline", "track lifecycle", "artifact body", "task state", "direct message state"),
                preconditions=("active actor identity is the exact Track owner_identity_id", "thread has at least one open comment row"),
                returns=("comments", "updated_ids"),
                use_when=("The Track owner wants durable resolved closure state for a discussion thread.",),
                do_not_use_when=("You need to continue discussion; use track.add_comment.",),
                risk_hints=_risk(),
            ),
            _action(
                name="update_requirements",
                description="Owner-only patch of Track requirement facts.",
                input_schema=_object_schema(
                    required=["track_id"],
                    properties={
                        "track_id": _track_id_property(),
                        "title": {"type": "string", "description": "Optional replacement Track title."},
                        "outcome": {"type": "string", "description": "Optional replacement Track outcome."},
                        "acceptance_criteria": _TEXT_LIST_SCHEMA,
                        "non_goals": _TEXT_LIST_SCHEMA,
                    },
                ),
                kind="write",
                mutates="runtime_objects",
                task_requirement=TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED,
                required_permission="track.update_requirements",
                authority="track.owner_requirement_facts",
                visibility="shared to roles with Track read access",
                durability="durable",
                result_content_level="track page",
                success_effect="Patches Track requirement facts without mutating lifecycle, now-state, relations, updates, or comments.",
                failure_state_guarantee=write_failure,
                reads=("one non-archived Track page",),
                writes=("Track title/outcome/acceptance criteria/non-goals",),
                does_not_write=("track lifecycle", "track now", "artifact relations", "timeline updates", "comments"),
                preconditions=("active actor identity is the exact Track owner_identity_id",),
                returns=("track",),
                use_when=("The Track owner needs to clarify shared requirement facts.",),
                do_not_use_when=("You need to change state or now; use track.update_status.",),
                risk_hints=_risk(),
            ),
            _action(
                name="update_status",
                description="Owner-only patch of Track lifecycle state and now-state.",
                input_schema=_object_schema(
                    required=["track_id", "state", "now"],
                    properties={
                        "track_id": _track_id_property(),
                        "state": {"type": "string", "description": "Target Track state.", "enum": ["active", "blocked", "done"]},
                        "now": _NOW_SCHEMA,
                    },
                ),
                kind="write",
                mutates="runtime_objects",
                task_requirement=TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED,
                required_permission="track.update_status",
                authority="track.owner_lifecycle",
                visibility="shared to roles with Track read access",
                durability="durable",
                result_content_level="track page",
                success_effect="Patches Track state and now-state while enforcing active/blocked/done invariants.",
                failure_state_guarantee=write_failure,
                reads=("one non-archived Track page", "current proof relations"),
                writes=("track state", "track now"),
                does_not_write=("requirement facts", "artifact relations", "timeline updates", "comments", "notifications"),
                preconditions=("active actor identity is the exact Track owner_identity_id",),
                returns=("track",),
                use_when=("The Track owner accepts a blocker, clears a blocker, or accepts proof as done.",),
                do_not_use_when=("You are reporting a blocker fact; use track.add_update kind=blocker.",),
                risk_hints=_risk(),
            ),
            _action(
                name="add_material",
                description="Relate one artifact as current shared material on the Track.",
                input_schema=_object_schema(
                    required=["track_id", "artifact_id", "label", "summary"],
                    properties={
                        "track_id": _track_id_property(),
                        "artifact_id": {"type": "string", "description": "Readable artifact id to relate as material."},
                        "label": {"type": "string", "description": "Human label for the material relation."},
                        "summary": {"type": "string", "description": "Summary shown on the material relation."},
                    },
                ),
                kind="write",
                mutates="runtime_objects",
                task_requirement=TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED,
                required_permission="track.add_material",
                authority="track.shared_fact",
                visibility="shared to roles with Track read access",
                durability="durable",
                result_content_level="track page plus artifact id",
                success_effect="Adds one current material relation without mutating Track lifecycle or Artifact body.",
                failure_state_guarantee=write_failure,
                reads=("one non-archived Track page", "one active-actor-owned artifact"),
                writes=("track artifact_relations",),
                does_not_write=("track lifecycle", "track timeline", "task state", "direct message state", "comments", "notifications"),
                preconditions=("track_id references an existing non-archived Track",),
                returns=("artifact_id", "track", "state_changes"),
                use_when=("You need to relate an artifact as current shared material on a Track.",),
                do_not_use_when=("You need a timeline fact without a material or proof relation; use track.add_update.", "You are adding proof; use track.add_proof."),
                risk_hints=_risk(),
            ),
            _action(
                name="add_update",
                description="Append one Track timeline update fact.",
                input_schema=_object_schema(
                    required=["track_id", "summary"],
                    properties={
                        "track_id": _track_id_property(),
                        "summary": {"type": "string", "description": "Update summary text appended to timeline."},
                        "kind": {"type": "string", "description": "Optional update kind label.", "enum": ["progress", "decision", "blocker"]},
                        "refs": {"type": "array", "description": "Optional artifact refs related to this update.", "items": _REFS_ITEM_SCHEMA},
                    },
                ),
                kind="write",
                mutates="runtime_objects",
                task_requirement=TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED,
                required_permission="track.add_update",
                authority="track.shared_fact",
                visibility="shared to roles with Track read access",
                durability="durable",
                result_content_level="timeline update row and track page",
                success_effect="Appends one progress, decision, or blocker fact without changing Track lifecycle.",
                failure_state_guarantee=write_failure,
                reads=("one non-archived Track page", "optional readable artifact refs"),
                writes=("track timeline update row",),
                does_not_write=("track lifecycle", "artifact relations", "artifact body", "task state", "comments", "notifications"),
                preconditions=("track_id references an existing non-archived Track",),
                returns=("track", "update"),
                use_when=("You need to append a timeline fact without changing owner-owned status.",),
                do_not_use_when=("You need a material or proof relation instead of a timeline fact; use track.add_material or track.add_proof.",),
                risk_hints=_risk(),
            ),
            _action(
                name="add_proof",
                description="Relate one artifact as current structured proof evidence.",
                input_schema=_object_schema(
                    required=["track_id", "artifact_id", "label", "summary"],
                    properties={
                        "track_id": _track_id_property(),
                        "artifact_id": {"type": "string", "description": "Readable artifact id to relate as proof."},
                        "label": {"type": "string", "description": "Human label for the proof relation."},
                        "summary": {"type": "string", "description": "Summary shown on the proof relation."},
                    },
                ),
                kind="write",
                mutates="runtime_objects",
                task_requirement=TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED,
                required_permission="track.add_proof",
                authority="track.shared_fact",
                visibility="shared to roles with Track read access",
                durability="durable",
                result_content_level="track page plus artifact id",
                success_effect="Adds one current proof relation without changing Track lifecycle or appending an update row.",
                failure_state_guarantee=write_failure,
                reads=("one non-archived Track page", "one active-actor-owned artifact"),
                writes=("track artifact_relations",),
                does_not_write=("track lifecycle", "track timeline", "task state", "direct message state", "comments", "notifications"),
                preconditions=("track_id references an existing non-archived Track",),
                returns=("artifact_id", "track", "state_changes"),
                use_when=("You need to relate structured proof evidence for owner acceptance.",),
                do_not_use_when=("You need material or timeline narrative instead of proof evidence; use track.add_material or track.add_update.", "You need owner acceptance as done; owner uses track.update_status."),
                risk_hints=_risk(),
            ),
            _action(
                name="archive",
                description="Owner-only archive of one shared Track page.",
                input_schema=_object_schema(required=["track_id"], properties={"track_id": _track_id_property("Track id to archive.")}),
                kind="write",
                mutates="runtime_objects",
                task_requirement=TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED,
                required_permission="track.archive",
                authority="track.owner_archive",
                visibility="shared to roles with Track read access until archived filters hide it",
                durability="durable",
                result_content_level="track page",
                success_effect="Archives one Track so it leaves active collaboration flows and rejects normal future writes.",
                failure_state_guarantee=write_failure,
                reads=("one Track page",),
                writes=("track archived_at",),
                does_not_write=("artifact body", "artifact relations", "task state", "direct message state", "comments", "notifications"),
                preconditions=("active actor identity is the exact Track owner_identity_id",),
                returns=("track",),
                use_when=("The Track owner needs to close a Track lifecycle from active collaboration flows.",),
                do_not_use_when=("You only need to reflect blockage or completion; use track.update_status.",),
                risk_hints=_risk(destructive=True),
            ),
        ),
    )


DEFINITION = _build_definition()
validate_definition(DEFINITION)


def build_invoke(
    resolve_publication_candidate: ResolvePublicationCandidate,
    read_reference_metadata: ReadReferenceMetadata,
):
    if not callable(resolve_publication_candidate):
        raise ValueError("Artifact publication candidate resolver must be callable")
    if not callable(read_reference_metadata):
        raise ValueError("Artifact reference metadata reader must be callable")

    def invoke(
        *,
        action: str,
        args: dict[str, Any],
        context: ToolContext,
    ) -> dict[str, Any]:
        from . import _impl

        return _impl.invoke(
            action=action,
            args=args,
            context=context,
            resolve_publication_candidate=resolve_publication_candidate,
            read_reference_metadata=read_reference_metadata,
        )

    return invoke
