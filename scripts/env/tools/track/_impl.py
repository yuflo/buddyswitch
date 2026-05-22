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
    active_buddy: str
    instance_id: str
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
    active_buddy: str,
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
        active_buddy=active_buddy,
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


def _reject_archived(*, action: str, active_buddy: str, track_id: str) -> dict[str, Any]:
    message = f"track '{track_id}' is archived and cannot be used via {action}"
    return tool_results.rejection(
        tool="track",
        action=action,
        active_buddy=active_buddy,
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


def _reject_authority(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return tool_results.rejection(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        code="E_TRACK_AUTHORITY",
        message=message,
        permission_boundary="track.lifecycle_authority",
        human_summary="Track lifecycle authority is PM-only.",
        why_blocked=message,
        impact="No lifecycle state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Retry as buddy 'pm'.",
        allowed_next_actions=["Use track.list to inspect current state."],
        correctable_fields=["active_buddy"],
    )


def _reject_refs(
    *,
    action: str,
    active_buddy: str,
    message: str,
    field_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return tool_results.rejection(
        tool="track",
        action=action,
        active_buddy=active_buddy,
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


def _reject_artifact_scope(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return tool_results.rejection(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        code="E_TRACK_ARTIFACT_SCOPE",
        message=message,
        permission_boundary="artifact.buddy_scope",
        human_summary="Only the owner of a draft artifact can publish it.",
        why_blocked=message,
        impact="No track or artifact state changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Publish an active-buddy-owned draft artifact.",
        allowed_next_actions=[
            "Use artifact.create_revision to create your own draft artifact.",
            "Use track.open to inspect current shared publication refs.",
        ],
        correctable_fields=["artifact_id"],
    )


def _require_fields(action: str, args: dict[str, Any], active_buddy: str) -> dict[str, Any] | None:
    unknown = sorted(key for key in args if key not in _allowed(action))
    if unknown:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"unsupported payload fields: {', '.join(unknown)}",
        )
    return None


def _require_track_id(action: str, args: dict[str, Any], active_buddy: str) -> tuple[str | None, dict[str, Any] | None]:
    track_id = args.get("track_id")
    if not isinstance(track_id, str) or not track_id.strip():
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="track_id is required")
    return track_id.strip(), None


def _attachment_projection_for_ref(
    *,
    artifact_id: str,
    active_buddy: str,
    context: TrackServiceContext,
) -> tuple[int, list[dict[str, Any]]]:
    artifact = context.repos.artifact.get_artifact(artifact_id)
    if not isinstance(artifact, dict):
        return 0, []
    decision = context.rules.artifact_visibility.artifact_read_decision(artifact, active_buddy)
    if not bool(decision.get("allowed")):
        return 0, []
    attachments = context.rules.artifact_visibility.attachment_summary_rows(artifact)
    return len(attachments), attachments


def _project_track_artifact_ref(
    *,
    ref: dict[str, Any],
    active_buddy: str,
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
        active_buddy=active_buddy,
        context=context,
    )
    projected["attachment_count"] = attachment_count
    projected["attachments"] = attachments
    return projected


def _track_page(
    track: dict[str, Any],
    *,
    active_buddy: str,
    context: TrackServiceContext,
) -> dict[str, Any]:
    page = dict(track)
    page["shared_materials"] = [
        _project_track_artifact_ref(ref=row, active_buddy=active_buddy, context=context)
        for row in track.get("shared_materials", [])
        if isinstance(row, dict) and bool(row.get("current"))
    ]
    page["updates"] = [row for row in track.get("updates", []) if isinstance(row, dict)]
    page["close_proof"] = [
        _project_track_artifact_ref(ref=row, active_buddy=active_buddy, context=context)
        for row in track.get("close_proof", [])
        if isinstance(row, dict) and bool(row.get("current", True))
    ]
    return page


def _track_summary(track: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": track.get("id"),
        "title": track.get("title"),
        "outcome": track.get("outcome"),
        "owner_buddy": track.get("owner_buddy"),
        "state": track.get("state"),
        "health": track.get("health"),
        "appetite": track.get("appetite"),
        "now": track.get("now"),
        "updated_at": track.get("updated_at"),
    }


def list_tracks_for_active_buddy(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.list"
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
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
        active_buddy=active_buddy,
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


def open_track_for_active_buddy(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.open"
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, active_buddy)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track = context.repos.track.get_track(track_id)
    if track is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"track not found: {track_id}")
    if track.get("archived_at") is not None:
        return _reject_archived(action=action, active_buddy=active_buddy, track_id=track_id)

    page = _track_page(track, active_buddy=active_buddy, context=context)
    return tool_results.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
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


def create_track_for_pm(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.create"
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error
    if active_buddy != "pm":
        return _reject_authority(action=action, active_buddy=active_buddy, message="only pm can create tracks")

    track_id, error = _require_track_id(action, args, active_buddy)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    title = args.get("title")
    outcome = args.get("outcome")
    appetite = args.get("appetite")
    now = args.get("now")
    if not isinstance(title, str) or not title.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="title is required")
    if not isinstance(outcome, str) or not outcome.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="outcome is required")
    if not isinstance(appetite, str) or not appetite.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="appetite is required")
    if not isinstance(now, dict):
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="now must be an object with required field next and optional blocker",
            field_errors=[_now_field_error()],
        )
    if not isinstance(now.get("next"), str) or not now.get("next", "").strip():
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="now.next is required",
            field_errors=[_now_field_error()],
        )
    blocker = now.get("blocker")
    if blocker is not None and not isinstance(blocker, str):
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="now.blocker must be a string or null",
            field_errors=[_now_field_error()],
        )

    state = args.get("state", "active")
    health = args.get("health", "ok")
    if state not in context.repos.track.VALID_TRACK_STATE:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"state must be one of {', '.join(context.repos.track.VALID_TRACK_STATE)}",
        )
    if health not in context.repos.track.VALID_TRACK_HEALTH:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"health must be one of {', '.join(context.repos.track.VALID_TRACK_HEALTH)}",
        )

    try:
        track = context.repos.track.create_track(
            track_id,
            title.strip(),
            owner_buddy="pm",
            outcome=outcome.strip(),
            appetite=appetite.strip(),
            now=now,
            state=state,
            health=health,
        )
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_results.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
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
        extra={"track_id": track_id, "track": _track_page(track, active_buddy=active_buddy, context=context)},
    )


