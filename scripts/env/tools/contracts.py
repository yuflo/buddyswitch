#!/usr/bin/env python3
"""Static env.tool contract registry.

This registry is intentionally static and policy-light:
- It defines tool/action names, payload views, and operation semantics.
- It does not encode state-dependent workflow policy.
- Runtime services remain authoritative for dynamic permission/state checks.
"""

from __future__ import annotations

from typing import Any

# Allowed mutability surface values used by operation semantics.
MUTATES_NONE = "none"
MUTATES_INSTANCE_BINDING = "instance_binding"
MUTATES_RUNTIME_OBJECTS = "runtime_objects"
MUTATES_RUN_COMMIT = "run_commit"
MUTATES_BROKER_TOKEN = "broker_token"
MUTATES_BROWSER_SESSION = "browser_session"

TOOL_REGISTRY: list[dict[str, Any]] = [
    {
        "tool": "task",
        "cli_resource": "task",
        "command": "python3 scripts/env/client.py task <operation>",
        "scope": "active-buddy runtime-enforced",
        "actions": [
            {
                "name": "create",
                "payload_fields": ["title", "summary"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "task.create",
                "authority": "manifest.permission",
                "preconditions": ["active buddy owns task.create permission"],
                "returns": ["task_id", "task", "current_binding"],
            },
            {
                "name": "list",
                "payload_fields": [],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "task.read",
                "authority": "manifest.permission",
                "preconditions": ["active buddy owns task.read permission"],
                "returns": ["tasks", "current_binding"],
            },
            {
                "name": "get",
                "payload_fields": ["task_id"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "task.read",
                "authority": "manifest.permission + task.buddy_scope",
                "preconditions": ["task_id references an active-buddy task"],
                "returns": ["task_id", "task", "current_binding"],
            },
            {
                "name": "get_current",
                "payload_fields": [],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "task.read",
                "authority": "manifest.permission + instance.binding",
                "preconditions": ["none"],
                "returns": ["task", "current_binding"],
            },
            {
                "name": "set_current",
                "payload_fields": ["task_id"],
                "kind": "bind",
                "mutates": MUTATES_INSTANCE_BINDING,
                "required_permission": "task.read",
                "authority": "task.buddy_scope + instance.binding",
                "preconditions": ["task_id references an active-buddy task"],
                "returns": ["task_id", "task", "current_binding"],
            },
            {
                "name": "update",
                "payload_fields": ["task_id", "title", "summary", "status"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "task.update",
                "authority": "manifest.permission + task.buddy_scope",
                "preconditions": ["task_id references an active-buddy task"],
                "returns": ["task_id", "task", "current_binding"],
            },
            {
                "name": "archive",
                "payload_fields": ["task_id"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "task.archive",
                "authority": "manifest.permission + task.buddy_scope",
                "preconditions": ["task_id references an active-buddy task"],
                "returns": ["task_id", "task", "current_binding"],
            },
        ],
    },
    {
        "tool": "track",
        "cli_resource": "track",
        "command": "python3 scripts/env/client.py track <operation>",
        "scope": "readable tracks; PM lifecycle authority; active-buddy task linkage",
        "actions": [
            {
                "name": "list",
                "payload_fields": [],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "track.read",
                "authority": "manifest.permission",
                "preconditions": ["active buddy owns track.read permission"],
                "returns": ["tracks", "discovery_summary", "current_binding"],
            },
            {
                "name": "get",
                "payload_fields": ["track_id"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "track.read",
                "authority": "manifest.permission + track.lookup",
                "preconditions": ["track_id references an existing track"],
                "returns": ["track_id", "track", "track_context_summary", "current_binding"],
            },
            {
                "name": "get_current",
                "payload_fields": [],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "track.read",
                "authority": "manifest.permission + instance.binding",
                "preconditions": ["none"],
                "returns": ["track", "current_binding"],
            },
            {
                "name": "create",
                "payload_fields": ["track_id", "title", "status", "current_buddy", "next_buddy", "summary"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "track.create",
                "authority": "pm.lifecycle_authority + manifest.permission",
                "preconditions": ["active buddy is pm"],
                "returns": ["track_id", "track", "current_binding"],
            },
            {
                "name": "update",
                "payload_fields": ["track_id", "title", "status", "current_buddy", "next_buddy", "summary"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "track.update",
                "authority": "pm.lifecycle_authority + manifest.permission",
                "preconditions": ["active buddy is pm", "track_id references an existing track"],
                "returns": ["track_id", "track", "current_binding"],
            },
            {
                "name": "advance",
                "payload_fields": ["track_id", "status", "current_buddy", "next_buddy", "summary"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "track.advance",
                "authority": "pm.lifecycle_authority + manifest.permission",
                "preconditions": ["active buddy is pm", "track_id references an existing track"],
                "returns": ["track_id", "track", "current_binding"],
            },
            {
                "name": "archive",
                "payload_fields": ["track_id"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "track.archive",
                "authority": "pm.lifecycle_authority + manifest.permission",
                "preconditions": ["active buddy is pm", "track_id references an existing track"],
                "returns": ["track_id", "track", "current_binding"],
            },
            {
                "name": "attach_task",
                "payload_fields": ["track_id", "task_id"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "task.update",
                "authority": "task.buddy_scope + track.lookup",
                "preconditions": ["task_id references an active-buddy task", "track_id references an existing track"],
                "returns": ["track_id", "task_id", "track", "task", "current_binding"],
            },
            {
                "name": "detach_task",
                "payload_fields": ["track_id", "task_id"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "task.update",
                "authority": "task.buddy_scope + track.lookup",
                "preconditions": ["task_id references an active-buddy task", "track_id references an existing track"],
                "returns": ["track_id", "task_id", "track", "task", "current_binding"],
            },
        ],
    },
    {
        "tool": "artifact",
        "cli_resource": "artifact",
        "command": "python3 scripts/env/client.py artifact <operation>",
        "scope": "active current task listing; active-buddy task artifact reads and writes",
        "actions": [
            {
                "name": "list",
                "payload_fields": [],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "artifact.read",
                "authority": "manifest.permission + instance.binding",
                "preconditions": ["none"],
                "returns": ["task_id", "artifacts", "current_binding"],
            },
            {
                "name": "get",
                "payload_fields": ["artifact_id"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "artifact.read",
                "authority": "artifact.buddy_scope",
                "preconditions": ["artifact_id references an active-buddy artifact"],
                "returns": ["artifact_id", "artifact", "current_binding"],
            },
            {
                "name": "get_current",
                "payload_fields": ["kind"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "artifact.read",
                "authority": "manifest.permission + instance.binding",
                "preconditions": ["none"],
                "returns": ["task_id", "artifacts", "current_binding"],
            },
            {
                "name": "validate_payload",
                "payload_fields": ["artifact_id", "task_id", "kind", "title", "summary", "content", "source_run_id"],
                "kind": "validate",
                "mutates": MUTATES_NONE,
                "required_permission": "artifact.create",
                "authority": "manifest.permission + task.buddy_scope + artifact.source_run",
                "preconditions": ["payload fields satisfy artifact.create_revision constraints"],
                "returns": ["normalized", "current_binding"],
            },
            {
                "name": "create_revision",
                "payload_fields": ["artifact_id", "task_id", "kind", "title", "summary", "content", "source_run_id"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "artifact.create",
                "authority": "manifest.permission + task.buddy_scope + artifact.source_run",
                "preconditions": ["payload fields satisfy artifact.create_revision constraints"],
                "returns": ["artifact_id", "artifact", "current_binding"],
            },
            {
                "name": "update_metadata",
                "payload_fields": ["artifact_id", "title", "summary", "source_run_id"],
                "kind": "write",
                "mutates": MUTATES_RUNTIME_OBJECTS,
                "required_permission": "artifact.update",
                "authority": "manifest.permission + artifact.buddy_scope + artifact.source_run",
                "preconditions": ["artifact_id references an active-buddy artifact"],
                "returns": ["artifact_id", "artifact", "current_binding"],
            },
        ],
    },
    {
        "tool": "context",
        "cli_resource": "context",
        "command": "python3 scripts/env/client.py context <operation>",
        "scope": "active instance context reads and prepared-context validation",
        "actions": [
            {
                "name": "get",
                "payload_fields": ["context"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "none",
                "authority": "active instance binding + context revision checks",
                "preconditions": ["optional context payload matches active instance"],
                "returns": [
                    "current_binding",
                    "task_context",
                    "track_context",
                    "decision_surface",
                    "context_sources_desc",
                    "current_context_summary",
                ],
            },
            {
                "name": "summarize",
                "payload_fields": [],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "none",
                "authority": "active instance binding",
                "preconditions": ["none"],
                "returns": ["current_binding", "current_context_summary", "decision_surface", "candidate_tracks"],
            },
            {
                "name": "list_sources",
                "payload_fields": [],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "none",
                "authority": "active instance binding",
                "preconditions": ["none"],
                "returns": ["sources"],
            },
        ],
    },
    {
        "tool": "binding",
        "cli_resource": "binding",
        "command": "python3 scripts/env/client.py binding <operation>",
        "scope": "active launcher instance binding",
        "actions": [
            {
                "name": "get",
                "payload_fields": [],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "none",
                "authority": "active instance binding",
                "preconditions": ["none"],
                "returns": ["current_binding"],
            },
            {
                "name": "set_task",
                "payload_fields": ["task_id"],
                "kind": "bind",
                "mutates": MUTATES_INSTANCE_BINDING,
                "required_permission": "none",
                "authority": "task.buddy_scope + instance.binding",
                "preconditions": ["task_id references an active-buddy task"],
                "returns": ["task_id", "track_id", "current_binding"],
            },
            {
                "name": "set_track",
                "payload_fields": ["track_id"],
                "kind": "bind",
                "mutates": MUTATES_INSTANCE_BINDING,
                "required_permission": "none",
                "authority": "pm.lifecycle_authority + track.lookup + instance.binding",
                "preconditions": ["active buddy is pm", "track_id references an existing track"],
                "returns": ["track_id", "current_binding"],
            },
            {
                "name": "clear",
                "payload_fields": [],
                "kind": "bind",
                "mutates": MUTATES_INSTANCE_BINDING,
                "required_permission": "none",
                "authority": "active instance binding",
                "preconditions": ["none"],
                "returns": ["current_binding"],
            },
        ],
    },
    {
        "tool": "handoff",
        "cli_resource": "handoff",
        "command": "python3 scripts/env/client.py handoff <operation>",
        "scope": "handoff target and transition validation",
        "actions": [
            {
                "name": "validate",
                "payload_fields": ["next_buddy", "reason", "context", "track_id"],
                "kind": "validate",
                "mutates": MUTATES_NONE,
                "required_permission": "none",
                "authority": "manifest.buddies + track.transition alignment",
                "preconditions": ["next_buddy references a manifest buddy"],
                "returns": ["handoff", "track_alignment", "discoverability"],
            },
        ],
    },
    {
        "tool": "run",
        "cli_resource": "run",
        "command": "python3 scripts/env/client.py run <operation>",
        "scope": "reserved run validation, commit, and receipt reads",
        "actions": [
            {
                "name": "commit",
                "payload_fields": ["context", "result"],
                "kind": "commit",
                "mutates": MUTATES_RUN_COMMIT,
                "required_permission": "none",
                "authority": "prepare.context_revision + runtime commit validation",
                "preconditions": ["context revision is active and result is valid"],
                "returns": ["receipt", "refreshed_context"],
            },
            {
                "name": "get_receipt",
                "payload_fields": ["run_id"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "none",
                "authority": "run.buddy_scope",
                "preconditions": ["run_id references an active-buddy run"],
                "returns": ["receipt"],
            },
            {
                "name": "get_raw",
                "payload_fields": ["run_id"],
                "kind": "read",
                "mutates": MUTATES_NONE,
                "required_permission": "none",
                "authority": "run.buddy_scope",
                "preconditions": ["run_id references an active-buddy run"],
                "returns": ["run"],
            },
            {
                "name": "validate_result",
                "payload_fields": ["context", "result"],
                "kind": "validate",
                "mutates": MUTATES_NONE,
                "required_permission": "none",
                "authority": "prepare.context_revision + runtime validation",
                "preconditions": ["context revision is active"],
                "returns": ["durable_signals"],
            },
        ],
    },
    {
        "tool": "evidence",
        "cli_resource": "evidence",
        "command": "python3 scripts/env/client.py evidence <operation>",
        "scope": "market browser evidence issuance for active prepared run",
        "actions": [
            {
                "name": "issue_browser",
                "payload_fields": ["context"],
                "kind": "issue",
                "mutates": MUTATES_BROKER_TOKEN,
                "required_permission": "none",
                "authority": "market profile + context revision + browser cockpit readiness",
                "preconditions": ["active buddy requires market evidence", "context belongs to active run"],
                "returns": ["tool_evidence", "feedback", "persist_payload_hint"],
            },
            {
                "name": "approve_downgrade",
                "payload_fields": ["context", "reason"],
                "kind": "issue",
                "mutates": MUTATES_BROKER_TOKEN,
                "required_permission": "none",
                "authority": "market profile + context revision + explicit reason",
                "preconditions": ["active buddy requires market evidence", "reason is non-empty"],
                "returns": ["tool_evidence", "feedback", "persist_payload_hint"],
            },
        ],
    },
    {
        "tool": "search",
        "cli_resource": "search",
        "command": "python3 scripts/env/client.py search <operation>",
        "scope": "runtime-visible search capability boundary and browser/search backend feedback",
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
                "authority": "env profile search boundary + instance browser endpoint",
                "preconditions": ["active BuddySwitch product-mode instance"],
                "returns": [
                    "native_codex_web_search",
                    "active_buddy",
                    "available_backends",
                    "backend_status",
                    "capability_boundary",
                    "permission_boundary",
                    "allowed_next_actions",
                    "command_hint",
                ],
            },
            {
                "name": "request",
                "payload_fields": ["query", "backend", "engine"],
                "kind": "request",
                "mutates": MUTATES_NONE,
                "required_permission": "none",
                "authority": "env profile search boundary + instance browser endpoint",
                "preconditions": ["backend is explicit", "query is non-empty"],
                "returns": [
                    "backend",
                    "engine",
                    "query",
                    "target_url",
                    "browser_endpoint",
                    "required_cockpit_tool",
                    "page_opened",
                    "permission_boundary",
                    "allowed_next_actions",
                    "command_hint",
                ],
            },
            {
                "name": "open_browser",
                "payload_fields": ["query", "engine"],
                "kind": "open",
                "mutates": MUTATES_BROWSER_SESSION,
                "required_permission": "none",
                "authority": "env profile search boundary + instance browser endpoint",
                "preconditions": ["query is non-empty", "instance browser endpoint is available"],
                "returns": [
                    "engine",
                    "query",
                    "target_url",
                    "browser_endpoint",
                    "page_opened",
                    "permission_boundary",
                    "allowed_next_actions",
                    "command_hint",
                ],
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


def env_tools_description() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for spec in TOOL_REGISTRY:
        tool = spec.get("tool")
        if not isinstance(tool, str) or not tool:
            continue
        operations: list[str] = []
        payload_fields: dict[str, list[str]] = {}
        for action_spec in spec.get("actions", []):
            action = action_spec.get("name")
            if not isinstance(action, str) or not action:
                continue
            operations.append(action)
            payload_fields[action] = list(action_spec.get("payload_fields", []))
        rows[tool] = {
            "command": spec.get("command"),
            "scope": spec.get("scope"),
            "broker_method": "env.tool",
            "envelope": {
                "tool": tool,
                "action": "<action>",
                "args": "<object>",
            },
            "cli_resource": spec.get("cli_resource"),
            "operations": operations,
            "payload_fields": payload_fields,
            "feedback_source": "runtime/tool response fields",
            "authoritative_fields": [
                "permission_boundary",
                "allowed_next_actions",
                "allowed_next_action_options",
                "command_hint",
                "stop_condition",
                "persist_payload_hint",
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
            }
    return rows
