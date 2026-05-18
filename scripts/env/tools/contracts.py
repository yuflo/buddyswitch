#!/usr/bin/env python3
"""Runless env.tool contract registry."""

from __future__ import annotations

from typing import Any

from env.tools import semantics

MUTATES_NONE = "none"
MUTATES_RUNTIME_OBJECTS = "runtime_objects"
MUTATES_RUNTIME_FILES = "runtime_files"
MUTATES_BROKER_TOKEN = "broker_token"
MUTATES_BROWSER_SESSION = "browser_session"

TOOL_REGISTRY: list[dict[str, Any]] = [
    {
        "tool": "task",
        "cli_resource": "task",
        "command": "python3 scripts/env/client.py task <operation>",
        "scope": "active-buddy private task work items",
        "actions": [
            {
                "name": "create",
                "payload_fields": ["task_id", "title", "summary", "status", "track_id"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "task.create",
                "authority": "task.buddy_scope",
                "preconditions": ["active buddy owns task.create permission"],
                "returns": ["task_id", "task"],
            },
            {
                "name": "list",
                "payload_fields": ["status", "track_id", "limit"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "task.read",
                "authority": "task.buddy_scope",
                "preconditions": ["active buddy owns task.read permission"],
                "returns": ["tasks"],
            },
            {
                "name": "get",
                "payload_fields": ["task_id"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "task.read",
                "authority": "task.buddy_scope",
                "preconditions": ["task_id references an active-buddy task"],
                "returns": ["task"],
            },
            {
                "name": "update",
                "payload_fields": ["task_id", "title", "summary", "status", "track_id"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "task.update",
                "authority": "task.buddy_scope",
                "preconditions": ["task_id references an active-buddy task"],
                "returns": ["task"],
            },
            {
                "name": "archive",
                "payload_fields": ["task_id"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "task.archive",
                "authority": "task.buddy_scope",
                "preconditions": ["task_id references an active-buddy task"],
                "returns": ["task"],
            },
        ],
    },
    {
        "tool": "track",
        "cli_resource": "track",
        "command": "python3 scripts/env/client.py track <operation>",
        "scope": "shared track progress pages and publication timeline",
        "actions": [
            {
                "name": "create",
                "payload_fields": ["track_id", "title", "outcome", "appetite", "now", "state", "health"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "track.create",
                "authority": "pm.lifecycle_authority",
                "preconditions": ["active buddy is pm"],
                "returns": ["track"],
            },
            {
                "name": "list",
                "payload_fields": ["state", "limit"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "track.read",
                "authority": "track.lookup",
                "preconditions": ["active buddy owns track.read permission"],
                "returns": ["tracks"],
            },
            {
                "name": "open",
                "payload_fields": ["track_id"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "track.read",
                "authority": "track.lookup",
                "preconditions": ["track_id references an existing non-archived track"],
                "returns": ["track"],
            },
            {
                "name": "update_now",
                "payload_fields": ["track_id", "now", "state", "health"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "track.update_now",
                "authority": "track.shared_mutation",
                "preconditions": ["track_id references an existing non-archived track"],
                "returns": ["track"],
            },
            {
                "name": "add_material",
                "payload_fields": ["track_id", "artifact_id", "label", "summary"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "track.add_material",
                "authority": "track.shared_mutation",
                "preconditions": [
                    "track_id references an existing non-archived track",
                    "artifact_id references an active-buddy-owned draft artifact",
                    "artifact is not already published to another track",
                ],
                "returns": ["artifact_id", "track", "state_changes"],
            },
            {
                "name": "add_update",
                "payload_fields": ["track_id", "summary", "kind", "refs"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "track.add_update",
                "authority": "track.shared_mutation",
                "preconditions": ["track_id references an existing non-archived track"],
                "returns": ["track", "update"],
            },
            {
                "name": "add_proof",
                "payload_fields": ["track_id", "artifact_id", "label", "summary"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "track.add_proof",
                "authority": "track.shared_mutation",
                "preconditions": [
                    "track_id references an existing non-archived track",
                    "artifact_id references an active-buddy-owned draft artifact",
                    "artifact is not already published to another track",
                ],
                "returns": ["artifact_id", "track", "state_changes"],
            },
            {
                "name": "archive",
                "payload_fields": ["track_id"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "track.archive",
                "authority": "pm.lifecycle_authority",
                "preconditions": ["active buddy is pm", "track_id references an existing track"],
                "returns": ["track"],
            },
        ],
    },
    {
        "tool": "artifact",
        "cli_resource": "artifact",
        "command": "python3 scripts/env/client.py artifact <operation>",
        "scope": "private drafts and published track material/proof artifacts",
        "actions": [
            {
                "name": "get",
                "payload_fields": ["artifact_id"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "artifact.read",
                "authority": "artifact.owner_or_publication_boundary",
                "preconditions": ["artifact_id references a readable artifact"],
                "returns": ["artifact"],
            },
            {
                "name": "create_revision",
                "payload_fields": [
                    "artifact_id",
                    "title",
                    "summary",
                    "template",
                    "body",
                    "supersedes_artifact_id",
                    "source_refs",
                    "read_claim",
                ],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "artifact.create",
                "authority": "artifact.buddy_scope",
                "preconditions": [
                    "active buddy owns artifact.create permission",
                    "status and published_to_track are not accepted create_revision inputs",
                ],
                "returns": ["artifact"],
            },
            {
                "name": "update_metadata",
                "payload_fields": ["artifact_id", "title", "summary", "template", "body", "source_refs", "read_claim"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "artifact.update",
                "authority": "artifact.buddy_scope",
                "preconditions": ["artifact_id references an active-buddy-owned artifact"],
                "returns": ["artifact"],
            },
        ],
    },
    {
        "tool": "buddybox",
        "cli_resource": "buddybox",
        "command": "python3 scripts/env/client.py buddybox <operation>",
        "scope": "active-buddy private local workspace files",
        "actions": [
            {
                "name": "desc",
                "payload_fields": [],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "buddybox.read",
                "authority": "buddybox.private_local_scope",
                "preconditions": ["active buddy is bound to an instance"],
                "returns": ["buddybox_desc"],
            },
            {
                "name": "list",
                "payload_fields": ["logical_name", "recursive", "limit"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "buddybox.read",
                "authority": "buddybox.private_local_scope",
                "preconditions": ["logical_name stays within active buddy private file capability when provided"],
                "returns": ["files"],
            },
            {
                "name": "read",
                "payload_fields": ["logical_name", "encoding"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "buddybox.read",
                "authority": "buddybox.private_local_scope",
                "preconditions": ["logical_name references one active buddy private file"],
                "returns": ["private_file"],
            },
            {
                "name": "write",
                "payload_fields": ["logical_name", "content", "content_base64", "content_type"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_FILES,
                "required_permission": "buddybox.write",
                "authority": "buddybox.private_local_scope",
                "preconditions": [
                    "logical_name stays inside active buddy private file capability",
                    "payload provides exactly one of content or content_base64",
                ],
                "returns": ["private_file"],
            },
            {
                "name": "delete",
                "payload_fields": ["logical_name"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_FILES,
                "required_permission": "buddybox.delete",
                "authority": "buddybox.private_local_scope",
                "preconditions": ["logical_name resolves inside active buddy private file capability"],
                "returns": ["deleted", "logical_name"],
            },
        ],
    },
    {
        "tool": "context",
        "cli_resource": "context",
        "command": "python3 scripts/env/client.py context <operation>",
        "scope": "runless read-only orientation payload",
        "actions": [
            {
                "name": "get",
                "payload_fields": ["track_id", "task_id", "limit"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "none",
                "authority": "read-only context discovery",
                "preconditions": ["filters are valid"],
                "returns": ["sections", "tool_catalog", "decision_surface"],
            },
            {
                "name": "summarize",
                "payload_fields": ["track_id", "task_id", "limit"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "none",
                "authority": "read-only context discovery",
                "preconditions": ["filters are valid"],
                "returns": ["summary", "candidate_tracks", "buddybox_desc"],
            },
            {
                "name": "list_sources",
                "payload_fields": [],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "none",
                "authority": "read-only context discovery",
                "preconditions": ["none"],
                "returns": ["sources"],
            },
        ],
    },
    {
        "tool": "evidence",
        "cli_resource": "evidence",
        "command": "python3 scripts/env/client.py evidence <operation>",
        "scope": "target-scoped browser evidence for market quality gates",
        "actions": [
            {
                "name": "issue_browser",
                "payload_fields": ["target_type", "target_id", "mode"],
                "kind": "issue",
                "mutates": MUTATES_BROKER_TOKEN,
                "required_permission": "evidence.issue",
                "authority": "market.evidence_scope",
                "preconditions": ["target_type is artifact", "target_id references readable target"],
                "returns": ["tool_evidence"],
            },
            {
                "name": "approve_downgrade",
                "payload_fields": ["target_type", "target_id", "reason"],
                "kind": "issue",
                "mutates": MUTATES_BROKER_TOKEN,
                "required_permission": "evidence.approve",
                "authority": "market.evidence_scope",
                "preconditions": ["target_type is artifact", "reason is non-empty"],
                "returns": ["tool_evidence"],
            },
        ],
    },
    {
        "tool": "message",
        "cli_resource": "message",
        "command": "python3 scripts/env/client.py message <operation>",
        "scope": "direct buddy-to-buddy inbox messaging",
        "actions": [
            {
                "name": "send",
                "payload_fields": ["to_buddy", "content", "reply_to"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "message.send",
                "authority": "message.direct_buddy_channel",
                "preconditions": ["to_buddy is a declared manifest buddy", "to_buddy != active_buddy"],
                "returns": ["message_id", "message"],
            },
            {
                "name": "list",
                "payload_fields": ["buddy"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "message.list",
                "authority": "message.active_buddy_inbox",
                "preconditions": ["active buddy owns message.list permission"],
                "returns": ["messages"],
            },
        ],
    },
    {
        "tool": "comment",
        "cli_resource": "comment",
        "command": "python3 scripts/env/client.py comment <operation>",
        "scope": "target-scoped plain-text comments on readable tracks and artifacts",
        "actions": [
            {
                "name": "add",
                "payload_fields": ["target_type", "target_id", "content", "reply_to"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "comment.add",
                "authority": "target.read_boundary",
                "preconditions": ["target_type is track or artifact", "active buddy has read access to target"],
                "returns": ["comment_id", "comment"],
            },
            {
                "name": "list",
                "payload_fields": ["target_type", "target_id"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "comment.list",
                "authority": "target.read_boundary",
                "preconditions": ["target_type is track or artifact", "active buddy has read access to target"],
                "returns": ["comments"],
            },
        ],
    },
    {
        "tool": "search",
        "cli_resource": "search",
        "command": "python3 scripts/env/client.py search <operation>",
        "scope": "runtime-visible search capability boundary",
        "backend_model": {
            "allowed_backends": ["browser", "search_api"],
            "allowed_engines": ["google", "web", "reddit", "x"],
            "native_codex_web_search": "disabled",
            "search_api_provider": "not-configured",
        },
        "actions": [
            {
                "name": "status",
                "payload_fields": [],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "none",
                "authority": "profile.search_boundary",
                "preconditions": ["active instance is available"],
                "returns": ["backend_status"],
            },
            {
                "name": "request",
                "payload_fields": ["query", "backend", "engine"],
                "kind": "request",
                "mutates": MUTATES_NONE,
                "required_permission": "none",
                "authority": "profile.search_boundary",
                "preconditions": ["query is non-empty"],
                "returns": ["target_url", "backend", "engine"],
            },
            {
                "name": "open_browser",
                "payload_fields": ["query", "engine"],
                "kind": "open",
                "mutates": MUTATES_BROWSER_SESSION,
                "required_permission": "none",
                "authority": "profile.search_boundary",
                "preconditions": ["query is non-empty"],
                "returns": ["target_url", "backend", "engine"],
            },
        ],
    },
]


def tool_registry_by_tool() -> dict[str, dict[str, Any]]:
    return {row["tool"]: row for row in TOOL_REGISTRY}


def get_tool_spec(tool: str) -> dict[str, Any] | None:
    return tool_registry_by_tool().get(tool)


def get_action_spec(tool: str, action: str) -> dict[str, Any] | None:
    spec = get_tool_spec(tool)
    if spec is None:
        return None
    for row in spec.get("actions", []):
        if row.get("name") == action:
            return row
    return None


def supported_actions(tool: str) -> set[str]:
    spec = get_tool_spec(tool)
    if spec is None:
        return set()
    return {row.get("name") for row in spec.get("actions", []) if isinstance(row.get("name"), str)}


def supported_tools() -> set[str]:
    return {row.get("tool") for row in TOOL_REGISTRY if isinstance(row.get("tool"), str)}


def semantic_contract_errors() -> list[str]:
    return semantics.semantic_coverage_errors(TOOL_REGISTRY)


def compact_tool_affordances() -> dict[str, dict[str, str]]:
    return semantics.compact_tool_affordances()


def env_tools_description() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for spec in TOOL_REGISTRY:
        tool = spec.get("tool")
        if not isinstance(tool, str) or not tool:
            continue
        capability_row = semantics.capability_semantics(tool)
        operations: list[str] = []
        payload_fields: dict[str, list[str]] = {}
        action_semantics: dict[str, dict[str, Any]] = {}
        for action_spec in spec.get("actions", []):
            action = action_spec.get("name")
            if not isinstance(action, str) or not action:
                continue
            operations.append(action)
            payload_fields[action] = list(action_spec.get("payload_fields", []))
            action_semantics[action] = semantics.action_semantics(tool, action)
        rows[tool] = {
            "title": capability_row.get("title", ""),
            "plain_description": capability_row.get("plain_description", ""),
            "use_when": list(capability_row.get("use_when", [])),
            "do_not_use_when": list(capability_row.get("do_not_use_when", [])),
            "capability_boundary": capability_row.get("capability_boundary", ""),
            "command": spec.get("command"),
            "scope": spec.get("scope"),
            "broker_method": "env.tool",
            "envelope": {"tool": tool, "action": "<action>", "args": "<object>"},
            "cli_resource": spec.get("cli_resource"),
            "operations": operations,
            "payload_fields": payload_fields,
            "action_semantics": action_semantics,
            "feedback_source": "runtime/tool response fields",
            "authoritative_fields": [
                "permission_boundary",
                "allowed_next_actions",
                "allowed_next_action_options",
                "state_changed",
                "durability",
            ],
        }
        if isinstance(spec.get("backend_model"), dict):
            rows[tool]["backend_model"] = dict(spec["backend_model"])
    return rows


def operation_semantics() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for tool_spec in TOOL_REGISTRY:
        tool = tool_spec.get("tool")
        if not isinstance(tool, str) or not tool:
            continue
        for action_spec in tool_spec.get("actions", []):
            action = action_spec.get("name")
            if not isinstance(action, str) or not action:
                continue
            key = f"{tool}.{action}"
            rows[key] = {
                "kind": action_spec.get("kind"),
                "mutates": action_spec.get("mutates"),
                "required_permission": action_spec.get("required_permission"),
                "authority": action_spec.get("authority"),
                "requires": list(action_spec.get("preconditions", [])),
                "returns": list(action_spec.get("returns", [])),
                "risk_hints": semantics.action_semantics(tool, action).get("risk_hints", {}),
            }
    return rows
