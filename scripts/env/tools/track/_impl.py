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
    current_identity: dict[str, Any]
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
    current_identity: dict[str, Any],
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
            "now",
            "state",
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
        current_identity=current_identity,
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


def _reject_archived(*, action: str, current_identity: dict[str, Any], active_role: str, track_id: str) -> dict[str, Any]:
    message = f"track '{track_id}' is archived and cannot be used via {action}"
    return tool_results.rejection(
        tool="track",
        action=action,
        current_identity=current_identity,
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


def _reject_authority(*, action: str, current_identity: dict[str, Any], active_role: str, message: str) -> dict[str, Any]:
    return tool_results.rejection(
        tool="track",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        code="E_TRACK_AUTHORITY",
        message=message,
        permission_boundary="track.owner_identity_id",
        human_summary="Track owner authority is required.",
        why_blocked=message,
        impact="No owner-only Track state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Ask the exact Track owner identity to perform this action.",
        allowed_next_actions=["Use track.list to inspect current state."],
        correctable_fields=["current_identity"],
    )


def _reject_refs(
    *,
    action: str,
    current_identity: dict[str, Any],
    active_role: str,
    message: str,
    field_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="track",
        action=action,
        current_identity=current_identity,
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
    current_identity: dict[str, Any],
    active_role: str,
    message: str,
    correctable_fields: list[str] | None = None,
    field_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="track",
        action=action,
        current_identity=current_identity,
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
    current_identity: dict[str, Any],
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
        current_identity=current_identity,
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


def _delivery_row_from_result(target_identity: dict[str, str], result: dict[str, Any]) -> dict[str, Any]:
    status = result.get("delivery_status") if isinstance(result.get("delivery_status"), str) else "delivery_failed"
    row: dict[str, Any] = {
        "target_identity_id": target_identity["identity_id"],
        "delivery_status": status,
    }
    for key in ("handling_status", "reachability_status", "signal_error"):
        value = result.get(key)
        if isinstance(value, str):
            row[key] = value
    return row


def _delivery_metadata(results: list[dict[str, Any]]) -> dict[str, Any]:
    target_count = len(results)
    delivered_count = sum(1 for row in results if row.get("delivery_status") == "delivered")
    failed_count = target_count - delivered_count
    if target_count == 0:
        delivery_status = "no_targets"
    elif failed_count == 0:
        delivery_status = "delivered"
    elif delivered_count > 0:
        delivery_status = "partial"
    else:
        delivery_status = "failed"
    return {
        "delivery_status": delivery_status,
        "delivery_summary": {
            "target_count": target_count,
            "delivered_count": delivered_count,
            "failed_count": failed_count,
        },
        "delivery_results": results,
    }


def _deliver_track_comment_signal(
    *,
    comment: dict[str, Any],
    reply_to_comment: dict[str, Any] | None,
    identity_routes: dict[str, dict[str, str]] | None = None,
    context: TrackServiceContext,
) -> dict[str, Any]:
    payload = context.rules.track_comment.track_comment_added_payload(comment)
    targets = context.rules.track_comment.track_comment_targets(
        comment,
        reply_to_comment=reply_to_comment,
        identity_routes=identity_routes,
    )
    results: list[dict[str, Any]] = []
    for target in targets:
        try:
            result = context.signal_delivery.deliver_signal(
                signal_type="track.comment.added",
                target_identity_id=target["identity_id"],
                target_role_id=target["role_id"],
                payload={
                    "track_id": payload["track_id"],
                    "comment_id": payload["comment_id"],
                    "thread_id": payload["thread_id"],
                },
            )
            results.append(_delivery_row_from_result(target, result))
        except Exception as exc:
            results.append(
                {
                    "target_identity_id": target["identity_id"],
                    "delivery_status": "delivery_failed",
                    "handling_status": "ignored",
                    "signal_error": str(exc),
                }
            )
    return _delivery_metadata(results)


def _reject_artifact_scope(*, action: str, current_identity: dict[str, Any], active_role: str, message: str) -> dict[str, Any]:
    return tool_results.rejection(
        tool="track",
        action=action,
        current_identity=current_identity,
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


def _require_fields(action: str, args: dict[str, Any], current_identity: dict[str, Any], active_role: str) -> dict[str, Any] | None:
    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message=f"unsupported payload fields: {', '.join(unknown)}",
        )
    return None


def _require_track_id(action: str, args: dict[str, Any], current_identity: dict[str, Any], active_role: str) -> tuple[str | None, dict[str, Any] | None]:
    track_id = args.get("track_id")
    if not isinstance(track_id, str) or not track_id.strip():
        return None, _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="track_id is required")
    return track_id.strip(), None


def _identity_route_payload(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    unknown = sorted(key for key in value if key not in {"identity_id", "role_id"})
    if unknown:
        raise ValueError(f"{field} contains unsupported fields: {', '.join(unknown)}")
    identity_id = value.get("identity_id")
    role_id = value.get("role_id")
    if not isinstance(identity_id, str) or not identity_id.strip():
        raise ValueError(f"{field}.identity_id must be a non-empty string")
    if not isinstance(role_id, str) or not role_id.strip():
        raise ValueError(f"{field}.role_id must be a non-empty string")
    return {"identity_id": identity_id.strip(), "role_id": role_id.strip()}


def _active_identity_id(current_identity: dict[str, Any]) -> str | None:
    identity_id = current_identity.get("id") if isinstance(current_identity, dict) else None
    return identity_id if isinstance(identity_id, str) and identity_id else None


def _comment_author_identity_id(comment: dict[str, Any]) -> str | None:
    identity_id = comment.get("by_identity_id")
    if isinstance(identity_id, str) and identity_id:
        return identity_id
    actor = comment.get("by_identity")
    if isinstance(actor, dict) and isinstance(actor.get("actor_id"), str):
        return actor["actor_id"]
    return None


def _require_owner_identity(
    *,
    action: str,
    track: dict[str, Any],
    current_identity: dict[str, Any],
    active_role: str,
) -> dict[str, Any] | None:
    if track.get("owner_identity_id") == _active_identity_id(current_identity):
        return None
    return _reject_authority(
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        message=(
            "only the exact Track owner identity can mutate requirement facts, lifecycle, "
            "comment thread resolution, or archive state"
        ),
    )


def _normalize_text_list_payload(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    rows: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field}[{index}] must be a non-empty string")
        rows.append(item.strip())
    return rows


def _identity_routes_for_mentions(*, context: Any, current_identity: dict[str, Any], active_role: str) -> dict[str, dict[str, str]]:
    routes: dict[str, dict[str, str]] = {}
    current_identity_id = current_identity.get("id")
    active_route = None
    if isinstance(current_identity_id, str) and current_identity_id.strip():
        active_route = {"identity_id": current_identity_id.strip(), "role_id": active_role}
    if active_route is not None:
        routes[active_route["identity_id"]] = active_route

    try:
        raw = context.actor_directory.list_online_actors(role_id=None)
    except Exception:
        return routes
    rows = raw.get("actors") if isinstance(raw, dict) and isinstance(raw.get("actors"), list) else []
    for row in rows:
        try:
            route = _identity_route_payload(
                {
                    "identity_id": row.get("identity_id") if isinstance(row, dict) else None,
                    "role_id": row.get("role_id") if isinstance(row, dict) else None,
                },
                "contact.identity_route",
            )
        except ValueError:
            continue
        routes[route["identity_id"]] = route
    return routes


def _normalize_mentioned_identity_ids(
    *,
    mentioned_identity_ids: Any,
    current_identity: dict[str, Any],
    active_role: str,
    action: str,
    context: Any,
) -> tuple[list[str], dict[str, dict[str, str]]] | dict[str, Any]:
    if mentioned_identity_ids is None:
        return [], {}
    if not isinstance(mentioned_identity_ids, list):
        return _reject_track_comment_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="mentioned_identity_ids must be a list",
            correctable_fields=["mentioned_identity_ids"],
            field_errors=[
                {
                    "path": "mentioned_identity_ids",
                    "message": "mentioned_identity_ids must be a list of actor identity id strings",
                    "expected": ["act-pm-example"],
                    "example": ["act-pm-example"],
                }
            ],
        )
    resolvable_routes = _identity_routes_for_mentions(context=context, current_identity=current_identity, active_role=active_role)
    normalized: list[str] = []
    routes: dict[str, dict[str, str]] = dict(resolvable_routes)
    seen: set[str] = set()
    for index, row in enumerate(mentioned_identity_ids):
        if not isinstance(row, str) or not row.strip():
            return _reject_track_comment_payload(
                action=action,
                current_identity=current_identity,
                active_role=active_role,
                message="mentioned_identity_ids entries must be non-empty strings",
                correctable_fields=["mentioned_identity_ids"],
        )
        identity_id = row.strip()
        route = resolvable_routes.get(identity_id)
        if route is None:
            return _reject_track_comment_payload(
                action=action,
                current_identity=current_identity,
                active_role=active_role,
                message=f"mentioned_identity_ids[{index}] must be a reachable actor identity id",
                correctable_fields=["mentioned_identity_ids"],
                field_errors=[
                    {
                        "path": f"mentioned_identity_ids[{index}]",
                        "message": "actor identity id must resolve to an active actor route",
                        "example": current_identity.get("id") if isinstance(current_identity.get("id"), str) else "act-example",
                    }
                ],
            )
        if identity_id not in seen:
            seen.add(identity_id)
            normalized.append(identity_id)
            routes[identity_id] = route
    return normalized, routes


def _attachment_projection_for_ref(
    *,
    artifact_id: str,
    current_identity: dict[str, Any],
    active_role: str,
    context: TrackServiceContext,
) -> tuple[int, list[dict[str, Any]]]:
    artifact = context.repos.artifact.get_artifact(artifact_id)
    if not isinstance(artifact, dict):
        return 0, []
    decision = context.rules.artifact_visibility.artifact_read_decision(artifact, current_identity)
    if not bool(decision.get("allowed")):
        return 0, []
    attachments = context.rules.artifact_visibility.attachment_summary_rows(artifact)
    return len(attachments), attachments


def _project_track_artifact_ref(
    *,
    ref: dict[str, Any],
    current_identity: dict[str, Any],
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
        current_identity=current_identity,
        active_role=active_role,
        context=context,
    )
    projected["attachment_count"] = attachment_count
    projected["attachments"] = attachments
    return projected


def _track_comment_cues(
    *,
    track_id: str,
    current_identity: dict[str, Any],
    context: TrackServiceContext,
) -> dict[str, Any]:
    comments = context.repos.track_comment.comments_for_track(track_id)
    by_id = {row.get("id"): row for row in comments if isinstance(row.get("id"), str)}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in comments:
        thread_id = row.get("thread_id")
        if isinstance(thread_id, str) and thread_id:
            grouped.setdefault(thread_id, []).append(row)

    def _preview(row: dict[str, Any]) -> str:
        content = row.get("content")
        if not isinstance(content, str):
            return ""
        return content[:120]

    def _mentions_me(row: dict[str, Any]) -> bool:
        active_identity_id = _active_identity_id(current_identity)
        mentions = row.get("mentioned_identity_ids")
        if not isinstance(mentions, list):
            return False
        return any(item == active_identity_id for item in mentions)

    def _replies_to_me(row: dict[str, Any]) -> bool:
        reply_to = row.get("reply_to")
        if not isinstance(reply_to, str) or not reply_to:
            return False
        parent = by_id.get(reply_to)
        if not isinstance(parent, dict):
            return False
        return _comment_author_identity_id(parent) == _active_identity_id(current_identity)

    recent = sorted(
        comments,
        key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")),
        reverse=True,
    )[:3]

    open_threads: list[dict[str, Any]] = []
    for thread_id, rows in grouped.items():
        rows.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))
        statuses = {row.get("status") for row in rows}
        thread_status = "resolved" if statuses == {"resolved"} else "open"
        latest = rows[-1]
        if thread_status == "open":
            open_threads.append(
                {
                    "thread_id": thread_id,
                    "latest_comment_id": latest.get("id"),
                    "latest_comment_preview": _preview(latest),
                    "latest_by_identity_id": latest.get("by_identity_id"),
                    "comment_count": len(rows),
                    "status": thread_status,
                    "mentions_me": any(_mentions_me(row) for row in rows),
                    "replies_to_me": any(_replies_to_me(row) for row in rows),
                }
            )
    open_threads.sort(key=lambda row: (str(row.get("latest_comment_id") or ""), str(row.get("thread_id") or "")), reverse=True)

    def _cue_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "comment_id": row.get("id"),
            "thread_id": row.get("thread_id"),
            "by_identity_id": row.get("by_identity_id"),
            "status": row.get("status"),
            "created_at": row.get("created_at"),
            "preview": _preview(row),
        }

    return {
        "open_thread_count": len(open_threads),
        "recent_comments": [_cue_row(row) for row in recent],
        "open_threads": open_threads,
        "mentions_to_me": [_cue_row(row) for row in comments if _mentions_me(row)],
        "replies_to_me": [_cue_row(row) for row in comments if _replies_to_me(row)],
        "source_of_truth": "track.list_comments",
    }


