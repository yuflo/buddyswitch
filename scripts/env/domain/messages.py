#!/usr/bin/env python3
"""Message domain rules for payload/scope validation and inbox filtering."""

from __future__ import annotations

from typing import Any, Callable, Optional, TypedDict


class MessagePayloadError(ValueError):
    def __init__(self, message: str, *, correctable_fields: list[str] | None = None) -> None:
        super().__init__(message)
        self.correctable_fields = correctable_fields


class MessageScopeError(ValueError):
    def __init__(
        self,
        *,
        message: str,
        permission_boundary: str,
        human_summary: str,
        why_blocked: str,
        retryable: bool = True,
        correctable_fields: list[str] | None = None,
        code: str = "E_MESSAGE_SCOPE",
    ) -> None:
        super().__init__(message)
        self.permission_boundary = permission_boundary
        self.human_summary = human_summary
        self.why_blocked = why_blocked
        self.retryable = retryable
        self.correctable_fields = correctable_fields
        self.code = code


class SendRequest(TypedDict):
    to_buddy: str
    content: str
    reply_to: str | None


class ListRequest(TypedDict):
    buddy: str | None


GetMessage = Callable[[str], Optional[dict[str, Any]]]


def manifest_buddy_ids(manifest: dict[str, Any] | None) -> set[str]:
    if not isinstance(manifest, dict):
        return set()
    buddies = manifest.get("buddies")
    if not isinstance(buddies, list):
        return set()
    return {
        buddy.get("id")
        for buddy in buddies
        if isinstance(buddy, dict) and isinstance(buddy.get("id"), str) and buddy.get("id")
    }


def ensure_active_buddy_is_manifest_declared(*, active_buddy: str, manifest_buddy_ids: set[str]) -> None:
    if active_buddy in manifest_buddy_ids:
        return
    raise MessageScopeError(
        message=f"active buddy '{active_buddy}' is not declared in manifest",
        permission_boundary="message.manifest_buddy",
        human_summary="Active buddy is not part of the manifest-declared message scope.",
        why_blocked="message actions require active_buddy to be declared in manifest.buddies.",
        retryable=False,
        correctable_fields=None,
    )


def _message_visible_to_active(message: dict[str, Any], active_buddy: str) -> bool:
    return message.get("from_buddy") == active_buddy or message.get("to_buddy") == active_buddy


def _same_pair(message: dict[str, Any], active_buddy: str, to_buddy: str) -> bool:
    participants = {message.get("from_buddy"), message.get("to_buddy")}
    return participants == {active_buddy, to_buddy}


def prepare_send_request(
    *,
    args: dict[str, Any],
    active_buddy: str,
    manifest_buddy_ids: set[str],
    get_message: GetMessage,
    allowed_fields: set[str],
) -> SendRequest:
    unknown = sorted(key for key in args if key not in allowed_fields)
    if unknown:
        raise MessagePayloadError(
            f"unsupported payload fields: {', '.join(unknown)}",
            correctable_fields=unknown,
        )

    to_buddy = args.get("to_buddy")
    if not isinstance(to_buddy, str) or not to_buddy.strip():
        raise MessagePayloadError("to_buddy must be a non-empty string", correctable_fields=["to_buddy"])
    to_buddy = to_buddy.strip()
    if to_buddy not in manifest_buddy_ids:
        raise MessagePayloadError(f"unknown target buddy: {to_buddy}", correctable_fields=["to_buddy"])
    if to_buddy == active_buddy:
        raise MessageScopeError(
            message="cannot send a message to yourself",
            permission_boundary="message.self_send",
            human_summary="Self-send messages are not allowed.",
            why_blocked="message.send requires distinct sender and recipient buddies.",
            retryable=True,
            correctable_fields=["to_buddy"],
        )

    content = args.get("content")
    if not isinstance(content, str) or not content.strip():
        raise MessagePayloadError(
            "content must be a non-empty string after trimming",
            correctable_fields=["content"],
        )
    content = content.strip()

    reply_to = args.get("reply_to")
    reply_to_id: str | None = None
    if reply_to is not None:
        if not isinstance(reply_to, str) or not reply_to.strip():
            raise MessagePayloadError(
                "reply_to must be a non-empty string when provided",
                correctable_fields=["reply_to"],
            )
        reply_to_id = reply_to.strip()
        referenced = get_message(reply_to_id)
        if referenced is None:
            raise MessageScopeError(
                message=f"reply_to references a message that does not exist: {reply_to_id}",
                permission_boundary="message.reply_to_scope",
                human_summary="The referenced message was not found.",
                why_blocked="reply_to must reference an existing message.",
                retryable=True,
                correctable_fields=["reply_to"],
            )
        if not _message_visible_to_active(referenced, active_buddy):
            raise MessageScopeError(
                message=f"reply_to message '{reply_to_id}' is not visible to active buddy",
                permission_boundary="message.reply_to_scope",
                human_summary="Active buddy is not a participant in the referenced conversation.",
                why_blocked="Active buddy must be a participant in the referenced message conversation.",
                retryable=True,
                correctable_fields=["reply_to"],
            )
        if not _same_pair(referenced, active_buddy, to_buddy):
            raise MessageScopeError(
                message=f"reply_to message '{reply_to_id}' is from a different conversation pair",
                permission_boundary="message.reply_to_scope",
                human_summary="Reply must stay in the same two-buddy conversation.",
                why_blocked="reply_to must reference a message in the same {active_buddy, to_buddy} conversation.",
                retryable=True,
                correctable_fields=["reply_to", "to_buddy"],
            )

    return {
        "to_buddy": to_buddy,
        "content": content,
        "reply_to": reply_to_id,
    }


def prepare_list_request(*, args: dict[str, Any], manifest_buddy_ids: set[str], allowed_fields: set[str]) -> ListRequest:
    unknown = sorted(key for key in args if key not in allowed_fields)
    if unknown:
        raise MessagePayloadError(
            f"unsupported payload fields: {', '.join(unknown)}",
            correctable_fields=unknown,
        )

    buddy_filter = args.get("buddy")
    if buddy_filter is None:
        return {"buddy": None}
    if not isinstance(buddy_filter, str):
        raise MessagePayloadError("buddy must be a non-empty string when provided", correctable_fields=["buddy"])
    normalized = buddy_filter.strip()
    if not normalized:
        return {"buddy": None}
    if normalized not in manifest_buddy_ids:
        raise MessagePayloadError(f"unknown buddy filter: {normalized}", correctable_fields=["buddy"])
    return {"buddy": normalized}


def filter_inbox_messages(
    *,
    messages: list[dict[str, Any]],
    active_buddy: str,
    sender_buddy: str | None = None,
) -> list[dict[str, Any]]:
    inbox = [message for message in messages if message.get("to_buddy") == active_buddy]
    if sender_buddy is not None:
        inbox = [message for message in inbox if message.get("from_buddy") == sender_buddy]
    return inbox