def _load_non_archived_track(
    *,
    action: str,
    active_buddy: str,
    track_id: str,
    context: TrackServiceContext,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    track = context.repos.track.get_track(track_id)
    if track is None:
        return None, _reject_payload(action=action, active_buddy=active_buddy, message=f"track not found: {track_id}")
    if track.get("archived_at") is not None:
        return None, _reject_archived(action=action, active_buddy=active_buddy, track_id=track_id)
    return track, None


def update_now_for_active_buddy(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.update_now"
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, active_buddy)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track, track_error = _load_non_archived_track(action=action, active_buddy=active_buddy, track_id=track_id, context=context)
    if track_error is not None:
        return track_error
    assert isinstance(track, dict)

    patch: dict[str, Any] = {}
    if "state" in args:
        state = args.get("state")
        if state not in context.repos.track.VALID_TRACK_STATE:
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message=f"state must be one of {', '.join(context.repos.track.VALID_TRACK_STATE)}",
            )
        patch["state"] = state
    if "health" in args:
        health = args.get("health")
        if health not in context.repos.track.VALID_TRACK_HEALTH:
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message=f"health must be one of {', '.join(context.repos.track.VALID_TRACK_HEALTH)}",
            )
        patch["health"] = health
    if "now" in args:
        now_value = args.get("now")
        if not isinstance(now_value, dict):
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message="now must be an object with required field next and optional blocker",
                field_errors=[_now_field_error()],
            )
        if not isinstance(now_value.get("next"), str) or not now_value.get("next", "").strip():
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message="now.next is required",
                field_errors=[_now_field_error()],
            )
        blocker = now_value.get("blocker")
        if blocker is not None and not isinstance(blocker, str):
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message="now.blocker must be a string or null",
                field_errors=[_now_field_error()],
            )
        patch["now"] = now_value

    if not patch:
        return _reject_payload(action=action, active_buddy=active_buddy, message="at least one of now/state/health is required")

    try:
        updated = context.repos.track.update_track(track_id, patch)
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    summary = f"{active_buddy} updated now-state"
    context.repos.track.append_track_update(
        track_id=track_id,
        by_buddy=active_buddy,
        kind="progress",
        summary=summary,
        refs=[],
    )
    updated = context.repos.track.get_track(track_id)
    assert isinstance(updated, dict)

    return tool_results.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Updated now/state/health on non-archived track '{track_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[track_id],
        state_changes=[{"object_type": "track", "change": "updated", "track_id": track_id}],
        allowed_next_actions=["Use track.open to verify now-state and timeline updates."],
        extra={"track_id": track_id, "track": _track_page(updated, active_buddy=active_buddy, context=context)},
    )


