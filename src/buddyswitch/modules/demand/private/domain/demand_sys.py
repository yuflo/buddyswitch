"""Canonical actor-owned Demand and private ingress-resolution owner."""

from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping
from uuid import uuid4

import buddyswitch.foundation.state.runtime as state_runtime
from buddyswitch.modules.demand.private.state import demands


TERMINAL_TYPES = ("completed", "canceled")
TRIAGE_DECISIONS = (
    "no_action_needed",
    "handled",
    "create",
    "merge_intake",
    "revise",
    "cancel",
)
INGRESS_RECEIPT_STATES = ("pending", "resolving", "settled", "failed")
_DEMAND_FIELDS = {
    "id",
    "description",
    "detail",
    "source_refs",
    "revision",
    "terminal",
    "created_at",
    "updated_at",
}
_INGRESS_RECEIPT_FIELDS = {
    "fingerprint",
    "fact",
    "state",
    "attempt_id",
    "outcome",
    "last_failure",
    "created_at",
    "updated_at",
}


class DemandError(ValueError):
    code = "E_DEMAND"


class DemandNotFound(DemandError):
    code = "E_DEMAND_NOT_FOUND"


class DemandRevisionConflict(DemandError):
    code = "E_DEMAND_REVISION_CONFLICT"


class DemandIngressConflict(DemandError):
    code = "E_DEMAND_INGRESS_CONFLICT"


class DemandTerminalConflict(DemandError):
    code = "E_DEMAND_TERMINAL"


class DemandPayloadError(DemandError):
    code = "E_DEMAND_PAYLOAD"


def _payload_error(message: str) -> DemandPayloadError:
    return DemandPayloadError(message)


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _payload_error(f"{field} must be an object")
    return value


def _require_exact_fields(
    value: Mapping[str, Any],
    fields: set[str],
    field: str,
) -> None:
    if set(value) != fields:
        expected = ", ".join(sorted(fields))
        raise _payload_error(f"{field} must contain exactly: {expected}")


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _payload_error(f"{field} must be a non-empty string")
    return value.strip()


def _require_revision(value: Any, field: str = "revision") -> int:
    if type(value) is not int or value < 1:
        raise _payload_error(f"{field} must be a positive integer")
    return value


def _require_id(value: Any, prefix: str, field: str) -> str:
    if not isinstance(value, str) or not value.startswith(prefix):
        raise _payload_error(f"{field} must start with {prefix}")
    try:
        return state_runtime.require_id(value, field)
    except ValueError as exc:
        raise _payload_error(str(exc)) from exc


def _require_demand_id(value: Any, field: str = "demand_id") -> str:
    return _require_id(value, "demand-", field)


def _require_attempt_id(value: Any, field: str = "attempt_id") -> str:
    return _require_id(value, "attempt-", field)


