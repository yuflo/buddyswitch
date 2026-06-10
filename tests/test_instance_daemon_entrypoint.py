#!/usr/bin/env python3
"""Tests for the instance daemon CLI entrypoint wiring."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import ast
import unittest
from itertools import count
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSTANCE_DAEMON_PATH = ROOT / "tools" / "launcher" / "instance_daemon.py"
DAEMON_SH_PATH = ROOT / "tools" / "launcher" / "daemon.sh"
CENTRAL_DAEMON_PATH = ROOT / "tools" / "launcher" / "central_daemon.py"
MODULE_COUNTER = count()


def load_instance_daemon() -> Any:
    if not INSTANCE_DAEMON_PATH.exists():
        raise AssertionError(f"expected module to exist: {INSTANCE_DAEMON_PATH}")
    module_name = f"buddyswitch_instance_daemon_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, INSTANCE_DAEMON_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {INSTANCE_DAEMON_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    def setUp(self) -> None:
        self.instance_daemon = load_instance_daemon()

    def test_default_daemon_handlers_are_built_through_notification_center(self) -> None:
        imports = imported_modules(INSTANCE_DAEMON_PATH)

        self.assertIn("notification_center", imports)
        self.assertIn("message_inbound", imports)
        self.assertNotIn("message_available_handler", imports)
        self.assertEqual(self.instance_daemon.default_notify_subscriptions(), ["message.available"])
        handlers = self.instance_daemon.default_daemon_handlers()
        self.assertEqual([type(handler).__name__ for handler in handlers], ["TaskCheckoutHandler", "MessageAvailableHandler"])

    def test_run_passes_unified_daemon_handler_list_to_daemon_core(self) -> None:
        recorded: dict[str, object] = {}
        original_run = self.instance_daemon.daemon_core.run_daemon

        def fake_run(
            instance_json: Path,
            *,
            handlers: list[object] | None = None,
            notify_subscriptions: list[str] | None = None,
        ) -> int:
            recorded["instance_json"] = instance_json
            recorded["handlers"] = handlers or []
            recorded["notify_subscriptions"] = notify_subscriptions or []
            return 0

        self.addCleanup(setattr, self.instance_daemon.daemon_core, "run_daemon", original_run)
        self.instance_daemon.daemon_core.run_daemon = fake_run

        result = self.instance_daemon.main(["run", "--instance-json", "/tmp/inst.json"])

        self.assertEqual(result, 0)
        handlers = recorded["handlers"]
        assert isinstance(handlers, list)
        self.assertEqual([type(handler).__name__ for handler in handlers], ["TaskCheckoutHandler", "MessageAvailableHandler"])
        self.assertEqual(type(handlers[0]).__name__, "TaskCheckoutHandler")
        self.assertEqual(getattr(handlers[0], "name", None), "task_checkout")
        self.assertEqual(getattr(handlers[1], "name", None), "message_available")
        self.assertEqual(recorded["instance_json"], Path("/tmp/inst.json"))
        self.assertEqual(recorded["notify_subscriptions"], ["message.available"])

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
            result = self.instance_daemon.main(["start", "--instance-json", "/tmp/inst.json"])

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), {"started": True, "pid": 4321})
        handlers = recorded["handlers"]
        assert isinstance(handlers, list)
        self.assertEqual([getattr(handler, "name", None) for handler in handlers], ["task_checkout", "message_available"])
        self.assertEqual(getattr(handlers[0], "name", None), "task_checkout")
        self.assertEqual(recorded["notify_subscriptions"], ["message.available"])

    def test_stop_prints_json_from_daemon_core(self) -> None:
        original_stop = self.instance_daemon.daemon_core.stop_daemon

        def fake_stop(instance_json: Path) -> dict[str, object]:
            self.assertEqual(instance_json, Path("/tmp/inst.json"))
            return {"ok": True, "terminated": True}

        self.addCleanup(setattr, self.instance_daemon.daemon_core, "stop_daemon", original_stop)
        self.instance_daemon.daemon_core.stop_daemon = fake_stop
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = self.instance_daemon.main(["stop", "--instance-json", "/tmp/inst.json"])

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
            result = self.instance_daemon.main(["status", "--instance-json", "/tmp/inst.json", "--json"])

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), {"live": True, "ready": True})
        handlers = recorded["handlers"]
        assert isinstance(handlers, list)
        self.assertEqual([getattr(handler, "name", None) for handler in handlers], ["task_checkout", "message_available"])
        self.assertEqual(recorded["notify_subscriptions"], ["message.available"])

    def test_daemon_shell_still_calls_instance_daemon_entrypoint(self) -> None:
        shell_source = DAEMON_SH_PATH.read_text(encoding="utf-8")
        self.assertIn("instance_daemon.py", shell_source)

    def test_daemon_shell_ensures_central_daemon_lifecycle(self) -> None:
        shell_source = DAEMON_SH_PATH.read_text(encoding="utf-8")
        self.assertIn("central_daemon.py", shell_source)
        self.assertIn("buddyswitch_central_daemon_ensure", shell_source)
        self.assertIn("buddyswitch_central_daemon_stop_if_idle", shell_source)
        self.assertTrue(CENTRAL_DAEMON_PATH.exists())


if __name__ == "__main__":
    unittest.main()