def add_material_to_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.add_material"
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, active_buddy)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track, track_error = _load_non_archived_track(action=action, active_buddy=active_buddy, track_id=track_id, context=context)
    if track_error is not None:
        return track_error
    assert isinstance(track, dict)

    artifact_id = args.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="artifact_id is required; create a draft via artifact.create_revision first",
        )

    label = args.get("label")
    if not isinstance(label, str) or not label.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="label is required")
    summary = args.get("summary", "")
    if not isinstance(summary, str):
        return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")

    try:
        publication = context.rules.publication.publish_material(
            track_id=track_id,
            artifact_id=artifact_id.strip(),
            label=label.strip(),
            from_buddy=active_buddy,
            summary=summary,
        )
    except ValueError as exc:
        message = str(exc)
        if "is owned by buddy" in message:
            return _reject_artifact_scope(action=action, active_buddy=active_buddy, message=message)
        return _reject_payload(action=action, active_buddy=active_buddy, message=message)
    updated_track = publication["track"]
    updated_artifact = publication["artifact"]
    superseded_artifact_id = publication["superseded_artifact_id"]

    changes: list[dict[str, Any]] = [
        {"object_type": "artifact", "change": "published_material", "artifact_id": updated_artifact["id"], "track_id": track_id},
        {"object_type": "track", "change": "material_added", "track_id": track_id, "artifact_id": updated_artifact["id"]},
    ]
    if isinstance(superseded_artifact_id, str) and superseded_artifact_id:
        changes.append(
            {
                "object_type": "artifact",
                "change": "superseded",
                "artifact_id": superseded_artifact_id,
                "track_id": track_id,
            }
        )

    return tool_results.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=(
            f"Published artifact '{updated_artifact['id']}' as current shared material on track '{track_id}' "
            f"and appended the track material ref."
        ),
        state_changed=True,
        durability="durable",
        updated_ids=[track_id, updated_artifact["id"]],
        state_changes=changes,
        allowed_next_actions=[
            "Use track.open to inspect current shared materials.",
            "Use artifact.get to read full artifact body.",
        ],
        extra={
            "track_id": track_id,
            "artifact_id": updated_artifact["id"],
            "track": _track_page(updated_track, active_buddy=active_buddy, context=context),
        },
    )


def add_update_to_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.add_update"
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, active_buddy)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    _, track_error = _load_non_archived_track(action=action, active_buddy=active_buddy, track_id=track_id, context=context)
    if track_error is not None:
        return track_error

    kind = "progress" if "kind" not in args else args.get("kind")
    summary = args.get("summary")
    if isinstance(kind, str):
        kind = kind.strip()
    if kind not in context.repos.track.VALID_UPDATE_KIND:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"kind must be one of {', '.join(context.repos.track.VALID_UPDATE_KIND)}",
        )
    if not isinstance(summary, str) or not summary.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="summary is required")

    refs_arg = args.get("refs", [])
    if not isinstance(refs_arg, list):
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="refs must be a list",
            field_errors=[_refs_field_error()],
        )
    refs: list[dict[str, Any]] = []
    for row in refs_arg:
        if not isinstance(row, dict) or row.get("type") != "artifact":
            return _reject_refs(
                action=action,
                active_buddy=active_buddy,
                message="refs entries must be artifact refs",
                field_errors=[_refs_field_error()],
            )
        ref_id = row.get("id")
        if not isinstance(ref_id, str) or not ref_id.strip():
            return _reject_refs(
                action=action,
                active_buddy=active_buddy,
                message="artifact ref id is required",
                field_errors=[_refs_field_error()],
            )
        normalized_ref_id = ref_id.strip()
        decision = context.rules.artifact_visibility.artifact_ref_decision_for_track_update(
            artifact_id=normalized_ref_id,
            active_buddy=active_buddy,
            track_id=track_id,
        )
        if not bool(decision.get("ok")):
            return _reject_refs(
                action=action,
                active_buddy=active_buddy,
                message=str(decision.get("message") or "artifact ref failed track update scope checks"),
            )
        refs.append({"type": "artifact", "id": normalized_ref_id})

    try:
        track, update = context.repos.track.append_track_update(
            track_id=track_id,
            by_buddy=active_buddy,
            kind=kind,
            summary=summary.strip(),
            refs=refs,
        )
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_results.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Added one '{kind}' update to track '{track_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[track_id],
        state_changes=[{"object_type": "track", "change": "update_added", "track_id": track_id, "update_id": update["id"]}],
        allowed_next_actions=["Use track.open to inspect timeline updates."],
        extra={"track_id": track_id, "update": update, "track": _track_page(track, active_buddy=active_buddy, context=context)},
    )


