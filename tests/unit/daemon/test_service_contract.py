"""Tests for the daemon service handler contract and runtime."""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any


from tests.support.paths import REPO_ROOT
from buddyswitch.application.daemon_host import AppActorDaemonHost

ROOT = REPO_ROOT
LAUNCHER = ROOT / "src" / "buddyswitch" / "launcher"

from buddyswitch.foundation.daemon import contracts  # noqa: E402
from buddyswitch.foundation.daemon import runtime  # noqa: E402
from buddyswitch.foundation.daemon import state as daemon_state  # noqa: E402

DAEMON_CORE_PATH = ROOT / "src" / "buddyswitch" / "foundation" / "daemon" / "instance.py"
MODULE_COUNTER = count()


def load_daemon_core() -> Any:
    return importlib.reload(importlib.import_module("buddyswitch.foundation.daemon.instance"))


class FakeRuntimeClient:
    def __init__(self, *, result: dict[str, object] | None = None, error: BaseException | None = None) -> None:
        self.result = result or {"turn": {"id": "turn-daemon-1"}}
        self.error = error
        self.requests: list[dict[str, object]] = []

    def request(self, method: str, params: dict[str, object] | None) -> dict[str, object]:
        self.requests.append({"method": method, "params": params or {}})
        if self.error is not None:
            raise self.error
        return self.result


class DaemonServiceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.core = load_daemon_core()

    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "act-dev-daed00000001"
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload: dict[str, Any] = {
            "actor_id": "act-dev-daed00000001",
            "role": "dev",
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(workspace_dir),
            "thread_id": "thr-main",
            "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
        }
        instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        return {
            "instance_root": instance_root,
            "instance_json": instance_json,
            "payload": payload,
        }

    def _state(self, instance_root: Path) -> Any:
        return daemon_state.DaemonState.load(
            instance_root=instance_root,
            actor_id="act-dev-daed00000001",
            main_thread_id="thr-main",
        )

    def _saved_state(self, instance_root: Path) -> dict[str, Any]:
        return json.loads(daemon_state.daemon_state_file(instance_root).read_text(encoding="utf-8"))

    def _json_log_events(self, path: Path) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if not path.exists():
            return events
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and isinstance(payload.get("event"), str):
                events.append(payload)
        return events

    def _completed(self, *, turn_id: str = "turn-user-1") -> dict[str, object]:
        return {
            "method": "turn/completed",
            "params": {
                "threadId": "thr-main",
                "turn": {
                    "id": turn_id,
                    "status": "completed",
                },
            },
        }

    def test_handler_result_has_explicit_statuses(self) -> None:
        ignored = contracts.HandlerResult.ignored()
        handled = contracts.HandlerResult.handled()
        failed = contracts.HandlerResult.failed("boom")

        self.assertEqual(ignored.status, "ignored")
        self.assertIsNone(ignored.message)
        self.assertEqual(handled.status, "handled")
        self.assertIsNone(handled.message)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.message, "boom")

    def test_daemon_status_reports_schedule_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self._state(instance["instance_root"])
            pending = state.create_schedule(
                delay_seconds=600,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-pending"},
                now="2026-06-24T00:00:00Z",
            )
            delivered = state.create_schedule(
                delay_seconds=0,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-delivered"},
                now="2026-06-24T00:00:00Z",
            )
            failed = state.create_schedule(
                delay_seconds=0,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-failed"},
                now="2026-06-24T00:00:00Z",
            )
            canceled = state.create_schedule(
                delay_seconds=0,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-canceled"},
                now="2026-06-24T00:00:00Z",
            )
            state.mark_schedule_delivered(delivered["schedule_id"], dispatch_result={"handling_status": "handled"}, now="2026-06-24T00:00:01Z")
            state.mark_schedule_failed(failed["schedule_id"], message="close failed", now="2026-06-24T00:00:02Z")
            state.cancel_schedule(canceled["schedule_id"], now="2026-06-24T00:00:03Z")

            status = self.core.daemon_status(instance["instance_json"], host=AppActorDaemonHost())

            self.assertEqual(status["schedules"]["ids"], ["schedule-1", "schedule-2", "schedule-3", "schedule-4"])
            self.assertEqual(
                status["schedules"]["counts"],
                {"pending": 1, "delivered": 1, "failed": 1, "canceled": 1},
            )
            self.assertEqual(status["schedules"]["items"][pending["schedule_id"]]["status"], "pending")
            self.assertEqual(status["schedules"]["items"][delivered["schedule_id"]]["status"], "delivered")
            self.assertEqual(status["schedules"]["items"][failed["schedule_id"]]["last_error"], "close failed")
            self.assertEqual(status["schedules"]["items"][canceled["schedule_id"]]["status"], "canceled")

    def test_cancel_pending_schedules_by_source_owner_cancels_only_matching_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self._state(instance["instance_root"])
            browser_pending = state.create_schedule(
                delay_seconds=600,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-pending"},
                source_context={"owner": "browser"},
                now="2026-07-04T00:00:00Z",
            )
            browser_release_pending = state.create_schedule(
                delay_seconds=600,
                trigger_type="browser.cockpit.release",
                payload={"reason": "idle_empty"},
                source_context={"owner": "browser"},
                now="2026-07-04T00:00:01Z",
            )
            task_pending = state.create_schedule(
                delay_seconds=600,
                trigger_type="task.example",
                payload={"task_id": "task-1"},
                source_context={"owner": "task"},
                now="2026-07-04T00:00:02Z",
            )
            browser_delivered = state.create_schedule(
                delay_seconds=0,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-delivered"},
                source_context={"owner": "browser"},
                now="2026-07-04T00:00:03Z",
            )
            browser_failed = state.create_schedule(
                delay_seconds=0,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-failed"},
                source_context={"owner": "browser"},
                now="2026-07-04T00:00:04Z",
            )
            browser_canceled = state.create_schedule(
                delay_seconds=0,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-canceled"},
                source_context={"owner": "browser"},
                now="2026-07-04T00:00:05Z",
            )
            state.mark_schedule_delivered(
                browser_delivered["schedule_id"],
                dispatch_result={"handling_status": "handled"},
                now="2026-07-04T00:00:06Z",
            )
            state.mark_schedule_failed(
                browser_failed["schedule_id"],
                message="close failed",
                now="2026-07-04T00:00:07Z",
            )
            state.cancel_schedule(browser_canceled["schedule_id"], now="2026-07-04T00:00:08Z")

            canceled = daemon_state.cancel_pending_schedules_by_source_owner(
                instance_root=instance["instance_root"],
                actor_id=instance["payload"]["actor_id"],
                main_thread_id=instance["payload"]["thread_id"],
                source_owner="browser",
                now="2026-07-04T00:00:10Z",
            )

            self.assertEqual(
                [row["schedule_id"] for row in canceled],
                [browser_pending["schedule_id"], browser_release_pending["schedule_id"]],
            )
            saved = self._saved_state(instance["instance_root"])
            self.assertEqual(saved["scheduled_triggers"][browser_pending["schedule_id"]]["status"], "canceled")
            self.assertEqual(saved["scheduled_triggers"][browser_pending["schedule_id"]]["updated_at"], "2026-07-04T00:00:10Z")
            self.assertEqual(saved["scheduled_triggers"][browser_pending["schedule_id"]]["canceled_at"], "2026-07-04T00:00:10Z")
            self.assertEqual(saved["scheduled_triggers"][browser_release_pending["schedule_id"]]["status"], "canceled")
            self.assertEqual(saved["scheduled_triggers"][task_pending["schedule_id"]]["status"], "pending")
            self.assertEqual(saved["scheduled_triggers"][browser_delivered["schedule_id"]]["status"], "delivered")
            self.assertEqual(saved["scheduled_triggers"][browser_failed["schedule_id"]]["status"], "failed")
            self.assertEqual(saved["scheduled_triggers"][browser_canceled["schedule_id"]]["status"], "canceled")

    def test_daemon_status_excludes_task_sys_product_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            status = self.core.daemon_status(instance["instance_json"], host=AppActorDaemonHost())

            self.assertNotIn("task_sys", status)

    def test_handler_status_result_scope_does_not_claim_external_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self._state(instance["instance_root"])

            class MessageHandler:
                name = "im_message_created"

            state.register_handlers(["im_message_created"])
            state.record_handler_result("im_message_created", contracts.HandlerResult.handled(), origin_turn_id="msg-1")

            status = self.core.daemon_status(instance["instance_json"], host=AppActorDaemonHost(), handlers=[MessageHandler()])

            item = status["handlers"]["items"]["im_message_created"]
            self.assertEqual(item["last_result"], "handled")
            self.assertEqual(item["result_scope"], "trigger_dispatch")
            self.assertNotIn("external_delivery", item)
            self.assertNotIn("phone_delivery", item)

    def test_daemon_runtime_replaces_action_gateway_without_alias(self) -> None:
        self.assertTrue(hasattr(runtime, "DaemonRuntime"))
        self.assertFalse(hasattr(self.core, "DaemonRuntime"))
        self.assertTrue(hasattr(contracts, "DaemonHandler"))
        self.assertFalse(hasattr(self.core, "DaemonHandler"))
        self.assertFalse(hasattr(self.core, "Action" + "Gateway"))

    def test_dispatch_passes_context_state_runtime_and_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"], host=AppActorDaemonHost())
            state = self._state(instance["instance_root"])
            client = FakeRuntimeClient()
            notification = self._completed()
            core = self.core

            class RecordingHandler:
                name = "recording"

                def __init__(self) -> None:
                    self.received: dict[str, object] = {}

                def handles(self, trigger: object) -> bool:
                    return getattr(trigger, "type", None) == "app_server.turn_completed"

                def handle(
                    self,
                    context_arg: object,
                    state_arg: object,
                    runtime_arg: object,
                    trigger_arg: object,
                ) -> object:
                    self.received = {
                        "context": context_arg,
                        "state": state_arg,
                        "runtime": runtime_arg,
                        "trigger": trigger_arg,
                    }
                    return contracts.HandlerResult.handled()

            handler = RecordingHandler()

            handled = self.core.dispatch_notification(context, state, client, notification, [handler], host=AppActorDaemonHost())

            self.assertTrue(handled)
            self.assertIs(handler.received["context"], context)
            self.assertIs(handler.received["state"], state)
            self.assertIsInstance(handler.received["runtime"], runtime.DaemonRuntime)
            trigger = handler.received["trigger"]
            self.assertEqual(getattr(trigger, "type"), "app_server.turn_completed")
            self.assertEqual(getattr(trigger, "origin_id"), "turn-user-1")

    def test_dispatch_records_declared_failure_under_handler_state_and_continues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"], host=AppActorDaemonHost())
            state = self._state(instance["instance_root"])
            client = FakeRuntimeClient()
            notification = self._completed()
            calls: list[str] = []
            core = self.core

            class FailingHandler:
                name = "first"

                def handles(self, trigger: object) -> bool:
                    return getattr(trigger, "type", None) == "app_server.turn_completed"

                def handle(self, *_args: object) -> object:
                    calls.append(self.name)
                    return contracts.HandlerResult.failed("declared failure")

            class LaterHandler:
                name = "second"

                def handles(self, trigger: object) -> bool:
                    return getattr(trigger, "type", None) == "app_server.turn_completed"

                def handle(self, *_args: object) -> object:
                    calls.append(self.name)
                    return contracts.HandlerResult.handled()

            handled = self.core.dispatch_notification(context, state, client, notification, [FailingHandler(), LaterHandler()], host=AppActorDaemonHost())

            self.assertTrue(handled)
            self.assertEqual(calls, ["first", "second"])
            saved = json.loads(daemon_state.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIsNone(saved["last_error"])
            self.assertEqual(saved["handlers"]["first"]["last_result"], "failed")
            self.assertEqual(saved["handlers"]["first"]["last_error"]["message"], "declared failure")
            self.assertEqual(saved["handlers"]["first"]["last_error"]["origin_turn_id"], "turn-user-1")
            self.assertEqual(saved["handlers"]["second"]["last_result"], "handled")
            self.assertIsNone(saved["handlers"]["second"]["last_error"])

    def test_dispatch_records_exception_under_handler_state_and_continues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"], host=AppActorDaemonHost())
            state = self._state(instance["instance_root"])
            client = FakeRuntimeClient()
            notification = self._completed()
            calls: list[str] = []
            core = self.core

            class ExplodingHandler:
                name = "exploder"

                def handles(self, trigger: object) -> bool:
                    return getattr(trigger, "type", None) == "app_server.turn_completed"

                def handle(self, *_args: object) -> object:
                    calls.append(self.name)
                    raise RuntimeError("handler exploded")

            class LaterHandler:
                name = "second"

                def handles(self, trigger: object) -> bool:
                    return getattr(trigger, "type", None) == "app_server.turn_completed"

                def handle(self, *_args: object) -> object:
                    calls.append(self.name)
                    return contracts.HandlerResult.handled()

            handled = self.core.dispatch_notification(context, state, client, notification, [ExplodingHandler(), LaterHandler()], host=AppActorDaemonHost())

            self.assertTrue(handled)
            self.assertEqual(calls, ["exploder", "second"])
            saved = json.loads(daemon_state.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIsNone(saved["last_error"])
            self.assertEqual(saved["handlers"]["exploder"]["last_result"], "failed")
            self.assertEqual(saved["handlers"]["exploder"]["last_error"]["message"], "handler exploded")
            self.assertEqual(saved["handlers"]["exploder"]["last_error"]["origin_turn_id"], "turn-user-1")

    def test_dispatch_writes_handler_result_breadcrumb_without_message_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"], host=AppActorDaemonHost())
            state = self._state(instance["instance_root"])
            client = FakeRuntimeClient()
            notification = self._completed()
            assert isinstance(notification["params"], dict)
            notification["params"]["raw_message"] = "secret message body"

            class RecordingHandler:
                name = "im_message_created"

                def handles(self, trigger: object) -> bool:
                    return getattr(trigger, "type", None) == "app_server.turn_completed"

                def handle(self, *_args: object) -> object:
                    return contracts.HandlerResult.handled()

            self_core = self.core

            handled = self.core.dispatch_notification(context, state, client, notification, [RecordingHandler()], host=AppActorDaemonHost())

            self.assertTrue(handled)
            log_path = self.core.daemon_log_file(instance["instance_root"])
            log_text = log_path.read_text(encoding="utf-8")
            self.assertNotIn("secret message body", log_text)
            events = self._json_log_events(log_path)
            self.assertIn("notification_received", [event["event"] for event in events])
            handler_events = [event for event in events if event["event"] == "handler_result"]
            self.assertEqual(len(handler_events), 1)
            self.assertEqual(handler_events[0]["service"], "daemon")
            self.assertEqual(handler_events[0]["actor_id"], "act-dev-daed00000001")
            self.assertEqual(handler_events[0]["handler"], "im_message_created")
            self.assertEqual(handler_events[0]["trigger_type"], "app_server.turn_completed")
            self.assertEqual(handler_events[0]["origin_id"], "turn-user-1")
            self.assertEqual(handler_events[0]["result"], "handled")

    def test_daemon_runtime_input_actor_delegates_exact_context_to_actor_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"], host=AppActorDaemonHost())
            calls: list[dict[str, Any]] = []
            host = AppActorDaemonHost()
            host.input_actor = lambda daemon_context, text: (
                calls.append({"context": daemon_context, "text": text})
                or {"action": "steer", "turn_id": "turn-demand-check"}
            )

            result = runtime.DaemonRuntime(context=context, host=host).input_actor(
                "Demand check"
            )

            self.assertEqual(
                result,
                {"action": "steer", "turn_id": "turn-demand-check"},
            )
            self.assertEqual(
                calls,
                [{"context": context, "text": "Demand check"}],
            )

    def test_daemon_runtime_handler_facing_surface_is_exactly_clean_runtime_methods(self) -> None:
        public_methods = {
            name
            for name, value in vars(runtime.DaemonRuntime).items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(
            public_methods,
            {"parent_activity", "input_actor"},
        )

    def test_daemon_runtime_handler_facing_surface_excludes_old_action_names(self) -> None:
        for old_name in (
            "submit_turn",
            "interrupt_parent",
            "start_" + "side_triage",
            "send_" + "side_triage",
            "start_" + "or_reuse_side_triage",
            "require_side_thread",
            "close_" + "side_triage",
            "submit_" + "side_triage_prompt",
        ):
            self.assertFalse(hasattr(runtime.DaemonRuntime, old_name), old_name)
