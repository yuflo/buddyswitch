#!/usr/bin/env python3
"""Runtime semantic descriptions for env.tool capabilities and actions."""

from __future__ import annotations

from typing import Any

_CAPABILITY_BOUNDARY_DEFAULT = "Service-level permission and ownership checks remain authoritative."

_CAPABILITIES: dict[str, dict[str, Any]] = {
    "task": {
        "title": "Task Management",
        "plain_description": "Manage active-buddy durable task work items used by track, artifact, and handoff tools.",
        "use_when": [
            "You need to create, list, read, update, or archive tasks owned by the active buddy.",
            "You need explicit task ids for artifact revisions or handoff payloads.",
        ],
        "do_not_use_when": [
            "You need PM track lifecycle changes; use track lifecycle actions.",
            "You need to store artifact body content; use artifact.create_revision.",
        ],
        "capability_boundary": "Only active-buddy-owned tasks are writable.",
    },
    "track": {
        "title": "Track Collaboration",
        "plain_description": "Read track context, maintain task-track relations, and apply PM-owned lifecycle mutations.",
        "use_when": [
            "You need track summaries or one track context with related task/artifact summaries.",
            "You need to join, attach, or detach task relations for explicit collaboration state.",
        ],
        "do_not_use_when": [
            "You need artifact body writes; use artifact actions.",
            "You need hidden current-track binding; runless mode uses explicit ids only.",
        ],
        "capability_boundary": "Track lifecycle writes are PM authority; non-PM buddies can read and manage their relations.",
    },
    "artifact": {
        "title": "Artifact Deliverables",
        "plain_description": "Read artifact summaries or full bodies and write durable product-readable artifact revisions.",
        "use_when": [
            "You need deliverable content attached to an active-buddy task.",
            "You need to validate, create, or update artifact metadata with explicit ids and refs.",
        ],
        "do_not_use_when": [
            "You only need active-buddy private scratch files; use buddybox.",
            "You need track lifecycle or task ownership updates; use track or task actions.",
        ],
        "capability_boundary": "Artifact writes require explicit active-buddy task ownership and valid source refs.",
    },
    "handoff": {
        "title": "Handoff Records",
        "plain_description": "Create explicit cross-buddy collaboration records that reference readable product objects.",
        "use_when": [
            "You need to validate or persist target-buddy handoff records with explicit source ids.",
            "You need durable collaboration context separate from private buddybox files.",
        ],
        "do_not_use_when": [
            "You need track lifecycle mutation; use track PM lifecycle actions.",
            "You need to share private buddybox payload directly; handoff requires product-readable refs.",
        ],
        "capability_boundary": "Handoff writes enforce source ownership, target buddy validity, and readable references.",
    },
    "buddybox": {
        "title": "Buddybox Files",
        "plain_description": (
            "Operate active-buddy private files through logical_name values; these files are active-instance-local "
            "and not product object state."
        ),
        "use_when": [
            "You need active buddy private files for drafts, lightweight prototypes, exports, reports, logs, generated files, or binary outputs.",
            "Use artifact.create_revision when the host decides content must become product-readable across buddies.",
        ],
        "do_not_use_when": [
            "You need cross-buddy readable deliverables, handoff payload authority, or shared source edits.",
            "You need to mutate runtime product objects directly; use task/track/artifact/handoff tools.",
        ],
        "capability_boundary": (
            "Only logical_name values inside the active buddy private file capability are allowed; "
            "buddybox logical names do not grant cross-buddy read authority."
        ),
    },
    "context": {
        "title": "Context Discovery",
        "plain_description": "Read runtime orientation, compact affordances, full tool catalog, and machine operation semantics.",
        "use_when": [
            "You need first-pass orientation and candidate ids before env tool writes.",
            "You need runtime-visible tool semantics without reading service implementation files.",
        ],
        "do_not_use_when": [
            "You need to mutate product or private file state.",
            "You need full artifact body content directly; use artifact.get.",
        ],
        "capability_boundary": "Context actions are read-only and never grant write authority.",
    },
    "evidence": {
        "title": "Market Evidence",
        "plain_description": "Issue target-scoped transient evidence token metadata for artifact quality gates.",
        "use_when": [
            "You need evidence token metadata for a specific artifact target.",
            "You need downgrade approval token metadata tied to a target id.",
        ],
        "do_not_use_when": [
            "You need durable product object writes.",
            "You need generic unrestricted browser actions; use search actions for browser intent/session.",
        ],
        "capability_boundary": "Evidence actions operate on target-scoped artifact ids and return transient token metadata.",
    },
    "search": {
        "title": "Search Boundary",
        "plain_description": "Expose search backend metadata, target URL planning, and browser-session open actions.",
        "use_when": [
            "You need backend/browser readiness status before open-world browsing.",
            "You need a planned target URL intent or an explicit browser page open action.",
        ],
        "do_not_use_when": [
            "You need durable product object writes.",
            "You need implicit phrase routing or hidden automation outside profile boundaries.",
        ],
        "capability_boundary": "Search actions remain within profile backend/engine boundaries and launcher browser session rules.",
    },
}


def _risk_hints(*, mutates: str, open_world: bool, destructive: bool = False, external_effect: bool = False) -> dict[str, Any]:
    return {
        "read_only": mutates == "none",
        "destructive": destructive,
        "idempotent": mutates == "none",
        "open_world": open_world,
        "requires_human_approval": False,
        "external_effect": external_effect,
    }


def _side_effects(*, mutates: str, writes: list[str], does_not_write: list[str], durability: str, idempotency: str) -> dict[str, Any]:
    return {
        "mutates": mutates,
        "writes": writes,
        "does_not_write": does_not_write,
        "durability": durability,
        "idempotency": idempotency,
    }