def _track_page(
    track: dict[str, Any],
    *,
    active_role: str,
    context: TrackServiceContext,
) -> dict[str, Any]:
    page = dict(track)
    current_identity = context["current_identity"]
    projected_relations = [
        _project_track_artifact_ref(ref=row, current_identity=current_identity, active_role=active_role, context=context)
        for row in track.get("artifact_relations", [])
        if isinstance(row, dict)
    ]
    page["artifact_relations"] = projected_relations
    page["materials"] = [row for row in projected_relations if row.get("role") == "material"]
    page["proofs"] = [row for row in projected_relations if row.get("role") == "proof"]
    page["updates"] = [row for row in track.get("updates", []) if isinstance(row, dict)]
    track_id = track.get("id")
    if isinstance(track_id, str) and track_id:
        page["comment_cues"] = _track_comment_cues(track_id=track_id, current_identity=current_identity, context=context)
    return page


def _track_summary(track: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": track.get("id"),
        "title": track.get("title"),
        "outcome": track.get("outcome"),
        "owner_identity_id": track.get("owner_identity_id"),
        "state": track.get("state"),
        "now": track.get("now"),
        "acceptance_criteria": track.get("acceptance_criteria"),
        "non_goals": track.get("non_goals"),
        "updated_at": track.get("updated_at"),
    }


