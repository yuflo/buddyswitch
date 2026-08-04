"""Runless read-only context discovery services."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, TypedDict

from buddyswitch.runtime_support import env_profiles
from buddyswitch.env.tool_runtime import registry as tool_registry
from buddyswitch.env.tool_runtime import role_auth
from buddyswitch.env.tool_runtime import results as tool_results
from buddyswitch.modules.artifact import public as artifact_public
from buddyswitch.modules.task import public as task_public
from buddyswitch.modules.track import public as track_public
from buddyswitch.modules.communication import public as communication_public
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

def _parent_disabled_actions() -> dict[str, set[str]]:
    return {
        tool: {
            action.name
            for action in tool_registry.get_definition(tool).actions
            if action.bound_capability_env is not None
        }
        for tool in tool_registry.supported_tools()
    }


def _parent_tool_catalog() -> dict[str, dict[str, Any]]:
    catalog = deepcopy(tool_registry.env_tools_description())
    for tool, disabled in _parent_disabled_actions().items():
        if not disabled:
            continue
        row = catalog.get(tool)
        if not isinstance(row, dict):
            continue
        row["operations"] = [
            action
            for action in row.get("operations", [])
            if action not in disabled
        ]
        for field in ("payload_fields", "input_schemas", "action_semantics"):
            values = row.get(field)
            if isinstance(values, dict):
                row[field] = {
                    action: value
                    for action, value in values.items()
                    if action not in disabled
                }
        native_actions = (row.get("native_mcp") or {}).get("actions")
        if isinstance(native_actions, dict):
            row["native_mcp"]["actions"] = {
                action: value
                for action, value in native_actions.items()
                if action not in disabled
            }
    return catalog


def _parent_operation_semantics() -> dict[str, dict[str, Any]]:
    disabled = {
        f"{tool}.{action}"
        for tool, actions in _parent_disabled_actions().items()
        for action in actions
    }
    return {
        action: semantics
        for action, semantics in tool_registry.operation_semantics().items()
        if action not in disabled
    }

class ContextServiceContext(TypedDict):
    active_role: str
    current_identity: dict[str, Any]
    actor_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]
    manifest_path: Path | None


def _reject_payload(*, action: str, current_identity: dict[str, Any], active_role: str, message: str) -> dict[str, Any]:
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
        current_identity=current_identity,
        active_role=active_role,
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


def _require_allowed_fields(action: str, args: dict[str, Any], current_identity: dict[str, Any], active_role: str) -> dict[str, Any] | None:
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
            current_identity=current_identity,
            active_role=active_role,
            message=f"unsupported payload fields: {', '.join(unknown)}",
        )
    return None


def _package_root_from_manifest_path(manifest_path: Path) -> Path:
    resolved = manifest_path.resolve(strict=False)
    if len(resolved.parents) < 2:
        raise ValueError(f"manifest path is not under expected repo layout: {resolved}")
    return resolved.parent.parent


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
    active_role: str,
) -> dict[str, Any]:
    manifest_path_raw = context.get("manifest_path")
    if manifest_path_raw is None:
        raise ValueError("manifest_path is required for source_workspace profile resolution")
    manifest_path = Path(str(manifest_path_raw)).expanduser().resolve(strict=False)
    package_root = _package_root_from_manifest_path(manifest_path)
    return env_profiles.require_env_profile(
        active_role,
        manifest_path=manifest_path,
        package_root=package_root,
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
    current_identity: dict[str, Any],
    active_role: str,
    message: str,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="context",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
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
    active_role: str,
    instance_payload: dict[str, Any],
    context: ContextServiceContext,
    include_resolved_path: bool,
) -> dict[str, Any]:
    profile = _load_active_env_profile(context, active_role)
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
        "active_role": active_role,
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


def _candidate_task_row(*, task: dict[str, Any]) -> dict[str, Any]:
    demand_ref = task.get("demand_ref")
    selection = task.get("selection")
    goal_binding = task.get("goal_binding")
    result = task.get("result")
    return {
        "task_id": task.get("id"),
        "demand_ref": demand_ref if isinstance(demand_ref, dict) else {},
        "objective": task.get("objective"),
        "selection": dict(selection) if isinstance(selection, dict) else {},
        "goal_binding": dict(goal_binding) if isinstance(goal_binding, dict) else None,
        "status": task.get("status"),
        "result": dict(result) if isinstance(result, dict) else None,
        "updated_at": task.get("updated_at"),
    }


def _capability_snapshot(*, context: ContextServiceContext) -> dict[str, Any]:
    operation_semantics = _parent_operation_semantics()
    affordances = tool_registry.compact_tool_affordances()
    artifact_create = operation_semantics["artifact.create_revision"]
    runtime_policy_preview = role_auth.role_action_summary(
        context["active_role"],
        context["manifest"],
        operation_semantics,
    )
    return {
        "runtime_policy_preview": runtime_policy_preview,
        "task_visibility": "Demand-bound Task objectives, native Goal bindings, and terminal Task results",
        "artifact_publication_path": " ".join(
            [
                str(artifact_create["success_effect"]),
                "Does not write:",
                ", ".join(str(row) for row in artifact_create["does_not_write"]),
            ]
        ),
        "track_comment_support": "Track comments are Track-scoped collaboration rows; use track.add_comment, track.list_comments, and track.resolve_comment_thread.",
        "search_boundary": str(affordances["search"]["object_model"]),
        "evidence_boundary": str(affordances["evidence"]["object_model"]),
        "writable_file_surface": "$BUDDYSWITCH_ACTOR_PRIVATE_DIR for persistent private files; $BUDDYSWITCH_INSTANCE_TMP for temporary files.",
    }


def _visible_tasks(
    *,
    task_filter: str | None,
    limit_value: int,
    context: ContextServiceContext,
) -> list[dict[str, Any]]:
    projection = task_public.actor_task_projection(
        context.current_actor_identity_profile,
    )
    tasks = projection["tasks"]
    if isinstance(task_filter, str) and task_filter.strip():
        tasks = [row for row in tasks if row.get("id") == task_filter.strip()]
    return tasks[:limit_value]


def _current_identity_id(context: ContextServiceContext) -> str | None:
    current_identity = getattr(context, "current_identity", None)
    identity_id = getattr(current_identity, "id", None)
    if isinstance(identity_id, str) and identity_id.strip():
        return identity_id.strip()
    raw_identity = context.get("current_identity") if hasattr(context, "get") else None
    if isinstance(raw_identity, dict) and isinstance(raw_identity.get("id"), str) and raw_identity["id"].strip():
        return raw_identity["id"].strip()
    return None


def _message_cues(*, limit_value: int, context: ContextServiceContext) -> dict[str, Any]:
    active_identity_id = _current_identity_id(context)
    if active_identity_id is None:
        inbox: list[dict[str, Any]] = []
    else:
        events = communication_public.list_im_events_for_identity(
            context["current_identity"]
        )
        inbox = [
            row
            for row in events
            if isinstance(row.get("target_identity"), dict)
            and row["target_identity"].get("id") == active_identity_id
            and row.get("visible_to_identity_id") == active_identity_id
        ]
        inbox.sort(
            key=lambda row: (
                str(row.get("created_at") or ""),
                int(row.get("sequence") or 0) if isinstance(row.get("sequence"), int) else 0,
                str(row.get("event_id") or ""),
            ),
            reverse=True,
        )
    latest = [
        {
            "event_id": row.get("event_id"),
            "message_id": row.get("message_id"),
            "conversation_id": row.get("conversation_id"),
            "sender_identity": row.get("sender_identity") if isinstance(row.get("sender_identity"), dict) else None,
            "target_identity": row.get("target_identity") if isinstance(row.get("target_identity"), dict) else None,
            "visible_to_identity_id": row.get("visible_to_identity_id"),
            "reply_to": row.get("reply_to"),
            "created_at": row.get("created_at"),
        }
        for row in inbox[:limit_value]
    ]
    return {
        "count": len(inbox),
        "latest_inbox": latest,
        "inbox_source_of_truth": "message.list",
        "conversation_source_of_truth": "message.conversation",
        "target_discovery": "Use message.contacts only when you need a target identities discovery view; message.send resolves explicit actor or external target_identity_id values through IM target rules.",
    }


def _current_context_sections(
    *,
    active_role: str,
    args: dict[str, Any],
    instance_payload: dict[str, Any],
    include_resolved_path: bool,
    context: ContextServiceContext,
) -> dict[str, Any]:
    track_filter = args.get("track_id")
    task_filter = args.get("task_id")
    limit = args.get("limit")
    limit_value = limit if isinstance(limit, int) and limit > 0 else 20

    track_snapshot = track_public.context_snapshot(
        current_identity=context["current_identity"],
        track_filter=track_filter if isinstance(track_filter, str) else None,
        limit=limit_value,
    )
    visible_tracks = list(track_snapshot.tracks)
    visible_tasks = _visible_tasks(
        task_filter=task_filter if isinstance(task_filter, str) else None,
        limit_value=limit_value,
        context=context,
    )
    visible_artifacts = artifact_public.list_readable_summaries(
        current_identity=context["current_identity"],
        track_id=track_filter if isinstance(track_filter, str) else None,
        limit=limit_value,
        active_role=active_role,
    )
    open_comment_threads = list(track_snapshot.open_comment_threads)
    recent_updates = list(track_snapshot.recent_updates)
    current_identity = context.current_identity.to_payload()
    message_cues = _message_cues(limit_value=limit_value, context=context)
    source_workspace = _build_source_workspace(
        active_role=active_role,
        instance_payload=instance_payload,
        context=context,
        include_resolved_path=include_resolved_path,
    )

    writable_surfaces = _build_writable_surfaces(instance_payload)
    candidate_tracks = list(track_snapshot.candidate_tracks)
    candidate_tasks = [_candidate_task_row(task=row) for row in visible_tasks]

    return {
        "tool_catalog": _parent_tool_catalog(),
        "operation_semantics": _parent_operation_semantics(),
        "tool_catalog_errors": tool_registry.tool_catalog_errors(),
        "tracks": visible_tracks,
        "tasks": visible_tasks,
        "artifact_summaries": visible_artifacts,
        "writable_surfaces": writable_surfaces,
        "candidate_tracks": candidate_tracks,
        "candidate_tasks": candidate_tasks,
        "candidate_artifacts": visible_artifacts,
        "open_comment_threads": open_comment_threads,
        "recent_updates": recent_updates,
        "message_cues": message_cues,
        "current_identity": current_identity,
        "source_workspace": source_workspace,
        "capability_snapshot": _capability_snapshot(
            context=context,
        ),
        "decision_surface": {
            "binding_state": {"state": "runless", "enum_values": ["runless"]},
            "active_role_relation": {"role": "explicit-id-tools"},
            "context_readiness": {
                "has_tracks": bool(visible_tracks),
                "has_tasks": bool(visible_tasks),
                "has_artifacts": bool(visible_artifacts),
                "has_open_comment_threads": bool(open_comment_threads),
                "has_recent_updates": bool(recent_updates),
                "has_writable_surfaces": bool(writable_surfaces),
            },
        },
        "current_context_summary": {
            "tracks": len(visible_tracks),
            "tasks": len(visible_tasks),
            "artifacts": len(visible_artifacts),
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
            "env": "BUDDYSWITCH_ACTOR_PRIVATE_DIR",
            "workspace_relative_root": "private",
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
            "description": "Demand-bound Task objectives, native Goal bindings, status, and terminal results.",
            "scope": "Task Sys task state",
            "source_of_truth": "task_sys.list / task_sys.get / task_sys.create / task_sys.cancel via runtime env tools",
        },
        "demands": {
            "description": "Actor-owned Demand needs, unchecked revisions, and canonical live state.",
            "scope": "active actor Demand state",
            "source_of_truth": "demand_sys.list / demand_sys.get via runtime env tools",
        },
        "artifacts": {
            "description": "Readable artifact summaries for private drafts and shared track materials/proofs.",
            "scope": "product deliverable state",
            "source_of_truth": "artifact.list / artifact.get via runtime env tools",
        },
        "messages": {
            "description": "Central IM messages: identity-scoped events through message.list, bidirectional visible context through message.conversation.",
            "scope": "active actor Central IM events and direct conversation communication",
            "source_of_truth": "message.list and message.conversation via runtime env tools",
        },
        "comments": {
            "description": "Track collaboration comments scoped to exactly one Track.",
            "scope": "Track discussion threads",
            "source_of_truth": "track.list_comments via runtime env tools",
        },
        "writable_surfaces": {
            "description": "Runtime writable filesystem surfaces for host-visible files.",
            "scope": "read-only writable-surface facts",
            "source_of_truth": "launcher instance environment and permission profile",
            "mutates_product_state": False,
            "grants_write_authority": False,
        },
        "source_workspace": {
            "description": "Runtime product source root facts for the active role.",
            "scope": "read-only source orientation",
            "source_of_truth": "env profile project.path/access and instance workspace projection",
            "mutates_product_state": False,
            "grants_write_authority": False,
            "configures_source_root": False,
        },
    }


def get_context(*, args: dict[str, Any], context: ContextServiceContext) -> dict[str, Any]:
    action = "context.get"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_allowed_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    try:
        sections = _current_context_sections(
            active_role=active_role,
            args=args,
            instance_payload=context["instance_payload"],
            include_resolved_path=True,
            context=context,
        )
    except Exception as exc:
        return _source_workspace_rejection(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message=str(exc),
        )
    extra_sections = dict(sections)
    extra_sections.pop("current_identity", None)
    return tool_results.success(
        tool="context",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        effect_summary="Returned full runtime context sections plus source_workspace facts, writable_surfaces facts, full tool catalog, and full operation semantics.",
        state_changed=False,
        durability="none",
        read_scope="read-only runtime context sections, source workspace facts, and full catalog metadata",
        allowed_next_actions=[
            "Use task/track/artifact tools with explicit ids.",
            "Use context.summarize for compact orientation.",
        ],
        extra=extra_sections,
    )


def summarize_context(*, args: dict[str, Any], context: ContextServiceContext) -> dict[str, Any]:
    action = "context.summarize"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_allowed_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    try:
        sections = _current_context_sections(
            active_role=active_role,
            args=args,
            instance_payload=context["instance_payload"],
            include_resolved_path=False,
            context=context,
        )
    except Exception as exc:
        return _source_workspace_rejection(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message=str(exc),
        )
    summary = {
        "current_context_summary": sections["current_context_summary"],
        "source_workspace": sections["source_workspace"],
        "candidate_tracks": sections["candidate_tracks"],
        "candidate_tasks": sections["candidate_tasks"],
        "candidate_artifacts": sections["candidate_artifacts"],
        "open_comment_threads": sections["open_comment_threads"],
        "recent_updates": sections["recent_updates"],
        "message_cues": sections["message_cues"],
        "context_sources": context_sources_desc(),
        "writable_surfaces": sections["writable_surfaces"],
        "tool_affordances": tool_registry.compact_tool_affordances(),
        "capability_snapshot": sections["capability_snapshot"],
        "decision_surface": sections["decision_surface"],
    }

    return tool_results.success(
        tool="context",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        effect_summary="Returned compact context orientation with source_workspace facts, writable_surfaces facts, candidate ids, and first-pass tool affordances.",
        state_changed=False,
        durability="none",
        read_scope="compact read-only orientation with source_workspace facts; not full catalog",
        allowed_next_actions=[
            "Use explicit ids from candidate_tracks/candidate_tasks/candidate_artifacts in subsequent tool calls.",
            "Use context.get for full sections when needed.",
        ],
        extra=summary,
    )


def list_sources(*, args: dict[str, Any], context: ContextServiceContext) -> dict[str, Any]:
    action = "context.list_sources"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_allowed_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    return tool_results.success(
        tool="context",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
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
