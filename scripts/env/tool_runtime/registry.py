#!/usr/bin/env python3
"""Registry, discovery, projection, and dispatch for black-box env.tool runtime."""

from __future__ import annotations

import copy
import importlib
import pkgutil
from pathlib import Path
from typing import Any, Mapping

import env.tools

from env.tool_runtime.definition import ActionDefinition
from env.tool_runtime.definition import ToolDefinition
from env.tool_runtime.definition import validate_definition
from env.tool_runtime import results as tool_results

_DEFINITION_CACHE: dict[str, ToolDefinition] = {}
_LOAD_ERRORS: dict[str, dict[str, str]] = {}


def clear_cache() -> None:
    _DEFINITION_CACHE.clear()
    _LOAD_ERRORS.clear()


def discover_tool_ids() -> list[str]:
    discovered: list[str] = []
    for info in pkgutil.iter_modules(env.tools.__path__):
        if not info.ispkg:
            continue
        name = info.name
        if name.startswith("_"):
            continue
        discovered.append(name)
    return sorted(set(discovered))


def _tool_module_name(tool: str) -> str:
    return f"env.tools.{tool}.tool"


def _load_tool_module(tool: str):
    return importlib.import_module(_tool_module_name(tool))


def load_definition(tool: str) -> ToolDefinition:
    if tool in _DEFINITION_CACHE:
        return _DEFINITION_CACHE[tool]
    module_name = _tool_module_name(tool)
    try:
        module = _load_tool_module(tool)
        definition = getattr(module, "DEFINITION", None)
        invoke = getattr(module, "invoke", None)
        if not callable(invoke):
            raise TypeError(f"{module_name}.invoke must be callable")
        if not isinstance(definition, ToolDefinition):
            raise TypeError(f"{module_name}.DEFINITION must be ToolDefinition")
        validate_definition(definition)
        if definition.id != tool:
            raise ValueError(f"{module_name}.DEFINITION.id must equal '{tool}'")
        _DEFINITION_CACHE[tool] = definition
        _LOAD_ERRORS.pop(tool, None)
        return definition
    except Exception as exc:
        _LOAD_ERRORS[tool] = {
            "tool": tool,
            "module": module_name,
            "error": str(exc),
        }
        raise


def supported_tools() -> set[str]:
    rows: set[str] = set()
    for tool in discover_tool_ids():
        try:
            load_definition(tool)
        except Exception:
            continue
        rows.add(tool)
    return rows


def supported_actions(tool: str) -> set[str]:
    try:
        definition = load_definition(tool)
    except Exception:
        return set()
    return {row.name for row in definition.actions}


def _action_spec_row(action: ActionDefinition) -> dict[str, Any]:
    properties = action.input_schema.get("properties")
    payload_fields: list[str] = []
    if isinstance(properties, dict):
        payload_fields = [name for name in properties if isinstance(name, str)]
    return {
        "name": action.name,
        "payload_fields": payload_fields,
        "kind": action.kind,
        "mutates": action.mutates,
        "required_permission": action.required_permission,
        "authority": action.authority,
        "preconditions": list(action.preconditions),
        "returns": list(action.returns),
    }


def get_definition(tool: str) -> ToolDefinition:
    return load_definition(tool)


def get_action_definition(tool: str, action: str) -> ActionDefinition:
    definition = load_definition(tool)
    for row in definition.actions:
        if row.name == action:
            return row
    raise KeyError(f"unsupported action: {tool}.{action}")


def payload_fields_for_action(tool: str, action: str) -> list[str]:
    try:
        row = get_action_definition(tool, action)
    except Exception:
        return []
    properties = row.input_schema.get("properties")
    if not isinstance(properties, dict):
        return []
    return [name for name in properties if isinstance(name, str)]


def tool_catalog_errors() -> list[dict[str, str]]:
    for tool in discover_tool_ids():
        try:
            load_definition(tool)
        except Exception:
            continue
    return [_LOAD_ERRORS[name] for name in sorted(_LOAD_ERRORS)]


def semantic_contract_errors() -> list[str]:
    return [f"{row['module']}: {row['error']}" for row in tool_catalog_errors()]


def _action_semantic_row(tool: str, row: ActionDefinition) -> dict[str, Any]:
    properties = row.input_schema.get("properties")
    inputs: dict[str, str] = {}
    if isinstance(properties, dict):
        for key, value in properties.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            description = value.get("description")
            if isinstance(description, str) and description.strip():
                explained = description.strip()
                value_type = value.get("type")
                if value_type == "object" or (isinstance(value_type, list) and "object" in value_type):
                    explained = f"{explained} Shape: object."
                elif value_type == "array" or (isinstance(value_type, list) and "array" in value_type):
                    explained = f"{explained} Shape: array."
                inputs[key] = explained
    return {
        "title": row.title,
        "plain_description": row.description,
        "use_when": list(row.use_when),
        "do_not_use_when": list(row.do_not_use_when),
        "inputs_explained": inputs,
        "side_effects": {
            "mutates": row.mutates,
            "writes": [],
            "does_not_write": [],
            "durability": "none" if row.mutates == "none" else "durable",
            "idempotency": "idempotent read" if row.mutates == "none" else "state mutation",
        },
        "risk_hints": dict(row.risk_hints),
        "success_means": f"{tool}.{row.name} completed under declared capability boundary.",
        "common_failures": list(row.preconditions),
    }