def list_tracks_for_active_role(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.list"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_fields(action, args, current_identity, active_role)
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
        current_identity=current_identity,
        active_role=active_role,
        effect_summary=f"Returned {len(payload_rows)} non-archived track page summary row(s).",
        state_changed=False,
        durability="none",
        read_scope="non-archived track page summaries",
        allowed_next_actions=[
            "Use track.open to read one track page.",
            "Use track.update_requirements, track.update_status, track.add_material, track.add_update, or track.add_proof on active tracks.",
        ],
        extra={"tracks": payload_rows},
    )


def open_track_for_active_role(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.open"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, current_identity, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track = context.repos.track.get_track(track_id)
    if track is None:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=f"track not found: {track_id}")
    if track.get("archived_at") is not None:
        return _reject_archived(action=action, current_identity=current_identity, active_role=active_role, track_id=track_id)

    page = _track_page(track, active_role=active_role, context=context)
    return tool_results.success(
        tool="track",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        effect_summary=f"Opened one shared track page '{track_id}'.",
        state_changed=False,
        durability="none",
        read_scope="one shared track page",
        allowed_next_actions=[
            "Use artifact.get with track material/proof artifact_id for full body reads.",
            "Use track.add_material/add_update/add_proof/update_requirements/update_status to update the page.",
        ],
        extra={"track_id": track_id, "track": page},
    )


