"""Registry, discovery, projection, and dispatch for black-box env.tool runtime."""

from __future__ import annotations

import copy
import importlib
import pkgutil
from pathlib import Path
from typing import Any, Mapping

import buddyswitch.env.tools

from buddyswitch.env.tool_runtime.definition import ActionDefinition
from buddyswitch.env.tool_runtime.definition import TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED
from buddyswitch.env.tool_runtime.definition import ToolDefinition
from buddyswitch.env.tool_runtime.definition import validate_definition
from buddyswitch.env.tool_runtime import results as tool_results

_DEFINITION_CACHE: dict[str, ToolDefinition] = {}
_LOAD_ERRORS: dict[str, dict[str, str]] = {}
_RETIRED_TOOL_IDS = frozenset({"task"})


def clear_cache() -> None:
    _DEFINITION_CACHE.clear()
    _LOAD_ERRORS.clear()


def discover_tool_ids() -> list[str]:
    discovered: list[str] = []
    for info in pkgutil.iter_modules(buddyswitch.env.tools.__path__):
        if not info.ispkg:
            continue
        name = info.name
        if name.startswith("_"):
            continue
        if name in _RETIRED_TOOL_IDS:
            continue
        discovered.append(name)
    return sorted(set(discovered))


def _tool_module_name(tool: str) -> str:
    return f"buddyswitch.env.tools.{tool}.tool"


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


def _selected_tools(*, exclude_tools: set[str] | None = None) -> list[str]:
    excluded = exclude_tools or set()
    return [tool for tool in sorted(supported_tools()) if tool not in excluded]


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
        "task_requirement": action.task_requirement,
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
    discovered = set(discover_tool_ids())
    for tool in sorted(discovered):
        try:
            load_definition(tool)
        except Exception:
            continue
    for stale in sorted(set(_LOAD_ERRORS) - discovered):
        _LOAD_ERRORS.pop(stale, None)
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
        "visibility": row.visibility,
        "task_requirement": row.task_requirement,
        "durability": row.durability,
        "result_content_level": row.result_content_level,
        "side_effects": {
            "mutates": row.mutates,
            "reads": list(row.reads),
            "writes": list(row.writes),
            "does_not_write": list(row.does_not_write),
            "durability": row.durability,
            "idempotency": "idempotent read" if row.mutates == "none" else "state mutation",
        },
        "risk_hints": dict(row.risk_hints),
        "success_means": row.success_effect,
        "failure_state_guarantee": row.failure_state_guarantee,
        "common_failures": list(row.preconditions),
    }


def env_tools_description(*, exclude_tools: set[str] | None = None) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for tool in _selected_tools(exclude_tools=exclude_tools):
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
            "object_model": definition.object_model,
            "scope": definition.scope,
            "broker_method": "env.tool",
            "envelope": {"tool": tool, "action": "<action>", "args": "<object>"},
            "native_mcp": {
                "tool_name_pattern": f"{tool}__<action>",
                "actions": {
                    action.name: f"{tool}__{action.name}"
                    for action in definition.actions
                },
            },
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


def operation_semantics(*, exclude_tools: set[str] | None = None) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for tool in _selected_tools(exclude_tools=exclude_tools):
        definition = load_definition(tool)
        for action in definition.actions:
            rows[f"{tool}.{action.name}"] = {
                "kind": action.kind,
                "mutates": action.mutates,
                "task_requirement": action.task_requirement,
                "required_permission": action.required_permission,
                "authority": action.authority,
                "requires": list(action.preconditions),
                "returns": list(action.returns),
                "reads": list(action.reads),
                "writes": list(action.writes),
                "does_not_write": list(action.does_not_write),
                "visibility": action.visibility,
                "durability": action.durability,
                "result_content_level": action.result_content_level,
                "success_effect": action.success_effect,
                "failure_state_guarantee": action.failure_state_guarantee,
                "risk_hints": dict(action.risk_hints),
            }
    return rows


