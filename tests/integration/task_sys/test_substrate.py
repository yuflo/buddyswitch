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
        status: str = "in_progress.side_processing",
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": task_id,
            "source_type": "test.projection",
            "source_ref": {"id": task_id},
            "actor_target": {"actor_id": actor_id, "role_id": role_id},
            "inbound_context": {"fixture": "projection"},
            "status": status,
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
        self.assertEqual(projection["active_count"], 2)
        self.assertEqual(projection["recoverable_count"], 1)
        self.assertEqual(
            [row["task_id"] for row in projection["tasks"]],
            ["task-projection-active", "task-projection-recoverable", "task-projection-completed"],
        )
        self.assertEqual(
            [row["task_id"] for row in projection["active_tasks"]],
            ["task-projection-active", "task-projection-recoverable"],
        )
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
                self.assertNotIn("task_desc", row)
                self.assertNotIn("task_relation", row)

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

    def _envelope(self, *, source_id: str = "event-1") -> dict[str, Any]:
        return {
            "source": {
                "type": "test.inbound.created",
                "ref": {"id": source_id, "channel": "fixture"},
            },
            "actor_target": {
                "role_id": "dev",
                "actor_id": self._runtime_actor_id(role="dev", label="act-dev-task-sys"),
            },
            "context": {
                "text": "Draft brief",
                "channel": "fixture",
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
        task_sys.record_side_need_parent(
            task_id,
            {
                "params": {
                    "parent_frame_context": {"next": "Draft the brief in parent."},
                    "interrupt": True,
                },
            },
        )

    def test_ingest_rejects_direct_user_input_without_persisting_task(self) -> None:
        task_sys = _task_sys()
        before = self._task_records()

        with self.assertRaisesRegex(ValueError, "user.input"):
            task_sys.ingest(
                {
                    "source": {
                        "type": "user.input",
                        "ref": {"id": "input-direct-1", "surface": "codex-tui"},
                    },
                    "actor_target": self._envelope()["actor_target"],
                    "context": {"text": "Uncontrolled direct input", "surface": "codex-tui"},
                }
            )

        self.assertEqual(self._task_records(), before)

    def test_ingest_rejects_im_message_without_persisting_task(self) -> None:
        task_sys = _task_sys()
        before = self._task_records()

        with self.assertRaisesRegex(ValueError, "im.message.created"):
            task_sys.ingest({
                "source": {
                    "type": "im.message.created",
                    "ref": {
                        "message_id": "msg-retired-1",
                        "conversation_id": "conv-retired-1",
                        "event_id": "imev-retired-1",
                    },
                },
                "actor_target": self._envelope()["actor_target"],
                "context": {"message_id": "msg-retired-1"},
            })

        self.assertEqual(self._task_records(), before)

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
        self.assertEqual(persisted["source_type"], "test.inbound.created")
        self.assertEqual(persisted["source_ref"], {"id": "event-1", "channel": "fixture"})
        self.assertEqual(persisted["actor_target"], envelope["actor_target"])
        self.assertEqual(persisted["inbound_context"], envelope["context"])
        self.assertEqual(persisted["status"], "in_progress.side_processing")
        self.assertNotIn("task_desc", persisted)
        self.assertNotIn("task_relation", persisted)
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
        self.assertEqual(
            frame["source"],
            {"type": "test.inbound.created", "ref": {"id": "event-1", "channel": "fixture"}},
        )
        self.assertEqual(frame["actor_target"], envelope["actor_target"])
        self.assertEqual(frame["context"], envelope["context"])

    def test_need_parent_moves_same_task_to_awaiting_parent_without_relation_analysis(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]

        result = task_sys.record_side_need_parent(
            task_id,
            {
                "params": {
                    "parent_frame_context": {"next": "Draft the brief in parent."},
                    "interrupt": False,
                },
            },
        )

        self.assertEqual(result["task_id"], task_id)
        self.assertEqual(result["task"]["status"], "in_progress.awaiting_parent")
        self.assertEqual(self._task_record(task_id)["status"], "in_progress.awaiting_parent")
        self.assertEqual([record["id"] for record in self._task_records()], [task_id])

    def test_ingest_rejects_initial_processor_variants_without_creating_tasks(self) -> None:
        task_sys = _task_sys()
        for value in ("none", "checkpoint", "side"):
            with self.subTest(initial_processor=value):
                with self.assertRaisesRegex(ValueError, "initial_processor"):
                    task_sys.ingest({**self._envelope(), "initial_processor": value})
                self.assertEqual(self._task_records(), [])

    def test_task_analysis_domain_api_is_retired(self) -> None:
        task_sys = _task_sys()

        self.assertFalse(hasattr(task_sys, "record_task_analysis_update"))
        self.assertFalse(hasattr(task_sys, "TASK_RELATION_KINDS"))

    def test_parent_runtime_instruction_shapes_are_task_traceable(self) -> None:
        task_sys = _task_sys()
        actor_target = self._envelope()["actor_target"]
        frame = {
            "kind": "task_sys.parent_frame",
            "task_id": "task-controlled-inbound-123456abcdef",
            "context": {"text": "Draft brief"},
        }

        submit = task_sys.runtime_instruction(
            "submit_parent",
            task_id="task-controlled-inbound-123456abcdef",
            actor_target=actor_target,
            frame=frame,
        )
        interrupt = task_sys.runtime_instruction(
            "interrupt_submit_parent",
            task_id="task-controlled-inbound-123456abcdef",
            actor_target=actor_target,
            frame=frame,
        )

        self.assertEqual(submit["type"], "submit_parent")
        self.assertEqual(interrupt["type"], "interrupt_submit_parent")
        for instruction in (submit, interrupt):
            with self.subTest(instruction=instruction["type"]):
                self.assertEqual(instruction["task_id"], "task-controlled-inbound-123456abcdef")
                self.assertEqual(instruction["actor_target"], actor_target)
                self.assertEqual(instruction["frame"], frame)

        with self.assertRaisesRegex(ValueError, "runtime instruction"):
            task_sys.runtime_instruction(
                "side_interrupt",
                task_id="task-controlled-inbound-123456abcdef",
                actor_target=actor_target,
                frame=frame,
            )

    def test_parent_instruction_from_need_parent_task_stays_parent_ready_until_runtime_start(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        task_sys.record_side_need_parent(
            task_id,
            {
                "params": {
                    "parent_frame_context": {"next": "Draft the brief in parent."},
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
        self.assertEqual(
            frame["source"],
            {"type": "test.inbound.created", "ref": {"id": "event-1", "channel": "fixture"}},
        )
        self.assertEqual(frame["inbound_context"], self._envelope()["context"])
        self.assertNotIn("task_desc", frame)
        self.assertNotIn("task_relation", frame)
        self.assertEqual(
            frame["execution_handoff"],
            {
                "parent_frame_context": {"next": "Draft the brief in parent."},
                "interrupt": True,
                "ordering": {"priority": "normal"},
                "side_thread_id": None,
                "cleanup": {},
            },
        )
        persisted = json.loads(self._task_record_path(task_id).read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], "in_progress.awaiting_parent")
        self.assertEqual(persisted["execution"]["processor"], None)
        self.assertEqual(persisted["execution"]["handoff"], frame["execution_handoff"])
        self.assertIsNone(persisted["execution"]["result"])
        self._assert_no_legacy_execution_fields(persisted)

    def test_record_parent_handoff_started_marks_parent_processing(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        self._move_to_needs_parent(task_id)

        result = task_sys.record_parent_handoff_started(task_id)

        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(result["task_id"], task_id)
        persisted = json.loads(self._task_record_path(task_id).read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], "in_progress.parent_processing")
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
        self.assertEqual(record["status"], "in_progress.awaiting_parent")
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
                "side_parent_requested",
                "parent_handoff_started",
                "closed",
            ],
        )

    def test_record_task_close_rejects_needs_parent_task(self) -> None:
        task_sys = _task_sys()
        task_id = task_sys.ingest(self._envelope())["task_id"]
        self._move_to_needs_parent(task_id)

        with self.assertRaisesRegex(ValueError, "awaiting_parent.*close"):
            task_sys.record_task_close(task_id, {"summary": "Skipped parent."})

        record = self._task_record(task_id)
        self.assertEqual(record["status"], "in_progress.awaiting_parent")
        self.assertEqual(record["execution"]["processor"], None)
        self.assertIsInstance(record["execution"]["handoff"], dict)
        self.assertIsNone(record["execution"]["result"])
        self._assert_no_legacy_execution_fields(record)

    def test_task_statuses_are_lifecycle_only(self) -> None:
        task_sys = _task_sys()

        self.assertEqual(
            task_sys.TASK_STATUSES,
            (
                "in_progress.side_processing",
                "in_progress.awaiting_parent",
                "in_progress.parent_processing",
                "completed",
                "canceled",
            ),
        )
        self.assertEqual(
            task_sys.ACTIVE_TASK_STATUSES,
            (
                "in_progress.side_processing",
                "in_progress.awaiting_parent",
                "in_progress.parent_processing",
            ),
        )
        self.assertEqual(task_sys.RECOVERABLE_TASK_REASONS, ("runtime_failed", "side_no_result", "side_timed_out"))
        self.assertNotIn("checkpoint", task_sys.TASK_STATUSES)
        self.assertNotIn("in_progress", task_sys.TASK_STATUSES)
        self.assertNotIn("no_actor_action", task_sys.RUNTIME_INSTRUCTION_TYPES)

    def test_side_runtime_failure_stays_side_processing_and_is_recoverable(self) -> None:
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
        self.assertEqual(record["status"], "in_progress.side_processing")
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
        self.assertEqual([row["id"] for row in projection["active_tasks"]], [task_id])
        self.assertEqual([row["id"] for row in projection["recoverable_tasks"]], [task_id])

    def test_actor_close_uses_side_processing_status_after_runtime_failure(self) -> None:
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

        result = task_sys.record_task_close(task_id, {"summary": "Recovered and completed."})

        record = self._task_record(task_id)
        self.assertTrue(result["ok"], msg=result)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["execution"]["processor"], None)
        self.assertEqual(record["execution"]["result"]["type"], "completion")
        self.assertEqual(record["execution"]["result"]["processor"], "side")
        self._assert_no_legacy_execution_fields(record)

    def test_record_task_cancel_moves_each_active_status_to_canceled(self) -> None:
        task_sys = _task_sys()

        for index, start_status in enumerate(task_sys.ACTIVE_TASK_STATUSES):
            with self.subTest(start_status=start_status):
                task_id = task_sys.ingest(
                    self._envelope(source_id=f"cancel-status-{index}")
                )["task_id"]
                if start_status in {task_sys.AWAITING_PARENT, task_sys.PARENT_PROCESSING}:
                    self._move_to_needs_parent(task_id)
                if start_status == task_sys.PARENT_PROCESSING:
                    task_sys.record_parent_handoff_started(task_id)

                result = task_sys.record_task_cancel(task_id, {"reason": "No longer required."})

                self.assertTrue(result["ok"], msg=result)
                self.assertEqual(result["outcome"], "cancel")
                self.assertEqual(result["task"]["status"], "canceled")
                self.assertEqual(self._task_record(task_id)["execution"]["result"]["type"], "cancellation")
                self.assertIn("canceled", self._event_types(task_id))

    def test_record_task_cancel_is_retry_safe_but_rejects_completed(self) -> None:
        task_sys = _task_sys()
        canceled_id = task_sys.ingest(
            self._envelope(source_id="cancel-retry")
        )["task_id"]

        first = task_sys.record_task_cancel(canceled_id, {"reason": "Superseded."})
        retry = task_sys.record_task_cancel(canceled_id, {"reason": "Retry."})
        completed_id = task_sys.ingest(
            self._envelope(source_id="completed-before-cancel")
        )["task_id"]
        task_sys.record_task_close(completed_id, {"summary": "Completed."})

        self.assertTrue(first["state_changed"])
        self.assertFalse(retry["state_changed"])
        self.assertEqual(retry["task"]["execution"]["result"], first["task"]["execution"]["result"])
        with self.assertRaisesRegex(ValueError, "completed.*cancel"):
            task_sys.record_task_cancel(completed_id, {"reason": "Too late."})
        self.assertEqual(self._task_record(completed_id)["status"], "completed")

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
            ({**valid, "source": "test.inbound.created"}, "source"),
            ({**valid, "source": {"ref": {"id": "event-1"}}}, "source.type"),
            ({**valid, "source": {"type": "test.inbound.created"}}, "source.ref"),
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
