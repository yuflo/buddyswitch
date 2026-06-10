#!/usr/bin/env python3
"""Track-page services for broker-routed env.tool operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

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

class TrackServiceContext(TypedDict):
    active_role: str
    actor_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


def _now_field_error() -> dict[str, Any]:
    return {
        "path": "now",
        "message": "now must be an object with required field next and optional blocker",
        "expected": {"next": "non-empty string", "blocker": "string|null"},
        "example": {"next": "Set up PM coordination.", "blocker": None},
    }


def _refs_field_error() -> dict[str, Any]:
    return {
        "path": "refs",
        "message": "refs must be a list of artifact reference objects",
        "expected": [{"type": "artifact", "id": "non-empty string"}],
        "example": [{"type": "artifact", "id": "art-example-r1"}],
    }


def _allowed(action: str) -> set[str]:
    _, action_name = action.split(".", 1)
    for row in _ACTION_DEFINITION_MAP.get("actions", []):
        if isinstance(row, dict) and row.get("name") == action_name:
            return {field for field in row.get("payload_fields", []) if isinstance(field, str)}
    return set()


def _reject_payload(
    *,
    action: str,
    active_actor: dict[str, Any],
    active_role: str,
    message: str,
    field_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    correctable_fields: list[str] | None = None
    if "unsupported payload fields:" in message:
        suffix = message.split("unsupported payload fields:", 1)[1].strip()
        if suffix:
            correctable_fields = [row.strip() for row in suffix.split(",") if row.strip()]
    else:
        for field in (
            "track_id",
            "title",
            "outcome",
            "appetite",
            "now",
            "state",
            "health",
            "kind",
            "label",
            "summary",
            "artifact_id",
            "content",
            "refs",
        ):
            if field in message:
                correctable_fields = [field]
                break
        lowered = message.lower()
        if not correctable_fields:
            if "already current material" in lowered or "already current close proof" in lowered:
                correctable_fields = ["artifact_id"]
            elif "cannot be republished" in lowered:
                correctable_fields = ["track_id"]
    return tool_results.rejection(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        code="E_TRACK_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Track request payload is invalid.",
        why_blocked=message,
        impact="No track or artifact state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix track payload fields and retry.",
        allowed_next_actions=[
            "Use track.list to inspect active tracks.",
            "Retry with only documented track payload fields.",
        ],
        correctable_fields=correctable_fields,
        field_errors=field_errors,
    )


def _reject_archived(*, action: str, active_actor: dict[str, Any], active_role: str, track_id: str) -> dict[str, Any]:
    message = f"track '{track_id}' is archived and cannot be used via {action}"
    return tool_results.rejection(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        code="E_TRACK_ARCHIVED",
        message=message,
        permission_boundary="track.lifecycle_status",
        human_summary="Archived tracks are hard collaboration boundaries.",
        why_blocked=message,
        impact="No track or artifact state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Choose a non-archived track.",
        allowed_next_actions=["Use track.list to find active tracks."],
        correctable_fields=["track_id"],
    )


def _reject_authority(*, action: str, active_actor: dict[str, Any], active_role: str, message: str) -> dict[str, Any]:
    return tool_results.rejection(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        code="E_TRACK_AUTHORITY",
        message=message,
        permission_boundary="track.lifecycle_authority",
        human_summary="Track lifecycle authority is PM-only.",
        why_blocked=message,
        impact="No lifecycle state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Retry as role 'pm'.",
        allowed_next_actions=["Use track.list to inspect current state."],
        correctable_fields=["active_role"],
    )


def _reject_refs(
    *,
    action: str,
    active_actor: dict[str, Any],
    active_role: str,
    message: str,
    field_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        code="E_TRACK_UPDATE_REFS",
        message=message,
        permission_boundary="track.update_refs",
        human_summary="Track update refs are invalid.",
        why_blocked=message,
        impact="No update row was appended.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix refs and retry.",
        allowed_next_actions=["Use track.open to inspect current material/proof artifact ids."],
        correctable_fields=["refs"],
        field_errors=field_errors or [_refs_field_error()],
    )


def _reject_track_comment_payload(
    *,
    action: str,
    active_actor: dict[str, Any],
    active_role: str,
    message: str,
    correctable_fields: list[str] | None = None,
    field_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        code="E_TRACK_COMMENT_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Track comment request payload is invalid.",
        why_blocked=message,
        impact="No Track comments were created or changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix Track comment payload fields and retry.",
        allowed_next_actions=["Use track.list_comments to inspect current Track discussion."],
        correctable_fields=correctable_fields,
        field_errors=field_errors,
    )


def _reject_track_comment_scope(
    *,
    action: str,
    active_actor: dict[str, Any],
    active_role: str,
    code: str,
    boundary: str,
    message: str,
    retryable: bool = False,
    correctable_fields: list[str] | None = None,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        code=code,
        message=message,
        permission_boundary=boundary,
        human_summary="Track comment scope denied.",
        why_blocked=message,
        impact="No Track comments were created or changed.",
        state_changed=False,
        retryable=retryable,
        retry_guidance="Fix Track comment scope and retry." if retryable else "This action cannot be retried as-is.",
        allowed_next_actions=["Use track.open or track.list_comments to verify Track comment scope first."],
        correctable_fields=correctable_fields,
    )


def _reject_artifact_scope(*, action: str, active_actor: dict[str, Any], active_role: str, message: str) -> dict[str, Any]:
    return tool_results.rejection(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        code="E_TRACK_ARTIFACT_SCOPE",
        message=message,
        permission_boundary="artifact.actor_scope",
        human_summary="Only the owner of a draft artifact can publish it.",
        why_blocked=message,
        impact="No track or artifact state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Publish an active-actor-owned draft artifact.",
        allowed_next_actions=[
            "Use artifact.create_revision to create your own draft artifact.",
            "Use track.open to inspect current shared publication refs.",
        ],
        correctable_fields=["artifact_id"],
    )


def _require_fields(action: str, args: dict[str, Any], active_actor: dict[str, Any], active_role: str) -> dict[str, Any] | None:
    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=f"unsupported payload fields: {', '.join(unknown)}",
        )
    return None


def _require_track_id(action: str, args: dict[str, Any], active_actor: dict[str, Any], active_role: str) -> tuple[str | None, dict[str, Any] | None]:
    track_id = args.get("track_id")
    if not isinstance(track_id, str) or not track_id.strip():
        return None, _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message="track_id is required")
    return track_id.strip(), None


def _manifest_roles(manifest: dict[str, Any]) -> set[str]:
    roles = manifest.get("roles")
    if isinstance(roles, dict):
        return {key for key in roles if isinstance(key, str) and key}
    if isinstance(roles, list):
        ids: set[str] = set()
        for row in roles:
            if not isinstance(row, dict):
                continue
            role_id = row.get("id")
            if isinstance(role_id, str) and role_id:
                ids.add(role_id)
        return ids
    return set()


def _actor_address_payload(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    unknown = sorted(key for key in value if key not in {"actor_id", "role_id"})
    if unknown:
        raise ValueError(f"{field} contains unsupported fields: {', '.join(unknown)}")
    actor_id = value.get("actor_id")
    role_id = value.get("role_id")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ValueError(f"{field}.actor_id must be a non-empty string")
    if not isinstance(role_id, str) or not role_id.strip():
        raise ValueError(f"{field}.role_id must be a non-empty string")
    return {"actor_id": actor_id.strip(), "role_id": role_id.strip()}


def _normalize_mentioned_actors(
    *,
    mentioned_actors: Any,
    active_actor: dict[str, Any],
    active_role: str,
    action: str,
    manifest: dict[str, Any],
) -> list[dict[str, str]] | dict[str, Any]:
    if mentioned_actors is None:
        return []
    if not isinstance(mentioned_actors, list):
        return _reject_track_comment_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="mentioned_actors must be a list",
            correctable_fields=["mentioned_actors"],
            field_errors=[
                {
                    "path": "mentioned_actors",
                    "message": "mentioned_actors must be a list of actor address payloads",
                    "expected": [{"actor_id": "act-pm-example", "role_id": "pm"}],
                    "example": [{"actor_id": "act-pm-example", "role_id": "pm"}],
                }
            ],
        )
    roles = _manifest_roles(manifest)
    normalized: list[dict[str, str]] = []
    seen_actor_ids: set[str] = set()
    for row in mentioned_actors:
        try:
            actor = _actor_address_payload(row, "mentioned_actors entry")
        except ValueError as exc:
            return _reject_track_comment_payload(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message=f"mentioned_actors entries must be actor address payloads: {exc}",
                correctable_fields=["mentioned_actors"],
            )
        role = actor["role_id"]
        if role not in roles:
            return _reject_track_comment_payload(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message=f"unknown mentioned actor role: {role}",
                correctable_fields=["mentioned_actors"],
                field_errors=[
                    {
                        "path": "mentioned_actors",
                        "message": f"unknown mentioned actor role: {role}",
                        "allowed_values": sorted(roles),
                        "example": [{"actor_id": f"act-{sorted(roles)[0]}-example", "role_id": sorted(roles)[0]}],
                    }
                ],
            )
        if actor["actor_id"] not in seen_actor_ids:
            seen_actor_ids.add(actor["actor_id"])
            normalized.append(actor)
    return normalized


def _attachment_projection_for_ref(
    *,
    artifact_id: str,
    active_actor: dict[str, Any],
    active_role: str,
    context: TrackServiceContext,
) -> tuple[int, list[dict[str, Any]]]:
    artifact = context.repos.artifact.get_artifact(artifact_id)
    if not isinstance(artifact, dict):
        return 0, []
    decision = context.rules.artifact_visibility.artifact_read_decision(artifact, active_actor)
    if not bool(decision.get("allowed")):
        return 0, []
    attachments = context.rules.artifact_visibility.attachment_summary_rows(artifact)
    return len(attachments), attachments


def _project_track_artifact_ref(
    *,
    ref: dict[str, Any],
    active_actor: dict[str, Any],
    active_role: str,
    context: TrackServiceContext,
) -> dict[str, Any]:
    projected = dict(ref)
    artifact_id = ref.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id:
        projected["attachment_count"] = 0
        projected["attachments"] = []
        return projected
    attachment_count, attachments = _attachment_projection_for_ref(
        artifact_id=artifact_id,
        active_actor=active_actor,
        active_role=active_role,
        context=context,
    )
    projected["attachment_count"] = attachment_count
    projected["attachments"] = attachments
    return projected


def _track_comment_cues(
    *,
    track_id: str,
    active_actor: dict[str, Any],
    context: TrackServiceContext,
) -> dict[str, Any]:
    comments = context.repos.track_comment.comments_for_track(track_id)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in comments:
        thread_id = row.get("thread_id")
        if isinstance(thread_id, str) and thread_id:
            grouped.setdefault(thread_id, []).append(row)

    open_thread_count = 0
    for rows in grouped.values():
        if any(row.get("status") == "open" for row in rows):
            open_thread_count += 1

    recent = sorted(
        comments,
        key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")),
        reverse=True,
    )[:3]
    active_actor_id = active_actor.get("actor_id")
    mentioned_comment_ids: list[str] = []
    for row in comments:
        mentions = row.get("mentioned_actors")
        if not isinstance(mentions, list):
            continue
        if any(isinstance(item, dict) and item.get("actor_id") == active_actor_id for item in mentions):
            comment_id = row.get("id")
            if isinstance(comment_id, str):
                mentioned_comment_ids.append(comment_id)

    return {
        "open_thread_count": open_thread_count,
        "recent_comments": [
            {
                "comment_id": row.get("id"),
                "thread_id": row.get("thread_id"),
                "by_actor": row.get("by_actor"),
                "status": row.get("status"),
                "created_at": row.get("created_at"),
            }
            for row in recent
        ],
        "mentioned_comment_ids": mentioned_comment_ids,
        "source_of_truth": "track.list_comments",
    }


def _track_page(
    track: dict[str, Any],
    *,
    active_role: str,
    context: TrackServiceContext,
) -> dict[str, Any]:
    page = dict(track)
    active_actor = context["active_actor"]
    page["artifact_relations"] = [
        _project_track_artifact_ref(ref=row, active_actor=active_actor, active_role=active_role, context=context)
        for row in track.get("artifact_relations", [])
        if isinstance(row, dict)
    ]
    page["updates"] = [row for row in track.get("updates", []) if isinstance(row, dict)]
    track_id = track.get("id")
    if isinstance(track_id, str) and track_id:
        page["comment_cues"] = _track_comment_cues(track_id=track_id, active_actor=active_actor, context=context)
    return page


def _track_summary(track: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": track.get("id"),
        "title": track.get("title"),
        "outcome": track.get("outcome"),
        "owner_role": track.get("owner_role"),
        "state": track.get("state"),
        "health": track.get("health"),
        "appetite": track.get("appetite"),
        "now": track.get("now"),
        "updated_at": track.get("updated_at"),
    }


def list_tracks_for_active_role(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.list"
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    payload_error = _require_fields(action, args, active_actor, active_role)
    if payload_error is not None:
        return payload_error

    rows = [row for row in context.repos.track.list_tracks() if row.get("archived_at") is None]
    state = args.get("state")
    if isinstance(state, str) and state.strip():
        rows = [row for row in rows if row.get("state") == state.strip()]

    limit = args.get("limit")
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]

    payload_rows = [_track_summary(row) for row in rows]
    return tool_results.success(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=f"Returned {len(payload_rows)} non-archived track page summary row(s).",
        state_changed=False,
        durability="none",
        read_scope="non-archived track page summaries",
        allowed_next_actions=[
            "Use track.open to read one track page.",
            "Use track.update_now, track.add_material, track.add_update, or track.add_proof on active tracks.",
        ],
        extra={"tracks": payload_rows},
    )


def open_track_for_active_role(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.open"
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    payload_error = _require_fields(action, args, active_actor, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, active_actor, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track = context.repos.track.get_track(track_id)
    if track is None:
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message=f"track not found: {track_id}")
    if track.get("archived_at") is not None:
        return _reject_archived(action=action, active_actor=active_actor, active_role=active_role, track_id=track_id)

    page = _track_page(track, active_role=active_role, context=context)
    return tool_results.success(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=f"Opened one shared track page '{track_id}'.",
        state_changed=False,
        durability="none",
        read_scope="one shared track page",
        allowed_next_actions=[
            "Use artifact.get with track material/proof artifact_id for full body reads.",
            "Use track.add_material/add_update/add_proof/update_now to update the page.",
        ],
        extra={"track_id": track_id, "track": page},
    )


def add_comment_to_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.add_comment"
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    payload_error = _require_fields(action, args, active_actor, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, active_actor, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    _, track_error = _load_non_archived_track(action=action, active_actor=active_actor, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error

    content = args.get("content")
    if not isinstance(content, str) or not content.strip():
        return _reject_track_comment_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="content must be a non-empty string",
            correctable_fields=["content"],
        )

    reply_to = args.get("reply_to")
    if reply_to is not None and (not isinstance(reply_to, str) or not reply_to.strip()):
        return _reject_track_comment_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="reply_to must be a non-empty string when provided",
            correctable_fields=["reply_to"],
        )

    mentioned_actors = _normalize_mentioned_actors(
        mentioned_actors=args.get("mentioned_actors"),
        active_actor=active_actor,
        active_role=active_role,
        action=action,
        manifest=context["manifest"],
    )
    if isinstance(mentioned_actors, dict):
        return mentioned_actors

    try:
        if isinstance(reply_to, str):
            comment = context.repos.track_comment.reply_to_track_comment(
                track_id=track_id,
                reply_to=reply_to.strip(),
                by_actor=active_actor,
                content=content.strip(),
                mentioned_actors=mentioned_actors,
            )
        else:
            comment = context.repos.track_comment.create_track_comment(
                track_id=track_id,
                by_actor=active_actor,
                content=content.strip(),
                mentioned_actors=mentioned_actors,
            )
    except ValueError as exc:
        message = str(exc)
        if "reply_to comment" in message:
            return _reject_track_comment_scope(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                code="E_TRACK_COMMENT_REPLY_SCOPE",
                boundary="track_comment.reply_to_scope",
                message=message,
                retryable=True,
                correctable_fields=["reply_to"],
            )
        return _reject_track_comment_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=message,
        )

    return tool_results.success(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=f"Added one durable Track comment on track '{track_id}'.",
        state_changed=True,
        durability="durable",
        created_ids=[comment["id"]],
        state_changes=[{"object_type": "track_comment", "change": "added", "track_id": track_id, "comment_id": comment["id"]}],
        allowed_next_actions=["Use track.list_comments for full discussion rows.", "Use track.add_comment to continue the thread."],
        extra={"track_id": track_id, "comment_id": comment["id"], "comment": comment},
    )


def list_comments_on_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.list_comments"
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    payload_error = _require_fields(action, args, active_actor, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, active_actor, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    _, track_error = _load_non_archived_track(action=action, active_actor=active_actor, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error

    status_filter = args.get("status", "all")
    if not isinstance(status_filter, str) or status_filter not in {"open", "resolved", "all"}:
        return _reject_track_comment_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="status must be one of open|resolved|all",
            correctable_fields=["status"],
        )

    matched = context.repos.track_comment.comments_for_track(track_id)
    if status_filter != "all":
        matched = [row for row in matched if row.get("status") == status_filter]
    matched.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))

    threads_map: dict[str, list[dict[str, Any]]] = {}
    for row in matched:
        thread_id = row.get("thread_id")
        if not isinstance(thread_id, str) or not thread_id:
            thread_id = str(row.get("id") or "")
        threads_map.setdefault(thread_id, []).append(row)

    threads: list[dict[str, Any]] = []
    open_count = 0
    resolved_count = 0
    for thread_id, rows in threads_map.items():
        rows.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))
        statuses = {row.get("status") for row in rows}
        thread_status = "resolved" if statuses == {"resolved"} else "open"
        if thread_status == "resolved":
            resolved_count += len(rows)
        else:
            open_count += len(rows)
        threads.append(
            {
                "thread_id": thread_id,
                "track_id": track_id,
                "status": thread_status,
                "comments": rows,
            }
        )
    threads.sort(key=lambda row: row.get("thread_id") or "")

    return tool_results.success(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=f"Returned {len(matched)} Track comment(s) for track '{track_id}'.",
        state_changed=False,
        durability="none",
        read_scope="Track comment threads for one Track",
        allowed_next_actions=["Use track.add_comment to continue Track discussion."],
        extra={
            "track_id": track_id,
            "comments": matched,
            "threads": threads,
            "status_counts": {"open": open_count, "resolved": resolved_count},
        },
    )


def resolve_comment_thread_on_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.resolve_comment_thread"
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    payload_error = _require_fields(action, args, active_actor, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, active_actor, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    _, track_error = _load_non_archived_track(action=action, active_actor=active_actor, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error

    comment_id = args.get("comment_id")
    if not isinstance(comment_id, str) or not comment_id.strip():
        return _reject_track_comment_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="comment_id must be a non-empty string",
            correctable_fields=["comment_id"],
        )

    resolution_summary = args.get("resolution_summary")
    if not isinstance(resolution_summary, str) or not resolution_summary.strip():
        return _reject_track_comment_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="resolution_summary must be a non-empty string",
            correctable_fields=["resolution_summary"],
        )

    try:
        resolved_rows = context.repos.track_comment.resolve_track_comment_thread(
            track_id=track_id,
            comment_id=comment_id.strip(),
            resolved_by_actor=active_actor,
            resolution_summary=resolution_summary.strip(),
        )
    except ValueError as exc:
        message = str(exc)
        if "already resolved" in message:
            return _reject_track_comment_scope(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                code="E_TRACK_COMMENT_STATE",
                boundary="track_comment.state",
                message=message,
                retryable=False,
                correctable_fields=["comment_id"],
            )
        if "different track" in message or "not found" in message:
            return _reject_track_comment_scope(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                code="E_TRACK_COMMENT_THREAD_SCOPE",
                boundary="track_comment.thread_scope",
                message=message,
                retryable=True,
                correctable_fields=["track_id", "comment_id"],
            )
        return _reject_track_comment_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=message,
        )

    updated_ids = [row.get("id") for row in resolved_rows if isinstance(row.get("id"), str)]
    return tool_results.success(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=f"Resolved Track comment thread containing comment '{comment_id.strip()}' with {len(updated_ids)} durable row update(s).",
        state_changed=True,
        durability="durable",
        updated_ids=updated_ids,
        state_changes=[
            {"object_type": "track_comment", "change": "resolved", "track_id": track_id, "comment_id": row_id}
            for row_id in updated_ids
        ],
        allowed_next_actions=[
            "Use track.list_comments with status='resolved' to verify closure output.",
            "Use track.add_comment to open new Track discussion if unresolved issues remain.",
        ],
        extra={"track_id": track_id, "comment_id": comment_id.strip(), "comments": resolved_rows},
    )


def create_track_for_pm(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.create"
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    payload_error = _require_fields(action, args, active_actor, active_role)
    if payload_error is not None:
        return payload_error
    if active_role != "pm":
        return _reject_authority(action=action, active_actor=active_actor, active_role=active_role, message="only pm can create tracks")

    track_id, error = _require_track_id(action, args, active_actor, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    title = args.get("title")
    outcome = args.get("outcome")
    appetite = args.get("appetite")
    now = args.get("now")
    if not isinstance(title, str) or not title.strip():
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message="title is required")
    if not isinstance(outcome, str) or not outcome.strip():
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message="outcome is required")
    if not isinstance(appetite, str) or not appetite.strip():
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message="appetite is required")
    if not isinstance(now, dict):
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="now must be an object with required field next and optional blocker",
            field_errors=[_now_field_error()],
        )
    if not isinstance(now.get("next"), str) or not now.get("next", "").strip():
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="now.next is required",
            field_errors=[_now_field_error()],
        )
    blocker = now.get("blocker")
    if blocker is not None and not isinstance(blocker, str):
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="now.blocker must be a string or null",
            field_errors=[_now_field_error()],
        )

    state = args.get("state", "active")
    health = args.get("health", "ok")
    if state not in context.repos.track.VALID_TRACK_STATE:
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=f"state must be one of {', '.join(context.repos.track.VALID_TRACK_STATE)}",
        )
    if health not in context.repos.track.VALID_TRACK_HEALTH:
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=f"health must be one of {', '.join(context.repos.track.VALID_TRACK_HEALTH)}",
        )

    try:
        track = context.repos.track.create_track(
            track_id,
            title.strip(),
            owner_role="pm",
            created_by_actor=active_actor,
            outcome=outcome.strip(),
            appetite=appetite.strip(),
            now=now,
            state=state,
            health=health,
        )
    except ValueError as exc:
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message=str(exc))

    return tool_results.success(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=f"Created one PM-owned track page '{track_id}'.",
        state_changed=True,
        durability="durable",
        created_ids=[track_id],
        state_changes=[{"object_type": "track", "change": "created", "track_id": track_id}],
        allowed_next_actions=[
            "Use artifact.create_revision to create draft content.",
            "Use track.add_material to publish first shared artifact.",
            "Use track.open to verify page contents.",
        ],
        extra={"track_id": track_id, "track": _track_page(track, active_role=active_role, context=context)},
    )


def _load_non_archived_track(
    *,
    action: str,
    active_actor: dict[str, Any],
    active_role: str,
    track_id: str,
    context: TrackServiceContext,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    track = context.repos.track.get_track(track_id)
    if track is None:
        return None, _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message=f"track not found: {track_id}")
    if track.get("archived_at") is not None:
        return None, _reject_archived(action=action, active_actor=active_actor, active_role=active_role, track_id=track_id)
    return track, None


def update_now_for_active_role(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.update_now"
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    payload_error = _require_fields(action, args, active_actor, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, active_actor, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track, track_error = _load_non_archived_track(action=action, active_actor=active_actor, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error
    assert isinstance(track, dict)

    patch: dict[str, Any] = {}
    if "state" in args:
        state = args.get("state")
        if state not in context.repos.track.VALID_TRACK_STATE:
            return _reject_payload(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message=f"state must be one of {', '.join(context.repos.track.VALID_TRACK_STATE)}",
            )
        patch["state"] = state
    if "health" in args:
        health = args.get("health")
        if health not in context.repos.track.VALID_TRACK_HEALTH:
            return _reject_payload(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message=f"health must be one of {', '.join(context.repos.track.VALID_TRACK_HEALTH)}",
            )
        patch["health"] = health
    if "now" in args:
        now_value = args.get("now")
        if not isinstance(now_value, dict):
            return _reject_payload(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message="now must be an object with required field next and optional blocker",
                field_errors=[_now_field_error()],
            )
        if not isinstance(now_value.get("next"), str) or not now_value.get("next", "").strip():
            return _reject_payload(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message="now.next is required",
                field_errors=[_now_field_error()],
            )
        blocker = now_value.get("blocker")
        if blocker is not None and not isinstance(blocker, str):
            return _reject_payload(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message="now.blocker must be a string or null",
                field_errors=[_now_field_error()],
            )
        patch["now"] = now_value

    if not patch:
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message="at least one of now/state/health is required")

    try:
        updated = context.repos.track.update_track(track_id, patch)
    except ValueError as exc:
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message=str(exc))

    summary = f"{active_role} updated now-state"
    context.repos.track.append_track_update(
        track_id=track_id,
        by_actor=active_actor,
        kind="progress",
        summary=summary,
        refs=[],
    )
    updated = context.repos.track.get_track(track_id)
    assert isinstance(updated, dict)

    return tool_results.success(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=f"Updated now/state/health on non-archived track '{track_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[track_id],
        state_changes=[{"object_type": "track", "change": "updated", "track_id": track_id}],
        allowed_next_actions=["Use track.open to verify now-state and timeline updates."],
        extra={"track_id": track_id, "track": _track_page(updated, active_role=active_role, context=context)},
    )


def add_material_to_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.add_material"
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    payload_error = _require_fields(action, args, active_actor, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, active_actor, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track, track_error = _load_non_archived_track(action=action, active_actor=active_actor, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error
    assert isinstance(track, dict)

    artifact_id = args.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="artifact_id is required; create a draft via artifact.create_revision first",
        )

    label = args.get("label")
    if not isinstance(label, str) or not label.strip():
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message="label is required")
    summary = args.get("summary", "")
    if not isinstance(summary, str):
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message="summary must be a string")

    try:
        relation_result = context.rules.track_artifact_relations.add_material_relation(
            track_id=track_id,
            artifact_id=artifact_id.strip(),
            label=label.strip(),
            from_actor=active_actor,
            summary=summary,
        )
    except ValueError as exc:
        message = str(exc)
        if "owned by another actor" in message:
            return _reject_artifact_scope(action=action, active_actor=active_actor, active_role=active_role, message=message)
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message=message)
    updated_track = relation_result["track"]
    related_artifact = relation_result["artifact"]
    superseded_artifact_id = relation_result["superseded_artifact_id"]

    changes: list[dict[str, Any]] = [
        {"object_type": "track", "change": "material_relation_added", "track_id": track_id, "artifact_id": related_artifact["id"]},
    ]
    if isinstance(superseded_artifact_id, str) and superseded_artifact_id:
        changes.append(
            {
                "object_type": "track",
                "change": "material_relation_superseded",
                "artifact_id": superseded_artifact_id,
                "track_id": track_id,
            }
        )

    return tool_results.success(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=(
            f"Related artifact '{related_artifact['id']}' as current material on track '{track_id}'."
        ),
        state_changed=True,
        durability="durable",
        updated_ids=[track_id],
        state_changes=changes,
        allowed_next_actions=[
            "Use track.open to inspect artifact relations.",
            "Use artifact.get to read full artifact body.",
        ],
        extra={
            "track_id": track_id,
            "artifact_id": related_artifact["id"],
            "track": _track_page(updated_track, active_role=active_role, context=context),
        },
    )


def add_update_to_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.add_update"
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    payload_error = _require_fields(action, args, active_actor, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, active_actor, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    _, track_error = _load_non_archived_track(action=action, active_actor=active_actor, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error

    kind = "progress" if "kind" not in args else args.get("kind")
    summary = args.get("summary")
    if isinstance(kind, str):
        kind = kind.strip()
    if kind not in context.repos.track.VALID_UPDATE_KIND:
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message=f"kind must be one of {', '.join(context.repos.track.VALID_UPDATE_KIND)}",
        )
    if not isinstance(summary, str) or not summary.strip():
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message="summary is required")

    refs_arg = args.get("refs", [])
    if not isinstance(refs_arg, list):
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="refs must be a list",
            field_errors=[_refs_field_error()],
        )
    refs: list[dict[str, Any]] = []
    for row in refs_arg:
        if not isinstance(row, dict) or row.get("type") != "artifact":
            return _reject_refs(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message="refs entries must be artifact refs",
                field_errors=[_refs_field_error()],
            )
        ref_id = row.get("id")
        if not isinstance(ref_id, str) or not ref_id.strip():
            return _reject_refs(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message="artifact ref id is required",
                field_errors=[_refs_field_error()],
            )
        normalized_ref_id = ref_id.strip()
        decision = context.rules.artifact_visibility.artifact_ref_decision_for_track_update(
            artifact_id=normalized_ref_id,
            active_actor=active_actor,
            track_id=track_id,
        )
        if not bool(decision.get("ok")):
            return _reject_refs(
                action=action,
                active_actor=active_actor,
                active_role=active_role,
                message=str(decision.get("message") or "artifact ref failed track update scope checks"),
            )
        refs.append({"type": "artifact", "id": normalized_ref_id})

    try:
        track, update = context.repos.track.append_track_update(
            track_id=track_id,
            by_actor=active_actor,
            kind=kind,
            summary=summary.strip(),
            refs=refs,
        )
    except ValueError as exc:
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message=str(exc))

    return tool_results.success(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=f"Added one '{kind}' update to track '{track_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[track_id],
        state_changes=[{"object_type": "track", "change": "update_added", "track_id": track_id, "update_id": update["id"]}],
        allowed_next_actions=["Use track.open to inspect timeline updates."],
        extra={"track_id": track_id, "update": update, "track": _track_page(track, active_role=active_role, context=context)},
    )


def add_proof_to_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.add_proof"
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    payload_error = _require_fields(action, args, active_actor, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, active_actor, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track, track_error = _load_non_archived_track(action=action, active_actor=active_actor, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error
    assert isinstance(track, dict)

    artifact_id = args.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return _reject_payload(
            action=action,
            active_actor=active_actor,
            active_role=active_role,
            message="artifact_id is required; create a draft via artifact.create_revision first",
        )

    label = args.get("label")
    if not isinstance(label, str) or not label.strip():
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message="label is required")
    summary = args.get("summary", "")
    if not isinstance(summary, str):
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message="summary must be a string")

    try:
        relation_result = context.rules.track_artifact_relations.add_proof_relation(
            track_id=track_id,
            artifact_id=artifact_id.strip(),
            label=label.strip(),
            from_actor=active_actor,
            summary=summary,
            update_summary=summary or f"{active_role} published proof",
        )
    except ValueError as exc:
        message = str(exc)
        if "owned by another actor" in message:
            return _reject_artifact_scope(action=action, active_actor=active_actor, active_role=active_role, message=message)
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message=message)
    updated_track = relation_result["track"]
    related_artifact = relation_result["artifact"]
    superseded_artifact_id = relation_result["superseded_artifact_id"]
    update = relation_result["update"]

    changes: list[dict[str, Any]] = [
        {"object_type": "track", "change": "proof_relation_added", "track_id": track_id, "artifact_id": related_artifact["id"]},
        {"object_type": "track", "change": "update_added", "track_id": track_id, "update_id": update["id"]},
    ]
    if isinstance(superseded_artifact_id, str) and superseded_artifact_id:
        changes.append(
            {
                "object_type": "track",
                "change": "proof_relation_superseded",
                "artifact_id": superseded_artifact_id,
                "track_id": track_id,
            }
        )

    return tool_results.success(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=(
            f"Related artifact '{related_artifact['id']}' as current proof on track '{track_id}' "
            f"and recorded proof update '{update['id']}'."
        ),
        state_changed=True,
        durability="durable",
        updated_ids=[track_id],
        state_changes=changes,
        allowed_next_actions=[
            "Use track.open to verify artifact relations and timeline updates.",
            "Use artifact.get to read proof body.",
            "Use track.update_now when proof changes track close readiness.",
        ],
        extra={
            "track_id": track_id,
            "artifact_id": related_artifact["id"],
            "update_id": update["id"],
            "track": _track_page(updated_track, active_role=active_role, context=context),
        },
    )


def archive_track_for_pm(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.archive"
    active_role = context["active_role"]
    active_actor = context["active_actor"]
    payload_error = _require_fields(action, args, active_actor, active_role)
    if payload_error is not None:
        return payload_error
    if active_role != "pm":
        return _reject_authority(action=action, active_actor=active_actor, active_role=active_role, message="only pm can archive tracks")

    track_id, error = _require_track_id(action, args, active_actor, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track = context.repos.track.get_track(track_id)
    if track is None:
        return _reject_payload(action=action, active_actor=active_actor, active_role=active_role, message=f"track not found: {track_id}")

    state_changed = False
    if track.get("archived_at") is None:
        track = context.repos.track.update_track(track_id, {"archived_at": context.repos.track.now_iso()})
        state_changed = True

    return tool_results.success(
        tool="track",
        action=action,
        active_actor=active_actor,
        active_role=active_role,
        effect_summary=(
            f"Archived track '{track_id}'." if state_changed else f"Track '{track_id}' was already archived."
        ),
        state_changed=state_changed,
        durability="durable",
        updated_ids=[track_id],
        state_changes=[{"object_type": "track", "change": "archived", "track_id": track_id}] if state_changed else [],
        allowed_next_actions=["Use track.list to continue with non-archived tracks."],
        extra={"track_id": track_id, "track": _track_page(track, active_role=active_role, context=context)},
    )


_ACTION_HANDLERS = {
    'add_comment': add_comment_to_track,
    'add_material': add_material_to_track,
    'add_proof': add_proof_to_track,
    'add_update': add_update_to_track,
    'archive': archive_track_for_pm,
    'create': create_track_for_pm,
    'list': list_tracks_for_active_role,
    'list_comments': list_comments_on_track,
    'open': open_track_for_active_role,
    'resolve_comment_thread': resolve_comment_thread_on_track,
    'update_now': update_now_for_active_role,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    return handler(args=args, context=context)
