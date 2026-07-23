"""Demand-owned attention handler for independent parent reconciliation and selection."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Mapping

HELPER_DIR = Path(__file__).resolve().parent
ROOT = HELPER_DIR.parents[1]
SCRIPTS = ROOT / "scripts"
for candidate in (HELPER_DIR, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import daemon_contracts  # noqa: E402
from env.domain import demand_sys, task_sys  # noqa: E402
from env.repos import runtime_files  # noqa: E402

ORCHESTRATION_TRIGGER = "demand.orchestrate"
RETRY_SECONDS = 5
_ACCELERATION_TRIGGERS = frozenset(
    {
        ORCHESTRATION_TRIGGER,
        "app_server.thread_goal_updated",
        "app_server.thread_goal_cleared",
        "app_server.turn_completed",
    }
)

ORCHESTRATION_PROMPT = """[DEMAND ORCHESTRATION — independent parent turn]
Use $demand-orchestration.
Reread canonical Task and Demand state; do not trust this attention snapshot.
First reconcile every newly terminal Task with its latest Demand. Task
completion is evidence, not automatic Demand completion. Then, if the Task
slot is empty and any live Demand exists, compare the entire live pool and
select exactly one Demand. Reread it and call task_sys__create once with its
opaque demand_ref, a self-contained native Goal objective, and the selection
reason. Do not create or complete a native Goal yourself.

Attention snapshot:
- demand_pool_revision: {pool_revision}
- live_demand_count: {live_count}
- terminal Task ids awaiting Demand reconciliation: {terminal_task_ids}
"""


def _actor_target(context: Any) -> dict[str, str]:
    return {
        "actor_id": runtime_files.require_id(
            getattr(context, "actor_id", ""),
            "context.actor_id",
        ),
        "role_id": runtime_files.require_id(
            getattr(context, "role", ""),
            "context.role",
        ),
    }


def _checkpoint(state: Any, name: str) -> dict[str, Any]:
    raw = state.handler_state(name)
    if not isinstance(raw, Mapping):
        raise ValueError("Demand orchestration handler state must be an object")
    value = raw.get("checkpoint")
    return dict(value) if isinstance(value, Mapping) else {}


def _write_checkpoint(state: Any, name: str, checkpoint: Mapping[str, Any]) -> bool:
    normalized = dict(checkpoint)
    if _checkpoint(state, name) == normalized:
        return False
    state.update_handler_state(name, {"checkpoint": normalized})
    return True


def _terminal_task_ids(actor_target: Mapping[str, Any]) -> list[str]:
    rows = task_sys.list_tasks(
        actor_target=actor_target,
        statuses=task_sys.TERMINAL_TASK_STATUSES,
    )
    return sorted(str(row["id"]) for row in rows)


def _active_task(actor_target: Mapping[str, Any]) -> dict[str, Any] | None:
    rows = task_sys.list_tasks(
        actor_target=actor_target,
        statuses=task_sys.ACTIVE_TASK_STATUSES,
    )
    if len(rows) > 1:
        raise ValueError("Demand orchestration requires at most one active Task")
    return rows[0] if rows else None


def _schedule_retry(state: Any) -> None:
    state.upsert_schedule(
        delay_seconds=RETRY_SECONDS,
        trigger_type=ORCHESTRATION_TRIGGER,
        payload={},
        source_context={"owner": "demand_orchestration", "reason": "parent_deferred"},
        schedule_key="demand-orchestration",
    )


class DemandOrchestrationHandler:
    """Own durable attention; Actor judgment stays in an independent parent turn."""

    name = "demand_orchestration"

    def handles(self, trigger: Any) -> bool:
        return getattr(trigger, "type", None) in _ACCELERATION_TRIGGERS

    def reconcile(
        self,
        context: Any,
        state: Any,
        runtime: Any,
    ) -> daemon_contracts.HandlerResult:
        actor_target = _actor_target(context)
        pool = demand_sys.pool_snapshot(actor_target)
        active = _active_task(actor_target)
        terminal_ids = _terminal_task_ids(actor_target)
        previous = _checkpoint(state, self.name)
        observed_terminal = {
            row
            for row in previous.get("observed_terminal_task_ids", [])
            if isinstance(row, str)
        }
        unobserved_terminal = [
            task_id for task_id in terminal_ids if task_id not in observed_terminal
        ]
        base: dict[str, Any] = {
            "demand_pool_revision": pool["demand_pool_revision"],
            "live_demand_count": pool["live_demand_count"],
            "terminal_task_ids": unobserved_terminal,
            "observed_terminal_task_ids": sorted(observed_terminal),
            "active_task_id": active.get("id") if active is not None else None,
            "submitted_turn_id": (
                previous.get("submitted_turn_id")
                if isinstance(previous.get("submitted_turn_id"), str)
                else None
            ),
        }

        if active is not None:
            changed = _write_checkpoint(
                state,
                self.name,
                {
                    **base,
                    "status": "deferred_active_task",
                    "pending_reason": (
                        "terminal_task_waits_for_empty_slot"
                        if unobserved_terminal
                        else "live_demand_waits_for_empty_slot"
                    ),
                },
            )
            return (
                daemon_contracts.HandlerResult.handled()
                if changed
                else daemon_contracts.HandlerResult.ignored()
            )

        if pool["live_demand_count"] == 0:
            changed = _write_checkpoint(
                state,
                self.name,
                {
                    **base,
                    "status": "consumed_empty_pool",
                    "pending_reason": None,
                    "terminal_task_ids": [],
                    "observed_terminal_task_ids": terminal_ids,
                    "observed_demand_pool_revision": pool["demand_pool_revision"],
                },
            )
            return (
                daemon_contracts.HandlerResult.handled()
                if changed
                else daemon_contracts.HandlerResult.ignored()
            )

        activity = runtime.parent_activity()
        parent_status = activity.get("status") if isinstance(activity, Mapping) else None
        if parent_status != "idle":
            _schedule_retry(state)
            changed = _write_checkpoint(
                state,
                self.name,
                {
                    **base,
                    "status": "deferred_parent_busy",
                    "pending_reason": "live_demand_without_active_task",
                    "parent_status": parent_status or "unavailable",
                },
            )
            return (
                daemon_contracts.HandlerResult.handled()
                if changed
                else daemon_contracts.HandlerResult.ignored()
            )

        submitted = runtime.input_actor(
            ORCHESTRATION_PROMPT.format(
                pool_revision=pool["demand_pool_revision"],
                live_count=pool["live_demand_count"],
                terminal_task_ids=(
                    ", ".join(unobserved_terminal)
                    if unobserved_terminal
                    else "none"
                ),
            )
        )
        turn_id = submitted.get("turn_id") if isinstance(submitted, Mapping) else None
        if not isinstance(turn_id, str) or not turn_id:
            raise ValueError("Demand orchestration parent submission returned no turn id")
        _write_checkpoint(
            state,
            self.name,
            {
                **base,
                "status": "submitted",
                "pending_reason": "live_demand_without_active_task",
                "submitted_turn_id": turn_id,
                "observed_terminal_task_ids": terminal_ids,
                "observed_demand_pool_revision": pool["demand_pool_revision"],
            },
        )
        return daemon_contracts.HandlerResult.handled()

    def handle(
        self,
        context: Any,
        state: Any,
        runtime: Any,
        trigger: Any,
    ) -> daemon_contracts.HandlerResult:
        if not self.handles(trigger):
            return daemon_contracts.HandlerResult.ignored()
        try:
            return self.reconcile(context, state, runtime)
        except Exception as exc:
            return daemon_contracts.HandlerResult.failed(str(exc))
