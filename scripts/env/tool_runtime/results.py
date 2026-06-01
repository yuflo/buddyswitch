#!/usr/bin/env python3
"""Canonical env.tool response helpers and structured next-action options."""

from __future__ import annotations

from typing import Any

from env.tool_runtime.definition import MUTATES_NONE

_SUCCESS_CANONICAL_FIELDS = {
    "ok",
    "tool",
    "action",
    "active_actor",
    "active_role",
    "effect_summary",
    "state_changed",
    "durability",
    "allowed_next_actions",
    "allowed_next_action_options",
    "state_changes",
    "created_ids",
    "updated_ids",
    "binding_changed",
    "read_scope",
    "validation_only",
    "follow_up_affordances",
}

_REJECTION_CANONICAL_FIELDS = {
    "ok",
    "tool",
    "action",
    "active_actor",
    "active_role",
    "error",
    "permission_boundary",
    "human_summary",
    "why_blocked",
    "impact",
    "state_changed",
    "durability",
    "retryable",
    "retry_guidance",
    "allowed_next_actions",
    "allowed_next_action_options",
    "boundary",
    "correctable_fields",
    "alternative_capabilities",
    "mutates_product_state",
    "field_errors",
}

_FORBIDDEN_AFFORDANCE_FRAGMENTS = (
    "must create artifact",
    "always create artifact",
    "only next action",
    "after writing a prd",
    "market research should",
    "if the user says",
)


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _role_id_text(value: Any, field: str = "active_role") -> str:
    role_id = getattr(value, "role_id", value)
    return _require_non_empty_text(role_id, field)


def _require_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a bool")
    return value


def _require_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


def _active_actor_payload(active_actor: dict[str, Any] | None, active_role: str) -> dict[str, Any]:
    if isinstance(active_actor, dict):
        return dict(active_actor)
    return {"role_id": _role_id_text(active_role)}


def _merge_extra(payload: dict[str, Any], extra: dict[str, Any], canonical_fields: set[str]) -> None:
    overlap = sorted(key for key in extra if key in canonical_fields)
    if overlap:
        raise ValueError(f"extra cannot override canonical fields: {', '.join(overlap)}")
    payload.update(extra)


def _require_conditional_affordance_text(value: Any, field: str) -> str:
    text = _require_non_empty_text(value, field)
    lowered = text.lower()
    for fragment in _FORBIDDEN_AFFORDANCE_FRAGMENTS:
        if fragment in lowered:
            raise ValueError(f"{field} must stay conditional and must not prescribe workflow steps")
    return text


def _validate_next_action_options(value: Any) -> list[dict[str, Any]]:
    rows = _require_list(value, "allowed_next_action_options")
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"allowed_next_action_options[{index}] must be an object")
        _require_conditional_affordance_text(row.get("reason"), f"allowed_next_action_options[{index}].reason")
        normalized.append(dict(row))
    return normalized


def _validate_field_errors(value: Any) -> list[dict[str, Any]]:
    rows = _require_list(value, "field_errors")
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"field_errors[{index}] must be an object")
        path = _require_non_empty_text(row.get("path"), f"field_errors[{index}].path")
        message = _require_non_empty_text(row.get("message"), f"field_errors[{index}].message")
        if not any(key in row for key in ("expected", "allowed_values", "example")):
            raise ValueError(
                f"field_errors[{index}] must include expected, allowed_values, or example"
            )
        normalized.append(dict(row, path=path, message=message))
    return normalized


