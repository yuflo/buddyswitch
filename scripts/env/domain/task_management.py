#!/usr/bin/env python3
"""Canonical task snapshot and mutation services."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from env.repos import runtime_files
from env.repos import tasks as task_repo


_TASK_PAYLOAD_FIELDS = {"title", "summary", "body", "priority", "track_id", "refs"}
_PROPOSE_FIELDS = {"type", "task_id", "task", "target", "reason", "evidence"}
_CONFIRM_FIELDS = {"confirmation_id", "decision", "reason"}
_TARGET_FIELDS = {"mode", "task_id", "task"}
_PUBLICATION_STYLE_FIELDS = {
    "artifact_id",
    "artifact_ids",
    "close_proof",
    "current_artifacts",
    "publish",
    "published_to_track",
    "shared_materials",
    "source_refs",
    "supersedes_artifact_id",
    "target_buddy",
    "template",
    "updates",
    "visibility",
}


def _task_excerpt(value: Any, *, limit: int = 180) -> str:
    if not isinstance(value, str):
        return ""
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _snapshot_task(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": task.get("id"),
        "title": task.get("title"),
        "status": task.get("status"),
        "summary": task.get("summary", ""),
        "body_excerpt": _task_excerpt(task.get("body", "")),
        "priority": task.get("priority"),
        "track_id": task.get("track_id"),
        "refs": task.get("refs", []),
        "updated_at": task.get("updated_at"),
    }


def _pending_switch_from_event(event: Mapping[str, Any]) -> dict[str, Any] | None:
    fields = event.get("fields")
    if not isinstance(fields, dict):
        return None
    confirmation_id = fields.get("confirmation_id")
    target = fields.get("target")
    if not isinstance(confirmation_id, str) or not confirmation_id:
        return None
    if not isinstance(target, dict):
        return None
    return {
        "confirmation_id": confirmation_id,
        "type": "task.switch",
        "from_task_id": event.get("task_id"),
        "target": target,
        "reason": fields.get("reason") if isinstance(fields.get("reason"), str) else "",
        "evidence": fields.get("evidence") if isinstance(fields.get("evidence"), str) else "",
    }


def current_snapshot(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    history_limit: int = 8,
) -> dict[str, Any]:
    """Read the canonical current task snapshot without mutating taskbox state."""

    all_events = task_repo.read_history_events(
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
        limit=0,
    )
    current_task_id: str | None = None
    pending_confirmation: dict[str, Any] | None = None
    for event in all_events:
        event_name = event.get("event")
        task_id = event.get("task_id")
        if not isinstance(task_id, str):
            continue
        if event_name == "task.create":
            current_task_id = task_id
        elif event_name == "task.switch.requested":
            pending_confirmation = _pending_switch_from_event(event)
        elif event_name == "task.switch.confirmed":
            current_task_id = task_id
            pending_confirmation = None
        elif event_name == "task.switch.rejected":
            current_task_id = task_id
            pending_confirmation = None
        elif event_name in {"task.close", "task.block"}:
            current_task_id = task_id

    current_task: dict[str, Any] | None = None
    if current_task_id is not None:
        loaded = task_repo.get_task(
            current_task_id,
            active_buddy=active_buddy,
            instance_json=instance_json,
            instance_payload=instance_payload,
        )
        if loaded is not None:
            current_task = _snapshot_task(loaded)

    if history_limit < 1:
        history_limit = 1
    recent_events = all_events[-history_limit:]
    task_state = "none"
    progress_summary = ""
    if current_task is not None:
        task_state = str(current_task.get("status") or "none")
        summary = current_task.get("summary")
        progress_summary = str(summary) if isinstance(summary, str) and summary else str(current_task.get("body_excerpt") or "")

    return {
        "owner_buddy": active_buddy,
        "task_state": task_state,
        "current_task": current_task,
        "pending_confirmation": pending_confirmation,
        "recent_events": recent_events,
        "last_event": recent_events[-1] if recent_events else None,
        "progress_summary": progress_summary,
    }


def _repo_kwargs(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> dict[str, Any]:
    return {
        "active_buddy": active_buddy,
        "instance_json": instance_json,
        "instance_payload": instance_payload,
    }


def _service_rejection(message: str, *, correctable_fields: list[str] | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "message": message,
        "correctable_fields": correctable_fields,
        "state_changed": False,
    }


def _service_success(
    *,
    effect_summary: str,
    snapshot: dict[str, Any],
    state_changed: bool,
    created_ids: list[str] | None = None,
    updated_ids: list[str] | None = None,
    state_changes: list[dict[str, Any]] | None = None,
    task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "effect_summary": effect_summary,
        "snapshot": snapshot,
        "state_changed": state_changed,
        "created_ids": created_ids or [],
        "updated_ids": updated_ids or [],
        "state_changes": state_changes or [],
    }
    if task is not None:
        payload["task"] = task
        payload["task_id"] = task.get("id")
    return payload


def _publication_fields(value: Any, *, path: str = "") -> list[str]:
    fields: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                continue
            child_path = f"{path}.{key}" if path else key
            if key in _PUBLICATION_STYLE_FIELDS:
                fields.append(child_path)
            fields.extend(_publication_fields(nested, path=child_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            fields.extend(_publication_fields(nested, path=f"{path}[{index}]"))
    return fields


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _optional_summary(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError("task.summary must be a string")
    return value


def _normalize_priority(value: Any) -> str:
    if value is None:
        return "normal"
    if value not in task_repo.valid_task_priorities():
        raise ValueError(f"task.priority must be one of {', '.join(task_repo.valid_task_priorities())}")
    return str(value)


def _normalize_track_id(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("task.track_id must be a non-empty string or null")
    return runtime_files.require_id(value.strip(), "task.track_id")


def _normalize_refs(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("task.refs must be a list")
    refs: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, dict):
            raise ValueError("task.refs entries must be objects")
        refs.append(dict(row))
    return refs


def _normalize_task_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("task must be an object")
    publication_fields = _publication_fields(value)
    if publication_fields:
        raise ValueError(f"publication-style payload fields: {', '.join(publication_fields)}")
    unknown = sorted(key for key in value if isinstance(key, str) and key not in _TASK_PAYLOAD_FIELDS)
    if unknown:
        raise ValueError(f"unsupported task fields: {', '.join(unknown)}")
    title = _require_text(value.get("title"), "task.title")
    body = _require_text(value.get("body"), "task.body")
    return {
        "title": title,
        "summary": _optional_summary(value.get("summary")),
        "body": body,
        "priority": _normalize_priority(value.get("priority")),
        "track_id": _normalize_track_id(value.get("track_id")),
        "refs": _normalize_refs(value.get("refs")),
    }


def _new_task_doc(*, task_id: str, active_buddy: str, task: Mapping[str, Any]) -> dict[str, Any]:
    now = runtime_files.now_iso()
    return {
        "id": task_id,
        "owner_buddy": active_buddy,
        "title": task["title"],
        "summary": task.get("summary", ""),
        "body": task["body"],
        "status": "active",
        "priority": task.get("priority", "normal"),
        "track_id": task.get("track_id"),
        "refs": task.get("refs", []),
        "created_at": now,
        "updated_at": now,
        "closed_at": None,
    }


def _current_full_task(
    snapshot: Mapping[str, Any],
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> dict[str, Any] | None:
    current = snapshot.get("current_task")
    if not isinstance(current, Mapping):
        return None
    task_id = current.get("id")
    if not isinstance(task_id, str):
        return None
    return task_repo.get_task(
        task_id,
        **_repo_kwargs(active_buddy=active_buddy, instance_json=instance_json, instance_payload=instance_payload),
    )


def _validate_propose_args(args: Mapping[str, Any]) -> dict[str, Any] | None:
    publication_fields = _publication_fields(args)
    if publication_fields:
        return _service_rejection(
            f"publication-style payload fields: {', '.join(publication_fields)}",
            correctable_fields=publication_fields,
        )
    unknown = sorted(key for key in args if isinstance(key, str) and key not in _PROPOSE_FIELDS)
    if unknown:
        return _service_rejection(f"unsupported payload fields: {', '.join(unknown)}", correctable_fields=unknown)
    for field in ("type", "reason", "evidence"):
        if not isinstance(args.get(field), str) or not str(args.get(field)).strip():
            return _service_rejection(f"{field} is required", correctable_fields=[field])
    if args.get("type") not in {"start", "switch", "finish", "block"}:
        return _service_rejection("type must be one of start, switch, finish, block", correctable_fields=["type"])
    return None


def _normalize_target(value: Any, *, active_buddy: str, instance_json: Path | str | None, instance_payload: Mapping[str, object] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("target must be an object")
    unknown = sorted(key for key in value if isinstance(key, str) and key not in _TARGET_FIELDS)
    if unknown:
        raise ValueError(f"unsupported target fields: {', '.join(unknown)}")
    mode = value.get("mode")
    if mode == "existing":
        task_id = _require_text(value.get("task_id"), "target.task_id")
        task_id = runtime_files.require_id(task_id, "target.task_id")
        if task_repo.get_task(
            task_id,
            **_repo_kwargs(active_buddy=active_buddy, instance_json=instance_json, instance_payload=instance_payload),
        ) is None:
            raise ValueError(f"target task not found: {task_id}")
        return {"mode": "existing", "task_id": task_id, "task": None}
    if mode == "new":
        task = _normalize_task_payload(value.get("task"))
        return {"mode": "new", "task_id": None, "task": task}
    raise ValueError("target.mode must be existing or new")


def propose_task(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    args: Mapping[str, Any],
) -> dict[str, Any]:
    validation_error = _validate_propose_args(args)
    if validation_error is not None:
        return validation_error

    snapshot = current_snapshot(
        active_buddy=active_buddy,
        instance_json=instance_json,
        instance_payload=instance_payload,
    )
    proposal_type = str(args["type"])
    reason = str(args["reason"]).strip()
    evidence = str(args["evidence"]).strip()
    repo_kwargs = _repo_kwargs(active_buddy=active_buddy, instance_json=instance_json, instance_payload=instance_payload)

    if proposal_type == "start":
        if snapshot.get("task_state") in {"active", "blocked"}:
            return _service_rejection(
                "Current task is active or blocked; use task.propose(type=switch) when replacing active work.",
                correctable_fields=["type"],
            )
        try:
            task_payload = _normalize_task_payload(args.get("task"))
            task_id = task_repo.next_task_id(task_payload["title"], **repo_kwargs)
        except ValueError as exc:
            return _service_rejection(str(exc))
        task = task_repo.save_task(_new_task_doc(task_id=task_id, active_buddy=active_buddy, task=task_payload), **repo_kwargs)
        task_repo.append_history(
            **repo_kwargs,
            event="task.create",
            task_id=task_id,
            fields={
                "title": task["title"],
                "status": task["status"],
                "reason": reason,
                "evidence": evidence,
            },
        )
        new_snapshot = current_snapshot(active_buddy=active_buddy, instance_json=instance_json, instance_payload=instance_payload)
        return _service_success(
            effect_summary=f"Started current task '{task_id}'.",
            snapshot=new_snapshot,
            state_changed=True,
            created_ids=[task_id],
            state_changes=[{"object_type": "task", "change": "created", "task_id": task_id}],
            task=task,
        )

    if proposal_type == "switch":
        current = snapshot.get("current_task")
        if not isinstance(current, Mapping) or not isinstance(current.get("id"), str):
            return _service_rejection("current task is required before proposing a switch", correctable_fields=["type"])
        if snapshot.get("pending_confirmation") is not None:
            return _service_rejection("pending task switch already exists", correctable_fields=["confirmation_id"])
        try:
            target = _normalize_target(
                args.get("target"),
                active_buddy=active_buddy,
                instance_json=instance_json,
                instance_payload=instance_payload,
            )
        except ValueError as exc:
            return _service_rejection(str(exc))
        confirmation_id = task_repo.next_confirmation_id(**repo_kwargs)
        task_repo.append_history(
            **repo_kwargs,
            event="task.switch.requested",
            task_id=str(current["id"]),
            fields={
                "confirmation_id": confirmation_id,
                "target": target,
                "reason": reason,
                "evidence": evidence,
            },
        )
        new_snapshot = current_snapshot(active_buddy=active_buddy, instance_json=instance_json, instance_payload=instance_payload)
        return _service_success(
            effect_summary=f"Requested task switch confirmation '{confirmation_id}'.",
            snapshot=new_snapshot,
            state_changed=True,
            state_changes=[{"object_type": "task_confirmation", "change": "requested", "confirmation_id": confirmation_id}],
        )

    if proposal_type in {"finish", "block"}:
        current_task = _current_full_task(
            snapshot,
            active_buddy=active_buddy,
            instance_json=instance_json,
            instance_payload=instance_payload,
        )
        if current_task is None:
            return _service_rejection("current task is required", correctable_fields=["task_id"])
        task_id = args.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            return _service_rejection("task_id is required", correctable_fields=["task_id"])
        try:
            task_id = runtime_files.require_id(task_id.strip(), "task_id")
        except ValueError as exc:
            return _service_rejection(str(exc), correctable_fields=["task_id"])
        if task_id != current_task.get("id"):
            return _service_rejection("task_id must match the current task", correctable_fields=["task_id"])
        updated = dict(current_task)
        now = runtime_files.now_iso()
        event = "task.close" if proposal_type == "finish" else "task.block"
        updated["status"] = "done" if proposal_type == "finish" else "blocked"
        updated["updated_at"] = now
        updated["closed_at"] = now if proposal_type == "finish" else None
        task = task_repo.save_task(updated, **repo_kwargs)
        task_repo.append_history(
            **repo_kwargs,
            event=event,
            task_id=task_id,
            fields={"reason": reason, "evidence": evidence},
        )
        new_snapshot = current_snapshot(active_buddy=active_buddy, instance_json=instance_json, instance_payload=instance_payload)
        return _service_success(
            effect_summary=f"Marked current task '{task_id}' as {updated['status']}.",
            snapshot=new_snapshot,
            state_changed=True,
            updated_ids=[task_id],
            state_changes=[{"object_type": "task", "change": event, "task_id": task_id}],
            task=task,
        )

    return _service_rejection("unsupported task proposal type", correctable_fields=["type"])


def confirm_task(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    args: Mapping[str, Any],
) -> dict[str, Any]:
    publication_fields = _publication_fields(args)
    if publication_fields:
        return _service_rejection(
            f"publication-style payload fields: {', '.join(publication_fields)}",
            correctable_fields=publication_fields,
        )
    unknown = sorted(key for key in args if isinstance(key, str) and key not in _CONFIRM_FIELDS)
    if unknown:
        return _service_rejection(f"unsupported payload fields: {', '.join(unknown)}", correctable_fields=unknown)
    confirmation_id = args.get("confirmation_id")
    if not isinstance(confirmation_id, str) or not confirmation_id.strip():
        return _service_rejection("confirmation_id is required", correctable_fields=["confirmation_id"])
    decision = args.get("decision")
    if decision not in {"accept", "reject"}:
        return _service_rejection("decision must be accept or reject", correctable_fields=["decision"])
    reason = args.get("reason")
    if reason is None:
        reason = ""
    if not isinstance(reason, str):
        return _service_rejection("reason must be a string", correctable_fields=["reason"])

    repo_kwargs = _repo_kwargs(active_buddy=active_buddy, instance_json=instance_json, instance_payload=instance_payload)
    snapshot = current_snapshot(active_buddy=active_buddy, instance_json=instance_json, instance_payload=instance_payload)
    pending = snapshot.get("pending_confirmation")
    if not isinstance(pending, Mapping):
        return _service_rejection("no pending confirmation exists", correctable_fields=["confirmation_id"])
    if pending.get("type") != "task.switch":
        return _service_rejection("only task.switch confirmations are supported", correctable_fields=["confirmation_id"])
    if pending.get("confirmation_id") != confirmation_id:
        return _service_rejection("confirmation_id does not match pending confirmation", correctable_fields=["confirmation_id"])

    current = snapshot.get("current_task")
    current_task_id = current.get("id") if isinstance(current, Mapping) else pending.get("from_task_id")
    if not isinstance(current_task_id, str) or not current_task_id:
        return _service_rejection("current task is unavailable", correctable_fields=["confirmation_id"])

    if decision == "reject":
        task_repo.append_history(
            **repo_kwargs,
            event="task.switch.rejected",
            task_id=current_task_id,
            fields={"confirmation_id": confirmation_id, "reason": reason},
        )
        new_snapshot = current_snapshot(active_buddy=active_buddy, instance_json=instance_json, instance_payload=instance_payload)
        return _service_success(
            effect_summary=f"Rejected task switch confirmation '{confirmation_id}'.",
            snapshot=new_snapshot,
            state_changed=True,
            state_changes=[{"object_type": "task_confirmation", "change": "rejected", "confirmation_id": confirmation_id}],
        )

    target = pending.get("target")
    if not isinstance(target, Mapping):
        return _service_rejection("pending confirmation target is invalid", correctable_fields=["confirmation_id"])
    created_ids: list[str] = []
    target_task_id: str | None
    if target.get("mode") == "existing":
        target_task_id = target.get("task_id") if isinstance(target.get("task_id"), str) else None
        if not target_task_id or task_repo.get_task(target_task_id, **repo_kwargs) is None:
            return _service_rejection("target task not found", correctable_fields=["confirmation_id"])
    elif target.get("mode") == "new":
        target_task = target.get("task")
        if not isinstance(target_task, Mapping):
            return _service_rejection("pending new target task is invalid", correctable_fields=["confirmation_id"])
        try:
            normalized = _normalize_task_payload(target_task)
            target_task_id = task_repo.next_task_id(normalized["title"], **repo_kwargs)
        except ValueError as exc:
            return _service_rejection(str(exc), correctable_fields=["confirmation_id"])
        task_repo.save_task(_new_task_doc(task_id=target_task_id, active_buddy=active_buddy, task=normalized), **repo_kwargs)
        created_ids.append(target_task_id)
    else:
        return _service_rejection("pending confirmation target mode is invalid", correctable_fields=["confirmation_id"])

    task_repo.append_history(
        **repo_kwargs,
        event="task.switch.confirmed",
        task_id=target_task_id,
        fields={"confirmation_id": confirmation_id, "reason": reason},
    )
    new_snapshot = current_snapshot(active_buddy=active_buddy, instance_json=instance_json, instance_payload=instance_payload)
    return _service_success(
        effect_summary=f"Accepted task switch confirmation '{confirmation_id}'.",
        snapshot=new_snapshot,
        state_changed=True,
        created_ids=created_ids,
        state_changes=[{"object_type": "task_confirmation", "change": "confirmed", "confirmation_id": confirmation_id}],
        task=task_repo.get_task(target_task_id, **repo_kwargs),
    )
