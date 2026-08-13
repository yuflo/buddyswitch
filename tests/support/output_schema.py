"""Load and validate BuddySwitch output schemas.

This module validates structural contracts only. It does not evaluate business
quality, research quality, or workflow completeness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


class OutputSchemaError(ValueError):
    """Raised when a schema or payload is invalid."""


def normalize_schema_path(raw_path: str) -> str:
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        raise OutputSchemaError(f"schema path must be repo-relative: {raw_path}")
    normalized = path.as_posix()
    parts = path.parts
    if not (
        len(parts) == 6
        and parts[:3] == ("src", "buddyswitch", "roles")
        and parts[4:] == ("assets", "result-schema.json")
    ):
        raise OutputSchemaError(
            "schema path must be one Role package assets/result-schema.json"
        )
    return normalized


def load_output_schema(raw_path: str) -> dict[str, Any]:
    normalized = normalize_schema_path(raw_path)
    path = ROOT / normalized
    if not path.exists():
        raise OutputSchemaError(f"schema file not found: {normalized}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OutputSchemaError(f"invalid JSON in schema {normalized}: {exc}") from exc
    if not isinstance(payload, dict):
        raise OutputSchemaError(f"schema {normalized} must contain a JSON object")
    return payload


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise OutputSchemaError(f"unsupported schema type: {expected}")


def _type_label(node: dict[str, Any]) -> str | None:
    raw = node.get("type")
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return " or ".join(str(item) for item in raw)
    raise OutputSchemaError("schema 'type' must be a string or list")


def _validate_node(value: Any, schema: dict[str, Any], path: str, errors: list[str]) -> None:
    raw_type = schema.get("type")
    allowed_types: list[str] = []
    if isinstance(raw_type, str):
        allowed_types = [raw_type]
    elif isinstance(raw_type, list):
        if not raw_type or any(not isinstance(item, str) for item in raw_type):
            raise OutputSchemaError("schema 'type' list must contain one or more strings")
        allowed_types = list(raw_type)
    elif raw_type is not None:
        raise OutputSchemaError("schema 'type' must be a string or list")

    if allowed_types and not any(_type_matches(value, expected) for expected in allowed_types):
        errors.append(f"{path}: expected {_type_label(schema)}, got {type(value).__name__}")
        return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} is not in enum {schema['enum']!r}")
        return

    if isinstance(value, dict):
        required = schema.get("required", [])
        if required:
            if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
                raise OutputSchemaError(f"{path}: object schema 'required' must be a list of strings")
            for key in required:
                if key not in value:
                    errors.append(f"{path}: missing required property '{key}'")

        properties = schema.get("properties", {})
        if properties and not isinstance(properties, dict):
            raise OutputSchemaError(f"{path}: object schema 'properties' must be an object")
        for key, child_schema in properties.items():
            if not isinstance(child_schema, dict):
                raise OutputSchemaError(f"{path}.{key}: property schema must be an object")
            if key in value:
                _validate_node(value[key], child_schema, f"{path}.{key}", errors)

        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            for key in extras:
                errors.append(f"{path}: unsupported property '{key}'")
        return

    if isinstance(value, list):
        min_items = schema.get("minItems")
        if min_items is not None:
            if not isinstance(min_items, int) or min_items < 0:
                raise OutputSchemaError(f"{path}: array schema minItems must be a non-negative integer")
            if len(value) < min_items:
                errors.append(f"{path}: expected at least {min_items} item(s), got {len(value)}")
        item_schema = schema.get("items")
        if item_schema is None:
            return
        if not isinstance(item_schema, dict):
            raise OutputSchemaError(f"{path}: array schema 'items' must be an object")
        for index, item in enumerate(value):
            _validate_node(item, item_schema, f"{path}[{index}]", errors)


def validate_output_payload(payload: Any, schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(schema, dict):
        raise OutputSchemaError("schema must be a JSON object")
    _validate_node(payload, schema, "$", errors)
    return errors