def add_comment_to_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.add_comment"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, current_identity, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    _, track_error = _load_non_archived_track(action=action, current_identity=current_identity, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error

    content = args.get("content")
    if not isinstance(content, str) or not content.strip():
        return _reject_track_comment_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="content must be a non-empty string",
            correctable_fields=["content"],
        )

    reply_to = args.get("reply_to")
    if reply_to is not None and (not isinstance(reply_to, str) or not reply_to.strip()):
        return _reject_track_comment_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="reply_to must be a non-empty string when provided",
            correctable_fields=["reply_to"],
        )

    mentioned_identity_payload = _normalize_mentioned_identity_ids(
        mentioned_identity_ids=args.get("mentioned_identity_ids"),
        current_identity=current_identity,
        active_role=active_role,
        action=action,
        context=context,
    )
    if isinstance(mentioned_identity_payload, dict):
        return mentioned_identity_payload
    mentioned_identity_ids, identity_routes = mentioned_identity_payload

    reply_to_comment: dict[str, Any] | None = None
    try:
        if isinstance(reply_to, str):
            comment = context.repos.track_comment.reply_to_track_comment(
                track_id=track_id,
                reply_to=reply_to.strip(),
                by_identity=current_identity,
                content=content.strip(),
                mentioned_identities=mentioned_identity_ids,
            )
            reply_to_comment = context.repos.track_comment.get_track_comment(track_id, reply_to.strip())
        else:
            comment = context.repos.track_comment.create_track_comment(
                track_id=track_id,
                by_identity=current_identity,
                content=content.strip(),
                mentioned_identities=mentioned_identity_ids,
            )
    except ValueError as exc:
        message = str(exc)
        if "reply_to comment" in message:
            return _reject_track_comment_scope(
                action=action,
                current_identity=current_identity,
                active_role=active_role,
                code="E_TRACK_COMMENT_REPLY_SCOPE",
                boundary="track_comment.reply_to_scope",
                message=message,
                retryable=True,
                correctable_fields=["reply_to"],
            )
        return _reject_track_comment_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message=message,
        )

    delivery_metadata = _deliver_track_comment_signal(
        comment=comment,
        reply_to_comment=reply_to_comment,
        identity_routes=identity_routes,
        context=context,
    )

    return tool_results.success(
        tool="track",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        effect_summary=f"Added one durable Track comment on track '{track_id}'.",
        state_changed=True,
        durability="durable",
        created_ids=[comment["id"]],
        state_changes=[{"object_type": "track_comment", "change": "added", "track_id": track_id, "comment_id": comment["id"]}],
        allowed_next_actions=["Use track.list_comments for full discussion rows.", "Use track.add_comment to continue the thread."],
        extra={"track_id": track_id, "comment_id": comment["id"], "comment": comment, **delivery_metadata},
    )