def _action_rows() -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}

    def add(
        tool: str,
        action: str,
        *,
        title: str,
        plain_description: str,
        use_when: list[str],
        do_not_use_when: list[str],
        inputs_explained: dict[str, str],
        side_effects: dict[str, Any],
        risk_hints: dict[str, Any],
        success_means: str,
        common_failures: list[str],
    ) -> None:
        rows[(tool, action)] = {
            "title": title,
            "plain_description": plain_description,
            "use_when": use_when,
            "do_not_use_when": do_not_use_when,
            "inputs_explained": inputs_explained,
            "side_effects": side_effects,
            "risk_hints": risk_hints,
            "success_means": success_means,
            "common_failures": common_failures,
        }

    # task actions
    add(
        "task",
        "create",
        title="Create Task",
        plain_description="Create one active-buddy durable task record and optionally attach it to a track.",
        use_when=[
            "You need a new active-buddy task_id for artifact or handoff writes.",
        ],
        do_not_use_when=[
            "You need PM track lifecycle mutation rather than task creation.",
        ],
        inputs_explained={
            "task_id": "Optional explicit task id; generated when omitted. Returned from task.create.",
            "title": "Required task title for the new active-buddy task.",
            "summary": "Optional concise task summary text.",
            "status": "Optional task status; defaults to active.",
            "track_id": "Optional track id from context.summarize.candidate_tracks, track.list, or track.get.",
        },
        side_effects=_side_effects(
            mutates="runtime_objects",
            writes=["buddyswitch/objects/tasks/*.json", "buddyswitch/objects/tracks/*.json (when track relation changes)"],
            does_not_write=["buddyswitch/local/buddybox", "instance current binding"],
            durability="durable",
            idempotency="non-idempotent when task_id omitted",
        ),
        risk_hints=_risk_hints(mutates="runtime_objects", open_world=False),
        success_means="One durable active-buddy task record was created and the response returns task_id plus task summary fields.",
        common_failures=["missing title", "invalid status", "track_id not found", "task_id already exists"],
    )
    add(
        "task",
        "list",
        title="Task List",
        plain_description="Return active-buddy task summary rows with optional status/track filters.",
        use_when=["You need owned task rows for id discovery before get/update/archive or artifact/handoff writes."],
        do_not_use_when=["You need full artifact body content; task rows include artifact ids, not artifact bodies."],
        inputs_explained={
            "status": "Optional task status filter.",
            "track_id": "Optional track id filter from candidate tracks or track surfaces.",
            "limit": "Optional positive limit for returned summary rows.",
        },
        side_effects=_side_effects(
            mutates="none",
            writes=[],
            does_not_write=["buddyswitch/objects/tasks/*.json", "buddyswitch/local/buddybox", "instance current binding"],
            durability="none",
            idempotency="idempotent read",
        ),
        risk_hints=_risk_hints(mutates="none", open_world=False),
        success_means="Active-buddy task summary rows were returned with task ids and artifact ids only; no full artifact body was returned.",
        common_failures=["invalid status filter", "invalid limit"],
    )
    add(
        "task",
        "get",
        title="Task Get",
        plain_description="Read one active-buddy task record by task_id.",
        use_when=["You need one owned task record with metadata and artifact ids before mutation or handoff."],
        do_not_use_when=["You need cross-buddy task mutation without ownership."],
        inputs_explained={
            "task_id": "Required owned task id from task.create, task.list, task.get, track.get, or context.get.tasks.",
        },
        side_effects=_side_effects(
            mutates="none",
            writes=[],
            does_not_write=["buddyswitch/objects/tasks/*.json", "buddyswitch/local/buddybox", "instance current binding"],
            durability="none",
            idempotency="idempotent read",
        ),
        risk_hints=_risk_hints(mutates="none", open_world=False),
        success_means="One active-buddy task record was returned with metadata and artifact ids; full artifact bodies remain in artifact.get.",
        common_failures=["missing task_id", "task not found", "task ownership denial"],
    )
    add(
        "task",
        "update",
        title="Task Update",
        plain_description="Patch one active-buddy task and optionally change its explicit track relation.",
        use_when=["You need to update title, summary, status, or track relation on one owned task."],
        do_not_use_when=["You need to write artifact body content; use artifact.create_revision."],
        inputs_explained={
            "task_id": "Required owned task id from task.list/get or track.get.",
            "title": "Optional replacement title.",
            "summary": "Optional replacement summary.",
            "status": "Optional replacement status.",
            "track_id": "Optional replacement track id from context.summarize candidate tracks or track surfaces.",
        },
        side_effects=_side_effects(
            mutates="runtime_objects",
            writes=["buddyswitch/objects/tasks/*.json", "buddyswitch/objects/tracks/*.json (when relation changes)"],
            does_not_write=["buddyswitch/local/buddybox", "instance current binding"],
            durability="durable",
            idempotency="conditionally idempotent",
        ),
        risk_hints=_risk_hints(mutates="runtime_objects", open_world=False),
        success_means="One active-buddy task record was updated and durable task/track relation state reflects patched fields.",
        common_failures=["missing task_id", "task not found", "task ownership denial", "invalid status"],
    )
    add(
        "task",
        "archive",
        title="Task Archive",
        plain_description="Set one active-buddy task status to archived.",
        use_when=["You need to archive one owned task id in durable product state."],
        do_not_use_when=["You need to keep task active and only change summary/title; use task.update."],
        inputs_explained={
            "task_id": "Required owned task id from task surfaces or track context.",
        },
        side_effects=_side_effects(
            mutates="runtime_objects",
            writes=["buddyswitch/objects/tasks/*.json", "buddyswitch/objects/tracks/*.json (when relation metadata changes)"],
            does_not_write=["buddyswitch/local/buddybox", "instance current binding"],
            durability="durable",
            idempotency="conditionally idempotent",
        ),
        risk_hints=_risk_hints(mutates="runtime_objects", open_world=False),
        success_means="The task status became archived in durable state, or response reports already-archived with no state change.",
        common_failures=["missing task_id", "task not found", "task ownership denial"],
    )

    # track actions
    track_inputs = {
        "list": {
            "status": "Optional track status filter.",
            "buddy": "Optional participating buddy filter.",
            "limit": "Optional positive limit for summary rows.",
        },
        "get": {
            "track_id": "Required track id from context.summarize.candidate_tracks or track.list.",
        },
        "join": {
            "track_id": "Required track id from context.summarize.candidate_tracks, track.list, or track.get.",
            "task_id": "Optional owned task id from task.list/task.get/track.get; creates one when omitted.",
            "title": "Optional task title used when join creates a new task.",
            "summary": "Optional task summary used when join creates a new task.",
        },
        "create": {
            "track_id": "Required new track id.",
            "title": "Required track title.",
            "status": "Optional initial lifecycle status.",
            "current_buddy": "Optional current buddy; defaults to pm.",
            "next_buddy": "Optional next buddy.",
            "summary": "Optional track summary.",
        },
        "update": {
            "track_id": "Required existing track id.",
            "title": "Optional replacement title.",
            "status": "Optional replacement status.",
            "current_buddy": "Optional replacement current buddy.",
            "next_buddy": "Optional replacement next buddy.",
            "summary": "Optional replacement summary.",
        },
        "advance": {
            "track_id": "Required existing track id.",
            "status": "Optional next status.",
            "current_buddy": "Optional next current buddy.",
            "next_buddy": "Optional next buddy.",
            "summary": "Optional summary patch.",
        },
        "archive": {
            "track_id": "Required existing track id.",
        },
        "attach_task": {
            "track_id": "Required existing track id from context or track surfaces.",
            "task_id": "Required owned task id from task.list/task.get.",
        },
        "detach_task": {
            "track_id": "Required existing track id from context or track surfaces.",
            "task_id": "Required owned task id from task.list/task.get.",
        },
    }
    track_modes = {
        "list": "none",
        "get": "none",
        "join": "runtime_objects",
        "create": "runtime_objects",
        "update": "runtime_objects",
        "advance": "runtime_objects",
        "archive": "runtime_objects",
        "attach_task": "runtime_objects",
        "detach_task": "runtime_objects",
    }
    track_text = {
        "list": (
            "Return readable track summary rows with optional filters.",
            "Readable track summary rows were returned; full artifact bodies remain in artifact.get.",
        ),
        "get": (
            "Read one track context by track_id including track metadata, related task summaries, and artifact summaries.",
            "One track context was returned with track metadata plus related task/artifact summaries and without full artifact bodies.",
        ),
        "join": (
            "Create, reuse, or attach an active-buddy task relation to one track using explicit ids.",
            "The track relation now references one active-buddy task through task_created, task_attached, or relation_reused state changes.",
        ),
        "create": (
            "Create one durable track lifecycle object (PM authority).",
            "One durable track object was created and returned with explicit lifecycle fields.",
        ),
        "update": (
            "Update one durable track lifecycle object (PM authority).",
            "One durable track object was updated with lifecycle field patches.",
        ),
        "advance": (
            "Advance one durable track lifecycle object (PM authority).",
            "One durable track lifecycle object advanced to the provided lifecycle state.",
        ),
        "archive": (
            "Archive one durable track lifecycle object (PM authority).",
            "One durable track object was archived.",
        ),
        "attach_task": (
            "Attach one owned task to one track by explicit ids.",
            "The explicit task-track relation was durably attached for one task and one track.",
        ),
        "detach_task": (
            "Detach one owned task from one track by explicit ids.",
            "The explicit task-track relation was durably detached for one task and one track.",
        ),
    }
    for action in (
        "list",
        "get",
        "join",
        "create",
        "update",
        "advance",
        "archive",
        "attach_task",
        "detach_task",
    ):
        mutates = track_modes[action]
        plain_description, success_means = track_text[action]
        add(
            "track",
            action,
            title=f"Track {action.replace('_', ' ').title()}",
            plain_description=plain_description,
            use_when=[
                "Use this action when you need explicit track context or task-track relation state aligned with active-buddy authority.",
            ],
            do_not_use_when=[
                "Do not use this action for hidden current-binding state; runless track writes require explicit ids.",
            ],
            inputs_explained=track_inputs[action],
            side_effects=_side_effects(
                mutates=mutates,
                writes=[] if mutates == "none" else ["buddyswitch/objects/tracks/*.json", "buddyswitch/objects/tasks/*.json"],
                does_not_write=["instance current binding", "buddyswitch/local/buddybox"],
                durability="none" if mutates == "none" else "durable",
                idempotency="idempotent read" if mutates == "none" else "conditionally idempotent",
            ),
            risk_hints=_risk_hints(mutates=mutates, open_world=False),
            success_means=success_means,
            common_failures=["missing required ids", "track not found", "pm lifecycle authority denial", "task ownership denial"],
        )

    # artifact actions
    add(
        "artifact",
        "list",
        title="Artifact List",
        plain_description="Return artifact summary rows for one track; full artifact content is excluded.",
        use_when=["You need readable artifact ids and summary metadata for one track."],
        do_not_use_when=["You need full artifact body content; use artifact.get."],
        inputs_explained={
            "track_id": "Required track id from context.summarize.candidate_tracks, track.list, or track.get.",
        },
        side_effects=_side_effects(
            mutates="none",
            writes=[],
            does_not_write=["buddyswitch/objects/artifacts/*.json", "buddyswitch/local/buddybox", "instance current binding"],
            durability="none",
            idempotency="idempotent read",
        ),
        risk_hints=_risk_hints(mutates="none", open_world=False),
        success_means="Artifact summary rows were returned for the track without full artifact content bodies.",
        common_failures=["missing track_id", "track not found", "artifact read scope denial"],
    )
    add(
        "artifact",
        "get",
        title="Artifact Get",
        plain_description="Read one artifact record by artifact_id including its full body content.",
        use_when=["You need full artifact content for one readable artifact id."],
        do_not_use_when=["You only need summary rows; use artifact.list."],
        inputs_explained={
            "artifact_id": "Required readable artifact id from artifact.list, artifact.create_revision, track.get artifact summaries, or context.get.artifact_summaries.",
        },
        side_effects=_side_effects(
            mutates="none",
            writes=[],
            does_not_write=["buddyswitch/objects/artifacts/*.json", "buddyswitch/local/buddybox", "instance current binding"],
            durability="none",
            idempotency="idempotent read",
        ),
        risk_hints=_risk_hints(mutates="none", open_world=False),
        success_means="One readable artifact record was returned with full content body and metadata fields.",
        common_failures=["missing artifact_id", "artifact not found", "artifact read scope denial"],
    )
    add(
        "artifact",
        "validate_payload",
        title="Artifact Validate Payload",
        plain_description="Validate and normalize a candidate artifact revision payload without mutating runtime state.",
        use_when=["You need validation-only confirmation before deciding to write artifact.create_revision."],
        do_not_use_when=["You intend to persist a revision immediately; use artifact.create_revision."],
        inputs_explained={
            "artifact_id": "Optional explicit artifact id for a future revision write.",
            "task_id": "Required owned task id from task.list, task.get, or track.join.",
            "kind": "Required artifact kind.",
            "title": "Required artifact title.",
            "summary": "Optional artifact summary.",
            "content": "Required JSON object body for the candidate artifact.",
            "source_refs": "Optional structured provenance refs normalized for later writes.",
            "read_claim": "Optional claim text used when normalizing restricted refs.",
        },
        side_effects=_side_effects(
            mutates="none",
            writes=[],
            does_not_write=["buddyswitch/objects/artifacts/*.json", "buddyswitch/objects/tasks/*.json", "buddyswitch/local/buddybox"],
            durability="none",
            idempotency="idempotent validation",
        ),
        risk_hints=_risk_hints(mutates="none", open_world=False),
        success_means="The candidate payload was validated and normalized with no write and no state mutation.",
        common_failures=["missing task_id", "invalid content", "task ownership denial", "invalid source_refs"],
    )
    add(
        "artifact",
        "create_revision",
        title="Artifact Create Revision",
        plain_description="Write one durable product-readable artifact revision for an active-buddy task.",
        use_when=["You need to persist a validated artifact body and provenance refs for one owned task."],
        do_not_use_when=["You only need payload validation; use artifact.validate_payload."],
        inputs_explained={
            "artifact_id": "Optional explicit artifact id; generated when omitted.",
            "task_id": "Required owned task id from task.list, task.get, or track.join.",
            "kind": "Required artifact kind.",
            "title": "Required artifact title.",
            "summary": "Optional artifact summary.",
            "content": "Required JSON object body content.",
            "source_refs": "Optional normalized provenance refs.",
            "read_claim": "Optional claim text used when normalizing restricted refs.",
        },
        side_effects=_side_effects(
            mutates="runtime_objects",
            writes=["buddyswitch/objects/artifacts/*.json", "buddyswitch/objects/tasks/*.json"],
            does_not_write=["buddyswitch/local/buddybox", "instance current binding"],
            durability="durable",
            idempotency="conditionally idempotent when artifact_id reused",
        ),
        risk_hints=_risk_hints(mutates="runtime_objects", open_world=False),
        success_means="One durable artifact revision was created and task artifact linkage was updated with explicit ids.",
        common_failures=["missing task_id", "task not found", "ownership denial", "invalid source_refs"],
    )
    add(
        "artifact",
        "update_metadata",
        title="Artifact Update Metadata",
        plain_description="Update artifact title, summary, and source refs without replacing artifact body content.",
        use_when=["You need metadata-only updates on one active-buddy-owned artifact id."],
        do_not_use_when=["You need a new artifact body revision; use artifact.create_revision."],
        inputs_explained={
            "artifact_id": "Required owned artifact id from artifact.list/get/create_revision or track.get summaries.",
            "title": "Optional replacement title.",
            "summary": "Optional replacement summary.",
            "source_refs": "Optional replacement provenance refs.",
            "read_claim": "Optional claim text used when normalizing restricted refs.",
        },
        side_effects=_side_effects(
            mutates="runtime_objects",
            writes=["buddyswitch/objects/artifacts/*.json"],
            does_not_write=["artifact body content payload", "buddyswitch/local/buddybox", "instance current binding"],
            durability="durable",
            idempotency="conditionally idempotent",
        ),
        risk_hints=_risk_hints(mutates="runtime_objects", open_world=False),
        success_means="Artifact metadata fields were durably updated while the existing artifact body content stayed unchanged.",
        common_failures=["missing artifact_id", "artifact not found", "artifact ownership denial", "invalid source_refs"],
    )

    # handoff actions
    add(
        "handoff",
        "list",
        title="Handoff List",
        plain_description="Return explicit readable handoff records visible to source, target, or PM roles.",
        use_when=["You need handoff records and ids without reading artifact body content."],
        do_not_use_when=["You need to write a new handoff record; use handoff.create."],
        inputs_explained={
            "track_id": "Optional track id filter from context.summarize or track surfaces.",
            "target_buddy": "Optional target buddy filter from manifest buddy ids.",
            "status": "Optional handoff status filter.",
            "limit": "Optional positive limit for handoff records.",
        },
        side_effects=_side_effects(
            mutates="none",
            writes=[],
            does_not_write=["buddyswitch/objects/handoffs/*.json", "buddyswitch/local/buddybox", "artifact bodies"],
            durability="none",
            idempotency="idempotent read",
        ),
        risk_hints=_risk_hints(mutates="none", open_world=False),
        success_means="Readable handoff records were returned for source/target/PM visibility without artifact body payloads.",
        common_failures=["invalid filters", "read scope denial"],
    )
    add(
        "handoff",
        "validate",
        title="Handoff Validate",
        plain_description="Validate target buddy, source ownership, and object refs for a candidate handoff payload without writing.",
        use_when=["You need validation-only checks before deciding whether to persist handoff.create."],
        do_not_use_when=["You need to persist a handoff record immediately; use handoff.create."],
        inputs_explained={
            "track_id": "Required track id from context.summarize.candidate_tracks, track.list, or track.get.",
            "source_task_id": "Optional owned source task id from task.list or task.get.",
            "target_buddy": "Required target buddy id from manifest buddy ids.",
            "artifact_ids": "Optional owned artifact ids from artifact.list/get or track.get summaries.",
            "source_refs": "Optional normalized readable refs; buddybox logical names are private and rejected here.",
            "reason": "Required handoff reason text.",
            "context": "Required handoff context text.",
            "status": "Optional handoff status (defaults to active).",
            "read_claim": "Optional claim text used when normalizing restricted refs.",
        },
        side_effects=_side_effects(
            mutates="none",
            writes=[],
            does_not_write=["buddyswitch/objects/handoffs/*.json", "buddyswitch/local/buddybox"],
            durability="none",
            idempotency="idempotent validation",
        ),
        risk_hints=_risk_hints(mutates="none", open_world=False),
        success_means="The candidate handoff payload was validated and normalized with no state mutation and no handoff write.",
        common_failures=["missing required fields", "target buddy unknown", "source ownership denial", "invalid source_refs"],
    )
    add(
        "handoff",
        "create",
        title="Handoff Create",
        plain_description="Write one durable handoff record that references readable product objects.",
        use_when=["You need to persist a validated handoff for a target buddy."],
        do_not_use_when=["You only need validation checks; use handoff.validate."],
        inputs_explained={
            "handoff_id": "Optional explicit handoff id; generated when omitted.",
            "track_id": "Required track id from context/track surfaces.",
            "source_task_id": "Optional owned source task id from task.list/task.get.",
            "target_buddy": "Required target buddy from manifest ids.",
            "artifact_ids": "Optional owned artifact ids from artifact/list/get responses.",
            "source_refs": "Optional readable source refs; buddybox logical_name refs remain private provenance and are not target-readable payloads.",
            "reason": "Required handoff reason text.",
            "context": "Required handoff context text.",
            "status": "Optional handoff status.",
            "read_claim": "Optional claim text used when normalizing restricted refs.",
        },
        side_effects=_side_effects(
            mutates="runtime_objects",
            writes=["buddyswitch/objects/handoffs/*.json"],
            does_not_write=["buddyswitch/local/buddybox", "instance current binding"],
            durability="durable",
            idempotency="conditionally idempotent when handoff_id reused",
        ),
        risk_hints=_risk_hints(mutates="runtime_objects", open_world=False),
        success_means="One durable handoff record was created with explicit source/target ids and readable object references.",
        common_failures=["target buddy unknown", "source ownership mismatch", "invalid source_refs", "handoff id conflict"],
    )

    # buddybox actions
    buddybox_rows: dict[str, dict[str, Any]] = {
        "desc": {
            "mutates": "none",
            "inputs_explained": {},
            "plain_description": "Return active buddy private file capability descriptor and compact state summary only.",
            "use_when": [
                "You need the private-file boundary and supported operations before file calls.",
                "You need capability orientation without reading file bodies.",
            ],
            "do_not_use_when": [
                "You need file summary rows; use buddybox.list.",
                "You need one file body; use buddybox.read.",
            ],
            "success_means": "Capability descriptor and compact private state summary were returned with no file content rows.",
            "common_failures": [
                "unsupported payload fields",
                "active buddy is not bound to a valid runtime instance",
            ],
        },
        "list": {
            "mutates": "none",
            "inputs_explained": {
                "logical_name": "Optional logical-name prefix inside active-buddy private capability; do not provide filesystem paths.",
                "recursive": "Whether to include nested files under the active-buddy private capability.",
                "limit": "Optional positive maximum number of summary rows.",
            },
            "plain_description": "List active-buddy private file summary rows only; file body content is excluded.",
            "use_when": [
                "You need per-file private summary rows before selecting one logical_name for read/write/delete.",
                "Use artifact.create_revision only when the host decides private content should become product-readable.",
            ],
            "do_not_use_when": [
                "You need file body content; use buddybox.read.",
                "You need cross-buddy readable deliverables directly.",
            ],
            "success_means": "Private file summary rows were returned with no content/content_base64 body fields.",
            "common_failures": [
                "unsupported payload fields",
                "empty logical_name prefix",
                "absolute logical_name",
                "logical_name traversal",
                "logical_name buddy prefix",
                "invalid limit value",
            ],
        },
        "read": {
            "mutates": "none",
            "inputs_explained": {
                "logical_name": "Required exact logical_name for one active-buddy private file.",
                "encoding": "Output preference: auto, utf-8, or base64.",
            },
            "plain_description": "Read one exact active-buddy private file and return either content or content_base64.",
            "use_when": [
                "You need one private file body for local iteration.",
                "You need to inspect output from a prior buddybox.write before next action.",
            ],
            "do_not_use_when": [
                "You need summary inventory; use buddybox.list.",
                "You need product-readable delivery immediately; use artifact.create_revision when host decides promotion.",
            ],
            "success_means": "One private file body was returned with content or content_base64 plus encoding metadata.",
            "common_failures": [
                "unsupported payload fields",
                "invalid encoding",
                "missing file",
                "absolute logical_name",
                "logical_name traversal",
                "logical_name buddy prefix",
            ],
        },
        "write": {
            "mutates": "runtime_files",
            "inputs_explained": {
                "logical_name": "Required logical_name inside active-buddy private capability; creates or overwrites one file.",
                "content": "UTF-8 text payload. Mutually exclusive with content_base64.",
                "content_base64": "Base64 payload for binary or non-UTF-8 content. Mutually exclusive with content.",
                "content_type": "MIME hint only, not a product contract.",
            },
            "plain_description": "Create or overwrite one active-buddy private file in active-instance-local storage.",
            "use_when": [
                "You need private drafts, lightweight prototypes, exports, reports, logs, generated files, or binary outputs.",
                "Artifact promotion remains optional when the host decides cross-buddy readability is needed.",
            ],
            "do_not_use_when": [
                "You need direct product object mutation; use task/track/artifact/handoff.",
                "You need cross-buddy readability from logical_name alone; logical_name is private provenance only.",
            ],
            "success_means": "One private file was created or overwritten in active-instance-local storage without product object mutation.",
            "common_failures": [
                "unsupported payload fields",
                "absolute logical_name",
                "logical_name traversal",
                "logical_name buddy prefix",
                "provide exactly one of content or content_base64",
                "invalid base64",
            ],
        },
        "delete": {
            "mutates": "runtime_files",
            "inputs_explained": {
                "logical_name": "Required exact logical_name for one active-buddy private file.",
            },
            "plain_description": "Delete one active-buddy private file if present.",
            "use_when": [
                "You need private workspace cleanup without product/collaboration object mutation.",
                "You need to remove one exact logical_name.",
            ],
            "do_not_use_when": [
                "You need to delete task/track/artifact/handoff objects.",
                "You need cross-buddy readable cleanup semantics.",
            ],
            "success_means": "One private file was deleted or already_absent was confirmed with no product object mutation.",
            "common_failures": [
                "unsupported payload fields",
                "absolute logical_name",
                "logical_name traversal",
                "logical_name buddy prefix",
                "logical_name points to a directory",
            ],
        },
    }
    for action, row in buddybox_rows.items():
        mut = str(row["mutates"])
        add(
            "buddybox",
            action,
            title=f"Buddybox {action.replace('_', ' ').title()}",
            plain_description=str(row["plain_description"]),
            use_when=list(row["use_when"]),
            do_not_use_when=list(row["do_not_use_when"]),
            inputs_explained=dict(row["inputs_explained"]),
            side_effects=_side_effects(
                mutates=mut,
                writes=[] if mut == "none" else ["active_buddy_private_file_workspace"],
                does_not_write=[
                    "buddyswitch/objects/tracks/*.json",
                    "buddyswitch/objects/tasks/*.json",
                    "buddyswitch/objects/artifacts/*.json",
                    "buddyswitch/objects/handoffs/*.json",
                    "cross-buddy collaboration state",
                    "instance current binding",
                ],
                durability="none" if mut == "none" else "active_instance_local",
                idempotency="idempotent read" if mut == "none" else "write non-idempotent, delete conditionally idempotent",
            ),
            risk_hints=_risk_hints(mutates=mut, open_world=False, destructive=(action == "delete")),
            success_means=str(row["success_means"]),
            common_failures=list(row["common_failures"]),
        )

    # context actions
    add(
        "context",
        "get",
        title="Context Get",
        plain_description="Read full runtime context sections plus full tool_catalog and operation_semantics.",
        use_when=["You need complete runtime-visible catalog semantics and context sections in one response."],
        do_not_use_when=["You only need compact first-pass orientation; use context.summarize."],
        inputs_explained={
            "track_id": "Optional track focus id filter.",
            "task_id": "Optional task focus id filter.",
            "limit": "Optional section row limit.",
        },
        side_effects=_side_effects(
            mutates="none",
            writes=[],
            does_not_write=["product objects", "buddyswitch/local/buddybox", "instance current binding"],
            durability="none",
            idempotency="idempotent read",
        ),
        risk_hints=_risk_hints(mutates="none", open_world=False),
        success_means="Full runtime context sections, full tool catalog, and full operation semantics were returned read-only.",
        common_failures=["invalid context filter payload", "unsupported filter key", "insufficient read scope"],
    )
    add(
        "context",
        "summarize",
        title="Context Summarize",
        plain_description="Read compact context orientation with candidate ids, buddybox descriptor, and compact first-pass tool affordances.",
        use_when=["You need compact first-pass tool choice guidance before requesting full catalog details."],
        do_not_use_when=["You need payload_fields, action_semantics, or operation_semantics for all actions; use context.get."],
        inputs_explained={
            "track_id": "Optional track focus id filter.",
            "task_id": "Optional task focus id filter.",
            "limit": "Optional summary row limit.",
        },
        side_effects=_side_effects(
            mutates="none",
            writes=[],
            does_not_write=["product objects", "buddyswitch/local/buddybox", "instance current binding"],
            durability="none",
            idempotency="idempotent read",
        ),
        risk_hints=_risk_hints(mutates="none", open_world=False),
        success_means="Compact orientation rows were returned; full tool catalog and operation semantics remain in context.get only.",
        common_failures=["invalid context filter payload", "unsupported filter key", "insufficient read scope"],
    )
    add(
        "context",
        "list_sources",
        title="Context List Sources",
        plain_description="Read source descriptors for runtime context sections.",
        use_when=["You need source descriptor metadata for tracks/tasks/artifacts/handoffs/buddybox."],
        do_not_use_when=["You need full context payloads or tool semantics; use context.get or context.summarize."],
        inputs_explained={},
        side_effects=_side_effects(
            mutates="none",
            writes=[],
            does_not_write=["product objects", "buddyswitch/local/buddybox", "instance current binding"],
            durability="none",
            idempotency="idempotent read",
        ),
        risk_hints=_risk_hints(mutates="none", open_world=False),
        success_means="Runtime source descriptors were returned without mutating state.",
        common_failures=["unsupported payload fields", "source descriptor read error"],
    )

    # evidence actions
    add(
        "evidence",
        "issue_browser",
        title="Evidence Issue Browser",
        plain_description="Issue transient target-scoped browser evidence token metadata for one artifact target.",
        use_when=["You need a target-scoped evidence token for an artifact id."],
        do_not_use_when=["You need durable product object writes.", "You need browser session page open; use search.open_browser."],
        inputs_explained={
            "target_type": "Required target type; currently artifact.",
            "target_id": "Required artifact target id from artifact.list/get/create_revision.",
            "mode": "Optional token issue mode hint.",
        },
        side_effects=_side_effects(
            mutates="broker_token",
            writes=["target-scoped evidence token metadata"],
            does_not_write=["buddyswitch/objects/*", "buddyswitch/local/buddybox", "browser session"],
            durability="transient token",
            idempotency="non-idempotent token issuance",
        ),
        risk_hints=_risk_hints(mutates="broker_token", open_world=False),
        success_means="Transient token metadata was issued for one artifact target id without durable product object writes.",
        common_failures=["missing target_type", "missing target_id", "target not found", "target scope mismatch"],
    )
    add(
        "evidence",
        "approve_downgrade",
        title="Evidence Approve Downgrade",
        plain_description="Issue transient downgrade-approval token metadata for one artifact target.",
        use_when=["You need explicit downgrade approval token metadata tied to one artifact id."],
        do_not_use_when=["You need durable product object writes.", "You need browser session page open; use search.open_browser."],
        inputs_explained={
            "target_type": "Required target type; currently artifact.",
            "target_id": "Required artifact target id from artifact surfaces.",
            "reason": "Required downgrade approval reason text.",
        },
        side_effects=_side_effects(
            mutates="broker_token",
            writes=["target-scoped evidence token metadata"],
            does_not_write=["buddyswitch/objects/*", "buddyswitch/local/buddybox", "browser session"],
            durability="transient token",
            idempotency="non-idempotent token issuance",
        ),
        risk_hints=_risk_hints(mutates="broker_token", open_world=False),
        success_means="Transient downgrade token metadata was issued for one artifact target id with no durable object mutation.",
        common_failures=["missing reason", "missing target fields", "target scope mismatch"],
    )

    # search actions
    add(
        "search",
        "status",
        title="Search Status",
        plain_description="Read search backend capability and browser readiness metadata for the active instance.",
        use_when=["You need metadata about available backends and browser readiness before open-world browsing."],
        do_not_use_when=["You need to open a browser page now; use search.open_browser."],
        inputs_explained={},
        side_effects=_side_effects(
            mutates="none",
            writes=[],
            does_not_write=["product objects", "browser session page state"],
            durability="none",
            idempotency="idempotent read",
        ),
        risk_hints=_risk_hints(mutates="none", open_world=False),
        success_means="Capability metadata and backend readiness status were returned without opening a browser page.",
        common_failures=["profile search boundary unavailable"],
    )
    add(
        "search",
        "request",
        title="Search Request",
        plain_description="Validate a search request and return target URL/browser intent without opening a page.",
        use_when=["You need a planned target URL intent before deciding whether to open browser session."],
        do_not_use_when=["You need immediate page open; use search.open_browser."],
        inputs_explained={
            "query": "Required non-empty search query.",
            "backend": "Required backend value from search.status available backends.",
            "engine": "Optional engine override from supported engines.",
        },
        side_effects=_side_effects(
            mutates="none",
            writes=[],
            does_not_write=["product objects", "browser session page state"],
            durability="none",
            idempotency="idempotent planning read",
        ),
        risk_hints=_risk_hints(mutates="none", open_world=True),
        success_means="Target URL and browser intent were returned with page_opened=false and no browser session mutation.",
        common_failures=["missing query", "backend not allowed", "engine not allowed", "browser endpoint unavailable"],
    )
    add(
        "search",
        "open_browser",
        title="Search Open Browser",
        plain_description="Open the planned target URL in launcher-managed browser session.",
        use_when=["You need browser session mutation to inspect search results in open-world browsing."],
        do_not_use_when=["You only need request planning metadata without opening a page; use search.request."],
        inputs_explained={
            "query": "Required non-empty search query.",
            "engine": "Optional engine override from supported engines.",
        },
        side_effects=_side_effects(
            mutates="browser_session",
            writes=["launcher-managed browser session state"],
            does_not_write=["product objects", "buddyswitch/local/buddybox"],
            durability="browser_session",
            idempotency="non-idempotent browser open",
        ),
        risk_hints=_risk_hints(mutates="browser_session", open_world=True, external_effect=True),
        success_means="The target URL was opened in browser session state and no durable product object was written.",
        common_failures=["missing query", "engine not allowed", "browser endpoint unavailable", "browser open failure"],
    )

    return rows


