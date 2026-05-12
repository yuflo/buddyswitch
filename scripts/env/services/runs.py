#!/usr/bin/env python3
"""Run reservation and commit service for broker-routed runtime operations."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any, TypedDict

import env_profiles
import env_store
from env_manifest import DEFAULT_MANIFEST, load_manifest, require_buddy
from env.services import bindings as binding_service


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


def find_active_task_reservation(task_id: str) -> dict[str, Any] | None:
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
    task_id: str,
    turn_identity: dict[str, Any],
    instance_id: str | None,
) -> None:
    env_store.require_runtime_workspace_write_root()
    if instance_id is not None:
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
    task_id: str,
    track_id: str | None,
    current_buddy: str,
    next_buddy: str | None,
    track_action: str | None = None,
) -> dict[str, Any]:
    resolved_next_buddy = next_buddy if isinstance(next_buddy, str) and next_buddy.strip() else None
    mode = "handoff" if resolved_next_buddy and resolved_next_buddy != current_buddy else "continue_current_task"
    if track_action == "archive":
        mode = "track_archived"
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
    task_id: str,
    artifact_ids: list[str],
    track_id: str | None,
) -> dict[str, Any]:
    paths: dict[str, Any] = {
        "run": run_content_path_value,
        "task": _task_object_path(task_id),
    }
    if artifact_ids:
        paths["artifacts"] = [_artifact_object_path(item) for item in artifact_ids]
    if track_id:
        paths["track"] = _track_object_path(track_id)
    return paths


def _apply_track_effect(
    *,
    track_effect: dict[str, Any] | None,
    active_buddy: str,
    request_text: str,
    task: dict[str, Any],
    effective_track_id: str | None,
) -> tuple[dict[str, Any], str | None, str | None, str | None, str | None, list[str]]:
    rt = _runtime()
    if track_effect is None:
        return task, effective_track_id, None, None, None, []

    action = str(track_effect.get("action") or "")
    if action == "create":
        new_id = track_effect.get("track_id") or rt._derive_track_id(request_text)
        title = track_effect.get("title") or str(new_id).replace("-", " ").title()
        status = track_effect.get("status") or "active"
        track = env_store.create_track(
            str(new_id),
            str(title),
            status=str(status),
            current_buddy=track_effect.get("current_buddy") or active_buddy,
            next_buddy=track_effect.get("next_buddy"),
            summary=track_effect.get("summary") or "",
        )
        updated_task = env_store.register_task_to_track(track["id"], task["id"])
        writes = [_task_object_path(updated_task["id"]), _track_object_path(track["id"])]
        return updated_task, track["id"], track["title"], track.get("next_buddy"), action, writes

    target_track_id = track_effect.get("track_id") or effective_track_id
    if not isinstance(target_track_id, str) or not target_track_id:
        raise ValueError("state_effects.track requires track_id for non-create actions")

    if action in {"update", "advance"}:
        patch: dict[str, Any] = {}
        for key in ("title", "status", "current_buddy", "next_buddy", "summary"):
            if key in track_effect and track_effect.get(key) is not None:
                patch[key] = track_effect.get(key)
        track = env_store.update_track(target_track_id, patch)
    elif action == "archive":
        track = env_store.update_track(target_track_id, {"status": "archived"})
    else:
        raise ValueError("state_effects.track.action must be one of create/update/advance/archive")

    updated_task = env_store.register_task_to_track(track["id"], task["id"])
    writes = [_task_object_path(updated_task["id"]), _track_object_path(track["id"])]
    return updated_task, track["id"], track["title"], track.get("next_buddy"), action, writes


def _build_run_audit(
    *,
    run_id: str,
    active_buddy: str,
    task: dict[str, Any],
    track_id: str | None,
    track_title: str | None,
    artifact_ids: list[str],
    track_action: str | None,
    writes: list[str],
    receipt_paths: dict[str, Any],
    related_run_ids: list[str],
    next_state: dict[str, Any],
    commit: dict[str, Any],
) -> dict[str, Any]:
    state_effects: dict[str, Any] = {}
    if commit.get("track_effect") is not None:
        state_effects["track"] = commit["track_effect"]
    if commit.get("task_effect") is not None:
        state_effects["task"] = commit["task_effect"]

    return {
        "run_id": run_id,
        "timestamp": env_store.now_iso(),
        "buddy_id": active_buddy,
        "task_id": task["id"],
        "track_id": track_id,
        "task_title": task["title"],
        "track_title": track_title,
        "artifact_ids": artifact_ids,
        "execution_summary": commit["execution_summary"],
        "working_notes": commit["working_notes"],
        "state_effects": state_effects,
        "handoff": commit.get("handoff"),
        "contributors": commit.get("contributors", {"skills": [], "agents": []}),
        "tool_evidence": commit.get("tool_evidence"),
        "next_state": next_state,
        "track_action": track_action,
        "receipt_paths": receipt_paths,
        "related_run_ids": related_run_ids,
        "writes": writes,
    }


def _normalize_commit(
    context: dict[str, Any],
    *,
    result: dict[str, Any],
    manifest_path: Path,
) -> dict[str, Any]:
    rt = _runtime()
    if not context.get("ok"):
        raise ValueError("context payload must be successful before persist_buddy_run")
    if not isinstance(result, dict):
        raise ValueError("result payload must be a JSON object")

    early_run_envelope = context.get("run_envelope")
    if not isinstance(early_run_envelope, dict):
        raise ValueError("run_envelope is required")
    early_run_id = early_run_envelope.get("run_id")
    if not isinstance(early_run_id, str) or not early_run_id.strip():
        raise ValueError("run_envelope.run_id is required")
    rt._assert_run_id_unused(early_run_id.strip())

    stored_task = rt._validate_context_revision(context)

    active_buddy = context.get("active_buddy")
    if not isinstance(active_buddy, str) or not active_buddy.strip():
        raise ValueError("active_buddy is required")
    active_buddy = active_buddy.strip()

    request_text = context.get("request_text")
    if not isinstance(request_text, str) or not request_text.strip():
        raise ValueError("request_text is required")

    current_task_id = context.get("current_task_id")
    if not isinstance(current_task_id, str) or not current_task_id.strip():
        raise ValueError("current_task_id is required")
    current_task_id = current_task_id.strip()
    if current_task_id != stored_task["id"]:
        raise ValueError(f"current_task_id mismatch: expected '{stored_task['id']}', received '{current_task_id}'")

    raw_current_track_id = context.get("current_track_id")
    current_track_id = (
        raw_current_track_id.strip()
        if isinstance(raw_current_track_id, str) and raw_current_track_id.strip()
        else None
    )

    run_id, _ = rt._validate_run_envelope(
        context=context,
        active_buddy=active_buddy,
        request_text=request_text,
        task_id=current_task_id,
        track_id=current_track_id,
    )

    manifest = load_manifest(manifest_path)
    buddy = require_buddy(manifest, active_buddy)
    env_profile = env_profiles.require_env_profile(
        active_buddy,
        manifest_path=manifest_path,
        repo_root=rt.REPO_ROOT,
    )
    commit = rt._validate_buddy_run_commit(
        context=context,
        result=result,
        manifest=manifest,
        buddy=buddy,
        env_profile=env_profile,
        task=stored_task,
        current_track_id=current_track_id,
    )

    rt._validate_task_binding(task=stored_task, explicit_track_id=current_track_id)
    return {
        "active_buddy": active_buddy,
        "request_text": request_text,
        "current_track_id": current_track_id,
        "run_id": run_id,
        "stored_task": stored_task,
        "commit": commit,
    }


def validate_run_result(
    context: dict[str, Any],
    *,
    result: dict[str, Any],
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    normalized = _normalize_commit(context, result=result, manifest_path=manifest_path)
    commit = normalized["commit"]
    return {
        "ok": True,
        "run_id": normalized["run_id"],
        "task_id": normalized["stored_task"]["id"],
        "active_buddy": normalized["active_buddy"],
        "durable_signals": {
            "artifacts": len(commit["artifacts"]),
            "state_effects": {
                "task": commit.get("task_effect") is not None,
                "track": commit.get("track_effect") is not None,
            },
            "handoff": commit.get("handoff") is not None,
        },
        "allowed_next_actions": ["Use run.commit with the same context and result when ready to persist."],
    }


def commit_buddy_run(
    context: dict[str, Any],
    *,
    result: dict[str, Any],
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    rt = _runtime()
    normalized = _normalize_commit(context, result=result, manifest_path=manifest_path)
    active_buddy = normalized["active_buddy"]
    request_text = normalized["request_text"]
    current_track_id = normalized["current_track_id"]
    run_id = normalized["run_id"]
    stored_task = normalized["stored_task"]
    commit = normalized["commit"]

    effective_track_id = current_track_id or stored_task.get("track_id")
    task_after_track, effective_track_id, track_title, track_next_buddy, track_action, track_writes = _apply_track_effect(
        track_effect=commit.get("track_effect"),
        active_buddy=active_buddy,
        request_text=request_text,
        task=stored_task,
        effective_track_id=effective_track_id,
    )

    task = task_after_track
    if effective_track_id:
        task = env_store.register_task_to_track(effective_track_id, task["id"])

    if commit.get("task_effect") is not None:
        task_patch: dict[str, Any] = {}
        task_effect = commit["task_effect"]
        if "status" in task_effect:
            task_patch["status"] = task_effect["status"]
        if "summary" in task_effect:
            task_patch["summary"] = task_effect["summary"]
        if task_patch:
            task = env_store.update_task(task["id"], task_patch)

    artifact_ids: list[str] = []
    for artifact_payload in commit["artifacts"]:
        artifact = env_store.create_artifact(
            artifact_id=rt._derive_artifact_id(task["id"], artifact_payload["kind"]),
            title=artifact_payload["title"],
            buddy=active_buddy,
            kind=artifact_payload["kind"],
            task_id=task["id"],
            source_run_id=run_id,
            summary=artifact_payload.get("summary", ""),
            content=artifact_payload["content"],
        )
        artifact_ids.append(artifact["id"])

    summary_for_task_run = commit["execution_summary"]
    task_effect = commit.get("task_effect")
    if isinstance(task_effect, dict) and isinstance(task_effect.get("summary"), str):
        summary_for_task_run = task_effect.get("summary") or summary_for_task_run
    env_store.add_run_to_task(task["id"], run_id, summary=summary_for_task_run)

    if effective_track_id:
        track = env_store.get_track(effective_track_id)
        if track is not None:
            if track_title is None:
                track_title = track.get("title")
            if track_next_buddy is None:
                track_next_buddy = track.get("next_buddy")

    handoff = commit.get("handoff")
    next_buddy = handoff.get("next_buddy") if isinstance(handoff, dict) else track_next_buddy
    next_state = _build_next_state(
        task_id=task["id"],
        track_id=effective_track_id,
        current_buddy=active_buddy,
        next_buddy=next_buddy,
        track_action=track_action,
    )

    run_content_path_value = env_store.run_content_path(run_id)
    related_run_ids = rt._related_run_ids_for_task(task["id"], run_id, limit=2)
    receipt_paths = _receipt_paths(
        run_content_path_value=run_content_path_value,
        task_id=task["id"],
        artifact_ids=artifact_ids,
        track_id=effective_track_id,
    )

    writes = list(track_writes)
    writes.append(_task_object_path(task["id"]))
    writes.extend(_artifact_object_path(artifact_id) for artifact_id in artifact_ids)
    writes.append(run_content_path_value)
    if effective_track_id:
        writes.append(_track_object_path(effective_track_id))
    writes = list(dict.fromkeys(writes))

    run_audit = _build_run_audit(
        run_id=run_id,
        active_buddy=active_buddy,
        task=task,
        track_id=effective_track_id,
        track_title=track_title,
        artifact_ids=artifact_ids,
        track_action=track_action,
        writes=writes,
        receipt_paths=receipt_paths,
        related_run_ids=related_run_ids,
        next_state=next_state,
        commit=commit,
    )
    env_store.save_run_content(run_id, run_audit)

    receipt: dict[str, Any] = {
        "ok": True,
        "buddy_id": active_buddy,
        "task_id": task["id"],
        "task_title": task["title"],
        "artifact_ids": artifact_ids,
        "run_id": run_id,
        "next_state": next_state,
        "receipt_paths": receipt_paths,
        "related_run_ids": related_run_ids,
    }
    if effective_track_id:
        receipt["track_id"] = effective_track_id
        if track_title is not None:
            receipt["track_title"] = track_title
    if track_action is not None:
        receipt["track_action"] = track_action
    if handoff is not None:
        receipt["handoff"] = handoff

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
    receipt: dict[str, Any] = {
        "ok": True,
        "buddy_id": audit.get("buddy_id"),
        "task_id": audit.get("task_id"),
        "artifact_ids": audit.get("artifact_ids", []),
        "run_id": audit.get("run_id"),
        "next_state": audit.get("next_state"),
        "receipt_paths": audit.get("receipt_paths"),
        "related_run_ids": audit.get("related_run_ids", []),
    }
    track_id = audit.get("track_id")
    if isinstance(track_id, str) and track_id:
        receipt["track_id"] = track_id
        receipt["track_title"] = audit.get("track_title")
    track_action = audit.get("track_action")
    if isinstance(track_action, str) and track_action:
        receipt["track_action"] = track_action
    handoff = audit.get("handoff")
    if isinstance(handoff, dict):
        receipt["handoff"] = handoff
    return {
        "ok": True,
        "run_id": audit.get("run_id"),
        "active_buddy": active_buddy,
        "receipt": receipt,
        "allowed_next_actions": ["Use context.get or prepare again for current task state."],
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
    payload = commit_buddy_run(
        prepared_context,
        result=result,
        manifest_path=context["manifest_path"] or DEFAULT_MANIFEST,
    )
    binding = binding_service.persist_binding_from_payload(payload)
    if binding is not None:
        task_id, track_id = binding
        try:
            binding_service.write_product_session_binding(product_session, task_id=task_id, track_id=track_id)
        except (OSError, ValueError) as exc:
            rt._mark_committed_binding_update_failed(payload, product_session, exc)
    return {"tool": "run", "action": action, **payload}


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
    return {"tool": "run", "action": action, **payload}


def get_receipt_for_active_instance(*, args: dict[str, Any], context: RunServiceContext) -> dict[str, Any]:
    action = "run.get_receipt"
    run_id = args.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        return _payload_error(action=action, context=context, message="run_id is required")
    payload = get_run_receipt(run_id=run_id.strip(), active_buddy=context["active_buddy"])
    return {"tool": "run", "action": action, **payload}


def get_raw_for_active_instance(*, args: dict[str, Any], context: RunServiceContext) -> dict[str, Any]:
    action = "run.get_raw"
    run_id = args.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        return _payload_error(action=action, context=context, message="run_id is required")
    payload = get_raw_run(run_id=run_id.strip(), active_buddy=context["active_buddy"])
    return {"tool": "run", "action": action, **payload}


def _payload_error(*, action: str, context: RunServiceContext, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": "run",
        "action": action,
        "error": {
            "code": "E_RUN_PAYLOAD",
            "message": message,
        },
        "permission_boundary": "request-payload",
        "active_buddy": context["active_buddy"],
        "allowed_next_actions": [
            'Send env.tool payload as {"tool":"run","action":"<action>","args":{...}}.',
            "Use prepare.runtime_context.env_tools.run.payload_fields to shape args.",
        ],
    }
