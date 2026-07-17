"""Integration proof for the existing-task parent Progress Check loop."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any, Callable

from env.domain import task_sys
from tests.support.runtime import RuntimeWorkspaceTestCase


def _adapter() -> Any:
    return importlib.import_module("task_sys_daemon_adapter")


class TaskSysProgressCheckTests(RuntimeWorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.actor_id = self._runtime_actor_id(role="dev", label="act-dev-progress-check")
        self.context = SimpleNamespace(
            actor_id=self.actor_id,
            role="dev",
            main_thread_id="thr-main-progress-check",
        )

    def _create_task(self, *, parent_processing: bool = True, actor_id: str | None = None) -> str:
        target_actor_id = actor_id or self.actor_id
        result = task_sys.ingest(
            {
                "source": {
                    "type": "test.inbound.created",
                    "ref": {"id": "event-progress-check", "channel": "fixture"},
                },
                "actor_target": {"actor_id": target_actor_id, "role_id": "dev"},
                "context": {"text": "Continue the parent-owned task."},
            }
        )
        task_id = str(result["task_id"])
        if parent_processing:
            task_sys.record_side_need_parent(
                task_id,
                {
                    "params": {
                        "parent_frame_context": {"next": "Continue in parent."},
                        "interrupt": False,
                    }
                },
            )
            task_sys.record_parent_handoff_started(task_id)
        return task_id

    def _trigger(
        self,
        *,
        thread_id: str | None = None,
        turn_id: str = "turn-parent-work-1",
        status: str = "completed",
    ) -> SimpleNamespace:
        return SimpleNamespace(
            type="app_server.turn_completed",
            source_context={
                "thread_id": thread_id or self.context.main_thread_id,
                "turn_id": turn_id,
                "turn_status": status,
            },
        )

    def _task_ids(self) -> set[str]:
        return {str(row["id"]) for row in task_sys.list_tasks()}

    def _run_with_submit(
        self,
        submit: Callable[[Any, dict[str, Any], dict[str, str]], dict[str, Any]],
        *,
        trigger: SimpleNamespace | None = None,
    ) -> tuple[Any, Any]:
        adapter = _adapter()
        original = adapter.task_sys_runtime.submit_parent_progress_check
        self.addCleanup(setattr, adapter.task_sys_runtime, "submit_parent_progress_check", original)
        adapter.task_sys_runtime.submit_parent_progress_check = submit
        handler = adapter.TaskSysProgressCheckHandler()
        result = handler.handle(self.context, object(), object(), trigger or self._trigger())
        return handler, result

    def test_completed_main_turn_can_close_existing_parent_task_without_new_task(self) -> None:
        task_id = self._create_task()
        before = self._task_ids()

        def submit(_context: Any, task: dict[str, Any], previous_turn: dict[str, str]) -> dict[str, Any]:
            self.assertEqual(task["id"], task_id)
            self.assertEqual(previous_turn["turn_id"], "turn-parent-work-1")
            task_sys.record_task_close(task_id, {"summary": "Progress Check confirmed completion."})
            return {"action": "progress_check", "task_id": task_id, "turn_id": "turn-progress-check-close"}

        _handler, result = self._run_with_submit(submit)

        self.assertEqual(result.status, "handled")
        self.assertEqual(task_sys.get_task(task_id)["status"], task_sys.COMPLETED)
        self.assertEqual(self._task_ids(), before)

    def test_completed_main_turn_can_cancel_existing_parent_task_without_new_task(self) -> None:
        task_id = self._create_task()
        before = self._task_ids()

        def submit(_context: Any, task: dict[str, Any], _previous_turn: dict[str, str]) -> dict[str, Any]:
            self.assertEqual(task["id"], task_id)
            task_sys.record_task_cancel(task_id, {"reason": "Actor stopped the parent task."})
            return {"action": "progress_check", "task_id": task_id, "turn_id": "turn-progress-check-cancel"}

        _handler, result = self._run_with_submit(submit)

        self.assertEqual(result.status, "handled")
        self.assertEqual(task_sys.get_task(task_id)["status"], task_sys.CANCELED)
        self.assertEqual(self._task_ids(), before)

    def test_continue_keeps_parent_status_and_ignores_its_own_completed_turn(self) -> None:
        task_id = self._create_task()
        before = self._task_ids()
        calls: list[str] = []

        def submit(_context: Any, task: dict[str, Any], _previous_turn: dict[str, str]) -> dict[str, Any]:
            calls.append(str(task["id"]))
            return {"action": "progress_check", "task_id": task_id, "turn_id": "turn-progress-check-continue"}

        handler, result = self._run_with_submit(submit)
        recursive = handler.handle(
            self.context,
            object(),
            object(),
            self._trigger(turn_id="turn-progress-check-continue"),
        )

        self.assertEqual(result.status, "handled")
        self.assertEqual(recursive.status, "ignored")
        self.assertEqual(calls, [task_id])
        self.assertEqual(task_sys.get_task(task_id)["status"], task_sys.PARENT_PROCESSING)
        self.assertEqual(self._task_ids(), before)

    def test_no_actor_owned_parent_processing_task_is_ignored_without_new_task(self) -> None:
        task_id = self._create_task(parent_processing=False)
        other_task_id = self._create_task(
            actor_id=self._runtime_actor_id(role="dev", label="act-dev-other-progress-check")
        )
        before = self._task_ids()

        def submit(*_args: Any) -> dict[str, Any]:
            raise AssertionError("Progress Check must not submit without a parent-processing task")

        _handler, result = self._run_with_submit(submit)

        self.assertEqual(result.status, "ignored")
        self.assertEqual(task_sys.get_task(task_id)["status"], task_sys.SIDE_PROCESSING)
        self.assertEqual(task_sys.get_task(other_task_id)["status"], task_sys.PARENT_PROCESSING)
        self.assertEqual(self._task_ids(), before)

    def test_non_main_or_non_completed_notification_is_ignored_without_new_task(self) -> None:
        task_id = self._create_task()
        before = self._task_ids()

        for trigger in (
            self._trigger(thread_id="thr-other"),
            self._trigger(turn_id="turn-running", status="inProgress"),
        ):
            with self.subTest(source_context=trigger.source_context):
                def submit(*_args: Any) -> dict[str, Any]:
                    raise AssertionError("Progress Check must not submit for this notification")

                _handler, result = self._run_with_submit(submit, trigger=trigger)
                self.assertEqual(result.status, "ignored")
                self.assertEqual(task_sys.get_task(task_id)["status"], task_sys.PARENT_PROCESSING)
                self.assertEqual(self._task_ids(), before)

    def test_submit_failure_leaves_same_parent_task_unchanged(self) -> None:
        task_id = self._create_task()
        before = self._task_ids()

        def submit(_context: Any, task: dict[str, Any], _previous_turn: dict[str, str]) -> dict[str, Any]:
            self.assertEqual(task["id"], task_id)
            raise RuntimeError("progress check submit failed")

        _handler, result = self._run_with_submit(submit)

        self.assertEqual(result.status, "failed")
        self.assertIn("progress check submit failed", str(result.message))
        self.assertEqual(task_sys.get_task(task_id)["status"], task_sys.PARENT_PROCESSING)
        self.assertEqual(self._task_ids(), before)
