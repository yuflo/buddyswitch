"""Demand source-fact scheduling adapter contracts."""

from __future__ import annotations

from typing import Any

import demand_sys_daemon_adapter


class _State:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def upsert_schedule(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"schedule_id": "schedule-1", **kwargs}


def test_enqueue_inbound_creates_one_due_now_generic_delivery_lease() -> None:
    state = _State()
    refs = [{
        "type": "im.message.created",
        "ref": {
            "message_id": "msg-adapter-1",
            "conversation_id": "conv-adapter-1",
            "event_id": "imev-adapter-1",
        },
    }]

    receipt = demand_sys_daemon_adapter.enqueue_inbound(
        state,
        source_key="im.message.created:msg-adapter-1",
        description="Support user data CSV export.",
        detail="Support user data CSV export.",
        source_refs=refs,
    )

    assert receipt["schedule_id"] == "schedule-1"
    assert state.calls == [{
        "delay_seconds": 0,
        "trigger_type": "demand.ingress.triage",
        "payload": {
            "source_key": "im.message.created:msg-adapter-1",
            "description": "Support user data CSV export.",
            "detail": "Support user data CSV export.",
            "source_refs": refs,
        },
        "source_context": {"owner": "demand_sys"},
        "schedule_key": (
            "demand-ingress:im.message.created:msg-adapter-1"
        ),
    }]


def test_enqueue_inbound_requires_generic_schedule_capability() -> None:
    try:
        demand_sys_daemon_adapter.enqueue_inbound(
            object(),
            source_key="source:1",
            description="Need.",
            detail="Detail.",
            source_refs=[],
        )
    except ValueError as exc:
        assert "upsert_schedule" in str(exc)
    else:
        raise AssertionError("missing schedule capability must fail")
