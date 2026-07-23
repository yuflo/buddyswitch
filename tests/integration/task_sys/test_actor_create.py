"""Actor-created Demand Task contract tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any

from env.domain import task_sys
from tests.support.paths import REPO_ROOT, SCRIPTS_ROOT
from tests.support.processes import ResourceLedger
from tests.support.runtime import RuntimeWorkspaceTestCase


class TaskSysActorCreateTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor_target = {
            "actor_id": self._runtime_actor_id(role="pm", label="phase3-task-create"),
            "role_id": "pm",
        }

    def _demand_ref(
        self,
        *,
        demand_id: str = "demand-phase3-create",
        basis_revision: int = 3,
    ) -> dict[str, Any]:
        return {
            "demand_id": demand_id,
            "basis_revision": basis_revision,
            "demand_ref": f"dref-{demand_id.removeprefix('demand-')}-{basis_revision}",
        }

    def _actor_demand_ref(
        self,
        *,
        demand_id: str = "demand-phase3-create",
        basis_revision: int = 3,
    ) -> dict[str, str]:
        demand_ref = self._demand_ref(
            demand_id=demand_id,
            basis_revision=basis_revision,
        )
        return {
            "demand_id": str(demand_ref["demand_id"]),
            "demand_ref": str(demand_ref["demand_ref"]),
        }

    def _execution_brief(self) -> dict[str, str]:
        return {
            "description": "Inspect the current product contract.",
            "detail": "Read the current contract and report the exact first priority.",
        }

    def _child_env(self) -> dict[str, str]:
        env = os.environ.copy()
        python_paths = [str(SCRIPTS_ROOT), str(REPO_ROOT)]
        if env.get("PYTHONPATH"):
            python_paths.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(python_paths)
        return env

    def test_create_persists_exact_demand_snapshot_and_starts_canonical_side_lifecycle(self) -> None:
        result = task_sys.create(
            actor_target=self.actor_target,
            demand_ref=self._demand_ref(),
            execution_brief=self._execution_brief(),
        )

        self.assertEqual(result["outcome"], "created")
        self.assertIs(result["state_changed"], True)
        task = result["task"]
        self.assertTrue(task["id"].startswith("task-demand-"), task["id"])
        self.assertEqual(task_sys.get_task(result["task_id"]), task)
        self.assertEqual(task["source_type"], "demand")
        self.assertEqual(task["source_ref"], self._demand_ref())
        self.assertEqual(
            task["inbound_context"],
            {"execution_brief": self._execution_brief()},
        )
        self.assertEqual(task["status"], task_sys.SIDE_PROCESSING)
        self.assertEqual(task["execution"]["processor"], "side")
        self.assertEqual(
            [event["type"] for event in task["events"]],
            ["created", "side_frame_started"],
        )
        instruction = result["instruction"]
        self.assertEqual(instruction["type"], "start_side")
        self.assertEqual(instruction["task_id"], task["id"])
        self.assertEqual(instruction["frame"]["source"], {
            "type": "demand",
            "ref": self._actor_demand_ref(),
        })
        self.assertEqual(
            instruction["frame"]["context"],
            {"execution_brief": self._execution_brief()},
        )

    def test_exact_create_replay_returns_same_task_without_starting_another_side(self) -> None:
        created = task_sys.create(
            actor_target=self.actor_target,
            demand_ref=self._demand_ref(),
            execution_brief=self._execution_brief(),
        )

        replay = task_sys.create(
            actor_target=self.actor_target,
            demand_ref=self._demand_ref(),
            execution_brief=self._execution_brief(),
        )

        self.assertEqual(replay["outcome"], "existing")
        self.assertIs(replay["state_changed"], False)
        self.assertEqual(replay["task_id"], created["task_id"])
        self.assertEqual(replay["task"], created["task"])
        self.assertIsNone(replay["instruction"])
        self.assertEqual(
            [task["id"] for task in task_sys.list_tasks(actor_target=self.actor_target)],
            [created["task_id"]],
        )

    def test_same_demand_ref_with_different_brief_conflicts_without_write(self) -> None:
        created = task_sys.create(
            actor_target=self.actor_target,
            demand_ref=self._demand_ref(),
            execution_brief=self._execution_brief(),
        )
        before = task_sys.list_tasks(actor_target=self.actor_target)

        with self.assertRaises(task_sys.TaskSourceConflict) as raised:
            task_sys.create(
                actor_target=self.actor_target,
                demand_ref=self._demand_ref(),
                execution_brief={
                    "description": "Changed execution brief.",
                    "detail": "The same Demand revision cannot be replayed with new Task input.",
                },
            )

        self.assertEqual(raised.exception.code, "E_TASK_SYS_SOURCE_CONFLICT")
        self.assertEqual(raised.exception.task_id, created["task_id"])
        self.assertEqual(task_sys.list_tasks(actor_target=self.actor_target), before)

    def test_different_source_conflicts_while_actor_has_an_active_task(self) -> None:
        created = task_sys.create(
            actor_target=self.actor_target,
            demand_ref=self._demand_ref(),
            execution_brief=self._execution_brief(),
        )
        before = task_sys.list_tasks(actor_target=self.actor_target)

        with self.assertRaises(task_sys.TaskActiveConflict) as raised:
            task_sys.create(
                actor_target=self.actor_target,
                demand_ref=self._demand_ref(
                    demand_id="demand-phase3-other",
                    basis_revision=1,
                ),
                execution_brief={
                    "description": "Process another need.",
                    "detail": "This Task must wait until the current Task is terminal.",
                },
            )

        self.assertEqual(raised.exception.code, "E_TASK_SYS_ACTIVE_CONFLICT")
        self.assertEqual(raised.exception.task_id, created["task_id"])
        self.assertEqual(raised.exception.task_status, task_sys.SIDE_PROCESSING)
        self.assertEqual(task_sys.list_tasks(actor_target=self.actor_target), before)

    def test_new_demand_revision_can_create_after_previous_task_is_terminal(self) -> None:
        first = task_sys.create(
            actor_target=self.actor_target,
            demand_ref=self._demand_ref(),
            execution_brief=self._execution_brief(),
        )
        task_sys.record_task_close(first["task_id"], {"summary": "Revision three completed."})

        next_revision = task_sys.create(
            actor_target=self.actor_target,
            demand_ref=self._demand_ref(basis_revision=4),
            execution_brief={
                "description": "Inspect the revised product contract.",
                "detail": "Process the newly revised Demand snapshot.",
            },
        )

        self.assertEqual(next_revision["outcome"], "created")
        self.assertNotEqual(next_revision["task_id"], first["task_id"])
        self.assertEqual(next_revision["task"]["source_ref"]["basis_revision"], 4)
        self.assertEqual(
            {
                task["id"]: task["status"]
                for task in task_sys.list_tasks(actor_target=self.actor_target)
            },
            {
                first["task_id"]: task_sys.COMPLETED,
                next_revision["task_id"]: task_sys.SIDE_PROCESSING,
            },
        )

    def test_concurrent_different_sources_create_exactly_one_active_task(self) -> None:
        gate_path = self.runtime_root / "start-task-create-race"
        child_source = """