def list_comments_on_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.list_comments"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, current_identity, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    _, track_error = _load_non_archived_track(action=action, current_identity=current_identity, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error

    status_filter = args.get("status", "all")
    if not isinstance(status_filter, str) or status_filter not in {"open", "resolved", "all"}:
        return _reject_track_comment_payload(
            action=action,
            current_identity=current_identity,
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
        current_identity=current_identity,
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
    current_identity = context["current_identity"]
    payload_error = _require_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, current_identity, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track, track_error = _load_non_archived_track(action=action, current_identity=current_identity, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error
    assert isinstance(track, dict)
    owner_error = _require_owner_identity(action=action, track=track, current_identity=current_identity, active_role=active_role)
    if owner_error is not None:
        return owner_error

    comment_id = args.get("comment_id")
    if not isinstance(comment_id, str) or not comment_id.strip():
        return _reject_track_comment_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="comment_id must be a non-empty string",
            correctable_fields=["comment_id"],
        )

    resolution_summary = args.get("resolution_summary")
    if not isinstance(resolution_summary, str) or not resolution_summary.strip():
        return _reject_track_comment_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="resolution_summary must be a non-empty string",
            correctable_fields=["resolution_summary"],
        )

    try:
        resolved_rows = context.repos.track_comment.resolve_track_comment_thread(
            track_id=track_id,
            comment_id=comment_id.strip(),
            resolved_by_identity=current_identity,
            resolution_summary=resolution_summary.strip(),
        )
    except ValueError as exc:
        message = str(exc)
        if "already resolved" in message:
            return _reject_track_comment_scope(
                action=action,
                current_identity=current_identity,
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
                current_identity=current_identity,
                active_role=active_role,
                code="E_TRACK_COMMENT_THREAD_SCOPE",
                boundary="track_comment.thread_scope",
                message=message,
                retryable=True,
                correctable_fields=["track_id", "comment_id"],
            )
        return _reject_track_comment_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message=message,
        )

    updated_ids = [row.get("id") for row in resolved_rows if isinstance(row.get("id"), str)]
    return tool_results.success(
        tool="track",
        action=action,
        current_identity=current_identity,
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


def _normalize_now_payload(
    *,
    action: str,
    value: Any,
    current_identity: dict[str, Any],
    active_role: str,
) -> dict[str, Any] | dict[str, Any]:
    if not isinstance(value, dict):
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="now must be an object with required field next and optional blocker",
            field_errors=[_now_field_error()],
        )
    if not isinstance(value.get("next"), str) or not value.get("next", "").strip():
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="now.next is required",
            field_errors=[_now_field_error()],
        )
    blocker = value.get("blocker")
    if blocker is not None and not isinstance(blocker, str):
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="now.blocker must be a string or null",
            field_errors=[_now_field_error()],
        )
    return {"next": value.get("next", "").strip(), "blocker": blocker}


