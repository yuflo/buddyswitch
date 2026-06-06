#!/usr/bin/env python3
"""Actor Task Management System operations and TaskViewModel projection."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from env.repos import runtime_files
from env.repos import tasks as task_repo


_TASK_PAYLOAD_FIELDS = {"title", "summary", "body", "priority", "origin", "refs", "track_id", "progress_summary"}
_CAPTURE_FIELDS = {"task", "reason", "evidence"}
_SELECT_FIELDS = {"task_id", "reason"}
_SWITCH_REQUEST_FIELDS = {"target", "reason", "evidence"}
_SWITCH_CONFIRM_FIELDS = {"confirmation_id", "decision", "reason"}
_PROGRESS_FIELDS = {"task_id", "summary", "evidence", "refs"}
_CHECKOUT_FIELDS = {"task_id", "next", "summary", "evidence", "reason", "refs"}
_REVIEW_FIELDS = {"history_limit"}
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
    "target_role",
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


def _view_task(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": task.get("id"),
        "title": task.get("title"),
        "status": task.get("status"),
        "summary": task.get("summary", ""),
        "body_excerpt": _task_excerpt(task.get("body", "")),
        "priority": task.get("priority"),
        "origin": task.get("origin", {"type": "manual"}),
        "refs": task.get("refs", []),
        "progress_summary": task.get("progress_summary") or task.get("summary", ""),
        "updated_at": task.get("updated_at"),
        "closed_at": task.get("closed_at"),
    }


def _repo_kwargs(
    *,
    active_role: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
) -> dict[str, Any]:
    return {
        "active_role": active_role,
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
    view: dict[str, Any],
    state_changed: bool,
    created_ids: list[str] | None = None,
    updated_ids: list[str] | None = None,
    state_changes: list[dict[str, Any]] | None = None,
    task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "effect_summary": effect_summary,
        "view": view,
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


def _unsupported_fields(args: Mapping[str, Any], allowed: set[str]) -> list[str]:
    return sorted(key for key in args if isinstance(key, str) and key not in allowed)


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _optional_text(value: Any, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
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


def _normalize_origin(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "manual"}
    if not isinstance(value, dict):
        raise ValueError("task.origin must be an object")
    return dict(value)


def _normalize_task_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("task must be an object")
    publication_fields = _publication_fields(value)
    if publication_fields:
        raise ValueError(f"publication-style payload fields: {', '.join(publication_fields)}")
    unknown = _unsupported_fields(value, _TASK_PAYLOAD_FIELDS)
    if unknown:
        raise ValueError(f"unsupported task fields: {', '.join(unknown)}")
    title = _require_text(value.get("title"), "task.title")
    body = _require_text(value.get("body"), "task.body")
    summary = _optional_summary(value.get("summary"))
    return {
        "title": title,
        "summary": summary,
        "body": body,
        "priority": _normalize_priority(value.get("priority")),
        "origin": _normalize_origin(value.get("origin")),
        "track_id": _normalize_track_id(value.get("track_id")),
        "refs": _normalize_refs(value.get("refs")),
        "progress_summary": summary,
    }


def _new_task_doc(*, task_id: str, active_actor: Mapping[str, Any], task: Mapping[str, Any], status: str) -> dict[str, Any]:
    now = runtime_files.now_iso()
    return {
        "id": task_id,
        "owner_actor": dict(active_actor),
        "title": task["title"],
        "summary": task.get("summary", ""),
        "body": task["body"],
        "status": status,
        "priority": task.get("priority", "normal"),
        "origin": task.get("origin", {"type": "manual"}),
        "track_id": task.get("track_id"),
        "refs": task.get("refs", []),
        "progress_summary": task.get("progress_summary", ""),
        "created_at": now,
        "updated_at": now,
        "closed_at": None,
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
        "from_task_id": event.get("task_id"),
        "target": target,
        "reason": fields.get("reason") if isinstance(fields.get("reason"), str) else "",
        "evidence": fields.get("evidence") if isinstance(fields.get("evidence"), str) else "",
    }


def _recent_evidence(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        fields = event.get("fields")
        if not isinstance(fields, dict):
            continue
        evidence = fields.get("evidence")
        refs = fields.get("refs")
        reason = fields.get("reason")
        if not evidence and not refs and event.get("event") != "task.blocked":
            continue
        row: dict[str, Any] = {
            "event": event.get("event"),
            "task_id": event.get("task_id"),
        }
        if isinstance(evidence, str) and evidence:
            row["evidence"] = evidence
        if isinstance(reason, str) and reason:
            row["reason"] = reason
        if isinstance(refs, list) and refs:
            row["refs"] = refs
        rows.append(row)
    return rows


def _available_actions(
    *,
    current_anchor: Mapping[str, Any] | None,
    pending_switch: Mapping[str, Any] | None,
    shelf: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
) -> list[str]:
    actions = ["current", "capture", "review"]
    if pending_switch is not None:
        actions.append("switch_confirm")
    if current_anchor is not None:
        actions.extend(["switch_request", "progress", "checkout"])
    elif shelf or blocked:
        actions.append("select")
    return actions


def _checkout_cue(current_anchor: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        "choices": ["continue", "finish", "block"],
        "requires": {"finish": "evidence", "block": "reason"},
        "available": current_anchor is not None,
    }


def _derive_current_and_pending(events: list[dict[str, Any]]) -> tuple[str | None, dict[str, Any] | None]:
    current_task_id: str | None = None
    pending_switch: dict[str, Any] | None = None
    for event in events:
        event_name = event.get("event")
        task_id = event.get("task_id")
        if not isinstance(task_id, str):
            continue
        if event_name in {"task.selected", "task.switch.confirmed", "task.create"}:
            current_task_id = task_id
            pending_switch = None
        elif event_name == "task.switch.requested":
            pending_switch = _pending_switch_from_event(event)
        elif event_name == "task.switch.rejected":
            current_task_id = task_id
            pending_switch = None
        elif event_name in {"task.finished", "task.blocked", "task.close", "task.block"}:
            if current_task_id == task_id:
                current_task_id = None
            pending_switch = None
    return current_task_id, pending_switch


def current_view(
    *,
    active_role: str,
    active_actor: Mapping[str, Any],
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    history_limit: int = 8,
) -> dict[str, Any]:
    """Read actor-facing task state without mutating taskbox state."""

    repo_kwargs = _repo_kwargs(active_role=active_role, instance_json=instance_json, instance_payload=instance_payload)
    all_events = task_repo.read_history_events(**repo_kwargs, limit=0)
    current_task_id, pending_switch = _derive_current_and_pending(all_events)
    current_anchor: dict[str, Any] | None = None
    if current_task_id is not None:
        loaded = task_repo.get_task(current_task_id, **repo_kwargs)
        if loaded is not None and loaded.get("status") == "active":
            current_anchor = _view_task(loaded)
        else:
            current_task_id = None

    tasks = task_repo.list_tasks(**repo_kwargs)
    shelf = [_view_task(task) for task in tasks if task.get("status") == "captured"]
    blocked = [_view_task(task) for task in tasks if task.get("status") == "blocked"]
    selected_events = all_events[-history_limit:] if history_limit > 0 else []
    warnings: list[dict[str, Any]] = []
    for task in blocked:
        warnings.append({"type": "blocked_task", "task_id": task["id"], "title": task["title"]})
    if pending_switch is not None:
        warnings.append({"type": "pending_switch", "confirmation_id": pending_switch["confirmation_id"]})

    return {
        "owner_actor": dict(active_actor),
        "current_anchor": current_anchor,
        "task_state": str(current_anchor.get("status")) if current_anchor is not None else "none",
        "shelf": shelf,
        "pending_switch": pending_switch,
        "recent_events": selected_events,
        "recent_evidence": _recent_evidence(selected_events),
        "available_actions": _available_actions(current_anchor=current_anchor, pending_switch=pending_switch, shelf=shelf, blocked=blocked),
        "checkout_cue": _checkout_cue(current_anchor),
        "warnings": warnings,
    }


def _current_full_task(view: Mapping[str, Any], *, active_role: str, instance_json: Path | str | None, instance_payload: Mapping[str, object] | None) -> dict[str, Any] | None:
    current = view.get("current_anchor")
    if not isinstance(current, Mapping):
        return None
    task_id = current.get("id")
    if not isinstance(task_id, str):
        return None
    return task_repo.get_task(
        task_id,
        **_repo_kwargs(active_role=active_role, instance_json=instance_json, instance_payload=instance_payload),
    )


def _validate_common(args: Mapping[str, Any], allowed: set[str]) -> dict[str, Any] | None:
    publication_fields = _publication_fields(args)
    if publication_fields:
        return _service_rejection(
            f"publication-style payload fields: {', '.join(publication_fields)}",
            correctable_fields=publication_fields,
        )
    unknown = _unsupported_fields(args, allowed)
    if unknown:
        return _service_rejection(f"unsupported payload fields: {', '.join(unknown)}", correctable_fields=unknown)
    return None


def capture_task(
    *,
    active_role: str,
    active_actor: Mapping[str, Any],
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    args: Mapping[str, Any],
) -> dict[str, Any]:
    validation_error = _validate_common(args, _CAPTURE_FIELDS)
    if validation_error is not None:
        return validation_error
    try:
        task_payload = _normalize_task_payload(args.get("task"))
        reason = _optional_text(args.get("reason"), "reason")
        evidence = _optional_text(args.get("evidence"), "evidence")
    except ValueError as exc:
        return _service_rejection(str(exc))
    repo_kwargs = _repo_kwargs(active_role=active_role, instance_json=instance_json, instance_payload=instance_payload)
    task_id = task_repo.next_task_id(task_payload["title"], **repo_kwargs)
    task = task_repo.save_task(_new_task_doc(task_id=task_id, active_actor=active_actor, task=task_payload, status="captured"), **repo_kwargs)
    task_repo.append_event(
        **repo_kwargs,
        event="task.captured",
        task_id=task_id,
        fields={"title": task["title"], "reason": reason, "evidence": evidence},
    )
    view = current_view(active_role=active_role, active_actor=active_actor, instance_json=instance_json, instance_payload=instance_payload)
    return _service_success(
        effect_summary=f"Captured task '{task_id}' on the shelf.",
        view=view,
        state_changed=True,
        created_ids=[task_id],
        state_changes=[{"object_type": "task", "change": "captured", "task_id": task_id}],
        task=task,
    )


def select_task(
    *,
    active_role: str,
    active_actor: Mapping[str, Any],
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    args: Mapping[str, Any],
) -> dict[str, Any]:
    validation_error = _validate_common(args, _SELECT_FIELDS)
    if validation_error is not None:
        return validation_error
    try:
        task_id = runtime_files.require_id(_require_text(args.get("task_id"), "task_id"), "task_id")
        reason = _optional_text(args.get("reason"), "reason")
    except ValueError as exc:
        return _service_rejection(str(exc), correctable_fields=["task_id"])
    repo_kwargs = _repo_kwargs(active_role=active_role, instance_json=instance_json, instance_payload=instance_payload)
    view = current_view(active_role=active_role, active_actor=active_actor, instance_json=instance_json, instance_payload=instance_payload)
    if view.get("current_anchor") is not None:
        return _service_rejection("active current anchor exists; request a switch instead", correctable_fields=["task_id"])
    task = task_repo.get_task(task_id, **repo_kwargs)
    if task is None:
        return _service_rejection(f"task not found: {task_id}", correctable_fields=["task_id"])
    if task.get("status") not in {"captured", "blocked"}:
        return _service_rejection("task_id must reference a captured or blocked task", correctable_fields=["task_id"])
    updated = dict(task)
    updated["status"] = "active"
    updated["updated_at"] = runtime_files.now_iso()
    saved = task_repo.save_task(updated, **repo_kwargs)
    task_repo.append_event(**repo_kwargs, event="task.selected", task_id=task_id, fields={"reason": reason})
    new_view = current_view(active_role=active_role, active_actor=active_actor, instance_json=instance_json, instance_payload=instance_payload)
    return _service_success(
        effect_summary=f"Selected task '{task_id}' as current anchor.",
        view=new_view,
        state_changed=True,
        updated_ids=[task_id],
        state_changes=[{"object_type": "task", "change": "selected", "task_id": task_id}],
        task=saved,
    )


def _normalize_target(value: Any, *, active_role: str, instance_json: Path | str | None, instance_payload: Mapping[str, object] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("target must be an object")
    unknown = _unsupported_fields(value, _TARGET_FIELDS)
    if unknown:
        raise ValueError(f"unsupported target fields: {', '.join(unknown)}")
    mode = value.get("mode")
    repo_kwargs = _repo_kwargs(active_role=active_role, instance_json=instance_json, instance_payload=instance_payload)
    if mode == "existing":
        task_id = runtime_files.require_id(_require_text(value.get("task_id"), "target.task_id"), "target.task_id")
        task = task_repo.get_task(task_id, **repo_kwargs)
        if task is None:
            raise ValueError(f"target task not found: {task_id}")
        if task.get("status") not in {"captured", "blocked"}:
            raise ValueError("target task must be captured or blocked")
        return {"mode": "existing", "task_id": task_id, "task": None}
    if mode == "new":
        task = _normalize_task_payload(value.get("task"))
        return {"mode": "new", "task_id": None, "task": task}
    raise ValueError("target.mode must be existing or new")


def request_task_switch(
    *,
    active_role: str,
    active_actor: Mapping[str, Any],
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    args: Mapping[str, Any],
) -> dict[str, Any]:
    validation_error = _validate_common(args, _SWITCH_REQUEST_FIELDS)
    if validation_error is not None:
        return validation_error
    repo_kwargs = _repo_kwargs(active_role=active_role, instance_json=instance_json, instance_payload=instance_payload)
    view = current_view(active_role=active_role, active_actor=active_actor, instance_json=instance_json, instance_payload=instance_payload)
    current = view.get("current_anchor")
    if not isinstance(current, Mapping) or not isinstance(current.get("id"), str):
        return _service_rejection("active current anchor is required before requesting a switch", correctable_fields=["target"])
    if view.get("pending_switch") is not None:
        return _service_rejection("pending task switch already exists", correctable_fields=["confirmation_id"])
    try:
        target = _normalize_target(args.get("target"), active_role=active_role, instance_json=instance_json, instance_payload=instance_payload)
        reason = _require_text(args.get("reason"), "reason")
        evidence = _optional_text(args.get("evidence"), "evidence")
    except ValueError as exc:
        return _service_rejection(str(exc))
    confirmation_id = task_repo.next_confirmation_id(**repo_kwargs)
    task_repo.append_event(
        **repo_kwargs,
        event="task.switch.requested",
        task_id=str(current["id"]),
        fields={"confirmation_id": confirmation_id, "target": target, "reason": reason, "evidence": evidence},
    )
    new_view = current_view(active_role=active_role, active_actor=active_actor, instance_json=instance_json, instance_payload=instance_payload)
    return _service_success(
        effect_summary=f"Requested task switch confirmation '{confirmation_id}'.",
        view=new_view,
        state_changed=True,
        state_changes=[{"object_type": "task_switch", "change": "requested", "confirmation_id": confirmation_id}],
    )


def confirm_task_switch(
    *,
    active_role: str,
    active_actor: Mapping[str, Any],
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    args: Mapping[str, Any],
) -> dict[str, Any]:
    validation_error = _validate_common(args, _SWITCH_CONFIRM_FIELDS)
    if validation_error is not None:
        return validation_error
    try:
        confirmation_id = _require_text(args.get("confirmation_id"), "confirmation_id")
        decision = _require_text(args.get("decision"), "decision")
        reason = _optional_text(args.get("reason"), "reason")
    except ValueError as exc:
        return _service_rejection(str(exc))
    if decision not in {"accept", "reject"}:
        return _service_rejection("decision must be accept or reject", correctable_fields=["decision"])
    repo_kwargs = _repo_kwargs(active_role=active_role, instance_json=instance_json, instance_payload=instance_payload)
    view = current_view(active_role=active_role, active_actor=active_actor, instance_json=instance_json, instance_payload=instance_payload)
    pending = view.get("pending_switch")
    if not isinstance(pending, Mapping):
        return _service_rejection("no pending switch exists", correctable_fields=["confirmation_id"])
    if pending.get("confirmation_id") != confirmation_id:
        return _service_rejection("confirmation_id does not match pending switch", correctable_fields=["confirmation_id"])
    current_task = _current_full_task(view, active_role=active_role, instance_json=instance_json, instance_payload=instance_payload)
    if current_task is None:
        return _service_rejection("current task is unavailable", correctable_fields=["confirmation_id"])
    current_task_id = str(current_task["id"])
    if decision == "reject":
        task_repo.append_event(
            **repo_kwargs,
            event="task.switch.rejected",
            task_id=current_task_id,
            fields={"confirmation_id": confirmation_id, "reason": reason},
        )
        new_view = current_view(active_role=active_role, active_actor=active_actor, instance_json=instance_json, instance_payload=instance_payload)
        return _service_success(
            effect_summary=f"Rejected task switch confirmation '{confirmation_id}'.",
            view=new_view,
            state_changed=True,
            state_changes=[{"object_type": "task_switch", "change": "rejected", "confirmation_id": confirmation_id}],
        )

    target = pending.get("target")
    if not isinstance(target, Mapping):
        return _service_rejection("pending switch target is invalid", correctable_fields=["confirmation_id"])
    created_ids: list[str] = []
    updated_ids = [current_task_id]
    target_task_id: str | None = None
    if target.get("mode") == "existing":
        target_task_id = target.get("task_id") if isinstance(target.get("task_id"), str) else None
        target_task = task_repo.get_task(str(target_task_id), **repo_kwargs) if target_task_id else None
        if target_task is None:
            return _service_rejection("target task not found", correctable_fields=["confirmation_id"])
    elif target.get("mode") == "new":
        target_task_payload = target.get("task")
        if not isinstance(target_task_payload, Mapping):
            return _service_rejection("pending new target task is invalid", correctable_fields=["confirmation_id"])
        try:
            normalized = _normalize_task_payload(target_task_payload)
        except ValueError as exc:
            return _service_rejection(str(exc), correctable_fields=["confirmation_id"])
        target_task_id = task_repo.next_task_id(normalized["title"], **repo_kwargs)
        target_task = task_repo.save_task(_new_task_doc(task_id=target_task_id, active_actor=active_actor, task=normalized, status="active"), **repo_kwargs)
        created_ids.append(target_task_id)
    else:
        return _service_rejection("pending switch target mode is invalid", correctable_fields=["confirmation_id"])

    shelved_current = dict(current_task)
    shelved_current["status"] = "captured"
    shelved_current["updated_at"] = runtime_files.now_iso()
    task_repo.save_task(shelved_current, **repo_kwargs)
    if target.get("mode") == "existing":
        assert target_task_id is not None
        target_task = task_repo.get_task(target_task_id, **repo_kwargs)
        if target_task is None:
            return _service_rejection("target task not found", correctable_fields=["confirmation_id"])
        activated = dict(target_task)
        activated["status"] = "active"
        activated["closed_at"] = None
        activated["updated_at"] = runtime_files.now_iso()
        task_repo.save_task(activated, **repo_kwargs)
    assert target_task_id is not None
    updated_ids.append(target_task_id)
    task_repo.append_event(
        **repo_kwargs,
        event="task.switch.confirmed",
        task_id=target_task_id,
        fields={"confirmation_id": confirmation_id, "from_task_id": current_task_id, "reason": reason},
    )
    new_view = current_view(active_role=active_role, active_actor=active_actor, instance_json=instance_json, instance_payload=instance_payload)
    return _service_success(
        effect_summary=f"Accepted task switch confirmation '{confirmation_id}'.",
        view=new_view,
        state_changed=True,
        created_ids=created_ids,
        updated_ids=updated_ids,
        state_changes=[{"object_type": "task_switch", "change": "confirmed", "confirmation_id": confirmation_id}],
        task=task_repo.get_task(target_task_id, **repo_kwargs),
    )


def append_task_progress(
    *,
    active_role: str,
    active_actor: Mapping[str, Any],
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    args: Mapping[str, Any],
) -> dict[str, Any]:
    validation_error = _validate_common(args, _PROGRESS_FIELDS)
    if validation_error is not None:
        return validation_error
    try:
        task_id = runtime_files.require_id(_require_text(args.get("task_id"), "task_id"), "task_id")
        summary = _optional_text(args.get("summary"), "summary")
        evidence = _optional_text(args.get("evidence"), "evidence")
        refs = _normalize_refs(args.get("refs"))
    except ValueError as exc:
        return _service_rejection(str(exc))
    if not evidence and not refs:
        return _service_rejection("evidence or refs are required", correctable_fields=["evidence", "refs"])
    repo_kwargs = _repo_kwargs(active_role=active_role, instance_json=instance_json, instance_payload=instance_payload)
    view = current_view(active_role=active_role, active_actor=active_actor, instance_json=instance_json, instance_payload=instance_payload)
    current_task = _current_full_task(view, active_role=active_role, instance_json=instance_json, instance_payload=instance_payload)
    if current_task is None or current_task.get("id") != task_id:
        return _service_rejection("task_id must match the active current anchor", correctable_fields=["task_id"])
    updated = dict(current_task)
    updated["progress_summary"] = summary or evidence or str(updated.get("progress_summary") or "")
    if refs:
        updated["refs"] = refs
    updated["updated_at"] = runtime_files.now_iso()
    saved = task_repo.save_task(updated, **repo_kwargs)
    task_repo.append_event(
        **repo_kwargs,
        event="task.progress.appended",
        task_id=task_id,
        fields={"summary": summary, "evidence": evidence, "refs": refs},
    )
    new_view = current_view(active_role=active_role, active_actor=active_actor, instance_json=instance_json, instance_payload=instance_payload)
    return _service_success(
        effect_summary=f"Appended progress to task '{task_id}'.",
        view=new_view,
        state_changed=True,
        updated_ids=[task_id],
        state_changes=[{"object_type": "task", "change": "progress_appended", "task_id": task_id}],
        task=saved,
    )


def checkout_task(
    *,
    active_role: str,
    active_actor: Mapping[str, Any],
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    args: Mapping[str, Any],
) -> dict[str, Any]:
    validation_error = _validate_common(args, _CHECKOUT_FIELDS)
    if validation_error is not None:
        return validation_error
    try:
        task_id = runtime_files.require_id(_require_text(args.get("task_id"), "task_id"), "task_id")
        next_step = _require_text(args.get("next"), "next")
        summary = _optional_text(args.get("summary"), "summary")
        evidence = _optional_text(args.get("evidence"), "evidence")
        reason = _optional_text(args.get("reason"), "reason")
        refs = _normalize_refs(args.get("refs"))
    except ValueError as exc:
        return _service_rejection(str(exc))
    if next_step not in {"continue", "finish", "block"}:
        return _service_rejection("next must be continue, finish, or block", correctable_fields=["next"])
    if next_step == "finish" and not evidence:
        return _service_rejection("evidence is required when finishing a task", correctable_fields=["evidence"])
    if next_step == "block" and not reason:
        return _service_rejection("reason is required when blocking a task", correctable_fields=["reason"])
    repo_kwargs = _repo_kwargs(active_role=active_role, instance_json=instance_json, instance_payload=instance_payload)
    view = current_view(active_role=active_role, active_actor=active_actor, instance_json=instance_json, instance_payload=instance_payload)
    current_task = _current_full_task(view, active_role=active_role, instance_json=instance_json, instance_payload=instance_payload)
    if current_task is None or current_task.get("id") != task_id:
        return _service_rejection("task_id must match the active current anchor", correctable_fields=["task_id"])
    updated = dict(current_task)
    now = runtime_files.now_iso()
    updated["updated_at"] = now
    if summary:
        updated["progress_summary"] = summary
    if refs:
        updated["refs"] = refs
    event = "task.checkout.continued"
    change = "checkout_continued"
    if next_step == "finish":
        updated["status"] = "done"
        updated["closed_at"] = now
        event = "task.finished"
        change = "finished"
    elif next_step == "block":
        updated["status"] = "blocked"
        updated["closed_at"] = None
        event = "task.blocked"
        change = "blocked"
    saved = task_repo.save_task(updated, **repo_kwargs)
    task_repo.append_event(
        **repo_kwargs,
        event=event,
        task_id=task_id,
        fields={"next": next_step, "summary": summary, "evidence": evidence, "reason": reason, "refs": refs},
    )
    new_view = current_view(active_role=active_role, active_actor=active_actor, instance_json=instance_json, instance_payload=instance_payload)
    return _service_success(
        effect_summary=f"Checked out task '{task_id}' with next={next_step}.",
        view=new_view,
        state_changed=True,
        updated_ids=[task_id],
        state_changes=[{"object_type": "task", "change": change, "task_id": task_id}],
        task=saved,
    )


def review_tasks(
    *,
    active_role: str,
    active_actor: Mapping[str, Any],
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    args: Mapping[str, Any],
) -> dict[str, Any]:
    validation_error = _validate_common(args, _REVIEW_FIELDS)
    if validation_error is not None:
        return validation_error
    history_limit = args.get("history_limit", 8)
    if history_limit is None:
        history_limit = 8
    if not isinstance(history_limit, int) or history_limit < 1:
        return _service_rejection("history_limit must be a positive integer", correctable_fields=["history_limit"])
    view = current_view(
        active_role=active_role,
        active_actor=active_actor,
        instance_json=instance_json,
        instance_payload=instance_payload,
        history_limit=history_limit,
    )
    return _service_success(
        effect_summary="Reviewed captured, blocked, pending, and current task cues.",
        view=view,
        state_changed=False,
    )
