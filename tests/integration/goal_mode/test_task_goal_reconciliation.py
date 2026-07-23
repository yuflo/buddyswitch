"""Task-to-native-Goal convergence and recovery contract."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import daemon_contracts
import daemon_triggers
import instance_daemon
import task_goal_handler
from env.domain import task_sys
from env.tool_runtime import task_goal_runtime_protocol
from tests.support.runtime import RuntimeWorkspaceTestCase


class TaskGoalReconciliationTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor_id = self._runtime_actor_id(role="dev", label="task-goal-handler")
        self.context = self._context(self.actor_id)

    def _context(self, actor_id: str) -> daemon_contracts.DaemonContext:
        instance_root = self._instance_root(actor_id)
        return daemon_contracts.DaemonContext(
            instance_json=instance_root / "instance.json",
            instance_payload={"actor_id": actor_id, "role": "dev"},
            actor_id=actor_id,
            instance_root=instance_root,
            main_thread_id=f"thread-main-{actor_id}",
            role="dev",
            workspace_dir=self.runtime_root,
            project_workspace_dir=self.runtime_root / "projects" / "app",
            socket_path=instance_root / "runtime" / "app-server.sock",
        )

    def _create(self, *, actor_id: str | None = None, suffix: str = "primary") -> dict[str, object]:
        target_actor = actor_id or self.actor_id
        return task_sys.create(
            actor_target={"actor_id": target_actor, "role_id": "dev"},
            demand_ref={
                "demand_id": f"demand-task-goal-{suffix}",
                "basis_revision": 1,
                "demand_ref": f"dref-task-goal-{suffix}",
            },
            objective=f"Deliver the observable native Goal result for {suffix}.",
            selection_reason=f"{suffix} is the selected live Demand.",
        )

    @staticmethod
    def _goal(
        context: daemon_contracts.DaemonContext,
        objective: str,
        *,
        status: str = "active",
        created_at: int = 100,
        updated_at: int = 100,
    ) -> dict[str, object]:
        return {
            "threadId": context.main_thread_id,
            "objective": objective,
            "status": status,
            "tokenBudget": None,
            "tokensUsed": 12,
            "timeUsedSeconds": 3,
            "createdAt": created_at,
            "updatedAt": updated_at,
        }

    def test_unbound_task_without_goal_sets_active_goal_and_binds_exact_snapshot(self) -> None:
        created = self._create()
        goal = self._goal(self.context, created["task"]["objective"])

        with (
            patch.object(task_goal_handler.app_server, "goal_get", return_value={"goal": None}) as get_goal,
            patch.object(task_goal_handler.app_server, "goal_set", return_value={"goal": goal}) as set_goal,
        ):
            result = task_goal_handler.reconcile_task(self.context, created["task_id"])

        self.assertEqual(result["goal_action"], "set_and_bound")
        self.assertEqual(
            task_sys.get_task(created["task_id"])["goal_binding"],
            {
                "thread_id": self.context.main_thread_id,
                "objective_hash": task_sys.objective_hash(created["task"]["objective"]),
                "goal_created_at": 100,
            },
        )
        get_goal.assert_called_once_with(self.context.socket_path, self.context.main_thread_id)
        set_goal.assert_called_once_with(
            self.context.socket_path,
            self.context.main_thread_id,
            objective=created["task"]["objective"],
            status="active",
        )

    def test_matching_existing_goal_binds_without_setting_a_second_goal(self) -> None:
        created = self._create()
        goal = self._goal(self.context, created["task"]["objective"])

        with (
            patch.object(task_goal_handler.app_server, "goal_get", return_value={"goal": goal}),
            patch.object(task_goal_handler.app_server, "goal_set") as set_goal,
        ):
            result = task_goal_handler.reconcile_task(self.context, created["task_id"])

        self.assertEqual(result["goal_action"], "bound_existing")
        set_goal.assert_not_called()

    def test_matching_complete_goal_binds_and_completes_exactly_once(self) -> None:
        created = self._create()
        goal = self._goal(
            self.context,
            created["task"]["objective"],
            status="complete",
            updated_at=130,
        )

        with patch.object(task_goal_handler.app_server, "goal_get", return_value={"goal": goal}):
            first = task_goal_handler.reconcile_task(self.context, created["task_id"])
            second = task_goal_handler.reconcile_task(self.context, created["task_id"])

        task = task_sys.get_task(created["task_id"])
        self.assertEqual(first["goal_action"], "completed")
        self.assertEqual(second["goal_action"], "already_completed")
        self.assertEqual(task["status"], task_sys.COMPLETED)
        self.assertEqual(task["result"]["goal_updated_at"], 130)

    def test_all_noncomplete_native_goal_states_leave_bound_task_active(self) -> None:
        for index, status in enumerate(("active", "paused", "blocked", "usageLimited", "budgetLimited"), start=1):
            with self.subTest(status=status):
                actor_id = self._runtime_actor_id(role="dev", label=f"task-goal-{status}")
                context = self._context(actor_id)
                created = self._create(actor_id=actor_id, suffix=f"state-{index}")
                goal = self._goal(context, created["task"]["objective"], status=status)
                task_sys.bind_goal(created["task_id"], goal)
                with patch.object(task_goal_handler.app_server, "goal_get", return_value={"goal": goal}):
                    result = task_goal_handler.reconcile_task(context, created["task_id"])
                self.assertEqual(result["goal_action"], "unchanged")
                self.assertEqual(task_sys.get_task(created["task_id"])["status"], task_sys.ACTIVE)

    def test_bound_task_with_missing_goal_is_canceled_once(self) -> None:
        created = self._create()
        goal = self._goal(self.context, created["task"]["objective"])
        task_sys.bind_goal(created["task_id"], goal)

        with patch.object(task_goal_handler.app_server, "goal_get", return_value={"goal": None}):
            first = task_goal_handler.reconcile_task(self.context, created["task_id"])
            second = task_goal_handler.reconcile_task(self.context, created["task_id"])

        task = task_sys.get_task(created["task_id"])
        self.assertEqual(first["goal_action"], "canceled_missing_goal")
        self.assertEqual(second["goal_action"], "goal_absent")
        self.assertEqual(task["status"], task_sys.CANCELED)
        self.assertIn("cleared or missing", task["result"]["reason"])

    def test_canceled_task_clear_failure_keeps_terminal_state_and_retry_converges(self) -> None:
        created = self._create()
        goal = self._goal(self.context, created["task"]["objective"])
        task_sys.bind_goal(created["task_id"], goal)
        task_sys.record_task_cancel(created["task_id"], "Actor canceled before Goal completion.")

        with (
            patch.object(task_goal_handler.app_server, "goal_get", return_value={"goal": goal}),
            patch.object(
                task_goal_handler.app_server,
                "goal_clear",
                side_effect=[RuntimeError("clear failed"), {"cleared": True}],
            ) as clear_goal,
        ):
            with self.assertRaisesRegex(RuntimeError, "clear failed"):
                task_goal_handler.reconcile_task(self.context, created["task_id"])
            self.assertEqual(task_sys.get_task(created["task_id"])["status"], task_sys.CANCELED)
            result = task_goal_handler.reconcile_task(self.context, created["task_id"])

        self.assertEqual(result["goal_action"], "cleared_canceled")
        self.assertEqual(clear_goal.call_count, 2)

    def test_unfinished_mismatched_goal_is_explicit_conflict_without_overwrite(self) -> None:
        created = self._create()
        mismatch = self._goal(self.context, "A foreign unfinished objective.")

        with (
            patch.object(task_goal_handler.app_server, "goal_get", return_value={"goal": mismatch}),
            patch.object(task_goal_handler.app_server, "goal_set") as set_goal,
            patch.object(task_goal_handler.app_server, "goal_clear") as clear_goal,
        ):
            with self.assertRaises(task_goal_handler.TaskGoalInvariantError):
                task_goal_handler.reconcile_task(self.context, created["task_id"])

        self.assertIsNone(task_sys.get_task(created["task_id"])["goal_binding"])
        set_goal.assert_not_called()
        clear_goal.assert_not_called()

    def test_completed_goal_consumed_by_prior_task_is_cleared_before_next_goal(self) -> None:
        first = self._create(suffix="prior")
        prior_goal = self._goal(self.context, first["task"]["objective"], status="complete")
        task_sys.bind_goal(first["task_id"], prior_goal)
        task_sys.record_goal_complete(first["task_id"], prior_goal)
        second = self._create(suffix="next")
        next_goal = self._goal(
            self.context,
            second["task"]["objective"],
            status="active",
            created_at=200,
            updated_at=200,
        )

        with (
            patch.object(
                task_goal_handler.app_server,
                "goal_get",
                side_effect=[{"goal": prior_goal}, {"goal": next_goal}],
            ),
            patch.object(task_goal_handler.app_server, "goal_clear", return_value={"cleared": True}) as clear_goal,
            patch.object(task_goal_handler.app_server, "goal_set", return_value={"goal": next_goal}) as set_goal,
        ):
            result = task_goal_handler.reconcile_task(self.context, second["task_id"])

        self.assertEqual(result["goal_action"], "replaced_terminal_and_bound")
        clear_goal.assert_called_once()
        set_goal.assert_called_once()
        self.assertEqual(task_sys.get_task(second["task_id"])["goal_binding"]["goal_created_at"], 200)

    def test_wrong_thread_goal_notification_is_ignored_without_query(self) -> None:
        handler = task_goal_handler.TaskGoalHandler()
        trigger = daemon_triggers.normalize_app_server_notification(
            {
                "method": "thread/goal/updated",
                "params": {
                    "threadId": "thread-other",
                    "turnId": "turn-other",
                    "goal": self._goal(self.context, "Other objective."),
                },
            },
            target_identity_id=self.actor_id,
            target_role_id="dev",
        )

        with patch.object(task_goal_handler.app_server, "goal_get") as get_goal:
            result = handler.handle(self.context, object(), object(), trigger)

        self.assertEqual(result.status, "ignored")
        get_goal.assert_not_called()

    def test_startup_reconcile_repairs_goal_completed_while_daemon_was_down(self) -> None:
        created = self._create()
        active_goal = self._goal(self.context, created["task"]["objective"])
        task_sys.bind_goal(created["task_id"], active_goal)
        completed_goal = dict(active_goal, status="complete", updatedAt=180)
        handler = task_goal_handler.TaskGoalHandler()

        with patch.object(task_goal_handler.app_server, "goal_get", return_value={"goal": completed_goal}):
            result = handler.reconcile(self.context, object(), object())

        self.assertEqual(result.status, "handled")
        self.assertEqual(task_sys.get_task(created["task_id"])["status"], task_sys.COMPLETED)

    def test_instance_daemon_registers_only_current_task_goal_command_and_handler(self) -> None:
        self.assertEqual(
            task_goal_runtime_protocol.COMMAND_KEYS,
            frozenset({"task_goal.reconcile_task"}),
        )
        factories = instance_daemon.default_application_command_factories()
        handlers = instance_daemon.default_daemon_handlers()

        self.assertIn(task_goal_handler.command_handlers, factories)
        self.assertTrue(any(isinstance(row, task_goal_handler.TaskGoalHandler) for row in handlers))
        self.assertNotIn("task_sys_daemon_adapter", Path(instance_daemon.__file__).read_text(encoding="utf-8"))