def env_tools_description() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for tool in sorted(supported_tools()):
        definition = load_definition(tool)
        operations: list[str] = []
        payload_fields: dict[str, list[str]] = {}
        input_schemas: dict[str, dict[str, Any]] = {}
        action_semantics: dict[str, dict[str, Any]] = {}
        for action in definition.actions:
            operations.append(action.name)
            payload_fields[action.name] = payload_fields_for_action(tool, action.name)
            input_schemas[action.name] = _schema_copy(action.input_schema)
            action_semantics[action.name] = _action_semantic_row(tool, action)

        rows[tool] = {
            "title": definition.title,
            "plain_description": definition.description,
            "use_when": list(definition.use_when),
            "do_not_use_when": list(definition.do_not_use_when),
            "capability_boundary": definition.capability_boundary,
            "command": definition.command,
            "scope": definition.scope,
            "broker_method": "env.tool",
            "envelope": {"tool": tool, "action": "<action>", "args": "<object>"},
            "cli_resource": definition.cli_resource,
            "operations": operations,
            "payload_fields": payload_fields,
            "input_schemas": input_schemas,
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
        if isinstance(definition.backend_model, dict) and definition.backend_model:
            rows[tool]["backend_model"] = dict(definition.backend_model)
    return rows


def operation_semantics() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for tool in sorted(supported_tools()):
        definition = load_definition(tool)
        for action in definition.actions:
            rows[f"{tool}.{action.name}"] = {
                "kind": action.kind,
                "mutates": action.mutates,
                "required_permission": action.required_permission,
                "authority": action.authority,
                "requires": list(action.preconditions),
                "returns": list(action.returns),
                "risk_hints": dict(action.risk_hints),
            }
    return rows


def compact_tool_affordances() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for tool in sorted(supported_tools()):
        definition = load_definition(tool)
        rows[tool] = {
            "capability": definition.title,
            "when_to_use": list(definition.use_when),
            "when_not_to_use": list(definition.do_not_use_when),
            "state_effect": definition.capability_boundary,
            "returns": definition.description,
        }
    return rows


def _schema_copy(schema: Mapping[str, Any] | Any) -> dict[str, Any]:
    if not isinstance(schema, Mapping):
        return {}
    return copy.deepcopy(dict(schema))


def action_mutates(tool: str, action: str) -> str | None:
    try:
        return get_action_definition(tool, action).mutates
    except Exception:
        return None


def _supported_tools_text() -> str:
    return ", ".join(sorted(supported_tools()))


def _supported_actions_text(tool: str) -> str:
    return ", ".join(sorted(supported_actions(tool)))


def _semantic_action(*, tool: str, action: str | None) -> str:
    normalized = action.strip() if isinstance(action, str) and action.strip() else "unknown"
    return f"{tool}.{normalized}"


def _reject(
    *,
    tool: str | None,
    action: str | None,
    active_buddy: str,
    code: str,
    message: str,
    permission_boundary: str,
    human_summary: str,
    why_blocked: str,
    retryable: bool,
    retry_guidance: str,
    allowed_next_actions: list[str],
    correctable_fields: list[str] | None = None,
) -> dict[str, Any]:
    fallback_tool = tool or "env.tool"
    semantic_action = _semantic_action(tool=fallback_tool, action=action)
    return tool_results.rejection(
        tool=fallback_tool,
        action=semantic_action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=permission_boundary,
        human_summary=human_summary,
        why_blocked=why_blocked,
        impact="No env action ran and runtime state was unchanged.",
        state_changed=False,
        retryable=retryable,
        retry_guidance=retry_guidance,
        allowed_next_actions=allowed_next_actions,
        correctable_fields=correctable_fields,
    )


def _invoke_tool(*, tool: str, action: str, args: dict[str, Any], context: Any) -> dict[str, Any]:
    module = _load_tool_module(tool)
    invoke = getattr(module, "invoke", None)
    if not callable(invoke):
        raise TypeError(f"{_tool_module_name(tool)}.invoke must be callable")
    response = invoke(action=action, args=args, context=context)
    if not isinstance(response, dict):
        raise TypeError(f"{_tool_module_name(tool)}.invoke must return an object")
    response.setdefault("tool", tool)
    response.setdefault("action", _semantic_action(tool=tool, action=action))
    return response


def dispatch_env_tool_request(
    *,
    payload: dict[str, Any],
    active_buddy: str,
    instance_id: str,
    instance_json: Path,
    instance_payload: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    raw_tool = payload.get("tool")
    if not isinstance(raw_tool, str) or not raw_tool.strip():
        return _reject(
            tool=None,
            action=None,
            active_buddy=active_buddy,
            code="E_ENV_TOOL",
            message="env.tool payload.tool must be a non-empty string",
            permission_boundary="env.tool",
            human_summary="The request is missing a valid env tool id.",
            why_blocked="payload.tool must be a non-empty string for env.tool routing.",
            retryable=True,
            retry_guidance="Fix payload.tool, payload.action, and payload.args, then retry.",
            allowed_next_actions=[
                "Send env.tool payload as {tool, action, args}.",
                f"Use one supported tool: {_supported_tools_text()}.",
            ],
            correctable_fields=["tool"],
        )
    tool = raw_tool.strip().lower()

    known_packages = set(discover_tool_ids())
    known_tools = supported_tools()
    if tool not in known_tools:
        if tool in known_packages:
            return _reject(
                tool=tool,
                action=None,
                active_buddy=active_buddy,
                code="E_ENV_TOOL_CATALOG",
                message=f"env.tool package '{tool}' exists but its definition is unavailable",
                permission_boundary="env.tool.catalog",
                human_summary=f"Tool '{tool}' package exists but its definition could not be loaded.",
                why_blocked="selected tool definition failed to load",
                retryable=False,
                retry_guidance="Fix selected tool definition errors before retrying.",
                allowed_next_actions=[
                    "Use context.get to inspect tool_catalog and tool_catalog_errors.",
                ],
                correctable_fields=["tool"],
            )
        return _reject(
            tool=tool,
            action=None,
            active_buddy=active_buddy,
            code="E_ENV_TOOL",
            message=f"unsupported env.tool payload.tool: {tool}",
            permission_boundary="env.tool",
            human_summary=f"Tool '{tool}' is not registered for env.tool.",
            why_blocked="payload.tool is not in the runtime supported env tool set.",
            retryable=True,
            retry_guidance="Inspect context.get.tool_catalog and retry with a supported tool.",
            allowed_next_actions=[
                f"Use one supported tool: {_supported_tools_text()}.",
                "Use context.get for tool_catalog and operation_semantics.",
            ],
            correctable_fields=["tool"],
        )

    raw_action = payload.get("action")
    if not isinstance(raw_action, str) or not raw_action.strip():
        return _reject(
            tool=tool,
            action=None,
            active_buddy=active_buddy,
            code="E_ENV_TOOL",
            message="env.tool payload.action must be a non-empty string",
            permission_boundary="env.tool",
            human_summary="The request is missing a valid env action id.",
            why_blocked="payload.action must be a non-empty string for the selected tool.",
            retryable=True,
            retry_guidance="Set payload.action to a supported action id and retry.",
            allowed_next_actions=[
                f"Use one supported action: {_supported_actions_text(tool)}.",
            ],
            correctable_fields=["action"],
        )
    action = raw_action.strip()
    if action not in supported_actions(tool):
        return _reject(
            tool=tool,
            action=action,
            active_buddy=active_buddy,
            code="E_ENV_TOOL",
            message=f"unsupported env.tool payload.action for {tool}: {action}",
            permission_boundary="env.tool",
            human_summary=f"Action '{action}' is not supported for tool '{tool}'.",
            why_blocked="payload.action is not registered under the selected tool.",
            retryable=True,
            retry_guidance="Inspect context.get.operation_semantics and retry with a supported action.",
            allowed_next_actions=[
                f"Use one supported action: {_supported_actions_text(tool)}.",
                f"Use context.get.tool_catalog['{tool}'] for action and payload field hints.",
            ],
            correctable_fields=["action"],
        )

    args = payload.get("args", {})
    if not isinstance(args, dict):
        return _reject(
            tool=tool,
            action=action,
            active_buddy=active_buddy,
            code="E_ENV_TOOL_PAYLOAD",
            message="env.tool payload.args must be an object",
            permission_boundary="request-payload",
            human_summary="The request args payload has the wrong shape.",
            why_blocked="payload.args must be a JSON object for env.tool handlers.",
            retryable=True,
            retry_guidance="Set payload.args to an object and include only supported fields.",
            allowed_next_actions=[
                f"Use context.get.tool_catalog['{tool}'].payload_fields to shape args.",
            ],
            correctable_fields=["args"],
        )

    from env.tool_runtime.context import ToolContext

    context = ToolContext(
        active_buddy=active_buddy,
        instance_id=instance_id,
        instance_json=instance_json,
        instance_payload=dict(instance_payload),
        manifest=dict(manifest),
        manifest_path=manifest_path,
    )
    try:
        return _invoke_tool(tool=tool, action=action, args=dict(args), context=context)
    except Exception as exc:
        return _reject(
            tool=tool,
            action=action,
            active_buddy=active_buddy,
            code="E_ENV_TOOL_DISPATCH",
            message=f"failed to invoke env tool {tool}.{action}: {exc}",
            permission_boundary="env.tool.dispatch",
            human_summary="Selected env tool invoke path could not be executed.",
            why_blocked=str(exc),
            retryable=False,
            retry_guidance="Fix the selected tool implementation before retrying this action.",
            allowed_next_actions=[
                "Use another registered tool that does not depend on this implementation.",
                "Inspect context.get.tool_catalog_errors for runtime load errors.",
            ],
        )
