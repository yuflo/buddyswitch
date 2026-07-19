"""Demand-owned inbound capture and actor-attention adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import daemon_contracts
from env.domain import demand_sys
from env.repos import runtime_files


DEMAND_CHECK_PROMPT = """[DEMAND CHECK]
Actor-owned Demand revisions require attention.
Call demand_sys.check(). Compare pending Demand descriptions with the live index,
load only plausible candidates with demand_sys.get_many, apply only necessary
Demand organization actions, and call demand_sys.complete_check with the exact
revisions observed. Do not create or modify Task Sys during this Demand Check."""


def _actor_input_receipt(result: Any) -> dict[str, str]:
    if not isinstance(result, Mapping):
        raise RuntimeError("actor input returned a non-object result")
    action = result.get("action")
    if action not in {"start", "steer"}:
        raise RuntimeError("actor input action must be start or steer")
    try:
        turn_id = runtime_files.require_id(
            result.get("turn_id"),
            "actor input turn_id",
        )
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    return {"action": action, "turn_id": turn_id}


def capture_inbound(
    context: daemon_contracts.DaemonContext,
    runtime: Any,
    *,
    intake_key: str,
    description: str,
    detail: str,
    source_refs: list[Mapping[str, Any]],
) -> dict[str, Any]:
    actor_target = {
        "actor_id": runtime_files.require_id(context.actor_id, "context.actor_id"),
        "role_id": runtime_files.require_id(context.role, "context.role"),
    }
    created = demand_sys.create(
        actor_target,
        intake_key,
        description,
        detail,
        source_refs,
    )
    pending = demand_sys.check(actor_target)
    actor_input = None
    if pending["pending_count"] > 0:
        actor_input = _actor_input_receipt(runtime.input_actor(DEMAND_CHECK_PROMPT))
    return {
        "demand_id": created["demand_id"],
        "revision": created["revision"],
        "capture_state_changed": created["state_changed"],
        "pending_count": pending["pending_count"],
        "attention_requested": pending["pending_count"] > 0,
        "actor_input": actor_input,
    }
