"""Canonical actor-owned Demand lifecycle and canonicalization owner."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Mapping
from uuid import uuid4

from env.repos import demands
from env.repos import runtime_files


TERMINAL_TYPES = ("completed", "canceled", "absorbed")
_RECORD_FIELDS = {
    "id",
    "intake_key",
    "description",
    "detail",
    "source_refs",
    "revision",
    "checked_revision",
    "terminal",
    "created_at",
    "updated_at",
}


class DemandError(ValueError):
    code = "E_DEMAND"


class DemandNotFound(DemandError):
    code = "E_DEMAND_NOT_FOUND"


class DemandRevisionConflict(DemandError):
    code = "E_DEMAND_REVISION_CONFLICT"


class DemandIntakeConflict(DemandError):
    code = "E_DEMAND_INTAKE_CONFLICT"


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


def _require_revision(value: Any, field: str = "expected_revision") -> int:
    if type(value) is not int or value < 1:
        raise _payload_error(f"{field} must be a positive integer")
    return value


def _require_checked_revision(value: Any, revision: int) -> int:
    if type(value) is not int or value < 0 or value > revision:
        raise _payload_error(
            "demand.checked_revision must be an integer between zero and revision"
        )
    return value


def _require_demand_id(value: Any, field: str = "demand_id") -> str:
    if not isinstance(value, str) or not value.startswith("demand-"):
        raise _payload_error(f"{field} must be a Demand id")
    try:
        return runtime_files.require_id(value, field)
    except ValueError as exc:
        raise _payload_error(str(exc)) from exc


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
        refs.append(
            {
                "type": _require_text(ref.get("type"), f"{field}[{index}].type"),
                "ref": _json_object_copy(ref.get("ref"), f"{field}[{index}].ref"),
            }
        )
    return refs


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
    elif terminal_type == "canceled":
        fields = {"type", "at", "summary"}
    else:
        fields = {"type", "at", "summary", "target_demand_id"}
    _require_exact_fields(terminal, fields, "demand.terminal")
    normalized: dict[str, Any] = {
        "type": terminal_type,
        "at": _require_text(terminal.get("at"), "demand.terminal.at"),
        "summary": _require_text(
            terminal.get("summary"),
            "demand.terminal.summary",
        ),
    }
    if "target_demand_id" in fields:
        normalized["target_demand_id"] = _require_demand_id(
            terminal.get("target_demand_id"),
            "demand.terminal.target_demand_id",
        )
    if "evidence_refs" in fields:
        normalized["evidence_refs"] = _normalize_refs(
            terminal.get("evidence_refs"),
            "demand.terminal.evidence_refs",
        )
    return normalized


def _normalize_record(value: Any) -> dict[str, Any]:
    record = _require_mapping(value, "demand")
    _require_exact_fields(record, _RECORD_FIELDS, "demand")
    revision = _require_revision(record.get("revision"), "demand.revision")
    return {
        "id": _require_demand_id(record.get("id"), "demand.id"),
        "intake_key": _require_text(record.get("intake_key"), "demand.intake_key"),
        "description": _require_text(record.get("description"), "demand.description"),
        "detail": _require_text(record.get("detail"), "demand.detail"),
        "source_refs": _normalize_refs(record.get("source_refs"), "demand.source_refs"),
        "revision": revision,
        "checked_revision": _require_checked_revision(
            record.get("checked_revision"),
            revision,
        ),
        "terminal": _normalize_terminal(record.get("terminal")),
        "created_at": _require_text(record.get("created_at"), "demand.created_at"),
        "updated_at": _require_text(record.get("updated_at"), "demand.updated_at"),
    }


def _records(state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_records = state.get("demands")
    if not isinstance(raw_records, Mapping):
        raise _payload_error("Demand actor aggregate demands must be an object")
    normalized: dict[str, dict[str, Any]] = {}
    intake_keys: set[str] = set()
    for indexed_id, raw_record in raw_records.items():
        demand_id = _require_demand_id(indexed_id, "Demand aggregate key")
        record = _normalize_record(raw_record)
        if record["id"] != demand_id:
            raise _payload_error("Demand aggregate key must match demand.id")
        if record["intake_key"] in intake_keys:
            raise _payload_error("Demand intake_key values must be unique per actor")
        intake_keys.add(record["intake_key"])
        normalized[demand_id] = record
    return normalized


def _receipt(*, state_changed: bool, changes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "state_changed": state_changed,
        "changes": changes,
        "check_required": bool(changes),
    }


def _new_demand_id(records: Mapping[str, Any]) -> str:
    while True:
        demand_id = f"demand-{uuid4().hex[:12]}"
        if demand_id not in records:
            return demand_id


def _find_record(
    records: Mapping[str, dict[str, Any]],
    demand_id: str,
) -> dict[str, Any]:
    record = records.get(demand_id)
    if record is None:
        raise DemandNotFound(f"Demand not found: {demand_id}")
    return record


def _require_expected_revision(record: Mapping[str, Any], expected_revision: int) -> None:
    if record["revision"] != expected_revision:
        raise DemandRevisionConflict(
            f"Demand {record['id']} is at revision {record['revision']}; "
            f"expected {expected_revision}. Read the current Demand and retry."
        )


def _require_live(record: Mapping[str, Any]) -> None:
    if record["terminal"] is not None:
        raise DemandTerminalConflict(f"Demand {record['id']} is terminal")


def create(
    actor_target: Mapping[str, Any],
    intake_key: Any,
    description: Any,
    detail: Any,
    source_refs: Any,
) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    normalized_intake_key = _require_text(intake_key, "intake_key")
    normalized_description = _require_text(description, "description")
    normalized_detail = _require_text(detail, "detail")
    normalized_source_refs = _normalize_refs(source_refs, "source_refs")

    def mutate(state: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        records = _records(state)
        for record in records.values():
            if record["intake_key"] != normalized_intake_key:
                continue
            same_input = (
                record["description"] == normalized_description
                and record["detail"] == normalized_detail
                and record["source_refs"] == normalized_source_refs
            )
            if same_input:
                return False, {
                    **_receipt(state_changed=False, changes=[]),
                    "demand_id": record["id"],
                    "revision": record["revision"],
                }
            raise DemandIntakeConflict(
                f"Demand intake_key already exists with different content: {normalized_intake_key}"
            )
        demand_id = _new_demand_id(records)
        now = runtime_files.now_iso()
        record = {
            "id": demand_id,
            "intake_key": normalized_intake_key,
            "description": normalized_description,
            "detail": normalized_detail,
            "source_refs": normalized_source_refs,
            "revision": 1,
            "checked_revision": 0,
            "terminal": None,
            "created_at": now,
            "updated_at": now,
        }
        state["demands"][demand_id] = record
        return True, {
            **_receipt(
                state_changed=True,
                changes=[{"demand_id": demand_id, "revision": 1, "kind": "created"}],
            ),
            "demand_id": demand_id,
            "revision": 1,
        }

    return demands.transact_actor_state(normalized_target, mutate)


def revise(
    actor_target: Mapping[str, Any],
    demand_id: Any,
    expected_revision: Any,
    description: Any,
    detail: Any,
) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    normalized_id = _require_demand_id(demand_id)
    normalized_revision = _require_revision(expected_revision)
    normalized_description = _require_text(description, "description")
    normalized_detail = _require_text(detail, "detail")

    def mutate(state: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        records = _records(state)
        record = _find_record(records, normalized_id)
        _require_live(record)
        _require_expected_revision(record, normalized_revision)
        if (
            record["description"] == normalized_description
            and record["detail"] == normalized_detail
        ):
            return False, _receipt(state_changed=False, changes=[])
        next_revision = record["revision"] + 1
        stored = state["demands"][normalized_id]
        stored.update(
            {
                "description": normalized_description,
                "detail": normalized_detail,
                "revision": next_revision,
                "updated_at": runtime_files.now_iso(),
            }
        )
        return True, _receipt(
            state_changed=True,
            changes=[
                {
                    "demand_id": normalized_id,
                    "revision": next_revision,
                    "kind": "revised",
                }
            ],
        )

    return demands.transact_actor_state(normalized_target, mutate)


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
    return sorted(records, key=lambda record: (record["created_at"], record["id"]))


def get(actor_target: Mapping[str, Any], demand_id: Any) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    normalized_id = _require_demand_id(demand_id)
    records = _records(demands.load_actor_state(normalized_target))
    return _find_record(records, normalized_id)


def get_many(
    actor_target: Mapping[str, Any],
    demand_ids: Any,
) -> list[dict[str, Any]]:
    normalized_target = demands.normalize_actor_target(actor_target)
    if not isinstance(demand_ids, list):
        raise _payload_error("demand_ids must be a list")
    normalized_ids = [
        _require_demand_id(value, f"demand_ids[{index}]")
        for index, value in enumerate(demand_ids)
    ]
    if len(normalized_ids) != len(set(normalized_ids)):
        raise _payload_error("demand_ids must contain unique Demand ids")
    records = _records(demands.load_actor_state(normalized_target))
    return [_find_record(records, demand_id) for demand_id in normalized_ids]


def check(actor_target: Mapping[str, Any]) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    records = list(_records(demands.load_actor_state(normalized_target)).values())
    attention_items = sorted(
        [record for record in records if record["revision"] > record["checked_revision"]],
        key=lambda record: (record["created_at"], record["id"]),
    )
    live_records = sorted(
        [record for record in records if record["terminal"] is None],
        key=lambda record: (record["created_at"], record["id"]),
    )
    return {
        "attention_items": attention_items,
        "live_index": [
            {"id": record["id"], "description": record["description"]}
            for record in live_records
        ],
        "pending_count": len(attention_items),
    }


def complete_check(
    actor_target: Mapping[str, Any],
    observed: Any,
) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    if not isinstance(observed, list):
        raise _payload_error("observed must be a list")
    normalized_observed: list[dict[str, Any]] = []
    observed_ids: set[str] = set()
    for index, raw_observation in enumerate(observed):
        observation = _require_mapping(raw_observation, f"observed[{index}]")
        _require_exact_fields(
            observation,
            {"demand_id", "revision"},
            f"observed[{index}]",
        )
        demand_id = _require_demand_id(
            observation.get("demand_id"),
            f"observed[{index}].demand_id",
        )
        if demand_id in observed_ids:
            raise _payload_error("observed must contain unique demand_id values")
        observed_ids.add(demand_id)
        normalized_observed.append(
            {
                "demand_id": demand_id,
                "revision": _require_revision(
                    observation.get("revision"),
                    f"observed[{index}].revision",
                ),
            }
        )

    def mutate(state: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        records = _records(state)
        for observation in normalized_observed:
            record = _find_record(records, observation["demand_id"])
            if observation["revision"] > record["revision"]:
                raise DemandRevisionConflict(
                    f"Observed revision {observation['revision']} is newer than Demand "
                    f"{record['id']} revision {record['revision']}"
                )
        changed = False
        for observation in normalized_observed:
            record = records[observation["demand_id"]]
            if observation["revision"] > record["checked_revision"]:
                state["demands"][record["id"]]["checked_revision"] = observation[
                    "revision"
                ]
                record["checked_revision"] = observation["revision"]
                changed = True
        still_pending = [
            {"demand_id": record["id"], "revision": record["revision"]}
            for observation in normalized_observed
            for record in [records[observation["demand_id"]]]
            if record["revision"] > record["checked_revision"]
        ]
        result = {
            "acknowledged": deepcopy(normalized_observed),
            "still_pending": still_pending,
            "state_changed": changed,
            "check_required": False,
        }
        return changed, result

    return demands.transact_actor_state(normalized_target, mutate)


def _next_revision(stored: dict[str, Any], *, now: str) -> int:
    revision = int(stored["revision"]) + 1
    stored["revision"] = revision
    stored["updated_at"] = now
    return revision


def _change(demand_id: str, revision: int, kind: str) -> dict[str, Any]:
    return {"demand_id": demand_id, "revision": revision, "kind": kind}


def _normalize_merged_target(value: Any) -> dict[str, Any]:
    merged = _require_mapping(value, "merged_target")
    _require_exact_fields(
        merged,
        {"description", "detail"},
        "merged_target",
    )
    return {
        "description": _require_text(
            merged.get("description"),
            "merged_target.description",
        ),
        "detail": _require_text(merged.get("detail"), "merged_target.detail"),
    }


def _absorbed_terminal_matches(
    record: Mapping[str, Any],
    target_demand_id: str,
    summary: str,
) -> bool:
    terminal = record.get("terminal")
    return bool(
        isinstance(terminal, Mapping)
        and terminal.get("type") == "absorbed"
        and terminal.get("target_demand_id") == target_demand_id
        and terminal.get("summary") == summary
    )


def absorb_into(
    actor_target: Mapping[str, Any],
    source_id: Any,
    source_revision: Any,
    target_id: Any,
    target_revision: Any,
    merged_target: Any,
    summary: Any,
) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    normalized_source_id = _require_demand_id(source_id, "source_id")
    normalized_source_revision = _require_revision(
        source_revision,
        "source_revision",
    )
    normalized_target_id = _require_demand_id(target_id, "target_id")
    if normalized_source_id == normalized_target_id:
        raise _payload_error("source_id and target_id must identify different Demands")
    normalized_target_revision = _require_revision(
        target_revision,
        "target_revision",
    )
    normalized_merged_target = _normalize_merged_target(merged_target)
    normalized_summary = _require_text(summary, "summary")

    def mutate(state: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        records = _records(state)
        source = _find_record(records, normalized_source_id)
        target = _find_record(records, normalized_target_id)
        merged_source_refs: list[dict[str, Any]] = []
        for source_ref in [*target["source_refs"], *source["source_refs"]]:
            if source_ref not in merged_source_refs:
                merged_source_refs.append(deepcopy(source_ref))
        if source["terminal"] is not None:
            if (
                _absorbed_terminal_matches(
                    source,
                    normalized_target_id,
                    normalized_summary,
                )
                and target["description"] == normalized_merged_target["description"]
                and target["detail"] == normalized_merged_target["detail"]
                and target["source_refs"] == merged_source_refs
            ):
                return False, _receipt(state_changed=False, changes=[])
            raise DemandTerminalConflict(f"Demand {normalized_source_id} is terminal")
        _require_live(target)
        _require_expected_revision(source, normalized_source_revision)
        _require_expected_revision(target, normalized_target_revision)
        now = runtime_files.now_iso()
        stored_target = state["demands"][normalized_target_id]
        stored_target.update(
            {
                **deepcopy(normalized_merged_target),
                "source_refs": merged_source_refs,
            }
        )
        next_target_revision = _next_revision(stored_target, now=now)
        stored_source = state["demands"][normalized_source_id]
        stored_source["terminal"] = {
            "type": "absorbed",
            "at": now,
            "target_demand_id": normalized_target_id,
            "summary": normalized_summary,
        }
        next_source_revision = _next_revision(stored_source, now=now)
        return True, _receipt(
            state_changed=True,
            changes=[
                _change(normalized_target_id, next_target_revision, "revised"),
                _change(normalized_source_id, next_source_revision, "absorbed"),
            ],
        )

    return demands.transact_actor_state(normalized_target, mutate)


def _terminalize_single(
    actor_target: Mapping[str, Any],
    demand_id: Any,
    expected_revision: Any,
    summary: Any,
    *,
    terminal_type: str,
    evidence_refs: Any = None,
) -> dict[str, Any]:
    normalized_target = demands.normalize_actor_target(actor_target)
    normalized_id = _require_demand_id(demand_id)
    normalized_revision = _require_revision(expected_revision)
    normalized_summary = _require_text(summary, "summary")
    normalized_evidence_refs = (
        _normalize_refs(evidence_refs, "evidence_refs")
        if terminal_type == "completed"
        else None
    )

    def mutate(state: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        records = _records(state)
        record = _find_record(records, normalized_id)
        expected_terminal: dict[str, Any] = {
            "type": terminal_type,
            "summary": normalized_summary,
        }
        if normalized_evidence_refs is not None:
            expected_terminal["evidence_refs"] = normalized_evidence_refs
        terminal = record["terminal"]
        if terminal is not None:
            if all(terminal.get(key) == value for key, value in expected_terminal.items()):
                return False, _receipt(state_changed=False, changes=[])
            raise DemandTerminalConflict(f"Demand {normalized_id} is terminal")
        _require_expected_revision(record, normalized_revision)
        now = runtime_files.now_iso()
        stored = state["demands"][normalized_id]
        next_terminal: dict[str, Any] = {
            "type": terminal_type,
            "at": now,
            "summary": normalized_summary,
        }
        if normalized_evidence_refs is not None:
            next_terminal["evidence_refs"] = deepcopy(normalized_evidence_refs)
        stored["terminal"] = next_terminal
        revision = _next_revision(stored, now=now)
        return True, _receipt(
            state_changed=True,
            changes=[_change(normalized_id, revision, terminal_type)],
        )

    return demands.transact_actor_state(normalized_target, mutate)


def complete(
    actor_target: Mapping[str, Any],
    demand_id: Any,
    expected_revision: Any,
    summary: Any,
    evidence_refs: Any,
) -> dict[str, Any]:
    return _terminalize_single(
        actor_target,
        demand_id,
        expected_revision,
        summary,
        terminal_type="completed",
        evidence_refs=evidence_refs,
    )


def cancel(
    actor_target: Mapping[str, Any],
    demand_id: Any,
    expected_revision: Any,
    summary: Any,
) -> dict[str, Any]:
    return _terminalize_single(
        actor_target,
        demand_id,
        expected_revision,
        summary,
        terminal_type="canceled",
    )
