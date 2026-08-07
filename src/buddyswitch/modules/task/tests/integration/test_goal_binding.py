"""Minimal Demand-bound Task owner contract for native Goal execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from buddyswitch.foundation.identity.model import ActorIdentityProfile, IdentityRef
import buddyswitch.foundation.state.runtime as state_runtime
from buddyswitch.modules.task.private.adapters.tool.tool import DEFINITION
from buddyswitch.modules.task.private.domain import task_sys
from tests.support.runtime import RuntimeWorkspaceTestCase


class TaskGoalBindingContractTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor_target = {
            "actor_id": self._runtime_actor_id(role="dev", label="goal-task-owner"),
            "role_id": "dev",
        }
        self.demand_ref = {
            "demand_id": "demand-goal-task-owner",
            "basis_revision": 4,
            "demand_ref": "dref-goal-task-owner",
        }
        self.objective = "Deliver one observable result, then mark the native Goal complete."
        self.selection_reason = "This is the only live Demand and the Task slot is empty."

    def _create(self, **overrides: Any) -> dict[str, Any]:
        values = {
            "actor_target": self.actor_target,
            "demand_ref": self.demand_ref,
            "objective": self.objective,
            "selection_reason": self.selection_reason,
        }
        values.update(overrides)
        return task_sys.create(**values)

    @staticmethod
    def _goal(
        *,
        thread_id: str = "thread-main-goal-task",
        objective: str = "Deliver one observable result, then mark the native Goal complete.",
        status: str = "active",
        created_at: int = 100,
        updated_at: int = 100,
    ) -> dict[str, Any]:
        return {
            "threadId": thread_id,
            "objective": objective,
            "status": status,
            "tokenBudget": None,
            "tokensUsed": 17,
            "timeUsedSeconds": 3,
            "createdAt": created_at,
            "updatedAt": updated_at,
        }

    def _task_path(self, task_id: str) -> Path:
        return state_runtime.OBJECTS_ROOT / "task-sys" / "tasks" / f"{task_id}.json"

    def test_create_writes_only_minimal_active_task_shape(self) -> None:
        result = self._create()

        self.assertEqual(result["outcome"], "created")
        self.assertIs(result["state_changed"], True)
        task = result["task"]
        self.assertEqual(
            set(task),
            {
                "schema_version",
                "id",
                "actor_target",
                "demand_ref",
                "objective",
                "selection",
                "goal_binding",
                "status",
                "result",
                "created_at",
                "updated_at",
            },
        )
        self.assertEqual(task["schema_version"], 1)
        self.assertEqual(task["actor_target"], self.actor_target)
        self.assertEqual(task["demand_ref"], self.demand_ref)
        self.assertEqual(task["objective"], self.objective)
        self.assertEqual(task["selection"]["reason"], self.selection_reason)
        self.assertIsInstance(task["selection"]["selected_at"], str)
        self.assertIsNone(task["goal_binding"])
        self.assertEqual(task["status"], task_sys.ACTIVE)
        self.assertIsNone(task["result"])
        self.assertEqual(task_sys.get_task(result["task_id"]), task)
        self.assertEqual(
            json.loads(self._task_path(result["task_id"]).read_text(encoding="utf-8")),
            task,
        )
        for retired in (
            "source_type",
            "source_ref",
            "inbound_context",
            "execution",
            "events",
            "processor",
            "handoff",
            "lease",
        ):
            self.assertNotIn(retired, task)

    def test_exact_create_retry_returns_same_active_task(self) -> None:
        created = self._create()

        replay = self._create()

        self.assertEqual(replay["outcome"], "existing")
        self.assertIs(replay["state_changed"], False)
        self.assertEqual(replay["task_id"], created["task_id"])
        self.assertEqual(
            [row["id"] for row in task_sys.list_tasks(actor_target=self.actor_target)],
            [created["task_id"]],
        )

    def test_one_active_task_rejects_another_demand_without_write(self) -> None:
        created = self._create()
        before = task_sys.list_tasks(actor_target=self.actor_target)

        with self.assertRaises(task_sys.TaskActiveConflict) as raised:
            self._create(
                demand_ref={
                    "demand_id": "demand-goal-task-other",
                    "basis_revision": 1,
                    "demand_ref": "dref-goal-task-other",
                },
                objective="Complete a different Demand.",
                selection_reason="This must wait.",
            )

        self.assertEqual(raised.exception.task_id, created["task_id"])
        self.assertEqual(raised.exception.task_status, task_sys.ACTIVE)
        self.assertEqual(task_sys.list_tasks(actor_target=self.actor_target), before)

    def test_same_demand_snapshot_with_changed_objective_conflicts(self) -> None:
        created = self._create()

        with self.assertRaises(task_sys.TaskSourceConflict) as raised:
            self._create(objective="A changed objective must not overwrite the active Task.")

        self.assertEqual(raised.exception.task_id, created["task_id"])

    def test_bind_goal_is_exact_and_idempotent(self) -> None:
        created = self._create()
        goal = self._goal()

        bound = task_sys.bind_goal(created["task_id"], goal)
        replay = task_sys.bind_goal(created["task_id"], goal)

        expected_binding = {
            "thread_id": goal["threadId"],
            "objective_hash": task_sys.objective_hash(self.objective),
            "goal_created_at": goal["createdAt"],
        }
        self.assertEqual(bound["task"]["goal_binding"], expected_binding)
        self.assertEqual(replay["task"]["goal_binding"], expected_binding)
        self.assertIs(bound["state_changed"], True)
        self.assertIs(replay["state_changed"], False)
        with self.assertRaises(task_sys.TaskGoalConflict):
            task_sys.bind_goal(
                created["task_id"],
                self._goal(thread_id="thread-other-goal-task"),
            )

    def test_only_matching_complete_goal_records_host_terminal_snapshot_once(self) -> None:
        created = self._create()
        active_goal = self._goal()
        task_sys.bind_goal(created["task_id"], active_goal)

        with self.assertRaises(task_sys.TaskGoalConflict):
            task_sys.record_goal_complete(
                created["task_id"],
                self._goal(status="blocked", updated_at=110),
            )
        completed_goal = self._goal(status="complete", updated_at=120)
        completed = task_sys.record_goal_complete(created["task_id"], completed_goal)
        replay = task_sys.record_goal_complete(created["task_id"], completed_goal)

        self.assertEqual(completed["task"]["status"], task_sys.COMPLETED)
        self.assertEqual(
            completed["task"]["result"],
            {
                "type": "goal_terminal",
                "goal_status": "complete",
                "thread_id": active_goal["threadId"],
                "objective_hash": task_sys.objective_hash(self.objective),
                "goal_created_at": active_goal["createdAt"],
                "goal_updated_at": 120,
                "token_budget": None,
                "tokens_used": 17,
                "time_used_seconds": 3,
                "recorded_at": completed["task"]["result"]["recorded_at"],
            },
        )
        self.assertIs(completed["state_changed"], True)
        self.assertIs(replay["state_changed"], False)

    def test_actor_cancel_is_terminal_and_does_not_mutate_demand(self) -> None:
        created = self._create()

        canceled = task_sys.record_task_cancel(
            created["task_id"],
            "The Actor explicitly stopped this Task.",
        )
        replay = task_sys.record_task_cancel(
            created["task_id"],
            "The Actor explicitly stopped this Task.",
        )

        self.assertEqual(canceled["task"]["status"], task_sys.CANCELED)
        self.assertEqual(canceled["task"]["result"]["type"], "actor_canceled")
        self.assertEqual(
            canceled["task"]["result"]["reason"],
            "The Actor explicitly stopped this Task.",
        )
        self.assertIs(canceled["state_changed"], True)
        self.assertIs(replay["state_changed"], False)
        self.assertEqual(self.demand_ref, created["task"]["demand_ref"])

    def test_retired_task_record_is_rejected_without_translation(self) -> None:
        tasks_dir = state_runtime.OBJECTS_ROOT / "task-sys" / "tasks"
        tasks_dir.mkdir(parents=True)
        retired_path = tasks_dir / "task-retired-frame.json"
        retired_path.write_text(
            json.dumps(
                {
                    "id": "task-retired-frame",
                    "status": "in_progress.side_processing",
                    "source_type": "demand",
                    "source_ref": self.demand_ref,
                    "execution": {"processor": "side"},
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "retired or invalid Task record"):
            task_sys.get_task("task-retired-frame")
        with self.assertRaisesRegex(ValueError, "retired or invalid Task record"):
            task_sys.list_tasks(actor_target=self.actor_target)

    def test_actor_scoped_list_ignores_foreign_current_schema_task(self) -> None:
        created = self._create()
        foreign_actor = {
            "actor_id": self._runtime_actor_id(role="dev", label="foreign-current-task"),
            "role_id": "dev",
        }
        foreign = task_sys.create(
            actor_target=foreign_actor,
            demand_ref={
                "demand_id": "demand-foreign-current-task",
                "basis_revision": 1,
                "demand_ref": "dref-foreign-current-task",
            },
            objective="Complete the independently current foreign Actor Task.",
            selection_reason="The foreign Actor has its own active Task slot.",
        )

        self.assertEqual(
            [row["id"] for row in task_sys.list_tasks(actor_target=self.actor_target)],
            [created["task_id"]],
        )
        self.assertEqual(
            {row["id"] for row in task_sys.list_tasks()},
            {created["task_id"], foreign["task_id"]},
        )

    def test_actor_scoped_list_rejects_owned_retired_task_record(self) -> None:
        tasks_dir = state_runtime.OBJECTS_ROOT / "task-sys" / "tasks"
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "task-demand-owned-retired.json").write_text(
            json.dumps(
                {
                    "id": "task-demand-owned-retired",
                    "actor_target": self.actor_target,
                    "status": "in_progress.side_processing",
                    "source_type": "demand",
                    "source_ref": self.demand_ref,
                    "execution": {"processor": "side"},
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "retired or invalid Task record"):
            task_sys.list_tasks(actor_target=self.actor_target)

    def test_actor_projection_has_active_and_terminal_groups_only(self) -> None:
        active = self._create()
        other_actor = {
            "actor_id": self._runtime_actor_id(role="dev", label="other-goal-task-owner"),
            "role_id": "dev",
        }
        terminal = task_sys.create(
            actor_target=other_actor,
            demand_ref={
                "demand_id": "demand-other-goal-task",
                "basis_revision": 1,
                "demand_ref": "dref-other-goal-task",
            },
            objective="Complete another actor's Task.",
            selection_reason="It is independently selected.",
        )
        task_sys.record_task_cancel(terminal["task_id"], "Fixture terminal state.")

        projection = task_sys.actor_task_projection(
            actor_profile=ActorIdentityProfile(
                identity=IdentityRef(id=self.actor_target["actor_id"], type="actor"),
                role_id=self.actor_target["role_id"],
            ),
        )

        self.assertEqual(
            set(projection),
            {
                "tasks",
                "active_tasks",
                "terminal_tasks",
                "task_count",
                "active_count",
                "terminal_count",
            },
        )
        self.assertEqual(projection["active_count"], 1)
        self.assertEqual(projection["terminal_count"], 0)
        self.assertEqual(projection["active_tasks"][0]["task_id"], active["task_id"])
        self.assertNotIn("recoverable_tasks", projection)
        self.assertNotIn("recoverable_count", projection)

    def test_actor_task_surface_and_runtime_protocol_are_minimal(self) -> None:
        self.assertEqual(
            {action.name for action in DEFINITION.actions},
            {"list", "get", "create", "cancel"},
        )
        create_action = next(action for action in DEFINITION.actions if action.name == "create")
        self.assertEqual(
            set(create_action.input_schema["properties"]),
            {"demand_ref", "objective", "selection_reason"},
        )
        self.assertEqual(
            create_action.input_schema["required"],
            ["demand_ref", "objective", "selection_reason"],
        )
        self.assertFalse(hasattr(task_sys, "record_task_close"))
        self.assertFalse(hasattr(task_sys, "record_side_need_parent"))

        from buddyswitch.modules.task.private.adapters.goal import protocol

        self.assertEqual(
            protocol.COMMAND_KEYS,
            frozenset({"task_goal.reconcile_task"}),
        )
