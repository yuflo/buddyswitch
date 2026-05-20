#!/usr/bin/env python3
"""Runless read-only context discovery services."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from env.tool_runtime import registry as tool_registry
from .tool import DEFINITION
from env.tool_runtime import results as tool_results


_ACTION_DEFINITION_MAP = {
    'actions': [
        {
            'name': row.name,
            'payload_fields': [
                field
                for field in (row.input_schema.get('properties') or {})
                if isinstance(field, str)
            ],
        }
        for row in DEFINITION.actions
    ]
}

class ContextServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    correctable_fields: list[str] | None = None
    if "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            correctable_fields = [row.strip() for row in suffix.split(",") if row.strip()]
    else:
        for field in ("track_id", "task_id", "limit"):
            if field in message:
                correctable_fields = [field]
                break
    return tool_results.rejection(
        tool="context",
        action=action,
        active_buddy=active_buddy,
        code="E_CONTEXT_PAYLOAD",
        message=message,
        permission_boundary="context.filter",
        human_summary="Context filter payload is invalid.",
        why_blocked=message,
        impact="Context discovery stayed read-only and did not mutate state.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix context filter payload and retry.",
        allowed_next_actions=[
            "Use context.list_sources to inspect valid sections.",
            "Retry with supported context filter fields only.",
        ],
        correctable_fields=correctable_fields,
    )


def _require_allowed_fields(action: str, args: dict[str, Any], active_buddy: str) -> dict[str, Any] | None:
    _, action_name = action.split(".", 1)
    allowed = set()
    for row in _ACTION_DEFINITION_MAP.get("actions", []):
        if isinstance(row, dict) and row.get("name") == action_name:
            allowed = {field for field in row.get("payload_fields", []) if isinstance(field, str)}
            break
    unknown = sorted(key for key in args if key not in allowed)
    if unknown:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"unsupported payload fields: {', '.join(unknown)}",
        )
    return None


def _candidate_track_row(*, track: dict[str, Any], active_buddy: str) -> dict[str, Any]:
    role = "owner" if track.get("owner_buddy") == active_buddy else "collaborator"
    return {
        "track_id": track.get("id"),
        "title": track.get("title"),
        "outcome": track.get("outcome", ""),
        "owner_buddy": track.get("owner_buddy"),
        "state": track.get("state"),
        "health": track.get("health"),
        "now": track.get("now"),
        "active_buddy_role": role,
        "updated_at": track.get("updated_at"),
    }


def _visible_tracks(*, track_filter: str | None, limit_value: int, context: ContextServiceContext) -> list[dict[str, Any]]:
    tracks = [row for row in context.repos.track.list_tracks() if row.get("archived_at") is None]
    if isinstance(track_filter, str) and track_filter.strip():
        tracks = [row for row in tracks if row.get("id") == track_filter.strip()]
    return tracks[:limit_value]


def _visible_tasks(
    *,
    active_buddy: str,
    task_filter: str | None,
    visible_track_ids: set[str],
    limit_value: int,
    context: ContextServiceContext,
) -> list[dict[str, Any]]:
    tasks = [row for row in context.repos.task.list_tasks() if row.get("buddy") == active_buddy]
    if isinstance(task_filter, str) and task_filter.strip():
        tasks = [row for row in tasks if row.get("id") == task_filter.strip()]
    rows: list[dict[str, Any]] = []
    for task in tasks:
        track_id = task.get("track_id")
        if isinstance(track_id, str) and track_id and track_id not in visible_track_ids:
            continue
        rows.append(task)
        if len(rows) >= limit_value:
            break
    return rows


def _current_material_rows(
    *,
    tracks: list[dict[str, Any]],
    active_buddy: str,
    limit_value: int,
    context: ContextServiceContext,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_material_ref_ids: set[str] = set()
    for track in tracks:
        track_id = track.get("id")
        if not isinstance(track_id, str) or not track_id:
            continue
        for row in context.rules.artifact_visibility.current_material_rows_for_track(track_id, active_buddy):
            artifact_id = row.get("artifact_id")
            if not isinstance(artifact_id, str) or not artifact_id or artifact_id in seen_material_ref_ids:
                continue
            seen_material_ref_ids.add(artifact_id)
            rows.append(row)
            if len(rows) >= limit_value:
                return rows
    return rows


def _current_context_sections(
    *,
    active_buddy: str,
    args: dict[str, Any],
    instance_payload: dict[str, Any],
    context: ContextServiceContext,
) -> dict[str, Any]:
    track_filter = args.get("track_id")
    task_filter = args.get("task_id")
    limit = args.get("limit")
    limit_value = limit if isinstance(limit, int) and limit > 0 else 20

    visible_tracks = _visible_tracks(
        track_filter=track_filter if isinstance(track_filter, str) else None,
        limit_value=limit_value,
        context=context,
    )
    visible_track_ids = {row.get("id") for row in visible_tracks if isinstance(row.get("id"), str)}
    visible_tasks = _visible_tasks(
        active_buddy=active_buddy,
        task_filter=task_filter if isinstance(task_filter, str) else None,
        visible_track_ids=visible_track_ids,
        limit_value=limit_value,
        context=context,
    )
    visible_artifacts = _current_material_rows(
        tracks=visible_tracks,
        active_buddy=active_buddy,
        limit_value=limit_value,
        context=context,
    )

    buddybox_desc = context.rules.buddybox_workspace.build_buddybox_desc(active_buddy, instance_payload=instance_payload)
    candidate_tracks = [_candidate_track_row(track=row, active_buddy=active_buddy) for row in visible_tracks]

    return {
        "tool_catalog": tool_registry.env_tools_description(),
        "operation_semantics": tool_registry.operation_semantics(),
        "tool_catalog_errors": tool_registry.tool_catalog_errors(),
        "tracks": visible_tracks,
        "tasks": visible_tasks,
        "artifact_summaries": visible_artifacts,
        "buddybox_desc": buddybox_desc,
        "candidate_tracks": candidate_tracks,
        "decision_surface": {
            "binding_state": {"state": "runless", "enum_values": ["runless"]},
            "active_buddy_relation": {"role": "explicit-id-tools"},
            "context_readiness": {
                "has_tracks": bool(visible_tracks),
                "has_tasks": bool(visible_tasks),
                "has_artifacts": bool(visible_artifacts),
                "has_buddybox_workspace": bool(buddybox_desc),
            },
        },
        "current_context_summary": {
            "tracks": len(visible_tracks),
            "tasks": len(visible_tasks),
            "artifacts": len(visible_artifacts),
            "has_buddybox_workspace": bool(buddybox_desc),
        },
    }


def context_sources_desc() -> dict[str, dict[str, Any]]:
    return {
        "tracks": {
            "description": "Readable track pages with current state and published materials.",
            "scope": "product collaboration state",
            "source_of_truth": "track.open / track.list via runtime env tools",
        },
        "tasks": {
            "description": "Active-buddy private task hints and checklists.",
            "scope": "active-buddy private task state",
            "source_of_truth": "task.get / task.list via runtime env tools",
        },
        "artifacts": {
            "description": "Readable artifact summaries for current shared track materials.",
            "scope": "product deliverable state",
            "source_of_truth": "artifact.get via runtime env tools",
        },
        "messages": {
            "description": "Direct buddy inbox messages, read through message.list.",
            "scope": "active-buddy inbox communication",
            "source_of_truth": "message.list via runtime env tools",
        },
        "comments": {
            "description": "Target-scoped comments on tracks and artifacts, read through comment.list.",
            "scope": "target discussion thread",
            "source_of_truth": "comment.list via runtime env tools",
        },
        "buddybox": {
            "description": "Active buddy private file capability metadata and tool-backed private data plane.",
            "scope": "active-buddy private file capability",
            "capability": "private_file_workspace",
            "owner_scope": "active_buddy",
            "lifetime_scope": "active_instance_workspace",
            "visibility": "active_buddy_private",
            "product_readable": False,
            "cross_buddy_readable": False,
            "mutates_product_state": False,
            "supports": [
                "describe_capability",
                "list_private_file_summaries",
                "read_private_file",
                "write_private_text",
                "write_private_binary",
                "delete_private_file",
            ],
        },
    }


def get_context(*, args: dict[str, Any], context: ContextServiceContext) -> dict[str, Any]:
    action = "context.get"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    sections = _current_context_sections(
        active_buddy=active_buddy,
        args=args,
        instance_payload=context["instance_payload"],
        context=context,
    )
    return tool_results.success(
        tool="context",
        action=action,
        active_buddy=active_buddy,
        effect_summary="Returned full runtime context sections plus full tool catalog and full operation semantics.",
        state_changed=False,
        durability="none",
        read_scope="read-only runtime context sections and full catalog metadata",
        allowed_next_actions=[
            "Use task/track/artifact/buddybox tools with explicit ids.",
            "Use context.summarize for compact orientation.",
        ],
        extra=sections,
    )


def summarize_context(*, args: dict[str, Any], context: ContextServiceContext) -> dict[str, Any]:
    action = "context.summarize"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    sections = _current_context_sections(
        active_buddy=active_buddy,
        args=args,
        instance_payload=context["instance_payload"],
        context=context,
    )
    summary = {
        "current_context_summary": sections["current_context_summary"],
        "candidate_tracks": sections["candidate_tracks"],
        "buddybox_desc": sections["buddybox_desc"],
        "tool_affordances": tool_registry.compact_tool_affordances(),
        "decision_surface": sections["decision_surface"],
    }

    return tool_results.success(
        tool="context",
        action=action,
        active_buddy=active_buddy,
        effect_summary="Returned compact context orientation with candidate ids, buddybox descriptor, and first-pass tool affordances.",
        state_changed=False,
        durability="none",
        read_scope="compact read-only orientation; not full catalog",
        allowed_next_actions=[
            "Use explicit ids from candidate tracks/tasks/artifacts in subsequent tool calls.",
            "Use context.get for full sections when needed.",
        ],
        extra=summary,
    )


def list_sources(*, args: dict[str, Any], context: ContextServiceContext) -> dict[str, Any]:
    action = "context.list_sources"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    return tool_results.success(
        tool="context",
        action=action,
        active_buddy=active_buddy,
        effect_summary="Returned context source descriptors only.",
        state_changed=False,
        durability="none",
        read_scope="source descriptor metadata only",
        allowed_next_actions=["Use context.summarize or context.get with optional filters."],
        extra={"sources": context_sources_desc()},
    )


_ACTION_HANDLERS = {
    'get': get_context,
    'list_sources': list_sources,
    'summarize': summarize_context,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    return handler(args=args, context=context)