def create_track_for_current_identity(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.create"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, current_identity, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    title = args.get("title")
    outcome = args.get("outcome")
    now = args.get("now")
    if not isinstance(title, str) or not title.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="title is required")
    if not isinstance(outcome, str) or not outcome.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="outcome is required")
    normalized_now = _normalize_now_payload(action=action, value=now, current_identity=current_identity, active_role=active_role)
    if isinstance(normalized_now, dict) and normalized_now.get("ok") is False:
        return normalized_now

    try:
        acceptance_criteria = _normalize_text_list_payload(args.get("acceptance_criteria", []), "acceptance_criteria")
        non_goals = _normalize_text_list_payload(args.get("non_goals", []), "non_goals")
    except ValueError as exc:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=str(exc))

    try:
        track = context.repos.track.create_track(
            track_id,
            title.strip(),
            outcome=outcome.strip(),
            owner_identity=current_identity,
            now=normalized_now,
            acceptance_criteria=acceptance_criteria,
            non_goals=non_goals,
        )
    except ValueError as exc:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=str(exc))

    return tool_results.success(
        tool="track",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        effect_summary=f"Created one active Track page '{track_id}' owned by the active actor.",
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
    current_identity: dict[str, Any],
    active_role: str,
    track_id: str,
    context: TrackServiceContext,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    track = context.repos.track.get_track(track_id)
    if track is None:
        return None, _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=f"track not found: {track_id}")
    if track.get("archived_at") is not None:
        return None, _reject_archived(action=action, current_identity=current_identity, active_role=active_role, track_id=track_id)
    return track, None


def update_requirements_for_owner(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.update_requirements"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, current_identity, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track, track_error = _load_non_archived_track(action=action, current_identity=current_identity, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error
    assert isinstance(track, dict)
    owner_error = _require_owner_identity(action=action, track=track, current_identity=current_identity, active_role=active_role)
    if owner_error is not None:
        return owner_error

    patch: dict[str, Any] = {}
    for field in ("title", "outcome"):
        if field in args:
            value = args.get(field)
            if not isinstance(value, str) or not value.strip():
                return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=f"{field} must be a non-empty string")
            patch[field] = value.strip()
    try:
        if "acceptance_criteria" in args:
            patch["acceptance_criteria"] = _normalize_text_list_payload(args.get("acceptance_criteria"), "acceptance_criteria")
        if "non_goals" in args:
            patch["non_goals"] = _normalize_text_list_payload(args.get("non_goals"), "non_goals")
    except ValueError as exc:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=str(exc))

    if not patch:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="at least one requirement field is required")

    try:
        updated = context.repos.track.update_track(track_id, patch)
    except ValueError as exc:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=str(exc))

    return tool_results.success(
        tool="track",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        effect_summary=f"Updated requirement facts on Track '{track_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[track_id],
        state_changes=[{"object_type": "track", "change": "requirements_updated", "track_id": track_id}],
        allowed_next_actions=["Use track.open to verify requirement facts."],
        extra={"track_id": track_id, "track": _track_page(updated, active_role=active_role, context=context)},
    )