def _json_object_copy(value: Any, field: str) -> dict[str, Any]:
    row = _require_mapping(value, field)
    if not all(isinstance(key, str) for key in row):
        raise _payload_error(f"{field} keys must be strings")
    copied = deepcopy(dict(row))
    try:
        json.dumps(copied, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise _payload_error(f"{field} must contain JSON-compatible values") from exc
    return copied


def _normalize_refs(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise _payload_error(f"{field} must be a list")
    refs: list[dict[str, Any]] = []
    for index, raw_ref in enumerate(value):
        ref = _require_mapping(raw_ref, f"{field}[{index}]")
        _require_exact_fields(ref, {"type", "ref"}, f"{field}[{index}]")
        normalized = {
            "type": _require_text(ref.get("type"), f"{field}[{index}].type"),
            "ref": _json_object_copy(ref.get("ref"), f"{field}[{index}].ref"),
        }
        if normalized not in refs:
            refs.append(normalized)
    return refs


def _merge_refs(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for group in groups:
        for ref in group:
            if ref not in merged:
                merged.append(deepcopy(ref))
    return merged


def _normalized_ingress_fact(
    description: Any,
    detail: Any,
    source_refs: Any,
) -> dict[str, Any]:
    return {
        "description": _require_text(description, "description"),
        "detail": _require_text(detail, "detail"),
        "source_refs": _normalize_refs(source_refs, "source_refs"),
    }


def _ingress_fingerprint(fact: Mapping[str, Any]) -> str:
    body = json.dumps(
        dict(fact),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _normalize_ingress_receipt(value: Any) -> dict[str, Any]:
    receipt = _require_mapping(value, "ingress receipt")
    _require_exact_fields(receipt, _INGRESS_RECEIPT_FIELDS, "ingress receipt")
    fingerprint = _require_text(
        receipt.get("fingerprint"),
        "ingress receipt.fingerprint",
    )
    if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
        raise _payload_error(
            "ingress receipt.fingerprint must be a lowercase sha256 hex digest"
        )
    fact = _require_mapping(receipt.get("fact"), "ingress receipt.fact")
    _require_exact_fields(
        fact,
        {"description", "detail", "source_refs"},
        "ingress receipt.fact",
    )
    normalized_fact = _normalized_ingress_fact(
        fact.get("description"),
        fact.get("detail"),
        fact.get("source_refs"),
    )
    if _ingress_fingerprint(normalized_fact) != fingerprint:
        raise _payload_error("ingress receipt fingerprint does not match its fact")
    state = receipt.get("state")
    if state not in INGRESS_RECEIPT_STATES:
        raise _payload_error(
            "ingress receipt.state must be one of "
            + ", ".join(INGRESS_RECEIPT_STATES)
        )
    attempt_id = receipt.get("attempt_id")
    if attempt_id is not None:
        attempt_id = _require_attempt_id(
            attempt_id,
            "ingress receipt.attempt_id",
        )
    outcome = receipt.get("outcome")
    if outcome is not None:
        outcome = _json_object_copy(outcome, "ingress receipt.outcome")
    last_failure = receipt.get("last_failure")
    if last_failure is not None:
        last_failure = _json_object_copy(
            last_failure,
            "ingress receipt.last_failure",
        )
    if state == "pending" and (attempt_id is not None or outcome is not None):
        raise _payload_error(
            "pending ingress receipt must not contain attempt_id or outcome"
        )
    if state == "resolving" and (attempt_id is None or outcome is not None):
        raise _payload_error(
            "resolving ingress receipt requires attempt_id and no outcome"
        )
    if state == "settled" and (attempt_id is None or outcome is None):
        raise _payload_error(
            "settled ingress receipt requires attempt_id and outcome"
        )
    if state == "failed" and (attempt_id is not None or outcome is not None):
        raise _payload_error(
            "failed ingress receipt must not contain attempt_id or outcome"
        )
    return {
        "fingerprint": fingerprint,
        "fact": normalized_fact,
        "state": state,
        "attempt_id": attempt_id,
        "outcome": outcome,
        "last_failure": last_failure,
        "created_at": _require_text(
            receipt.get("created_at"),
            "ingress receipt.created_at",
        ),
        "updated_at": _require_text(
            receipt.get("updated_at"),
            "ingress receipt.updated_at",
        ),
    }


def _normalize_terminal(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    terminal = _require_mapping(value, "demand.terminal")
    terminal_type = terminal.get("type")
    if terminal_type not in TERMINAL_TYPES:
        raise _payload_error(
            f"demand.terminal.type must be one of {', '.join(TERMINAL_TYPES)}"
        )
    if terminal_type == "completed":
        fields = {"type", "at", "summary", "evidence_refs"}
    else:
        fields = {"type", "at", "summary"}
    _require_exact_fields(terminal, fields, "demand.terminal")
    normalized: dict[str, Any] = {
        "type": terminal_type,
        "at": _require_text(terminal.get("at"), "demand.terminal.at"),
        "summary": _require_text(terminal.get("summary"), "demand.terminal.summary"),
    }
    if terminal_type == "completed":
        normalized["evidence_refs"] = _normalize_refs(
            terminal.get("evidence_refs"),
            "demand.terminal.evidence_refs",
        )
    return normalized


def _normalize_demand(value: Any) -> dict[str, Any]:
    record = _require_mapping(value, "demand")
    _require_exact_fields(record, _DEMAND_FIELDS, "demand")
    return {
        "id": _require_demand_id(record.get("id"), "demand.id"),
        "description": _require_text(record.get("description"), "demand.description"),
        "detail": _require_text(record.get("detail"), "demand.detail"),
        "source_refs": _normalize_refs(record.get("source_refs"), "demand.source_refs"),
        "revision": _require_revision(record.get("revision"), "demand.revision"),
        "terminal": _normalize_terminal(record.get("terminal")),
        "created_at": _require_text(record.get("created_at"), "demand.created_at"),
        "updated_at": _require_text(record.get("updated_at"), "demand.updated_at"),
    }


def _normalize_ingress_proposal(value: Any) -> dict[str, Any]:
    proposal = _require_mapping(value, "proposal")
    fields = {
        "decision",
        "reason",
        "demand_ref",
        "description",
        "detail",
        "reply_content",
    }
    _require_exact_fields(proposal, fields, "proposal")
    decision = proposal.get("decision")
    if decision not in TRIAGE_DECISIONS:
        raise _payload_error(
            f"proposal.decision must be one of {', '.join(TRIAGE_DECISIONS)}"
        )
    applicable: set[str] = set()
    if decision == "handled":
        applicable.add("reply_content")
    elif decision == "create":
        applicable.update({"description", "detail"})
    elif decision in {"merge_intake", "revise"}:
        applicable.update({"demand_ref", "description", "detail"})
    elif decision == "cancel":
        applicable.add("demand_ref")
    normalized: dict[str, Any] = {
        "decision": decision,
        "reason": _require_text(proposal.get("reason"), "proposal.reason"),
        "demand_ref": None,
        "description": None,
        "detail": None,
        "reply_content": None,
    }
    for field in ("demand_ref", "description", "detail", "reply_content"):
        if field in applicable:
            normalized[field] = _require_text(
                proposal.get(field),
                f"proposal.{field}",
            )
        elif proposal.get(field) is not None:
            raise _payload_error(
                f"proposal.{field} must be null for {decision}"
            )
    return normalized


def validate_ingress_proposal(value: Any) -> dict[str, Any]:
    """Return the Demand-owned canonical proposal before any external effect."""

    return _normalize_ingress_proposal(value)


def _records(state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_records = state.get("demands")
    if not isinstance(raw_records, Mapping):
        raise _payload_error("Demand actor aggregate demands must be an object")
    normalized: dict[str, dict[str, Any]] = {}
    for indexed_id, raw_record in raw_records.items():
        demand_id = _require_demand_id(indexed_id, "Demand aggregate key")
        record = _normalize_demand(raw_record)
        if record["id"] != demand_id:
            raise _payload_error("Demand aggregate key must match demand.id")
        normalized[demand_id] = record
    return normalized


def _ingress_receipts(state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_receipts = state.get("ingress_receipts")
    if not isinstance(raw_receipts, Mapping):
        raise _payload_error(
            "Demand actor aggregate ingress_receipts must be an object"
        )
    normalized: dict[str, dict[str, Any]] = {}
    for raw_source_key, raw_receipt in raw_receipts.items():
        source_key = _require_text(raw_source_key, "ingress receipt source key")
        normalized[source_key] = _normalize_ingress_receipt(raw_receipt)
    return normalized


def _new_id(prefix: str, occupied: Mapping[str, Any]) -> str:
    while True:
        identifier = f"{prefix}-{uuid4().hex[:12]}"
        if identifier not in occupied:
            return identifier


def _find_demand(
    records: Mapping[str, dict[str, Any]],
    demand_id: str,
) -> dict[str, Any]:
    record = records.get(demand_id)
    if record is None:
        raise DemandNotFound(f"Demand not found: {demand_id}")
    return record


def _require_live(record: Mapping[str, Any]) -> None:
    if record["terminal"] is not None:
        raise DemandTerminalConflict(f"Demand {record['id']} is terminal")


def _encode_ref(demand_id: str, revision: int) -> str:
    body = json.dumps(
        {"demand_id": demand_id, "revision": revision},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(body).decode("ascii").rstrip("=")
    checksum = hashlib.sha256(body).hexdigest()[:16]
    return f"dref-{encoded}.{checksum}"


def _decode_ref(value: Any) -> tuple[str, int]:
    token = _require_text(value, "demand_ref")
    if not token.startswith("dref-") or "." not in token:
        raise _payload_error("demand_ref must be an opaque Demand reference")
    encoded, checksum = token[len("dref-"):].rsplit(".", 1)
    try:
        padding = "=" * (-len(encoded) % 4)
        body = base64.urlsafe_b64decode((encoded + padding).encode("ascii"))
        payload = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise _payload_error("demand_ref is invalid") from exc
    if hashlib.sha256(body).hexdigest()[:16] != checksum:
        raise _payload_error("demand_ref checksum is invalid")
    row = _require_mapping(payload, "demand_ref payload")
    _require_exact_fields(
        row,
        {"demand_id", "revision"},
        "demand_ref payload",
    )
    return (
        _require_demand_id(row.get("demand_id"), "demand_ref demand_id"),
        _require_revision(row.get("revision"), "demand_ref revision"),
    )


def _project_with_ref(record: Mapping[str, Any]) -> dict[str, Any]:
    projected = deepcopy(dict(record))
    projected["demand_ref"] = _encode_ref(
        str(record["id"]),
        int(record["revision"]),
    )
    return projected


def resolve_demand_ref(
    actor_target: Mapping[str, Any],
    demand_ref: Any,
    *,
    require_live: bool = True,
) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    demand_id, basis_revision = _decode_ref(demand_ref)
    record = _find_demand(
        _records(demands.load_actor_state(normalized_target)),
        demand_id,
    )
    if record["revision"] != basis_revision:
        raise DemandRevisionConflict(
            f"Demand {demand_id} changed after this demand_ref was read"
        )
    if require_live:
        _require_live(record)
    return {
        "demand_id": demand_id,
        "basis_revision": basis_revision,
        "demand_ref": _encode_ref(demand_id, basis_revision),
    }


def _new_demand_record(
    records: Mapping[str, Any],
    *,
    description: str,
    detail: str,
    source_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    now = state_runtime.now_iso()
    return {
        "id": _new_id("demand", records),
        "description": description,
        "detail": detail,
        "source_refs": deepcopy(source_refs),
        "revision": 1,
        "terminal": None,
        "created_at": now,
        "updated_at": now,
    }


def _change(demand_id: str, kind: str) -> dict[str, str]:
    return {"demand_id": demand_id, "kind": kind}


def _increment_pool_revision(state: dict[str, Any]) -> int:
    current = state.get("demand_pool_revision")
    if type(current) is not int or current < 0:
        raise _payload_error(
            "Demand actor aggregate demand_pool_revision must be a non-negative integer"
        )
    next_revision = current + 1
    state["demand_pool_revision"] = next_revision
    return next_revision


def list_demands(
    actor_target: Mapping[str, Any],
    state: str = "live",
) -> list[dict[str, Any]]:
    normalized_target = demands.normalize_actor_target(actor_target)
    if state not in {"live", "terminal", "all"}:
        raise _payload_error("state must be one of live, terminal, or all")
    records = list(_records(demands.load_actor_state(normalized_target)).values())
    if state == "live":
        records = [record for record in records if record["terminal"] is None]
    elif state == "terminal":
        records = [record for record in records if record["terminal"] is not None]
    return sorted(
        (_project_with_ref(record) for record in records),
        key=lambda record: (record["created_at"], record["id"]),
    )


def get(actor_target: Mapping[str, Any], demand_id: Any) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    normalized_id = _require_demand_id(demand_id)
    record = _find_demand(
        _records(demands.load_actor_state(normalized_target)),
        normalized_id,
    )
    return _project_with_ref(record)


def _revise_record(
    stored: dict[str, Any],
    *,
    description: str,
    detail: str,
    source_refs: list[dict[str, Any]] | None = None,
) -> bool:
    merged_refs = (
        _merge_refs(stored["source_refs"], source_refs)
        if source_refs is not None
        else deepcopy(stored["source_refs"])
    )
    if (
        stored["description"] == description
        and stored["detail"] == detail
        and stored["source_refs"] == merged_refs
    ):
        return False
    stored.update(
        {
            "description": description,
            "detail": detail,
            "source_refs": merged_refs,
            "revision": int(stored["revision"]) + 1,
            "updated_at": state_runtime.now_iso(),
        }
    )
    return True


def _terminal_matches(
    record: Mapping[str, Any],
    *,
    terminal_type: str,
    summary: str,
    evidence_refs: list[dict[str, Any]] | None,
) -> bool:
    terminal = record.get("terminal")
    if not isinstance(terminal, Mapping):
        return False
    if terminal.get("type") != terminal_type or terminal.get("summary") != summary:
        return False
    if terminal_type == "completed":
        return terminal.get("evidence_refs") == evidence_refs
    return True


def _terminalize_record(
    stored: dict[str, Any],
    *,
    terminal_type: str,
    summary: str,
    evidence_refs: list[dict[str, Any]] | None,
    source_refs: list[dict[str, Any]] | None = None,
) -> None:
    now = state_runtime.now_iso()
    terminal: dict[str, Any] = {
        "type": terminal_type,
        "at": now,
        "summary": summary,
    }
    if terminal_type == "completed":
        terminal["evidence_refs"] = deepcopy(evidence_refs)
    stored.update(
        {
            "source_refs": (
                _merge_refs(stored["source_refs"], source_refs)
                if source_refs is not None
                else deepcopy(stored["source_refs"])
            ),
            "revision": int(stored["revision"]) + 1,
            "terminal": terminal,
            "updated_at": now,
        }
    )


def _terminalize(
    actor_target: Mapping[str, Any],
    demand_ref: Any,
    *,
    terminal_type: str,
    summary: Any,
    evidence_refs: Any = None,
) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    demand_id, basis_revision = _decode_ref(demand_ref)
    normalized_summary = _require_text(summary, "summary")
    normalized_evidence = (
        _normalize_refs(evidence_refs, "evidence_refs")
        if terminal_type == "completed"
        else None
    )
    if terminal_type == "completed" and not normalized_evidence:
        raise _payload_error("evidence_refs must contain at least one reference")

    def mutate(state: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        records = _records(state)
        record = _find_demand(records, demand_id)
        if record["terminal"] is not None:
            if (
                record["revision"] == basis_revision + 1
                and _terminal_matches(
                    record,
                    terminal_type=terminal_type,
                    summary=normalized_summary,
                    evidence_refs=normalized_evidence,
                )
            ):
                return False, {
                    "state_changed": False,
                    "changes": [],
                    "demand_id": demand_id,
                    "demand_ref": _encode_ref(demand_id, record["revision"]),
                    "demand_pool_revision": state["demand_pool_revision"],
                }
            raise DemandTerminalConflict(f"Demand {demand_id} is terminal")
        if record["revision"] != basis_revision:
            raise DemandRevisionConflict(
                f"Demand {demand_id} changed after this demand_ref was read"
            )
        stored = state["demands"][demand_id]
        _terminalize_record(
            stored,
            terminal_type=terminal_type,
            summary=normalized_summary,
            evidence_refs=normalized_evidence,
        )
        pool_revision = _increment_pool_revision(state)
        return True, {
            "state_changed": True,
            "changes": [_change(demand_id, terminal_type)],
            "demand_id": demand_id,
            "demand_ref": _encode_ref(demand_id, int(stored["revision"])),
            "demand_pool_revision": pool_revision,
        }

    return demands.transact_actor_state(normalized_target, mutate)


def complete(
    actor_target: Mapping[str, Any],
    demand_ref: Any,
    summary: Any,
    evidence_refs: Any,
) -> dict[str, Any]:
    return _terminalize(
        actor_target,
        demand_ref,
        terminal_type="completed",
        summary=summary,
        evidence_refs=evidence_refs,
    )


def claim_ingress(
    actor_target: Mapping[str, Any],
    source_key: Any,
    description: Any,
    detail: Any,
    source_refs: Any,
) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    normalized_source_key = _require_text(source_key, "source_key")
    normalized_fact = _normalized_ingress_fact(
        description,
        detail,
        source_refs,
    )
    fingerprint = _ingress_fingerprint(normalized_fact)

    def mutate(state: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        receipts = _ingress_receipts(state)
        existing = receipts.get(normalized_source_key)
        if existing is not None:
            if existing["fingerprint"] != fingerprint:
                raise DemandIngressConflict(
                    "Demand ingress source_key already exists with different content: "
                    f"{normalized_source_key}"
                )
            return False, {
                "state_changed": False,
                "source_key": normalized_source_key,
                "state": existing["state"],
            }
        now = state_runtime.now_iso()
        state["ingress_receipts"][normalized_source_key] = {
            "fingerprint": fingerprint,
            "fact": normalized_fact,
            "state": "pending",
            "attempt_id": None,
            "outcome": None,
            "last_failure": None,
            "created_at": now,
            "updated_at": now,
        }
        return True, {
            "state_changed": True,
            "source_key": normalized_source_key,
            "state": "pending",
        }

    return demands.transact_actor_state(normalized_target, mutate)


def get_ingress_receipt(
    actor_target: Mapping[str, Any],
    source_key: Any,
) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    normalized_source_key = _require_text(source_key, "source_key")
    receipt = _ingress_receipts(
        demands.load_actor_state(normalized_target)
    ).get(normalized_source_key)
    if receipt is None:
        raise DemandNotFound(
            f"Demand ingress receipt not found: {normalized_source_key}"
        )
    return deepcopy(receipt)


def list_unsettled_ingress(
    actor_target: Mapping[str, Any],
) -> list[dict[str, Any]]:
    normalized_target = demands.normalize_actor_target(actor_target)
    receipts = _ingress_receipts(demands.load_actor_state(normalized_target))
    return sorted(
        (
            {
                "source_key": source_key,
                **deepcopy(receipt),
            }
            for source_key, receipt in receipts.items()
            if receipt["state"] in {"pending", "resolving"}
        ),
        key=lambda receipt: (receipt["created_at"], receipt["source_key"]),
    )


def pool_snapshot(actor_target: Mapping[str, Any]) -> dict[str, int]:
    normalized_target = demands.normalize_actor_target(actor_target)
    state = demands.load_actor_state(normalized_target)
    records = _records(state)
    return {
        "demand_pool_revision": state["demand_pool_revision"],
        "live_demand_count": sum(
            1 for record in records.values() if record["terminal"] is None
        ),
    }


def begin_ingress_resolution(
    actor_target: Mapping[str, Any],
    source_key: Any,
) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    normalized_source_key = _require_text(source_key, "source_key")

    def mutate(state: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        receipt = _ingress_receipts(state).get(normalized_source_key)
        if receipt is None:
            raise DemandNotFound(
                f"Demand ingress receipt not found: {normalized_source_key}"
            )
        if receipt["state"] == "resolving":
            return False, {
                "state_changed": False,
                "source_key": normalized_source_key,
                "attempt_id": receipt["attempt_id"],
            }
        if receipt["state"] in {"settled", "failed"}:
            raise DemandTerminalConflict(
                f"Demand ingress receipt {normalized_source_key} is {receipt['state']}"
            )
        attempt_id = _new_id("attempt", {})
        state["ingress_receipts"][normalized_source_key].update(
            {
                "state": "resolving",
                "attempt_id": attempt_id,
                "outcome": None,
                "updated_at": state_runtime.now_iso(),
            }
        )
        return True, {
            "state_changed": True,
            "source_key": normalized_source_key,
            "attempt_id": attempt_id,
        }

    return demands.transact_actor_state(normalized_target, mutate)


def _apply_ingress_target_change(
    state: dict[str, Any],
    records: dict[str, dict[str, Any]],
    *,
    receipt: dict[str, Any],
    proposal: dict[str, Any],
) -> tuple[bool, dict[str, Any]] | None:
    demand_id, basis_revision = _decode_ref(proposal["demand_ref"])
    record = _find_demand(records, demand_id)
    _require_live(record)
    if record["revision"] != basis_revision:
        return None
    stored = state["demands"][demand_id]
    decision = proposal["decision"]
    if decision in {"merge_intake", "revise"}:
        changed = _revise_record(
            stored,
            description=proposal["description"],
            detail=proposal["detail"],
            source_refs=receipt["fact"]["source_refs"],
        )
        return changed, {
            "decision": decision,
            "demand_changed": changed,
            "demand_id": demand_id,
            "demand_ref": _encode_ref(demand_id, int(stored["revision"])),
        }
    if decision == "cancel":
        _terminalize_record(
            stored,
            terminal_type="canceled",
            summary=proposal["reason"],
            evidence_refs=None,
            source_refs=receipt["fact"]["source_refs"],
        )
        return True, {
            "decision": "cancel",
            "demand_changed": True,
            "demand_id": demand_id,
            "demand_ref": _encode_ref(demand_id, int(stored["revision"])),
            "reason": proposal["reason"],
        }
    raise _payload_error(f"unsupported ingress target decision: {decision}")


def resolve_ingress(
    actor_target: Mapping[str, Any],
    source_key: Any,
    attempt_id: Any,
    proposal: Any,
    *,
    handled_verified: Any,
) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    normalized_source_key = _require_text(source_key, "source_key")
    normalized_attempt_id = _require_attempt_id(attempt_id)
    normalized_proposal = _normalize_ingress_proposal(proposal)
    if type(handled_verified) is not bool:
        raise _payload_error("handled_verified must be a boolean")

    def mutate(state: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        records = _records(state)
        receipt = _ingress_receipts(state).get(normalized_source_key)
        if receipt is None:
            raise DemandNotFound(
                f"Demand ingress receipt not found: {normalized_source_key}"
            )
        if receipt["state"] == "settled":
            if receipt["attempt_id"] != normalized_attempt_id:
                raise DemandRevisionConflict(
                    f"Demand ingress receipt {normalized_source_key} resolution attempt changed"
                )
            outcome = deepcopy(receipt["outcome"])
            if not isinstance(outcome, dict):
                raise _payload_error(
                    "settled ingress receipt outcome must be an object"
                )
            return False, {
                "state_changed": False,
                "source_key": normalized_source_key,
                **outcome,
            }
        if (
            receipt["state"] != "resolving"
            or receipt["attempt_id"] != normalized_attempt_id
        ):
            raise DemandRevisionConflict(
                f"Demand ingress receipt {normalized_source_key} resolution attempt changed"
            )
        decision = normalized_proposal["decision"]
        if decision == "handled" and not handled_verified:
            raise _payload_error(
                "handled proposal requires verified source-local handling"
            )

        demand_changed = False
        outcome: dict[str, Any]
        if decision in {"no_action_needed", "handled"}:
            outcome = {
                "decision": decision,
                "demand_changed": False,
                "demand_pool_revision": state["demand_pool_revision"],
            }
        elif decision == "create":
            record = _new_demand_record(
                records,
                description=normalized_proposal["description"],
                detail=normalized_proposal["detail"],
                source_refs=receipt["fact"]["source_refs"],
            )
            state["demands"][record["id"]] = record
            demand_changed = True
            outcome = {
                "decision": "create",
                "demand_changed": True,
                "demand_id": record["id"],
                "demand_ref": _encode_ref(record["id"], 1),
                "demand_pool_revision": _increment_pool_revision(state),
            }
        else:
            target_change = _apply_ingress_target_change(
                state,
                records,
                receipt=receipt,
                proposal=normalized_proposal,
            )
            if target_change is None:
                state["ingress_receipts"][normalized_source_key].update(
                    {
                        "state": "pending",
                        "attempt_id": None,
                        "outcome": None,
                        "last_failure": {
                            "code": "stale_demand_ref",
                            "message": (
                                "The target Demand changed after triage read it."
                            ),
                            "at": state_runtime.now_iso(),
                        },
                        "updated_at": state_runtime.now_iso(),
                    }
                )
                return True, {
                    "state_changed": True,
                    "source_key": normalized_source_key,
                    "retry_required": True,
                    "reason": "stale_demand_ref",
                    "demand_pool_revision": state["demand_pool_revision"],
                }
            demand_changed, outcome = target_change
            outcome["demand_pool_revision"] = (
                _increment_pool_revision(state)
                if demand_changed
                else state["demand_pool_revision"]
            )

        if demand_changed is False and outcome["demand_pool_revision"] != state["demand_pool_revision"]:
            raise _payload_error("receipt-only resolution changed Demand pool revision")
        state["ingress_receipts"][normalized_source_key].update(
            {
                "state": "settled",
                "outcome": deepcopy(outcome),
                "last_failure": None,
                "updated_at": state_runtime.now_iso(),
            }
        )
        return True, {
            "state_changed": True,
            "source_key": normalized_source_key,
            **outcome,
        }

    return demands.transact_actor_state(normalized_target, mutate)


def fail_ingress_resolution(
    actor_target: Mapping[str, Any],
    source_key: Any,
    attempt_id: Any,
    failure: Any,
    *,
    retriable: Any,
) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    normalized_source_key = _require_text(source_key, "source_key")
    normalized_attempt_id = _require_attempt_id(attempt_id)
    normalized_failure = _require_mapping(failure, "failure")
    _require_exact_fields(normalized_failure, {"code", "message"}, "failure")
    failure_code = _require_text(normalized_failure.get("code"), "failure.code")
    failure_message = _require_text(
        normalized_failure.get("message"),
        "failure.message",
    )
    if type(retriable) is not bool:
        raise _payload_error("retriable must be a boolean")

    def mutate(state: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        receipt = _ingress_receipts(state).get(normalized_source_key)
        if receipt is None:
            raise DemandNotFound(
                f"Demand ingress receipt not found: {normalized_source_key}"
            )
        if (
            receipt["state"] != "resolving"
            or receipt["attempt_id"] != normalized_attempt_id
        ):
            raise DemandRevisionConflict(
                f"Demand ingress receipt {normalized_source_key} resolution attempt changed"
            )
        next_state = "pending" if retriable else "failed"
        now = state_runtime.now_iso()
        state["ingress_receipts"][normalized_source_key].update(
            {
                "state": next_state,
                "attempt_id": None,
                "outcome": None,
                "last_failure": {
                    "code": failure_code,
                    "message": failure_message,
                    "at": now,
                },
                "updated_at": now,
            }
        )
        return True, {
            "state_changed": True,
            "source_key": normalized_source_key,
            "state": next_state,
            "retry_required": retriable,
        }

    return demands.transact_actor_state(normalized_target, mutate)
