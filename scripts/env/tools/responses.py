#!/usr/bin/env python3
"""Canonical env.tool response helpers and structured next-action options."""

from __future__ import annotations

from typing import Any

from env.tools import contracts

_SUCCESS_CANONICAL_FIELDS = {
    "ok",
    "tool",
    "action",
    "active_buddy",
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
    "active_buddy",
    "error",
    "permission_boundary",
    "human_summary",
    "why_blocked",
    "impact",
    "state_changed",
    "retryable",
    "retry_guidance",
    "allowed_next_actions",
    "allowed_next_action_options",
}


def _require_non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _require_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a bool")
    return value


def _require_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


def _merge_extra(payload: dict[str, Any], extra: dict[str, Any], canonical_fields: set[str]) -> None:
    overlap = sorted(key for key in extra if key in canonical_fields)
    if overlap:
        raise ValueError(f"extra cannot override canonical fields: {', '.join(overlap)}")
    payload.update(extra)


def next_action_option(
    *,
    tool: str,
    action: str,
    reason: str,
    option_id: str | None = None,
    preconditions: list[str] | None = None,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    action_spec = contracts.get_action_spec(tool, action)
    mutates = contracts.MUTATES_NONE
    default_preconditions: list[str] = []
    if isinstance(action_spec, dict):
        raw_mutates = action_spec.get("mutates")
        if isinstance(raw_mutates, str) and raw_mutates:
            mutates = raw_mutates
        for row in action_spec.get("preconditions", []):
            if isinstance(row, str) and row:
                default_preconditions.append(row)

    normalized_preconditions = list(preconditions) if isinstance(preconditions, list) else default_preconditions
    normalized_source_refs = (
        list(source_refs)
        if isinstance(source_refs, list) and source_refs
        else [f"runtime_context.operation_semantics['{tool}.{action}']"]
    )
    return {
        "id": option_id or f"{tool}.{action}",
        "tool": tool,
        "action": action,
        "mutates": mutates,
        "preconditions": normalized_preconditions,
        "reason": reason,
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


def success(
    *,
    tool: str,
    action: str,
    active_buddy: str,
    effect_summary: str,
    state_changed: bool,
    durability: str,
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
        "active_buddy": active_buddy,
        "effect_summary": _require_non_empty_text(effect_summary, "effect_summary"),
        "state_changed": _require_bool(state_changed, "state_changed"),
        "durability": _require_non_empty_text(durability, "durability"),
        "allowed_next_actions": list(allowed_next_actions or []),
    }
    if isinstance(allowed_next_action_options, list):
        payload["allowed_next_action_options"] = allowed_next_action_options
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
    active_buddy: str,
    code: str,
    message: str,
    permission_boundary: str,
    human_summary: str,
    why_blocked: str,
    impact: str,
    state_changed: bool,
    retryable: bool,
    retry_guidance: str,
    allowed_next_actions: list[str],
    allowed_next_action_options: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "tool": tool,
        "action": action,
        "active_buddy": active_buddy,
        "error": {
            "code": code,
            "message": message,
        },
        "permission_boundary": permission_boundary,
        "human_summary": _require_non_empty_text(human_summary, "human_summary"),
        "why_blocked": _require_non_empty_text(why_blocked, "why_blocked"),
        "impact": _require_non_empty_text(impact, "impact"),
        "state_changed": _require_bool(state_changed, "state_changed"),
        "retryable": _require_bool(retryable, "retryable"),
        "retry_guidance": _require_non_empty_text(retry_guidance, "retry_guidance"),
        "allowed_next_actions": list(allowed_next_actions),
    }
    if isinstance(allowed_next_action_options, list):
        payload["allowed_next_action_options"] = allowed_next_action_options
    if isinstance(extra, dict):
        _merge_extra(payload, extra, _REJECTION_CANONICAL_FIELDS)
    return payload
