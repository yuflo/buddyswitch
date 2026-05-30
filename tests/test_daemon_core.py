#!/usr/bin/env python3
"""Tests for daemon core state, lifecycle, and run loop."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DAEMON_CORE_PATH = ROOT / "tools" / "launcher" / "daemon_core.py"
INSTANCE_DAEMON_PATH = ROOT / "tools" / "launcher" / "instance_daemon.py"
MODULE_COUNTER = count()


def load_daemon_core() -> Any:
    if not DAEMON_CORE_PATH.exists():
        raise AssertionError(f"expected daemon core module to exist: {DAEMON_CORE_PATH}")
    module_name = f"buddyswitch_daemon_core_{next(MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, DAEMON_CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {DAEMON_CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StopDaemonLoop(RuntimeError):
    pass


class DaemonCoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.core = load_daemon_core()


class DaemonCoreStateTests(DaemonCoreTestCase):
    def _instance_root(self, temp_root: str) -> Path:
        root = Path(temp_root) / "instances" / "inst-dev-daed00000001"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def test_daemon_registration_projects_actor_address_and_registry_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            workspace_dir = instance_root / "workspace"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            instance_json = instance_root / "instance.json"
            instance_json.write_text(
                json.dumps(
                    {
                        "instance_id": "inst-dev-daed00000001",
                        "buddy": "dev",
                        "status": "active",
                        "instance_root": str(instance_root),
                        "workspace_dir": str(workspace_dir),
                        "thread_id": "thr-main",
                        "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
                    },
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )
            context = self.core.load_daemon_context(instance_json)
            actor_address = self.core.actor_address_for_context(context)
            calls: list[dict[str, Any]] = []
            original_register = self.core.daemon_client.register_actor

            def fake_register_actor(**kwargs: Any) -> dict[str, Any]:
                calls.append(kwargs)
                return {"record": {"actor_address": kwargs["actor_address"], "endpoint": kwargs["endpoint"]}}

            self.addCleanup(setattr, self.core.daemon_client, "register_actor", original_register)
            self.core.daemon_client.register_actor = fake_register_actor

            row = self.core.register_daemon_actor(context, actor_address)["record"]

            self.assertEqual(
                row["actor_address"],
                {"buddy_id": "dev", "instance_id": "inst-dev-daed00000001"},
            )
            self.assertEqual(row["endpoint"]["kind"], "daemon_mailbox_socket")
            self.assertEqual(row["endpoint"]["socket_path"], str(self.core.daemon_mailbox.mailbox_socket_path(context.instance_root)))
            self.assertEqual(calls[0]["heartbeat"], {"kind": "central_daemon_rpc"})
            self.assertEqual(calls[0]["socket_path"], self.core.central_daemon_socket_path(context))

    def test_daemon_reachability_client_uses_explicit_actor_address(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            workspace_dir = instance_root / "workspace"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            instance_json = instance_root / "instance.json"
            instance_json.write_text(
                json.dumps(
                    {
                        "instance_id": "inst-dev-daed00000001",
                        "buddy": "dev",
                        "status": "active",
                        "instance_root": str(instance_root),
                        "workspace_dir": str(workspace_dir),
                        "thread_id": "thr-main",
                        "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
                    },
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )
            context = self.core.load_daemon_context(instance_json)
            actor_address = self.core.actor_address_for_context(context)

            self.assertEqual(actor_address.to_payload(), {"buddy_id": "dev", "instance_id": "inst-dev-daed00000001"})
            self.assertNotIn("to_buddy", self.core.register_daemon_actor.__code__.co_varnames)

    def test_missing_state_initializes_empty_valid_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)

            state = self.core.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daed00000001",
                main_thread_id="thr-main",
            )

            self.assertEqual(state.payload["instance_id"], "inst-dev-daed00000001")
            self.assertEqual(state.payload["main_thread_id"], "thr-main")
            self.assertEqual(state.payload["daemon_origin_turn_ids"], [])
            self.assertEqual(state.payload["handlers"], {})
            self.assertIsNone(state.payload["ready"])
            self.assertIsNone(state.payload["last_error"])

    def test_recording_daemon_origin_turn_persists_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daed00000001",
                main_thread_id="thr-main",
            )

            state.record_daemon_origin_turn("turn-daemon-1")

            saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["daemon_origin_turn_ids"], ["turn-daemon-1"])
            self.assertTrue(state.is_daemon_origin_turn("turn-daemon-1"))
            self.assertFalse(state.is_daemon_origin_turn("turn-user-1"))
            self.assertNotIn("last_origin_turn_id", saved)
            self.assertNotIn("last_stop_tui_turn_id", saved)

    def test_daemon_origin_turn_ids_keep_latest_50(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daed00000001",
                main_thread_id="thr-main",
            )

            for index in range(55):
                state.record_daemon_origin_turn(f"turn-daemon-{index}")

            saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(len(saved["daemon_origin_turn_ids"]), 50)
            self.assertEqual(saved["daemon_origin_turn_ids"][0], "turn-daemon-5")
            self.assertEqual(saved["daemon_origin_turn_ids"][-1], "turn-daemon-54")

    def test_recording_error_persists_last_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daed00000001",
                main_thread_id="thr-main",
            )

            state.record_error(origin_turn_id=None, message="socket gone")

            saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertIsNone(saved["last_error"]["origin_turn_id"])
            self.assertEqual(saved["last_error"]["message"], "socket gone")
            self.assertRegex(saved["last_error"]["at"], r"^\d{4}-\d{2}-\d{2}T")

    def test_handler_state_updates_persist_under_handlers_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daed00000001",
                main_thread_id="thr-main",
            )

            state.update_handler_state(
                "task_checkout",
                {
                    "last_origin_turn_id": "turn-user-1",
                    "last_action_turn_id": "turn-daemon-1",
                },
            )

            saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(
                saved["handlers"]["task_checkout"],
                {
                    "last_origin_turn_id": "turn-user-1",
                    "last_action_turn_id": "turn-daemon-1",
                },
            )
            self.assertEqual(
                state.handler_state("task_checkout"),
                {
                    "last_origin_turn_id": "turn-user-1",
                    "last_action_turn_id": "turn-daemon-1",
                },
            )

    def test_handler_registration_state_initializes_observability_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daed00000001",
                main_thread_id="thr-main",
            )

            state.register_handlers(["task_checkout", "fake"])

            saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            for handler_name in ("task_checkout", "fake"):
                handler_state = saved["handlers"][handler_name]
                self.assertIs(handler_state["registered"], True)
                self.assertIs(handler_state["enabled"], True)
                self.assertIs(handler_state["active"], True)
                self.assertIsNone(handler_state["last_result"])
                self.assertIsNone(handler_state["last_error"])

    def test_record_handler_error_persists_under_handlers_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daed00000001",
                main_thread_id="thr-main",
            )

            state.record_handler_error("task_checkout", origin_turn_id="turn-user-1", message="turn/start failed")

            saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["handlers"]["task_checkout"]["last_error"]["origin_turn_id"], "turn-user-1")
            self.assertEqual(saved["handlers"]["task_checkout"]["last_error"]["message"], "turn/start failed")
            self.assertRegex(saved["handlers"]["task_checkout"]["last_error"]["at"], r"^\d{4}-\d{2}-\d{2}T")

    def test_recording_ready_state_persists_pid_and_main_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daed00000001",
                main_thread_id="thr-main",
            )

            state.record_ready(pid=4321, main_thread_id="thr-main")

            saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["ready"]["pid"], 4321)
            self.assertEqual(saved["ready"]["main_thread_id"], "thr-main")
            self.assertRegex(saved["ready"]["at"], r"^\d{4}-\d{2}-\d{2}T")

    def test_ready_for_rejects_other_pid_or_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daed00000001",
                main_thread_id="thr-main",
            )
            state.record_ready(pid=4321, main_thread_id="thr-main")

            self.assertTrue(state.ready_for(4321, "thr-main"))
            self.assertFalse(state.ready_for(9999, "thr-main"))
            self.assertFalse(state.ready_for(4321, "thr-other"))


class FakeBindingClient:
    def __init__(self, *, result: dict[str, object] | None = None, error: BaseException | None = None) -> None:
        self.result = result or {"thread": {"id": "thr-main"}}
        self.error = error
        self.requests: list[dict[str, object]] = []

    def request(self, method: str, params: dict[str, object] | None) -> dict[str, object]:
        self.requests.append({"method": method, "params": params or {}})
        if self.error is not None:
            raise self.error
        return self.result


class DaemonCoreBindingTests(DaemonCoreTestCase):
    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "inst-dev-daed00000001"
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload: dict[str, Any] = {
            "instance_id": "inst-dev-daed00000001",
            "buddy": "dev",
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(workspace_dir),
            "thread_id": "thr-main",
            "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
        }
        instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        return {
            "instance_root": instance_root,
            "workspace_dir": workspace_dir,
            "instance_json": instance_json,
            "payload": payload,
        }

    def test_bind_main_thread_uses_thread_resume_for_current_instance_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            client = FakeBindingClient()

            self.core.bind_main_thread(context, client)

            self.assertEqual([request["method"] for request in client.requests], ["thread/resume"])
            params = client.requests[0]["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["threadId"], "thr-main")
            self.assertEqual(params["cwd"], str(instance["workspace_dir"]))
            self.assertEqual(
                params["runtimeWorkspaceRoots"],
                [
                    str(instance["workspace_dir"]),
                    str(Path(temp_root) / "project" / "workspace"),
                ],
            )
            self.assertEqual(params["permissions"], "buddyswitch-runtime")
            self.assertEqual(params["excludeTurns"], True)

    def test_bind_main_thread_fails_on_wrong_resumed_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])
            client = FakeBindingClient(result={"thread": {"id": "thr-other"}})

            with self.assertRaises(self.core.app_server.AppServerProtocolError):
                self.core.bind_main_thread(context, client)


class DaemonCoreLifecycleTests(DaemonCoreTestCase):
    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "inst-dev-daed00000001"
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload = {
            "instance_id": "inst-dev-daed00000001",
            "buddy": "dev",
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(instance_root / "workspace"),
            "thread_id": "thr-main",
            "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
        }
        instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        return {"instance_root": instance_root, "instance_json": instance_json}

    def _patch_process_start(self, pids: list[int]) -> list[list[str]]:
        commands: list[list[str]] = []
        original_popen = self.core.subprocess.Popen

        class FakeProcess:
            def __init__(self, pid: int) -> None:
                self.pid = pid

            def poll(self) -> None:
                return None

        def fake_popen(command: list[str], **_kwargs: object) -> FakeProcess:
            commands.append(command)
            return FakeProcess(pids.pop(0))

        self.addCleanup(setattr, self.core.subprocess, "Popen", original_popen)
        self.core.subprocess.Popen = fake_popen
        return commands

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
                state = self.core.DaemonState.load(
                    instance_root=instance_root,
                    instance_id="inst-dev-daed00000001",
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
        self.addCleanup(setattr, self.core, "_pid_is_live", original_pid_is_live)
        self.core._pid_is_live = lambda pid: pid in live_pids

    def test_start_daemon_creates_runtime_files_and_is_idempotent_when_pid_is_live(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            commands = self._patch_process_start([4321])
            self._patch_pid_live({4321})
            self._patch_sleep_to_record_ready(instance_root=instance["instance_root"], pid=4321)

            first = self.core.start_daemon(instance["instance_json"])
            second = self.core.start_daemon(instance["instance_json"])

            self.assertTrue(first["started"])
            self.assertFalse(second["started"])
            self.assertEqual(first["pid"], 4321)
            self.assertEqual(second["pid"], 4321)
            self.assertTrue(first["ready"])
            self.assertTrue(second["ready"])
            self.assertEqual(len(commands), 1)
            self.assertEqual(commands[0][0], self.core.sys.executable)
            self.assertEqual(Path(commands[0][1]).resolve(), INSTANCE_DAEMON_PATH.resolve())
            self.assertEqual(commands[0][2:], ["run", "--instance-json", str(instance["instance_json"])])
            self.assertTrue(self.core.daemon_pid_file(instance["instance_root"]).exists())
            self.assertTrue(self.core.daemon_log_file(instance["instance_root"]).exists())
            self.assertTrue(self.core.daemon_state_file(instance["instance_root"]).exists())

    def test_start_daemon_replaces_stale_pid_before_starting_new_daemon(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            self.core.daemon_pid_file(instance["instance_root"]).parent.mkdir(parents=True, exist_ok=True)
            self.core.daemon_pid_file(instance["instance_root"]).write_text("9999\n", encoding="utf-8")
            commands = self._patch_process_start([4322])
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
            original_terminate = self.core._terminate_pid
            terminated: list[int] = []
            self.addCleanup(setattr, self.core, "_terminate_pid", original_terminate)
            self.core._terminate_pid = lambda pid: terminated.append(pid) or True

            with self.assertRaises(RuntimeError):
                self.core.start_daemon(instance["instance_json"])

            self.assertEqual(terminated, [4324])
            self.assertFalse(self.core.daemon_pid_file(instance["instance_root"]).exists())

    def test_start_daemon_replaces_live_unready_pid_before_starting_new_daemon(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            self.core.daemon_pid_file(instance["instance_root"]).parent.mkdir(parents=True, exist_ok=True)
            self.core.daemon_pid_file(instance["instance_root"]).write_text("9999\n", encoding="utf-8")
            commands = self._patch_process_start([4325])
            self._patch_pid_live({9999, 4325})
            self._patch_sleep_to_record_ready(instance_root=instance["instance_root"], pid=4325)
            original_terminate = self.core._terminate_pid
            terminated: list[int] = []
            self.addCleanup(setattr, self.core, "_terminate_pid", original_terminate)
            self.core._terminate_pid = lambda pid: terminated.append(pid) or True

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
            self.core.daemon_pid_file(instance["instance_root"]).write_text("4321\n", encoding="utf-8")
            terminated: list[int] = []
            self._patch_pid_live({4321})
            original_terminate = self.core._terminate_pid
            original_unregister = self.core.unregister_daemon_actor
            unregistered: list[dict[str, object]] = []
            self.addCleanup(setattr, self.core, "_terminate_pid", original_terminate)
            self.addCleanup(setattr, self.core, "unregister_daemon_actor", original_unregister)
            self.core._terminate_pid = lambda pid: terminated.append(pid) or True
            self.core.unregister_daemon_actor = lambda context, actor_address: unregistered.append(
                {"context": context, "actor_address": actor_address.to_payload()}
            ) or {"record": {"actor_address": actor_address.to_payload()}}

            payload = self.core.stop_daemon(instance["instance_json"])

            self.assertTrue(payload["terminated"])
            self.assertEqual(terminated, [4321])
            self.assertEqual(unregistered[0]["actor_address"], {"buddy_id": "dev", "instance_id": "inst-dev-daed00000001"})
            self.assertFalse(self.core.daemon_pid_file(instance["instance_root"]).exists())

    def test_stop_daemon_does_not_fail_when_central_unregister_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            self.core.daemon_pid_file(instance["instance_root"]).parent.mkdir(parents=True, exist_ok=True)
            self.core.daemon_pid_file(instance["instance_root"]).write_text("4321\n", encoding="utf-8")
            terminated: list[int] = []
            self._patch_pid_live({4321})
            original_terminate = self.core._terminate_pid
            original_unregister = self.core.unregister_daemon_actor
            self.addCleanup(setattr, self.core, "_terminate_pid", original_terminate)
            self.addCleanup(setattr, self.core, "unregister_daemon_actor", original_unregister)
            self.core._terminate_pid = lambda pid: terminated.append(pid) or True

            def fail_unregister(_context: object, _actor_address: object) -> dict[str, object]:
                raise RuntimeError("central daemon unavailable")

            self.core.unregister_daemon_actor = fail_unregister

            payload = self.core.stop_daemon(instance["instance_json"])

            self.assertTrue(payload["terminated"])
            self.assertEqual(payload["unregister_status"], "failed")
            self.assertIn("central daemon unavailable", payload["unregister_error"])
            self.assertEqual(terminated, [4321])
            self.assertFalse(self.core.daemon_pid_file(instance["instance_root"]).exists())
            state = json.loads(self.core.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIn("central daemon unavailable", state["last_error"]["message"])

    def test_daemon_status_reports_paths_live_state_and_last_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance["instance_root"],
                instance_id="inst-dev-daed00000001",
                main_thread_id="thr-main",
            )
            state.record_ready(pid=4321, main_thread_id="thr-main")
            state.record_error(origin_turn_id=None, message="socket gone")
            self.core.daemon_pid_file(instance["instance_root"]).write_text("4321\n", encoding="utf-8")
            self._patch_pid_live({4321})

            payload = self.core.daemon_status(instance["instance_json"])

            self.assertEqual(payload["pid"], 4321)
            self.assertTrue(payload["pid_live"])
            self.assertTrue(payload["live"])
            self.assertTrue(payload["ready"])
            self.assertEqual(payload["ready_main_thread_id"], "thr-main")
            self.assertEqual(payload["log_path"], str(self.core.daemon_log_file(instance["instance_root"])))
            self.assertEqual(payload["state_path"], str(self.core.daemon_state_file(instance["instance_root"])))
            self.assertIsNone(payload["last_error"]["origin_turn_id"])
            self.assertEqual(payload["last_error"]["message"], "socket gone")

    def test_daemon_status_reports_registered_handler_observability(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)

            class FakeHandler:
                name = "task_checkout"

            payload = self.core.daemon_status(instance["instance_json"], handlers=[FakeHandler()])

            self.assertEqual(payload["handlers"]["registered"], ["task_checkout"])
            item = payload["handlers"]["items"]["task_checkout"]
            self.assertIs(item["registered"], True)
            self.assertIs(item["enabled"], True)
            self.assertIs(item["active"], True)
            self.assertIsNone(item["last_result"])
            self.assertIsNone(item["last_error"])
            self.assertIsNone(item["last_action_turn_id"])

    def test_daemon_status_includes_persisted_unregistered_handler_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance["instance_root"],
                instance_id="inst-dev-daed00000001",
                main_thread_id="thr-main",
            )
            state.record_handler_error("message", origin_turn_id="turn-user-1", message="message failed")

            class FakeHandler:
                name = "task_checkout"

            payload = self.core.daemon_status(instance["instance_json"], handlers=[FakeHandler()])

            self.assertEqual(payload["handlers"]["registered"], ["task_checkout"])
            message_state = payload["handlers"]["items"]["message"]
            self.assertIs(message_state["registered"], False)
            self.assertIs(message_state["enabled"], False)
            self.assertIs(message_state["active"], False)
            self.assertEqual(message_state["last_error"]["message"], "message failed")


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
        self.notifications: list[dict[str, object]] = []

    def handle_notification(
        self,
        context: object,
        state: object,
        actions: object,
        notification: dict[str, object],
    ) -> object:
        self.notifications.append(notification)
        return self.result


class ExplodingOnceHandler:
    def __init__(self, *, result: object) -> None:
        self.name = "exploder"
        self.result = result
        self.calls = 0

    def handle_notification(
        self,
        context: object,
        state: object,
        actions: object,
        notification: dict[str, object],
    ) -> object:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("handler exploded")
        return self.result


class DaemonCoreRunLoopTests(DaemonCoreTestCase):
    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "inst-dev-daed00000001"
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload: dict[str, Any] = {
            "instance_id": "inst-dev-daed00000001",
            "buddy": "dev",
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

        def fake_register(context: object, actor_address: object) -> dict[str, object]:
            calls["registered"].append(getattr(actor_address, "to_payload")())
            return {"record": {"actor_address": getattr(actor_address, "to_payload")()}}

        def fake_heartbeat(context: object, actor_address: object) -> dict[str, object]:
            calls["heartbeat"].append(getattr(actor_address, "to_payload")())
            return {"record": {"actor_address": getattr(actor_address, "to_payload")()}}

        def fake_unregister(context: object, actor_address: object) -> dict[str, object]:
            calls["unregistered"].append(getattr(actor_address, "to_payload")())
            return {"record": {"actor_address": getattr(actor_address, "to_payload")()}}

        self.addCleanup(setattr, self.core, "start_daemon_mailbox", original_start_mailbox)
        self.addCleanup(setattr, self.core, "register_daemon_actor", original_register)
        self.addCleanup(setattr, self.core, "heartbeat_daemon_actor", original_heartbeat)
        self.addCleanup(setattr, self.core, "unregister_daemon_actor", original_unregister)
        self.core.start_daemon_mailbox = fake_start_mailbox
        self.core.register_daemon_actor = fake_register
        self.core.heartbeat_daemon_actor = fake_heartbeat
        self.core.unregister_daemon_actor = fake_unregister
        return calls

    def test_run_daemon_continues_after_notification_idle_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            handler = RecordingHandler(name="recording", result=self.core.HandlerResult.ignored())
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
            self.assertEqual(handler.notifications, [self._completed(turn_id="turn-user-1")])
            self.assertEqual(len(communication["mailbox_started"]), 1)
            self.assertEqual(len(communication["heartbeat"]), 1)
            self.assertEqual(len(communication["unregistered"]), 1)
            self.assertEqual(len(communication["mailbox_closed"]), 1)
            state = json.loads(self.core.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIsNone(state["last_error"])

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
            state = json.loads(self.core.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIsNone(state["last_error"]["origin_turn_id"])
            self.assertIn("socket gone", state["last_error"]["message"])

    def test_run_daemon_records_handler_exception_and_continues_to_later_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            exploding = ExplodingOnceHandler(result=self.core.HandlerResult.ignored())
            recorder = RecordingHandler(name="recorder", result=self.core.HandlerResult.ignored())
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
            self.assertEqual(recorder.notifications, [notification_one, notification_two])
            state = json.loads(self.core.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIsNone(state["last_error"])
            self.assertEqual(state["handlers"]["exploder"]["last_error"]["origin_turn_id"], "turn-user-1")
            self.assertEqual(state["handlers"]["exploder"]["last_error"]["message"], "handler exploded")

    def test_run_daemon_calls_multiple_handlers_in_explicit_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            seen: list[tuple[str, str]] = []
            notification = self._completed(turn_id="turn-user-1")
            result = self.core.HandlerResult.ignored()

            class OrderedHandler:
                def __init__(self, name: str) -> None:
                    self.name = name

                def handle_notification(
                    self,
                    context: object,
                    state: object,
                    actions: object,
                    notification_payload: dict[str, object],
                ) -> object:
                    turn = notification_payload["params"]["turn"]["id"]
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


if __name__ == "__main__":
    unittest.main()
