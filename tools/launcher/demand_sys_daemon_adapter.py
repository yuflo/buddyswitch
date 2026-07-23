"""Demand-owned adapter from validated source facts to generic daemon schedules."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


DEMAND_INGRESS_TRIAGE_TRIGGER = "demand.ingress.triage"


def enqueue_inbound(
    state: Any,
    *,
    source_key: str,
    description: str,
    detail: str,
    source_refs: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Persist one exact source fact as a generic due-now delivery lease."""

    upsert = getattr(state, "upsert_schedule", None)
    if not callable(upsert):
        raise ValueError("daemon state does not expose upsert_schedule")
    payload = {
        "source_key": source_key,
        "description": description,
        "detail": detail,
        "source_refs": [dict(ref) for ref in source_refs],
    }
    return dict(
        upsert(
            delay_seconds=0,
            trigger_type=DEMAND_INGRESS_TRIAGE_TRIGGER,
            payload=payload,
            source_context={"owner": "demand_sys"},
            schedule_key=f"demand-ingress:{source_key}",
        )
    )
