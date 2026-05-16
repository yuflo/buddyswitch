#!/usr/bin/env python3
"""Runless read-only context discovery services."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.services import buddybox as buddybox_service
from env.services import track_relations
from env.tools import contracts as tool_contracts
from env.tools import responses as tool_responses


class ContextServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


_GET_FIELDS = {"track_id", "task_id", "limit"}
_SUMMARIZE_FIELDS = {"track_id", "task_id", "limit"}
_LIST_SOURCES_FIELDS: set[str] = set()


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return tool_responses.rejection(
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
    )


def _require_allowed_fields(action: str, args: dict[str, Any], active_buddy: str) -> dict[str, Any] | None:
    allowed = _GET_FIELDS if action == "context.get" else _SUMMARIZE_FIELDS if action == "context.summarize" else _LIST_SOURCES_FIELDS
    unknown = sorted(key for key in args if key not in allowed)
    if unknown:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"unsupported payload fields: {', '.join(unknown)}")
    return None


def _artifact_summary(artifact: dict[str, Any], active_buddy: str) -> dict[str, Any]:
    row = track_relations.artifact_summary_row(artifact, active_buddy)
    row["task_id"] = artifact.get("task_id")
    row["updated_at"] = artifact.get("updated_at")
    return row


def _current_context_sections(*, active_buddy: str, args: dict[str, Any], instance_payload: dict[str, Any]) -> dict[str, Any]:
    tracks = env_store.list_tracks()
    tasks = env_store.list_tasks()
    artifacts = env_store.list_artifacts()
    handoffs = env_store.list_handoffs()

    track_filter = args.get("track_id")
    if isinstance(track_filter, str) and track_filter.strip():
        tracks = [row for row in tracks if row.get("id") == track_filter.strip()]

    task_filter = args.get("task_id")
    if isinstance(task_filter, str) and task_filter.strip():
        tasks = [row for row in tasks if row.get("id") == task_filter.strip()]

    limit = args.get("limit")
    limit_value = limit if isinstance(limit, int) and limit > 0 else 20

    visible_tracks = tracks[:limit_value]
    visible_tasks = [row for row in tasks if row.get("buddy") == active_buddy][:limit_value]

    visible_artifacts: list[dict[str, Any]] = []
    for artifact in artifacts:
        decision = track_relations.artifact_read_decision(artifact, active_buddy)
        if bool(decision.get("allowed")):
            visible_artifacts.append(_artifact_summary(artifact, active_buddy))
        if len(visible_artifacts) >= limit_value:
            break

    visible_handoffs = [
        row
        for row in handoffs
        if row.get("source_buddy") == active_buddy or row.get("target_buddy") == active_buddy or active_buddy == "pm"
    ][:limit_value]

    buddybox_desc = buddybox_service.build_buddybox_desc(active_buddy, instance_payload=instance_payload)

    candidate_tracks = []
    for track in visible_tracks:
        relation = "observer"
        if track.get("current_buddy") == active_buddy:
            relation = "current_buddy"
        elif track.get("next_buddy") == active_buddy:
            relation = "next_buddy"
        elif any(isinstance(task, dict) and task.get("track_id") == track.get("id") for task in visible_tasks):
            relation = "participant"
        candidate_tracks.append(
            {
                "track_id": track.get("id"),
                "title": track.get("title"),
                "status": track.get("status"),
                "current_buddy": track.get("current_buddy"),
                "next_buddy": track.get("next_buddy"),
                "summary": track.get("summary", ""),
                "active_buddy_role": relation,
                "updated_at": track.get("updated_at"),
            }
        )

    return {
        "tool_catalog": tool_contracts.env_tools_description(),
        "operation_semantics": tool_contracts.operation_semantics(),
        "tracks": visible_tracks,
        "tasks": visible_tasks,
        "artifact_summaries": visible_artifacts,
        "handoff_summaries": visible_handoffs,
        "buddybox_desc": buddybox_desc,
        "candidate_tracks": candidate_tracks,
        "decision_surface": {
            "binding_state": {"state": "runless", "enum_values": ["runless"]},
            "active_buddy_relation": {"role": "explicit-id-tools"},
            "context_readiness": {
                "has_tracks": bool(visible_tracks),
                "has_tasks": bool(visible_tasks),
                "has_artifacts": bool(visible_artifacts),
                "has_handoffs": bool(visible_handoffs),
                "has_buddybox_workspace": bool(buddybox_desc),
            },
        },
        "current_context_summary": {
            "tracks": len(visible_tracks),
            "tasks": len(visible_tasks),
            "artifacts": len(visible_artifacts),
            "handoffs": len(visible_handoffs),
            "has_buddybox_workspace": bool(buddybox_desc),
        },
    }


def context_sources_desc() -> dict[str, dict[str, Any]]:
    return {
        "tracks": {
            "description": "Readable track collaboration lanes.",
            "scope": "product collaboration state",
            "source_of_truth": "buddyswitch/objects/tracks/*.json",
        },
        "tasks": {
            "description": "Readable task work items.",
            "scope": "product collaboration state",
            "source_of_truth": "buddyswitch/objects/tasks/*.json",
        },
        "artifacts": {
            "description": "Readable artifact summaries and provenance refs.",
            "scope": "product deliverable state",
            "source_of_truth": "buddyswitch/objects/artifacts/*.json",
        },
        "handoffs": {
            "description": "Explicit handoff records with object references.",
            "scope": "cross-buddy collaboration state",
            "source_of_truth": "buddyswitch/objects/handoffs/*.json",
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
    )
    return tool_responses.success(
        tool="context",
        action=action,
        active_buddy=active_buddy,
        effect_summary="Returned runless context discovery sections without mutating state.",
        state_changed=False,
        durability="none",
        read_scope="read-only product-state orientation",
        allowed_next_actions=[
            "Use task/track/artifact/handoff/buddybox tools with explicit ids.",
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
    )
    summary = {
        "current_context_summary": sections["current_context_summary"],
        "candidate_tracks": sections["candidate_tracks"],
        "buddybox_desc": sections["buddybox_desc"],
        "tool_affordances": tool_contracts.compact_tool_affordances(),
        "decision_surface": sections["decision_surface"],
    }

    return tool_responses.success(
        tool="context",
        action=action,
        active_buddy=active_buddy,
        effect_summary="Returned compact runless context summary with candidate ids.",
        state_changed=False,
        durability="none",
        read_scope="read-only compact orientation",
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

    sources = context_sources_desc()
    return tool_responses.success(
        tool="context",
        action=action,
        active_buddy=active_buddy,
        effect_summary="Returned runless context source descriptors.",
        state_changed=False,
        durability="none",
        read_scope="source descriptor metadata only",
        allowed_next_actions=["Use context.summarize or context.get with optional filters."],
        extra={"sources": sources},
    )