_ACTIONS = _action_rows()


def compact_tool_affordances() -> dict[str, dict[str, Any]]:
    return {
        "task": {
            "capability": "active_buddy_task_work_items",
            "choose_when": "You need active-buddy task ids, summaries, or task field updates.",
            "id_inputs_from": "task.create/task.list/task.get, track.get, or context.get.tasks.",
            "returns": "task summary rows or one task record with artifact ids.",
            "state_effect": "create/update/archive mutate durable task state; list/get are read-only.",
            "durability": "durable for writes, none for reads.",
            "supports": ["create", "list", "get", "update", "archive"],
        },
        "track": {
            "capability": "track_context_and_task_relations",
            "choose_when": "You need track summaries/context, PM lifecycle changes, or task-track relation updates.",
            "id_inputs_from": "context.summarize.candidate_tracks, track.list, track.get, task.list/task.get.",
            "returns": "track summaries or one track context with related task/artifact summaries.",
            "state_effect": "join/lifecycle/attach/detach mutate durable track-relation state.",
            "durability": "durable for writes, none for list/get.",
            "supports": ["list", "get", "join", "create", "update", "advance", "archive", "attach_task", "detach_task"],
        },
        "artifact": {
            "capability": "product_readable_deliverables",
            "choose_when": "You need artifact summaries, full artifact bodies, or durable artifact revision writes.",
            "id_inputs_from": "track surfaces, task surfaces, artifact.list/get/create, context.get.artifact_summaries.",
            "returns": "list gives summaries; get gives full body; validate gives normalized payload.",
            "state_effect": "create_revision/update_metadata mutate durable artifact/task linkage.",
            "durability": "durable for writes, none for list/get/validate.",
            "supports": ["list", "get", "validate_payload", "create_revision", "update_metadata"],
        },
        "handoff": {
            "capability": "explicit_cross_buddy_handoff_records",
            "choose_when": "You need validation or durable persistence of target-buddy collaboration records.",
            "id_inputs_from": "track/task/artifact surfaces and manifest buddy ids.",
            "returns": "handoff records or validated normalized candidate payload.",
            "state_effect": "create mutates durable handoff state; list/validate are read-only.",
            "durability": "durable for create, none for list/validate.",
            "supports": ["list", "validate", "create"],
        },
        "buddybox": {
            "capability": "active_buddy_private_file_workspace",
            "choose_when": "You need private drafts/prototypes/exports/logs/reports/generated/binary files.",
            "id_inputs_from": "host-chosen logical_name values scoped to active buddy private capability.",
            "returns": "desc capability metadata, list summaries, read one file body, write/delete file status.",
            "state_effect": "write/delete mutate private files only, never product objects.",
            "durability": "active_instance_local for write/delete, none for desc/list/read.",
            "supports": ["desc", "list", "read", "write", "delete"],
        },
        "context": {
            "capability": "runtime_context_and_tool_discovery",
            "choose_when": "You need compact orientation or full runtime catalog/operation semantics.",
            "id_inputs_from": "optional track_id/task_id filters provided by host.",
            "returns": "summarize gives compact orientation; get gives full sections + full catalog.",
            "state_effect": "read-only discovery; no writes.",
            "durability": "none",
            "supports": ["summarize", "get", "list_sources"],
        },
        "evidence": {
            "capability": "target_scoped_transient_evidence_tokens",
            "choose_when": "You need token metadata bound to one artifact target for evidence workflows.",
            "id_inputs_from": "artifact ids from artifact.list/get/create_revision.",
            "returns": "target-scoped transient token metadata.",
            "state_effect": "issues token metadata only; no durable product object writes.",
            "durability": "transient token",
            "supports": ["issue_browser", "approve_downgrade"],
        },
        "search": {
            "capability": "search_boundary_and_browser_session_open",
            "choose_when": "You need backend status, target URL planning, or explicit browser session open.",
            "id_inputs_from": "query/backend/engine from host and search.status capability output.",
            "returns": "status metadata, request target_url/page_opened=false, or open_browser session effect.",
            "state_effect": "open_browser mutates browser session only; status/request are read-only.",
            "durability": "browser_session for open_browser, none for status/request.",
            "supports": ["status", "request", "open_browser"],
        },
        "project_source": {
            "capability": "shared_project_source_workspace",
            "choose_when": "You need shared source file edits distinct from env runtime object/private-file state.",
            "id_inputs_from": "project paths and repo context, not env tool ids.",
            "returns": "source file read/write outcomes via project tooling.",
            "state_effect": "outside env.tool runtime object state.",
            "durability": "project workspace file durability.",
            "supports": ["read_shared_source", "write_shared_source_when_permitted"],
        },
    }


