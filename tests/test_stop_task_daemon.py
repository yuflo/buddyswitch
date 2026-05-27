#!/usr/bin/env python3
"""Tests for the STOP Task TUI daemon."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from typing import Any
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DAEMON_PATH = ROOT / "tools" / "launcher" / "instance_daemon.py"
SPEC = importlib.util.spec_from_file_location("buddyswitch_instance_daemon", DAEMON_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load spec for {DAEMON_PATH}")
INSTANCE_DAEMON = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTANCE_DAEMON)


class StopTaskDaemonStateTests(unittest.TestCase):
    def _instance_root(self, temp_root: str) -> Path:
        root = Path(temp_root) / "instances" / "inst-dev-daemon"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def test_missing_state_initializes_empty_valid_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)

            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )

            self.assertEqual(state.payload["instance_id"], "inst-dev-daemon")
            self.assertEqual(state.payload["main_thread_id"], "thr-main")
            self.assertEqual(state.payload["daemon_origin_turn_ids"], [])
            self.assertIsNone(state.payload["last_error"])

    def test_recording_daemon_origin_turn_persists_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )

            state.record_stop_tui_turn(origin_turn_id="turn-user-1", stop_tui_turn_id="turn-daemon-1")

            saved = json.loads(INSTANCE_DAEMON.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["last_origin_turn_id"], "turn-user-1")
            self.assertEqual(saved["last_stop_tui_turn_id"], "turn-daemon-1")
            self.assertEqual(saved["daemon_origin_turn_ids"], ["turn-daemon-1"])
            self.assertTrue(state.is_daemon_origin_turn("turn-daemon-1"))
            self.assertFalse(state.is_daemon_origin_turn("turn-user-1"))

    def test_daemon_origin_turn_ids_keep_latest_50(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )

            for index in range(55):
                state.record_stop_tui_turn(origin_turn_id=f"turn-user-{index}", stop_tui_turn_id=f"turn-daemon-{index}")

            saved = json.loads(INSTANCE_DAEMON.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(len(saved["daemon_origin_turn_ids"]), 50)
            self.assertEqual(saved["daemon_origin_turn_ids"][0], "turn-daemon-5")
            self.assertEqual(saved["daemon_origin_turn_ids"][-1], "turn-daemon-54")

    def test_recording_error_persists_last_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )

            state.record_error(origin_turn_id="turn-user-1", message="turn/start failed")

            saved = json.loads(INSTANCE_DAEMON.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["last_error"]["origin_turn_id"], "turn-user-1")
            self.assertEqual(saved["last_error"]["message"], "turn/start failed")
            self.assertRegex(saved["last_error"]["at"], r"^\d{4}-\d{2}-\d{2}T")

    def test_recording_ready_state_persists_pid_and_main_thread_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )

            state.record_ready(pid=4321, main_thread_id="thr-main")

            saved = json.loads(INSTANCE_DAEMON.daemon_state_file(instance_root).read_text(encoding="utf-8"))
            self.assertEqual(saved["ready"]["pid"], 4321)
            self.assertEqual(saved["ready"]["main_thread_id"], "thr-main")
            self.assertRegex(saved["ready"]["at"], r"^\d{4}-\d{2}-\d{2}T")

    def test_ready_for_rejects_other_pid_or_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance_root = self._instance_root(temp_root)
            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance_root,
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )
            state.record_ready(pid=4321, main_thread_id="thr-main")

            self.assertTrue(state.ready_for(4321, "thr-main"))
            self.assertFalse(state.ready_for(9999, "thr-main"))
            self.assertFalse(state.ready_for(4321, "thr-other"))


class StopTaskDaemonFilterTests(unittest.TestCase):
    def _state(self, temp_root: str) -> object:
        instance_root = Path(temp_root) / "instances" / "inst-dev-daemon"
        instance_root.mkdir(parents=True, exist_ok=True)
        return INSTANCE_DAEMON.DaemonState.load(
            instance_root=instance_root,
            instance_id="inst-dev-daemon",
            main_thread_id="thr-main",
        )

    def _completed(self, *, thread_id: str = "thr-main", turn_id: str = "turn-user-1", status: str = "completed") -> dict[str, object]:
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

    def test_real_completed_other_thread_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state = self._state(temp_root)

            previous_turn = INSTANCE_DAEMON.completed_turn_for_stop_tui(
                self._completed(thread_id="thr-side"),
                state,
            )

            self.assertIsNone(previous_turn)

    def test_real_non_completed_statuses_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state = self._state(temp_root)

            self.assertIsNone(INSTANCE_DAEMON.completed_turn_for_stop_tui(self._completed(status="failed"), state))
            self.assertIsNone(INSTANCE_DAEMON.completed_turn_for_stop_tui(self._completed(status="interrupted"), state))
            self.assertIsNone(INSTANCE_DAEMON.completed_turn_for_stop_tui(self._completed(status="inProgress"), state))

    def test_real_daemon_origin_turn_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state = self._state(temp_root)
            state.record_stop_tui_turn(origin_turn_id="turn-user-1", stop_tui_turn_id="turn-daemon-1")

            previous_turn = INSTANCE_DAEMON.completed_turn_for_stop_tui(
                self._completed(turn_id="turn-daemon-1"),
                state,
            )

            self.assertIsNone(previous_turn)

    def test_real_completed_main_thread_user_turn_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            state = self._state(temp_root)

            previous_turn = INSTANCE_DAEMON.completed_turn_for_stop_tui(self._completed(), state)

            self.assertEqual(
                previous_turn,
                {"thread_id": "thr-main", "turn_id": "turn-user-1", "status": "completed"},
            )


class FakeDaemonClient:
    def __init__(self, *, result: dict[str, object] | None = None, error: BaseException | None = None) -> None:
        self.result = result or {"turn": {"id": "turn-daemon-1"}}
        self.error = error
        self.requests: list[dict[str, object]] = []

    def request(self, method: str, params: dict[str, object] | None) -> dict[str, object]:
        self.requests.append({"method": method, "params": params or {}})
        if self.error is not None:
            raise self.error
        return self.result


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


class StopDaemonLoop(RuntimeError):
    pass


class FakeRunDaemonClient:
    def __init__(
        self,
        *,
        notifications: list[dict[str, object] | BaseException],
        bind_result: dict[str, object] | None = None,
        bind_error: BaseException | None = None,
        turn_start_result: dict[str, object] | None = None,
        turn_start_error: BaseException | None = None,
    ) -> None:
        self.notifications = list(notifications)
        self.bind_result = bind_result or {"thread": {"id": "thr-main"}}
        self.bind_error = bind_error
        self.turn_start_result = turn_start_result or {"turn": {"id": "turn-daemon-1"}}
        self.turn_start_error = turn_start_error
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
        if method == "turn/start":
            if self.turn_start_error is not None:
                raise self.turn_start_error
            return self.turn_start_result
        raise AssertionError(f"unexpected request method: {method}")

    def read_notification(self) -> dict[str, object]:
        if not self.notifications:
            raise StopDaemonLoop("stop")
        item = self.notifications.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class StopTaskDaemonSendTests(unittest.TestCase):
    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "inst-dev-daemon"
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload: dict[str, Any] = {
            "instance_id": "inst-dev-daemon",
            "buddy": "dev",
            "status": "active",
            "instance_root": str(instance_root),
            "workspace_dir": str(instance_root / "workspace"),
            "thread_id": "thr-main",
            "app_server_socket": str(instance_root / "runtime" / "app-server.sock"),
        }
        instance_json.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        return {
            "instance_root": instance_root,
            "instance_json": instance_json,
            "payload": payload,
        }

    def _patch_snapshot_render(self) -> list[tuple[str, object]]:
        calls: list[tuple[str, object]] = []

        def fake_current_snapshot(**kwargs: object) -> dict[str, object]:
            calls.append(("snapshot", kwargs))
            return {
                "current_task": {"id": "task-1", "status": "active", "summary": "summary"},
                "last_event": None,
                "progress_summary": "summary",
            }

        def fake_render_stop_task_tui(snapshot: object, previous_turn: object) -> str:
            calls.append(("render", {"snapshot": snapshot, "previous_turn": previous_turn}))
            return "[TASK CHECKOUT]\nContinue -> no task update"

        self.addCleanup(setattr, INSTANCE_DAEMON.task_management, "current_snapshot", INSTANCE_DAEMON.task_management.current_snapshot)
        self.addCleanup(setattr, INSTANCE_DAEMON.task_tui, "render_stop_task_tui", INSTANCE_DAEMON.task_tui.render_stop_task_tui)
        INSTANCE_DAEMON.task_management.current_snapshot = fake_current_snapshot
        INSTANCE_DAEMON.task_tui.render_stop_task_tui = fake_render_stop_task_tui
        return calls

    def _completed(self, *, thread_id: str = "thr-main", turn_id: str = "turn-user-1", status: str = "completed") -> dict[str, object]:
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

    def test_real_completed_turn_sends_one_stop_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = INSTANCE_DAEMON.load_daemon_context(instance["instance_json"])
            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance["instance_root"],
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )
            calls = self._patch_snapshot_render()
            client = FakeDaemonClient(result={"turn": {"id": "turn-daemon-1"}})

            sent = INSTANCE_DAEMON.handle_notification(
                context,
                state,
                client,
                self._completed(),
            )

            self.assertTrue(sent)
            self.assertEqual([request["method"] for request in client.requests], ["turn/start"])
            params = client.requests[0]["params"]
            assert isinstance(params, dict)
            self.assertEqual(params["threadId"], "thr-main")
            self.assertEqual(params["permissions"], "buddyswitch-runtime")
            input_payload = params["input"]
            assert isinstance(input_payload, list)
            prompt = input_payload[0]["text"]
            self.assertTrue(prompt.startswith("[TASK CHECKOUT]"))
            self.assertNotIn("[TASK CONTEXT]", prompt)
            self.assertNotIn("[USER INPUT]", prompt)
            self.assertEqual([name for name, _payload in calls], ["snapshot", "render"])
            self.assertTrue(state.is_daemon_origin_turn("turn-daemon-1"))

    def test_turn_start_failure_records_error_without_retry_or_steer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = INSTANCE_DAEMON.load_daemon_context(instance["instance_json"])
            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance["instance_root"],
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )
            self._patch_snapshot_render()
            client = FakeDaemonClient(
                error=INSTANCE_DAEMON.app_server.AppServerRequestError("turn/start", -32000, "active thread"),
            )

            sent = INSTANCE_DAEMON.handle_notification(
                context,
                state,
                client,
                self._completed(),
            )

            self.assertFalse(sent)
            self.assertEqual([request["method"] for request in client.requests], ["turn/start"])
            saved = json.loads(INSTANCE_DAEMON.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertEqual(saved["last_error"]["origin_turn_id"], "turn-user-1")
            self.assertIn("turn/start failed", saved["last_error"]["message"])
            self.assertFalse(state.is_daemon_origin_turn("turn-user-1"))

            client.error = None
            client.result = {"turn": {"id": "turn-daemon-2"}}
            sent_later = INSTANCE_DAEMON.handle_notification(
                context,
                state,
                client,
                self._completed(turn_id="turn-user-2"),
            )
            self.assertTrue(sent_later)
            self.assertEqual([request["method"] for request in client.requests], ["turn/start", "turn/start"])
            self.assertNotIn("turn/steer", [request["method"] for request in client.requests])


class StopTaskDaemonBindingTests(unittest.TestCase):
    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "inst-dev-daemon"
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload: dict[str, Any] = {
            "instance_id": "inst-dev-daemon",
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
            context = INSTANCE_DAEMON.load_daemon_context(instance["instance_json"])
            client = FakeBindingClient()

            INSTANCE_DAEMON.bind_main_thread(context, client)

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
            context = INSTANCE_DAEMON.load_daemon_context(instance["instance_json"])
            client = FakeBindingClient(result={"thread": {"id": "thr-other"}})

            with self.assertRaises(INSTANCE_DAEMON.app_server.AppServerProtocolError):
                INSTANCE_DAEMON.bind_main_thread(context, client)

    def test_bind_main_thread_fails_on_thread_resume_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            context = INSTANCE_DAEMON.load_daemon_context(instance["instance_json"])
            client = FakeBindingClient(
                error=INSTANCE_DAEMON.app_server.AppServerRequestError("thread/resume", -32000, "resume failed"),
            )

            with self.assertRaises(INSTANCE_DAEMON.app_server.AppServerRequestError):
                INSTANCE_DAEMON.bind_main_thread(context, client)


class StopTaskDaemonLifecycleTests(unittest.TestCase):
    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "inst-dev-daemon"
        instance_root.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload = {
            "instance_id": "inst-dev-daemon",
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
        original_popen = INSTANCE_DAEMON.subprocess.Popen

        class FakeProcess:
            def __init__(self, pid: int) -> None:
                self.pid = pid

            def poll(self) -> None:
                return None

        def fake_popen(command: list[str], **_kwargs: object) -> FakeProcess:
            commands.append(command)
            return FakeProcess(pids.pop(0))

        self.addCleanup(setattr, INSTANCE_DAEMON.subprocess, "Popen", original_popen)
        INSTANCE_DAEMON.subprocess.Popen = fake_popen
        return commands

    def _patch_sleep_to_record_ready(
        self,
        *,
        instance_root: Path,
        pid: int,
        main_thread_id: str = "thr-main",
    ) -> None:
        original_sleep = INSTANCE_DAEMON.time.sleep
        recorded = {"done": False}

        def fake_sleep(_seconds: float) -> None:
            if not recorded["done"]:
                state = INSTANCE_DAEMON.DaemonState.load(
                    instance_root=instance_root,
                    instance_id="inst-dev-daemon",
                    main_thread_id=main_thread_id,
                )
                state.record_ready(pid=pid, main_thread_id=main_thread_id)
                recorded["done"] = True

        self.addCleanup(setattr, INSTANCE_DAEMON.time, "sleep", original_sleep)
        INSTANCE_DAEMON.time.sleep = fake_sleep

    def _patch_monotonic_step(self, *, start: float = 0.0, step: float = 0.1) -> None:
        original_monotonic = INSTANCE_DAEMON.time.monotonic
        current = {"value": start - step}

        def fake_monotonic() -> float:
            current["value"] += step
            return current["value"]

        self.addCleanup(setattr, INSTANCE_DAEMON.time, "monotonic", original_monotonic)
        INSTANCE_DAEMON.time.monotonic = fake_monotonic

    def _patch_ready_constants(self, *, timeout_seconds: float, poll_seconds: float) -> None:
        original_timeout = getattr(INSTANCE_DAEMON, "DAEMON_READY_TIMEOUT_SECONDS", None)
        original_poll = getattr(INSTANCE_DAEMON, "DAEMON_READY_POLL_SECONDS", None)
        if hasattr(INSTANCE_DAEMON, "DAEMON_READY_TIMEOUT_SECONDS"):
            self.addCleanup(setattr, INSTANCE_DAEMON, "DAEMON_READY_TIMEOUT_SECONDS", original_timeout)
        else:
            self.addCleanup(delattr, INSTANCE_DAEMON, "DAEMON_READY_TIMEOUT_SECONDS")
        if hasattr(INSTANCE_DAEMON, "DAEMON_READY_POLL_SECONDS"):
            self.addCleanup(setattr, INSTANCE_DAEMON, "DAEMON_READY_POLL_SECONDS", original_poll)
        else:
            self.addCleanup(delattr, INSTANCE_DAEMON, "DAEMON_READY_POLL_SECONDS")
        INSTANCE_DAEMON.DAEMON_READY_TIMEOUT_SECONDS = timeout_seconds
        INSTANCE_DAEMON.DAEMON_READY_POLL_SECONDS = poll_seconds

    def _patch_exited_process_start(self, pid: int) -> None:
        original_popen = INSTANCE_DAEMON.subprocess.Popen

        class FakeExitedProcess:
            def __init__(self) -> None:
                self.pid = pid

            def poll(self) -> int:
                return 1

        def fake_popen(command: list[str], **_kwargs: object) -> FakeExitedProcess:
            return FakeExitedProcess()

        self.addCleanup(setattr, INSTANCE_DAEMON.subprocess, "Popen", original_popen)
        INSTANCE_DAEMON.subprocess.Popen = fake_popen

    def _patch_pid_live(self, live_pids: set[int]) -> None:
        original_pid_is_live = INSTANCE_DAEMON._pid_is_live
        self.addCleanup(setattr, INSTANCE_DAEMON, "_pid_is_live", original_pid_is_live)
        INSTANCE_DAEMON._pid_is_live = lambda pid: pid in live_pids

    def test_start_creates_runtime_files_and_is_idempotent_when_pid_is_live(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            commands = self._patch_process_start([4321])
            self._patch_pid_live({4321})
            self._patch_sleep_to_record_ready(instance_root=instance["instance_root"], pid=4321)

            first = INSTANCE_DAEMON.start_daemon(instance["instance_json"])
            second = INSTANCE_DAEMON.start_daemon(instance["instance_json"])

            self.assertTrue(first["started"])
            self.assertFalse(second["started"])
            self.assertEqual(first["pid"], 4321)
            self.assertEqual(second["pid"], 4321)
            self.assertTrue(first["ready"])
            self.assertEqual(first["ready_main_thread_id"], "thr-main")
            self.assertTrue(second["ready"])
            self.assertEqual(len(commands), 1)
            self.assertTrue(INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).exists())
            self.assertTrue(INSTANCE_DAEMON.daemon_log_file(instance["instance_root"]).exists())
            self.assertTrue(INSTANCE_DAEMON.daemon_state_file(instance["instance_root"]).exists())

    def test_start_cleans_stale_pid_before_starting_new_daemon(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).parent.mkdir(parents=True, exist_ok=True)
            INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).write_text("9999\n", encoding="utf-8")
            commands = self._patch_process_start([4322])
            self._patch_pid_live({4322})
            self._patch_sleep_to_record_ready(instance_root=instance["instance_root"], pid=4322)

            payload = INSTANCE_DAEMON.start_daemon(instance["instance_json"])

            self.assertTrue(payload["started"])
            self.assertEqual(payload["pid"], 4322)
            self.assertTrue(payload["ready"])
            self.assertEqual(len(commands), 1)
            self.assertEqual(INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).read_text(encoding="utf-8").strip(), "4322")

    def test_start_fails_when_process_exits_before_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            self._patch_exited_process_start(4323)
            self._patch_pid_live(set())

            with self.assertRaises(RuntimeError):
                INSTANCE_DAEMON.start_daemon(instance["instance_json"])

            self.assertFalse(INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).exists())

    def test_start_fails_when_ready_times_out(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            self._patch_process_start([4324])
            self._patch_pid_live({4324})
            self._patch_ready_constants(timeout_seconds=0.2, poll_seconds=0.05)
            self._patch_monotonic_step(start=0.0, step=0.1)
            original_terminate = INSTANCE_DAEMON._terminate_pid
            terminated: list[int] = []
            self.addCleanup(setattr, INSTANCE_DAEMON, "_terminate_pid", original_terminate)
            INSTANCE_DAEMON._terminate_pid = lambda pid: terminated.append(pid) or True

            with self.assertRaises(RuntimeError):
                INSTANCE_DAEMON.start_daemon(instance["instance_json"])

            self.assertEqual(terminated, [4324])
            self.assertFalse(INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).exists())

    def test_start_replaces_live_unready_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).parent.mkdir(parents=True, exist_ok=True)
            INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).write_text("9999\n", encoding="utf-8")
            commands = self._patch_process_start([4325])
            self._patch_pid_live({9999, 4325})
            self._patch_sleep_to_record_ready(instance_root=instance["instance_root"], pid=4325)
            original_terminate = INSTANCE_DAEMON._terminate_pid
            terminated: list[int] = []
            self.addCleanup(setattr, INSTANCE_DAEMON, "_terminate_pid", original_terminate)
            INSTANCE_DAEMON._terminate_pid = lambda pid: terminated.append(pid) or True

            payload = INSTANCE_DAEMON.start_daemon(instance["instance_json"])

            self.assertEqual(terminated, [9999])
            self.assertTrue(payload["started"])
            self.assertEqual(payload["pid"], 4325)
            self.assertTrue(payload["ready"])
            self.assertEqual(len(commands), 1)

    def test_stop_terminates_live_daemon_and_removes_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).parent.mkdir(parents=True, exist_ok=True)
            INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).write_text("4321\n", encoding="utf-8")
            terminated: list[int] = []
            self._patch_pid_live({4321})
            original_terminate = INSTANCE_DAEMON._terminate_pid
            self.addCleanup(setattr, INSTANCE_DAEMON, "_terminate_pid", original_terminate)
            INSTANCE_DAEMON._terminate_pid = lambda pid: terminated.append(pid) or True

            payload = INSTANCE_DAEMON.stop_daemon(instance["instance_json"])

            self.assertTrue(payload["terminated"])
            self.assertEqual(terminated, [4321])
            self.assertFalse(INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).exists())

    def test_status_reports_paths_live_state_and_last_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            state = INSTANCE_DAEMON.DaemonState.load(
                instance_root=instance["instance_root"],
                instance_id="inst-dev-daemon",
                main_thread_id="thr-main",
            )
            state.record_ready(pid=4321, main_thread_id="thr-main")
            state.record_error(origin_turn_id="turn-user-1", message="turn/start failed")
            INSTANCE_DAEMON.daemon_pid_file(instance["instance_root"]).write_text("4321\n", encoding="utf-8")
            self._patch_pid_live({4321})

            payload = INSTANCE_DAEMON.daemon_status(instance["instance_json"])

            self.assertEqual(payload["pid"], 4321)
            self.assertTrue(payload["pid_live"])
            self.assertTrue(payload["live"])
            self.assertTrue(payload["ready"])
            self.assertEqual(payload["ready_main_thread_id"], "thr-main")
            self.assertEqual(payload["log_path"], str(INSTANCE_DAEMON.daemon_log_file(instance["instance_root"])))
            self.assertEqual(payload["state_path"], str(INSTANCE_DAEMON.daemon_state_file(instance["instance_root"])))
            self.assertEqual(payload["last_error"]["origin_turn_id"], "turn-user-1")


class StopTaskDaemonRunLoopTests(unittest.TestCase):
    def _instance(self, temp_root: str) -> dict[str, Any]:
        instance_root = Path(temp_root) / "instances" / "inst-dev-daemon"
        workspace_dir = instance_root / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        instance_json = instance_root / "instance.json"
        payload: dict[str, Any] = {
            "instance_id": "inst-dev-daemon",
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
        original_client = INSTANCE_DAEMON.app_server.AppServerClient

        def fake_factory(*_args: object, **_kwargs: object) -> FakeRunDaemonClient:
            return fake_client

        self.addCleanup(setattr, INSTANCE_DAEMON.app_server, "AppServerClient", original_client)
        INSTANCE_DAEMON.app_server.AppServerClient = fake_factory

    def _patch_snapshot_render(self, *, render_side_effect: list[object] | None = None) -> None:
        original_snapshot = INSTANCE_DAEMON.task_management.current_snapshot
        original_render = INSTANCE_DAEMON.task_tui.render_stop_task_tui
        effects = list(render_side_effect or ["[TASK CHECKOUT]\nContinue -> no task update"])

        def fake_snapshot(**_kwargs: object) -> dict[str, object]:
            return {
                "current_task": {"id": "task-1", "status": "active", "summary": "summary"},
                "last_event": None,
                "progress_summary": "summary",
            }

        def fake_render(_snapshot: object, _previous_turn: object) -> str:
            if not effects:
                return "[TASK CHECKOUT]\nContinue -> no task update"
            effect = effects.pop(0)
            if isinstance(effect, BaseException):
                raise effect
            assert isinstance(effect, str)
            return effect

        self.addCleanup(setattr, INSTANCE_DAEMON.task_management, "current_snapshot", original_snapshot)
        self.addCleanup(setattr, INSTANCE_DAEMON.task_tui, "render_stop_task_tui", original_render)
        INSTANCE_DAEMON.task_management.current_snapshot = fake_snapshot
        INSTANCE_DAEMON.task_tui.render_stop_task_tui = fake_render

    def test_run_daemon_continues_after_notification_idle_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            fake_client = FakeRunDaemonClient(
                notifications=[
                    INSTANCE_DAEMON.app_server.AppServerTimeoutError("idle"),
                    self._completed(turn_id="turn-user-1"),
                    StopDaemonLoop("stop"),
                ],
            )
            self._patch_app_server_client(fake_client)
            self._patch_snapshot_render()

            with self.assertRaises(StopDaemonLoop):
                INSTANCE_DAEMON.run_daemon(instance["instance_json"])

            self.assertEqual([request["method"] for request in fake_client.requests], ["thread/resume", "turn/start"])
            state = json.loads(INSTANCE_DAEMON.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIsNone(state["last_error"])
            self.assertEqual(state["daemon_origin_turn_ids"], ["turn-daemon-1"])

    def test_run_daemon_records_startup_bind_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            fake_client = FakeRunDaemonClient(
                notifications=[],
                bind_error=INSTANCE_DAEMON.app_server.AppServerRequestError("thread/resume", -32000, "resume failed"),
            )
            self._patch_app_server_client(fake_client)

            result = INSTANCE_DAEMON.run_daemon(instance["instance_json"])

            self.assertEqual(result, 1)
            state = json.loads(INSTANCE_DAEMON.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIsNone(state["last_error"]["origin_turn_id"])
            self.assertIn("thread/resume failed", state["last_error"]["message"])

    def test_run_daemon_records_fatal_app_server_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            fake_client = FakeRunDaemonClient(
                notifications=[INSTANCE_DAEMON.app_server.AppServerUnavailableError("socket gone")],
            )
            self._patch_app_server_client(fake_client)

            result = INSTANCE_DAEMON.run_daemon(instance["instance_json"])

            self.assertEqual(result, 1)
            state = json.loads(INSTANCE_DAEMON.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertIsNone(state["last_error"]["origin_turn_id"])
            self.assertIn("socket gone", state["last_error"]["message"])

    def test_run_daemon_records_notification_handler_exception_and_continues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_root:
            instance = self._instance(temp_root)
            fake_client = FakeRunDaemonClient(
                notifications=[
                    self._completed(turn_id="turn-user-1"),
                    self._completed(turn_id="turn-user-2"),
                    StopDaemonLoop("stop"),
                ],
                turn_start_result={"turn": {"id": "turn-daemon-2"}},
            )
            self._patch_app_server_client(fake_client)
            self._patch_snapshot_render(
                render_side_effect=[
                    RuntimeError("renderer exploded"),
                    "[TASK CHECKOUT]\nContinue -> no task update",
                ]
            )

            with self.assertRaises(StopDaemonLoop):
                INSTANCE_DAEMON.run_daemon(instance["instance_json"])

            self.assertEqual([request["method"] for request in fake_client.requests], ["thread/resume", "turn/start"])
            state = json.loads(INSTANCE_DAEMON.daemon_state_file(instance["instance_root"]).read_text(encoding="utf-8"))
            self.assertEqual(state["last_error"]["origin_turn_id"], "turn-user-1")
            self.assertIn("renderer exploded", state["last_error"]["message"])
            self.assertEqual(state["daemon_origin_turn_ids"], ["turn-daemon-2"])


if __name__ == "__main__":
    unittest.main()
