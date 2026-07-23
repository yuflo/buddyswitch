"""External-safe, actor-scoped read projections for Demand records."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from env.domain import demand_sys


def external_demand_projection(
    record: Mapping[str, Any],
    *,
    actor_target: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "demand_id": record["id"],
        "demand_ref": record["demand_ref"],
        "description": record["description"],
        "actor": dict(actor_target),
        "revision": record["revision"],
        "terminal": deepcopy(record["terminal"]),
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
    }


def _sort_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return (str(record["updated_at"]), str(record["id"]))


def list_external_demands(*, actor_target: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = demand_sys.list_demands(actor_target, state="all")
    records.sort(key=_sort_key, reverse=True)
    return [
        external_demand_projection(record, actor_target=actor_target)
        for record in records
    ]


def get_external_demand(
    demand_id: str,
    *,
    actor_target: Mapping[str, Any],
) -> dict[str, Any] | None:
    try:
        record = demand_sys.get(actor_target, demand_id)
    except demand_sys.DemandNotFound:
        return None
    return external_demand_projection(record, actor_target=actor_target)
