"""Exact current cross-component Demand operations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from buddyswitch.modules.demand.private.adapters.daemon import (
    demand_sys_daemon_adapter,
)
from buddyswitch.modules.demand.private.domain import demand_sys


def resolve_demand_ref(
    *,
    actor_target: Mapping[str, Any],
    demand_ref: Any,
) -> dict[str, Any]:
    return demand_sys.resolve_demand_ref(
        actor_target=actor_target,
        demand_ref=demand_ref,
    )


def enqueue_inbound(
    state: Any,
    *,
    source_key: str,
    description: str,
    detail: str,
    source_refs: list[Mapping[str, Any]],
) -> dict[str, Any]:
    return demand_sys_daemon_adapter.enqueue_inbound(
        state,
        source_key=source_key,
        description=description,
        detail=detail,
        source_refs=source_refs,
    )
