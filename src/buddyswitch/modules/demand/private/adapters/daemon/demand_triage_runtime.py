"""Host-authorized application operation for Demand ingress resolution."""

from __future__ import annotations

import hashlib
from pathlib import Path
import secrets
import sys
from typing import Any, Mapping



from buddyswitch.launcher import side_thread_registry  # noqa: E402
from buddyswitch.env.services import messages as message_service  # noqa: E402
from buddyswitch.modules.demand.private.domain import demand_sys  # noqa: E402


PURPOSE = "demand-triage"


class DemandTriageRuntimeError(RuntimeError):
    """A stable runtime authorization or coordination failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retriable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retriable = retriable


def hash_capability(capability: Any) -> str:
    if not isinstance(capability, str) or not capability.strip():
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_CAPABILITY",
            "Demand triage capability is required",
        )
    return (
        "sha256:"
        + hashlib.sha256(capability.strip().encode("utf-8")).hexdigest()
    )


def mint_capability() -> tuple[str, str]:
    token = "dtriage-" + secrets.token_urlsafe(32)
    return token, hash_capability(token)


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_AUTHORITY",
            f"{field} is required",
        )
    return value.strip()


def _instance_identity(
    instance_record: Mapping[str, Any],
) -> tuple[dict[str, str], str]:
    actor_id = _required_text(instance_record.get("actor_id"), "actor_id")
    role_id = _required_text(instance_record.get("role"), "role")
    main_thread_id = _required_text(
        instance_record.get("thread_id"),
        "thread_id",
    )
    if instance_record.get("status") != "active":
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_AUTHORITY",
            "Demand triage requires an active actor instance",
        )
    return {"actor_id": actor_id, "role_id": role_id}, main_thread_id


def _capability_lease(
    *,
    instance_json: Path,
    actor_id: str,
    main_thread_id: str,
    actual_thread_id: str,
    capability_hash: str,
) -> dict[str, Any]:
    rows = side_thread_registry.find_side_threads_by_capability_hash(
        instance_json,
        actor_id=actor_id,
        capability_hash=capability_hash,
    )
    if not rows:
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_CAPABILITY",
            "Demand triage capability is unknown or revoked",
        )
    if len(rows) != 1:
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_AUTHORITY",
            "Demand triage capability does not identify exactly one side lease",
        )
    row = rows[0]
    if row.get("capability_state") == "consumed":
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_CAPABILITY_CONSUMED",
            "Demand triage capability was already consumed",
        )
    if row.get("capability_state") != "open":
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_CAPABILITY",
            "Demand triage capability is not open",
        )
    side_thread_id = row.get("thread_id")
    if (
        row.get("parent_thread_id") != main_thread_id
        or side_thread_id == main_thread_id
        or row.get("purpose") != PURPOSE
        or side_thread_id != actual_thread_id
    ):
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_AUTHORITY",
            "Demand triage capability is bound to the wrong thread purpose",
        )
    binding = row.get("binding")
    if not isinstance(binding, Mapping):
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_AUTHORITY",
            "Demand triage capability is missing its ingress binding",
        )
    _required_text(side_thread_id, "side_thread_id")
    _required_text(binding.get("source_key"), "binding.source_key")
    _required_text(binding.get("attempt_id"), "binding.attempt_id")
    return row


def _receipt_binding(
    *,
    actor_target: Mapping[str, Any],
    row: Mapping[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    binding = row["binding"]
    source_key = _required_text(binding.get("source_key"), "binding.source_key")
    attempt_id = _required_text(binding.get("attempt_id"), "binding.attempt_id")
    try:
        receipt = demand_sys.get_ingress_receipt(actor_target, source_key)
    except demand_sys.DemandError as exc:
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_AUTHORITY",
            "Demand triage source binding is not owned by this actor",
        ) from exc
    if receipt.get("attempt_id") != attempt_id:
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_AUTHORITY",
            "Demand triage attempt binding changed",
        )
    if receipt.get("state") not in {"resolving", "settled"}:
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_AUTHORITY",
            f"Demand triage receipt is not resolvable: {receipt.get('state')!r}",
        )
    return source_key, attempt_id, receipt


def _handled_source(
    *,
    actor_id: str,
    receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    fact = receipt.get("fact")
    refs = fact.get("source_refs") if isinstance(fact, Mapping) else None
    if not isinstance(refs, list) or len(refs) != 1:
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_HANDLED",
            "handled requires exactly one IM source",
        )
    source = refs[0]
    ref = source.get("ref") if isinstance(source, Mapping) else None
    if source.get("type") != "im.message.created" or not isinstance(ref, Mapping):
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_HANDLED",
            "handled is available only for an IM message source",
        )
    message_id = _required_text(ref.get("message_id"), "source.message_id")
    conversation_id = _required_text(
        ref.get("conversation_id"),
        "source.conversation_id",
    )
    response = message_service.get_im_message(
        identity={"id": actor_id, "type": "actor"},
        message_id=message_id,
    )
    if response.get("ok") is not True:
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_HANDLED",
            "handled source Message is not visible to the actor",
        )
    message = response["message"]
    if (
        message.get("conversation_id") != conversation_id
        or message.get("target_identity")
        != {"id": actor_id, "type": "actor"}
    ):
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_HANDLED",
            "handled source Message does not match the actor binding",
        )
    sender = message.get("sender_identity")
    if not isinstance(sender, Mapping):
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_HANDLED",
            "handled source Message sender is invalid",
        )
    return message, {
        "id": _required_text(sender.get("id"), "source.sender.id"),
        "type": _required_text(sender.get("type"), "source.sender.type"),
    }


def _verify_reply(
    *,
    actor_id: str,
    source_message: Mapping[str, Any],
    target: Mapping[str, str],
    reply: Mapping[str, Any],
) -> bool:
    return (
        reply.get("reply_to") == source_message.get("id")
        and reply.get("conversation_id") == source_message.get("conversation_id")
        and reply.get("sender_identity")
        == {"id": actor_id, "type": "actor"}
        and reply.get("target_identity") == dict(target)
    )


def _ensure_handled_reply(
    *,
    actor_id: str,
    receipt: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> str:
    content = _required_text(proposal.get("reply_content"), "reply_content")
    source_message, target = _handled_source(
        actor_id=actor_id,
        receipt=receipt,
    )
    replies = message_service.list_im_replies(
        identity={"id": actor_id, "type": "actor"},
        message_id=str(source_message["id"]),
    )
    if replies.get("ok") is not True:
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_HANDLED",
            "failed to inspect replies for the handled source",
            retriable=True,
        )
    for reply in replies.get("replies", []):
        if isinstance(reply, Mapping) and _verify_reply(
            actor_id=actor_id,
            source_message=source_message,
            target=target,
            reply=reply,
        ):
            return _required_text(reply.get("id"), "reply.id")

    sent = message_service.send_im_message(
        sender_identity={"id": actor_id, "type": "actor"},
        target_identity=dict(target),
        content=content,
        reply_to=str(source_message["id"]),
    )
    if sent.get("ok") is not True:
        error = sent.get("error")
        message = (
            error.get("message")
            if isinstance(error, Mapping)
            and isinstance(error.get("message"), str)
            else "Message owner rejected the handled reply"
        )
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_HANDLED",
            message,
            retriable=True,
        )
    message_id = _required_text(
        sent.get("message", {}).get("id")
        if isinstance(sent.get("message"), Mapping)
        else None,
        "reply.id",
    )
    stored = message_service.get_im_message(
        identity={"id": actor_id, "type": "actor"},
        message_id=message_id,
    )
    reply = stored.get("message") if stored.get("ok") is True else None
    if not isinstance(reply, Mapping) or not _verify_reply(
        actor_id=actor_id,
        source_message=source_message,
        target=target,
        reply=reply,
    ):
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_HANDLED",
            "Message owner did not persist the exact handled reply",
            retriable=True,
        )
    return message_id


def resolve_request(
    *,
    instance_json: Path,
    instance_record: Mapping[str, Any],
    capability: Any,
    actual_thread_id: Any,
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(proposal, Mapping):
        raise DemandTriageRuntimeError(
            "E_DEMAND_TRIAGE_PAYLOAD",
            "Demand triage proposal must be an object",
        )
    resolved_thread_id = _required_text(
        actual_thread_id,
        "actual_thread_id",
    )
    capability_hash = hash_capability(capability)
    actor_target, main_thread_id = _instance_identity(instance_record)
    row = _capability_lease(
        instance_json=Path(instance_json),
        actor_id=actor_target["actor_id"],
        main_thread_id=main_thread_id,
        actual_thread_id=resolved_thread_id,
        capability_hash=capability_hash,
    )
    source_key, attempt_id, receipt = _receipt_binding(
        actor_target=actor_target,
        row=row,
    )
    normalized_proposal = demand_sys.validate_ingress_proposal(proposal)
    handled_message_id: str | None = None
    if normalized_proposal["decision"] == "handled":
        handled_message_id = _ensure_handled_reply(
            actor_id=actor_target["actor_id"],
            receipt=receipt,
            proposal=normalized_proposal,
        )
    result = demand_sys.resolve_ingress(
        actor_target,
        source_key,
        attempt_id,
        normalized_proposal,
        handled_verified=handled_message_id is not None,
    )
    side_thread_registry.consume_side_thread_capability(
        Path(instance_json),
        actor_id=actor_target["actor_id"],
        side_thread_id=str(row["thread_id"]),
        capability_hash=capability_hash,
    )
    response = dict(result)
    response["ingress_state_changed"] = bool(result.get("state_changed"))
    response["state_changed"] = True
    response["lease_consumed"] = True
    if handled_message_id is not None:
        response["handled_message_id"] = handled_message_id
    return response
