"""Tests for unified daemon trigger normalization and routing."""

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

ROOT = REPO_ROOT
LAUNCHER = ROOT / "tools" / "launcher"

import daemon_contracts  # noqa: E402
import daemon_state  # noqa: E402

DAEMON_CORE_PATH = ROOT / "tools" / "launcher" / "daemon_core.py"
TRIGGERS_PATH = ROOT / "tools" / "launcher" / "daemon_triggers.py"
MODULE_COUNTER = count()


def load_module(path: Path) -> Any:
    if not path.exists():
        raise AssertionError(f"expected module to exist: {path}")
    return importlib.reload(importlib.import_module(path.stem))


class RecordingHandler:
    name = "recording"

    def __init__(self) -> None:
        self.handled: list[Any] = []

    def handles(self, trigger: Any) -> bool:
        return trigger.type == "example.ready"

    def handle(self, _context: object, _state: object, _runtime: object, trigger: Any) -> object:
        self.handled.append(trigger)
        return daemon_contracts.HandlerResult.handled()


class FailingHandler:
    name = "failing"

    def handles(self, trigger: Any) -> bool:
        return trigger.type == "example.ready"

    def handle(self, _context: object, _state: object, _runtime: object, _trigger: Any) -> object:
        return daemon_contracts.HandlerResult.failed("handler failed intentionally")


class InvalidReturnHandler:
    name = "invalid_return"

    def handles(self, trigger: Any) -> bool:
        return trigger.type == "example.ready"

    def handle(self, _context: object, _state: object, _runtime: object, _trigger: Any) -> object:
        return object()


class IgnoringHandler:
    name = "ignoring"

    def handles(self, trigger: Any) -> bool:
        return trigger.type == "task.updated"

    def handle(self, *_args: object) -> object:
        raise AssertionError("ignored handler must not be called")


class DaemonTriggerRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.triggers = load_module(TRIGGERS_PATH)
        self.daemon_core = load_module(DAEMON_CORE_PATH)

    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "act-dev-daemon"
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload = {
            "actor_id": "act-dev-daemon",
            "role": "dev",
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(workspace_dir),
            "thread_id": "thr-main",
            "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
        }
        instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        context = self.daemon_core.load_daemon_context(instance_json)
        state = daemon_state.DaemonState.load(
            instance_root=instance_root,
            actor_id="act-dev-daemon",
            main_thread_id="thr-main",
        )
        return {"context": context, "state": state}

    def _identity_route(self) -> dict[str, str]:
        return {"identity_id": "act-dev-daemon", "role_id": "dev"}

    def _trigger(self, *, trigger_type: str = "example.ready") -> Any:
        return self.triggers.DaemonTrigger(
            source="mailbox_cross_actor_signal",
            type=trigger_type,
            target_identity_id="act-dev-daemon",
            target_role_id="dev",
            origin_id="sig-readable",
            correlation_id="corr-readable",
            payload={"message_id": "msg-readable"},
            source_context={"signal_id": "sig-readable"},
        )

    def test_daemon_trigger_preserves_core_fields(self) -> None:
        trigger = self._trigger()

        self.assertEqual(trigger.source, "mailbox_cross_actor_signal")
        self.assertEqual(trigger.type, "example.ready")
        self.assertEqual(trigger.target_identity_id, "act-dev-daemon")
        self.assertEqual(trigger.target_role_id, "dev")
        self.assertEqual(trigger.origin_id, "sig-readable")
        self.assertEqual(trigger.correlation_id, "corr-readable")
        self.assertEqual(trigger.payload, {"message_id": "msg-readable"})
        self.assertEqual(trigger.source_context, {"signal_id": "sig-readable"})

    def test_app_server_turn_completed_notification_normalizes_to_daemon_trigger(self) -> None:
        notification = {
            "method": "turn/completed",
            "params": {
                "threadId": "thr-main",
                "turn": {"id": "turn-user-1", "status": "completed"},
            },
        }

        trigger = self.triggers.normalize_app_server_notification(
            notification,
            target_identity_id="act-dev-daemon",
            target_role_id="dev",
        )

        self.assertEqual(trigger.source, "app_server_notification")
        self.assertEqual(trigger.type, "app_server.turn_completed")
        self.assertEqual(trigger.target_identity_id, "act-dev-daemon")
        self.assertEqual(trigger.target_role_id, "dev")
        self.assertEqual(trigger.origin_id, "turn-user-1")
        self.assertEqual(trigger.payload, notification["params"])
        self.assertEqual(
            trigger.source_context,
            {
                "method": "turn/completed",
                "thread_id": "thr-main",
                "turn_id": "turn-user-1",
                "turn_status": "completed",
            },
        )

    def test_app_server_thread_idle_notification_normalizes_generic_thread_status(self) -> None:
        notification = {
            "method": "thread/status/changed",
            "params": {
                "threadId": "thr-side",
                "status": {"type": "idle"},
            },
        }

        trigger = self.triggers.normalize_app_server_notification(
            notification,
            target_identity_id="act-dev-daemon",
            target_role_id="dev",
        )

        self.assertEqual(trigger.type, "app_server.thread_status_changed")
        self.assertIsNone(trigger.origin_id)
        self.assertEqual(
            trigger.source_context,
            {
                "method": "thread/status/changed",
                "thread_id": "thr-side",
                "thread_status": "idle",
            },
        )

    def test_cross_actor_signal_normalizes_to_daemon_trigger(self) -> None:
        signal = {
            "signal_id": "sig-readable",
            "type": "example.ready",
            "source_identity_id": "act-pm-daemon",
            "source_role_id": "pm",
            "target_identity_id": "act-dev-daemon",
            "target_role_id": "dev",
            "payload": {"message_id": "msg-readable"},
            "created_at": "2026-05-30T00:00:00Z",
        }

        trigger = self.triggers.normalize_cross_actor_signal(signal)

        self.assertEqual(trigger.source, "mailbox_cross_actor_signal")
        self.assertEqual(trigger.type, "example.ready")
        self.assertEqual(trigger.target_identity_id, "act-dev-daemon")
        self.assertEqual(trigger.target_role_id, "dev")
        self.assertEqual(trigger.origin_id, "sig-readable")
        self.assertEqual(trigger.payload, {"message_id": "msg-readable"})
        self.assertEqual(
            trigger.source_context,
            {
                "signal_id": "sig-readable",
                "source_identity_id": "act-pm-daemon",
                "source_role_id": "pm",
                "created_at": "2026-05-30T00:00:00Z",
            },
        )

    def test_trigger_router_dispatches_only_through_unified_handler_interface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            handler = RecordingHandler()

            result = self.daemon_core.dispatch_trigger(
                instance["context"],
                instance["state"],
                runtime=object(),
                trigger=self._trigger(),
                handlers=[IgnoringHandler(), handler],
            )

            self.assertEqual(result["matched_count"], 1)
            self.assertEqual(result["handled_count"], 1)
            self.assertEqual(result["handling_status"], "handled")
            self.assertEqual(handler.handled, [self._trigger()])
            saved = json.loads(daemon_state.daemon_state_file(instance["context"].instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["handlers"]["recording"]["last_result"], "handled")

    def test_trigger_router_reports_handler_failures_and_invalid_returns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)

            result = self.daemon_core.dispatch_trigger(
                instance["context"],
                instance["state"],
                runtime=object(),
                trigger=self._trigger(),
                handlers=[FailingHandler(), InvalidReturnHandler()],
            )

            self.assertEqual(result["matched_count"], 2)
            self.assertEqual(result["handled_count"], 0)
            self.assertEqual(result["handling_status"], "failed")
            self.assertIn("handler failed intentionally", result["handling_error"])
            self.assertIn("handler returned invalid result", result["handling_error"])
            saved = json.loads(daemon_state.daemon_state_file(instance["context"].instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["handlers"]["failing"]["last_result"], "failed")
            self.assertEqual(saved["handlers"]["invalid_return"]["last_result"], "failed")

    def test_trigger_router_source_has_no_legacy_entry_method_calls(self) -> None:
        import inspect

        source = inspect.getsource(self.daemon_core.dispatch_trigger)

        self.assertNotIn("handle_notification", source)
        self.assertNotIn("handle_signal", source)
        self.assertNotIn("handle_parent_required", source)

    def test_scheduled_trigger_registration_persists_pending_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)

            schedule = instance["state"].create_schedule(
                delay_seconds=600,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-idle-1"},
                source_context={"owner": "browser"},
                now="2026-06-24T00:00:00Z",
            )

            self.assertEqual(schedule["schedule_id"], "schedule-1")
            self.assertEqual(schedule["type"], "browser.page.expired")
            self.assertEqual(schedule["status"], "pending")
            self.assertEqual(schedule["due_at"], "2026-06-24T00:10:00Z")
            self.assertEqual(schedule["created_at"], "2026-06-24T00:00:00Z")
            self.assertEqual(schedule["updated_at"], "2026-06-24T00:00:00Z")
            self.assertEqual(schedule["last_error"], None)
            self.assertEqual(schedule["payload"], {"target_id": "target-idle-1"})
            self.assertEqual(schedule["source_context"], {"owner": "browser"})

            saved = json.loads(daemon_state.daemon_state_file(instance["context"].instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["scheduled_trigger_ids"], ["schedule-1"])
            self.assertEqual(saved["scheduled_triggers"]["schedule-1"], schedule)

    def test_keyed_schedule_upsert_replaces_pending_schedule_for_same_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)

            first = instance["state"].upsert_schedule(
                delay_seconds=300,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-1"},
                source_context={"owner": "browser", "attempt": 1},
                schedule_key="browser.page.idle:target-1",
                now="2026-06-24T00:00:00Z",
            )
            second = instance["state"].upsert_schedule(
                delay_seconds=300,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-1", "refreshed": True},
                source_context={"owner": "browser", "attempt": 2},
                schedule_key="browser.page.idle:target-1",
                now="2026-06-24T00:04:00Z",
            )

            self.assertEqual(second["schedule_id"], first["schedule_id"])
            self.assertEqual(second["schedule_key"], "browser.page.idle:target-1")
            self.assertEqual(second["created_at"], "2026-06-24T00:00:00Z")
            self.assertEqual(second["updated_at"], "2026-06-24T00:04:00Z")
            self.assertEqual(second["due_at"], "2026-06-24T00:09:00Z")
            self.assertEqual(second["payload"], {"target_id": "target-1", "refreshed": True})
            self.assertEqual(second["source_context"], {"owner": "browser", "attempt": 2})

            saved = json.loads(daemon_state.daemon_state_file(instance["context"].instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["scheduled_trigger_ids"], ["schedule-1"])
            self.assertEqual(saved["scheduled_triggers"]["schedule-1"], second)
            self.assertNotIn("browser_page_idle", saved)
            self.assertNotIn("current_" + "target_id", saved)

    def test_keyed_schedule_upsert_does_not_reuse_non_pending_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            delivered = instance["state"].upsert_schedule(
                delay_seconds=0,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-1", "generation": 1},
                schedule_key="browser.page.idle:target-1",
                now="2026-06-24T00:00:00Z",
            )
            instance["state"].mark_schedule_delivered(
                delivered["schedule_id"],
                dispatch_result={"handling_status": "handled"},
                now="2026-06-24T00:00:01Z",
            )

            pending = instance["state"].upsert_schedule(
                delay_seconds=300,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-1", "generation": 2},
                schedule_key="browser.page.idle:target-1",
                now="2026-06-24T00:01:00Z",
            )

            self.assertEqual(delivered["schedule_id"], "schedule-1")
            self.assertEqual(pending["schedule_id"], "schedule-2")
            saved = json.loads(daemon_state.daemon_state_file(instance["context"].instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["scheduled_trigger_ids"], ["schedule-1", "schedule-2"])
            self.assertEqual(saved["scheduled_triggers"]["schedule-1"]["status"], "delivered")
            self.assertEqual(saved["scheduled_triggers"]["schedule-2"]["status"], "pending")

    def test_due_scheduled_trigger_dispatch_marks_delivered_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            instance["state"].create_schedule(
                delay_seconds=0,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-ttl-1"},
                source_context={"owner": "browser"},
                now="2026-06-24T00:00:00Z",
            )
            handled: list[Any] = []
            core = self.daemon_core

            class BrowserExpiryHandler:
                name = "browser_page_expired"

                def handles(self, trigger: Any) -> bool:
                    return trigger.type == "browser.page.expired"

                def handle(self, _context: object, _state: object, _runtime: object, trigger: Any) -> object:
                    handled.append(trigger)
                    return daemon_contracts.HandlerResult.handled()

            first = self.daemon_core.sweep_due_scheduled_triggers(
                instance["context"],
                instance["state"],
                runtime=object(),
                handlers=[BrowserExpiryHandler()],
                now="2026-06-24T00:00:01Z",
            )
            second = self.daemon_core.sweep_due_scheduled_triggers(
                instance["context"],
                instance["state"],
                runtime=object(),
                handlers=[BrowserExpiryHandler()],
                now="2026-06-24T00:00:02Z",
            )

            self.assertEqual(first["swept_count"], 1)
            self.assertEqual(first["delivered_count"], 1)
            self.assertEqual(first["failed_count"], 0)
            self.assertEqual(second["swept_count"], 0)
            self.assertEqual(len(handled), 1)
            trigger = handled[0]
            self.assertEqual(trigger.source, "scheduled_trigger")
            self.assertEqual(trigger.type, "browser.page.expired")
            self.assertEqual(trigger.origin_id, "schedule-1")
            self.assertEqual(trigger.payload, {"target_id": "target-ttl-1"})
            self.assertEqual(trigger.source_context["schedule_id"], "schedule-1")
            self.assertEqual(trigger.source_context["owner"], "browser")
            saved = json.loads(daemon_state.daemon_state_file(instance["context"].instance_root).read_text(encoding="utf-8"))
            row = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(row["status"], "delivered")
            self.assertEqual(row["delivered_at"], "2026-06-24T00:00:01Z")
            self.assertIsNone(row["last_error"])
            self.assertEqual(row["dispatch_result"]["handling_status"], "handled")

    def test_due_scheduled_trigger_preserves_schedule_refreshed_during_handling(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            instance["state"].upsert_schedule(
                delay_seconds=0,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-ttl-1"},
                source_context={"owner": "browser", "generation": 1},
                schedule_key="browser.page.idle:target-ttl-1",
                now="2026-06-24T00:00:00Z",
            )
            handled: list[Any] = []
            core = self.daemon_core

            class RefreshingBrowserExpiryHandler:
                name = "browser_page_expired"

                def handles(self, trigger: Any) -> bool:
                    return trigger.type == "browser.page.expired"

                def handle(self, _context: object, state: Any, _runtime: object, trigger: Any) -> object:
                    handled.append(trigger)
                    state.upsert_schedule(
                        delay_seconds=300,
                        trigger_type="browser.page.expired",
                        payload={"target_id": "target-ttl-1"},
                        source_context={"owner": "browser", "generation": 2},
                        schedule_key="browser.page.idle:target-ttl-1",
                        now="2026-06-24T00:00:01Z",
                    )
                    return daemon_contracts.HandlerResult.handled()

            first = self.daemon_core.sweep_due_scheduled_triggers(
                instance["context"],
                instance["state"],
                runtime=object(),
                handlers=[RefreshingBrowserExpiryHandler()],
                now="2026-06-24T00:00:01Z",
            )
            second = self.daemon_core.sweep_due_scheduled_triggers(
                instance["context"],
                instance["state"],
                runtime=object(),
                handlers=[RefreshingBrowserExpiryHandler()],
                now="2026-06-24T00:00:02Z",
            )

            self.assertEqual(first["swept_count"], 1)
            self.assertEqual(first["delivered_count"], 0)
            self.assertEqual(first["failed_count"], 0)
            self.assertEqual(second["swept_count"], 0)
            self.assertEqual(len(handled), 1)
            saved = json.loads(daemon_state.daemon_state_file(instance["context"].instance_root).read_text(encoding="utf-8"))
            row = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(row["status"], "pending")
            self.assertEqual(row["due_at"], "2026-06-24T00:05:01Z")
            self.assertEqual(row["source_context"], {"owner": "browser", "generation": 2})
            self.assertEqual(row["payload"], {"target_id": "target-ttl-1"})

    def test_due_scheduled_trigger_with_no_handler_marks_failed_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            instance["state"].create_schedule(
                delay_seconds=0,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-ttl-1"},
                now="2026-06-24T00:00:00Z",
            )

            first = self.daemon_core.sweep_due_scheduled_triggers(
                instance["context"],
                instance["state"],
                runtime=object(),
                handlers=[],
                now="2026-06-24T00:00:01Z",
            )
            second = self.daemon_core.sweep_due_scheduled_triggers(
                instance["context"],
                instance["state"],
                runtime=object(),
                handlers=[],
                now="2026-06-24T00:00:02Z",
            )

            self.assertEqual(first["swept_count"], 1)
            self.assertEqual(first["failed_count"], 1)
            self.assertEqual(second["swept_count"], 0)
            saved = json.loads(daemon_state.daemon_state_file(instance["context"].instance_root).read_text(encoding="utf-8"))
            row = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(row["status"], "failed")
            self.assertEqual(row["last_error"], "scheduled trigger had no matching handler")
            self.assertEqual(row["dispatch_result"]["handling_status"], "ignored")

    def test_due_scheduled_trigger_handler_failure_marks_failed_without_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            instance["state"].create_schedule(
                delay_seconds=0,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-ttl-1"},
                now="2026-06-24T00:00:00Z",
            )
            core = self.daemon_core

            class FailingBrowserExpiryHandler:
                name = "browser_page_expired"

                def handles(self, trigger: Any) -> bool:
                    return trigger.type == "browser.page.expired"

                def handle(self, *_args: object) -> object:
                    return daemon_contracts.HandlerResult.failed("close failed")

            first = self.daemon_core.sweep_due_scheduled_triggers(
                instance["context"],
                instance["state"],
                runtime=object(),
                handlers=[FailingBrowserExpiryHandler()],
                now="2026-06-24T00:00:01Z",
            )
            second = self.daemon_core.sweep_due_scheduled_triggers(
                instance["context"],
                instance["state"],
                runtime=object(),
                handlers=[FailingBrowserExpiryHandler()],
                now="2026-06-24T00:00:02Z",
            )

            self.assertEqual(first["swept_count"], 1)
            self.assertEqual(first["failed_count"], 1)
            self.assertEqual(second["swept_count"], 0)
            saved = json.loads(daemon_state.daemon_state_file(instance["context"].instance_root).read_text(encoding="utf-8"))
            row = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(row["status"], "failed")
            self.assertEqual(row["last_error"], "close failed")
            self.assertEqual(row["dispatch_result"]["handling_status"], "failed")

    def test_canceled_schedule_is_not_dispatched(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            schedule = instance["state"].create_schedule(
                delay_seconds=0,
                trigger_type="browser.page.expired",
                payload={"target_id": "target-ttl-1"},
                now="2026-06-24T00:00:00Z",
            )
            instance["state"].cancel_schedule(schedule["schedule_id"], now="2026-06-24T00:00:01Z")
            calls: list[str] = []

            class BrowserExpiryHandler:
                name = "browser_page_expired"

                def handles(self, trigger: Any) -> bool:
                    return trigger.type == "browser.page.expired"

                def handle(self, *_args: object) -> object:
                    calls.append("called")
                    raise AssertionError("canceled schedule must not dispatch")

            result = self.daemon_core.sweep_due_scheduled_triggers(
                instance["context"],
                instance["state"],
                runtime=object(),
                handlers=[BrowserExpiryHandler()],
                now="2026-06-24T00:00:02Z",
            )

            self.assertEqual(result["swept_count"], 0)
            self.assertEqual(calls, [])
            saved = json.loads(daemon_state.daemon_state_file(instance["context"].instance_root).read_text(encoding="utf-8"))
            row = saved["scheduled_triggers"]["schedule-1"]
            self.assertEqual(row["status"], "canceled")
            self.assertEqual(row["canceled_at"], "2026-06-24T00:00:01Z")
