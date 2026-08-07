"""Read and ownership checks for the rebuilt Task substrate."""

from __future__ import annotations

from buddyswitch.foundation.identity.model import ActorIdentityProfile, IdentityRef
from buddyswitch.modules.task.private import read_model as task_read
from buddyswitch.modules.task.private.domain import task_sys
from tests.support.runtime import RuntimeWorkspaceTestCase


class TaskSysSubstrateTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor_target = {
            "actor_id": self._runtime_actor_id(role="dev", label="goal-task-substrate"),
            "role_id": "dev",
        }
        self.profile = ActorIdentityProfile(
            identity=IdentityRef(id=self.actor_target["actor_id"], type="actor"),
            role_id="dev",
        )

    def _create(self) -> dict[str, object]:
        return task_sys.create(
            actor_target=self.actor_target,
            demand_ref={
                "demand_id": "demand-goal-task-substrate",
                "basis_revision": 2,
                "demand_ref": "dref-goal-task-substrate",
            },
            objective="Prove the rebuilt Task read boundary.",
            selection_reason="This fixture is the only selected Demand.",
        )

    def test_external_projection_hides_internal_demand_revision(self) -> None:
        task = self._create()["task"]

        external = task_read.external_task_projection(task)

        self.assertEqual(
            external["demand_ref"],
            {
                "demand_id": "demand-goal-task-substrate",
                "demand_ref": "dref-goal-task-substrate",
            },
        )
        self.assertNotIn("basis_revision", external["demand_ref"])
        self.assertNotIn("execution", external)
        self.assertNotIn("events", external)

    def test_projection_classifies_only_active_and_terminal(self) -> None:
        created = self._create()

        active = task_read.actor_external_task_projection(actor_profile=self.profile)
        task_sys.record_task_cancel(created["task_id"], "Finish projection fixture.")
        terminal = task_read.actor_external_task_projection(actor_profile=self.profile)

        self.assertEqual(active["active_count"], 1)
        self.assertEqual(active["terminal_count"], 0)
        self.assertEqual(terminal["active_count"], 0)
        self.assertEqual(terminal["terminal_count"], 1)
        self.assertNotIn("recoverable_tasks", terminal)
        self.assertNotIn("recoverable_count", terminal)

    def test_get_external_task_enforces_actor_scope(self) -> None:
        created = self._create()
        other = ActorIdentityProfile(
            identity=IdentityRef(
                id=self._runtime_actor_id(role="dev", label="other-goal-task-substrate"),
                type="actor",
            ),
            role_id="dev",
        )

        self.assertIsNotNone(task_read.get_external_task(created["task_id"], actor_profile=self.profile))
        self.assertIsNone(task_read.get_external_task(created["task_id"], actor_profile=other))

    def test_invalid_status_filter_is_rejected(self) -> None:
        self._create()

        with self.assertRaisesRegex(ValueError, "unsupported Task status"):
            task_sys.list_tasks(statuses=("recoverable",))
