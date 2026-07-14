"""Tests for the minimal task sys substrate."""

from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"

from env.repos import runtime_files  # noqa: E402
from env.domain.identity import ActorIdentityProfile, IdentityRef  # noqa: E402
from tests.support.runtime import RuntimeWorkspaceTestCase  # noqa: E402


def _task_sys() -> Any:
    return importlib.import_module("env.domain.task_sys")


class TaskSysSubstrateTests(RuntimeWorkspaceTestCase):
    def _actor_profile(self, *, identity_id: str | None = None, role_id: str = "dev") -> ActorIdentityProfile:
        return ActorIdentityProfile(
            identity=IdentityRef(
                id=identity_id or self._runtime_actor_id(role="dev", label="act-dev-task-sys"),
                type="actor",
            ),
            role_id=role_id,
        )

    def _projection_record(
        self,
        *,
        task_id: str,
        actor_id: str,
        role_id: str,
        status: str = "in_progress",
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": task_id,
            "source_type": "test.projection",
            "source_ref": {"id": task_id},
            "actor_target": {"actor_id": actor_id, "role_id": role_id},
            "inbound_context": {"fixture": "projection"},
            "status": status,
            "task_desc": f"Summary {task_id}",
            "task_relation": {"kind": "independent", "target_task_id": None},
            "execution": {"processor": "side" if result is None else None, "handoff": None, "result": result},
            "events": [{"type": "created", "at": "2026-07-12T00:00:00Z"}],
            "created_at": "2026-07-12T00:00:00Z",
            "updated_at": "2026-07-12T00:00:01Z",
        }

    def test_actor_task_projection_reads_once_and_builds_all_current_groups(self) -> None:
        task_sys = _task_sys()
        actor_id = self._runtime_actor_id(role="dev", label="act-dev-task-sys")
        records = [
            self._projection_record(task_id="task-projection-active", actor_id=actor_id, role_id="dev"),
            self._projection_record(
                task_id="task-projection-recoverable",
                actor_id=actor_id,
                role_id="dev",
                result={"type": "failure", "reason": "runtime_failed", "stage": "side_input"},
            ),
            self._projection_record(
                task_id="task-projection-completed",
                actor_id=actor_id,
                role_id="dev",
                status="completed",
            ),
            self._projection_record(task_id="task-projection-other-actor", actor_id="act-dev-other", role_id="dev"),
            self._projection_record(task_id="task-projection-other-role", actor_id=actor_id, role_id="pm"),
        ]

        with mock.patch.object(task_sys, "list_tasks", return_value=records) as read_records:
            projection = task_sys.actor_task_projection(actor_profile=self._actor_profile())

        read_records.assert_called_once_with()
        self.assertEqual(projection["task_count"], 3)
        self.assertEqual(projection["active_count"], 1)
        self.assertEqual(projection["recoverable_count"], 1)
        self.assertEqual(
            [row["task_id"] for row in projection["tasks"]],
            ["task-projection-active", "task-projection-recoverable", "task-projection-completed"],
        )
        self.assertEqual([row["task_id"] for row in projection["active_tasks"]], ["task-projection-active"])
        self.assertEqual(
            [row["task_id"] for row in projection["recoverable_tasks"]],
            ["task-projection-recoverable"],
        )
        summary_keys = set(projection["tasks"][0])
        for group in ("tasks", "active_tasks", "recoverable_tasks"):
            for row in projection[group]:
                self.assertEqual(set(row), summary_keys)
                self.assertEqual(row["id"], row["task_id"])
                self.assertEqual(row["event_types"], ["created"])
                self.assertEqual(row["task_relation"], {"kind": "independent", "target_task_id": None})

    def test_actor_task_projection_empty_storage_has_zero_counts(self) -> None:
        task_sys = _task_sys()

        with mock.patch.object(task_sys, "list_tasks", return_value=[]) as read_records:
            projection = task_sys.actor_task_projection(actor_profile=self._actor_profile())

        read_records.assert_called_once_with()
        self.assertEqual(
            projection,
            {
                "tasks": [],
                "active_tasks": [],
                "recoverable_tasks": [],
                "task_count": 0,
                "active_count": 0,
                "recoverable_count": 0,
            },
        )

    def _envelope(self) -> dict[str, Any]:
        return {
            "source": {
                "type": "user.input",
                "ref": {"id": "input-1", "surface": "cli"},
            },
            "actor_target": {
                "role_id": "dev",
                "actor_id": self._runtime_actor_id(role="dev", label="act-dev-task-sys"),
            },
            "context": {
                "text": "Draft brief",
                "surface": "cli",
            },
        }

    def _task_record_path(self, task_id: str) -> Path:
        return runtime_files.OBJECTS_ROOT / "task-sys" / "tasks" / f"{task_id}.json"

    def _task_record(self, task_id: str) -> dict[str, Any]:
        return json.loads(self._task_record_path(task_id).read_text(encoding="utf-8"))

    def _task_records(self) -> list[dict[str, Any]]:
        tasks_dir = runtime_files.OBJECTS_ROOT / "task-sys" / "tasks"
        if not tasks_dir.exists():
            return []
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(tasks_dir.glob("*.json"))
        ]

    def _event_types(self, task_id: str) -> list[str]:
        record = self._task_record(task_id)
        events = record.get("events")
        self.assertIsInstance(events, list, msg=record)
        assert isinstance(events, list)
        return [str(row.get("type")) for row in events if isinstance(row, dict)]

    def _assert_no_legacy_execution_fields(self, record: dict[str, Any]) -> None:
        for field in ("active_processor", "side_result", "parent_handoff_params", "failure_result", "close_result"):
            with self.subTest(field=field):
                self.assertNotIn(field, record)

    def _move_to_needs_parent(self, task_id: str) -> None:
        task_sys = _task_sys()
        task_sys.record_task_analysis_update(
            task_id,
            {
                "task_desc": "Draft brief",
                "task_relation": {"kind": "independent", "target_task_id": None},
            },
        )
        task_sys.record_side_need_parent(
            task_id,
            {
                "params": {
                    "parent_frame_context": {
                        "next": "Draft the brief in parent.",
                        "task_desc": "Draft brief",
                        "task_relation": {"kind": "independent", "target_task_id": None},
                    },
                    "interrupt": True,
                },
            },
        )

    def test_ingest_persists_task_record_and_returns_start_side_instruction(self) -> None:
        task_sys = _task_sys()
        envelope = self._envelope()

        result = task_sys.ingest(envelope)

        self.assertTrue(result.get("ok"), msg=result)
        task_id = result.get("task_id")
        self.assertIsInstance(task_id, str, msg=result)
        assert isinstance(task_id, str)
        self.assertTrue(task_id.startswith("task-"), msg=task_id)
        record_path = self._task_record_path(task_id)
        self.assertTrue(record_path.exists(), msg=record_path)
        persisted = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(result.get("task"), persisted)
        self.assertEqual(persisted["id"], task_id)
        self.assertEqual(persisted["source_type"], "user.input")
        self.assertEqual(persisted["source_ref"], {"id": "input-1", "surface": "cli"})
        self.assertEqual(persisted["actor_target"], envelope["actor_target"])
        self.assertEqual(persisted["inbound_context"], envelope["context"])
        self.assertEqual(persisted["status"], "in_progress")
        self.assertIsNone(persisted["task_desc"])
        self.assertEqual(persisted["task_relation"], {"kind": "independent", "target_task_id": None})
        self.assertEqual(
            persisted["execution"],
            {
                "processor": "side",
                "handoff": None,
                "result": None,
            },
        )
        self._assert_no_legacy_execution_fields(persisted)
        self.assertNotIn("checkpoint_metadata", persisted)
        events = persisted.get("events")
        self.assertIsInstance(events, list, msg=persisted)
        assert isinstance(events, list)
        self.assertGreaterEqual(len(events), 2, msg=events)
        self.assertEqual(events[0].get("type"), "created")
        self.assertIn("side_frame_started", [row.get("type") for row in events if isinstance(row, dict)])
        self.assertIsInstance(persisted.get("created_at"), str)
        self.assertIsInstance(persisted.get("updated_at"), str)

        instruction = result.get("instruction")
        self.assertIsInstance(instruction, dict, msg=result)
        assert isinstance(instruction, dict)
        self.assertEqual(instruction["type"], "start_side")
        self.assertEqual(instruction["task_id"], task_id)
        self.assertEqual(instruction["actor_target"], envelope["actor_target"])
        frame = instruction.get("frame")
        self.assertIsInstance(frame, dict, msg=instruction)
        assert isinstance(frame, dict)
        self.assertEqual(frame["kind"], "task_sys.side_frame")
        self.assertEqual(frame["task_id"], task_id)
        self.assertEqual(frame["source"], {"type": "user.input", "ref": {"id": "input-1", "surface": "cli"}})
        self.assertEqual(frame["actor_target"], envelope["actor_target"])
        self.assertEqual(frame["context"], envelope["context"])

    def test_ingest_rejects_initial_processor_variants_without_creating_tasks(self) -> None:
        task_sys = _task_sys()
        for value in ("none", "checkpoint", "side"):
            with self.subTest(initial_processor=value):
                with self.assertRaisesRegex(ValueError, "initial_processor"):
                    task_sys.ingest({**self._envelope(), "initial_processor": value})
                self.assertEqual(self._task_records(), [])

    def test_record_task_analysis_update_writes_desc_and_independent_relation(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]

        result = task_sys.record_task_analysis_update(
            task_id,
            {
                "task_desc": "Draft brief",
                "task_relation": {"kind": "independent", "target_task_id": None},
            },
        )

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["task_id"], task_id)
        record = self._task_record(task_id)
        self.assertEqual(record["task_desc"], "Draft brief")
        self.assertEqual(record["task_relation"], {"kind": "independent", "target_task_id": None})
        self.assertIsInstance(record["updated_at"], str)
        self.assertIn("task_analysis_updated", self._event_types(task_id))

    def test_record_task_analysis_update_accepts_after_and_before_same_actor_target(self) -> None:
        task_sys = _task_sys()
        first_task_id = task_sys.ingest(self._envelope())["task_id"]
        second_task_id = task_sys.ingest(self._envelope())["task_id"]

        after_result = task_sys.record_task_analysis_update(
            second_task_id,
            {
                "task_desc": "Continue brief",
                "task_relation": {"kind": "after", "target_task_id": first_task_id},
            },
        )
        before_result = task_sys.record_task_analysis_update(
            first_task_id,
            {
                "task_desc": "Prepare input",
                "task_relation": {"kind": "before", "target_task_id": second_task_id},
            },
        )

        self.assertTrue(after_result["ok"], msg=after_result)
        self.assertTrue(before_result["ok"], msg=before_result)
        self.assertEqual(
            self._task_record(second_task_id)["task_relation"],
            {"kind": "after", "target_task_id": first_task_id},
        )
        self.assertEqual(
            self._task_record(first_task_id)["task_relation"],
            {"kind": "before", "target_task_id": second_task_id},
        )

    def test_record_task_analysis_update_rejects_invalid_desc_without_mutating(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        before = self._task_record(task_id)

        for task_desc in ("", "   ", "x" * 50):
            with self.subTest(task_desc=task_desc):
                with self.assertRaisesRegex(ValueError, "task_desc"):
                    task_sys.record_task_analysis_update(
                        task_id,
                        {
                            "task_desc": task_desc,
                            "task_relation": {"kind": "independent", "target_task_id": None},
                        },
                    )
                self.assertEqual(self._task_record(task_id), before)

    def test_record_task_analysis_update_rejects_invalid_relation_without_mutating(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        other_actor_envelope = self._envelope()
        other_actor_envelope["actor_target"] = {
            "role_id": "dev",
            "actor_id": self._runtime_actor_id(role="dev", label="act-dev-other-task-sys"),
        }
        cross_actor_task_id = task_sys.ingest(other_actor_envelope)["task_id"]
        before = self._task_record(task_id)
        cases = (
            ({"kind": "related", "target_task_id": None}, "kind"),
            ({"kind": "after", "target_task_id": None}, "target_task_id"),
            ({"kind": "before"}, "target_task_id"),
            ({"kind": "after", "target_task_id": "task-user-input-missing"}, "not found"),
            ({"kind": "before", "target_task_id": cross_actor_task_id}, "same actor"),
            ({"kind": "after", "target_task_id": task_id}, "self"),
        )

        for relation, expected in cases:
            with self.subTest(relation=relation):
                with self.assertRaisesRegex(ValueError, expected):
                    task_sys.record_task_analysis_update(
                        task_id,
                        {
                            "task_desc": "Draft brief",
                            "task_relation": relation,
                        },
                    )
                self.assertEqual(self._task_record(task_id), before)

    def test_parent_runtime_instruction_shapes_are_task_traceable(self) -> None:
        task_sys = _task_sys()
        actor_target = self._envelope()["actor_target"]
        frame = {
            "kind": "task_sys.parent_frame",
            "task_id": "task-user-input-123456abcdef",
            "context": {"text": "Draft brief"},
        }

        submit = task_sys.runtime_instruction(
            "submit_parent",
            task_id="task-user-input-123456abcdef",
            actor_target=actor_target,
            frame=frame,
        )
        interrupt = task_sys.runtime_instruction(
            "interrupt_submit_parent",
            task_id="task-user-input-123456abcdef",
            actor_target=actor_target,
            frame=frame,
        )

        self.assertEqual(submit["type"], "submit_parent")
        self.assertEqual(interrupt["type"], "interrupt_submit_parent")
        for instruction in (submit, interrupt):
            with self.subTest(instruction=instruction["type"]):
                self.assertEqual(instruction["task_id"], "task-user-input-123456abcdef")
                self.assertEqual(instruction["actor_target"], actor_target)
                self.assertEqual(instruction["frame"], frame)

        with self.assertRaisesRegex(ValueError, "runtime instruction"):
            task_sys.runtime_instruction(
                "side_interrupt",
                task_id="task-user-input-123456abcdef",
                actor_target=actor_target,
                frame=frame,
            )

    def test_parent_instruction_from_need_parent_task_stays_parent_ready_until_runtime_start(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        task_sys.record_task_analysis_update(
            task_id,
            {
                "task_desc": "Draft brief",
                "task_relation": {"kind": "independent", "target_task_id": None},
            },
        )
        task_sys.record_side_need_parent(
            task_id,
            {
                "params": {
                    "parent_frame_context": {
                        "next": "Draft the brief in parent.",
                        "task_desc": "Draft brief",
                        "task_relation": {"kind": "independent", "target_task_id": None},
                    },
                    "interrupt": True,
                    "ordering": {"priority": "normal"},
                },
            },
        )

        instruction = task_sys.parent_handoff_instruction(task_id)

        self.assertEqual(instruction["type"], "interrupt_submit_parent")
        self.assertEqual(instruction["task_id"], task_id)
        self.assertEqual(instruction["actor_target"], self._envelope()["actor_target"])
        frame = instruction.get("frame")
        self.assertIsInstance(frame, dict, msg=instruction)
        assert isinstance(frame, dict)
        self.assertEqual(frame["kind"], "task_sys.parent_frame")
        self.assertEqual(frame["task_id"], task_id)
        self.assertEqual(frame["source"], {"type": "user.input", "ref": {"id": "input-1", "surface": "cli"}})
        self.assertEqual(frame["inbound_context"], self._envelope()["context"])
        self.assertEqual(frame["task_desc"], "Draft brief")
        self.assertEqual(frame["task_relation"], {"kind": "independent", "target_task_id": None})
        self.assertEqual(
            frame["execution_handoff"],
            {
                "parent_frame_context": {
                    "next": "Draft the brief in parent.",
                    "task_desc": "Draft brief",
                    "task_relation": {"kind": "independent", "target_task_id": None},
                },
                "interrupt": True,
                "ordering": {"priority": "normal"},
                "side_thread_id": None,
                "cleanup": {},
            },
        )
        persisted = json.loads(self._task_record_path(task_id).read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], "in_progress")
        self.assertEqual(persisted["execution"]["processor"], None)
        self.assertEqual(persisted["execution"]["handoff"], frame["execution_handoff"])
        self.assertIsNone(persisted["execution"]["result"])
        self._assert_no_legacy_execution_fields(persisted)

    def test_side_need_parent_requires_recorded_relation_analysis(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]

        with self.assertRaisesRegex(ValueError, "task analysis"):
            task_sys.record_side_need_parent(
                task_id,
                {
                    "params": {
                        "parent_frame_context": {"next": "Draft the brief in parent."},
                        "interrupt": True,
                    },
                },
            )

        persisted = self._task_record(task_id)
        self.assertEqual(persisted["status"], "in_progress")
        self.assertIsNone(persisted["task_desc"])
        self.assertEqual(persisted["task_relation"], {"kind": "independent", "target_task_id": None})
        self.assertEqual(persisted["execution"]["processor"], "side")
        self.assertIsNone(persisted["execution"]["handoff"])

    def test_record_parent_handoff_started_marks_parent_processing(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        self._move_to_needs_parent(task_id)

        result = task_sys.record_parent_handoff_started(task_id)

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["task_id"], task_id)
        persisted = json.loads(self._task_record_path(task_id).read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], "in_progress")
        self.assertEqual(persisted["execution"]["processor"], "parent")
        self.assertIsInstance(persisted["execution"]["handoff"], dict)
        self.assertIsNone(persisted["execution"]["result"])
        self._assert_no_legacy_execution_fields(persisted)

    def test_record_side_cleanup_updates_need_parent_execution_handoff(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        self._move_to_needs_parent(task_id)

        result = task_sys.record_side_cleanup(
            task_id,
            {
                "side_thread_id": "thr-side-parent",
                "cleanup": {
                    "lease_unregistered": True,
                    "turn_interrupt_ok": True,
                },
            },
        )

        self.assertTrue(result["ok"], msg=result)
        record = self._task_record(task_id)
        self.assertEqual(record["status"], "in_progress")
        self.assertEqual(record["execution"]["processor"], None)
        self.assertEqual(record["execution"]["handoff"]["side_thread_id"], "thr-side-parent")
        self.assertEqual(record["execution"]["handoff"]["cleanup"]["lease_unregistered"], True)
        self.assertEqual(record["execution"]["handoff"]["cleanup"]["turn_interrupt_ok"], True)
        self._assert_no_legacy_execution_fields(record)
        self.assertIn("side_cleanup_recorded", self._event_types(task_id))

    def test_record_task_close_closes_side_processing_task(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]

        result = task_sys.record_task_close(task_id, {"summary": "Handled in side."})

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["outcome"], "close")
        self.assertEqual(result["task_id"], task_id)
        record = self._task_record(task_id)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["execution"]["processor"], None)
        self.assertEqual(record["execution"]["result"]["type"], "completion")
        self.assertEqual(record["execution"]["result"]["processor"], "side")
        self.assertEqual(record["execution"]["result"]["summary"], "Handled in side.")
        self.assertIsInstance(record["execution"]["result"]["updated_at"], str)
        self._assert_no_legacy_execution_fields(record)
        event_types = self._event_types(task_id)
        self.assertEqual(event_types[0], "created")
        self.assertIn("closed", event_types)

    def test_record_side_cleanup_updates_side_completion_result(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        task_sys.record_task_close(task_id, {"summary": "Handled in side."})

        result = task_sys.record_side_cleanup(
            task_id,
            {
                "side_thread_id": "thr-side-clean",
                "cleanup": {
                    "lease_unregistered": True,
                    "turn_interrupt_ok": False,
                    "turn_interrupt_error": "thread already gone",
                },
            },
        )

        self.assertTrue(result["ok"], msg=result)
        record = self._task_record(task_id)
        self.assertEqual(record["execution"]["result"]["processor"], "side")
        self.assertEqual(record["execution"]["result"]["side_thread_id"], "thr-side-clean")
        self.assertEqual(record["execution"]["result"]["cleanup"]["lease_unregistered"], True)
        self.assertEqual(record["execution"]["result"]["cleanup"]["turn_interrupt_ok"], False)
        self.assertEqual(record["execution"]["result"]["cleanup"]["turn_interrupt_error"], "thread already gone")
        self._assert_no_legacy_execution_fields(record)
        self.assertIn("side_cleanup_recorded", self._event_types(task_id))

    def test_record_task_close_closes_parent_processing_task(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        self._move_to_needs_parent(task_id)
        task_sys.record_parent_handoff_started(task_id)

        result = task_sys.record_task_close(task_id, {"summary": "Parent completed the source task."})

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["outcome"], "close")
        record = self._task_record(task_id)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["execution"]["processor"], None)
        self.assertEqual(record["execution"]["result"]["type"], "completion")
        self.assertEqual(record["execution"]["result"]["processor"], "parent")
        self.assertEqual(record["execution"]["result"]["summary"], "Parent completed the source task.")
        self.assertIsInstance(record["execution"]["result"]["updated_at"], str)
        self._assert_no_legacy_execution_fields(record)
        self.assertEqual(
            self._event_types(task_id),
            [
                "created",
                "side_frame_started",
                "task_analysis_updated",
                "side_parent_requested",
                "parent_handoff_started",
                "closed",
            ],
        )

    def test_record_task_close_rejects_needs_parent_task(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        self._move_to_needs_parent(task_id)

        with self.assertRaisesRegex(ValueError, "side or parent processor"):
            task_sys.record_task_close(task_id, {"summary": "Skipped parent."})

        record = self._task_record(task_id)
        self.assertEqual(record["status"], "in_progress")
        self.assertEqual(record["execution"]["processor"], None)
        self.assertIsInstance(record["execution"]["handoff"], dict)
        self.assertIsNone(record["execution"]["result"])
        self._assert_no_legacy_execution_fields(record)

    def test_task_statuses_are_lifecycle_only(self) -> None:
        task_sys = _task_sys()

        self.assertEqual(task_sys.TASK_STATUSES, ("in_progress", "completed", "canceled"))
        self.assertEqual(task_sys.ACTIVE_TASK_STATUSES, ("in_progress",))
        self.assertEqual(task_sys.RECOVERABLE_TASK_REASONS, ("runtime_failed", "side_no_result", "side_timed_out"))
        self.assertEqual(task_sys.TASK_RELATION_KINDS, ("independent", "after", "before"))
        self.assertNotIn("checkpoint", task_sys.TASK_STATUSES)
        self.assertNotIn("no_actor_action", task_sys.RUNTIME_INSTRUCTION_TYPES)

    def test_side_runtime_failure_is_recoverable_but_not_active(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        original = self._task_record(task_id)

        result = task_sys.record_side_runtime_failure(
            task_id,
            {
                "reason": "runtime_failed",
                "stage": "side_input",
                "processor": "side",
                "error": "thread not loaded",
                "retryable": True,
                "attempts": 2,
                "last_side_thread_id": "thr-side-stale",
                "cleanup": {
                    "lease_unregistered": True,
                    "turn_interrupt_ok": False,
                    "turn_interrupt_error": "thread not loaded",
                },
            },
        )

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["outcome"], "runtime_failed")
        self.assertEqual(result["task_id"], task_id)
        record = self._task_record(task_id)
        self.assertEqual(record["status"], "in_progress")
        self.assertEqual(record["execution"]["processor"], None)
        self.assertEqual(record["execution"]["result"]["type"], "failure")
        self.assertEqual(record["execution"]["result"]["reason"], "runtime_failed")
        self.assertEqual(record["execution"]["result"]["stage"], "side_input")
        self.assertEqual(record["execution"]["result"]["processor"], "side")
        self.assertEqual(record["execution"]["result"]["error"], "thread not loaded")
        self.assertIs(record["execution"]["result"]["retryable"], True)
        self.assertEqual(record["execution"]["result"]["attempts"], 2)
        self.assertEqual(record["execution"]["result"]["last_side_thread_id"], "thr-side-stale")
        self.assertEqual(record["execution"]["result"]["cleanup"]["lease_unregistered"], True)
        self.assertIsInstance(record["execution"]["result"]["updated_at"], str)
        self._assert_no_legacy_execution_fields(record)
        for field in ("source_type", "source_ref", "actor_target", "inbound_context"):
            with self.subTest(field=field):
                self.assertEqual(record[field], original[field])
        self.assertIn("side_runtime_failed", self._event_types(task_id))

        self.assertEqual(
            set(task_sys.RECOVERABLE_TASK_REASONS),
            {"runtime_failed", "side_no_result", "side_timed_out"},
        )
        projection = task_sys.actor_task_projection(actor_profile=self._actor_profile())
        self.assertEqual(projection["active_tasks"], [])
        self.assertEqual([row["id"] for row in projection["recoverable_tasks"]], [task_id])

    def test_failed_side_runtime_task_cannot_be_closed_as_success(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        task_sys.record_side_runtime_failure(
            task_id,
            {
                "reason": "side_no_result",
                "stage": "side_turn",
                "processor": "side",
                "error": "side frame completed without task_sys.close or task_sys.need_parent",
                "retryable": True,
                "attempts": 1,
            },
        )

        with self.assertRaisesRegex(ValueError, "side or parent processor"):
            task_sys.record_task_close(task_id, {"summary": "Pretend success."})

        record = self._task_record(task_id)
        self.assertEqual(record["status"], "in_progress")
        self.assertEqual(record["execution"]["processor"], None)
        self.assertEqual(record["execution"]["result"]["type"], "failure")
        self.assertEqual(record["execution"]["result"]["reason"], "side_no_result")
        self._assert_no_legacy_execution_fields(record)

    def test_record_task_close_is_retry_safe_for_closed_task(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        first = task_sys.record_task_close(task_id, {"summary": "Initial close."})

        second = task_sys.record_task_close(task_id, {"summary": "Retry close."})

        self.assertTrue(second["ok"], msg=second)
        self.assertEqual(second["outcome"], "close")
        record = self._task_record(task_id)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["execution"]["processor"], None)
        self.assertEqual(record["execution"]["result"], first["task"]["execution"]["result"])
        self._assert_no_legacy_execution_fields(record)

    def test_parent_instruction_rejects_non_parent_ready_task(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]

        with self.assertRaisesRegex(ValueError, "parent handoff"):
            task_sys.parent_handoff_instruction(task_id)

    def test_ingest_rejects_invalid_envelope_shapes(self) -> None:
        task_sys = _task_sys()
        valid = self._envelope()
        cases = (
            ({}, "source"),
            ({**valid, "source": "user.input"}, "source"),
            ({**valid, "source": {"ref": {"id": "input-1"}}}, "source.type"),
            ({**valid, "source": {"type": "user.input"}}, "source.ref"),
            ({**valid, "actor_target": {"role_id": "dev"}}, "actor_target.actor_id"),
            ({**valid, "actor_target": {"actor_id": valid["actor_target"]["actor_id"]}}, "actor_target.role_id"),
            ({**valid, "context": "Draft brief"}, "context"),
            ({**valid, "initial_processor": "parent"}, "initial_processor"),
            ({**valid, "initial_processor": "side"}, "initial_processor"),
            ({**valid, "initial_processor": "checkpoint"}, "initial_processor"),
        )
        for payload, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(ValueError, expected):
                    task_sys.ingest(payload)

    def test_task_sys_substrate_has_no_daemon_or_taskbox_dependencies(self) -> None:
        source = (ROOT / "scripts" / "env" / "domain" / "task_sys.py").read_text(encoding="utf-8")

        for forbidden in (
            "daemon_core",
            "daemon_client",
            "app_server",
            "tools.launcher",
            "task_management",
            "taskbox",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