def capability_semantics(tool: str) -> dict[str, Any]:
    row = _CAPABILITIES.get(tool)
    if isinstance(row, dict):
        return row
    return {
        "title": f"{tool.title()} Capability",
        "plain_description": f"Runtime capability metadata for '{tool}'.",
        "use_when": [f"Inspect runtime catalog details for '{tool}' before calling it."],
        "do_not_use_when": ["Capability is not part of the active runtime tool registry."],
        "capability_boundary": _CAPABILITY_BOUNDARY_DEFAULT,
    }


def action_semantics(tool: str, action: str) -> dict[str, Any]:
    row = _ACTIONS.get((tool, action))
    if isinstance(row, dict):
        return row
    return {
        "title": f"{tool}.{action}",
        "plain_description": f"Runtime semantic row for {tool}.{action}.",
        "use_when": ["Inspect the runtime catalog entry before invoking this action."],
        "do_not_use_when": ["The action is unavailable in this runtime."],
        "inputs_explained": {},
        "side_effects": _side_effects(
            mutates="none",
            writes=[],
            does_not_write=["runtime state"],
            durability="none",
            idempotency="idempotent",
        ),
        "risk_hints": _risk_hints(mutates="none", open_world=False),
        "success_means": "Runtime returned a structured action response.",
        "common_failures": ["unsupported action", "invalid payload"],
    }


