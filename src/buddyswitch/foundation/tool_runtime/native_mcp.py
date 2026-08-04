"""Native MCP projection for BuddySwitch env.tool actions."""

from __future__ import annotations

import copy
from typing import Any

from buddyswitch.foundation.tool_runtime import registry
from buddyswitch.foundation.tool_runtime.definition import ActionDefinition, ToolDefinition


__all__ = (
    "bound_capability_env",
    "encode_native_tool_name",
    "list_native_tool_specs",
    "resolve_native_tool_name",
)


_NATIVE_TOOL_SEPARATOR = "__"


def encode_native_tool_name(tool: str, action: str) -> str:
    if not isinstance(tool, str) or not tool.strip():
        raise ValueError("tool must be a non-empty string")
    if not isinstance(action, str) or not action.strip():
        raise ValueError("action must be a non-empty string")
    return f"{tool.strip()}{_NATIVE_TOOL_SEPARATOR}{action.strip()}"


def _decode_native_tool_name(name: str) -> tuple[str, str]:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("native tool name must be a non-empty string")
    normalized = name.strip()
    parts = normalized.split(_NATIVE_TOOL_SEPARATOR)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"invalid BuddySwitch native tool name: {name}")
    return parts[0], parts[1]


def resolve_native_tool_name(name: str) -> tuple[str, str]:
    tool, action = _decode_native_tool_name(name)
    if tool not in registry.supported_tools() or action not in registry.supported_actions(tool):
        raise KeyError(f"unsupported BuddySwitch native env tool: {name}")
    return tool, action


def bound_capability_env(tool: str, action: str) -> str | None:
    return registry.get_action_definition(tool, action).bound_capability_env


def _schema_copy(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    return copy.deepcopy(schema)


def _format_rows(label: str, rows: tuple[str, ...]) -> list[str]:
    if not rows:
        return []
    return [f"{label}: {row}" for row in rows]


def _native_tool_description(tool: str, definition: ToolDefinition, action: ActionDefinition) -> str:
    rows: list[str] = [
        f"{definition.title} / {action.title}.",
        action.description,
        f"Tool: {tool}.",
        f"Action: {action.name}.",
        f"Permission: {action.required_permission}.",
        f"Kind: {action.kind}.",
        f"Mutation: {action.mutates}.",
        f"Authority: {action.authority}.",
        f"Visibility: {action.visibility}.",
        f"Durability: {action.durability}.",
        f"Result content level: {action.result_content_level}.",
        f"Reads: {', '.join(action.reads) if action.reads else 'none'}.",
        f"Writes: {', '.join(action.writes) if action.writes else 'none'}.",
        f"Does not write: {', '.join(action.does_not_write)}.",
        f"Success means: {action.success_effect}.",
        f"Failure state guarantee: {action.failure_state_guarantee}.",
    ]
    rows.extend(_format_rows("Use when", action.use_when))
    rows.extend(_format_rows("Do not use when", action.do_not_use_when))
    rows.extend(_format_rows("Precondition", action.preconditions))
    rows.extend(_format_rows("Returns", action.returns))
    if action.risk_hints:
        rows.append(f"Risk hints: {dict(action.risk_hints)}.")
    return "\n".join(row for row in rows if row)


def _native_tool_spec(tool: str, definition: ToolDefinition, action: ActionDefinition) -> dict[str, Any]:
    return {
        "name": encode_native_tool_name(tool, action.name),
        "title": action.title,
        "description": _native_tool_description(tool, definition, action),
        "inputSchema": _schema_copy(action.input_schema),
    }


def list_native_tool_specs(*, exclude_tools: set[str] | None = None) -> list[dict[str, Any]]:
    excluded = exclude_tools or set()
    specs: list[dict[str, Any]] = []
    for tool in sorted(registry.supported_tools()):
        if tool in excluded:
            continue
        definition = registry.get_definition(tool)
        for action in definition.actions:
            specs.append(_native_tool_spec(tool, definition, action))
    return specs
