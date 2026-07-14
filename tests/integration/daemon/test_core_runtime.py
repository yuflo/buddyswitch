"""Tests for daemon core state, lifecycle, and run loop."""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any
from unittest.mock import patch


from tests.support.paths import REPO_ROOT

ROOT = REPO_ROOT
SCRIPTS = ROOT / "scripts"
LAUNCHER = ROOT / "tools" / "launcher"

import daemon_contracts  # noqa: E402
import daemon_state  # noqa: E402
from env.repos import identities as identity_repo  # noqa: E402
from env.repos import runtime_files  # noqa: E402

DAEMON_CORE_PATH = ROOT / "tools" / "launcher" / "daemon_core.py"
INSTANCE_DAEMON_PATH = ROOT / "tools" / "launcher" / "instance_daemon.py"
MODULE_COUNTER = count()
RUNTIME_ENV_KEYS = (
    "BUDDYSWITCH_SHARED_ROOT",
    "BUDDYSWITCH_STATE_ROOT",
    "BUDDYSWITCH_INSTANCE_ROOT",
    "BUDDYSWITCH_INSTANCE_JSON",
    "BUDDYSWITCH_WORKSPACE_DIR",
    "BUDDYSWITCH_ACTOR_ID",
    "BUDDYSWITCH_ROLE_ID",
)


def load_daemon_core() -> Any:
    if not DAEMON_CORE_PATH.exists():
        raise AssertionError(f"expected daemon core module to exist: {DAEMON_CORE_PATH}")
    return importlib.reload(importlib.import_module("daemon_core"))


class StopDaemonLoop(RuntimeError):
    pass


class DaemonCoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_runtime_env = {key: os.environ.get(key) for key in RUNTIME_ENV_KEYS}
        self.addCleanup(self._restore_runtime_env, self._saved_runtime_env)
        self.core = load_daemon_core()

    def _restore_runtime_env(self, values: dict[str, str | None]) -> None:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        runtime_files.refresh_runtime_roots_from_env()