def add_proof_to_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.add_proof"
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    track_id, error = _require_track_id(action, args, active_buddy)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track, track_error = _load_non_archived_track(action=action, active_buddy=active_buddy, track_id=track_id, context=context)
    if track_error is not None:
        return track_error
    assert isinstance(track, dict)

    artifact_id = args.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="artifact_id is required; create a draft via artifact.create_revision first",
        )

    label = args.get("label")
    if not isinstance(label, str) or not label.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="label is required")
    summary = args.get("summary", "")
    if not isinstance(summary, str):
        return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")

    try:
        publication = context.rules.publication.publish_proof(
            track_id=track_id,
            artifact_id=artifact_id.strip(),
            label=label.strip(),
            from_buddy=active_buddy,
            summary=summary,
            update_summary=summary or f"{active_buddy} published proof",
        )
    except ValueError as exc:
        message = str(exc)
        if "is owned by buddy" in message:
            return _reject_artifact_scope(action=action, active_buddy=active_buddy, message=message)
        return _reject_payload(action=action, active_buddy=active_buddy, message=message)
    updated_track = publication["track"]
    updated_artifact = publication["artifact"]
    superseded_artifact_id = publication["superseded_artifact_id"]
    update = publication["update"]

    changes: list[dict[str, Any]] = [
        {"object_type": "artifact", "change": "published_proof", "artifact_id": updated_artifact["id"], "track_id": track_id},
        {"object_type": "track", "change": "proof_added", "track_id": track_id, "artifact_id": updated_artifact["id"]},
        {"object_type": "track", "change": "update_added", "track_id": track_id, "update_id": update["id"]},
    ]
    if isinstance(superseded_artifact_id, str) and superseded_artifact_id:
        changes.append(
            {
                "object_type": "artifact",
                "change": "superseded",
                "artifact_id": superseded_artifact_id,
                "track_id": track_id,
            }
        )

    return tool_results.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=(
            f"Published artifact '{updated_artifact['id']}' as current close proof on track '{track_id}', "
            f"appended close_proof ref, and recorded proof update '{update['id']}'."
        ),
        state_changed=True,
        durability="durable",
        updated_ids=[track_id, updated_artifact["id"]],
        state_changes=changes,
        allowed_next_actions=[
            "Use track.open to verify close_proof and timeline updates.",
            "Use artifact.get to read proof body.",
            "Use track.update_now when proof changes track close readiness.",
        ],
        extra={
            "track_id": track_id,
            "artifact_id": updated_artifact["id"],
            "update_id": update["id"],
            "track": _track_page(updated_track, active_buddy=active_buddy, context=context),
        },
    )


def archive_track_for_pm(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.archive"
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error
    if active_buddy != "pm":
        return _reject_authority(action=action, active_buddy=active_buddy, message="only pm can archive tracks")

    track_id, error = _require_track_id(action, args, active_buddy)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track = context.repos.track.get_track(track_id)
    if track is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"track not found: {track_id}")

    state_changed = False
    if track.get("archived_at") is None:
        track = context.repos.track.update_track(track_id, {"archived_at": context.repos.track.now_iso()})
        state_changed = True

    return tool_results.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=(
            f"Archived track '{track_id}'." if state_changed else f"Track '{track_id}' was already archived."
        ),
        state_changed=state_changed,
        durability="durable",
        updated_ids=[track_id],
        state_changes=[{"object_type": "track", "change": "archived", "track_id": track_id}] if state_changed else [],
        allowed_next_actions=["Use track.list to continue with non-archived tracks."],
        extra={"track_id": track_id, "track": _track_page(track, active_buddy=active_buddy, context=context)},
    )


_ACTION_HANDLERS = {
    'add_material': add_material_to_track,
    'add_proof': add_proof_to_track,
    'add_update': add_update_to_track,
    'archive': archive_track_for_pm,
    'create': create_track_for_pm,
    'list': list_tracks_for_active_buddy,
    'open': open_track_for_active_buddy,
    'update_now': update_now_for_active_buddy,
}


def invoke(*, action: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"unsupported action: {action}")
    return handler(args=args, context=context)
