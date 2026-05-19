#!/usr/bin/env python3
"""Runless buddybox services."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, TypedDict

from env.repos import buddybox_files as buddybox_repo
from env.tools import responses as tool_responses


class BuddyboxServiceContext(TypedDict):
    active_buddy: str
    instance_id: str
    instance_json: Path
    instance_payload: dict[str, Any]
    manifest: dict[str, Any]


BUDDYBOX_PRIVACY_MESSAGE = (
    "This is the active buddy's private file capability. "
    "Other buddies cannot list, read, write, or delete these files. "
    "Use artifact when content must become product-readable."
)
_PRIVATE_BOUNDARY = "active_buddy_private_file_capability"

_DESC_FIELDS: set[str] = set()
_LIST_FIELDS = {"logical_name", "recursive", "limit"}
_READ_FIELDS = {"logical_name", "encoding"}
_WRITE_FIELDS = {"logical_name", "content", "content_base64", "content_type"}
_DELETE_FIELDS = {"logical_name"}


def _manifest_buddy_ids(context: BuddyboxServiceContext) -> set[str]:
    buddies: set[str] = set()
    for row in context.get("manifest", {}).get("buddies", []):
        if isinstance(row, dict):
            buddy_id = row.get("id")
            if isinstance(buddy_id, str) and buddy_id.strip():
                buddies.add(buddy_id.strip())
    buddies.add(context["active_buddy"])
    return buddies


def build_buddybox_desc(active_buddy: str, *, instance_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    root = buddybox_repo.ensure_active_buddy_root(active_buddy=active_buddy, instance_payload=instance_payload)
    return {
        "capability": "private_file_workspace",
        "owner_scope": "active_buddy",
        "lifetime_scope": "active_instance_workspace",
        "visibility": "active_buddy_private",
        "product_readable": False,
        "cross_buddy_readable": False,
        "mutates_product_state": False,
        "message": BUDDYBOX_PRIVACY_MESSAGE,
        "supports": [
            "describe_capability",
            "list_private_file_summaries",
            "read_private_file",
            "write_private_text",
            "write_private_binary",
            "delete_private_file",
        ],
        "state_summary": buddybox_repo.state_summary(root=root),
    }


def _operation_semantic_ref(action: str) -> str:
    return f"context.get.operation_semantics['buddybox.{action}']"


def _tool_catalog_ref(tool: str) -> str:
    return f"context.get.tool_catalog['{tool}']"


def _next_option(
    *,
    tool: str,
    action: str,
    option_id: str,
    reason: str,
    preconditions: list[str] | None = None,
) -> dict[str, Any]:
    source_refs = [_tool_catalog_ref(tool), f"context.get.operation_semantics['{tool}.{action}']"]
    return tool_responses.next_action_option(
        tool=tool,
        action=action,
        option_id=option_id,
        reason=reason,
        preconditions=preconditions,
        source_refs=source_refs,
    )


def _desc_options() -> list[dict[str, Any]]:
    return [
        _next_option(
            tool="buddybox",
            action="list",
            option_id="inspect_private_buddybox_summaries",
            reason="Inspect private file summary rows in the active buddy capability.",
        ),
        _next_option(
            tool="buddybox",
            action="write",
            option_id="write_private_buddybox_file",
            reason="Create or replace one active-buddy private file.",
        ),
    ]


def _list_options() -> list[dict[str, Any]]:
    return [
        _next_option(
            tool="buddybox",
            action="read",
            option_id="read_private_buddybox_file",
            reason="Read one private file chosen from summary rows.",
        ),
        _next_option(
            tool="buddybox",
            action="write",
            option_id="write_private_buddybox_file",
            reason="Create or replace one active-buddy private file.",
        ),
    ]


def _read_options() -> list[dict[str, Any]]:
    return [
        _next_option(
            tool="buddybox",
            action="write",
            option_id="replace_private_buddybox_file",
            reason="Replace this private file with an updated version.",
        ),
        _next_option(
            tool="artifact",
            action="create_revision",
            option_id="promote_readable_content_when_needed",
            reason="Use artifact.create_revision when the host decides content should become product-readable.",
        ),
    ]


def _write_options() -> list[dict[str, Any]]:
    return [
        _next_option(
            tool="buddybox",
            action="read",
            option_id="confirm_private_buddybox_file",
            reason="Confirm the private file that was just written.",
        ),
        _next_option(
            tool="buddybox",
            action="list",
            option_id="inspect_private_buddybox_summaries",
            reason="Inspect private summaries after the write.",
        ),
        _next_option(
            tool="artifact",
            action="create_revision",
            option_id="promote_readable_content_when_needed",
            reason="Use artifact.create_revision when the host decides content should become product-readable.",
        ),
    ]


def _delete_options() -> list[dict[str, Any]]:
    return [
        _next_option(
            tool="buddybox",
            action="list",
            option_id="inspect_private_buddybox_summaries",
            reason="Inspect remaining private summaries after delete.",
        ),
        _next_option(
            tool="buddybox",
            action="write",
            option_id="write_private_buddybox_file",
            reason="Create a replacement private file if needed.",
        ),
    ]


def _private_file_state_fields(logical_name: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "object_kind": "private_file",
        "visibility": "active_buddy_private",
        "owner_scope": "active_buddy",
        "lifetime_scope": "active_instance_workspace",
        "product_readable": False,
        "cross_buddy_readable": False,
        "mutates_product_state": False,
        "mutated_product_objects": [],
    }
    if isinstance(logical_name, str):
        payload["logical_name"] = logical_name
    return payload


def _available_affordances(action: str, *, include_artifact: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if action in {"desc", "list", "read", "write", "delete"}:
        rows.append(
            tool_responses.tool_affordance(
                "buddybox",
                "list",
                "list private file summaries",
                "host needs private file inventory",
            )
        )
        rows.append(
            tool_responses.tool_affordance(
                "buddybox",
                "read",
                "read one private file",
                "host needs one exact private file body",
            )
        )
        rows.append(
            tool_responses.tool_affordance(
                "buddybox",
                "write",
                "create or overwrite one private file",
                "host needs private workspace mutation",
            )
        )
        rows.append(
            tool_responses.tool_affordance(
                "buddybox",
                "delete",
                "delete one private file",
                "host needs private workspace cleanup",
                risk="destructive private file mutation",
            )
        )
    if include_artifact:
        rows.append(
            tool_responses.tool_affordance(
                "artifact",
                "create_revision",
                "create product-readable content",
                "host decides content must become product-readable for another buddy or product workflow",
                risk="creates or updates product deliverable state",
                mutates_product_state=True,
            )
        )
    return rows


def _alternative_capabilities() -> list[dict[str, Any]]:
    return [
        tool_responses.alternative_capability(
            tool="artifact",
            action="create_revision",
            condition="Use when private content should become product-readable.",
            mutates_product_state=True,
        )
    ]


def _reject_payload(
    *,
    action: str,
    active_buddy: str,
    message: str,
    correctable_fields: list[str] | None = None,
) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        code="E_BUDDYBOX_PAYLOAD",
        message=message,
        permission_boundary="request-payload",
        human_summary="Buddybox payload is invalid for the active buddy private file capability.",
        why_blocked=message,
        impact="No private file changed and no product/collaboration object changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix payload fields and retry with logical_name.",
        allowed_next_actions=[],
        allowed_next_action_options=[
            _next_option(
                tool="buddybox",
                action="desc",
                option_id="review_buddybox_private_boundary",
                reason="Review private capability semantics before retrying.",
            )
        ],
        error_class="invalid_input",
        boundary=_PRIVATE_BOUNDARY,
        correctable_fields=correctable_fields,
        alternative_capabilities=_alternative_capabilities(),
        mutates_product_state=False,
    )


def _reject_logical_name(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        code="E_BUDDYBOX_LOGICAL_NAME",
        message=message,
        permission_boundary="logical-name",
        human_summary="Buddybox logical_name is invalid for the active buddy private file capability.",
        why_blocked=message,
        impact="No private file changed and no product/collaboration object changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Use a relative logical_name without buddy prefix or traversal.",
        allowed_next_actions=[],
        error_class="invalid_input",
        boundary=_PRIVATE_BOUNDARY,
        correctable_fields=["logical_name"],
        alternative_capabilities=_alternative_capabilities(),
        mutates_product_state=False,
    )


def _reject_boundary(*, action: str, active_buddy: str, message: str) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        code="E_BUDDYBOX_BOUNDARY",
        message=message,
        permission_boundary="active-private-boundary",
        human_summary="Buddybox request crossed active buddy private file boundary.",
        why_blocked=message,
        impact="No private file changed and no product/collaboration object changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Choose a logical_name that resolves inside the active buddy private root.",
        allowed_next_actions=[],
        error_class="boundary_violation",
        boundary=_PRIVATE_BOUNDARY,
        correctable_fields=["logical_name"],
        alternative_capabilities=_alternative_capabilities(),
        mutates_product_state=False,
    )


def _reject_not_found(*, action: str, active_buddy: str, logical_name: str) -> dict[str, Any]:
    return tool_responses.rejection(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        code="E_BUDDYBOX_NOT_FOUND",
        message=f"private file not found: {logical_name}",
        permission_boundary="active-private-boundary",
        human_summary="Buddybox logical_name does not resolve to an existing private file.",
        why_blocked=f"private file '{logical_name}' was not found in active buddy private file capability",
        impact="No private file changed and no product/collaboration object changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="List summaries first or write the file before read/delete.",
        allowed_next_actions=[],
        error_class="not_found",
        boundary=_PRIVATE_BOUNDARY,
        correctable_fields=["logical_name"],
        alternative_capabilities=_alternative_capabilities(),
        mutates_product_state=False,
    )


def _require_allowed_fields(action: str, args: dict[str, Any], active_buddy: str) -> dict[str, Any] | None:
    if action == "buddybox.desc":
        allowed = _DESC_FIELDS
    elif action == "buddybox.list":
        allowed = _LIST_FIELDS
    elif action == "buddybox.read":
        allowed = _READ_FIELDS
    elif action == "buddybox.write":
        allowed = _WRITE_FIELDS
    else:
        allowed = _DELETE_FIELDS

    if "path" in args:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="source field 'path' is retired for buddybox; use logical_name",
            correctable_fields=["logical_name"],
        )

    unknown = sorted(key for key in args if key not in allowed)
    if unknown:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message=f"unsupported payload fields: {', '.join(unknown)}",
            correctable_fields=["logical_name"],
        )
    return None


def _active_root_for_request(
    *, action: str, active_buddy: str, context: BuddyboxServiceContext
) -> tuple[Path | None, dict[str, Any] | None]:
    try:
        root = buddybox_repo.ensure_active_buddy_root(
            active_buddy=active_buddy,
            instance_payload=context["instance_payload"],
        )
    except buddybox_repo.BuddyboxBoundaryError as exc:
        return None, _reject_boundary(action=action, active_buddy=active_buddy, message=str(exc))
    return root, None


def describe_buddybox_for_active_buddy(*, args: dict[str, Any], context: BuddyboxServiceContext) -> dict[str, Any]:
    action = "buddybox.desc"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    try:
        desc = build_buddybox_desc(active_buddy, instance_payload=context["instance_payload"])
    except buddybox_repo.BuddyboxBoundaryError as exc:
        return _reject_boundary(action=action, active_buddy=active_buddy, message=str(exc))
    return tool_responses.success(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        effect_summary="Returned private file capability semantics and compact state summary only.",
        state_changed=False,
        durability="none",
        read_scope="active-buddy private file capability description",
        allowed_next_actions=[],
        allowed_next_action_options=_desc_options(),
        extra={
            **desc,
            "available_affordances": _available_affordances("desc", include_artifact=True),
            **_private_file_state_fields(),
        },
    )


def list_buddybox_for_active_buddy(*, args: dict[str, Any], context: BuddyboxServiceContext) -> dict[str, Any]:
    action = "buddybox.list"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    root, boundary_error = _active_root_for_request(action=action, active_buddy=active_buddy, context=context)
    if boundary_error is not None:
        return boundary_error
    assert root is not None
    buddy_ids = _manifest_buddy_ids(context)

    try:
        prefix = buddybox_repo.normalize_logical_prefix(
            args.get("logical_name"),
            active_buddy=active_buddy,
            buddy_ids=buddy_ids,
        )
    except buddybox_repo.BuddyboxLogicalNameError as exc:
        return _reject_logical_name(action=action, active_buddy=active_buddy, message=str(exc))

    recursive = bool(args.get("recursive", False))
    limit = args.get("limit")
    limit_value = limit if isinstance(limit, int) and limit > 0 else 200

    files = buddybox_repo.list_private_file_summaries(
        root=root,
        active_buddy=active_buddy,
        recursive=recursive,
        limit=limit_value,
        logical_prefix=prefix,
    )

    return tool_responses.success(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Listed {len(files)} private file summary row(s).",
        state_changed=False,
        durability="none",
        read_scope="active-buddy private file summaries",
        allowed_next_actions=[],
        allowed_next_action_options=_list_options(),
        extra={
            **_private_file_state_fields(),
            "files": files,
            "available_affordances": _available_affordances("list", include_artifact=True),
        },
    )


def read_buddybox_for_active_buddy(*, args: dict[str, Any], context: BuddyboxServiceContext) -> dict[str, Any]:
    action = "buddybox.read"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    root, boundary_error = _active_root_for_request(action=action, active_buddy=active_buddy, context=context)
    if boundary_error is not None:
        return boundary_error
    assert root is not None

    buddy_ids = _manifest_buddy_ids(context)
    try:
        logical_name = buddybox_repo.normalize_logical_name(
            args.get("logical_name"),
            active_buddy=active_buddy,
            buddy_ids=buddy_ids,
        )
    except buddybox_repo.BuddyboxLogicalNameError as exc:
        return _reject_logical_name(action=action, active_buddy=active_buddy, message=str(exc))

    preferred = args.get("encoding")
    encoding = "auto"
    if isinstance(preferred, str) and preferred.strip():
        encoding = preferred.strip().lower()
        if encoding not in {"auto", "utf-8", "base64"}:
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message="encoding must be auto, utf-8, or base64",
                correctable_fields=["encoding"],
            )

    try:
        raw, content_type = buddybox_repo.read_private_file(root=root, logical_name=logical_name)
    except FileNotFoundError:
        return _reject_not_found(action=action, active_buddy=active_buddy, logical_name=logical_name)
    except buddybox_repo.BuddyboxBoundaryError as exc:
        return _reject_boundary(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
        )
    payload: dict[str, Any] = {
        **_private_file_state_fields(logical_name),
        "size_bytes": len(raw),
        "content_type": content_type,
        "private_to_buddy": active_buddy,
    }

    if encoding == "base64":
        payload["encoding"] = "base64"
        payload["content_base64"] = base64.b64encode(raw).decode("ascii")
    else:
        try:
            payload["content"] = raw.decode("utf-8")
            payload["encoding"] = "utf-8"
        except UnicodeDecodeError:
            payload["encoding"] = "base64"
            payload["content_base64"] = base64.b64encode(raw).decode("ascii")

    payload["available_affordances"] = _available_affordances("read", include_artifact=True)

    return tool_responses.success(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"Read one private file '{logical_name}' and returned file body as content or content_base64.",
        state_changed=False,
        durability="none",
        read_scope="one active-buddy private file content",
        allowed_next_actions=[],
        allowed_next_action_options=_read_options(),
        extra=payload,
    )


def write_buddybox_for_active_buddy(*, args: dict[str, Any], context: BuddyboxServiceContext) -> dict[str, Any]:
    action = "buddybox.write"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    root, boundary_error = _active_root_for_request(action=action, active_buddy=active_buddy, context=context)
    if boundary_error is not None:
        return boundary_error
    assert root is not None

    buddy_ids = _manifest_buddy_ids(context)
    try:
        logical_name = buddybox_repo.normalize_logical_name(
            args.get("logical_name"),
            active_buddy=active_buddy,
            buddy_ids=buddy_ids,
        )
    except buddybox_repo.BuddyboxLogicalNameError as exc:
        return _reject_logical_name(action=action, active_buddy=active_buddy, message=str(exc))

    content = args.get("content")
    content_base64 = args.get("content_base64")
    if (content is None and content_base64 is None) or (content is not None and content_base64 is not None):
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="provide exactly one of content or content_base64",
            correctable_fields=["content", "content_base64"],
        )

    if content is not None:
        if not isinstance(content, str):
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message="content must be a string",
                correctable_fields=["content"],
            )
        raw = content.encode("utf-8")
    else:
        if not isinstance(content_base64, str) or not content_base64.strip():
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message="content_base64 must be a non-empty string",
                correctable_fields=["content_base64"],
            )
        try:
            raw = base64.b64decode(content_base64.encode("ascii"), validate=True)
        except Exception:
            return _reject_payload(
                action=action,
                active_buddy=active_buddy,
                message="content_base64 must be valid base64",
                correctable_fields=["content_base64"],
            )

    try:
        existed, inferred_content_type = buddybox_repo.write_private_file(
            root=root,
            logical_name=logical_name,
            content=raw,
        )
    except IsADirectoryError:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="logical_name points to a directory, not a file",
            correctable_fields=["logical_name"],
        )
    except buddybox_repo.BuddyboxBoundaryError as exc:
        return _reject_boundary(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
        )

    content_type = args.get("content_type")
    if not isinstance(content_type, str) or not content_type.strip():
        content_type = inferred_content_type

    payload = {
        **_private_file_state_fields(logical_name),
        "size_bytes": len(raw),
        "content_type": content_type,
        "private_to_buddy": active_buddy,
        "created": not existed,
        "overwrote": existed,
        "available_affordances": _available_affordances("write", include_artifact=True),
    }

    change_word = "overwrote" if existed else "created"
    return tool_responses.success(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        effect_summary=f"{change_word.capitalize()} one private file '{logical_name}'.",
        state_changed=True,
        durability="active_instance_local",
        created_ids=[logical_name] if not existed else None,
        updated_ids=[logical_name] if existed else None,
        state_changes=[
            {
                "object_type": "private_file",
                "change": "overwritten" if existed else "created",
                "logical_name": logical_name,
            }
        ],
        allowed_next_actions=[],
        allowed_next_action_options=_write_options(),
        extra=payload,
    )


def delete_buddybox_for_active_buddy(*, args: dict[str, Any], context: BuddyboxServiceContext) -> dict[str, Any]:
    action = "buddybox.delete"
    active_buddy = context["active_buddy"]
    payload_error = _require_allowed_fields(action, args, active_buddy)
    if payload_error is not None:
        return payload_error

    root, boundary_error = _active_root_for_request(action=action, active_buddy=active_buddy, context=context)
    if boundary_error is not None:
        return boundary_error
    assert root is not None

    buddy_ids = _manifest_buddy_ids(context)
    try:
        logical_name = buddybox_repo.normalize_logical_name(
            args.get("logical_name"),
            active_buddy=active_buddy,
            buddy_ids=buddy_ids,
        )
    except buddybox_repo.BuddyboxLogicalNameError as exc:
        return _reject_logical_name(action=action, active_buddy=active_buddy, message=str(exc))

    try:
        deleted = buddybox_repo.delete_private_file(root=root, logical_name=logical_name)
    except IsADirectoryError:
        return _reject_payload(
            action=action,
            active_buddy=active_buddy,
            message="logical_name points to a directory, not a file",
            correctable_fields=["logical_name"],
        )
    except buddybox_repo.BuddyboxBoundaryError as exc:
        return _reject_boundary(
            action=action,
            active_buddy=active_buddy,
            message=str(exc),
        )

    payload = {
        **_private_file_state_fields(logical_name),
        "deleted": deleted,
        "private_to_buddy": active_buddy,
        "available_affordances": _available_affordances("delete", include_artifact=False),
    }

    return tool_responses.success(
        tool="buddybox",
        action=action,
        active_buddy=active_buddy,
        effect_summary=(
            f"Deleted private file '{logical_name}'."
            if deleted
            else f"Private file '{logical_name}' was already absent."
        ),
        state_changed=deleted,
        durability="active_instance_local" if deleted else "none",
        updated_ids=[logical_name] if deleted else None,
        state_changes=[
            {
                "object_type": "private_file",
                "change": "deleted" if deleted else "already_absent",
                "logical_name": logical_name,
            }
        ],
        allowed_next_actions=[],
        allowed_next_action_options=_delete_options(),
        extra=payload,
    )
