#!/usr/bin/env python3
"""Track-page services for broker-routed env.tool operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.services import artifact_visibility
from env.tools import responses as tool_responses


class TrackServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


_LIST_FIELDS = {"state", "limit"}
_OPEN_FIELDS = {"track_id"}
_CREATE_FIELDS = {"track_id", "title", "outcome", "appetite", "now", "state", "health"}
_UPDATE_NOW_FIELDS = {"track_id", "now", "state", "health", "owner_buddy"}
_ADD_MATERIAL_FIELDS = {"track_id", "artifact_id", "title", "kind", "label", "summary", "content", "source_refs"}
_ADD_UPDATE_FIELDS = {"track_id", "summary", "kind", "refs", "owner_buddy"}
_ADD_PROOF_FIELDS = {"track_id", "artifact_id", "title", "kind", "label", "summary", "content", "source_refs"}
_ARCHIVE_FIELDS = {"track_id"}


def _allowed(action: str) -> set[str]:
    if action == "track.list":
        return _LIST_FIELDS
    if action == "track.open":
        return _OPEN_FIELDS
    if action == "track.create":
        return _CREATE_FIELDS
    if action == "track.update_now":
        return _UPDATE_NOW_FIELDS
    if action == "track.add_material":
        return _ADD_MATERIAL_FIELDS
    if action == "track.add_update":
        return _ADD_UPDATE_FIELDS
    if action == "track.add_proof":
        return _ADD_PROOF_FIELDS
    if action == "track.archive":
        return _ARCHIVE_FIELDS
    return set()


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
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
    return tool_responses.rejection(
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
    )


def _reject_archived(*, action: str, active_buddy: str, track_id: str) -> dict[str, Any]:
    message = f"track '{track_id}' is archived and cannot be used via {action}"
    return tool_responses.rejection(
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
    return tool_responses.rejection(
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


def _reject_refs(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return tool_responses.rejection(
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


def _track_page(track: dict[str, Any]) -> dict[str, Any]:
    page = dict(track)
    page["shared_materials"] = [
        row for row in track.get("shared_materials", []) if isinstance(row, dict) and bool(row.get("current"))
    ]
    page["updates"] = [row for row in track.get("updates", []) if isinstance(row, dict)]
    page["close_proof"] = [row for row in track.get("close_proof", []) if isinstance(row, dict)]
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

    rows = [row for row in env_store.list_tracks() if row.get("archived_at") is None]
    state = args.get("state")
    if isinstance(state, str) and state.strip():
        rows = [row for row in rows if row.get("state") == state.strip()]

    limit = args.get("limit")
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]

    payload_rows = [_track_summary(row) for row in rows]
    return tool_responses.success(
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

    track = env_store.get_track(track_id)
    if track is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"track not found: {track_id}")
    if track.get("archived_at") is not None:
        return _reject_archived(action=action, active_buddy=active_buddy, track_id=track_id)

    page = _track_page(track)
    return tool_responses.success(
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

    if "owner_buddy" in args:
        return _reject_payload(action=action, active_buddy=active_buddy, message="owner_buddy is immutable and cannot be patched")

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
        return _reject_payload(action=action, active_buddy=active_buddy, message="now is required")

    state = args.get("state", "active")
    health = args.get("health", "ok")
    if state not in env_store.VALID_TRACK_STATE:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"state must be one of {', '.join(env_store.VALID_TRACK_STATE)}",
        )
    if health not in env_store.VALID_TRACK_HEALTH:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"health must be one of {', '.join(env_store.VALID_TRACK_HEALTH)}",
        )

    try:
        track = env_store.create_track(
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

    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Created one PM-owned track page '{track_id}'.",
        state_changed=True,
        durability="durable",
        created_ids=[track_id],
        state_changes=[{"object_type": "track", "change": "created", "track_id": track_id}],
        allowed_next_actions=[
            "Use track.add_material to publish first shared artifact.",
            "Use track.open to verify page contents.",
        ],
        extra={"track_id": track_id, "track": _track_page(track)},
    )


def _load_non_archived_track(*, action: str, active_buddy: str, track_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    track = env_store.get_track(track_id)
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

    if "owner_buddy" in args:
        return _reject_payload(action=action, active_buddy=active_buddy, message="owner_buddy is immutable and cannot be patched")

    track_id, error = _require_track_id(action, args, active_buddy)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    track, track_error = _load_non_archived_track(action=action, active_buddy=active_buddy, track_id=track_id)
    if track_error is not None:
        return track_error
    assert isinstance(track, dict)

    patch: dict[str, Any] = {}
    if "state" in args:
        state = args.get("state")
        if state not in env_store.VALID_TRACK_STATE:
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message=f"state must be one of {', '.join(env_store.VALID_TRACK_STATE)}",
            )
        patch["state"] = state
    if "health" in args:
        health = args.get("health")
        if health not in env_store.VALID_TRACK_HEALTH:
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message=f"health must be one of {', '.join(env_store.VALID_TRACK_HEALTH)}",
            )
        patch["health"] = health
    if "now" in args:
        if not isinstance(args.get("now"), dict):
            return _reject_payload(action=action, active_buddy=active_buddy, message="now must be an object")
        patch["now"] = args.get("now")

    if not patch:
        return _reject_payload(action=action, active_buddy=active_buddy, message="at least one of now/state/health is required")

    try:
        updated = env_store.update_track(track_id, patch)
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    summary = f"{active_buddy} updated now-state"
    env_store.append_track_update(
        track_id=track_id,
        by_buddy=active_buddy,
        kind="progress",
        summary=summary,
        refs=[],
    )
    updated = env_store.get_track(track_id)
    assert isinstance(updated, dict)

    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Updated now/state/health on non-archived track '{track_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[track_id],
        state_changes=[{"object_type": "track", "change": "updated", "track_id": track_id}],
        allowed_next_actions=["Use track.open to verify now-state and timeline updates."],
        extra={"track_id": track_id, "track": _track_page(updated)},
    )


def _create_material_artifact(
    *,
    active_buddy: str,
    args: dict[str, Any],
    action: str,
    track_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    artifact_id = args.get("artifact_id")
    if isinstance(artifact_id, str) and artifact_id.strip():
        artifact = env_store.get_artifact(artifact_id.strip())
        if artifact is None:
            return None, _reject_payload(action=action, active_buddy=active_buddy, message=f"artifact not found: {artifact_id.strip()}")
        if artifact.get("created_by") != active_buddy:
            return None, tool_responses.rejection(
                tool="track",
                action=action,
                active_buddy=active_buddy,
                code="E_TRACK_ARTIFACT_SCOPE",
                message=f"artifact '{artifact_id.strip()}' is owned by buddy '{artifact.get('created_by')}'",
                permission_boundary="artifact.buddy_scope",
                human_summary="Only the owner can publish an existing draft artifact.",
                why_blocked="artifact ownership mismatch",
                impact="No publication occurred.",
                state_changed=False,
                retryable=False,
                retry_guidance="Retry with an active-buddy-owned draft artifact.",
                allowed_next_actions=["Use artifact.create_revision to create your own draft first."],
                correctable_fields=["artifact_id"],
            )
        published_to_track = artifact.get("published_to_track")
        if published_to_track is not None:
            if not isinstance(published_to_track, str) or not published_to_track.strip():
                return None, _reject_payload(
                    action=action,
                    active_buddy=active_buddy,
                    message=f"artifact '{artifact_id.strip()}' has invalid published_to_track and cannot be republished",
                )
            if published_to_track != track_id:
                return None, _reject_payload(
                    action=action,
                    active_buddy=active_buddy,
                    message=(
                        f"artifact '{artifact_id.strip()}' is already published to track '{published_to_track}' "
                        f"and cannot be republished to '{track_id}'"
                    ),
                )
        return artifact, None

    title = args.get("title")
    kind = args.get("kind")
    summary = args.get("summary", "")
    content = args.get("content")
    if not isinstance(title, str) or not title.strip():
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="title is required when artifact_id is omitted")
    if not isinstance(kind, str) or not kind.strip():
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="kind is required when artifact_id is omitted")
    if not isinstance(summary, str):
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")
    if not isinstance(content, dict):
        return None, _reject_payload(action=action, active_buddy=active_buddy, message="content must be a JSON object")

    try:
        artifact = env_store.create_artifact(
            artifact_id=None,
            title=title.strip(),
            kind=kind.strip(),
            created_by=active_buddy,
            summary=summary,
            content=content,
            source_refs=args.get("source_refs") if isinstance(args.get("source_refs"), list) else None,
        )
    except ValueError as exc:
        return None, _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))
    return artifact, None


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

    _, track_error = _load_non_archived_track(action=action, active_buddy=active_buddy, track_id=track_id)
    if track_error is not None:
        return track_error

    label = args.get("label")
    if not isinstance(label, str) or not label.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="label is required")

    artifact, artifact_error = _create_material_artifact(
        active_buddy=active_buddy,
        args=args,
        action=action,
        track_id=track_id,
    )
    if artifact_error is not None:
        return artifact_error
    assert isinstance(artifact, dict)

    summary = args.get("summary", artifact.get("summary", ""))
    if not isinstance(summary, str):
        return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")

    try:
        track, artifact, state_changed = env_store.publish_track_material(
            track_id=track_id,
            artifact_id=str(artifact["id"]),
            label=label.strip(),
            from_buddy=active_buddy,
            summary=summary,
        )
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=(
            f"Published material artifact '{artifact['id']}' to track '{track_id}'."
            if state_changed
            else f"Artifact '{artifact['id']}' was already published as current material on track '{track_id}'."
        ),
        state_changed=state_changed,
        durability="durable",
        updated_ids=[track_id, artifact["id"]] if state_changed else [],
        state_changes=(
            [
                {"object_type": "artifact", "change": "published_material", "artifact_id": artifact["id"], "track_id": track_id},
                {"object_type": "track", "change": "material_added", "track_id": track_id},
            ]
            if state_changed
            else []
        ),
        allowed_next_actions=[
            "Use track.open to inspect current shared materials.",
            "Use artifact.get to read full artifact body.",
        ],
        extra={"track_id": track_id, "artifact_id": artifact["id"], "track": _track_page(track)},
    )


def add_update_to_track(*, args: dict[str, Any], context: TrackServiceContext) -> dict[str, Any]:
    action = "track.add_update"
    active_buddy = context["active_buddy"]
    payload_error = _require_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    if "owner_buddy" in args:
        return _reject_payload(action=action, active_buddy=active_buddy, message="owner_buddy is immutable and cannot be patched")

    track_id, error = _require_track_id(action, args, active_buddy)
    if error is not None:
        return error
    assert isinstance(track_id, str)

    _, track_error = _load_non_archived_track(action=action, active_buddy=active_buddy, track_id=track_id)
    if track_error is not None:
        return track_error

    kind = args.get("kind")
    summary = args.get("summary")
    if kind not in env_store.VALID_UPDATE_KIND:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"kind must be one of {', '.join(env_store.VALID_UPDATE_KIND)}",
        )
    if not isinstance(summary, str) or not summary.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="summary is required")

    refs_arg = args.get("refs", [])
    if not isinstance(refs_arg, list):
        return _reject_payload(action=action, active_buddy=active_buddy, message="refs must be a list")
    refs: list[dict[str, Any]] = []
    for row in refs_arg:
        if not isinstance(row, dict) or row.get("type") != "artifact":
            return _reject_refs(action=action, active_buddy=active_buddy, message="refs entries must be artifact refs")
        ref_id = row.get("id")
        if not isinstance(ref_id, str) or not ref_id.strip():
            return _reject_refs(action=action, active_buddy=active_buddy, message="artifact ref id is required")
        artifact = env_store.get_artifact(ref_id.strip())
        if artifact is None:
            return _reject_refs(action=action, active_buddy=active_buddy, message=f"artifact not found: {ref_id.strip()}")
        decision = artifact_visibility.artifact_read_decision(artifact, active_buddy)
        if not bool(decision.get("allowed")):
            why = str(decision.get("why") or "artifact is not readable for track updates")
            return _reject_refs(
                action=action,
                active_buddy=active_buddy,
                message=f"artifact '{ref_id.strip()}' cannot be used in refs: {why}",
            )
        if decision.get("track_id") != track_id:
            return _reject_refs(
                action=action,
                active_buddy=active_buddy,
                message=(
                    f"artifact '{ref_id.strip()}' belongs to track '{decision.get('track_id')}' "
                    f"and cannot be referenced from track '{track_id}'"
                ),
            )
        if decision.get("relation") not in {"track_material", "track_proof"}:
            return _reject_refs(
                action=action,
                active_buddy=active_buddy,
                message=f"artifact '{ref_id.strip()}' is not a current material or close proof on track '{track_id}'",
            )
        refs.append({"type": "artifact", "id": ref_id.strip()})

    try:
        track, update = env_store.append_track_update(
            track_id=track_id,
            by_buddy=active_buddy,
            kind=kind,
            summary=summary.strip(),
            refs=refs,
        )
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Added one '{kind}' update to track '{track_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[track_id],
        state_changes=[{"object_type": "track", "change": "update_added", "track_id": track_id, "update_id": update["id"]}],
        allowed_next_actions=["Use track.open to inspect timeline updates."],
        extra={"track_id": track_id, "update": update, "track": _track_page(track)},
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

    _, track_error = _load_non_archived_track(action=action, active_buddy=active_buddy, track_id=track_id)
    if track_error is not None:
        return track_error

    label = args.get("label")
    if not isinstance(label, str) or not label.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="label is required")

    artifact, artifact_error = _create_material_artifact(
        active_buddy=active_buddy,
        args=args,
        action=action,
        track_id=track_id,
    )
    if artifact_error is not None:
        return artifact_error
    assert isinstance(artifact, dict)

    summary = args.get("summary", artifact.get("summary", ""))
    if not isinstance(summary, str):
        return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a string")

    try:
        track, artifact, state_changed = env_store.publish_track_proof(
            track_id=track_id,
            artifact_id=str(artifact["id"]),
            label=label.strip(),
            from_buddy=active_buddy,
            summary=summary,
        )
        update: dict[str, Any] | None = None
        if state_changed:
            track, update = env_store.append_track_update(
                track_id=track_id,
                by_buddy=active_buddy,
                kind="proof",
                summary=summary or f"{active_buddy} published proof",
                refs=[{"type": "artifact", "id": artifact["id"]}],
            )
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_responses.success(
        tool="track",
        action=action,
        active_buddy=active_buddy,
        effect_summary=(
            f"Published proof artifact '{artifact['id']}' to track '{track_id}'."
            if state_changed
            else f"Artifact '{artifact['id']}' was already published as proof on track '{track_id}'."
        ),
        state_changed=state_changed,
        durability="durable",
        updated_ids=[track_id, artifact["id"]] if state_changed else [],
        state_changes=(
            [
                {"object_type": "artifact", "change": "published_proof", "artifact_id": artifact["id"], "track_id": track_id},
                {"object_type": "track", "change": "proof_added", "track_id": track_id, "update_id": update["id"] if isinstance(update, dict) else None},
            ]
            if state_changed
            else []
        ),
        allowed_next_actions=["Use track.open to verify close_proof and proof updates."],
        extra={"track_id": track_id, "artifact_id": artifact["id"], "track": _track_page(track)},
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

    track = env_store.get_track(track_id)
    if track is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"track not found: {track_id}")

    state_changed = False
    if track.get("archived_at") is None:
        track = env_store.update_track(track_id, {"archived_at": env_store.now_iso()})
        state_changed = True

    return tool_responses.success(
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
        extra={"track_id": track_id, "track": _track_page(track)},
    )