def compact_tool_affordances(*, exclude_tools: set[str] | None = None) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for tool in _selected_tools(exclude_tools=exclude_tools):
        definition = load_definition(tool)
        rows[tool] = {
            "capability": definition.title,
            "object_model": definition.object_model,
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


def _normalize_action_for_dispatch(*, tool: str, action: str) -> str:
    normalized = action.strip()
    if tool == "context" and normalized == "list-sources":
        return "list_sources"
    return normalized


def _reject(
    *,
    tool: str | None,
    action: str | None,
    current_identity: dict[str, Any],
    active_role: str,
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
        current_identity=current_identity,
        active_role=active_role,
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


def _active_task_required_rejection(
    *,
    tool: str,
    action: str,
    current_identity: dict[str, Any],
    active_role: str,
) -> dict[str, Any]:
    semantic_action = _semantic_action(tool=tool, action=action)
    return tool_results.rejection(
        tool=tool,
        action=semantic_action,
        current_identity=current_identity,
        active_role=active_role,
        code="E_TASK_SYS_ACTIVE_TASK_REQUIRED",
        message="Task Sys active task is required for this env tool action",
        permission_boundary="task_sys.active_task",
        human_summary="A Task Sys task is required for this action.",
        why_blocked=(
            f"Action {tool}.{action} performs task-owned work, "
            "but Task Sys has no active task for this actor."
        ),
        impact="No env action ran and runtime state was unchanged.",
        state_changed=False,
        durability="none",
        retryable=True,
        retry_guidance=(
            "Demand orchestration must select one live Demand and create one native-Goal Task "
            "before task-bound product work can run."
        ),
        allowed_next_actions=[
            "Use task_sys.list to confirm that the native-Goal Task slot is empty.",
            "Demand orchestration may select one live Demand and call task_sys.create.",
            "Use task_sys.get when a Task id exists and its Goal binding needs inspection.",
        ],
        alternative_capabilities=[
            tool_results.alternative_capability(
                tool="task_sys",
                action="list",
                condition="List active or terminal Actor-owned Tasks.",
                mutates_product_state=False,
            ),
            tool_results.alternative_capability(
                tool="task_sys",
                action="get",
                condition="Read full detail for one actor-owned Task Sys task.",
                mutates_product_state=False,
            ),
            tool_results.alternative_capability(
                tool="task_sys",
                action="create",
                condition="Create one Task only after Demand orchestration selected a current live Demand.",
                mutates_product_state=True,
            ),
        ],
        extra={
            "category": "task_required",
            "gate_source": "env.tool task requirement",
            "gate_stage": "pre_dispatch",
            "executed": False,
            "task_requirement": TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED,
        },
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
    current_identity = getattr(context, "current_identity", None)
    if current_identity is not None and hasattr(current_identity, "to_payload"):
        response["current_identity"] = current_identity.to_payload()
    response["active_role"] = getattr(context, "role_id", context.get("active_role"))
    return response


def _actor_identity_profile_from_dispatch(*, actor_id: str, active_role: str) -> Any:
    from buddyswitch.env.domain.identity import ActorIdentityProfile
    from buddyswitch.env.domain.identity import actor_identity

    return ActorIdentityProfile(
        identity=actor_identity(actor_id),
        role_id=active_role,
    )


def dispatch_env_tool_request(
    *,
    payload: dict[str, Any],
    active_role: str,
    actor_id: str,
    instance_json: Path,
    instance_payload: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path | None = None,
    invocation: dict[str, Any] | None = None,
    demand_ingress_application: Any | None = None,
) -> dict[str, Any]:
    runtime_actor = _actor_identity_profile_from_dispatch(actor_id=actor_id, active_role=active_role)
    current_identity = runtime_actor.identity.to_payload()
    active_role = runtime_actor.role_id

    raw_tool = payload.get("tool")
    if not isinstance(raw_tool, str) or not raw_tool.strip():
        return _reject(
            tool=None,
            action=None,
            current_identity=current_identity,
            active_role=active_role,
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
                    current_identity=current_identity,
                    active_role=active_role,
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
            current_identity=current_identity,
            active_role=active_role,
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
            current_identity=current_identity,
            active_role=active_role,
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
    action = _normalize_action_for_dispatch(tool=tool, action=raw_action)
    if action not in supported_actions(tool):
        return _reject(
            tool=tool,
            action=action,
            current_identity=current_identity,
            active_role=active_role,
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

    action_definition = get_action_definition(tool, action)
    from buddyswitch.env.tool_runtime import auth_feedback
    from buddyswitch.env.tool_runtime import role_auth

    auth_decision = role_auth.authorize(action_definition.required_permission, runtime_actor.role_id, manifest)
    if not auth_decision.allowed:
        return auth_feedback.role_auth_rejection(
            tool=tool,
            action=action,
            current_identity=current_identity,
            active_role=runtime_actor.role_id,
            decision=auth_decision,
        )

    args = payload.get("args", {})
    if not isinstance(args, dict):
        return _reject(
            tool=tool,
            action=action,
            current_identity=current_identity,
            active_role=active_role,
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

    from buddyswitch.env.tool_runtime.context import InvocationFact, ToolContext

    invocation_payload = invocation or {}
    if not isinstance(invocation_payload, dict):
        raise ValueError("invocation must be an object")
    normalized_invocation: dict[str, str | None] = {}
    for field_name in (
        "thread_id",
        "turn_id",
        "request_id",
        "demand_inbound_capability",
    ):
        value = invocation_payload.get(field_name)
        if value is not None and (
            not isinstance(value, str) or not value.strip()
        ):
            raise ValueError(
                f"invocation.{field_name} must be a non-empty string"
            )
        normalized_invocation[field_name] = (
            value.strip() if isinstance(value, str) else None
        )

    context = ToolContext.from_identity_profile(
        actor_identity_profile=runtime_actor,
        instance_json=instance_json,
        instance_payload=dict(instance_payload),
        manifest=dict(manifest),
        manifest_path=manifest_path,
        invocation=InvocationFact(**normalized_invocation),
        demand_ingress_application=demand_ingress_application,
    )
    if action_definition.task_requirement == TASK_REQUIREMENT_ACTIVE_TASK_REQUIRED:
        from buddyswitch.env.domain import task_sys

        projection = task_sys.actor_task_projection(actor_profile=runtime_actor)
        if projection["active_count"] == 0:
            return _active_task_required_rejection(
                tool=tool,
                action=action,
                current_identity=current_identity,
                active_role=active_role,
            )

    try:
        return _invoke_tool(tool=tool, action=action, args=dict(args), context=context)
    except Exception as exc:
        return _reject(
            tool=tool,
            action=action,
            current_identity=current_identity,
            active_role=active_role,
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