def update_status_for_owner(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.update_status"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, current_identity, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track, track_error = _load_non_archived_track(action=action, current_identity=current_identity, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error
    assert isinstance(track, dict)
    owner_error = _require_owner_identity(action=action, track=track, current_identity=current_identity, active_role=active_role)
    if owner_error is not None:
        return owner_error

    state = args.get("state")
    if state not in context.repos.track.VALID_TRACK_STATE:
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message=f"state must be one of {', '.join(context.repos.track.VALID_TRACK_STATE)}",
        )
    normalized_now = _normalize_now_payload(action=action, value=args.get("now"), current_identity=current_identity, active_role=active_role)
    if isinstance(normalized_now, dict) and normalized_now.get("ok") is False:
        return normalized_now

    try:
        updated = context.repos.track.update_track(track_id, {"state": state, "now": normalized_now})
    except ValueError as exc:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=str(exc))

    return tool_results.success(
        tool="track",
        action=action,
        current_identity=current_identity,
        active_role=active_role,
        effect_summary=f"Updated owner status on Track '{track_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[track_id],
        state_changes=[{"object_type": "track", "change": "status_updated", "track_id": track_id}],
        allowed_next_actions=["Use track.open to verify state and now fields."],
        extra={"track_id": track_id, "track": _track_page(updated, active_role=active_role, context=context)},
    )


