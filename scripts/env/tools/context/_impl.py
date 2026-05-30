#!/usr/bin/env python3
"""Runless read-only context discovery services."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

import env_profiles
from env.tool_runtime import registry as tool_registry
from env.tool_runtime import results as tool_results
from .tool import DEFINITION


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

_DISCOVERY_EXCLUDED_TOOLS = {"buddybox"}

class ContextServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]
    manifest_path: Path | None


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


def _repo_root_from_manifest_path(manifest_path: Path) -> Path:
    resolved = manifest_path.resolve(strict=False)
    if len(resolved.parents) < 2:
        raise ValueError(f"manifest path is not under expected repo layout: {resolved}")
    return resolved.parents[1]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _shared_root_from_instance_json_path(instance_json_path: Path) -> Path | None:
    instance_root = instance_json_path.parent
    if instance_root.parent.name != "instances":
        return None
    return instance_root.parent.parent.resolve(strict=False)


def _launcher_project_workspace_from_context(
    *,
    context: ContextServiceContext,
    runtime_workspace: Path,
) -> Path | None:
    instance_json_raw = context.get("instance_json")
    if isinstance(instance_json_raw, Path):
        shared_root = _shared_root_from_instance_json_path(instance_json_raw.resolve(strict=False))
        if shared_root is not None:
            return (shared_root / "project" / "workspace").resolve(strict=False)
    if runtime_workspace.name == "workspace" and runtime_workspace.parent.parent.name == "instances":
        shared_root = runtime_workspace.parent.parent.parent.resolve(strict=False)
        return (shared_root / "project" / "workspace").resolve(strict=False)
    return None


def _source_root_from_runtime_projection(
    *,
    runtime_workspace: Path,
    project_workspace: Path | None,
    project_path: str,
) -> Path:
    runtime_source_root = runtime_workspace / project_path
    resolved_source_root = runtime_source_root.resolve(strict=False)
    if _is_relative_to(resolved_source_root, runtime_workspace):
        return resolved_source_root
    if project_workspace is None:
        raise ValueError("source root symlink resolves outside runtime workspace and launcher project workspace")
    expected_project_source_root = (project_workspace / project_path).resolve(strict=False)
    if resolved_source_root != expected_project_source_root:
        raise ValueError("source root symlink resolves outside launcher project workspace")
    return resolved_source_root


def _load_active_env_profile(
    context: ContextServiceContext,
    active_buddy: str,
) -> dict[str, Any]:
    manifest_path_raw = context.get("manifest_path")
    if manifest_path_raw is None:
        raise ValueError("manifest_path is required for source_workspace profile resolution")
    manifest_path = Path(str(manifest_path_raw)).expanduser().resolve(strict=False)
    repo_root = _repo_root_from_manifest_path(manifest_path)
    return env_profiles.require_env_profile(
        active_buddy,
        manifest_path=manifest_path,
        repo_root=repo_root,
    )


def _classify_source_root(root: Path, *, limit: int = 20) -> tuple[str, list[str], bool]:
    if not root.exists() or not root.is_dir():
        return "missing", [], False
    all_entries = sorted(path.name for path in root.iterdir() if not path.name.startswith("."))
    entries = all_entries[:limit]
    truncated = len(all_entries) > limit
    if not entries:
        return "empty", [], truncated
    lowered = {entry.lower() for entry in all_entries}
    if lowered <= {"readme", "readme.md"}:
        return "readme_only", entries, truncated
    return "has_source", entries, truncated


def _source_workspace_rejection(
    *,
    action: str,
    active_buddy: str,
    message: str,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="context",
        action=action,
        active_buddy=active_buddy,
        code="E_CONTEXT_SOURCE_WORKSPACE",
        message=message,
        permission_boundary="context.source_workspace",
        human_summary="Source workspace facts are unavailable for this runtime context.",
        why_blocked=message,
        impact="Context did not guess source-root facts and did not mutate state.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix env profile/runtime workspace wiring, then retry context discovery.",
        allowed_next_actions=[
            "Check env profile validation and project.path/source_root settings.",
            "Retry context.summarize or context.get after runtime profile resolution is fixed.",
        ],
    )


def _build_source_workspace(
    *,
    active_buddy: str,
    instance_payload: dict[str, Any],
    context: ContextServiceContext,
    include_resolved_path: bool,
) -> dict[str, Any]:
    profile = _load_active_env_profile(context, active_buddy)
    project_path = str(profile.get("project", {}).get("path", "")).strip()
    if not project_path:
        raise ValueError("env profile project.path is missing")
    source_root_access = str(profile.get("filesystem_capability", {}).get("source_root", "")).strip()
    if source_root_access not in {"write", "read-only"}:
        raise ValueError("env profile filesystem_capability.source_root must be 'write' or 'read-only'")

    workspace_key = "workspace" + "_dir"
    runtime_workspace_raw = instance_payload.get(workspace_key)
    if not isinstance(runtime_workspace_raw, str) or not runtime_workspace_raw.strip():
        raise ValueError("instance payload workspace path is missing")
    runtime_workspace = Path(runtime_workspace_raw).expanduser().resolve(strict=False)
    runtime_source_raw = runtime_workspace / project_path
    if not _is_relative_to(runtime_source_raw, runtime_workspace):
        raise ValueError("profile project.path resolves outside runtime workspace")
    project_workspace = _launcher_project_workspace_from_context(
        context=context,
        runtime_workspace=runtime_workspace,
    )
    source_root = _source_root_from_runtime_projection(
        runtime_workspace=runtime_workspace,
        project_workspace=project_workspace,
        project_path=project_path,
    )

    state, entries, truncated = _classify_source_root(source_root)
    source_workspace: dict[str, Any] = {
        "active_buddy": active_buddy,
        "path": project_path,
        "access": source_root_access,
        "can_write_source": source_root_access == "write",
        "state": state,
        "top_level_entries": entries,
        "top_level_entries_truncated": truncated,
        "source_of_truth": "env_profile.project.path + env_profile.filesystem_capability.source_root + workspace_projection",
        "permission_boundary": (
            "context is read-only; filesystem writes are enforced by sandbox profile; "
            "context does not configure roots or grant write access"
        ),
    }
    if include_resolved_path:
        source_workspace["resolved_path"] = str(source_root)
    return source_workspace


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


def _candidate_request_row(*, request: dict[str, Any], active_buddy: str) -> dict[str, Any]:
    direction = "incoming" if request.get("to_buddy") == active_buddy else "outgoing"
    if active_buddy == "pm" and request.get("to_buddy") != active_buddy and request.get("from_buddy") != active_buddy:
        direction = "pm-visible"
    result_refs = request.get("result_refs")
    blocker = request.get("blocker")
    return {
        "request_id": request.get("id"),
        "track_id": request.get("track_id"),
        "from_buddy": request.get("from_buddy"),
        "to_buddy": request.get("to_buddy"),
        "title": request.get("title"),
        "status": request.get("status"),
        "direction": direction,
        "blocker": blocker if isinstance(blocker, str) else None,
        "result_ref_count": len(result_refs) if isinstance(result_refs, list) else 0,
        "updated_at": request.get("updated_at"),
    }


def _candidate_task_row(*, task: dict[str, Any]) -> dict[str, Any]:
    refs = task.get("refs")
    return {
        "task_id": task.get("id"),
        "title": task.get("title"),
        "summary": task.get("summary"),
        "status": task.get("status"),
        "priority": task.get("priority"),
        "track_id": task.get("track_id"),
        "closed_at": task.get("closed_at"),
        "ref_count": len(refs) if isinstance(refs, list) else 0,
        "updated_at": task.get("updated_at"),
    }


def _capability_snapshot(*, context: ContextServiceContext) -> dict[str, Any]:
    operation_semantics = tool_registry.operation_semantics(exclude_tools=_DISCOVERY_EXCLUDED_TOOLS)
    affordances = tool_registry.compact_tool_affordances(exclude_tools=_DISCOVERY_EXCLUDED_TOOLS)
    artifact_create = operation_semantics["artifact.create_revision"]
    runtime_policy_preview = context.runtime_policy_preview(operation_semantics)
    return {
        "runtime_policy_preview": runtime_policy_preview,
        "task_visibility": str(operation_semantics["task.current"]["visibility"]),
        "artifact_publication_path": " ".join(
            [
                str(artifact_create["success_effect"]),
                "Does not write:",
                ", ".join(str(row) for row in artifact_create["does_not_write"]),
            ]
        ),
        "comment_target_support": str(affordances["comment"]["object_model"]),
        "request_lifecycle_visibility": str(operation_semantics["request.create"]["visibility"]),
        "search_boundary": str(affordances["search"]["object_model"]),
        "evidence_boundary": str(affordances["evidence"]["object_model"]),
        "writable_file_surface": "$BUDDYSWITCH_BUDDYBOX_DIR for persistent private files; $BUDDYSWITCH_INSTANCE_TMP for temporary files.",
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
    tasks = context.repos.task.list_tasks(
        active_buddy=active_buddy,
        instance_json=context["instance_json"],
        instance_payload=context["instance_payload"],
    )
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


def _candidate_artifact_rows(
    *,
    track_filter: str | None,
    active_buddy: str,
    limit_value: int,
    context: ContextServiceContext,
) -> list[dict[str, Any]]:
    normalized_track_filter = track_filter.strip() if isinstance(track_filter, str) and track_filter.strip() else None
    rows: list[dict[str, Any]] = []
    for artifact in context.repos.artifact.list_artifacts():
        decision = context.rules.artifact_visibility.artifact_read_decision(artifact, active_buddy)
        if not bool(decision.get("allowed")):
            continue
        if not _context_artifact_row_allowed(
            artifact=artifact,
            decision=decision,
            active_buddy=active_buddy,
            track_filter=normalized_track_filter,
        ):
            continue
        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, str) or not artifact_id:
            continue
        comment_counts = context.rules.artifact_relations.comment_counts_for_artifact(artifact_id)
        relation_counts = context.rules.artifact_relations.relation_counts_for_artifact(
            artifact_id=artifact_id,
            active_buddy=active_buddy,
        )
        rows.append(
            context.rules.artifact_visibility.artifact_list_row(
                artifact,
                active_buddy,
                comment_counts=comment_counts,
                relation_counts=relation_counts,
            )
        )
    rows.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("artifact_id") or "")), reverse=True)
    return rows[:limit_value]


def _context_artifact_row_allowed(
    *,
    artifact: dict[str, Any],
    decision: dict[str, Any],
    active_buddy: str,
    track_filter: str | None,
) -> bool:
    relation = decision.get("relation")
    if isinstance(track_filter, str) and track_filter:
        if decision.get("track_id") != track_filter:
            return False
        return relation in {"track_material", "track_proof"}
    if relation in {"track_material", "track_proof"}:
        return True
    return artifact.get("status") == "draft" and artifact.get("created_by") == active_buddy


def _open_comment_thread_rows(
    *,
    visible_track_ids: set[str],
    visible_artifact_ids: set[str],
    limit_value: int,
    context: ContextServiceContext,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for comment in context.repos.comment.list_comments():
        target_type = comment.get("target_type")
        target_id = comment.get("target_id")
        if not isinstance(target_type, str) or not isinstance(target_id, str):
            continue
        normalized_target_type = "artifact" if target_type == "artifact_section" else target_type
        if normalized_target_type == "track":
            if target_id not in visible_track_ids:
                continue
        elif normalized_target_type == "artifact":
            if target_id not in visible_artifact_ids:
                continue
        else:
            continue
        thread_id = comment.get("thread_id")
        if not isinstance(thread_id, str) or not thread_id:
            continue
        grouped.setdefault(thread_id, []).append(comment)

    rows: list[dict[str, Any]] = []
    for thread_id, thread_comments in grouped.items():
        open_count = sum(1 for row in thread_comments if row.get("status") == "open")
        if open_count <= 0:
            continue
        latest = max(
            thread_comments,
            key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")),
        )
        target_type = latest.get("target_type")
        if target_type == "artifact_section":
            target_type = "artifact"
        rows.append(
            {
                "thread_id": thread_id,
                "target_type": target_type,
                "target_id": latest.get("target_id"),
                "latest_comment_id": latest.get("id"),
                "latest_by_buddy": latest.get("by_buddy"),
                "open_comment_count": open_count,
                "updated_at": latest.get("created_at"),
            }
        )
    rows.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("thread_id") or "")), reverse=True)
    return rows[:limit_value]


def _recent_update_rows(
    *,
    tracks: list[dict[str, Any]],
    limit_value: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track in tracks:
        track_id = track.get("id")
        if not isinstance(track_id, str) or not track_id:
            continue
        for update in track.get("updates", []):
            if not isinstance(update, dict):
                continue
            refs = update.get("refs")
            ref_count = len(refs) if isinstance(refs, list) else 0
            rows.append(
                {
                    "track_id": track_id,
                    "update_id": update.get("id"),
                    "kind": update.get("kind"),
                    "summary": update.get("summary"),
                    "by_buddy": update.get("by_buddy"),
                    "ref_count": ref_count,
                    "created_at": update.get("created_at"),
                }
            )
    rows.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("update_id") or "")), reverse=True)
    return rows[:limit_value]


def _message_cues(*, limit_value: int, context: ContextServiceContext) -> dict[str, Any]:
    active_actor_address = context.actor_address
    inbox = context.rules.message.filter_inbox_messages(
        messages=context.repos.message.list_messages(),
        active_actor_address=active_actor_address,
        sender_buddy=None,
        q=None,
        limit=limit_value,
    )
    latest = [
        {
            "message_id": row.get("id"),
            "from_actor_address": row.get("from_actor_address"),
            "to_actor_address": row.get("to_actor_address"),
            "reply_to": row.get("reply_to"),
            "created_at": row.get("created_at"),
        }
        for row in inbox
    ]
    return {
        "count": len(inbox),
        "latest": latest,
        "source_of_truth": "message.list",
        "target_discovery": "Use message.contacts to discover online target actor addresses.",
    }


def _visible_requests(
    *,
    active_buddy: str,
    track_filter: str | None,
    visible_track_ids: set[str],
    limit_value: int,
    context: ContextServiceContext,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    normalized_track_filter = track_filter.strip() if isinstance(track_filter, str) and track_filter.strip() else None
    for request in context.repos.request.list_requests():
        track_id = request.get("track_id")
        if not isinstance(track_id, str) or not track_id:
            continue
        if isinstance(normalized_track_filter, str):
            if track_id != normalized_track_filter:
                continue
        elif visible_track_ids and track_id not in visible_track_ids:
            continue
        try:
            context.rules.comment_target.assert_target_readable(
                target_type="track",
                target_id=track_id,
                active_buddy=active_buddy,
                action="context.get",
            )
            context.rules.request.ensure_visible(request, active_buddy)
        except (
            context.rules.comment_target.CommentTargetPayloadError,
            context.rules.comment_target.CommentTargetScopeError,
            context.rules.request.RequestScopeError,
        ):
            continue
        rows.append(request)
        if len(rows) >= limit_value:
            break
    return rows


def _current_context_sections(
    *,
    active_buddy: str,
    args: dict[str, Any],
    instance_payload: dict[str, Any],
    include_resolved_path: bool,
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
    visible_artifacts = _candidate_artifact_rows(
        track_filter=track_filter if isinstance(track_filter, str) else None,
        active_buddy=active_buddy,
        limit_value=limit_value,
        context=context,
    )
    visible_requests = _visible_requests(
        active_buddy=active_buddy,
        track_filter=track_filter if isinstance(track_filter, str) else None,
        visible_track_ids=visible_track_ids,
        limit_value=limit_value,
        context=context,
    )
    visible_artifact_ids = {
        row.get("artifact_id")
        for row in visible_artifacts
        if isinstance(row, dict) and isinstance(row.get("artifact_id"), str)
    }
    open_comment_threads = _open_comment_thread_rows(
        visible_track_ids=visible_track_ids,
        visible_artifact_ids={str(row) for row in visible_artifact_ids if isinstance(row, str)},
        limit_value=limit_value,
        context=context,
    )
    recent_updates = _recent_update_rows(
        tracks=visible_tracks,
        limit_value=limit_value,
    )
    actor_address = context.actor_address.to_payload()
    message_cues = _message_cues(limit_value=limit_value, context=context)
    source_workspace = _build_source_workspace(
        active_buddy=active_buddy,
        instance_payload=instance_payload,
        context=context,
        include_resolved_path=include_resolved_path,
    )

    writable_surfaces = _build_writable_surfaces(instance_payload)
    candidate_tracks = [_candidate_track_row(track=row, active_buddy=active_buddy) for row in visible_tracks]
    candidate_requests = [_candidate_request_row(request=row, active_buddy=active_buddy) for row in visible_requests]
    candidate_tasks = [_candidate_task_row(task=row) for row in visible_tasks]

    return {
        "tool_catalog": tool_registry.env_tools_description(exclude_tools=_DISCOVERY_EXCLUDED_TOOLS),
        "operation_semantics": tool_registry.operation_semantics(exclude_tools=_DISCOVERY_EXCLUDED_TOOLS),
        "tool_catalog_errors": tool_registry.tool_catalog_errors(),
        "tracks": visible_tracks,
        "tasks": visible_tasks,
        "artifact_summaries": visible_artifacts,
        "requests": visible_requests,
        "writable_surfaces": writable_surfaces,
        "candidate_tracks": candidate_tracks,
        "candidate_requests": candidate_requests,
        "candidate_tasks": candidate_tasks,
        "candidate_artifacts": visible_artifacts,
        "open_comment_threads": open_comment_threads,
        "recent_updates": recent_updates,
        "message_cues": message_cues,
        "actor_address": actor_address,
        "source_workspace": source_workspace,
        "capability_snapshot": _capability_snapshot(
            context=context,
        ),
        "decision_surface": {
            "binding_state": {"state": "runless", "enum_values": ["runless"]},
            "active_buddy_relation": {"role": "explicit-id-tools"},
            "context_readiness": {
                "has_tracks": bool(visible_tracks),
                "has_tasks": bool(visible_tasks),
                "has_artifacts": bool(visible_artifacts),
                "has_requests": bool(visible_requests),
                "has_open_comment_threads": bool(open_comment_threads),
                "has_recent_updates": bool(recent_updates),
                "has_writable_surfaces": bool(writable_surfaces),
            },
        },
        "current_context_summary": {
            "tracks": len(visible_tracks),
            "tasks": len(visible_tasks),
            "artifacts": len(visible_artifacts),
            "requests": len(visible_requests),
            "open_comment_threads": len(open_comment_threads),
            "recent_updates": len(recent_updates),
            "messages": int(message_cues.get("count", 0)),
            "has_writable_surfaces": bool(writable_surfaces),
        },
    }


def _build_writable_surfaces(instance_payload: dict[str, Any]) -> dict[str, Any]:
    del instance_payload
    return {
        "persistent_files": {
            "kind": "host_writable_directory",
            "env": "BUDDYSWITCH_BUDDYBOX_DIR",
            "workspace_relative_root": "buddybox",
            "durability": "active_instance_persistent",
            "mutates_product_state": False,
        },
        "temporary_files": {
            "kind": "host_writable_directory",
            "env": "BUDDYSWITCH_INSTANCE_TMP",
            "durability": "active_instance_ephemeral",
            "mutates_product_state": False,
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
            "source_of_truth": "task.current / task.propose / task.confirm via runtime env tools",
        },
        "artifacts": {
            "description": "Readable artifact summaries for private drafts and shared track materials/proofs.",
            "scope": "product deliverable state",
            "source_of_truth": "artifact.list / artifact.get via runtime env tools",
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
        "requests": {
            "description": "Cross-buddy durable collaboration request lifecycle rows.",
            "scope": "requester-recipient-pm visible request state",
            "source_of_truth": "request.list / request.get via runtime env tools",
        },
        "writable_surfaces": {
            "description": "Runtime writable filesystem surfaces for host-visible files.",
            "scope": "read-only writable-surface facts",
            "source_of_truth": "launcher instance environment and permission profile",
            "mutates_product_state": False,
            "grants_write_authority": False,
        },
        "source_workspace": {
            "description": "Runtime product source root facts for the active buddy.",
            "scope": "read-only source orientation",
            "source_of_truth": "env profile project.path/access and instance workspace projection",
            "mutates_product_state": False,
            "grants_write_authority": False,
            "configures_source_root": False,
        },
    }


def get_context(*, args: dict[str, Any], context: ContextServiceContext) -> dict[str, Any]:
    action = "context.get"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    try:
        sections = _current_context_sections(
            active_buddy=active_buddy,
            args=args,
            instance_payload=context["instance_payload"],
            include_resolved_path=True,
            context=context,
        )
    except Exception as exc:
        return _source_workspace_rejection(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
        )
    return tool_results.success(
        tool="context",
        action=action,
        active_buddy=active_buddy,
        effect_summary="Returned full runtime context sections plus source_workspace facts, writable_surfaces facts, full tool catalog, and full operation semantics.",
        state_changed=False,
        durability="none",
        read_scope="read-only runtime context sections, source workspace facts, and full catalog metadata",
        allowed_next_actions=[
            "Use task/track/artifact tools with explicit ids.",
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

    try:
        sections = _current_context_sections(
            active_buddy=active_buddy,
            args=args,
            instance_payload=context["instance_payload"],
            include_resolved_path=False,
            context=context,
        )
    except Exception as exc:
        return _source_workspace_rejection(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
        )
    summary = {
        "current_context_summary": sections["current_context_summary"],
        "source_workspace": sections["source_workspace"],
        "candidate_tracks": sections["candidate_tracks"],
        "candidate_requests": sections["candidate_requests"],
        "candidate_tasks": sections["candidate_tasks"],
        "candidate_artifacts": sections["candidate_artifacts"],
        "open_comment_threads": sections["open_comment_threads"],
        "recent_updates": sections["recent_updates"],
        "message_cues": sections["message_cues"],
        "actor_address": sections["actor_address"],
        "writable_surfaces": sections["writable_surfaces"],
        "tool_affordances": tool_registry.compact_tool_affordances(exclude_tools=_DISCOVERY_EXCLUDED_TOOLS),
        "capability_snapshot": sections["capability_snapshot"],
        "decision_surface": sections["decision_surface"],
    }

    return tool_results.success(
        tool="context",
        action=action,
        active_buddy=active_buddy,
        effect_summary="Returned compact context orientation with source_workspace facts, writable_surfaces facts, candidate ids, and first-pass tool affordances.",
        state_changed=False,
        durability="none",
        read_scope="compact read-only orientation with source_workspace facts; not full catalog",
        allowed_next_actions=[
            "Use explicit ids from candidate_tracks/candidate_tasks/candidate_artifacts/candidate_requests in subsequent tool calls.",
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
        effect_summary="Returned read-only context source descriptors, including source_workspace orientation semantics.",
        state_changed=False,
        durability="none",
        read_scope="read-only source descriptor metadata only; no root configuration or write grants",
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