import json
from pathlib import Path
import sys
import time

from env.domain import task_sys

actor_target = {"actor_id": sys.argv[1], "role_id": "pm"}
index = int(sys.argv[2])
gate_path = Path(sys.argv[3])
deadline = time.monotonic() + 5.0
while not gate_path.exists() and time.monotonic() < deadline:
    time.sleep(0.005)
if not gate_path.exists():
    raise RuntimeError("race gate did not open")
try:
    result = task_sys.create(
        actor_target=actor_target,
        demand_ref={
            "demand_id": f"demand-race-{index}",
            "basis_revision": 1,
            "demand_ref": f"dref-race-{index}",
        },
        execution_brief={
            "description": f"Concurrent need {index}.",
            "detail": f"Only one concurrent need may become a Task: {index}.",
        },
    )
    print(json.dumps({"outcome": result["outcome"], "task_id": result["task_id"]}))
except task_sys.TaskActiveConflict as exc:
    print(json.dumps({"outcome": "active_conflict", "task_id": exc.task_id}))
"""
        ledger = ResourceLedger.from_environment()
        processes = [
            ledger.start_process(
                [
                    sys.executable,
                    "-c",
                    child_source,
                    self.actor_target["actor_id"],
                    str(index),
                    str(gate_path),
                ],
                cwd=REPO_ROOT,
                env=self._child_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for index in range(8)
        ]
        time.sleep(0.05)
        gate_path.write_text("go", encoding="utf-8")

        results: list[dict[str, str]] = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=5.0)
            self.assertEqual((process.returncode, stderr), (0, ""))
            results.append(json.loads(stdout))
        ledger.reconcile_descriptors()

        self.assertEqual(
            [result["outcome"] for result in results].count("created"),
            1,
        )
        self.assertEqual(
            [result["outcome"] for result in results].count("active_conflict"),
            7,
        )
        tasks = task_sys.list_tasks(actor_target=self.actor_target)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["status"], task_sys.SIDE_PROCESSING)
        self.assertEqual(
            {result["task_id"] for result in results},
            {tasks[0]["id"]},
        )

    def test_completed_demand_task_builds_one_strict_parent_outcome_instruction(self) -> None:
        created = task_sys.create(
            actor_target=self.actor_target,
            demand_ref=self._demand_ref(),
            execution_brief=self._execution_brief(),
        )
        closed = task_sys.record_task_close(
            created["task_id"],
            {"summary": "Satisfied the selected Demand snapshot."},
        )

        instruction = task_sys.outcome_instruction(created["task_id"])

        self.assertEqual(instruction["type"], "submit_parent")
        self.assertEqual(instruction["task_id"], created["task_id"])
        self.assertEqual(instruction["actor_target"], self.actor_target)
        self.assertEqual(
            instruction["frame"],
            {
                "kind": "task_sys.outcome_frame",
                "task_id": created["task_id"],
                "status": task_sys.COMPLETED,
                "source": {"type": "demand", "ref": self._actor_demand_ref()},
                "evidence_ref": {
                    "type": "task_sys.task",
                    "ref": {"task_id": created["task_id"]},
                },
                "outcome": closed["task"]["execution"]["result"],
            },
        )

    def test_canceled_demand_task_builds_one_strict_parent_outcome_instruction(self) -> None:
        created = task_sys.create(
            actor_target=self.actor_target,
            demand_ref=self._demand_ref(),
            execution_brief=self._execution_brief(),
        )
        canceled = task_sys.record_task_cancel(
            created["task_id"],
            {"reason": "The selected execution route is no longer viable."},
        )

        instruction = task_sys.outcome_instruction(created["task_id"])

        self.assertEqual(instruction["type"], "submit_parent")
        self.assertEqual(instruction["task_id"], created["task_id"])
        self.assertEqual(instruction["actor_target"], self.actor_target)
        self.assertEqual(
            instruction["frame"],
            {
                "kind": "task_sys.outcome_frame",
                "task_id": created["task_id"],
                "status": task_sys.CANCELED,
                "source": {"type": "demand", "ref": self._actor_demand_ref()},
                "evidence_ref": {
                    "type": "task_sys.task",
                    "ref": {"task_id": created["task_id"]},
                },
                "outcome": canceled["task"]["execution"]["result"],
            },
        )

if __name__ == "__main__":
    import unittest

    unittest.main()
