#!/usr/bin/env python3
"""Canonical env.tool response helpers and structured next-action options."""

from __future__ import annotations

from typing import Any

from env.tools import contracts


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


def success(
    *,
    tool: str,
    action: str,
    active_buddy: str,
    allowed_next_actions: list[str] | None = None,
    allowed_next_action_options: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "tool": tool,
        "action": action,
        "active_buddy": active_buddy,
        "allowed_next_actions": list(allowed_next_actions or []),
    }
    if isinstance(allowed_next_action_options, list):
        payload["allowed_next_action_options"] = allowed_next_action_options
    if isinstance(extra, dict):
        payload.update(extra)
    return payload


def rejection(
    *,
    tool: str,
    action: str,
    active_buddy: str,
    code: str,
    message: str,
    permission_boundary: str,
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
        "allowed_next_actions": list(allowed_next_actions),
    }
    if isinstance(allowed_next_action_options, list):
        payload["allowed_next_action_options"] = allowed_next_action_options
    if isinstance(extra, dict):
        payload.update(extra)
    return payload
