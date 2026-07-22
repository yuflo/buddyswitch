"""Integration proof for the existing-Task processor Progress Check loop."""

from __future__ import annotations

import importlib
import json
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
        self.instance_json = self._instance_root(self.actor_id) / "instance.json"
        self.instance_json.parent.mkdir(parents=True, exist_ok=True)
        self.instance_json.write_text(
            json.dumps(
                {
                    "actor_id": self.actor_id,
                    "role": "dev",
                    "thread_id": "thr-main-progress-check",
                    "side_threads": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.context = SimpleNamespace(
            actor_id=self.actor_id,
            role="dev",
            main_thread_id="thr-main-progress-check",
            instance_json=self.instance_json,
        )

    def _create_task(self, *, parent_processing: bool = True, actor_id: str | None = None) -> str:
        target_actor_id = actor_id or self.actor_id
        result = task_sys.create(
            actor_target={"actor_id": target_actor_id, "role_id": "dev"},
            demand_ref={
                "demand_id": f"demand-progress-check-{target_actor_id}",
                "basis_revision": 1,
            },
            execution_brief={
                "description": "Continue the parent-owned Task.",
                "detail": "Continue the parent-owned Task after its completed turn.",
            },
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

    def _side_status_trigger(
        self,
        *,
        thread_id: str = "thr-side-progress-check",
        status: str = "idle",
    ) -> SimpleNamespace:
        return SimpleNamespace(
            type="app_server.thread_status_changed",
            source_context={
                "thread_id": thread_id,
                "thread_status": status,
            },
        )

    def _task_ids(self) -> set[str]:
        return {str(row["id"]) for row in task_sys.list_tasks()}

    def _register_side(self, task_id: str, *, purpose: str = "task_sys.side_frame") -> None:
        _adapter()
        side_thread_registry = importlib.import_module("side_thread_registry")
        side_thread_registry.register_side_thread(
            self.instance_json,
            actor_id=self.actor_id,
            parent_thread_id=self.context.main_thread_id,
            side_thread_id="thr-side-progress-check",
            task_id=task_id,
            purpose=purpose,
            turn_id="turn-side-work-1",
            turn_kind="work",
        )

    def _update_side_turn(self, turn_id: str, *, turn_kind: str | None = None) -> None:
        side_thread_registry = importlib.import_module("side_thread_registry")
        side_thread_registry.update_side_thread(
            self.instance_json,
            actor_id=self.actor_id,
            parent_thread_id=self.context.main_thread_id,
            side_thread_id="thr-side-progress-check",
            turn_id=turn_id,
            turn_kind=turn_kind,
        )

    def _daemon_state(self) -> Any:
        state_module = importlib.import_module("daemon_state")
        return state_module.DaemonState.load(
            instance_root=self.instance_json.parent,
            actor_id=self.actor_id,
            main_thread_id=self.context.main_thread_id,
        )

    def _run_with_submit(
        self,
        submit: Callable[..., dict[str, Any]],
        *,
        trigger: SimpleNamespace | None = None,
    ) -> tuple[Any, Any]:
        adapter = _adapter()
        original = adapter.task_sys_runtime.submit_task_progress_check
        self.addCleanup(setattr, adapter.task_sys_runtime, "submit_task_progress_check", original)
        adapter.task_sys_runtime.submit_task_progress_check = submit
        handler = adapter.TaskSysProgressCheckHandler()
        result = handler.handle(self.context, self._daemon_state(), object(), trigger or self._trigger())
        return handler, result

    def test_completed_main_turn_can_close_existing_parent_task_without_new_task(self) -> None:
        task_id = self._create_task()
        before = self._task_ids()

        def submit(
            _context: Any,
            task: dict[str, Any],
            previous_turn: dict[str, str],
            *,
            processor: str,
            side_thread_id: str | None = None,
        ) -> dict[str, Any]:
            self.assertEqual(task["id"], task_id)
            self.assertEqual(previous_turn["turn_id"], "turn-parent-work-1")
            self.assertEqual(processor, "parent")
            self.assertIsNone(side_thread_id)
            task_sys.record_task_close(task_id, {"summary": "Progress Check confirmed completion."})
            return {"action": "progress_check", "task_id": task_id, "turn_id": "turn-progress-check-close"}

        _handler, result = self._run_with_submit(submit)

        self.assertEqual(result.status, "handled")
        self.assertEqual(task_sys.get_task(task_id)["status"], task_sys.COMPLETED)
        self.assertEqual(self._task_ids(), before)

    def test_completed_main_turn_can_cancel_existing_parent_task_without_new_task(self) -> None:
        task_id = self._create_task()
        before = self._task_ids()

        def submit(_context: Any, task: dict[str, Any], _previous_turn: dict[str, str], **kwargs: Any) -> dict[str, Any]:
            self.assertEqual(task["id"], task_id)
            self.assertEqual(kwargs["processor"], "parent")
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

        def submit(_context: Any, task: dict[str, Any], _previous_turn: dict[str, str], **kwargs: Any) -> dict[str, Any]:
            calls.append(str(task["id"]))
            self.assertEqual(kwargs["processor"], "parent")
            return {"action": "progress_check", "task_id": task_id, "turn_id": "turn-progress-check-continue"}

        handler, result = self._run_with_submit(submit)
        recursive = handler.handle(
            self.context,
            self._daemon_state(),
            object(),
            self._trigger(turn_id="turn-progress-check-continue"),
        )

        self.assertEqual(result.status, "handled")
        self.assertEqual(recursive.status, "ignored")
        self.assertEqual(calls, [task_id])
        self.assertEqual(task_sys.get_task(task_id)["status"], task_sys.PARENT_PROCESSING)
        self.assertEqual(self._task_ids(), before)

    def test_new_handler_after_restart_ignores_persisted_parent_progress_check_turn(self) -> None:
        task_id = self._create_task()
        adapter = _adapter()
        calls: list[str] = []
        original = adapter.task_sys_runtime.submit_task_progress_check
        self.addCleanup(setattr, adapter.task_sys_runtime, "submit_task_progress_check", original)

        def submit(_context: Any, task: dict[str, Any], _previous_turn: dict[str, str], **_kwargs: Any) -> dict[str, Any]:
            calls.append(str(task["id"]))
            return {"action": "progress_check", "task_id": task_id, "turn_id": "turn-parent-check-persisted"}

        adapter.task_sys_runtime.submit_task_progress_check = submit
        first = adapter.TaskSysProgressCheckHandler().handle(
            self.context,
            self._daemon_state(),
            object(),
            self._trigger(turn_id="turn-parent-work-persisted"),
        )
        restarted = adapter.TaskSysProgressCheckHandler().handle(
            self.context,
            self._daemon_state(),
            object(),
            self._trigger(turn_id="turn-parent-check-persisted"),
        )

        self.assertEqual(first.status, "handled")
        self.assertEqual(restarted.status, "ignored")
        self.assertEqual(calls, [task_id])

    def test_parent_progress_check_persists_pending_before_external_submit(self) -> None:
        task_id = self._create_task()
        adapter = _adapter()
        state = self._daemon_state()
        calls: list[str] = []
        original = adapter.task_sys_runtime.submit_task_progress_check
        original_update = state.update_handler_state

        def fail_first_checkpoint(_handler_name: str, _values: dict[str, Any]) -> None:
            raise RuntimeError("checkpoint persistence unavailable")

        def submit(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            calls.append(task_id)
            return {"action": "progress_check", "task_id": task_id, "turn_id": "turn-must-not-submit"}

        self.addCleanup(setattr, adapter.task_sys_runtime, "submit_task_progress_check", original)
        self.addCleanup(setattr, state, "update_handler_state", original_update)
        adapter.task_sys_runtime.submit_task_progress_check = submit
        state.update_handler_state = fail_first_checkpoint

        result = adapter.TaskSysProgressCheckHandler().handle(
            self.context,
            state,
            object(),
            self._trigger(turn_id="turn-parent-before-submit"),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("checkpoint persistence unavailable", str(result.message))
        self.assertEqual(calls, [])

    def test_parent_progress_check_receipt_failure_keeps_durable_pending_and_blocks_resubmit(self) -> None:
        task_id = self._create_task()
        adapter = _adapter()
        state = self._daemon_state()
        calls: list[str] = []
        update_calls = 0
        original = adapter.task_sys_runtime.submit_task_progress_check
        original_update = state.update_handler_state

        def fail_receipt_checkpoint(handler_name: str, values: dict[str, Any]) -> None:
            nonlocal update_calls
            update_calls += 1
            if update_calls == 2:
                raise RuntimeError("receipt checkpoint persistence failed")
            original_update(handler_name, values)

        def submit(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            calls.append(task_id)
            return {"action": "progress_check", "task_id": task_id, "turn_id": "turn-parent-check-uncertain"}

        self.addCleanup(setattr, adapter.task_sys_runtime, "submit_task_progress_check", original)
        self.addCleanup(setattr, state, "update_handler_state", original_update)
        adapter.task_sys_runtime.submit_task_progress_check = submit
        state.update_handler_state = fail_receipt_checkpoint

        first = adapter.TaskSysProgressCheckHandler().handle(
            self.context,
            state,
            object(),
            self._trigger(turn_id="turn-parent-work-uncertain"),
        )
        restarted = adapter.TaskSysProgressCheckHandler().handle(
            self.context,
            self._daemon_state(),
            object(),
            self._trigger(turn_id="turn-parent-check-uncertain"),
        )

        checkpoint = self._daemon_state().handler_state("task_sys_progress_check")["checkpoint"]
        self.assertEqual(first.status, "failed")
        self.assertIn("receipt checkpoint persistence failed", str(first.message))
        self.assertEqual(restarted.status, "ignored")
        self.assertEqual(calls, [task_id])
        self.assertEqual(
            checkpoint,
            {
                "processor": "parent",
                "task_id": task_id,
                "thread_id": self.context.main_thread_id,
                "source_turn_id": "turn-parent-work-uncertain",
                "status": "submitting",
            },
        )

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

    def test_registered_side_idle_checks_existing_side_task_and_ignores_its_own_idle(self) -> None:
        task_id = self._create_task(parent_processing=False)
        self._register_side(task_id)
        before = self._task_ids()
        calls: list[str] = []

        def submit(
            _context: Any,
            task: dict[str, Any],
            previous_turn: dict[str, str],
            *,
            processor: str,
            side_thread_id: str | None = None,
        ) -> dict[str, Any]:
            calls.append(str(task["id"]))
            self.assertEqual(processor, "side")
            self.assertEqual(side_thread_id, "thr-side-progress-check")
            self.assertEqual(previous_turn["turn_id"], "turn-side-work-1")
            self.assertEqual(previous_turn["status"], "idle")
            self._update_side_turn("turn-side-progress-check", turn_kind="progress_check")
            return {"action": "progress_check", "task_id": task_id, "turn_id": "turn-side-progress-check"}

        handler, result = self._run_with_submit(
            submit,
            trigger=self._side_status_trigger(),
        )
        recursive = _adapter().TaskSysProgressCheckHandler().handle(
            self.context,
            self._daemon_state(),
            object(),
            self._side_status_trigger(),
        )

        self.assertEqual(result.status, "handled")
        self.assertEqual(recursive.status, "ignored")
        self.assertEqual(calls, [task_id])
        self.assertEqual(task_sys.get_task(task_id)["status"], task_sys.SIDE_PROCESSING)
        self.assertEqual(self._task_ids(), before)

    def test_unregistered_non_task_or_non_idle_side_and_non_completed_parent_are_ignored(self) -> None:
        task_id = self._create_task()
        before = self._task_ids()

        for trigger in (
            self._side_status_trigger(thread_id="thr-other"),
            self._side_status_trigger(status="active"),
            self._side_status_trigger(thread_id=self.context.main_thread_id),
            self._trigger(turn_id="turn-running", status="inProgress"),
        ):
            with self.subTest(source_context=trigger.source_context):
                def submit(*_args: Any) -> dict[str, Any]:
                    raise AssertionError("Progress Check must not submit for this notification")

                _handler, result = self._run_with_submit(submit, trigger=trigger)
                self.assertEqual(result.status, "ignored")
                self.assertEqual(task_sys.get_task(task_id)["status"], task_sys.PARENT_PROCESSING)
                self.assertEqual(self._task_ids(), before)

        side_task_id = task_sys.get_task(task_id)["id"]
        self._register_side(side_task_id, purpose="host_control.side")
        _handler, result = self._run_with_submit(
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("Progress Check must not submit for a non-Task side thread")
            ),
            trigger=self._side_status_trigger(),
        )
        self.assertEqual(result.status, "ignored")

    def test_terminal_or_wrong_owner_task_side_lease_is_ignored(self) -> None:
        terminal_task_id = self._create_task(parent_processing=False)
        task_sys.record_task_cancel(terminal_task_id, {"reason": "Terminal before notification."})
        self._register_side(terminal_task_id)

        def submit(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("Progress Check must not submit for an invalid Task side lease")

        _handler, terminal_result = self._run_with_submit(
            submit,
            trigger=self._side_status_trigger(),
        )
        self.assertEqual(terminal_result.status, "ignored")

        other_actor_id = self._runtime_actor_id(role="dev", label="act-dev-other-side-owner")
        other_task_id = self._create_task(parent_processing=False, actor_id=other_actor_id)
        self._register_side(other_task_id)
        _handler, wrong_owner_result = self._run_with_submit(
            submit,
            trigger=self._side_status_trigger(),
        )
        self.assertEqual(wrong_owner_result.status, "ignored")

    def test_submit_failure_leaves_same_parent_task_unchanged(self) -> None:
        task_id = self._create_task()
        before = self._task_ids()

        def submit(_context: Any, task: dict[str, Any], _previous_turn: dict[str, str], **_kwargs: Any) -> dict[str, Any]:
            self.assertEqual(task["id"], task_id)
            raise RuntimeError("progress check submit failed")

        _handler, result = self._run_with_submit(submit)

        self.assertEqual(result.status, "failed")
        self.assertIn("progress check submit failed", str(result.message))
        self.assertEqual(task_sys.get_task(task_id)["status"], task_sys.PARENT_PROCESSING)
        self.assertEqual(self._task_ids(), before)
