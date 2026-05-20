#!/usr/bin/env python3
"""Service-light env.tool catalog projection from per-tool packages."""

from __future__ import annotations

from typing import Any

from env.tools import discovery

_SEMANTIC_REQUIRED_FIELDS = {
    "use_when",
    "do_not_use_when",
    "inputs_explained",
    "common_failures",
    "success_means",
    "risk_hints",
}


def _load_contract_spec(tool: str) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    try:
        spec = discovery.read_module_attr(tool, "contract", "TOOL_SPEC")
    except Exception as exc:
        return None, {"tool": tool, "module": f"env.tools.{tool}.contract", "error": str(exc)}
    if not isinstance(spec, dict):
        return None, {"tool": tool, "module": f"env.tools.{tool}.contract", "error": "TOOL_SPEC must be an object"}
    if spec.get("tool") != tool:
        return None, {"tool": tool, "module": f"env.tools.{tool}.contract", "error": "TOOL_SPEC.tool mismatch"}
    actions = spec.get("actions")
    if not isinstance(actions, list):
        return None, {"tool": tool, "module": f"env.tools.{tool}.contract", "error": "TOOL_SPEC.actions must be a list"}
    return dict(spec), None


def _load_tool_semantics(tool: str) -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]] | None, list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    capability: dict[str, Any] | None = None
    action_semantics: dict[str, dict[str, Any]] | None = None

    try:
        loaded_capability = discovery.read_module_attr(tool, "semantics", "CAPABILITY")
        if isinstance(loaded_capability, dict):
            capability = dict(loaded_capability)
        else:
            errors.append(
                {
                    "tool": tool,
                    "module": f"env.tools.{tool}.semantics",
                    "error": "CAPABILITY must be an object",
                }
            )
    except Exception as exc:
        errors.append({"tool": tool, "module": f"env.tools.{tool}.semantics", "error": str(exc)})

    try:
        loaded_action_semantics = discovery.read_module_attr(tool, "semantics", "ACTION_SEMANTICS")
        if isinstance(loaded_action_semantics, dict):
            normalized: dict[str, dict[str, Any]] = {}
            for action, row in loaded_action_semantics.items():
                if isinstance(action, str) and isinstance(row, dict):
                    normalized[action] = dict(row)
            action_semantics = normalized
        else:
            errors.append(
                {
                    "tool": tool,
                    "module": f"env.tools.{tool}.semantics",
                    "error": "ACTION_SEMANTICS must be an object",
                }
            )
    except Exception as exc:
        errors.append({"tool": tool, "module": f"env.tools.{tool}.semantics", "error": str(exc)})

    return capability, action_semantics, errors


def _loaded_rows() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, dict[str, Any]]], list[dict[str, str]]]:
    specs: dict[str, dict[str, Any]] = {}
    capabilities: dict[str, dict[str, Any]] = {}
    action_semantics_by_tool: dict[str, dict[str, dict[str, Any]]] = {}
    errors: list[dict[str, str]] = []

    for tool in discovery.discover_tool_ids():
        spec, spec_error = _load_contract_spec(tool)
        if spec_error is not None:
            errors.append(spec_error)
            continue
        assert isinstance(spec, dict)
        specs[tool] = spec

        capability, action_semantics, semantic_errors = _load_tool_semantics(tool)
        errors.extend(semantic_errors)
        if capability is not None:
            capabilities[tool] = capability
        if action_semantics is not None:
            action_semantics_by_tool[tool] = action_semantics

    return specs, capabilities, action_semantics_by_tool, errors


def tool_specs() -> list[dict[str, Any]]:
    specs, _, _, _ = _loaded_rows()
    return [specs[tool] for tool in sorted(specs)]


def tool_catalog_errors() -> list[dict[str, str]]:
    _, _, _, errors = _loaded_rows()
    return errors


def supported_tools() -> set[str]:
    return {row.get("tool") for row in tool_specs() if isinstance(row.get("tool"), str)}


def get_tool_spec(tool: str) -> dict[str, Any] | None:
    specs, _, _, _ = _loaded_rows()
    return specs.get(tool)


def get_action_spec(tool: str, action: str) -> dict[str, Any] | None:
    spec = get_tool_spec(tool)
    if not isinstance(spec, dict):
        return None
    for row in spec.get("actions", []):
        if isinstance(row, dict) and row.get("name") == action:
            return row
    return None


def supported_actions(tool: str) -> set[str]:
    spec = get_tool_spec(tool)
    if not isinstance(spec, dict):
        return set()
    return {row.get("name") for row in spec.get("actions", []) if isinstance(row, dict) and isinstance(row.get("name"), str)}


def payload_fields_for_action(tool: str, action: str) -> set[str]:
    spec = get_action_spec(tool, action)
    if not isinstance(spec, dict):
        return set()
    return {row for row in spec.get("payload_fields", []) if isinstance(row, str)}