class DaemonCoreLifecycleTests(DaemonCoreTestCase):
    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "act-dev-daed00000001"
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload = {
            "actor_id": "act-dev-daed00000001",
            "role": "dev",
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(instance_root / "workspace"),
            "thread_id": "thr-main",
            "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
        }
        instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        return {"instance_root": instance_root, "instance_json": instance_json}

    def _patch_process_start(self, pids: list[int]) -> tuple[list[list[str]], list[dict[str, object]]]:
        commands: list[list[str]] = []
        popen_kwargs: list[dict[str, object]] = []
        original_popen = self.core.subprocess.Popen

        class FakeProcess:
            def __init__(self, pid: int) -> None:
                self.pid = pid

            def poll(self) -> None:
                return None

        def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
            commands.append(command)
            popen_kwargs.append(kwargs)
            return FakeProcess(pids.pop(0))

        self.addCleanup(setattr, self.core.subprocess, "Popen", original_popen)
        self.core.subprocess.Popen = fake_popen
        return commands, popen_kwargs

    def _patch_sleep_to_record_ready(
        self,
        *,
        instance_root: Path,
        pid: int,
        main_thread_id: str = "thr-main",
    ) -> None:
        original_sleep = self.core.time.sleep
        recorded = {"done": False}

        def fake_sleep(_seconds: float) -> None:
            if not recorded["done"]:
                state = daemon_state.DaemonState.load(
                    instance_root=instance_root,
                    actor_id="act-dev-daed00000001",
                    main_thread_id=main_thread_id,
                )
                state.record_ready(pid=pid, main_thread_id=main_thread_id)
                recorded["done"] = True

        self.addCleanup(setattr, self.core.time, "sleep", original_sleep)
        self.core.time.sleep = fake_sleep

    def _patch_monotonic_step(self, *, start: float = 0.0, step: float = 0.1) -> None:
        original_monotonic = self.core.time.monotonic
        current = {"value": start - step}

        def fake_monotonic() -> float:
            current["value"] += step
            return current["value"]

        self.addCleanup(setattr, self.core.time, "monotonic", original_monotonic)
        self.core.time.monotonic = fake_monotonic

    def _patch_ready_constants(self, *, timeout_seconds: float, poll_seconds: float) -> None:
        original_timeout = self.core.DAEMON_READY_TIMEOUT_SECONDS
        original_poll = self.core.DAEMON_READY_POLL_SECONDS
        self.addCleanup(setattr, self.core, "DAEMON_READY_TIMEOUT_SECONDS", original_timeout)
        self.addCleanup(setattr, self.core, "DAEMON_READY_POLL_SECONDS", original_poll)
        self.core.DAEMON_READY_TIMEOUT_SECONDS = timeout_seconds
        self.core.DAEMON_READY_POLL_SECONDS = poll_seconds

    def _patch_exited_process_start(self, pid: int) -> None:
        original_popen = self.core.subprocess.Popen

        class FakeExitedProcess:
            def __init__(self) -> None:
                self.pid = pid

            def poll(self) -> int:
                return 1

        def fake_popen(command: list[str], **_kwargs: object) -> FakeExitedProcess:
            return FakeExitedProcess()

        self.addCleanup(setattr, self.core.subprocess, "Popen", original_popen)
        self.core.subprocess.Popen = fake_popen

    def _patch_pid_live(self, live_pids: set[int]) -> None:
        original_pid_is_live = self.core._pid_is_live
        original_start_identity = self.core.process_identity.start_identity
        original_matches = self.core.process_identity.matches
        original_is_running = self.core.process_identity.is_running
        self.addCleanup(setattr, self.core, "_pid_is_live", original_pid_is_live)
        self.addCleanup(
            setattr,
            self.core.process_identity,
            "start_identity",
            original_start_identity,
        )
        self.addCleanup(setattr, self.core.process_identity, "matches", original_matches)
        self.addCleanup(
            setattr,
            self.core.process_identity,
            "is_running",
            original_is_running,
        )
        self.core._pid_is_live = lambda pid: pid in live_pids
        self.core.process_identity.start_identity = lambda pid: f"test:{pid}"
        self.core.process_identity.matches = (
            lambda record: record.pid in live_pids
            and record.start_identity == f"test:{record.pid}"
        )
        self.core.process_identity.is_running = self.core.process_identity.matches

    def test_start_daemon_creates_runtime_files_and_is_idempotent_when_pid_is_live(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            commands, _popen_kwargs = self._patch_process_start([4321])
            self._patch_pid_live({4321})
            self._patch_sleep_to_record_ready(instance_root=instance["instance_root"], pid=4321)

            with patch.dict(os.environ, {"BUDDYSWITCH_PYTHON": "/configured/runtime/python"}, clear=False):
                first = self.core.start_daemon(instance["instance_json"])
                second = self.core.start_daemon(instance["instance_json"])

            self.assertTrue(first["started"])
            self.assertFalse(second["started"])
            self.assertEqual(first["pid"], 4321)
            self.assertEqual(second["pid"], 4321)
            self.assertTrue(first["ready"])
            self.assertTrue(second["ready"])
            self.assertEqual(len(commands), 1)
            self.assertEqual(commands[0][0], "/configured/runtime/python")
            self.assertEqual(Path(commands[0][1]).resolve(), INSTANCE_DAEMON_PATH.resolve())
            self.assertEqual(commands[0][2:], ["run", "--instance-json", str(instance["instance_json"])])
            self.assertTrue(self.core.daemon_pid_file(instance["instance_root"]).exists())
            self.assertTrue(self.core.daemon_log_file(instance["instance_root"]).exists())
            self.assertTrue(daemon_state.daemon_state_file(instance["instance_root"]).exists())

    def test_start_daemon_passes_shared_state_root_to_child_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            _commands, popen_kwargs = self._patch_process_start([4326])
            self._patch_pid_live({4326})
            self._patch_sleep_to_record_ready(instance_root=instance["instance_root"], pid=4326)

            payload = self.core.start_daemon(instance["instance_json"])

            self.assertTrue(payload["started"])
            self.assertEqual(len(popen_kwargs), 1)
            env = popen_kwargs[0].get("env")
            self.assertIsInstance(env, dict)
            assert isinstance(env, dict)
            self.assertEqual(env["BUDDYSWITCH_SHARED_ROOT"], str(Path(temp_root)))
            self.assertEqual(env["BUDDYSWITCH_STATE_ROOT"], str(Path(temp_root) / "state"))
            self.assertEqual(env["BUDDYSWITCH_INSTANCE_ROOT"], str(instance["instance_root"]))
            self.assertEqual(env["BUDDYSWITCH_INSTANCE_JSON"], str(instance["instance_json"]))
            self.assertEqual(env["BUDDYSWITCH_WORKSPACE_DIR"], str(instance["instance_root"] / "workspace"))

    def test_start_daemon_passes_actor_identity_env_to_child_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            _commands, popen_kwargs = self._patch_process_start([4330])
            self._patch_pid_live({4330})
            self._patch_sleep_to_record_ready(instance_root=instance["instance_root"], pid=4330)

            payload = self.core.start_daemon(instance["instance_json"])

            self.assertTrue(payload["started"])
            env = popen_kwargs[0].get("env")
            self.assertIsInstance(env, dict)
            assert isinstance(env, dict)
            self.assertEqual(env["BUDDYSWITCH_ACTOR_ID"], "act-dev-daed00000001")
            self.assertEqual(env["BUDDYSWITCH_ROLE_ID"], "dev")

    def test_start_daemon_replaces_stale_pid_before_starting_new_daemon(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            self.core.daemon_pid_file(instance["instance_root"]).parent.mkdir(parents=True, exist_ok=True)
            self.core.daemon_pid_file(instance["instance_root"]).write_text("9999\n", encoding="utf-8")
            commands, _popen_kwargs = self._patch_process_start([4322])
            self._patch_pid_live({4322})
            self._patch_sleep_to_record_ready(instance_root=instance["instance_root"], pid=4322)

            payload = self.core.start_daemon(instance["instance_json"])

            self.assertTrue(payload["started"])
            self.assertEqual(payload["pid"], 4322)
            self.assertTrue(payload["ready"])
            self.assertEqual(len(commands), 1)
            self.assertEqual(self.core.daemon_pid_file(instance["instance_root"]).read_text(encoding="utf-8").strip(), "4322")

    def test_start_daemon_fails_closed_if_process_exits_before_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            self._patch_exited_process_start(4323)
            self._patch_pid_live(set())

            with self.assertRaises(RuntimeError):
                self.core.start_daemon(instance["instance_json"])

            self.assertFalse(self.core.daemon_pid_file(instance["instance_root"]).exists())

    def test_start_daemon_fails_closed_if_readiness_times_out(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            self._patch_process_start([4324])
            self._patch_pid_live({4324})
            self._patch_ready_constants(timeout_seconds=0.2, poll_seconds=0.05)
            self._patch_monotonic_step(start=0.0, step=0.1)
            original_terminate = self.core._terminate_record
            terminated: list[int] = []
            self.addCleanup(setattr, self.core, "_terminate_record", original_terminate)
            self.core._terminate_record = lambda record: terminated.append(record.pid) or True

            with self.assertRaises(RuntimeError):
                self.core.start_daemon(instance["instance_json"])

            self.assertEqual(terminated, [4324])
            self.assertFalse(self.core.daemon_pid_file(instance["instance_root"]).exists())

    def test_start_daemon_replaces_live_unready_pid_before_starting_new_daemon(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            self.core.daemon_pid_file(instance["instance_root"]).parent.mkdir(parents=True, exist_ok=True)
            commands, _popen_kwargs = self._patch_process_start([4325])
            self._patch_pid_live({9999, 4325})
            self.core.process_identity.write_record(
                self.core.daemon_pid_file(instance["instance_root"]),
                9999,
            )
            self._patch_sleep_to_record_ready(instance_root=instance["instance_root"], pid=4325)
            original_terminate = self.core._terminate_record
            terminated: list[int] = []
            self.addCleanup(setattr, self.core, "_terminate_record", original_terminate)
            self.core._terminate_record = lambda record: terminated.append(record.pid) or True

            payload = self.core.start_daemon(instance["instance_json"])

            self.assertEqual(terminated, [9999])
            self.assertTrue(payload["started"])
            self.assertEqual(payload["pid"], 4325)
            self.assertTrue(payload["ready"])
            self.assertEqual(len(commands), 1)

    def test_stop_daemon_terminates_live_pid_and_removes_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            self.core.daemon_pid_file(instance["instance_root"]).parent.mkdir(parents=True, exist_ok=True)
            terminated: list[int] = []
            self._patch_pid_live({4321})
            self.core.process_identity.write_record(
                self.core.daemon_pid_file(instance["instance_root"]),
                4321,
            )
            original_terminate = self.core._terminate_record
            original_unregister = self.core.unregister_daemon_actor
            unregistered: list[dict[str, object]] = []
            self.addCleanup(setattr, self.core, "_terminate_record", original_terminate)
            self.addCleanup(setattr, self.core, "unregister_daemon_actor", original_unregister)
            self.core._terminate_record = lambda record: terminated.append(record.pid) or True
            self.core.unregister_daemon_actor = lambda context, identity_route: unregistered.append(
                {"context": context, "identity_route": dict(identity_route)}
            ) or {"record": {"identity_id": identity_route["identity_id"], "role_id": identity_route["role_id"]}}

            payload = self.core.stop_daemon(instance["instance_json"])

            self.assertTrue(payload["terminated"])
            self.assertEqual(terminated, [4321])
            self.assertEqual(unregistered[0]["identity_route"], {"identity_id": "act-dev-daed00000001", "role_id": "dev"})
            self.assertFalse(self.core.daemon_pid_file(instance["instance_root"]).exists())

    def test_stop_daemon_does_not_fail_when_central_unregister_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            self.core.daemon_pid_file(instance["instance_root"]).parent.mkdir(parents=True, exist_ok=True)
            terminated: list[int] = []
            self._patch_pid_live({4321})
            self.core.process_identity.write_record(
                self.core.daemon_pid_file(instance["instance_root"]),
                4321,
            )
            original_terminate = self.core._terminate_record
            original_unregister = self.core.unregister_daemon_actor
            self.addCleanup(setattr, self.core, "_terminate_record", original_terminate)
            self.addCleanup(setattr, self.core, "unregister_daemon_actor", original_unregister)
            self.core._terminate_record = lambda record: terminated.append(record.pid) or True

            def fail_unregister(_context: object, _identity_route: object) -> dict[str, object]:
                raise RuntimeError("central daemon unavailable")

            self.core.unregister_daemon_actor = fail_unregister

            payload = self.core.stop_daemon(instance["instance_json"])

            self.assertTrue(payload["terminated"])
            self.assertEqual(payload["unregister_status"], "failed")
            self.assertIn("central daemon unavailable", payload["unregister_error"])
            self.assertEqual(terminated, [4321])
            self.assertFalse(self.core.daemon_pid_file(instance["instance_root"]).exists())
            state = json.loads(daemon_state.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIn("central daemon unavailable", state["last_error"]["message"])

    def test_stop_daemon_preserves_actor_identity_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            os.environ["BUDDYSWITCH_SHARED_ROOT"] = str(Path(temp_root))
            os.environ["BUDDYSWITCH_STATE_ROOT"] = str(Path(temp_root) / "state")
            os.environ["BUDDYSWITCH_ACTOR_ID"] = "act-dev-daed00000001"
            runtime_files.refresh_runtime_roots_from_env()
            expected_profile = identity_repo.save_actor_identity_profile(
                {"identity": {"id": "act-dev-daed00000001", "type": "actor"}, "role_id": "dev"}
            )
            self.core.daemon_pid_file(instance["instance_root"]).parent.mkdir(parents=True, exist_ok=True)
            self._patch_pid_live({4321})
            self.core.process_identity.write_record(
                self.core.daemon_pid_file(instance["instance_root"]),
                4321,
            )
            original_terminate = self.core._terminate_record
            original_unregister = self.core.unregister_daemon_actor
            self.addCleanup(setattr, self.core, "_terminate_record", original_terminate)
            self.addCleanup(setattr, self.core, "unregister_daemon_actor", original_unregister)
            self.core._terminate_record = lambda _record: True
            self.core.unregister_daemon_actor = lambda _context, identity_route: {
                "record": {"identity_id": identity_route["identity_id"], "role_id": identity_route["role_id"]}
            }

            payload = self.core.stop_daemon(instance["instance_json"])

            self.assertTrue(payload["terminated"])
            self.assertEqual(identity_repo.get_actor_identity_profile("act-dev-daed00000001"), expected_profile)

    def test_daemon_status_reports_paths_live_state_and_last_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = daemon_state.DaemonState.load(
                instance_root=instance["instance_root"],
                actor_id="act-dev-daed00000001",
                main_thread_id="thr-main",
            )
            state.record_ready(pid=4321, main_thread_id="thr-main")
            state.record_error(origin_turn_id=None, message="socket gone")
            self._patch_pid_live({4321})
            self.core.process_identity.write_record(
                self.core.daemon_pid_file(instance["instance_root"]),
                4321,
            )

            payload = self.core.daemon_status(instance["instance_json"])

            self.assertEqual(payload["pid"], 4321)
            self.assertTrue(payload["pid_live"])
            self.assertTrue(payload["live"])
            self.assertTrue(payload["ready"])
            self.assertEqual(payload["ready_main_thread_id"], "thr-main")
            self.assertEqual(payload["log_path"], str(self.core.daemon_log_file(instance["instance_root"])))
            self.assertEqual(payload["state_path"], str(daemon_state.daemon_state_file(instance["instance_root"])))
            self.assertIsNone(payload["last_error"]["origin_turn_id"])
            self.assertEqual(payload["last_error"]["message"], "socket gone")

    def test_daemon_status_reports_registered_handler_observability(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)

            class FakeHandler:
                name = "example_primary"

            payload = self.core.daemon_status(
                instance["instance_json"],
                handlers=[FakeHandler(), type("FakeMessageHandler", (), {"name": "example_handler"})()],
            )

            self.assertEqual(payload["handlers"]["registered"], ["example_primary", "example_handler"])
            item = payload["handlers"]["items"]["example_primary"]
            self.assertIs(item["registered"], True)
            self.assertIs(item["enabled"], True)
            self.assertIs(item["active"], True)
            self.assertIsNone(item["last_result"])
            self.assertIsNone(item["last_error"])
            self.assertNotIn("last_" + "action" + "_turn_id", item)
            self.assertNotIn("mailbox_handlers", payload)
            mailbox_item = payload["handlers"]["items"]["example_handler"]
            self.assertIs(mailbox_item["registered"], True)
            self.assertIs(mailbox_item["enabled"], True)
            self.assertIs(mailbox_item["active"], True)
            self.assertIsNone(mailbox_item["last_result"])
            self.assertIsNone(mailbox_item["last_error"])
            self.assertNotIn("last_" + "action" + "_turn_id", mailbox_item)

    def test_daemon_status_includes_persisted_unregistered_handler_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = daemon_state.DaemonState.load(
                instance_root=instance["instance_root"],
                actor_id="act-dev-daed00000001",
                main_thread_id="thr-main",
            )
            state.record_handler_error("message", origin_turn_id="turn-user-1", message="message failed")
            state.record_handler_error(
                "example_handler",
                origin_turn_id="turn-user-2",
                message="example handler failed",
            )

            class FakeHandler:
                name = "example_primary"

            payload = self.core.daemon_status(
                instance["instance_json"],
                handlers=[FakeHandler(), type("FakeMessageHandler", (), {"name": "example_handler"})()],
            )

            self.assertEqual(payload["handlers"]["registered"], ["example_primary", "example_handler"])
            message_state = payload["handlers"]["items"]["message"]
            self.assertIs(message_state["registered"], False)
            self.assertIs(message_state["enabled"], False)
            self.assertIs(message_state["active"], False)
            self.assertEqual(message_state["last_error"]["message"], "message failed")
            self.assertNotIn("mailbox_handlers", payload)
            mailbox_state = payload["handlers"]["items"]["example_handler"]
            self.assertIs(mailbox_state["registered"], True)
            self.assertIs(mailbox_state["enabled"], True)
            self.assertIs(mailbox_state["active"], True)
            self.assertEqual(mailbox_state["last_error"]["message"], "example handler failed")


class FakeRunDaemonClient:
    def __init__(
        self,
        *,
        notifications: list[dict[str, object] | BaseException],
        bind_result: dict[str, object] | None = None,
        bind_error: BaseException | None = None,
    ) -> None:
        self.notifications = list(notifications)
        self.bind_result = bind_result or {"thread": {"id": "thr-main"}}
        self.bind_error = bind_error
        self.requests: list[dict[str, object]] = []

    def __enter__(self) -> FakeRunDaemonClient:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        return None

    def request(self, method: str, params: dict[str, object] | None) -> dict[str, object]:
        self.requests.append({"method": method, "params": params or {}})
        if method == "thread/resume":
            if self.bind_error is not None:
                raise self.bind_error
            return self.bind_result
        raise AssertionError(f"unexpected request method: {method}")

    def read_notification(self) -> dict[str, object]:
        if not self.notifications:
            raise StopDaemonLoop("stop")
        item = self.notifications.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class RecordingHandler:
    def __init__(self, *, name: str, result: object) -> None:
        self.name = name
        self.result = result
        self.triggers: list[object] = []

    def handles(self, trigger: object) -> bool:
        return getattr(trigger, "type", None) == "app_server.turn_completed"

    def handle(
        self,
        context: object,
        state: object,
        runtime: object,
        trigger: object,
    ) -> object:
        del context, state, runtime
        self.triggers.append(trigger)
        return self.result


class ExplodingOnceHandler:
    def __init__(self, *, result: object) -> None:
        self.name = "exploder"
        self.result = result
        self.calls = 0

    def handles(self, trigger: object) -> bool:
        return getattr(trigger, "type", None) == "app_server.turn_completed"

    def handle(
        self,
        context: object,
        state: object,
        runtime: object,
        trigger: object,
    ) -> object:
        del context, state, runtime, trigger
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("handler exploded")
        return self.result


class DaemonCoreRunLoopTests(DaemonCoreTestCase):
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

    def _completed(self, *, turn_id: str, thread_id: str = "thr-main", status: str = "completed") -> dict[str, object]:
        return {
            "method": "turn/completed",
            "params": {
                "threadId": thread_id,
                "turn": {
                    "id": turn_id,
                    "items": [],
                    "itemsView": "summary",
                    "status": status,
                    "error": None,
                    "startedAt": 0,
                    "completedAt": 1 if status != "inProgress" else None,
                    "durationMs": 1 if status != "inProgress" else None,
                },
            },
        }

    def _patch_app_server_client(self, fake_client: FakeRunDaemonClient) -> None:
        original_client = self.core.app_server.AppServerClient

        def fake_factory(*_args: object, **_kwargs: object) -> FakeRunDaemonClient:
            return fake_client

        self.addCleanup(setattr, self.core.app_server, "AppServerClient", original_client)
        self.core.app_server.AppServerClient = fake_factory

    def _patch_daemon_communication(self) -> dict[str, list[object]]:
        original_start_mailbox = self.core.start_daemon_mailbox
        original_register = self.core.register_daemon_actor
        original_heartbeat = self.core.heartbeat_daemon_actor
        original_unregister = self.core.unregister_daemon_actor
        calls: dict[str, list[object]] = {
            "mailbox_started": [],
            "mailbox_closed": [],
            "registered": [],
            "heartbeat": [],
            "unregistered": [],
        }

        class FakeMailbox:
            def close(self) -> None:
                calls["mailbox_closed"].append(True)

        def fake_start_mailbox(**kwargs: object) -> FakeMailbox:
            calls["mailbox_started"].append(kwargs)
            return FakeMailbox()

        def fake_register(context: object, identity_route: dict[str, str]) -> dict[str, object]:
            calls["registered"].append(dict(identity_route))
            return {"record": {"identity_id": identity_route["identity_id"], "role_id": identity_route["role_id"]}}

        def fake_heartbeat(context: object, identity_route: dict[str, str]) -> dict[str, object]:
            calls["heartbeat"].append(dict(identity_route))
            return {"record": {"identity_id": identity_route["identity_id"], "role_id": identity_route["role_id"]}}

        def fake_unregister(context: object, identity_route: dict[str, str]) -> dict[str, object]:
            calls["unregistered"].append(dict(identity_route))
            return {"record": {"identity_id": identity_route["identity_id"], "role_id": identity_route["role_id"]}}

        self.addCleanup(setattr, self.core, "start_daemon_mailbox", original_start_mailbox)
        self.addCleanup(setattr, self.core, "register_daemon_actor", original_register)
        self.addCleanup(setattr, self.core, "heartbeat_daemon_actor", original_heartbeat)
        self.addCleanup(setattr, self.core, "unregister_daemon_actor", original_unregister)
        self.core.start_daemon_mailbox = fake_start_mailbox
        self.core.register_daemon_actor = fake_register
        self.core.heartbeat_daemon_actor = fake_heartbeat
        self.core.unregister_daemon_actor = fake_unregister
        return calls

    def test_run_daemon_binds_shared_state_root_before_handlers_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            wrong_root = Path(temp_root) / "wrong-state"
            os.environ.pop("BUDDYSWITCH_SHARED_ROOT", None)
            os.environ["BUDDYSWITCH_STATE_ROOT"] = str(wrong_root)
            runtime_files.refresh_runtime_roots_from_env()

            fake_client = FakeRunDaemonClient(notifications=[StopDaemonLoop("stop")])
            self._patch_app_server_client(fake_client)
            communication = self._patch_daemon_communication()
            observed_roots: list[Path] = []
            fake_start_mailbox = self.core.start_daemon_mailbox

            def observing_start_mailbox(**kwargs: object) -> object:
                observed_roots.append(runtime_files.STATE_ROOT)
                return fake_start_mailbox(**kwargs)

            self.core.start_daemon_mailbox = observing_start_mailbox

            with self.assertRaises(StopDaemonLoop):
                self.core.run_daemon(instance["instance_json"], handlers=[])

            expected_state_root = Path(temp_root) / "state"
            expected_resolved_state_root = expected_state_root.resolve(strict=False)
            self.assertEqual(os.environ["BUDDYSWITCH_STATE_ROOT"], str(expected_state_root))
            self.assertEqual(runtime_files.STATE_ROOT, expected_resolved_state_root)
            self.assertEqual(observed_roots, [expected_resolved_state_root])
            self.assertEqual(len(communication["mailbox_closed"]), 1)

    def test_run_daemon_ensures_actor_identity_profile_before_registering_reachability(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            fake_client = FakeRunDaemonClient(notifications=[StopDaemonLoop("stop")])
            self._patch_app_server_client(fake_client)
            communication = self._patch_daemon_communication()
            observed_profile_at_register: list[dict[str, object] | None] = []
            fake_register = self.core.register_daemon_actor

            def observing_register(context: object, identity_route: dict[str, str]) -> dict[str, object]:
                observed_profile_at_register.append(identity_repo.get_actor_identity_profile(identity_route["identity_id"]))
                return fake_register(context, identity_route)

            self.core.register_daemon_actor = observing_register

            with self.assertRaises(StopDaemonLoop):
                self.core.run_daemon(instance["instance_json"], handlers=[])

            profile = identity_repo.get_actor_identity_profile("act-dev-daed00000001")
            self.assertEqual(
                profile,
                {"identity": {"id": "act-dev-daed00000001", "type": "actor"}, "role_id": "dev"},
            )
            self.assertEqual(observed_profile_at_register, [profile])
            self.assertEqual(len(communication["mailbox_closed"]), 1)

    def test_run_daemon_rejects_conflicting_existing_actor_identity_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            os.environ["BUDDYSWITCH_SHARED_ROOT"] = str(Path(temp_root))
            os.environ["BUDDYSWITCH_STATE_ROOT"] = str(Path(temp_root) / "state")
            os.environ["BUDDYSWITCH_ACTOR_ID"] = "act-dev-daed00000001"
            runtime_files.refresh_runtime_roots_from_env()
            identity_repo.save_actor_identity_profile(
                {"identity": {"id": "act-dev-daed00000001", "type": "actor"}, "role_id": "pm"}
            )
            fake_client = FakeRunDaemonClient(notifications=[])
            self._patch_app_server_client(fake_client)
            communication = self._patch_daemon_communication()

            with self.assertRaisesRegex(ValueError, "actor identity profile role mismatch"):
                self.core.run_daemon(instance["instance_json"], handlers=[])

            self.assertEqual(communication["registered"], [])

    def test_run_daemon_continues_after_notification_idle_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            handler = RecordingHandler(name="recording", result=daemon_contracts.HandlerResult.ignored())
            fake_client = FakeRunDaemonClient(
                notifications=[
                    self.core.app_server.AppServerTimeoutError("idle"),
                    self._completed(turn_id="turn-user-1"),
                    StopDaemonLoop("stop"),
                ],
            )
            self._patch_app_server_client(fake_client)
            communication = self._patch_daemon_communication()

            with self.assertRaises(StopDaemonLoop):
                self.core.run_daemon(instance["instance_json"], handlers=[handler])

            self.assertEqual([request["method"] for request in fake_client.requests], ["thread/resume"])
            self.assertEqual([trigger.type for trigger in handler.triggers], ["app_server.turn_completed"])
            self.assertEqual([trigger.origin_id for trigger in handler.triggers], ["turn-user-1"])
            self.assertEqual(len(communication["mailbox_started"]), 1)
            self.assertEqual(len(communication["heartbeat"]), 1)
            self.assertEqual(len(communication["unregistered"]), 1)
            self.assertEqual(len(communication["mailbox_closed"]), 1)
            state = json.loads(daemon_state.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIsNone(state["last_error"])

    def test_run_daemon_sweeps_due_schedules_on_app_server_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            fake_client = FakeRunDaemonClient(
                notifications=[
                    self.core.app_server.AppServerTimeoutError("idle"),
                    StopDaemonLoop("stop"),
                ],
            )
            self._patch_app_server_client(fake_client)
            self._patch_daemon_communication()
            original_sweep = self.core.sweep_due_scheduled_triggers
            sweep_calls: list[dict[str, object]] = []

            def fake_sweep(context: object, state: object, runtime: object, handlers: object) -> dict[str, object]:
                sweep_calls.append(
                    {
                        "actor_id": getattr(context, "actor_id"),
                        "state": state,
                        "runtime": runtime,
                        "handlers": handlers,
                    }
                )
                return {"swept_count": 0, "delivered_count": 0, "failed_count": 0, "schedules": []}

            self.addCleanup(setattr, self.core, "sweep_due_scheduled_triggers", original_sweep)
            self.core.sweep_due_scheduled_triggers = fake_sweep

            with self.assertRaises(StopDaemonLoop):
                self.core.run_daemon(instance["instance_json"], handlers=[])

            self.assertEqual(len(sweep_calls), 1)
            self.assertEqual(sweep_calls[0]["actor_id"], "act-dev-daed00000001")

    def test_run_daemon_sweeps_due_schedules_after_notification_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            order: list[str] = []

            class OrderedHandler:
                name = "ordered"

                def handles(self, trigger: object) -> bool:
                    return getattr(trigger, "type", None) == "app_server.turn_completed"

                def handle(self, context: object, state: object, runtime: object, trigger: object) -> object:
                    del context, state, runtime, trigger
                    order.append("handler")
                    return daemon_contracts.HandlerResult.handled()

            self_core = self.core
            handler = OrderedHandler()
            fake_client = FakeRunDaemonClient(
                notifications=[
                    self._completed(turn_id="turn-user-1"),
                    StopDaemonLoop("stop"),
                ],
            )
            self._patch_app_server_client(fake_client)
            self._patch_daemon_communication()
            original_sweep = self.core.sweep_due_scheduled_triggers

            def fake_sweep(context: object, state: object, runtime: object, handlers: object) -> dict[str, object]:
                del context, state, runtime, handlers
                order.append("sweep")
                return {"swept_count": 0, "delivered_count": 0, "failed_count": 0, "schedules": []}

            self.addCleanup(setattr, self.core, "sweep_due_scheduled_triggers", original_sweep)
            self.core.sweep_due_scheduled_triggers = fake_sweep

            with self.assertRaises(StopDaemonLoop):
                self.core.run_daemon(instance["instance_json"], handlers=[handler])

            self.assertEqual(order, ["handler", "sweep"])
            state_payload = json.loads(daemon_state.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIn("scheduled_triggers", state_payload)
            self.assertNotIn("browser", state_payload)

    def test_run_daemon_records_fatal_app_server_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            fake_client = FakeRunDaemonClient(
                notifications=[self.core.app_server.AppServerUnavailableError("socket gone")],
            )
            self._patch_app_server_client(fake_client)
            self._patch_daemon_communication()

            result = self.core.run_daemon(instance["instance_json"], handlers=[])

            self.assertEqual(result, 1)
            state = json.loads(daemon_state.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIsNone(state["last_error"]["origin_turn_id"])
            self.assertIn("socket gone", state["last_error"]["message"])

    def test_run_daemon_records_handler_exception_and_continues_to_later_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            exploding = ExplodingOnceHandler(result=daemon_contracts.HandlerResult.ignored())
            recorder = RecordingHandler(name="recorder", result=daemon_contracts.HandlerResult.ignored())
            notification_one = self._completed(turn_id="turn-user-1")
            notification_two = self._completed(turn_id="turn-user-2")
            fake_client = FakeRunDaemonClient(
                notifications=[
                    notification_one,
                    notification_two,
                    StopDaemonLoop("stop"),
                ],
            )
            self._patch_app_server_client(fake_client)
            self._patch_daemon_communication()

            with self.assertRaises(StopDaemonLoop):
                self.core.run_daemon(instance["instance_json"], handlers=[exploding, recorder])

            self.assertEqual(exploding.calls, 2)
            self.assertEqual([trigger.origin_id for trigger in recorder.triggers], ["turn-user-1", "turn-user-2"])
            state = json.loads(daemon_state.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIsNone(state["last_error"])
            self.assertEqual(state["handlers"]["exploder"]["last_error"]["origin_turn_id"], "turn-user-1")
            self.assertEqual(state["handlers"]["exploder"]["last_error"]["message"], "handler exploded")

    def test_run_daemon_calls_multiple_handlers_in_explicit_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            seen: list[tuple[str, str]] = []
            notification = self._completed(turn_id="turn-user-1")
            result = daemon_contracts.HandlerResult.ignored()

            class OrderedHandler:
                def __init__(self, name: str) -> None:
                    self.name = name

                def handles(self, trigger_payload: object) -> bool:
                    return getattr(trigger_payload, "type", None) == "app_server.turn_completed"

                def handle(
                    self,
                    context: object,
                    state: object,
                    runtime: object,
                    trigger_payload: object,
                ) -> object:
                    del context, state, runtime
                    source_context = getattr(trigger_payload, "source_context")
                    turn = source_context["turn_id"]
                    assert isinstance(turn, str)
                    seen.append((self.name, turn))
                    return result

            fake_client = FakeRunDaemonClient(
                notifications=[
                    notification,
                    StopDaemonLoop("stop"),
                ],
            )
            self._patch_app_server_client(fake_client)
            self._patch_daemon_communication()

            with self.assertRaises(StopDaemonLoop):
                self.core.run_daemon(
                    instance["instance_json"],
                    handlers=[OrderedHandler("one"), OrderedHandler("two")],
                )

            self.assertEqual(seen, [("one", "turn-user-1"), ("two", "turn-user-1")])