def add_material_to_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.add_material"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, current_identity, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track, track_error = _load_non_archived_track(action=action, current_identity=current_identity, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error
    assert isinstance(track, dict)

    artifact_id = args.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="artifact_id is required; create a draft via artifact.create_revision first",
        )

    label = args.get("label")
    if not isinstance(label, str) or not label.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="label is required")
    summary = args.get("summary", "")
    if not isinstance(summary, str):
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="summary must be a string")

    try:
        relation_result = context.rules.track_artifact_relations.add_material_relation(
            track_id=track_id,
            artifact_id=artifact_id.strip(),
            label=label.strip(),
            from_identity=current_identity,
            summary=summary,
        )
    except ValueError as exc:
        message = str(exc)
        if "owned by another identity" in message:
            return _reject_artifact_scope(action=action, current_identity=current_identity, active_role=active_role, message=message)
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=message)
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
        current_identity=current_identity,
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
    current_identity = context["current_identity"]
    payload_error = _require_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, current_identity, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    _, track_error = _load_non_archived_track(action=action, current_identity=current_identity, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error

    kind = "progress" if "kind" not in args else args.get("kind")
    summary = args.get("summary")
    if isinstance(kind, str):
        kind = kind.strip()
    if kind not in context.repos.track.VALID_UPDATE_KIND:
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message=f"kind must be one of {', '.join(context.repos.track.VALID_UPDATE_KIND)}",
        )
    if not isinstance(summary, str) or not summary.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="summary is required")

    refs_arg = args.get("refs", [])
    if not isinstance(refs_arg, list):
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="refs must be a list",
            field_errors=[_refs_field_error()],
        )
    refs: list[dict[str, Any]] = []
    for row in refs_arg:
        if not isinstance(row, dict) or row.get("type") != "artifact":
            return _reject_refs(
                action=action,
                current_identity=current_identity,
                active_role=active_role,
                message="refs entries must be artifact refs",
                field_errors=[_refs_field_error()],
            )
        ref_id = row.get("id")
        if not isinstance(ref_id, str) or not ref_id.strip():
            return _reject_refs(
                action=action,
                current_identity=current_identity,
                active_role=active_role,
                message="artifact ref id is required",
                field_errors=[_refs_field_error()],
            )
        normalized_ref_id = ref_id.strip()
        decision = context.rules.artifact_visibility.artifact_ref_decision_for_track_update(
            artifact_id=normalized_ref_id,
            current_identity=current_identity,
            track_id=track_id,
        )
        if not bool(decision.get("ok")):
            return _reject_refs(
                action=action,
                current_identity=current_identity,
                active_role=active_role,
                message=str(decision.get("message") or "artifact ref failed track update scope checks"),
            )
        refs.append({"type": "artifact", "id": normalized_ref_id})

    try:
        track, update = context.repos.track.append_track_update(
            track_id=track_id,
            by_identity=current_identity,
            kind=kind,
            summary=summary.strip(),
            refs=refs,
        )
    except ValueError as exc:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=str(exc))

    return tool_results.success(
        tool="track",
        action=action,
        current_identity=current_identity,
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
    current_identity = context["current_identity"]
    payload_error = _require_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, current_identity, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track, track_error = _load_non_archived_track(action=action, current_identity=current_identity, active_role=active_role, track_id=track_id, context=context)
    if track_error is not None:
        return track_error
    assert isinstance(track, dict)

    artifact_id = args.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return _reject_payload(
            action=action,
            current_identity=current_identity,
            active_role=active_role,
            message="artifact_id is required; create a draft via artifact.create_revision first",
        )

    label = args.get("label")
    if not isinstance(label, str) or not label.strip():
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="label is required")
    summary = args.get("summary", "")
    if not isinstance(summary, str):
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message="summary must be a string")

    try:
        relation_result = context.rules.track_artifact_relations.add_proof_relation(
            track_id=track_id,
            artifact_id=artifact_id.strip(),
            label=label.strip(),
            from_identity=current_identity,
            summary=summary,
        )
    except ValueError as exc:
        message = str(exc)
        if "owned by another identity" in message:
            return _reject_artifact_scope(action=action, current_identity=current_identity, active_role=active_role, message=message)
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=message)
    updated_track = relation_result["track"]
    related_artifact = relation_result["artifact"]
    superseded_artifact_id = relation_result["superseded_artifact_id"]

    changes: list[dict[str, Any]] = [
        {"object_type": "track", "change": "proof_relation_added", "track_id": track_id, "artifact_id": related_artifact["id"]},
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
        current_identity=current_identity,
        active_role=active_role,
        effect_summary=(
            f"Related artifact '{related_artifact['id']}' as current proof on track '{track_id}'."
        ),
        state_changed=True,
        durability="durable",
        updated_ids=[track_id],
        state_changes=changes,
        allowed_next_actions=[
            "Use track.open to verify proof relations.",
            "Use artifact.get to read proof body.",
            "Owner can use track.update_status to accept proof as done.",
        ],
        extra={
            "track_id": track_id,
            "artifact_id": related_artifact["id"],
            "track": _track_page(updated_track, active_role=active_role, context=context),
        },
    )


def archive_track_for_owner(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.archive"
    active_role = context["active_role"]
    current_identity = context["current_identity"]
    payload_error = _require_fields(action, args, current_identity, active_role)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, current_identity, active_role)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track = context.repos.track.get_track(track_id)
    if track is None:
        return _reject_payload(action=action, current_identity=current_identity, active_role=active_role, message=f"track not found: {track_id}")
    owner_error = _require_owner_identity(action=action, track=track, current_identity=current_identity, active_role=active_role)
    if owner_error is not None:
        return owner_error

    state_changed = False
    if track.get("archived_at") is None:
        track = context.repos.track.update_track(track_id, {"archived_at": context.repos.track.now_iso()})
        state_changed = True

    return tool_results.success(
        tool="track",
        action=action,
        current_identity=current_identity,
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
    'archive': archive_track_for_owner,
    'create': create_track_for_current_identity,
    'list': list_tracks_for_active_role,
    'list_comments': list_comments_on_track,
    'open': open_track_for_active_role,
    'resolve_comment_thread': resolve_comment_thread_on_track,
    'update_requirements': update_requirements_for_owner,
    'update_status': update_status_for_owner,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    return handler(args=args, context=context)