def _capability_row(tool: str) -> dict[str, Any]:
    _, capabilities, _, _ = _loaded_rows()
    row = capabilities.get(tool)
    if isinstance(row, dict):
        return row
    return {
        "title": tool,
        "plain_description": "No semantic capability row is registered for this tool.",
        "use_when": [],
        "do_not_use_when": [],
        "capability_boundary": "Service-level permission and ownership checks remain authoritative.",
    }


def _action_semantic_row(tool: str, action: str) -> dict[str, Any]:
    _, _, action_semantics_by_tool, _ = _loaded_rows()
    tool_rows = action_semantics_by_tool.get(tool)
    if isinstance(tool_rows, dict):
        row = tool_rows.get(action)
        if isinstance(row, dict):
            return row
    return {
        "title": f"{tool}.{action}",
        "plain_description": "No semantic action row is registered for this action.",
        "use_when": [],
        "do_not_use_when": [],
        "inputs_explained": {},
        "side_effects": {
            "mutates": "unknown",
            "writes": [],
            "does_not_write": [],
            "durability": "unknown",
            "idempotency": "unknown",
        },
        "risk_hints": {},
        "success_means": "No semantic action row is registered.",
        "common_failures": [],
    }


def env_tools_description() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for spec in tool_specs():
        tool = spec.get("tool")
        if not isinstance(tool, str) or not tool:
            continue
        capability = _capability_row(tool)
        operations: list[str] = []
        payload_fields: dict[str, list[str]] = {}
        action_semantics: dict[str, dict[str, Any]] = {}
        for action_spec in spec.get("actions", []):
            if not isinstance(action_spec, dict):
                continue
            action = action_spec.get("name")
            if not isinstance(action, str) or not action:
                continue
            operations.append(action)
            payload_fields[action] = [row for row in action_spec.get("payload_fields", []) if isinstance(row, str)]
            action_semantics[action] = _action_semantic_row(tool, action)
        rows[tool] = {
            "title": capability.get("title", ""),
            "plain_description": capability.get("plain_description", ""),
            "use_when": list(capability.get("use_when", [])),
            "do_not_use_when": list(capability.get("do_not_use_when", [])),
            "capability_boundary": capability.get("capability_boundary", ""),
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
    for spec in tool_specs():
        tool = spec.get("tool")
        if not isinstance(tool, str) or not tool:
            continue
        for action_spec in spec.get("actions", []):
            if not isinstance(action_spec, dict):
                continue
            action = action_spec.get("name")
            if not isinstance(action, str) or not action:
                continue
            semantic = _action_semantic_row(tool, action)
            rows[f"{tool}.{action}"] = {
                "kind": action_spec.get("kind"),
                "mutates": action_spec.get("mutates"),
                "required_permission": action_spec.get("required_permission"),
                "authority": action_spec.get("authority"),
                "requires": list(action_spec.get("preconditions", [])),
                "returns": list(action_spec.get("returns", [])),
                "risk_hints": dict(semantic.get("risk_hints", {})),
            }
    return rows


def compact_tool_affordances() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for tool in sorted(supported_tools()):
        capability = _capability_row(tool)
        rows[tool] = {
            "capability": capability.get("title", ""),
            "when_to_use": list(capability.get("use_when", [])),
            "when_not_to_use": list(capability.get("do_not_use_when", [])),
            "state_effect": capability.get(
                "capability_boundary",
                "Service-level permission and ownership checks remain authoritative.",
            ),
            "returns": capability.get("plain_description", ""),
        }
    return rows


def semantic_contract_errors() -> list[str]:
    specs, capabilities, action_semantics_by_tool, errors = _loaded_rows()
    messages = [f"{row['module']}: {row['error']}" for row in errors]

    for tool in discovery.discover_tool_ids():
        if tool not in specs:
            messages.append(f"missing contract semantics for tool '{tool}'")
            continue
        if tool not in capabilities or tool not in action_semantics_by_tool:
            messages.append(f"missing action semantics for tool '{tool}'")
            continue

        contract_actions = {
            row.get("name")
            for row in specs[tool].get("actions", [])
            if isinstance(row, dict) and isinstance(row.get("name"), str)
        }
        semantic_actions = {name for name in action_semantics_by_tool[tool] if isinstance(name, str)}
        for action in sorted(contract_actions - semantic_actions):
            messages.append(f"missing action semantics for '{tool}.{action}'")
        for action in sorted(semantic_actions - contract_actions):
            messages.append(f"orphan action semantics for '{tool}.{action}'")

        for action in sorted(contract_actions):
            row = action_semantics_by_tool[tool].get(action)
            if not isinstance(row, dict):
                messages.append(f"invalid action semantics row for '{tool}.{action}'")
                continue
            for field in sorted(_SEMANTIC_REQUIRED_FIELDS):
                if field not in row:
                    messages.append(f"missing semantic field '{field}' for '{tool}.{action}'")

    return messages
