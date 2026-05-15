#!/usr/bin/env python3
"""Runless semantic metadata for env.tool capabilities and actions."""

from __future__ import annotations

from typing import Any

_CAPABILITY_BOUNDARY_DEFAULT = "Service-level permission and ownership checks remain authoritative."

_CAPABILITIES: dict[str, dict[str, Any]] = {
    "task": {
        "title": "Task Management",
        "plain_description": "Create and manage active-buddy tasks as durable work items.",
        "use_when": [
            "You need to create, read, update, or archive a task owned by the active buddy.",
            "You need explicit task ids to attach artifacts or handoffs.",
        ],
        "do_not_use_when": [
            "You need PM-only track lifecycle changes; use track actions instead.",
            "You need artifact body storage; use artifact.create_revision instead.",
        ],
        "capability_boundary": "Only active-buddy-owned tasks are writable.",
    },
    "track": {
        "title": "Track Collaboration",
        "plain_description": "Read tracks, join them with explicit task relations, and let PM mutate lifecycle.",
        "use_when": [
            "You need readable track context, task membership, or lifecycle state.",
            "You need to create/reuse task relation on a track via track.join.",
        ],
        "do_not_use_when": [
            "You need to write artifact content directly; use artifact actions.",
            "You need implicit current-binding selection; runless model has no binding authority.",
        ],
        "capability_boundary": "PM-only lifecycle mutations; other buddies can read/join relations.",
    },
    "artifact": {
        "title": "Artifact Deliverables",
        "plain_description": "Create and read formal task artifacts with revision and source_refs provenance.",
        "use_when": [
            "You need durable deliverable content attached to a specific task.",
            "You need to revise artifact metadata or content with explicit task ownership.",
        ],
        "do_not_use_when": [
            "You need task/track orchestration metadata; use task or handoff actions.",
            "You need durable file outputs; use buddybox actions.",
        ],
        "capability_boundary": "Writes require explicit task_id and active-buddy task ownership.",
    },
    "handoff": {
        "title": "Handoff Records",
        "plain_description": "Create explicit cross-buddy handoff objects referencing product objects.",
        "use_when": [
            "You need to transfer work context across buddies with explicit readable artifact/object references.",
            "You need structured validation before writing a handoff record.",
        ],
        "do_not_use_when": [
            "You need to mutate track lifecycle state; use PM track lifecycle actions.",
            "You need to persist generic notes; use artifact or buddybox instead.",
        ],
        "capability_boundary": "Handoff writes enforce source ownership and target buddy validity.",
    },
    "buddybox": {
        "title": "Buddybox Files",
        "plain_description": (
            "Describe and operate the active buddy private local workspace for private drafts, lightweight prototypes, "
            "exports, reports, logs, generated files, and binary outputs; buddybox is not collaborative, "
            "not visible to other buddies, and not product object state."
        ),
        "use_when": [
            "You need active buddy private local files such as drafts, lightweight prototypes, exports, reports, logs, generated files, or binary outputs.",
            "Use artifact.create_revision when the host decides content must become product-readable across buddies.",
        ],
        "do_not_use_when": [
            "You need cross-buddy readable deliverables, product objects, shared source edits, or handoff-readable payloads.",
            "You need collaboration-readable transport authority; buddybox paths do not grant cross-buddy read authority.",
        ],
        "capability_boundary": "Only active buddy private local root paths are allowed; buddybox paths do not grant cross-buddy read authority.",
    },
    "context": {
        "title": "Context Discovery",
        "plain_description": "Read-only orientation payload for runless product state and tool catalog.",
        "use_when": [
            "You need a snapshot of readable tracks/tasks/artifacts/handoffs and buddybox_desc.",
            "You need candidate ids for subsequent explicit tool writes.",
        ],
        "do_not_use_when": [
            "You need write authority or selection state; context is read-only.",
            "You need full artifact body payloads; use artifact.get.",
        ],
        "capability_boundary": "No run envelopes, persist hints, or current-binding authority.",
    },
    "evidence": {
        "title": "Market Evidence",
        "plain_description": "Issue target-scoped browser evidence tokens for artifact quality gates.",
        "use_when": [
            "Market workflow requires browser evidence attached to artifact targets.",
            "You need explicit approval reason for evidence downgrade on a target.",
        ],
        "do_not_use_when": [
            "You need generic provenance refs without market gate requirements.",
            "You need run-scoped evidence tied to prepared runs; runless model has no run tokens.",
        ],
        "capability_boundary": "Evidence is target-scoped to artifact ids.",
    },
    "search": {
        "title": "Search Boundary",
        "plain_description": "Expose runtime-visible search capability status and browser request intents.",
        "use_when": [
            "You need to inspect available search backends and browser readiness.",
            "You need a structured target URL plan for manual browser search actions.",
        ],
        "do_not_use_when": [
            "You need durable product state writes; search responses are orientation only.",
            "You need hidden browser automation bypassing explicit request surfaces.",
        ],
        "capability_boundary": "Search actions remain within profile-defined backend and engine boundaries.",
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
        plain_description="Create one active-buddy task with optional track attachment.",
        use_when=["You need a new owned task id for subsequent writes."],
        do_not_use_when=["You need PM track lifecycle changes instead of task creation."],
        inputs_explained={
            "task_id": "Optional explicit task id; generated when omitted.",
            "title": "Required task title.",
            "summary": "Optional concise task summary.",
            "status": "Optional task status; defaults to active.",
            "track_id": "Optional existing track id to attach this task.",
        },
        side_effects=_side_effects(
            mutates="runtime_objects",
            writes=["buddyswitch/objects/tasks/*.json", "buddyswitch/objects/tracks/*.json (optional relation update)"],
            does_not_write=["buddyswitch/local/buddybox", "buddyswitch/local/buddybox", "instance current binding"],
            durability="durable",
            idempotency="non-idempotent when task_id omitted",
        ),
        risk_hints=_risk_hints(mutates="runtime_objects", open_world=False),
        success_means="A task object was written and the response includes task_id and task payload.",
        common_failures=["missing title", "invalid status", "track_id not found", "task_id already exists"],
    )
    for action, desc in {
        "list": "List active-buddy tasks with optional filters.",
        "get": "Read one active-buddy task by task_id.",
        "update": "Patch one active-buddy task fields.",
        "archive": "Archive one active-buddy task.",
    }.items():
        mut = "none" if action in {"list", "get"} else "runtime_objects"
        fields = {
            "list": {"status": "Optional status filter.", "track_id": "Optional track id filter.", "limit": "Optional positive limit."},
            "get": {"task_id": "Required task id to read."},
            "update": {
                "task_id": "Required task id.",
                "title": "Optional updated title.",
                "summary": "Optional updated summary.",
                "status": "Optional updated status.",
                "track_id": "Optional updated track relation.",
            },
            "archive": {"task_id": "Required task id."},
        }[action]
        add(
            "task",
            action,
            title=f"Task {action.replace('_', ' ').title()}",
            plain_description=desc,
            use_when=[f"You need task.{action} behavior on owned tasks."],
            do_not_use_when=["You need cross-buddy task mutation without ownership."],
            inputs_explained=fields,
            side_effects=_side_effects(
                mutates=mut,
                writes=[] if mut == "none" else ["buddyswitch/objects/tasks/*.json", "buddyswitch/objects/tracks/*.json (optional relation update)"],
                does_not_write=["buddyswitch/local/buddybox", "instance current binding"],
                durability="none" if mut == "none" else "durable",
                idempotency="idempotent for reads" if mut == "none" else "conditionally idempotent",
            ),
            risk_hints=_risk_hints(mutates=mut, open_world=False),
            success_means=f"task.{action} completed within active-buddy scope.",
            common_failures=["missing task_id", "task not found", "task ownership denial"],
        )

    # track actions
    track_rows = {
        "list": ("none", {"status": "Optional status filter.", "buddy": "Optional buddy participation filter.", "limit": "Optional positive limit."}),
        "get": ("none", {"track_id": "Required track id."}),
        "join": ("runtime_objects", {"track_id": "Required track id.", "task_id": "Optional owned task id to reuse.", "title": "Optional title when creating task.", "summary": "Optional summary when creating task."}),
        "create": ("runtime_objects", {"track_id": "Required track id.", "title": "Required track title.", "status": "Optional status.", "current_buddy": "Optional current buddy; defaults to pm.", "next_buddy": "Optional next buddy.", "summary": "Optional summary."}),
        "update": ("runtime_objects", {"track_id": "Required track id.", "title": "Optional title patch.", "status": "Optional status patch.", "current_buddy": "Optional current buddy patch.", "next_buddy": "Optional next buddy patch.", "summary": "Optional summary patch."}),
        "advance": ("runtime_objects", {"track_id": "Required track id.", "status": "Optional next status.", "current_buddy": "Optional next current buddy.", "next_buddy": "Optional next buddy.", "summary": "Optional summary patch."}),
        "archive": ("runtime_objects", {"track_id": "Required track id."}),
        "attach_task": ("runtime_objects", {"track_id": "Required track id.", "task_id": "Required owned task id."}),
        "detach_task": ("runtime_objects", {"track_id": "Required track id.", "task_id": "Required owned task id."}),
    }
    for action, (mut, fields) in track_rows.items():
        add(
            "track",
            action,
            title=f"Track {action.replace('_', ' ').title()}",
            plain_description=f"Execute track.{action} under runless track/task relation rules.",
            use_when=[f"You need track.{action} behavior."],
            do_not_use_when=["You need hidden current-binding selection as write authority."],
            inputs_explained=fields,
            side_effects=_side_effects(
                mutates=mut,
                writes=[] if mut == "none" else ["buddyswitch/objects/tracks/*.json", "buddyswitch/objects/tasks/*.json"],
                does_not_write=["instance current binding", "buddyswitch/local/buddybox", "buddyswitch/local/buddybox"],
                durability="none" if mut == "none" else "durable",
                idempotency="idempotent for reads" if mut == "none" else "conditionally idempotent",
            ),
            risk_hints=_risk_hints(mutates=mut, open_world=False),
            success_means=f"track.{action} returned structured track/task relation state.",
            common_failures=["missing track_id", "track not found", "pm lifecycle authority denial"],
        )

    # artifact actions
    artifact_rows = {
        "list": ("none", {"track_id": "Required track id to list relation-readable artifacts."}),
        "get": ("none", {"artifact_id": "Required artifact id."}),
        "validate_payload": (
            "none",
            {
                "artifact_id": "Optional explicit artifact id.",
                "task_id": "Required owned task id.",
                "kind": "Required artifact kind.",
                "title": "Required title.",
                "summary": "Optional summary.",
                "content": "Required JSON object content.",
                "source_refs": "Optional structured provenance refs.",
            },
        ),
        "create_revision": (
            "runtime_objects",
            {
                "artifact_id": "Optional explicit artifact id.",
                "task_id": "Required owned task id.",
                "kind": "Required artifact kind.",
                "title": "Required title.",
                "summary": "Optional summary.",
                "content": "Required JSON object content.",
                "source_refs": "Optional structured provenance refs.",
                "read_claim": "Optional claim string when summarizing full internal sources.",
            },
        ),
        "update_metadata": (
            "runtime_objects",
            {
                "artifact_id": "Required owned artifact id.",
                "title": "Optional new title.",
                "summary": "Optional new summary.",
                "source_refs": "Optional source_refs replacement.",
                "read_claim": "Optional claim string when summarizing full internal sources.",
            },
        ),
    }
    for action, (mut, fields) in artifact_rows.items():
        add(
            "artifact",
            action,
            title=f"Artifact {action.replace('_', ' ').title()}",
            plain_description=f"Execute artifact.{action} with explicit task/artifact ids and source_refs.",
            use_when=[f"You need artifact.{action} behavior in runless model."],
            do_not_use_when=["You need implicit task fallback instead of explicit task_id."],
            inputs_explained=fields,
            side_effects=_side_effects(
                mutates=mut,
                writes=[] if mut == "none" else ["buddyswitch/objects/artifacts/*.json", "buddyswitch/objects/tasks/*.json"],
                does_not_write=["buddyswitch/local/buddybox", "instance current binding"],
                durability="none" if mut == "none" else "durable",
                idempotency="idempotent for reads" if mut == "none" else "conditionally idempotent",
            ),
            risk_hints=_risk_hints(mutates=mut, open_world=False),
            success_means=f"artifact.{action} completed with explicit ids and runless provenance fields.",
            common_failures=["missing task_id", "artifact/task not found", "ownership denial", "invalid source_refs"],
        )

    # handoff actions
    handoff_fields = {
        "list": {"track_id": "Optional track id filter.", "target_buddy": "Optional target buddy filter.", "status": "Optional status filter.", "limit": "Optional positive limit."},
        "validate": {
            "track_id": "Required track id.",
            "source_task_id": "Optional source task id.",
            "target_buddy": "Required target buddy id.",
            "artifact_ids": "Optional artifact id list.",
            "source_refs": "Optional source_refs list.",
            "reason": "Required handoff reason.",
            "context": "Required handoff context.",
            "status": "Optional handoff status.",
            "read_claim": "Optional full-summary claim for internal refs.",
        },
        "create": {
            "handoff_id": "Optional explicit handoff id.",
            "track_id": "Required track id.",
            "source_task_id": "Optional source task id.",
            "target_buddy": "Required target buddy id.",
            "artifact_ids": "Optional artifact id list.",
            "source_refs": "Optional source_refs list.",
            "reason": "Required handoff reason.",
            "context": "Required handoff context.",
            "status": "Optional handoff status.",
            "read_claim": "Optional full-summary claim for internal refs.",
        },
    }
    for action in ("list", "validate", "create"):
        mut = "none" if action in {"list", "validate"} else "runtime_objects"
        add(
            "handoff",
            action,
            title=f"Handoff {action.replace('_', ' ').title()}",
            plain_description=f"Execute handoff.{action} with explicit product object references.",
            use_when=[f"You need handoff.{action} behavior."],
            do_not_use_when=["You need run-audit-derived implicit handoff behavior."],
            inputs_explained=handoff_fields[action],
            side_effects=_side_effects(
                mutates=mut,
                writes=[] if mut == "none" else ["buddyswitch/objects/handoffs/*.json"],
                does_not_write=["buddyswitch/local/buddybox", "instance current binding"],
                durability="none" if mut == "none" else "durable",
                idempotency="idempotent for reads/validate" if mut == "none" else "non-idempotent unless handoff_id reused",
            ),
            risk_hints=_risk_hints(mutates=mut, open_world=False),
            success_means=f"handoff.{action} returned structured object-based collaboration state.",
            common_failures=["target_buddy unknown", "source ownership mismatch", "invalid source_refs"],
        )

    # buddybox actions
    buddybox_rows: dict[str, dict[str, Any]] = {
        "desc": {
            "mutates": "none",
            "inputs_explained": {},
            "plain_description": "Return active buddy private local workspace semantics and compact state summary only.",
            "use_when": [
                "You need the private-local boundary, available operations, and compact workspace state before file operations.",
                "You need a semantic orientation entrypoint without reading file bodies.",
            ],
            "do_not_use_when": [
                "You need file summary rows; use buddybox.list.",
                "You need a file body or binary payload; use buddybox.read.",
            ],
            "success_means": "desc returned semantic description and compact local summary only; no file content or full file list was returned.",
            "common_failures": [
                "unsupported payload fields",
                "active buddy is not bound to a valid runtime instance",
            ],
        },
        "list": {
            "mutates": "none",
            "inputs_explained": {
                "path": "Optional active buddy prefix filter under <active_buddy>/...; rows stay in active buddy private local workspace.",
                "recursive": "Whether to include nested files under the active buddy local root.",
                "limit": "Optional positive maximum number of summary rows.",
            },
            "plain_description": "List active-buddy private local file summary rows only (no file content).",
            "use_when": [
                "You need per-file summary rows (path, size_bytes, updated_at, content_type, private_to_buddy).",
                "You need to pick a private local file before read/write/delete.",
            ],
            "do_not_use_when": [
                "You need file bodies (`content` or `content_base64`); use buddybox.read.",
                "You need cross-buddy readable deliverables; use artifact.create_revision when host decides promotion is needed.",
            ],
            "success_means": "list returned summaries only with no file content and no product/collaboration object changed.",
            "common_failures": [
                "unsupported payload fields",
                "path traversal or absolute path",
                "foreign buddy prefix outside active root",
                "invalid limit value",
            ],
        },
        "read": {
            "mutates": "none",
            "inputs_explained": {
                "path": "Required active buddy prefix path under <active_buddy>/... for one private local file read.",
                "encoding": "Output preference: auto, utf-8, or base64.",
            },
            "plain_description": "Read one exact active-buddy private local file path without mutating product/collaboration objects.",
            "use_when": [
                "You need one private local file body for local iteration.",
                "You need to inspect output from a prior buddybox.write before deciding next action.",
            ],
            "do_not_use_when": [
                "You need to browse many files; use buddybox.list.",
                "You need product-readable delivery; use artifact.create_revision when host decides content must become product-readable.",
            ],
            "success_means": (
                "read returned one active buddy private local file at one exact path and either content "
                "or content_base64 with encoding explaining interpretation."
            ),
            "common_failures": [
                "unsupported payload fields",
                "missing file",
                "path traversal or absolute path",
                "foreign buddy prefix outside active root",
                "invalid encoding",
            ],
        },
        "write": {
            "mutates": "runtime_files",
            "inputs_explained": {
                "path": "Required active buddy prefix write path under <active_buddy>/...; creates or overwrites one file.",
                "content": "UTF-8 text payload. Mutually exclusive with content_base64.",
                "content_base64": "Base64 payload for binary or non-UTF-8 content. Mutually exclusive with content.",
                "content_type": "MIME hint only, not a product contract.",
            },
            "plain_description": "Create or replace one active-buddy private local file.",
            "use_when": [
                "You need to create or overwrite one active buddy private local draft/prototype/export/report/log/generated/binary file.",
                "You may promote readable content with artifact.create_revision when the host decides product-readable sharing is needed.",
            ],
            "do_not_use_when": [
                "You need to mutate product objects directly; use task/track/artifact/handoff tools.",
                "You need cross-buddy readable authority from a local path; buddybox paths are private provenance only.",
            ],
            "success_means": (
                "write created or overwrote one active buddy private local file and did not create "
                "artifact/handoff/task/track/context/evidence objects."
            ),
            "common_failures": [
                "unsupported payload fields",
                "path traversal or absolute path",
                "foreign buddy prefix outside active root",
                "provide exactly one of content or content_base64",
                "invalid base64",
            ],
        },
        "delete": {
            "mutates": "runtime_files",
            "inputs_explained": {
                "path": "Required active buddy prefix path under <active_buddy>/... for one private local file delete.",
            },
            "plain_description": "Delete one active-buddy private local file if present.",
            "use_when": [
                "You need to remove one active buddy private local file from private iteration workspace.",
                "You need to clean private local outputs without changing product/collaboration objects.",
            ],
            "do_not_use_when": [
                "You need to delete product objects; use artifact/task/track/handoff tools.",
                "You need cross-buddy readable cleanup; buddybox delete is private-local only.",
            ],
            "success_means": "delete removed one active buddy private local file or confirmed it was absent; no product/collaboration object changed.",
            "common_failures": [
                "unsupported payload fields",
                "path traversal or absolute path",
                "foreign buddy prefix outside active root",
                "path points to a directory instead of a file",
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
                writes=[] if mut == "none" else ["buddyswitch/local/buddybox/<active_buddy>/**"],
                does_not_write=[
                    "buddyswitch/objects/tracks/*.json",
                    "buddyswitch/objects/tasks/*.json",
                    "buddyswitch/objects/artifacts/*.json",
                    "buddyswitch/objects/handoffs/*.json",
                    "instance current binding",
                ],
                durability="none" if mut == "none" else "durable",
                idempotency="idempotent for desc/list/read" if mut == "none" else "write non-idempotent, delete conditionally idempotent",
            ),
            risk_hints=_risk_hints(mutates=mut, open_world=False, destructive=(action == "delete")),
            success_means=str(row["success_means"]),
            common_failures=list(row["common_failures"]),
        )

    # context actions
    context_rows = {
        "get": {"track_id": "Optional track focus id.", "task_id": "Optional task focus id.", "limit": "Optional section limit."},
        "summarize": {"track_id": "Optional track focus id.", "task_id": "Optional task focus id.", "limit": "Optional summary limit."},
        "list_sources": {},
    }
    for action, fields in context_rows.items():
        add(
            "context",
            action,
            title=f"Context {action.replace('_', ' ').title()}",
            plain_description=f"Read runless context.{action} orientation payload without mutating state.",
            use_when=["You need orientation before choosing explicit product write targets."],
            do_not_use_when=["You need write authority, run reservation, or current-binding mutation."],
            inputs_explained=fields,
            side_effects=_side_effects(
                mutates="none",
                writes=[],
                does_not_write=["buddyswitch/local/buddybox", "buddyswitch/local/buddybox", "instance current binding", "product objects"],
                durability="none",
                idempotency="idempotent",
            ),
            risk_hints=_risk_hints(mutates="none", open_world=False),
            success_means=f"context.{action} returned readable runless product-state orientation sections.",
            common_failures=["invalid context filter payload", "malformed stored object", "insufficient read scope"],
        )

    # evidence actions
    for action, fields in {
        "issue_browser": {"target_type": "Required: artifact.", "target_id": "Required target id.", "mode": "Optional issue mode hint."},
        "approve_downgrade": {"target_type": "Required: artifact.", "target_id": "Required target id.", "reason": "Required downgrade approval reason."},
    }.items():
        add(
            "evidence",
            action,
            title=f"Evidence {action.replace('_', ' ').title()}",
            plain_description=f"Execute evidence.{action} as target-scoped market gate token flow.",
            use_when=[f"You need evidence.{action} for artifact quality gates."],
            do_not_use_when=["You need run-scoped evidence tokens or context-discovery envelopes."],
            inputs_explained=fields,
            side_effects=_side_effects(
                mutates="broker_token",
                writes=["target-scoped evidence token state"],
                does_not_write=["buddyswitch/local/buddybox", "task run lineage"],
                durability="transient token",
                idempotency="non-idempotent token issuance",
            ),
            risk_hints=_risk_hints(mutates="broker_token", open_world=False),
            success_means=f"evidence.{action} returned target-scoped token metadata with no run id.",
            common_failures=["target not found", "target scope mismatch", "missing reason", "permission denial"],
        )

    # search actions
    search_rows = {
        "status": ("none", {"": ""}),
        "request": ("none", {"query": "Required query string.", "backend": "Optional backend override.", "engine": "Optional engine override."}),
        "open_browser": ("browser_session", {"query": "Required query string.", "engine": "Optional engine override."}),
    }
    for action, (mut, fields) in search_rows.items():
        inputs = {} if "" in fields else fields
        add(
            "search",
            action,
            title=f"Search {action.replace('_', ' ').title()}",
            plain_description=f"Execute search.{action} within runtime-visible search capability boundaries.",
            use_when=[f"You need search.{action} behavior with explicit backend/engine boundaries."],
            do_not_use_when=["You need durable state mutation or hidden autonomous browsing."],
            inputs_explained=inputs,
            side_effects=_side_effects(
                mutates=mut,
                writes=[] if mut == "none" else ["browser session state"],
                does_not_write=["product object state"],
                durability="none" if mut == "none" else "transient browser session",
                idempotency="idempotent for status/request; open_browser is non-idempotent",
            ),
            risk_hints=_risk_hints(mutates=mut, open_world=(action != "status"), external_effect=(action == "open_browser")),
            success_means=f"search.{action} returned structured capability feedback for explicit host decisions.",
            common_failures=["missing query", "backend not allowed", "browser endpoint unavailable"],
        )

    return rows


_ACTIONS = _action_rows()


def compact_tool_affordances() -> dict[str, dict[str, str]]:
    return {
        "buddybox": {
            "use_for": (
                "active buddy private local files: drafts, lightweight prototypes, exports, reports, "
                "logs, generated files, binary outputs"
            ),
            "not_for": (
                "cross-buddy readable deliverables, product objects, shared source edits, or "
                "handoff-readable payloads"
            ),
            "promote_with": "artifact.create_revision when readable content must become product-readable",
            "inspect_with": "context.get.tool_catalog['buddybox'] or python3 scripts/turn_runtime.py status",
        },
        "artifact": {
            "use_for": "task-scoped product-readable deliverables and revisions",
            "not_for": "private local files, generated binary outputs, or active-buddy scratch work",
            "inspect_with": "context.get.tool_catalog['artifact'] or python3 scripts/turn_runtime.py status",
        },
    }


def capability_semantics(tool: str) -> dict[str, Any]:
    row = _CAPABILITIES.get(tool)
    if isinstance(row, dict):
        return row
    return {
        "title": f"{tool.title()} Capability",
        "plain_description": f"Runtime capability metadata for '{tool}'.",
        "use_when": [f"You need '{tool}' capability behavior."],
        "do_not_use_when": ["Capability is not part of the active tool registry for this runtime."],
        "capability_boundary": _CAPABILITY_BOUNDARY_DEFAULT,
    }


def action_semantics(tool: str, action: str) -> dict[str, Any]:
    row = _ACTIONS.get((tool, action))
    if isinstance(row, dict):
        return row
    return {
        "title": f"{tool}.{action}",
        "plain_description": f"Semantic metadata for action '{tool}.{action}'.",
        "use_when": [f"You need to call {tool}.{action}."],
        "do_not_use_when": [f"The action {tool}.{action} is unavailable in this runtime."],
        "inputs_explained": {},
        "side_effects": _side_effects(
            mutates="none",
            writes=[],
            does_not_write=["runtime state"],
            durability="none",
            idempotency="idempotent",
        ),
        "risk_hints": _risk_hints(mutates="none", open_world=False),
        "success_means": f"{tool}.{action} returned a structured response.",
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
