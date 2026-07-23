"""Broker-routed response contracts for the native-Goal Task tool."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from env.domain import demand_sys, task_sys
from env.tool_runtime import context as runtime_context
from tests.integration.env_tool._response_case import EnvToolResponseCase


class EnvToolTaskResponseTests(EnvToolResponseCase):
    def _seed_active_task(self, *, instance_json: Path, role: str, actor_id: str) -> None:
        del instance_json, role, actor_id

    def _demand_ref(self, *, actor_id: str, label: str) -> str:
        created = demand_sys.create(
            {"actor_id": actor_id, "role_id": "dev"},
            f"actor-create:{label}",
            "Deliver the selected observable result.",
            "This Demand is used by the Task tool response contract.",
            [
                {
                    "type": "actor.self_requested",
                    "ref": {"thread_id": "thr-main", "turn_id": f"turn-{label}"},
                }
            ],
        )
        return str(created["demand_ref"])

    @staticmethod
    def _create_args(demand_ref: str, *, objective: str = "Deliver the selected observable result.") -> dict[str, str]:
        return {
            "demand_ref": demand_ref,
            "objective": objective,
            "selection_reason": "This is the only live Demand and the Task slot is empty.",
        }

    def test_create_and_exact_retry_both_request_idempotent_goal_convergence(self) -> None:
        actor_label = "act-dev-goal-task-create-response"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        demand_ref = self._demand_ref(actor_id=actor_id, label="goal-task-create")
        args = self._create_args(demand_ref)

        with patch.object(
            runtime_context.TaskGoalRuntimeAccess,
            "reconcile_task",
            autospec=True,
            return_value={"status": "active", "binding_changed": False},
        ) as reconcile:
            created = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="create",
                args=args,
            )
            replay = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="create",
                args=args,
            )

        self._assert_write_success_contract(created)
        self._assert_success_contract(replay)
        self.assertEqual(created["outcome"], "created")
        self.assertEqual(replay["outcome"], "existing")
        self.assertEqual(replay["task_id"], created["task_id"])
        self.assertEqual(created["task_status"], task_sys.ACTIVE)
        self.assertEqual(created["goal_reconciliation"]["status"], "reconciled")
        self.assertEqual(reconcile.call_count, 2)

    def test_runtime_failure_keeps_durable_active_task_unbound_and_pending(self) -> None:
        actor_label = "act-dev-goal-task-runtime-failure"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        demand_ref = self._demand_ref(actor_id=actor_id, label="goal-task-runtime-failure")

        with patch.object(
            runtime_context.TaskGoalRuntimeAccess,
            "reconcile_task",
            autospec=True,
            side_effect=RuntimeError("daemon unavailable"),
        ):
            result = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="create",
                args=self._create_args(demand_ref),
            )

        self._assert_write_success_contract(result)
        task = task_sys.get_task(result["task_id"])
        self.assertEqual(task["status"], task_sys.ACTIVE)
        self.assertIsNone(task["goal_binding"])
        self.assertEqual(result["goal_reconciliation"]["status"], "pending")
        self.assertIn("daemon unavailable", result["goal_reconciliation"]["error"])

    def test_create_conflicts_do_not_call_goal_runtime(self) -> None:
        actor_label = "act-dev-goal-task-conflict"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        demand_ref = self._demand_ref(actor_id=actor_id, label="goal-task-conflict")

        with patch.object(
            runtime_context.TaskGoalRuntimeAccess,
            "reconcile_task",
            autospec=True,
            return_value={"status": "active"},
        ) as reconcile:
            created = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="create",
                args=self._create_args(demand_ref),
            )
            conflict = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="create",
                args=self._create_args(demand_ref, objective="Changed objective must conflict."),
            )

        self.assertTrue(created["ok"])
        self._assert_rejection_contract(conflict)
        self.assertEqual(conflict["error"]["code"], "E_TASK_SYS_SOURCE_CONFLICT")
        reconcile.assert_called_once()

    def test_cancel_records_terminal_task_then_requests_goal_cleanup(self) -> None:
        actor_label = "act-dev-goal-task-cancel"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        created = task_sys.create(
            actor_target={"actor_id": actor_id, "role_id": "dev"},
            demand_ref={
                "demand_id": "demand-goal-task-cancel-response",
                "basis_revision": 1,
                "demand_ref": "dref-goal-task-cancel-response",
            },
            objective="Stop this fixture explicitly.",
            selection_reason="Cancellation response fixture.",
        )

        with patch.object(
            runtime_context.TaskGoalRuntimeAccess,
            "reconcile_task",
            autospec=True,
            return_value={"status": "goal_absent"},
        ) as reconcile:
            canceled = self._dispatch(
                instance_json=instance_json,
                actor_id=actor_label,
                role="dev",
                tool="task_sys",
                action="cancel",
                args={"task_id": created["task_id"], "reason": "Actor stopped the fixture."},
            )

        self._assert_write_success_contract(canceled)
        self.assertEqual(canceled["task_status"], task_sys.CANCELED)
        self.assertEqual(task_sys.get_task(created["task_id"])["result"]["type"], "actor_canceled")
        reconcile.assert_called_once()

    def test_list_and_get_expose_no_frame_or_recoverable_contract(self) -> None:
        actor_label = "act-dev-goal-task-read"
        actor_id = self._runtime_actor_id(role="dev", label=actor_label)
        instance_json = self._instance_json(role="dev", actor_id=actor_label)
        created = task_sys.create(
            actor_target={"actor_id": actor_id, "role_id": "dev"},
            demand_ref={
                "demand_id": "demand-goal-task-read-response",
                "basis_revision": 1,
                "demand_ref": "dref-goal-task-read-response",
            },
            objective="Read the current Task contract.",
            selection_reason="Task read response fixture.",
        )

        listed = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            role="dev",
            tool="task_sys",
            action="list",
            args={"status": "active"},
        )
        detail = self._dispatch(
            instance_json=instance_json,
            actor_id=actor_label,
            role="dev",
            tool="task_sys",
            action="get",
            args={"task_id": created["task_id"]},
        )

        self._assert_success_contract(listed)
        self._assert_success_contract(detail)
        self.assertEqual(listed["active_count"], 1)
        self.assertEqual(listed["terminal_count"], 0)
        self.assertNotIn("recoverable_count", listed)
        for retired in ("execution", "events", "inbound_context", "source_type", "source_ref"):
            self.assertNotIn(retired, detail["task"])