def next_action_option(
    *,
    tool: str,
    action: str,
    reason: str,
    option_id: str | None = None,
    mutates: str | None = None,
    preconditions: list[str] | None = None,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    normalized_mutates = mutates if isinstance(mutates, str) and mutates else MUTATES_NONE
    normalized_preconditions = list(preconditions) if isinstance(preconditions, list) else []
    normalized_source_refs = (
        list(source_refs)
        if isinstance(source_refs, list) and source_refs
        else [f"runtime_context.operation_semantics['{tool}.{action}']"]
    )
    return {
        "id": option_id or f"{tool}.{action}",
        "tool": tool,
        "action": action,
        "native_tool": f"{tool}__{action}",
        "mutates": normalized_mutates,
        "preconditions": normalized_preconditions,
        "reason": _require_conditional_affordance_text(reason, "reason"),
        "source_refs": normalized_source_refs,
    }


def follow_up_affordance(
    *,
    tool: str,
    action: str,
    reason: str,
    affordance_id: str | None = None,
    preconditions: list[str] | None = None,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    return next_action_option(
        tool=tool,
        action=action,
        reason=reason,
        option_id=affordance_id or f"follow_up.{tool}.{action}",
        preconditions=preconditions,
        source_refs=source_refs,
    )


def tool_affordance(
    tool: str,
    action: str,
    effect: str,
    condition: str,
    risk: str | None = None,
    mutates_product_state: bool = False,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "tool": _require_non_empty_text(tool, "tool"),
        "action": _require_non_empty_text(action, "action"),
        "effect": _require_non_empty_text(effect, "effect"),
        "condition": _require_conditional_affordance_text(condition, "condition"),
        "mutates_product_state": bool(mutates_product_state),
    }
    if isinstance(risk, str) and risk.strip():
        row["risk"] = risk.strip()
    return row


def alternative_capability(
    *,
    tool: str,
    action: str,
    condition: str,
    mutates_product_state: bool | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "tool": _require_non_empty_text(tool, "tool"),
        "action": _require_non_empty_text(action, "action"),
        "condition": _require_conditional_affordance_text(condition, "condition"),
    }
    if isinstance(mutates_product_state, bool):
        row["mutates_product_state"] = mutates_product_state
    return row


def success(
    *,
    tool: str,
    action: str,
    active_role: str,
    effect_summary: str,
    state_changed: bool,
    durability: str,
    active_actor: dict[str, Any] | None = None,
    allowed_next_actions: list[str] | None = None,
    allowed_next_action_options: list[dict[str, Any]] | None = None,
    state_changes: list[dict[str, Any]] | None = None,
    created_ids: list[str] | None = None,
    updated_ids: list[str] | None = None,
    binding_changed: bool | None = None,
    read_scope: str | None = None,
    validation_only: bool | None = None,
    follow_up_affordances: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "tool": tool,
        "action": action,
        "active_actor": _active_actor_payload(active_actor, active_role),
        "active_role": _role_id_text(active_role),
        "effect_summary": _require_non_empty_text(effect_summary, "effect_summary"),
        "state_changed": _require_bool(state_changed, "state_changed"),
        "durability": _require_non_empty_text(durability, "durability"),
        "allowed_next_actions": list(allowed_next_actions or []),
    }
    if isinstance(allowed_next_action_options, list):
        payload["allowed_next_action_options"] = _validate_next_action_options(allowed_next_action_options)
    if state_changes is not None:
        payload["state_changes"] = _require_list(state_changes, "state_changes")
    if created_ids is not None:
        payload["created_ids"] = _require_list(created_ids, "created_ids")
    if updated_ids is not None:
        payload["updated_ids"] = _require_list(updated_ids, "updated_ids")
    if binding_changed is not None:
        payload["binding_changed"] = _require_bool(binding_changed, "binding_changed")
    if read_scope is not None:
        payload["read_scope"] = _require_non_empty_text(read_scope, "read_scope")
    if validation_only is not None:
        payload["validation_only"] = _require_bool(validation_only, "validation_only")
    if follow_up_affordances is not None:
        payload["follow_up_affordances"] = _require_list(follow_up_affordances, "follow_up_affordances")
    if isinstance(extra, dict):
        _merge_extra(payload, extra, _SUCCESS_CANONICAL_FIELDS)
    return payload


def rejection(
    *,
    tool: str,
    action: str,
    active_role: str,
    code: str,
    message: str,
    permission_boundary: str,
    human_summary: str,
    why_blocked: str,
    impact: str,
    state_changed: bool,
    durability: str = "none",
    retryable: bool,
    retry_guidance: str,
    active_actor: dict[str, Any] | None = None,
    allowed_next_actions: list[str] | None = None,
    allowed_next_action_options: list[dict[str, Any]] | None = None,
    error_class: str | None = None,
    boundary: str | None = None,
    correctable_fields: list[str] | None = None,
    alternative_capabilities: list[dict[str, Any]] | None = None,
    mutates_product_state: bool | None = None,
    field_errors: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "tool": tool,
        "action": action,
        "active_actor": _active_actor_payload(active_actor, active_role),
        "active_role": _role_id_text(active_role),
        "error": {
            "code": code,
            "message": message,
        },
        "permission_boundary": permission_boundary,
        "human_summary": _require_non_empty_text(human_summary, "human_summary"),
        "why_blocked": _require_non_empty_text(why_blocked, "why_blocked"),
        "impact": _require_non_empty_text(impact, "impact"),
        "state_changed": _require_bool(state_changed, "state_changed"),
        "durability": _require_non_empty_text(durability, "durability"),
        "retryable": _require_bool(retryable, "retryable"),
        "retry_guidance": _require_non_empty_text(retry_guidance, "retry_guidance"),
        "allowed_next_actions": list(allowed_next_actions or []),
    }
    if isinstance(error_class, str) and error_class.strip():
        payload["error"]["class"] = error_class.strip()
    if isinstance(boundary, str) and boundary.strip():
        payload["boundary"] = boundary.strip()
    if isinstance(correctable_fields, list):
        payload["correctable_fields"] = list(correctable_fields)
    if isinstance(alternative_capabilities, list):
        payload["alternative_capabilities"] = list(alternative_capabilities)
    if mutates_product_state is not None:
        payload["mutates_product_state"] = _require_bool(mutates_product_state, "mutates_product_state")
    if field_errors is not None:
        payload["field_errors"] = _validate_field_errors(field_errors)
    if isinstance(allowed_next_action_options, list):
        payload["allowed_next_action_options"] = _validate_next_action_options(allowed_next_action_options)
    if isinstance(extra, dict):
        _merge_extra(payload, extra, _REJECTION_CANONICAL_FIELDS)
    return payload
