#!/usr/bin/env python3
"""Tests for daemon core state, lifecycle, and run loop."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from itertools import count
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

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
)


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
        self._saved_runtime_env = {key: os.environ.get(key) for key in RUNTIME_ENV_KEYS}
        self.addCleanup(self._restore_runtime_env, self._saved_runtime_env)
        self.core = load_daemon_core()

    def _restore_runtime_env(self, values: dict[str, str | None]) -> None:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        runtime_files.reset_runtime_root_override()
        runtime_files.refresh_runtime_roots_from_env()


class DaemonCoreStateTests(DaemonCoreTestCase):
    def _instance_root(self, temp_root: str) -> Path:
        root = Path(temp_root) / "instances" / "act-dev-daed00000001"
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
                        "actor_id": "act-dev-daed00000001",
                        "role": "dev",
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
                {"role_id": "dev", "actor_id": "act-dev-daed00000001"},
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
                        "actor_id": "act-dev-daed00000001",
                        "role": "dev",
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

            self.assertEqual(actor_address.to_payload(), {"role_id": "dev", "actor_id": "act-dev-daed00000001"})
            self.assertNotIn("to_role", self.core.register_daemon_actor.__code__.co_varnames)

    def test_missing_state_initializes_empty_valid_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)

            state = self.core.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-daed00000001",
                main_thread_id="thr-main",
            )

            self.assertEqual(state.payload["actor_id"], "act-dev-daed00000001")
            self.assertEqual(state.payload["main_thread_id"], "thr-main")
            self.assertEqual(state.payload["daemon_origin_turn_ids"], [])
            self.assertEqual(state.payload["daemon_runtime_call_ids"], [])
            self.assertEqual(state.payload["daemon_runtime_calls"], {})
            self.assertNotIn("daemon_" + "action_ids", state.payload)
            self.assertNotIn("daemon_" + "actions", state.payload)
            self.assertEqual(state.payload["handlers"], {})
            self.assertIsNone(state.payload["ready"])
            self.assertIsNone(state.payload["last_error"])

    def test_recording_daemon_origin_turn_persists_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-daed00000001",
                main_thread_id="thr-main",
            )

            state.record_daemon_origin_turn(
                "turn-daemon-1",
                handler_name="example_handler",
                origin_turn_id="msg-1",
            )

            saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["daemon_origin_turn_ids"], ["turn-daemon-1"])
            self.assertEqual(saved["daemon_origin_turns"]["turn-daemon-1"]["handler_name"], "example_handler")
            self.assertEqual(saved["daemon_origin_turns"]["turn-daemon-1"]["origin_turn_id"], "msg-1")
            self.assertEqual(saved["daemon_origin_turns"]["turn-daemon-1"]["turn_id"], "turn-daemon-1")
            self.assertRegex(saved["daemon_origin_turns"]["turn-daemon-1"]["created_at"], r"^\d{4}-\d{2}-\d{2}T")
            self.assertEqual(state.daemon_turn_record("turn-daemon-1")["handler_name"], "example_handler")
            self.assertTrue(state.is_daemon_origin_turn("turn-daemon-1"))
            self.assertTrue(state.is_daemon_origin_turn_from("turn-daemon-1", "example_handler"))
            self.assertFalse(state.is_daemon_origin_turn_from("turn-daemon-1", "task_checkout"))
            self.assertFalse(state.is_daemon_origin_turn("turn-user-1"))
            self.assertNotIn("last_origin_turn_id", saved)
            self.assertNotIn("last_stop_tui_turn_id", saved)

    def test_legacy_daemon_origin_without_provenance_is_only_task_checkout_filtered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-daed00000001",
                main_thread_id="thr-main",
            )

            state.record_daemon_origin_turn("turn-legacy-1")

            self.assertTrue(state.is_daemon_origin_turn("turn-legacy-1"))
            self.assertIsNone(state.daemon_turn_record("turn-legacy-1"))
            self.assertTrue(state.is_daemon_origin_turn_from("turn-legacy-1", "task_checkout"))
            self.assertFalse(state.is_daemon_origin_turn_from("turn-legacy-1", "example_handler"))

    def test_daemon_origin_turn_ids_keep_latest_50(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-daed00000001",
                main_thread_id="thr-main",
            )

            for index in range(55):
                state.record_daemon_origin_turn(
                    f"turn-daemon-{index}",
                    handler_name="task_checkout",
                    origin_turn_id=f"turn-user-{index}",
                )

            saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(len(saved["daemon_origin_turn_ids"]), 50)
            self.assertEqual(saved["daemon_origin_turn_ids"][0], "turn-daemon-5")
            self.assertEqual(saved["daemon_origin_turn_ids"][-1], "turn-daemon-54")
            self.assertEqual(len(saved["daemon_origin_turns"]), 50)
            self.assertNotIn("turn-daemon-4", saved["daemon_origin_turns"])
            self.assertEqual(saved["daemon_origin_turns"]["turn-daemon-54"]["handler_name"], "task_checkout")

    def test_recording_error_persists_last_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-daed00000001",
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
                actor_id="act-dev-daed00000001",
                main_thread_id="thr-main",
            )

            state.update_handler_state(
                "task_checkout",
                {
                    "last_origin_turn_id": "turn-user-1",
                    "last_runtime_turn_id": "turn-daemon-1",
                },
            )

            saved = json.loads(self.core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(
                saved["handlers"]["task_checkout"],
                {
                    "last_origin_turn_id": "turn-user-1",
                    "last_runtime_turn_id": "turn-daemon-1",
                },
            )
            self.assertEqual(
                state.handler_state("task_checkout"),
                {
                    "last_origin_turn_id": "turn-user-1",
                    "last_runtime_turn_id": "turn-daemon-1",
                },
            )

    def test_handler_registration_state_initializes_observability_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance_root,
                actor_id="act-dev-daed00000001",
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
                actor_id="act-dev-daed00000001",
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
                actor_id="act-dev-daed00000001",
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
                actor_id="act-dev-daed00000001",
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

    def test_derive_daemon_runtime_env_projects_shared_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = self.core.load_daemon_context(instance["instance_json"])

            env = self.core.derive_daemon_runtime_env(context)

            shared_root = Path(temp_root)
            self.assertEqual(
                env,
                {
                    "BUDDYSWITCH_SHARED_ROOT": str(shared_root),
                    "BUDDYSWITCH_STATE_ROOT": str(shared_root / "state"),
                    "BUDDYSWITCH_INSTANCE_ROOT": str(instance["instance_root"]),
                    "BUDDYSWITCH_INSTANCE_JSON": str(instance["instance_json"]),
                    "BUDDYSWITCH_WORKSPACE_DIR": str(instance["workspace_dir"]),
                },
            )


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
                state = self.core.DaemonState.load(
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
        self.addCleanup(setattr, self.core, "_pid_is_live", original_pid_is_live)
        self.core._pid_is_live = lambda pid: pid in live_pids

    def test_start_daemon_creates_runtime_files_and_is_idempotent_when_pid_is_live(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            commands, _popen_kwargs = self._patch_process_start([4321])
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
            commands, _popen_kwargs = self._patch_process_start([4325])
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
            self.assertEqual(unregistered[0]["actor_address"], {"role_id": "dev", "actor_id": "act-dev-daed00000001"})
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
                actor_id="act-dev-daed00000001",
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

    def test_daemon_status_reports_recent_runtime_call_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self.core.DaemonState.load(
                instance_root=instance["instance_root"],
                actor_id="act-dev-daed00000001",
                main_thread_id="thr-main",
            )
            record = state.record_runtime_call(
                handler_name="example_handler",
                origin_id="msg-1",
                runtime_method="side_start",
                parent_thread_id="thr-main",
                side_thread_id="thr-side-1",
                turn_id="turn-side-1",
                status="succeeded",
            )

            payload = self.core.daemon_status(instance["instance_json"])

            self.assertNotIn("actions", payload)
            self.assertEqual(payload["runtime"]["ids"], [record["runtime_call_id"]])
            self.assertEqual(payload["runtime"]["items"][record["runtime_call_id"]]["runtime_method"], "side_start")
            self.assertEqual(payload["runtime"]["items"][record["runtime_call_id"]]["side_thread_id"], "thr-side-1")
            self.assertEqual(payload["runtime"]["items"][record["runtime_call_id"]]["origin_id"], "msg-1")

    def test_daemon_status_reports_registered_handler_observability(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)

            class FakeHandler:
                name = "task_checkout"

            payload = self.core.daemon_status(
                instance["instance_json"],
                handlers=[FakeHandler(), type("FakeMessageHandler", (), {"name": "example_handler"})()],
            )

            self.assertEqual(payload["handlers"]["registered"], ["task_checkout", "example_handler"])
            item = payload["handlers"]["items"]["task_checkout"]
            self.assertIs(item["registered"], True)
            self.assertIs(item["enabled"], True)
            self.assertIs(item["active"], True)
            self.assertIsNone(item["last_result"])
            self.assertIsNone(item["last_error"])
            self.assertIsNone(item["last_runtime_turn_id"])
            self.assertNotIn("last_" + "action" + "_turn_id", item)
            self.assertNotIn("mailbox_handlers", payload)
            mailbox_item = payload["handlers"]["items"]["example_handler"]
            self.assertIs(mailbox_item["registered"], True)
            self.assertIs(mailbox_item["enabled"], True)
            self.assertIs(mailbox_item["active"], True)
            self.assertIsNone(mailbox_item["last_result"])
            self.assertIsNone(mailbox_item["last_error"])
            self.assertIsNone(mailbox_item["last_runtime_turn_id"])
            self.assertNotIn("last_" + "action" + "_turn_id", mailbox_item)

    def test_daemon_status_includes_persisted_unregistered_handler_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = self.core.DaemonState.load(
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
                name = "task_checkout"

            payload = self.core.daemon_status(
                instance["instance_json"],
                handlers=[FakeHandler(), type("FakeMessageHandler", (), {"name": "example_handler"})()],
            )

            self.assertEqual(payload["handlers"]["registered"], ["task_checkout", "example_handler"])
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

    def test_run_daemon_binds_shared_state_root_before_handlers_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            wrong_root = Path(temp_root) / "wrong-state"
            runtime_files.reset_runtime_root_override()
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
            self.assertEqual([trigger.type for trigger in handler.triggers], ["app_server.turn_completed"])
            self.assertEqual([trigger.origin_id for trigger in handler.triggers], ["turn-user-1"])
            self.assertEqual(len(communication["mailbox_started"]), 1)
            self.assertEqual(len(communication["heartbeat"]), 1)
            self.assertEqual(len(communication["unregistered"]), 1)
            self.assertEqual(len(communication["mailbox_closed"]), 1)
            state = json.loads(self.core.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
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
            self.assertEqual([trigger.origin_id for trigger in recorder.triggers], ["turn-user-1", "turn-user-2"])
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


if __name__ == "__main__":
    unittest.main()
