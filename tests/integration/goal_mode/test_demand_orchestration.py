"""Demand reconciliation and serialized Task selection run in an independent parent turn."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import demand_orchestration_handler
import demand_triage_handler
from env.domain import demand_sys, task_sys
from tests.support.runtime import RuntimeWorkspaceTestCase


class _State:
    def __init__(self) -> None:
        self.handlers: dict[str, dict[str, Any]] = {}
        self.schedules: dict[str, dict[str, Any]] = {}

    def handler_state(self, name: str) -> dict[str, Any]:
        return dict(self.handlers.get(name, {}))

    def update_handler_state(self, name: str, update: dict[str, Any]) -> None:
        current = dict(self.handlers.get(name, {}))
        current.update(update)
        self.handlers[name] = current

    def upsert_schedule(self, **kwargs: Any) -> dict[str, Any]:
        key = str(kwargs["schedule_key"])
        self.schedules[key] = dict(kwargs)
        return {"schedule_id": f"schedule-{key}", **kwargs}


class _Runtime:
    def __init__(self, *, parent_status: str = "idle") -> None:
        self.parent_status = parent_status
        self.inputs: list[str] = []

    def parent_activity(self) -> dict[str, Any]:
        return {"status": self.parent_status, "active_turn_id": None}

    def input_actor(self, text: str) -> dict[str, str]:
        self.inputs.append(text)
        self.parent_status = "running"
        return {"action": "start", "turn_id": f"turn-orchestration-{len(self.inputs)}"}


class DemandOrchestrationTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor_id = self._runtime_actor_id(role="market", label="demand-orchestration")
        self.actor_target = {"actor_id": self.actor_id, "role_id": "market"}
        self.context = SimpleNamespace(
            actor_id=self.actor_id,
            role="market",
            instance_json=self._instance_root(self.actor_id) / "instance.json",
            instance_root=self._instance_root(self.actor_id),
            main_thread_id="thread-main-demand-orchestration",
            socket_path=self._instance_root(self.actor_id) / "runtime" / "app-server.sock",
            workspace_dir=self.runtime_root,
            project_workspace_dir=self.runtime_root / "projects" / "app",
            permissions="buddyswitch-runtime",
        )

    def _demand(self, suffix: str = "primary") -> dict[str, Any]:
        return demand_sys.create(
            self.actor_target,
            f"actor-create:{suffix}",
            f"Deliver the {suffix} Demand result.",
            f"Canonical live Demand {suffix}.",
            [
                {
                    "type": "actor.self_requested",
                    "ref": {
                        "thread_id": self.context.main_thread_id,
                        "turn_id": f"turn-{suffix}",
                    },
                }
            ],
        )

    def _task(self, demand: dict[str, Any], suffix: str = "primary") -> dict[str, Any]:
        resolved = demand_sys.resolve_demand_ref(
            actor_target=self.actor_target,
            demand_ref=demand["demand_ref"],
        )
        return task_sys.create(
            actor_target=self.actor_target,
            demand_ref=resolved,
            objective=f"Complete the observable Task result for {suffix}.",
            selection_reason=f"{suffix} is the selected live Demand.",
        )

    def _complete_task(self, task: dict[str, Any]) -> dict[str, Any]:
        goal = {
            "threadId": self.context.main_thread_id,
            "objective": task["task"]["objective"],
            "status": "complete",
            "tokenBudget": None,
            "tokensUsed": 30,
            "timeUsedSeconds": 4,
            "createdAt": 100,
            "updatedAt": 120,
        }
        task_sys.bind_goal(task["task_id"], goal)
        return task_sys.record_goal_complete(task["task_id"], goal)

    def test_triage_handler_owns_only_side_ingress_and_no_task_or_parent_rule(self) -> None:
        source = Path(demand_triage_handler.__file__).read_text(encoding="utf-8")

        self.assertNotIn("from env.domain import task_sys", source)
        self.assertNotIn("ORCHESTRATION_PROMPT", source)
        self.assertNotIn("ORCHESTRATION_TRIGGER", source)
        self.assertNotIn("parent_activity", source)
        self.assertNotIn("input_actor", source)
        self.assertNotIn("needs_parent_judgment", source)

    def test_actor_created_live_demand_starts_one_independent_parent_turn(self) -> None:
        self._demand()
        state = _State()
        runtime = _Runtime()
        handler = demand_orchestration_handler.DemandOrchestrationHandler()

        first = handler.reconcile(self.context, state, runtime)
        second = handler.reconcile(self.context, state, runtime)

        self.assertEqual(first.status, "handled")
        self.assertEqual(second.status, "handled")
        self.assertEqual(len(runtime.inputs), 1)
        prompt = runtime.inputs[0]
        self.assertIn("Use $demand-orchestration", prompt)
        self.assertIn("independent parent turn", prompt)
        self.assertIn("select exactly one", prompt)
        self.assertNotIn("task_sys.outcome_frame", prompt)
        self.assertNotIn("need_parent", prompt)
        checkpoint = state.handler_state("demand_orchestration")["checkpoint"]
        self.assertEqual(checkpoint["submitted_turn_id"], "turn-orchestration-1")
        self.assertEqual(checkpoint["pending_reason"], "live_demand_without_active_task")

    def test_parent_busy_defers_without_losing_durable_attention(self) -> None:
        self._demand("busy")
        state = _State()
        runtime = _Runtime(parent_status="running")
        handler = demand_orchestration_handler.DemandOrchestrationHandler()

        deferred = handler.reconcile(self.context, state, runtime)
        runtime.parent_status = "idle"
        submitted = handler.handle(
            self.context,
            state,
            runtime,
            SimpleNamespace(type=demand_orchestration_handler.ORCHESTRATION_TRIGGER),
        )

        self.assertEqual(deferred.status, "handled")
        self.assertEqual(submitted.status, "handled")
        self.assertEqual(len(runtime.inputs), 1)
        self.assertIn("demand-orchestration", state.schedules)
        checkpoint = state.handler_state("demand_orchestration")["checkpoint"]
        self.assertEqual(checkpoint["status"], "submitted")

    def test_active_task_defers_selection_and_preserves_pending_pool_attention(self) -> None:
        first = self._demand("active")
        self._task(first, "active")
        self._demand("queued")
        state = _State()
        runtime = _Runtime()

        result = demand_orchestration_handler.DemandOrchestrationHandler().reconcile(
            self.context,
            state,
            runtime,
        )

        self.assertEqual(result.status, "handled")
        self.assertEqual(runtime.inputs, [])
        checkpoint = state.handler_state("demand_orchestration")["checkpoint"]
        self.assertEqual(checkpoint["status"], "deferred_active_task")
        self.assertIsNotNone(checkpoint["active_task_id"])

    def test_terminal_task_attention_does_not_mutate_demand_before_parent_turn(self) -> None:
        demand = self._demand("terminal")
        task = self._task(demand, "terminal")
        self._complete_task(task)
        before = demand_sys.list_demands(self.actor_target)
        state = _State()
        runtime = _Runtime()

        result = demand_orchestration_handler.DemandOrchestrationHandler().reconcile(
            self.context,
            state,
            runtime,
        )

        self.assertEqual(result.status, "handled")
        self.assertEqual(demand_sys.list_demands(self.actor_target), before)
        self.assertEqual(len(runtime.inputs), 1)
        self.assertIn(task["task_id"], runtime.inputs[0])
        self.assertIn("terminal Task", runtime.inputs[0])
        self.assertEqual(
            state.handler_state("demand_orchestration")["checkpoint"]["terminal_task_ids"],
            [task["task_id"]],
        )

    def test_zero_live_demands_consumes_terminal_attention_without_parent_turn(self) -> None:
        demand = self._demand("already-satisfied")
        task = self._task(demand, "already-satisfied")
        self._complete_task(task)
        demand_sys.complete(
            self.actor_target,
            demand["demand_ref"],
            "Demand was independently satisfied.",
            [{"type": "task_sys.task", "ref": {"task_id": task["task_id"]}}],
        )
        state = _State()
        runtime = _Runtime()

        first = demand_orchestration_handler.DemandOrchestrationHandler().reconcile(
            self.context,
            state,
            runtime,
        )
        second = demand_orchestration_handler.DemandOrchestrationHandler().reconcile(
            self.context,
            state,
            runtime,
        )

        self.assertEqual(first.status, "handled")
        self.assertEqual(second.status, "ignored")
        self.assertEqual(runtime.inputs, [])
        checkpoint = state.handler_state("demand_orchestration")["checkpoint"]
        self.assertEqual(checkpoint["status"], "consumed_empty_pool")
        self.assertEqual(checkpoint["observed_terminal_task_ids"], [task["task_id"]])

    def test_duplicate_restart_recomputes_from_canonical_truth(self) -> None:
        self._demand("restart")
        first_state = _State()
        first_runtime = _Runtime(parent_status="running")
        handler = demand_orchestration_handler.DemandOrchestrationHandler()
        handler.reconcile(self.context, first_state, first_runtime)

        restarted_state = _State()
        restarted_runtime = _Runtime(parent_status="idle")
        result = handler.reconcile(self.context, restarted_state, restarted_runtime)

        self.assertEqual(result.status, "handled")
        self.assertEqual(len(restarted_runtime.inputs), 1)
        self.assertIn("select exactly one", restarted_runtime.inputs[0])
