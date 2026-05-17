#!/usr/bin/env python3
"""Runtime semantic descriptions for env.tool capabilities and actions."""

from __future__ import annotations

from typing import Any

_CAPABILITY_BOUNDARY_DEFAULT = "Service-level permission and ownership checks remain authoritative."

_CAPABILITIES: dict[str, dict[str, Any]] = {
    "task": {
        "title": "Task Management",
        "plain_description": "Manage active-buddy durable task work items used by track and artifact tools.",
        "use_when": [
            "You need to create, list, read, update, or archive tasks owned by the active buddy.",
            "You need explicit task ids for artifact revisions.",
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
    "buddybox": {
        "title": "Buddybox Files",
        "plain_description": "Operate active-buddy private files through logical_name values.",
        "use_when": [
            "You need active buddy private files for drafts, exports, logs, or generated files.",
            "Use artifact.create_revision when the host decides content must become product-readable across buddies.",
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
            "You need broadcast or group messaging; use repeated message.send instead.",
            "You need read receipts, message status, or read tracking.",
            "You need object-level discussion; use comment.add for track/artifact comments.",
            "You need to edit or delete sent messages.",
        ],
        "capability_boundary": "Messages are direct buddy-to-buddy only. Self-send, broadcast, status, and read receipts are not supported.",
    },
    "comment": {
        "title": "Object Comments",
        "plain_description": "Add and list plain-text comments on readable track and artifact targets.",
        "use_when": [
            "You need to discuss a specific track or artifact.",
            "You need to read discussion threads attached to a readable target.",
        ],
        "do_not_use_when": [
            "You need task comments; only track and artifact targets are supported.",
            "You need comment resolution, status, or edit/delete.",
            "You need direct buddy messaging; use message.send.",
            "You need broadcast or review workflows.",
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

    add("task", "create", plain_description="Create one active-buddy durable task.", mutates="runtime_objects", open_world=False)
    add("task", "list", plain_description="List active-buddy tasks.", mutates="none", open_world=False)
    add("task", "get", plain_description="Get one active-buddy task.", mutates="none", open_world=False)
    add("task", "update", plain_description="Update one active-buddy task.", mutates="runtime_objects", open_world=False)
    add("task", "archive", plain_description="Archive one active-buddy task.", mutates="runtime_objects", open_world=False)

    add("track", "list", plain_description="List readable tracks.", mutates="none", open_world=False)
    add("track", "get", plain_description="Read one track context.", mutates="none", open_world=False)
    add("track", "join", plain_description="Create or reuse active-buddy track-task relation.", mutates="runtime_objects", open_world=False)
    add("track", "create", plain_description="Create one PM-owned track.", mutates="runtime_objects", open_world=False)
    add("track", "update", plain_description="Update one PM-owned track.", mutates="runtime_objects", open_world=False)
    add("track", "archive", plain_description="Archive one PM-owned track.", mutates="runtime_objects", open_world=False)
    add("track", "attach_task", plain_description="Attach active-buddy task to track.", mutates="runtime_objects", open_world=False)
    add("track", "detach_task", plain_description="Detach active-buddy task from track.", mutates="runtime_objects", open_world=False)

    add("artifact", "list", plain_description="List current artifact summaries for a track.", mutates="none", open_world=False)
    add("artifact", "get", plain_description="Get one readable artifact with content.", mutates="none", open_world=False)
    add("artifact", "validate_payload", plain_description="Validate artifact create payload.", mutates="none", open_world=False)
    add("artifact", "create_revision", plain_description="Create one artifact revision.", mutates="runtime_objects", open_world=False)
    add("artifact", "update_metadata", plain_description="Update owned artifact metadata.", mutates="runtime_objects", open_world=False)

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
