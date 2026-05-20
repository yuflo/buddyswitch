#!/usr/bin/env python3
"""Runtime tool protocol definitions and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Mapping

MUTATES_NONE = "none"
MUTATES_RUNTIME_OBJECTS = "runtime_objects"
MUTATES_RUNTIME_FILES = "runtime_files"
MUTATES_BROKER_TOKEN = "broker_token"
MUTATES_BROWSER_SESSION = "browser_session"

_ALLOWED_MUTATION_VALUES = {
    MUTATES_NONE,
    MUTATES_RUNTIME_OBJECTS,
    MUTATES_RUNTIME_FILES,
    MUTATES_BROKER_TOKEN,
    MUTATES_BROWSER_SESSION,
}
_TOOL_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_ACTION_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_ENUM_LIKE_FIELDS = {"status", "state", "health", "kind", "template", "target_type", "backend", "engine"}


@dataclass(frozen=True)
class ActionDefinition:
    name: str
    title: str
    description: str
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    kind: str
    mutates: str
    required_permission: str
    authority: str
    preconditions: tuple[str, ...] = ()
    returns: tuple[str, ...] = ()
    risk_hints: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolDefinition:
    id: str
    title: str
    description: str
    cli_resource: str
    command: str
    scope: str
    capability_boundary: str
    use_when: tuple[str, ...]
    do_not_use_when: tuple[str, ...]
    actions: tuple[ActionDefinition, ...]
    backend_model: Mapping[str, Any] = field(default_factory=dict)


def _require_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_schema_object(schema: Mapping[str, Any], *, field: str) -> None:
    if not isinstance(schema, Mapping):
        raise ValueError(f"{field} must be an object")
    if schema.get("type") != "object":
        raise ValueError(f"{field}.type must equal 'object'")
    if schema.get("additionalProperties") is not False:
        raise ValueError(f"{field}.additionalProperties must be false")
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        raise ValueError(f"{field}.properties must be an object")
    required = schema.get("required")
    if not isinstance(required, list):
        raise ValueError(f"{field}.required must be a list")
    for index, name in enumerate(required):
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{field}.required[{index}] must be a non-empty string")
        if name not in properties:
            raise ValueError(f"{field}.required[{index}] must reference a declared property")
    for property_name, property_schema in properties.items():
        if not isinstance(property_name, str) or not property_name.strip():
            raise ValueError(f"{field}.properties keys must be non-empty strings")
        if not isinstance(property_schema, Mapping):
            raise ValueError(f"{field}.properties.{property_name} must be an object")
        _validate_property_schema(
            property_schema,
            field=f"{field}.properties.{property_name}",
            property_name=property_name,
        )


def _schema_type_has(schema: Mapping[str, Any], expected: str) -> bool:
    value = schema.get("type")
    if value == expected:
        return True
    if isinstance(value, list):
        return expected in value
    return False


def _validate_property_schema(schema: Mapping[str, Any], *, field: str, property_name: str) -> None:
    description = schema.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"{field}.description must be a non-empty string")

    if property_name in _ENUM_LIKE_FIELDS:
        enum_values = schema.get("enum")
        if not isinstance(enum_values, list) or not enum_values:
            raise ValueError(f"{field}.enum must be a non-empty list")
        for index, row in enumerate(enum_values):
            if not isinstance(row, str) or not row.strip():
                raise ValueError(f"{field}.enum[{index}] must be a non-empty string")

    if _schema_type_has(schema, "object"):
        _validate_object_property(schema, field=field)

    if _schema_type_has(schema, "array"):
        items = schema.get("items")
        if not isinstance(items, Mapping):
            raise ValueError(f"{field}.items must be an object")
        _validate_combined_variants(items, field=f"{field}.items")
        if _schema_type_has(items, "object"):
            _validate_object_property(items, field=f"{field}.items")

    _validate_combined_variants(schema, field=field)


def _validate_object_property(schema: Mapping[str, Any], *, field: str) -> None:
    if schema.get("additionalProperties") is not False:
        raise ValueError(f"{field}.additionalProperties must be false")
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        raise ValueError(f"{field}.properties must be an object")
    required = schema.get("required")
    if not isinstance(required, list):
        raise ValueError(f"{field}.required must be a list")
    for index, name in enumerate(required):
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{field}.required[{index}] must be a non-empty string")
        if name not in properties:
            raise ValueError(f"{field}.required[{index}] must reference a declared property")
    for nested_name, nested_schema in properties.items():
        if not isinstance(nested_name, str) or not nested_name.strip():
            raise ValueError(f"{field}.properties keys must be non-empty strings")
        if not isinstance(nested_schema, Mapping):
            raise ValueError(f"{field}.properties.{nested_name} must be an object")
        _validate_property_schema(
            nested_schema,
            field=f"{field}.properties.{nested_name}",
            property_name=nested_name,
        )


def _validate_combined_variants(schema: Mapping[str, Any], *, field: str) -> None:
    for key in ("anyOf", "oneOf", "allOf"):
        value = schema.get(key)
        if value is None:
            continue
        if not isinstance(value, list) or not value:
            raise ValueError(f"{field}.{key} must be a non-empty list")
        for index, row in enumerate(value):
            if not isinstance(row, Mapping):
                raise ValueError(f"{field}.{key}[{index}] must be an object")
            if _schema_type_has(row, "object"):
                _validate_object_property(row, field=f"{field}.{key}[{index}]")


def _validate_output_schema(schema: Mapping[str, Any], *, field: str) -> None:
    if not isinstance(schema, Mapping):
        raise ValueError(f"{field} must be an object")
    if schema == {"$ref": "ToolResult"}:
        return
    if schema.get("type") != "object":
        raise ValueError(f"{field} must be an object schema or {{$ref: 'ToolResult'}}")


def validate_definition(definition: ToolDefinition) -> None:
    if not isinstance(definition, ToolDefinition):
        raise ValueError("definition must be ToolDefinition")

    tool_id = _require_text(definition.id, field="ToolDefinition.id")
    if _TOOL_ID_RE.match(tool_id) is None:
        raise ValueError("ToolDefinition.id must be lowercase text")

    _require_text(definition.title, field=f"{tool_id}.title")
    _require_text(definition.description, field=f"{tool_id}.description")
    _require_text(definition.cli_resource, field=f"{tool_id}.cli_resource")
    _require_text(definition.command, field=f"{tool_id}.command")
    _require_text(definition.scope, field=f"{tool_id}.scope")
    _require_text(definition.capability_boundary, field=f"{tool_id}.capability_boundary")

    seen_actions: set[str] = set()
    for action in definition.actions:
        if not isinstance(action, ActionDefinition):
            raise ValueError(f"{tool_id}.actions entries must be ActionDefinition")
        name = _require_text(action.name, field=f"{tool_id}.actions.name")
        if _ACTION_ID_RE.match(name) is None:
            raise ValueError(f"{tool_id}.actions.{name}: action id must be lowercase with underscores")
        if name in seen_actions:
            raise ValueError(f"{tool_id}.actions.{name}: duplicate action id")
        seen_actions.add(name)

        _require_text(action.title, field=f"{tool_id}.{name}.title")
        _require_text(action.description, field=f"{tool_id}.{name}.description")
        _require_text(action.kind, field=f"{tool_id}.{name}.kind")
        _require_text(action.required_permission, field=f"{tool_id}.{name}.required_permission")
        _require_text(action.authority, field=f"{tool_id}.{name}.authority")
        if action.mutates not in _ALLOWED_MUTATION_VALUES:
            raise ValueError(f"{tool_id}.{name}.mutates must be one of {_ALLOWED_MUTATION_VALUES}")

        _validate_schema_object(action.input_schema, field=f"{tool_id}.{name}.input_schema")
        _validate_output_schema(action.output_schema, field=f"{tool_id}.{name}.output_schema")
