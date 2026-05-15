#!/usr/bin/env python3
"""Runless memory services."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, TypedDict

import env_store
from env.services import source_refs as source_ref_service
from env.tools import responses as tool_responses


class MemoryServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


_LIST_FIELDS = {"buddy", "kind", "status", "source_ref", "limit"}
_GET_FIELDS = {"memory_id"}
_WRITE_FIELDS = {"memory_id", "kind", "title", "summary", "content", "source_refs", "read_claim"}
_UPDATE_FIELDS = {"memory_id", "kind", "title", "summary", "content", "source_refs", "status", "read_claim"}
_ARCHIVE_FIELDS = {"memory_id"}


def _reject_payload(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="memory",
        action=action,
        active_buddy=active_buddy,
        code="E_MEMORY_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Memory payload is invalid.",
        why_blocked=message,
        impact="No memory object changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix memory payload fields and retry.",
        allowed_next_actions=[
            "Use memory.list to inspect readable memory ids.",
            "Retry with valid memory kind/status/content fields.",
        ],
    )


def _reject_scope(*, action: str, active_buddy: str, boundary: str, message: str, code: str = "E_MEMORY_SCOPE") -> dict[str, Any]:
    return tool_responses.rejection(
        tool="memory",
        action=action,
        active_buddy=active_buddy,
        code=code,
        message=message,
        permission_boundary=boundary,
        human_summary="Memory scope check failed.",
        why_blocked=message,
        impact="No memory object changed.",
        state_changed=False,
        retryable=False,
        retry_guidance="Use owner-scoped memory ids or PM summary scope rules.",
        allowed_next_actions=[
            "Use memory.list without cross-buddy full-read assumptions.",
            "Use own memory ids for write/update/archive actions.",
        ],
    )


def _allow_fields(action: str) -> set[str]:
    if action == "memory.list":
        return _LIST_FIELDS
    if action == "memory.get":
        return _GET_FIELDS
    if action == "memory.write":
        return _WRITE_FIELDS
    if action == "memory.update":
        return _UPDATE_FIELDS
    return _ARCHIVE_FIELDS


def _require_allowed_fields(action: str, args: dict[str, Any], active_buddy: str) -> dict[str, Any] | None:
    unknown = sorted(key for key in args if key not in _allow_fields(action))
    if unknown:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"unsupported payload fields: {', '.join(unknown)}")
    return None


def _memory_row(row: dict[str, Any], *, full: bool) -> dict[str, Any]:
    payload = {
        "id": row.get("id"),
        "buddy": row.get("buddy"),
        "kind": row.get("kind"),
        "title": row.get("title"),
        "summary": row.get("summary"),
        "status": row.get("status"),
        "source_refs": row.get("source_refs"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }
    if full:
        payload["content"] = row.get("content")
    return payload


def _is_pm(active_buddy: str) -> bool:
    return active_buddy == "pm"


def _validate_kind(kind: Any) -> str | None:
    if not isinstance(kind, str) or not kind.strip():
        return None
    kind = kind.strip()
    if kind not in env_store.VALID_MEMORY_KINDS:
        return None
    return kind


def list_memories_for_active_buddy(*, args: dict[str, Any], context: MemoryServiceContext) -> dict[str, Any]:
    action = "memory.list"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    rows = env_store.list_memories()

    requested_buddy = args.get("buddy")
    if isinstance(requested_buddy, str) and requested_buddy.strip():
        requested_buddy = requested_buddy.strip()
        if requested_buddy != active_buddy and not _is_pm(active_buddy):
            return _reject_scope(
                action=action,
                active_buddy=active_buddy,
                boundary="memory.read_scope",
                code="E_MEMORY_READ_SCOPE",
                message="cross-buddy memory list is allowed only for pm summary scope",
            )
        rows = [row for row in rows if row.get("buddy") == requested_buddy]
    elif not _is_pm(active_buddy):
        rows = [row for row in rows if row.get("buddy") == active_buddy]

    kind = args.get("kind")
    if isinstance(kind, str) and kind.strip():
        rows = [row for row in rows if row.get("kind") == kind.strip()]

    status = args.get("status")
    if isinstance(status, str) and status.strip():
        rows = [row for row in rows if row.get("status") == status.strip()]

    source_ref = args.get("source_ref")
    if isinstance(source_ref, str) and source_ref.strip():
        token = source_ref.strip()
        filtered: list[dict[str, Any]] = []
        for row in rows:
            refs = row.get("source_refs")
            if not isinstance(refs, list):
                continue
            if any(isinstance(ref, dict) and token in str(ref) for ref in refs):
                filtered.append(row)
        rows = filtered

    limit = args.get("limit")
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]

    full = _is_pm(active_buddy) and (not isinstance(requested_buddy, str) or requested_buddy == active_buddy)
    summaries = [_memory_row(row, full=False if row.get("buddy") != active_buddy else full) for row in rows]

    return tool_responses.success(
        tool="memory",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Listed {len(summaries)} readable memory record(s).",
        state_changed=False,
        durability="none",
        read_scope="owner full records; pm cross-buddy summary scope",
        allowed_next_actions=[
            "Use memory.get with memory_id for one record.",
            "Use memory.write to persist a new reusable conclusion.",
        ],
        extra={"memories": summaries},
    )


def get_memory_for_active_buddy(*, args: dict[str, Any], context: MemoryServiceContext) -> dict[str, Any]:
    action = "memory.get"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    memory_id = args.get("memory_id")
    if not isinstance(memory_id, str) or not memory_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="memory_id is required")
    memory_id = memory_id.strip()

    memory = env_store.get_memory(memory_id)
    if memory is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"memory not found: {memory_id}")

    owner = memory.get("buddy")
    if owner != active_buddy and not _is_pm(active_buddy):
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary="memory.read_scope",
            code="E_MEMORY_READ_SCOPE",
            message=f"memory '{memory_id}' is owned by buddy '{owner}'",
        )

    # PM cross-buddy read stays summary-only in first implementation.
    full = owner == active_buddy
    row = _memory_row(memory, full=full)
    if not full:
        row["content"] = None

    return tool_responses.success(
        tool="memory",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Read memory '{memory_id}' in allowed scope.",
        state_changed=False,
        durability="none",
        read_scope="owner full read; pm cross-buddy summary read",
        allowed_next_actions=[
            "Use memory.update for owned memory records.",
            "Use memory.archive when a memory should be retired.",
        ],
        extra={"memory_id": memory_id, "memory": row},
    )


def write_memory_for_active_buddy(*, args: dict[str, Any], context: MemoryServiceContext) -> dict[str, Any]:
    action = "memory.write"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    kind = _validate_kind(args.get("kind"))
    if kind is None:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary="memory.kind",
            code="E_MEMORY_KIND",
            message=f"kind must be one of {', '.join(env_store.VALID_MEMORY_KINDS)}",
        )

    title = args.get("title")
    summary = args.get("summary")
    content = args.get("content")
    if not isinstance(title, str) or not title.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="title is required")
    if not isinstance(summary, str) or not summary.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="summary is required")
    if not isinstance(content, dict):
        return _reject_payload(action=action, active_buddy=active_buddy, message="content must be a JSON object")

    read_claim = args.get("read_claim")
    if read_claim is not None and not isinstance(read_claim, str):
        return _reject_payload(action=action, active_buddy=active_buddy, message="read_claim must be a string")

    try:
        source_refs, scope_error = source_ref_service.normalize_source_refs(
            args.get("source_refs"), active_buddy=active_buddy, read_claim=read_claim if isinstance(read_claim, str) else None
        )
    except ValueError as exc:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary="source_refs.required_fields",
            code="E_SOURCE_REFS",
            message=str(exc),
        )
    if isinstance(scope_error, dict):
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary=str(scope_error.get("permission_boundary", "source_refs.read_scope")),
            code="E_SOURCE_REFS_READ_SCOPE",
            message=str(scope_error.get("why_blocked", "source_refs read scope denied")),
        )

    memory_id = args.get("memory_id")
    if memory_id is None:
        memory_id = f"mem-{active_buddy}-{env_store.slugify(title)}-{uuid.uuid4().hex[:8]}"
    if not isinstance(memory_id, str) or not memory_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="memory_id must be a non-empty string")

    try:
        created = env_store.create_memory(
            memory_id=memory_id.strip(),
            buddy=active_buddy,
            kind=kind,
            title=title.strip(),
            summary=summary.strip(),
            content=content,
            source_refs=source_refs,
            status="active",
        )
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_responses.success(
        tool="memory",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Created memory '{created['id']}'.",
        state_changed=True,
        durability="durable",
        created_ids=[created["id"]],
        allowed_next_actions=[
            "Use memory.get to inspect full content.",
            "Use artifact.create_revision to reference this memory in deliverables.",
        ],
        extra={"memory_id": created["id"], "memory": _memory_row(created, full=True)},
    )


def update_memory_for_active_buddy(*, args: dict[str, Any], context: MemoryServiceContext) -> dict[str, Any]:
    action = "memory.update"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    memory_id = args.get("memory_id")
    if not isinstance(memory_id, str) or not memory_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="memory_id is required")
    memory_id = memory_id.strip()

    memory = env_store.get_memory(memory_id)
    if memory is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"memory not found: {memory_id}")
    if memory.get("buddy") != active_buddy:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary="memory.buddy_scope",
            code="E_MEMORY_BUDDY_SCOPE",
            message=f"memory '{memory_id}' is owned by buddy '{memory.get('buddy')}'",
        )

    patch: dict[str, Any] = {}
    if "kind" in args:
        kind = _validate_kind(args.get("kind"))
        if kind is None:
            return _reject_scope(
                action=action,
                active_buddy=active_buddy,
                boundary="memory.kind",
                code="E_MEMORY_KIND",
                message=f"kind must be one of {', '.join(env_store.VALID_MEMORY_KINDS)}",
            )
        patch["kind"] = kind
    if "title" in args:
        title = args["title"]
        if not isinstance(title, str) or not title.strip():
            return _reject_payload(action=action, active_buddy=active_buddy, message="title must be a non-empty string")
        patch["title"] = title.strip()
    if "summary" in args:
        summary = args["summary"]
        if not isinstance(summary, str) or not summary.strip():
            return _reject_payload(action=action, active_buddy=active_buddy, message="summary must be a non-empty string")
        patch["summary"] = summary.strip()
    if "content" in args:
        content = args["content"]
        if not isinstance(content, dict):
            return _reject_payload(action=action, active_buddy=active_buddy, message="content must be a JSON object")
        patch["content"] = content
    if "status" in args:
        status = args["status"]
        if status not in env_store.VALID_MEMORY_STATUS:
            return _reject_scope(
                action=action,
                active_buddy=active_buddy,
                boundary="memory.status",
                code="E_MEMORY_STATUS",
                message=f"status must be one of {', '.join(env_store.VALID_MEMORY_STATUS)}",
            )
        patch["status"] = status
    if "source_refs" in args:
        read_claim = args.get("read_claim")
        if read_claim is not None and not isinstance(read_claim, str):
            return _reject_payload(action=action, active_buddy=active_buddy, message="read_claim must be a string")
        try:
            source_refs, scope_error = source_ref_service.normalize_source_refs(
                args.get("source_refs"), active_buddy=active_buddy, read_claim=read_claim if isinstance(read_claim, str) else None
            )
        except ValueError as exc:
            return _reject_scope(
                action=action,
                active_buddy=active_buddy,
                boundary="source_refs.required_fields",
                code="E_SOURCE_REFS",
                message=str(exc),
            )
        if isinstance(scope_error, dict):
            return _reject_scope(
                action=action,
                active_buddy=active_buddy,
                boundary=str(scope_error.get("permission_boundary", "source_refs.read_scope")),
                code="E_SOURCE_REFS_READ_SCOPE",
                message=str(scope_error.get("why_blocked", "source_refs read scope denied")),
            )
        patch["source_refs"] = source_refs

    if not patch:
        return _reject_payload(action=action, active_buddy=active_buddy, message="at least one patch field is required")

    try:
        updated = env_store.update_memory(memory_id, patch)
    except ValueError as exc:
        return _reject_payload(action=action, active_buddy=active_buddy, message=str(exc))

    return tool_responses.success(
        tool="memory",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Updated memory '{memory_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[memory_id],
        allowed_next_actions=["Use memory.get to verify updated content and source_refs."],
        extra={"memory_id": memory_id, "memory": _memory_row(updated, full=True)},
    )


def archive_memory_for_active_buddy(*, args: dict[str, Any], context: MemoryServiceContext) -> dict[str, Any]:
    action = "memory.archive"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    memory_id = args.get("memory_id")
    if not isinstance(memory_id, str) or not memory_id.strip():
        return _reject_payload(action=action, active_buddy=active_buddy, message="memory_id is required")
    memory_id = memory_id.strip()

    memory = env_store.get_memory(memory_id)
    if memory is None:
        return _reject_payload(action=action, active_buddy=active_buddy, message=f"memory not found: {memory_id}")
    if memory.get("buddy") != active_buddy:
        return _reject_scope(
            action=action,
            active_buddy=active_buddy,
            boundary="memory.buddy_scope",
            code="E_MEMORY_BUDDY_SCOPE",
            message=f"memory '{memory_id}' is owned by buddy '{memory.get('buddy')}'",
        )

    if memory.get("status") == "archived":
        return tool_responses.success(
            tool="memory",
            action=action,
            active_buddy=active_buddy,
            effect_summary=f"Memory '{memory_id}' is already archived.",
            state_changed=False,
            durability="none",
            allowed_next_actions=["Use memory.list --status archived to inspect archived memory."],
            extra={"memory_id": memory_id, "memory": _memory_row(memory, full=True)},
        )

    updated = env_store.update_memory(memory_id, {"status": "archived"})
    return tool_responses.success(
        tool="memory",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Archived memory '{memory_id}'.",
        state_changed=True,
        durability="durable",
        updated_ids=[memory_id],
        allowed_next_actions=["Use memory.list --status active for remaining active memory."],
        extra={"memory_id": memory_id, "memory": _memory_row(updated, full=True)},
    )
