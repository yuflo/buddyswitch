#!/usr/bin/env python3
"""Run reservation and audit-only commit service for broker-routed runtime operations."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, TypedDict

import env_profiles
import env_store
from env_manifest import DEFAULT_MANIFEST, load_manifest, require_buddy
from env.services import handoffs as handoff_service
from env.services import track_relations
from env.tools import responses as tool_responses


class RunServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]
    manifest_path: Path | None


def _runtime() -> Any:
    import turn_runtime

    return turn_runtime


def _write_runtime_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=True, indent=2) + os.linesep
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        handle.write(serialized)
        temp_name = handle.name
    os.replace(temp_name, path)


def reserved_run_path(run_id: str) -> Path:
    return env_store.CONTENT_ROOT / "runs" / "reserved" / f"{run_id}.json"


def _normalize_turn_identity(turn_identity: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(turn_identity, dict):
        raise ValueError("turn_identity payload is required")
    return {
        "instance_id": turn_identity.get("instance_id"),
        "active_buddy": turn_identity.get("active_buddy"),
        "request_text": turn_identity.get("request_text"),
        "task_id": turn_identity.get("task_id"),
        "track_id": turn_identity.get("track_id"),
        "context_revision": turn_identity.get("context_revision"),
        "sequence": turn_identity.get("sequence"),
        "run_id": turn_identity.get("run_id"),
    }


def find_active_task_reservation(task_id: str | None) -> dict[str, Any] | None:
    if task_id is None:
        return None
    reserved_dir = reserved_run_path("placeholder").parent
    if not reserved_dir.exists():
        return None
    for path in sorted(reserved_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"run reservation is invalid: {path.name}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"run reservation is invalid: {path.name}")
        if payload.get("status") != "reserved":
            continue
        if payload.get("task_id") == task_id:
            return payload
    return None


def save_run_reservation(
    *,
    run_id: str,
    context_revision: str,
    sequence: int,
    task_id: str | None,
    turn_identity: dict[str, Any],
    instance_id: str | None,
) -> None:
    env_store.require_runtime_workspace_write_root()
    if instance_id is not None and task_id is not None:
        existing = find_active_task_reservation(task_id)
        if existing is not None:
            existing_run_id = existing.get("run_id")
            existing_instance_id = existing.get("instance_id")
            raise ValueError(
                f"Task '{task_id}' already has an active run reservation"
                f" '{existing_run_id}' for instance '{existing_instance_id or 'unknown'}'."
            )
    reservation = {
        "run_id": run_id,
        "status": "reserved",
        "context_revision": context_revision,
        "sequence": sequence,
        "task_id": task_id,
        "turn_identity": _normalize_turn_identity(turn_identity),
        "reserved_at": env_store.now_iso(),
    }
    if instance_id is not None:
        reservation["instance_id"] = instance_id
    _write_runtime_json(reserved_run_path(run_id), reservation)


def load_run_reservation(run_id: str) -> dict[str, Any]:
    path = reserved_run_path(run_id)
    if not path.exists():
        raise ValueError(f"run reservation not found: {run_id}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"run reservation is invalid: {run_id}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"run reservation is invalid: {run_id}")
    if payload.get("status") != "reserved":
        raise ValueError(f"run reservation is invalid: {run_id}")
    return payload


def clear_run_reservation(run_id: str) -> dict[str, Any] | None:
    path = reserved_run_path(run_id)
    try:
        if path.exists():
            path.unlink()
    except OSError as exc:
        return {
            "code": "W_RUN_RESERVATION_CLEAR_FAILED",
            "message": f"run reservation could not be cleared: {exc}",
            "run_id": run_id,
            "reservation_path": str(path),
        }
    return None


def _track_object_path(track_id: str) -> str:
    return f"buddyswitch/objects/tracks/{track_id}.json"


def _task_object_path(task_id: str) -> str:
    return f"buddyswitch/objects/tasks/{task_id}.json"


def _artifact_object_path(artifact_id: str) -> str:
    return f"buddyswitch/objects/artifacts/{artifact_id}.json"


def _build_next_state(
    *,
    task_id: str | None,
    track_id: str | None,
    current_buddy: str,
    next_buddy: str | None,
) -> dict[str, Any]:
    resolved_next_buddy = next_buddy if isinstance(next_buddy, str) and next_buddy.strip() else None
    if resolved_next_buddy and resolved_next_buddy != current_buddy:
        mode = "handoff"
    elif task_id:
        mode = "task_associated"
    elif track_id:
        mode = "track_associated"
    else:
        mode = "taskless_audit"
    return {
        "task_id": task_id,
        "track_id": track_id,
        "current_buddy": current_buddy,
        "next_buddy": resolved_next_buddy,
        "mode": mode,
    }


def _receipt_paths(
    *,
    run_content_path_value: str,
    task_id: str | None,
    artifact_ids: list[str],
    track_id: str | None,
) -> dict[str, Any]:
    paths: dict[str, Any] = {"run": run_content_path_value}
    if isinstance(task_id, str):
        paths["task"] = _task_object_path(task_id)
    if artifact_ids:
        paths["artifacts"] = [_artifact_object_path(item) for item in artifact_ids]
    if isinstance(track_id, str):
        paths["track"] = _track_object_path(track_id)
    return paths


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{label} must contain non-empty strings")
        cleaned.append(item.strip())
    return cleaned


def _known_buddy_ids(manifest: dict[str, Any]) -> set[str]:
    return {
        buddy.get("id")
        for buddy in manifest.get("buddies", [])
        if isinstance(buddy, dict) and isinstance(buddy.get("id"), str)
    }


def _non_empty_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    return candidate if candidate else None


def _handoff_target_from_args(handoff_args: dict[str, Any]) -> str | None:
    target = _non_empty_str(handoff_args.get("target_buddy"))
    if target is not None:
        return target
    return _non_empty_str(handoff_args.get("next_buddy"))


def _reject_retired_persist_fields(*, rt: Any, result: dict[str, Any]) -> None:
    if "skill_id" in result:
        rt._raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "top-level skill_id is retired; record skills under contributors.skills.",
            permission_boundary="persist.skill_id",
            allowed_next_actions=[
                "Move skill identifiers to contributors.skills before retrying run.commit.",
            ],
        )
    if "state_effects" in result:
        rt._raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "state_effects lifecycle writes are retired; use env.tool task/track actions.",
            permission_boundary="persist.state_effects",
            allowed_next_actions=[
                "python3 scripts/env/client.py task update --payload <json-file>",
                "python3 scripts/env/client.py track update --payload <json-file>",
                "python3 scripts/env/client.py track advance --payload <json-file>",
                "python3 scripts/env/client.py track join --track-id <track-id>",
            ],
        )
    if "artifacts" in result:
        rt._raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "embedded artifacts are retired; create revisions through artifact-tool first.",
            permission_boundary="persist.artifacts",
            allowed_next_actions=[
                "python3 scripts/env/client.py artifact create-revision --payload <json-file>",
            ],
        )


def _validate_association_metadata(
    *,
    rt: Any,
    result: dict[str, Any],
    active_buddy: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    task_id = result.get("task_id")
    if task_id is not None and (not isinstance(task_id, str) or not task_id.strip()):
        raise ValueError("task_id must be a non-empty string when provided")
    track_id = result.get("track_id")
    if track_id is not None and (not isinstance(track_id, str) or not track_id.strip()):
        raise ValueError("track_id must be a non-empty string when provided")

    task: dict[str, Any] | None = None
    if isinstance(task_id, str):
        normalized_task_id = env_store.require_id(task_id.strip(), "task id")
        task = env_store.get_task(normalized_task_id)
        if task is None:
            rt._raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                f"task not found: {normalized_task_id}",
                permission_boundary="persist.task_id",
                allowed_next_actions=["Use task.list to inspect active-buddy tasks before associating task_id."],
            )
        if task.get("buddy") != active_buddy:
            rt._raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                f"task belongs to buddy '{task.get('buddy')}', not active buddy '{active_buddy}'",
                permission_boundary="task.buddy_scope",
                allowed_next_actions=["Use a task owned by the active buddy."],
            )

    track: dict[str, Any] | None = None
    if isinstance(track_id, str):
        normalized_track_id = env_store.require_id(track_id.strip(), "track id")
        track = env_store.get_track(normalized_track_id)
        if track is None:
            rt._raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                f"track not found: {normalized_track_id}",
                permission_boundary="persist.track_id",
                allowed_next_actions=["Use track.list to inspect valid track ids before associating track_id."],
            )

    artifact_ids_raw = result.get("artifact_ids", [])
    if artifact_ids_raw is None:
        artifact_ids_raw = []
    if not isinstance(artifact_ids_raw, list):
        raise ValueError("artifact_ids must be a list when provided")
    artifact_ids: list[str] = []
    seen: set[str] = set()
    for item in artifact_ids_raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("artifact_ids must contain non-empty strings")
        artifact_id = env_store.require_id(item.strip(), "artifact id")
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        artifact = env_store.get_artifact(artifact_id)
        if artifact is None:
            track_hint = (
                f"python3 scripts/env/client.py artifact list --track-id {track['id']}"
                if isinstance(track, dict) and isinstance(track.get("id"), str)
                else None
            )
            task_hint = (
                f"python3 scripts/env/client.py task get --task-id {task['id']}"
                if isinstance(task, dict) and isinstance(task.get("id"), str)
                else None
            )
            hints = [hint for hint in (track_hint, task_hint) if isinstance(hint, str)]
            if not hints:
                hints = ["python3 scripts/env/client.py track list"]
            rt._raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                f"artifact not found: {artifact_id}",
                permission_boundary="persist.artifact_ids",
                allowed_next_actions=hints,
            )
        artifact_task_id = artifact.get("task_id")
        if not isinstance(artifact_task_id, str) or not artifact_task_id:
            rt._raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                f"artifact is missing task ownership: {artifact_id}",
                permission_boundary="artifact.ownership",
                allowed_next_actions=["Use artifact.create_revision to write broker-owned artifacts."],
            )
        owner_task = env_store.get_task(artifact_task_id)
        if owner_task is None:
            rt._raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                f"artifact task owner not found: {artifact_task_id}",
                permission_boundary="artifact.ownership",
                allowed_next_actions=["Repair task ownership before associating artifact ids."],
            )
        if owner_task.get("buddy") != active_buddy:
            rt._raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                f"artifact '{artifact_id}' belongs to task owned by '{owner_task.get('buddy')}', not '{active_buddy}'",
                permission_boundary="artifact.buddy_scope",
                allowed_next_actions=["Associate artifacts owned by tasks of the active buddy only."],
            )
        if task is not None and artifact_task_id != task["id"]:
            rt._raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                f"artifact '{artifact_id}' does not belong to associated task '{task['id']}'",
                permission_boundary="persist.artifact_ids",
                allowed_next_actions=["Use artifact ids that belong to the associated task_id."],
            )
        artifact_ids.append(artifact_id)

    return task, track, artifact_ids


def _validate_run_context_and_reservation(*, rt: Any, context: dict[str, Any]) -> dict[str, Any]:
    validated = rt._validate_prepared_run_context(context)
    run_id = validated["run_id"]
    rt._assert_run_id_unused(run_id)
    reservation = load_run_reservation(run_id)

    if reservation.get("context_revision") != validated["context_revision"]:
        raise ValueError("run reservation mismatch: context_revision differs from reserved envelope")
    if reservation.get("sequence") != validated["sequence"]:
        raise ValueError("run reservation mismatch: sequence differs from reserved envelope")
    if reservation.get("task_id") != validated["task_id"]:
        raise ValueError("run reservation mismatch: task_id differs from reserved envelope")
    reservation_turn_identity = reservation.get("turn_identity")
    if not isinstance(reservation_turn_identity, dict):
        raise ValueError("run reservation mismatch: turn_identity payload is missing")
    if _normalize_turn_identity(reservation_turn_identity) != _normalize_turn_identity(validated["turn_identity"]):
        raise ValueError("run reservation mismatch: turn_identity differs from reserved envelope")
    reservation_instance_id = reservation.get("instance_id")
    if isinstance(reservation_instance_id, str) and reservation_instance_id:
        if validated.get("instance_id") != reservation_instance_id:
            raise ValueError("run reservation mismatch: instance differs from reserved envelope")
    return validated


def _normalize_commit(
    context: dict[str, Any],
    *,
    result: dict[str, Any],
    manifest_path: Path,
) -> dict[str, Any]:
    rt = _runtime()
    if not context.get("ok"):
        raise ValueError("context payload must be successful before run.commit")
    if not isinstance(result, dict):
        raise ValueError("result payload must be a JSON object")

    validated_context = _validate_run_context_and_reservation(rt=rt, context=context)
    active_buddy = validated_context.get("active_buddy")
    if not isinstance(active_buddy, str) or not active_buddy.strip():
        raise ValueError("active_buddy is required")
    active_buddy = active_buddy.strip()

    request_text = validated_context.get("request_text")
    if not isinstance(request_text, str) or not request_text.strip():
        raise ValueError("request_text is required")

    manifest = load_manifest(manifest_path)
    require_buddy(manifest, active_buddy)
    env_profile = env_profiles.require_env_profile(
        active_buddy,
        manifest_path=manifest_path,
        repo_root=rt.REPO_ROOT,
    )

    _reject_retired_persist_fields(rt=rt, result=result)

    execution_summary = result.get("execution_summary")
    if not isinstance(execution_summary, str) or not execution_summary.strip():
        rt._raise_runtime_feedback(
            "E_RUNTIME_PERSIST",
            "execution_summary must be a non-empty string",
            permission_boundary="persist.execution_summary",
            allowed_next_actions=[
                "Provide execution_summary with a short durable summary for this run.",
            ],
        )

    working_notes = result.get("working_notes")
    normalized_working_notes = [] if working_notes is None else _require_string_list(working_notes, "working_notes")

    task, track, artifact_ids = _validate_association_metadata(
        rt=rt,
        result=result,
        active_buddy=active_buddy,
    )

    handoff = result.get("handoff")
    normalized_handoff: dict[str, Any] | None = None
    if handoff is not None:
        if not isinstance(handoff, dict):
            raise ValueError("handoff must be an object when provided")
        handoff_args = dict(handoff)
        if "track_id" not in handoff_args and isinstance(track, dict):
            handoff_args["track_id"] = track.get("id")
        if "source_task_id" not in handoff_args and isinstance(task, dict):
            handoff_args["source_task_id"] = task.get("id")
        if "source_run_id" not in handoff_args:
            handoff_args["source_run_id"] = validated_context.get("run_id")
        if "artifact_ids" not in handoff_args and artifact_ids:
            handoff_args["artifact_ids"] = list(artifact_ids)
        if "historical_artifact_ids" not in handoff_args:
            handoff_args["historical_artifact_ids"] = []

        target_buddy = _handoff_target_from_args(handoff_args)
        reason = _non_empty_str(handoff_args.get("reason"))
        handoff_context_text = _non_empty_str(handoff_args.get("context"))
        if target_buddy is None:
            rt._raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                "handoff.next_buddy (or handoff.target_buddy) is required",
                permission_boundary="persist.handoff",
                allowed_next_actions=[
                    "Provide handoff.next_buddy and handoff.reason/context in result.handoff.",
                ],
            )
        if reason is None or handoff_context_text is None:
            rt._raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                "handoff.reason and handoff.context must be non-empty strings",
                permission_boundary="persist.handoff",
                allowed_next_actions=[
                    "Provide handoff.reason and handoff.context as non-empty strings.",
                ],
            )
        known_buddies = _known_buddy_ids(manifest)
        if target_buddy not in known_buddies:
            rt._raise_runtime_feedback(
                "E_RUNTIME_PERSIST",
                f"target_buddy must reference a manifest buddy id; got '{target_buddy}'",
                permission_boundary="manifest.buddies",
                allowed_next_actions=[
                    "Use one of the manifest buddy ids as target_buddy/next_buddy.",
                ],
            )

        has_track = _non_empty_str(handoff_args.get("track_id")) is not None
        has_source_task = _non_empty_str(handoff_args.get("source_task_id")) is not None
        has_artifacts = isinstance(handoff_args.get("artifact_ids"), list) and bool(handoff_args.get("artifact_ids"))
        strict_handoff_payload = has_track and has_source_task and has_artifacts

        # Preserve legacy audit-only handoff shape when strict source linkage cannot be inferred.
        if not strict_handoff_payload:
            normalized_handoff = {
                "next_buddy": target_buddy,
                "reason": reason,
                "context": handoff_context_text,
            }
        else:
            handoff_context: handoff_service.HandoffServiceContext = {
                "active_buddy": active_buddy,
                "instance_id": str(validated_context.get("instance_id") or ""),
                "instance_json": Path(validated_context.get("instance_json") or "."),
                "instance_payload": {
                    "current_task_id": task.get("id") if isinstance(task, dict) else None,
                    "current_track_id": track.get("id") if isinstance(track, dict) else None,
                },
                "manifest": manifest,
            }
            normalized_handoff, handoff_error = handoff_service._validate_handoff_payload(
                args=handoff_args,
                context=handoff_context,
                action="run.validate_result",
                mutate=False,
            )
            if handoff_error is not None:
                error_row = handoff_error.get("error") if isinstance(handoff_error.get("error"), dict) else {}
                message = str(error_row.get("message") or "handoff validation failed")
                boundary = str(handoff_error.get("permission_boundary") or "persist.handoff")
                if boundary == "request-payload":
                    boundary = "persist.handoff"
                rt._raise_runtime_feedback(
                    "E_RUNTIME_PERSIST",
                    message,
                    permission_boundary=boundary,
                    allowed_next_actions=list(handoff_error.get("allowed_next_actions") or []),
                )
            assert isinstance(normalized_handoff, dict)

    contributors = result.get("contributors")
    normalized_contributors = {"skills": [], "agents": []}
    if contributors is not None:
        if not isinstance(contributors, dict):
            raise ValueError("contributors must be an object")
        if "skills" in contributors:
            normalized_contributors["skills"] = _require_string_list(contributors.get("skills"), "contributors.skills")
        if "agents" in contributors:
            normalized_contributors["agents"] = _require_string_list(contributors.get("agents"), "contributors.agents")

    normalized_tool_evidence = rt._validate_market_tool_evidence(
        context=context,
        result=result,
        env_profile=env_profile,
        active_buddy=active_buddy,
    )

    return {
        "validated_context": validated_context,
        "active_buddy": active_buddy,
        "request_text": request_text,
        "run_id": validated_context["run_id"],
        "context_revision": validated_context["context_revision"],
        "instance_id": validated_context["instance_id"],
        "task": task,
        "track": track,
        "artifact_ids": artifact_ids,
        "execution_summary": execution_summary.strip(),
        "working_notes": normalized_working_notes,
        "handoff": normalized_handoff,
        "contributors": normalized_contributors,
        "tool_evidence": normalized_tool_evidence,
    }


def _canonical_result_hash(result: dict[str, Any]) -> str:
    body = json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _context_run_id(context: dict[str, Any]) -> str | None:
    run_envelope = context.get("run_envelope")
    if not isinstance(run_envelope, dict):
        return None
    turn_identity = run_envelope.get("turn_identity")
    if isinstance(turn_identity, dict):
        run_id = turn_identity.get("run_id")
        if isinstance(run_id, str) and run_id.strip():
            return run_id.strip()
    run_id = run_envelope.get("run_id")
    if isinstance(run_id, str) and run_id.strip():
        return run_id.strip()
    return None


def _load_run_audit_if_exists(run_id: str) -> dict[str, Any] | None:
    path = env_store.STATE_ROOT / env_store.run_content_path(run_id)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"run content is invalid: {run_id}")
    return payload


def _receipt_from_run_audit(audit: dict[str, Any]) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "ok": True,
        "buddy_id": audit.get("buddy_id"),
        "artifact_ids": audit.get("artifact_ids", []),
        "run_id": audit.get("run_id"),
        "next_state": audit.get("next_state"),
        "receipt_paths": audit.get("receipt_paths"),
        "related_run_ids": audit.get("related_run_ids", []),
    }
    task_id = audit.get("task_id")
    if isinstance(task_id, str) and task_id:
        receipt["task_id"] = task_id
        receipt["task_title"] = audit.get("task_title")
    track_id = audit.get("track_id")
    if isinstance(track_id, str) and track_id:
        receipt["track_id"] = track_id
        receipt["track_title"] = audit.get("track_title")
    handoff = audit.get("handoff")
    if isinstance(handoff, dict):
        receipt["handoff"] = handoff
    return receipt


def validate_run_result(
    context: dict[str, Any],
    *,
    result: dict[str, Any],
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    normalized = _normalize_commit(context, result=result, manifest_path=manifest_path)
    task = normalized["task"]
    track = normalized["track"]
    artifact_ids = normalized["artifact_ids"]
    validated_handoff = normalized["handoff"] if isinstance(normalized.get("handoff"), dict) else None
    return {
        "ok": True,
        "run_id": normalized["run_id"],
        "active_buddy": normalized["active_buddy"],
        "durable_signals": {
            "task_association": task.get("id") if isinstance(task, dict) else None,
            "track_association": track.get("id") if isinstance(track, dict) else None,
            "artifact_refs": artifact_ids,
            "handoff": validated_handoff is not None,
            "validated_handoff": validated_handoff,
            "retired_field_rejections": [],
        },
        "validated_handoff": validated_handoff,
        "retired_field_rejections": [],
        "allowed_next_actions": ["Use run.commit with the same context and result when ready to persist."],
    }


def commit_buddy_run(
    context: dict[str, Any],
    *,
    result: dict[str, Any],
    manifest_path: Path = DEFAULT_MANIFEST,
    idempotency_key: str | None = None,
    result_hash: str | None = None,
) -> dict[str, Any]:
    rt = _runtime()
    context_run_id = _context_run_id(context)
    if context_run_id is None:
        raise ValueError("context run_id is required")

    provided_idempotency_key = idempotency_key.strip() if isinstance(idempotency_key, str) and idempotency_key.strip() else None
    provided_result_hash = result_hash.strip() if isinstance(result_hash, str) and result_hash.strip() else None
    computed_result_hash = _canonical_result_hash(result)
    if provided_result_hash is not None and provided_result_hash != computed_result_hash:
        raise ValueError("result_hash does not match canonical result hash")

    existing_audit = _load_run_audit_if_exists(context_run_id)
    if existing_audit is not None:
        stored_idempotency_key = existing_audit.get("idempotency_key")
        stored_result_hash = existing_audit.get("result_hash")
        if (
            isinstance(stored_idempotency_key, str)
            and stored_idempotency_key
            and isinstance(stored_result_hash, str)
            and stored_result_hash
            and provided_idempotency_key == stored_idempotency_key
            and computed_result_hash == stored_result_hash
        ):
            existing_receipt = _receipt_from_run_audit(existing_audit)
            refreshed_context = rt._post_persist_refreshed_context_unavailable(existing_receipt)
            return {
                "ok": True,
                "receipt": existing_receipt,
                "refreshed_context": refreshed_context,
            }
        rt._raise_runtime_feedback(
            "E_RUNTIME_PERSIST_CONFLICT",
            f"persist conflict for run_id '{context_run_id}': stored result differs from retry payload",
            permission_boundary="persist.idempotency",
            allowed_next_actions=[
                "Rerun prepare to obtain a fresh run context before persisting a different result.",
            ],
        )

    normalized = _normalize_commit(context, result=result, manifest_path=manifest_path)
    run_id = normalized["run_id"]
    task = normalized["task"]
    track = normalized["track"]
    task_id = task.get("id") if isinstance(task, dict) else None
    track_id = track.get("id") if isinstance(track, dict) else None
    handoff = normalized["handoff"]
    next_buddy = handoff.get("next_buddy") if isinstance(handoff, dict) else None
    next_state = _build_next_state(
        task_id=task_id if isinstance(task_id, str) else None,
        track_id=track_id if isinstance(track_id, str) else None,
        current_buddy=normalized["active_buddy"],
        next_buddy=next_buddy if isinstance(next_buddy, str) else None,
    )
    run_content_path_value = env_store.run_content_path(run_id)
    related_run_ids: list[str] = []
    if isinstance(task_id, str):
        related_run_ids = rt._related_run_ids_for_task(task_id, run_id, limit=2)
    receipt_paths = _receipt_paths(
        run_content_path_value=run_content_path_value,
        task_id=task_id if isinstance(task_id, str) else None,
        artifact_ids=normalized["artifact_ids"],
        track_id=track_id if isinstance(track_id, str) else None,
    )
    writes = [run_content_path_value]
    run_audit: dict[str, Any] = {
        "run_id": run_id,
        "timestamp": env_store.now_iso(),
        "buddy_id": normalized["active_buddy"],
        "instance_id": normalized["instance_id"],
        "request_text": normalized["request_text"],
        "context_revision": normalized["context_revision"],
        "task_id": task_id if isinstance(task_id, str) else None,
        "track_id": track_id if isinstance(track_id, str) else None,
        "artifact_ids": normalized["artifact_ids"],
        "execution_summary": normalized["execution_summary"],
        "working_notes": normalized["working_notes"],
        "handoff": normalized["handoff"],
        "contributors": normalized["contributors"],
        "tool_evidence": normalized["tool_evidence"],
        "next_state": next_state,
        "receipt_paths": receipt_paths,
        "related_run_ids": related_run_ids,
        "writes": writes,
        "idempotency_key": provided_idempotency_key,
        "result_hash": computed_result_hash,
    }
    if isinstance(task, dict):
        run_audit["task_title"] = task.get("title")
    if isinstance(track, dict):
        run_audit["track_title"] = track.get("title")
    env_store.save_run_content(run_id, run_audit)

    receipt = _receipt_from_run_audit(run_audit)

    reservation_clear_warning = clear_run_reservation(run_id)
    if reservation_clear_warning is not None:
        warnings = receipt.setdefault("warnings", [])
        if isinstance(warnings, list):
            warnings.append(reservation_clear_warning)

    refreshed_context = rt._post_persist_refreshed_context_unavailable(receipt)
    return {
        "ok": True,
        "receipt": receipt,
        "refreshed_context": refreshed_context,
    }


def _load_run_audit(run_id: str) -> dict[str, Any]:
    try:
        normalized_run_id = env_store.require_id(run_id.strip(), "run id")
    except AttributeError as exc:
        raise ValueError("run_id is required") from exc
    path = env_store.STATE_ROOT / env_store.run_content_path(normalized_run_id)
    if not path.exists():
        raise ValueError(f"run not found: {normalized_run_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"run content is invalid: {normalized_run_id}")
    return payload


def get_raw_run(*, run_id: str, active_buddy: str) -> dict[str, Any]:
    audit = _load_run_audit(run_id)
    buddy_id = audit.get("buddy_id")
    if isinstance(buddy_id, str) and buddy_id != active_buddy:
        raise ValueError(f"run belongs to buddy '{buddy_id}', not active buddy '{active_buddy}'")
    return {
        "ok": True,
        "run_id": audit.get("run_id"),
        "active_buddy": active_buddy,
        "run": audit,
        "allowed_next_actions": ["Use run.get_receipt when only receipt fields are needed."],
    }


def get_run_receipt(*, run_id: str, active_buddy: str) -> dict[str, Any]:
    audit = _load_run_audit(run_id)
    buddy_id = audit.get("buddy_id")
    if isinstance(buddy_id, str) and buddy_id != active_buddy:
        raise ValueError(f"run belongs to buddy '{buddy_id}', not active buddy '{active_buddy}'")
    receipt = _receipt_from_run_audit(audit)
    return {
        "ok": True,
        "run_id": audit.get("run_id"),
        "active_buddy": active_buddy,
        "receipt": receipt,
        "allowed_next_actions": ["Use context.get or prepare again for current context state."],
    }


def _product_session_from_context(context: RunServiceContext) -> dict[str, Any]:
    return {
        "instance_json": context["instance_json"],
        "payload": dict(context["instance_payload"]),
        "instance_id": context["instance_id"],
        "active_buddy": context["active_buddy"],
    }


def commit_for_active_instance(*, args: dict[str, Any], context: RunServiceContext) -> dict[str, Any]:
    rt = _runtime()
    action = "run.commit"
    prepared_context = args.get("context")
    result = args.get("result")
    if not isinstance(prepared_context, dict):
        return _payload_error(action=action, context=context, message="context is required")
    if not isinstance(result, dict):
        return _payload_error(action=action, context=context, message="result is required")

    product_session = _product_session_from_context(context)
    rt._validate_product_persist_context_binding(prepared_context, product_session)
    prepared_run_id = _context_run_id(prepared_context)
    reservation_existed_before_commit = (
        isinstance(prepared_run_id, str) and bool(prepared_run_id) and reserved_run_path(prepared_run_id).exists()
    )
    payload = commit_buddy_run(
        prepared_context,
        result=result,
        manifest_path=context["manifest_path"] or DEFAULT_MANIFEST,
        idempotency_key=args.get("idempotency_key") if isinstance(args.get("idempotency_key"), str) else None,
        result_hash=args.get("result_hash") if isinstance(args.get("result_hash"), str) else None,
    )
    receipt = payload.get("receipt") if isinstance(payload.get("receipt"), dict) else {}
    run_id = receipt.get("run_id")
    state_changes = [{"object_type": "run_commit", "object_id": run_id, "change": "run audit committed"}] if isinstance(run_id, str) else []
    if reservation_existed_before_commit and isinstance(prepared_run_id, str):
        reservation_exists_after_commit = reserved_run_path(prepared_run_id).exists()
        if not reservation_exists_after_commit:
            state_changes.append(
                {
                    "object_type": "run_reservation",
                    "object_id": prepared_run_id,
                    "change": "consumed",
                }
            )
    return tool_responses.success(
        tool="run",
        action=action,
        active_buddy=context["active_buddy"],
        effect_summary=f"Committed durable run audit for run_id '{run_id or 'unknown'}'.",
        state_changed=True,
        durability="run_commit",
        state_changes=state_changes,
        created_ids=[run_id] if isinstance(run_id, str) else [],
        allowed_next_actions=[
            "Use run.get_receipt to read compact persisted receipt fields.",
            "Use context.get or rerun prepare for refreshed runtime context.",
        ],
        extra={
            "receipt": receipt,
            "refreshed_context": payload.get("refreshed_context"),
        },
    )


def validate_result_for_active_instance(*, args: dict[str, Any], context: RunServiceContext) -> dict[str, Any]:
    action = "run.validate_result"
    prepared_context = args.get("context")
    result = args.get("result")
    if not isinstance(prepared_context, dict):
        return _payload_error(action=action, context=context, message="context is required")
    if not isinstance(result, dict):
        return _payload_error(action=action, context=context, message="result is required")
    payload = validate_run_result(
        prepared_context,
        result=result,
        manifest_path=context["manifest_path"] or DEFAULT_MANIFEST,
    )
    return tool_responses.success(
        tool="run",
        action=action,
        active_buddy=context["active_buddy"],
        effect_summary="Validated run payload against prepared context without committing run state.",
        state_changed=False,
        durability="none",
        validation_only=True,
        follow_up_affordances=[
            tool_responses.follow_up_affordance(
                tool="run",
                action="commit",
                reason="Persist validated result as durable run audit.",
            )
        ],
        allowed_next_actions=list(payload.get("allowed_next_actions", []))
        or ["Use run.commit with the same context and result when ready to persist."],
        extra={
            "run_id": payload.get("run_id"),
            "durable_signals": payload.get("durable_signals"),
            "validated_handoff": payload.get("validated_handoff"),
            "retired_field_rejections": payload.get("retired_field_rejections", []),
        },
    )


def get_receipt_for_active_instance(*, args: dict[str, Any], context: RunServiceContext) -> dict[str, Any]:
    action = "run.get_receipt"
    run_id = args.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        return _payload_error(action=action, context=context, message="run_id is required")
    payload = get_run_receipt(run_id=run_id.strip(), active_buddy=context["active_buddy"])
    return tool_responses.success(
        tool="run",
        action=action,
        active_buddy=context["active_buddy"],
        effect_summary=f"Read run receipt for run_id '{payload.get('run_id')}'.",
        state_changed=False,
        durability="none",
        read_scope="Committed run receipt fields only.",
        allowed_next_actions=list(payload.get("allowed_next_actions", []))
        or ["Use context.get or prepare again for current context state."],
        extra={
            "run_id": payload.get("run_id"),
            "receipt": payload.get("receipt"),
        },
    )


def get_raw_for_active_instance(*, args: dict[str, Any], context: RunServiceContext) -> dict[str, Any]:
    action = "run.get_raw"
    run_id = args.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        return _payload_error(action=action, context=context, message="run_id is required")
    payload = get_raw_run(run_id=run_id.strip(), active_buddy=context["active_buddy"])
    return tool_responses.success(
        tool="run",
        action=action,
        active_buddy=context["active_buddy"],
        effect_summary=f"Read raw committed run audit for run_id '{payload.get('run_id')}'.",
        state_changed=False,
        durability="none",
        read_scope="Full committed run audit payload.",
        allowed_next_actions=list(payload.get("allowed_next_actions", []))
        or ["Use run.get_receipt when only receipt fields are needed."],
        extra={
            "run_id": payload.get("run_id"),
            "run": payload.get("run"),
        },
    )


def _payload_error(*, action: str, context: RunServiceContext, message: str) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="run",
        action=action,
        active_buddy=context["active_buddy"],
        code="E_RUN_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Run payload is invalid.",
        why_blocked=message,
        impact="No run audit, reservation, or runtime object state was changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix required run payload fields and retry.",
        allowed_next_actions=[
            'Send env.tool payload as {"tool":"run","action":"<action>","args":{...}}.',
            "Use prepare.runtime_context.env_tools.run.payload_fields to shape args.",
        ],
        extra={
            "next_actions": [
                {"tool": "context", "action": "summarize"},
                {"tool": "run", "action": "validate_result"},
            ],
            "command_hint": track_relations.command_hint("context", "summarize"),
            "relation": "none",
            "missing_preconditions": ["run action payload must include required fields"],
            "no_content_leak": True,
        },
    )
