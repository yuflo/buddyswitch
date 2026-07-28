"""Actor Task creation stays Demand-bound and native-Goal-only."""

from __future__ import annotations

from buddyswitch.env.domain import task_sys
from tests.support.runtime import RuntimeWorkspaceTestCase


class TaskSysActorCreateTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor_target = {
            "actor_id": self._runtime_actor_id(role="pm", label="goal-task-create"),
            "role_id": "pm",
        }

    @staticmethod
    def _ref(revision: int = 3) -> dict[str, object]:
        return {
            "demand_id": "demand-goal-task-create",
            "basis_revision": revision,
            "demand_ref": f"dref-goal-task-create-{revision}",
        }

    def _create(self, revision: int = 3) -> dict[str, object]:
        return task_sys.create(
            actor_target=self.actor_target,
            demand_ref=self._ref(revision),
            objective=f"Deliver revision {revision} through one native Goal.",
            selection_reason=f"Revision {revision} is the current selected Demand snapshot.",
        )

    def test_create_records_current_demand_revision_without_execution_frame(self) -> None:
        result = self._create()

        self.assertEqual(result["task"]["demand_ref"], self._ref())
        self.assertEqual(result["task"]["status"], task_sys.ACTIVE)
        self.assertIsNone(result["task"]["goal_binding"])
        for retired in ("instruction", "frame", "execution", "events", "source_type", "source_ref"):
            self.assertNotIn(retired, result)
            self.assertNotIn(retired, result["task"])

    def test_exact_retry_is_idempotent_but_changed_selection_conflicts(self) -> None:
        first = self._create()
        replay = self._create()

        self.assertEqual(replay["task_id"], first["task_id"])
        self.assertEqual(replay["outcome"], "existing")
        with self.assertRaises(task_sys.TaskSourceConflict):
            task_sys.create(
                actor_target=self.actor_target,
                demand_ref=self._ref(),
                objective="Changed Task objective.",
                selection_reason="Changed selection judgment.",
            )

    def test_terminal_goal_task_releases_slot_for_new_demand_snapshot(self) -> None:
        first = self._create()
        goal = {
            "threadId": "thread-goal-task-create",
            "objective": first["task"]["objective"],
            "status": "complete",
            "tokenBudget": None,
            "tokensUsed": 42,
            "timeUsedSeconds": 5,
            "createdAt": 100,
            "updatedAt": 120,
        }
        task_sys.bind_goal(first["task_id"], goal)
        task_sys.record_goal_complete(first["task_id"], goal)

        second = self._create(revision=4)

        self.assertNotEqual(second["task_id"], first["task_id"])
        self.assertEqual(
            {
                row["id"]: row["status"]
                for row in task_sys.list_tasks(actor_target=self.actor_target)
            },
            {
                first["task_id"]: task_sys.COMPLETED,
                second["task_id"]: task_sys.ACTIVE,
            },
        )

    def test_actor_cancel_releases_slot_without_changing_demand_snapshot(self) -> None:
        first = self._create()
        original_ref = dict(first["task"]["demand_ref"])

        task_sys.record_task_cancel(first["task_id"], "Selection was explicitly stopped.")
        second = self._create(revision=4)

        self.assertEqual(task_sys.get_task(first["task_id"])["demand_ref"], original_ref)
        self.assertEqual(second["task"]["status"], task_sys.ACTIVE)