def semantic_coverage_errors(registry: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []

    for tool_spec in registry:
        tool = tool_spec.get("tool")
        if not isinstance(tool, str) or not tool:
            errors.append("registry entry missing tool id")
            continue
        capability = capability_semantics(tool)
        for key in ("title", "plain_description", "use_when", "do_not_use_when", "capability_boundary"):
            if key not in capability:
                errors.append(f"capability missing {tool}.{key}")

        for action_spec in tool_spec.get("actions", []):
            action = action_spec.get("name")
            if not isinstance(action, str) or not action:
                errors.append(f"action missing name for tool {tool}")
                continue
            semantic = action_semantics(tool, action)
            for key in (
                "title",
                "plain_description",
                "use_when",
                "do_not_use_when",
                "inputs_explained",
                "side_effects",
                "risk_hints",
                "success_means",
                "common_failures",
            ):
                if key not in semantic:
                    errors.append(f"action semantics missing {tool}.{action}.{key}")

            payload_fields = action_spec.get("payload_fields", [])
            if not isinstance(payload_fields, list):
                errors.append(f"registry payload_fields must be list for {tool}.{action}")
                continue
            explained = semantic.get("inputs_explained")
            if not isinstance(explained, dict):
                errors.append(f"inputs_explained must be dict for {tool}.{action}")
                continue
            missing = sorted(field for field in payload_fields if field not in explained)
            if missing:
                errors.append(f"inputs_explained missing fields for {tool}.{action}: {', '.join(missing)}")

    return errors
