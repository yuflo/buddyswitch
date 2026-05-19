#!/usr/bin/env python3
"""Runtime semantic descriptions for env.tool capabilities and actions."""

from __future__ import annotations

from typing import Any

_CAPABILITY_BOUNDARY_DEFAULT = "Service-level permission and ownership checks remain authoritative."

_CAPABILITIES: dict[str, dict[str, Any]] = {
    "task": {
        "title": "Task Management",
        "plain_description": "Manage active-buddy private tasks as optional work aids.",
        "use_when": [
            "You need to create, list, read, update, or archive tasks owned by the active buddy.",
            "You need a private organizational hint via task.track_id.",
        ],
        "do_not_use_when": [
            "You need shared collaboration material; use track.open and artifact.get.",
            "You need to publish shared artifacts; use track.add_material or track.add_proof.",
        ],
        "capability_boundary": "Only active-buddy-owned tasks are readable/writable.",
    },
    "track": {
        "title": "Track Pages",
        "plain_description": "Operate shared progress pages and shared materials/proof publication.",
        "use_when": [
            "You need to create, list, open, update now-state, add materials/updates/proof, or archive tracks.",
            "You need cross-buddy shared collaboration state on a non-archived track.",
        ],
        "do_not_use_when": [
            "You need to read full artifact body by id; use artifact.get.",
            "You need private buddy drafts/files; use artifact.create_revision or buddybox tools.",
        ],
        "capability_boundary": "Only PM can create/archive tracks; all buddies can mutate non-archived shared page fields in V1.",
    },
    "artifact": {
        "title": "Artifact Bodies",
        "plain_description": "Read full artifact bodies and manage active-buddy private artifact metadata/drafts.",
        "use_when": [
            "You need full artifact content via artifact.get.",
            "You need to create/update an active-buddy private draft artifact.",
        ],
        "do_not_use_when": [
            "You need to publish artifact to shared collaboration; use track.add_material or track.add_proof.",
            "You need task relation workflow; task_id publication path is removed.",
        ],
        "capability_boundary": "Private drafts are owner-only until published to a non-archived track by track actions.",
    },
    "buddybox": {
        "title": "Buddybox Files",
        "plain_description": "Operate active-buddy private files through logical_name values.",
        "use_when": [
            "You need active buddy private files for drafts, exports, logs, or generated files.",
            "Use artifact or track publication when content must become product-readable.",
        ],
        "do_not_use_when": [
            "You need cross-buddy readable deliverables.",
            "You need to mutate runtime product objects directly; use task/track/artifact tools.",
        ],
        "capability_boundary": "Only logical_name values inside the active buddy private file capability are allowed.",
    },
    "context": {
        "title": "Context Discovery",
        "plain_description": "Read runtime orientation, compact affordances, full tool catalog, and operation semantics.",
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
    "message": {
        "title": "Buddy Messages",
        "plain_description": "Send and list direct buddy-to-buddy inbox messages.",
        "use_when": [
            "You need to send a direct message to another declared manifest buddy.",
            "You need to list messages sent to the active buddy inbox.",
        ],
        "do_not_use_when": [
            "You need object-level discussion; use comment.add for track/artifact comments.",
            "You need message status, read receipts, editing, or deleting.",
        ],
        "capability_boundary": "Messages are direct buddy-to-buddy only.",
    },
    "comment": {
        "title": "Object Comments",
        "plain_description": "Add and list plain-text comments on readable track and artifact targets.",
        "use_when": [
            "You need to discuss a specific track or artifact.",
            "You need to read comment threads attached to a readable target.",
        ],
        "do_not_use_when": [
            "You need task comments; only track and artifact targets are supported.",
            "You need comment resolution/edit/delete lifecycle mutation.",
        ],
        "capability_boundary": "Comments require active-buddy read access to the target track or artifact.",
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

    def add(tool: str, action: str, *, plain_description: str, mutates: str, open_world: bool) -> None:
        rows[(tool, action)] = {
            "title": f"{tool}.{action}",
            "plain_description": plain_description,
            "use_when": [],
            "do_not_use_when": [],
            "inputs_explained": {},
            "side_effects": _side_effects(
                mutates=mutates,
                writes=["runtime objects" if mutates == "runtime_objects" else ""],
                does_not_write=[],
                durability="durable" if mutates != "none" else "none",
                idempotency="idempotent read" if mutates == "none" else "conditionally idempotent",
            ),
            "risk_hints": _risk_hints(mutates=mutates, open_world=open_world),
            "success_means": "Operation completed with structured tool feedback.",
            "common_failures": [],
        }

    add("task", "create", plain_description="Create one active-buddy private task.", mutates="runtime_objects", open_world=False)
    add("task", "list", plain_description="List active-buddy private tasks.", mutates="none", open_world=False)
    add("task", "get", plain_description="Get one active-buddy private task.", mutates="none", open_world=False)
    add("task", "update", plain_description="Update one active-buddy private task.", mutates="runtime_objects", open_world=False)
    add("task", "archive", plain_description="Archive one active-buddy private task.", mutates="runtime_objects", open_world=False)

    add("track", "create", plain_description="Create one PM-owned shared track page.", mutates="runtime_objects", open_world=False)
    add("track", "list", plain_description="List non-archived track page summaries.", mutates="none", open_world=False)
    add("track", "open", plain_description="Open one non-archived shared track page.", mutates="none", open_world=False)
    add("track", "update_now", plain_description="Update now/state/health on non-archived track page.", mutates="runtime_objects", open_world=False)
    add("track", "add_material", plain_description="Publish shared material to track page.", mutates="runtime_objects", open_world=False)
    add("track", "add_update", plain_description="Append timeline update to track page.", mutates="runtime_objects", open_world=False)
    add("track", "add_proof", plain_description="Publish close proof to track page.", mutates="runtime_objects", open_world=False)
    add("track", "archive", plain_description="Archive one PM-owned shared track page.", mutates="runtime_objects", open_world=False)

    add("artifact", "get", plain_description="Get one readable artifact with full content.", mutates="none", open_world=False)
    add("artifact", "create_revision", plain_description="Create one active-buddy private artifact draft.", mutates="runtime_objects", open_world=False)
    add("artifact", "update_metadata", plain_description="Update active-buddy-owned artifact metadata.", mutates="runtime_objects", open_world=False)

    add("buddybox", "desc", plain_description="Describe buddybox capability.", mutates="none", open_world=False)
    add("buddybox", "list", plain_description="List buddybox files.", mutates="none", open_world=False)
    add("buddybox", "read", plain_description="Read one buddybox file.", mutates="none", open_world=False)
    add("buddybox", "write", plain_description="Write one buddybox file.", mutates="runtime_files", open_world=False)
    add("buddybox", "delete", plain_description="Delete one buddybox file.", mutates="runtime_files", open_world=False)

    add("context", "get", plain_description="Get full runtime context sections.", mutates="none", open_world=False)
    add("context", "summarize", plain_description="Get compact runtime context.", mutates="none", open_world=False)
    add("context", "list_sources", plain_description="List context source descriptors.", mutates="none", open_world=False)

    add("evidence", "issue_browser", plain_description="Issue browser evidence token metadata.", mutates="broker_token", open_world=False)
    add("evidence", "approve_downgrade", plain_description="Issue downgrade approval metadata.", mutates="broker_token", open_world=False)

    add("message", "send", plain_description="Send one durable direct buddy-to-buddy message.", mutates="runtime_objects", open_world=False)
    add("message", "list", plain_description="List active-buddy inbox messages.", mutates="none", open_world=False)

    add("comment", "add", plain_description="Add one comment to a readable track or artifact.", mutates="runtime_objects", open_world=False)
    add("comment", "list", plain_description="List comments for a readable track or artifact.", mutates="none", open_world=False)

    add("search", "status", plain_description="Read search backend status.", mutates="none", open_world=True)
    add("search", "request", plain_description="Issue search request intent.", mutates="none", open_world=True)
    add("search", "open_browser", plain_description="Open browser query URL.", mutates="browser_session", open_world=True)

    rows[("track", "create")].update(
        {
            "use_when": [
                "You need PM to initialize one shared track page before publishing materials/proof.",
            ],
            "do_not_use_when": [
                "You need to write artifact markdown body content; use artifact.create_revision.",
            ],
            "inputs_explained": {
                "track_id": "Stable id for one track page object.",
                "title": "Human-readable track title.",
                "outcome": "Target outcome for this track.",
                "appetite": "Expected timebox text.",
                "now": "Current next step and blocker object.",
            },
            "side_effects": _side_effects(
                mutates="runtime_objects",
                writes=["buddyswitch/objects/tracks/<track-id>.json"],
                does_not_write=["artifacts", "tasks"],
                durability="durable",
                idempotency="non-idempotent create",
            ),
            "success_means": "One PM-owned non-archived track object was created and is readable via track.open.",
            "common_failures": [
                "active buddy is not pm",
                "track_id already exists",
                "payload fields are missing or invalid",
            ],
        }
    )
    rows[("track", "open")].update(
        {
            "use_when": [
                "You need current shared material/proof refs and track timeline from a non-archived track.",
            ],
            "do_not_use_when": [
                "You need full markdown body text for an artifact id; use artifact.get.",
            ],
            "inputs_explained": {
                "track_id": "Track page id to read.",
            },
            "side_effects": _side_effects(
                mutates="none",
                writes=[],
                does_not_write=["tracks", "artifacts", "tasks"],
                durability="none",
                idempotency="idempotent read",
            ),
            "success_means": "Returned one track page view with current shared_materials and current close_proof refs only.",
            "common_failures": [
                "track_id not found",
                "track is archived",
            ],
        }
    )
    rows[("track", "add_material")].update(
        {
            "use_when": [
                "You need to publish an existing active-buddy-owned draft artifact as current shared track material.",
            ],
            "do_not_use_when": [
                "You need to create artifact body content from scratch; use artifact.create_revision first.",
            ],
            "inputs_explained": {
                "track_id": "Non-archived track target.",
                "artifact_id": "Existing active-buddy draft artifact id.",
                "label": "Track-facing display label for the material slot.",
                "summary": "Short track-facing summary for the publication row.",
            },
            "side_effects": _side_effects(
                mutates="runtime_objects",
                writes=[
                    "artifact publication fields (status, published_to_track, is_current)",
                    "track.shared_materials row with current flag",
                ],
                does_not_write=["artifact body content"],
                durability="durable",
                idempotency="non-idempotent publish",
            ),
            "success_means": "Artifact is published and track.shared_materials has a new current ref for the publication slot.",
            "common_failures": [
                "track is archived",
                "artifact is missing, not owned, non-draft, duplicate, or cross-track bound",
                "legacy inline kind/content payload fields were sent",
            ],
        }
    )
    rows[("track", "add_proof")].update(
        {
            "use_when": [
                "You need to publish an existing active-buddy-owned draft artifact as current close proof.",
            ],
            "do_not_use_when": [
                "You need to create proof markdown body content first; use artifact.create_revision.",
            ],
            "inputs_explained": {
                "track_id": "Non-archived track target.",
                "artifact_id": "Existing active-buddy draft artifact id.",
                "label": "Track-facing label for proof slot.",
                "summary": "Proof summary text for close_proof and update row.",
            },
            "side_effects": _side_effects(
                mutates="runtime_objects",
                writes=[
                    "artifact publication fields (status, published_to_track, is_current)",
                    "track.close_proof row with current flag",
                    "track.updates proof row",
                ],
                does_not_write=["artifact body content"],
                durability="durable",
                idempotency="non-idempotent publish",
            ),
            "success_means": "Artifact is published as close proof, track.close_proof is updated, and proof update row is appended.",
            "common_failures": [
                "track is archived",
                "artifact is missing, not owned, non-draft, duplicate, or cross-track bound",
                "legacy inline kind/content payload fields were sent",
            ],
        }
    )
    rows[("artifact", "create_revision")].update(
        {
            "use_when": [
                "You need one active-buddy private markdown draft/revision artifact.",
            ],
            "do_not_use_when": [
                "You need to publish shared material/proof directly; use track.add_material or track.add_proof.",
            ],
            "inputs_explained": {
                "artifact_id": "Optional explicit artifact id; autogenerated when omitted.",
                "title": "Artifact title for summaries.",
                "summary": "Short summary line.",
                "template": "Artifact V1 template kind.",
                "body": "Non-empty markdown body text.",
                "supersedes_artifact_id": "Optional current draft/published artifact id for revision linkage.",
                "source_refs": "Optional structured provenance refs.",
                "read_claim": "Optional source_refs readability hint.",
            },
            "side_effects": _side_effects(
                mutates="runtime_objects",
                writes=["buddyswitch/objects/artifacts/<artifact-id>.json"],
                does_not_write=["track objects"],
                durability="durable",
                idempotency="non-idempotent create",
            ),
            "success_means": "Created one private draft artifact only; no track publication happened.",
            "common_failures": [
                "status or published_to_track was supplied",
                "template/body/title payload validation failed",
                "supersedes_artifact_id is invalid for current revision scope",
            ],
        }
    )
    rows[("artifact", "get")].update(
        {
            "use_when": [
                "You need full markdown body content for one explicit readable artifact id.",
            ],
            "do_not_use_when": [
                "You only need current artifact refs; use track.open.",
            ],
            "inputs_explained": {
                "artifact_id": "Explicit artifact id to read.",
            },
            "side_effects": _side_effects(
                mutates="none",
                writes=[],
                does_not_write=["tracks", "artifacts"],
                durability="none",
                idempotency="idempotent read",
            ),
            "success_means": "Returned full artifact body for an id readable by owner or by track publication scope.",
            "common_failures": [
                "artifact_id missing or not found",
                "artifact is private draft owned by another buddy",
                "artifact publication track is archived",
            ],
        }
    )

    rows[("comment", "add")].update(
        {
            "use_when": [
                "You need to add one plain-text comment to a readable track/artifact target.",
                "You need optional thread reply, anchor, mention, or artifact revision-chain context.",
            ],
            "do_not_use_when": [
                "You need to mutate comment lifecycle status (resolve/reopen/edit/delete).",
            ],
            "inputs_explained": {
                "target_type": "track, artifact, or artifact_section target scope.",
                "target_id": "Readable target object id.",
                "content": "Non-empty plain-text comment body.",
                "reply_to": "Optional parent comment id on the same target thread.",
                "artifact_revision_id": "Optional artifact revision id in the same revision chain as target.",
                "anchor": "Required for artifact_section targets; optional anchor text otherwise.",
                "mentions": "Optional list of manifest-declared buddy ids to mention.",
            },
            "side_effects": _side_effects(
                mutates="runtime_objects",
                writes=["buddyswitch/objects/comments/<comment-id>.json"],
                does_not_write=["tracks", "artifacts", "tasks"],
                durability="durable",
                idempotency="non-idempotent create",
            ),
            "success_means": "Created one durable comment row attached to the selected readable target thread.",
            "common_failures": [
                "target is unreadable or unsupported",
                "reply_to is missing, cross-target, or out of scope",
                "artifact_revision_id is outside target revision chain",
                "anchor/mentions/content payload validation failed",
            ],
        }
    )

    rows[("comment", "list")].update(
        {
            "use_when": [
                "You need comment rows and thread view for one readable target.",
                "You need optional status filter with open/resolved/all.",
            ],
            "do_not_use_when": [
                "You need to mutate comment lifecycle status.",
            ],
            "inputs_explained": {
                "target_type": "track, artifact, or artifact_section target scope.",
                "target_id": "Readable target object id.",
                "status": "Optional filter: open, resolved, or all (default all).",
            },
            "side_effects": _side_effects(
                mutates="none",
                writes=[],
                does_not_write=["comments", "tracks", "artifacts", "tasks"],
                durability="none",
                idempotency="idempotent read",
            ),
            "success_means": "Returned comment rows, grouped threads, and status counts for the target.",
            "common_failures": [
                "target is unreadable or unsupported",
                "status filter is not one of open|resolved|all",
            ],
        }
    )

    return rows


def compact_tool_affordances() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for tool, payload in _CAPABILITIES.items():
        rows[tool] = {
            "capability": payload.get("title", ""),
            "when_to_use": payload.get("use_when", []),
            "when_not_to_use": payload.get("do_not_use_when", []),
            "state_effect": payload.get("capability_boundary", _CAPABILITY_BOUNDARY_DEFAULT),
            "returns": payload.get("plain_description", ""),
        }
    return rows


def capability_semantics(tool: str) -> dict[str, Any]:
    payload = _CAPABILITIES.get(tool)
    if payload is None:
        return {
            "title": tool,
            "plain_description": "No semantic capability row is registered for this tool.",
            "use_when": [],
            "do_not_use_when": [],
            "capability_boundary": _CAPABILITY_BOUNDARY_DEFAULT,
        }
    return dict(payload)


def action_semantics(tool: str, action: str) -> dict[str, Any]:
    rows = _action_rows()
    payload = rows.get((tool, action))
    if payload is None:
        return {
            "title": f"{tool}.{action}",
            "plain_description": "No semantic action row is registered for this action.",
            "use_when": [],
            "do_not_use_when": [],
            "inputs_explained": {},
            "side_effects": _side_effects(mutates="unknown", writes=[], does_not_write=[], durability="unknown", idempotency="unknown"),
            "risk_hints": _risk_hints(mutates="unknown", open_world=False),
            "success_means": "No semantic action row is registered.",
            "common_failures": [],
        }
    return dict(payload)


def semantic_coverage_errors(registry: list[dict[str, Any]]) -> list[str]:
    rows = _action_rows()
    errors: list[str] = []
    for tool_row in registry:
        tool = tool_row.get("tool")
        if not isinstance(tool, str):
            continue
        if tool not in _CAPABILITIES:
            errors.append(f"missing capability semantics for tool '{tool}'")
        actions = tool_row.get("actions")
        if not isinstance(actions, list):
            continue
        for action_row in actions:
            action = action_row.get("name")
            if not isinstance(action, str):
                continue
            if (tool, action) not in rows:
                errors.append(f"missing action semantics for '{tool}.{action}'")
    return errors
