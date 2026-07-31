"""Tests for the instance daemon CLI entrypoint wiring."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import ast
import unittest
from itertools import count
from pathlib import Path
from typing import Any


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
INSTANCE_DAEMON_PATH = ROOT / "src" / "buddyswitch" / "launcher" / "instance_daemon.py"
DAEMON_SH_PATH = (
    ROOT / "src" / "buddyswitch" / "launcher" / "shell" / "daemon.sh"
)
CENTRAL_DAEMON_PATH = ROOT / "src" / "buddyswitch" / "launcher" / "central_daemon.py"
MODULE_COUNTER = count()
EXPECTED_SUBSCRIPTIONS = ["im.message.created", "track.comment.added"]
EXPECTED_HANDLER_TYPES = [
    "ImMessageCreatedHandler",
    "TrackCommentAddedHandler",
    "BrowserPageExpiredHandler",
    "BrowserReleaseHandler",
    "BrowserFailedOpenPageCleanupHandler",
    "DemandTriageHandler",
    "TaskGoalHandler",
    "DemandOrchestrationHandler",
]
EXPECTED_HANDLER_NAMES = [
    "im_message_created",
    "track_comment_added",
    "browser_page_expired",
    "browser_cockpit_release",
    "browser_failed_open_page_cleanup",
    "demand_triage",
    "task_goal",
    "demand_orchestration",
]


def load_instance_daemon() -> Any:
    if not INSTANCE_DAEMON_PATH.exists():
        raise AssertionError(f"expected module to exist: {INSTANCE_DAEMON_PATH}")
    return importlib.reload(importlib.import_module("buddyswitch.launcher.instance_daemon"))


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name:
                imports.add(module_name)
            for alias in node.names:
                imports.add(f"{module_name}.{alias.name}" if module_name else alias.name)
    return imports


class InstanceDaemonEntrypointTests(unittest.TestCase):
    def test_task_application_commands_are_registered_only_at_composition_root(self) -> None:
        imports = imported_modules(INSTANCE_DAEMON_PATH)
        self.assertFalse(
            [
                name
                for name in imports
                if name.startswith("buddyswitch.modules.task")
                or name == "buddyswitch.launcher.task_goal_handler"
            ]
        )
        self.assertNotIn("task_sys_daemon_adapter", imports)
        factories = self.instance_daemon.default_application_command_factories(
            self.application.daemon_handlers
        )
        expected = [
            registration.application_command_factory
            for registration in self.application.daemon_handlers
            if registration.name == "task_goal"
        ]
        self.assertEqual(factories, expected)

    def setUp(self) -> None:
        self.instance_daemon = load_instance_daemon()
        from buddyswitch.application.build import build_application

        self.application = build_application()

    def test_default_daemon_handlers_are_built_through_notification_center(self) -> None:
        imports = imported_modules(INSTANCE_DAEMON_PATH)

        self.assertIn("buddyswitch.launcher.notification_center", imports)
        self.assertIn("buddyswitch.launcher.browser_inbound", imports)
        self.assertIn("buddyswitch.launcher.message_inbound", imports)
        self.assertFalse(
            any("track" in name for name in imports),
            msg=imports,
        )
        self.assertNotIn("buddyswitch.launcher.demand_triage_handler", imports)
        self.assertNotIn("buddyswitch.launcher.demand_orchestration_handler", imports)
        self.assertNotIn("message" + "_available" + "_handler", imports)
        self.assertNotIn("track_comment_added_handler", imports)
        self.assertNotIn("browser_page_expired_handler", imports)
        self.assertNotIn("task_" + "checkout_handler", imports)
        self.assertFalse((ROOT / "src" / "buddyswitch" / "launcher" / ("task_" + "checkout_handler.py")).exists())
        self.assertEqual(
            self.instance_daemon.default_notify_subscriptions(
                self.application.inbound_sources
            ),
            EXPECTED_SUBSCRIPTIONS,
        )
        handlers = self.instance_daemon.default_daemon_handlers(
            self.application.daemon_handlers,
            self.application.inbound_sources,
        )
        self.assertEqual([type(handler).__name__ for handler in handlers], EXPECTED_HANDLER_TYPES)
        self.assertEqual(type(handlers[-2]).__name__, "TaskGoalHandler")
        self.assertEqual(type(handlers[-1]).__name__, "DemandOrchestrationHandler")

    def test_component_handler_identity_must_match_registration_and_built_ins(self) -> None:
        from buddyswitch.launcher.daemon_contracts import DaemonHandlerRegistration

        class MismatchedHandler:
            name = "actual"

        with self.assertRaisesRegex(
            ValueError,
            "daemon handler registration 'declared' constructed 'actual'",
        ):
            self.instance_daemon.default_daemon_handlers(
                (
                    DaemonHandlerRegistration(
                        name="declared",
                        factory=MismatchedHandler,
                    ),
                )
            )

        class BuiltInCollision:
            name = "im_message_created"

        with self.assertRaisesRegex(
            ValueError,
            "duplicate daemon handler registration: im_message_created",
        ):
            self.instance_daemon.default_daemon_handlers(
                (
                    DaemonHandlerRegistration(
                        name="im_message_created",
                        factory=BuiltInCollision,
                    ),
                )
            )

    def test_run_passes_unified_daemon_handler_list_to_daemon_core(self) -> None:
        recorded: dict[str, object] = {}
        original_run = self.instance_daemon.daemon_core.run_daemon

        def fake_run(
            instance_json: Path,
            *,
            handlers: list[object] | None = None,
            notify_subscriptions: list[str] | None = None,
            application_command_factories: list[object] | None = None,
        ) -> int:
            recorded["instance_json"] = instance_json
            recorded["handlers"] = handlers or []
            recorded["notify_subscriptions"] = notify_subscriptions or []
            recorded["application_command_factories"] = application_command_factories or []
            return 0

        self.addCleanup(setattr, self.instance_daemon.daemon_core, "run_daemon", original_run)
        self.instance_daemon.daemon_core.run_daemon = fake_run

        result = self.instance_daemon.main(
            ["run", "--instance-json", "/tmp/inst.json"],
            component_registrations=self.application.daemon_handlers,
            inbound_source_registrations=self.application.inbound_sources,
        )

        self.assertEqual(result, 0)
        handlers = recorded["handlers"]
        assert isinstance(handlers, list)
        self.assertEqual([type(handler).__name__ for handler in handlers], EXPECTED_HANDLER_TYPES)
        self.assertEqual(getattr(handlers[0], "name", None), "im_message_created")
        self.assertEqual(getattr(handlers[1], "name", None), "track_comment_added")
        self.assertEqual(recorded["instance_json"], Path("/tmp/inst.json"))
        self.assertEqual(recorded["notify_subscriptions"], EXPECTED_SUBSCRIPTIONS)
        self.assertEqual(
            recorded["application_command_factories"],
            self.instance_daemon.default_application_command_factories(
                self.application.daemon_handlers
            ),
        )

    def test_start_prints_json_from_daemon_core(self) -> None:
        original_start = self.instance_daemon.daemon_core.start_daemon
        recorded: dict[str, object] = {}

        def fake_start(
            instance_json: Path,
            *,
            handlers: list[object] | None = None,
            notify_subscriptions: list[str] | None = None,
        ) -> dict[str, object]:
            self.assertEqual(instance_json, Path("/tmp/inst.json"))
            recorded["handlers"] = handlers or []
            recorded["notify_subscriptions"] = notify_subscriptions or []
            return {"started": True, "pid": 4321}

        self.addCleanup(setattr, self.instance_daemon.daemon_core, "start_daemon", original_start)
        self.instance_daemon.daemon_core.start_daemon = fake_start
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = self.instance_daemon.main(
                ["start", "--instance-json", "/tmp/inst.json"],
                component_registrations=self.application.daemon_handlers,
                inbound_source_registrations=self.application.inbound_sources,
            )

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), {"started": True, "pid": 4321})
        handlers = recorded["handlers"]
        assert isinstance(handlers, list)
        self.assertEqual([getattr(handler, "name", None) for handler in handlers], EXPECTED_HANDLER_NAMES)
        self.assertEqual(getattr(handlers[0], "name", None), "im_message_created")
        self.assertEqual(recorded["notify_subscriptions"], EXPECTED_SUBSCRIPTIONS)

    def test_stop_prints_json_from_daemon_core(self) -> None:
        original_stop = self.instance_daemon.daemon_core.stop_daemon

        def fake_stop(instance_json: Path) -> dict[str, object]:
            self.assertEqual(instance_json, Path("/tmp/inst.json"))
            return {"ok": True, "terminated": True}

        self.addCleanup(setattr, self.instance_daemon.daemon_core, "stop_daemon", original_stop)
        self.instance_daemon.daemon_core.stop_daemon = fake_stop
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = self.instance_daemon.main(
                ["stop", "--instance-json", "/tmp/inst.json"],
                component_registrations=self.application.daemon_handlers,
                inbound_source_registrations=self.application.inbound_sources,
            )

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), {"ok": True, "terminated": True})

    def test_status_prints_json_from_daemon_core(self) -> None:
        original_status = self.instance_daemon.daemon_core.daemon_status
        recorded: dict[str, object] = {}

        def fake_status(
            instance_json: Path,
            *,
            handlers: list[object] | None = None,
            notify_subscriptions: list[str] | None = None,
        ) -> dict[str, object]:
            self.assertEqual(instance_json, Path("/tmp/inst.json"))
            recorded["handlers"] = handlers or []
            recorded["notify_subscriptions"] = notify_subscriptions or []
            return {"live": True, "ready": True}

        self.addCleanup(setattr, self.instance_daemon.daemon_core, "daemon_status", original_status)
        self.instance_daemon.daemon_core.daemon_status = fake_status
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = self.instance_daemon.main(
                ["status", "--instance-json", "/tmp/inst.json", "--json"],
                component_registrations=self.application.daemon_handlers,
                inbound_source_registrations=self.application.inbound_sources,
            )

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), {"live": True, "ready": True})
        handlers = recorded["handlers"]
        assert isinstance(handlers, list)
        self.assertEqual([getattr(handler, "name", None) for handler in handlers], EXPECTED_HANDLER_NAMES)
        self.assertEqual(recorded["notify_subscriptions"], EXPECTED_SUBSCRIPTIONS)

    def test_daemon_shell_still_calls_instance_daemon_entrypoint(self) -> None:
        shell_source = DAEMON_SH_PATH.read_text(encoding="utf-8")
        self.assertIn("-m buddyswitch.application.entrypoints.instance_daemon", shell_source)

    def test_daemon_shell_ensures_central_daemon_lifecycle(self) -> None:
        shell_source = DAEMON_SH_PATH.read_text(encoding="utf-8")
        self.assertIn("-m buddyswitch.application.entrypoints.central_daemon", shell_source)
        self.assertIn("buddyswitch_central_daemon_ensure", shell_source)
        self.assertIn("buddyswitch_central_daemon_stop_if_idle", shell_source)
        self.assertTrue(CENTRAL_DAEMON_PATH.exists())
